"""Annotate every `genocide` occurrence with a model, once, by hand.

**This step is never run by CI and never run by the deploy.** It is the only
thing in the repository that spends money, and the only thing that cannot be
reproduced by re-running the pipeline: the GitHub Pages build rebuilds all
derived data from the pinned corpus and has no key, no budget and no way to
re-ask a model. What it produces is therefore a *committed input* —
`model_annotations/genocide/runs/<run_id>/` — read by `15_usage.py` exactly as
the human annotations under `annotations/` are read by 03. See
`model_annotations/README.md`, and docs/PLAN.md §5: no model output may
overwrite corpus text, lexicon counts or human annotations. Nothing here writes
into `annotations/`, into any parquet, or into any lexicon artefact.

The key is read from `OPENAI_API_KEY` in the environment. This repository has no
dotenv loader — `.env` is shell configuration for the cluster harness, sourced by
`scripts/cluster/env.sh` and never by a Python step — so export the variable in
your shell for the length of the run. It is never written into a manifest, a row
or a log.

The default path is the **Batch API** over the Responses API: one request per
speech, chunked, with every batch id written into the manifest the moment it
exists, so an interrupted run resumes with `--poll` instead of being resubmitted
and paid for twice. `--live` calls the Responses API directly with bounded
concurrency, for a pilot small enough that waiting a day would be the expensive
part.

A speech whose response fails validation contributes no rows. It is recorded in
`failures.jsonl` with the reason and left absent, because the alternative — a
repaired or retried-until-plausible annotation — is an annotation nobody wrote.
15 reports the resulting coverage gap.

The model this study targets is `gpt-5.6-luna` (Responses + Batch endpoints,
structured outputs, reasoning effort none|low|medium|high|xhigh|max, 128k output
ceiling — developers.openai.com/api/docs/models/gpt-5.6-luna, checked
2026-08-30). Pass the id exactly: the `gpt-5.6` alias routes to Sol, a different
model, and the id recorded in every row is the id that was actually asked.

Usage:
    export OPENAI_API_KEY=...
    python scripts/14_llm_annotate.py --run-id 2026-09-05-luna-v1 \\
        --model gpt-5.6-luna [--reasoning-effort high] [--limit 25] \\
        [--live] [--poll] [--retry-failures]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import annotate, artifacts, audit, console, llm
from lib.annotate import Builder, Outcome, Speech
from lib.paths import INTERIM, MODEL_ANNOTATIONS, ROOT, ensure_dirs, rel

#: The population, the columns, the ceiling and the manifest are 16's too, and
#: live in `lib.annotate` so the two steps cannot drift apart; see its docstring.
TERM = annotate.TERM
DOCUMENTED_SPEECHES = annotate.DOCUMENTED_SPEECHES
DOCUMENTED_OCCURRENCES = annotate.DOCUMENTED_OCCURRENCES
COLUMNS = annotate.COLUMNS
BATCH_CHUNK = annotate.BATCH_CHUNK

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
RUNS = STORE / "runs"
CURRENT_RUN = STORE / "current_run.txt"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"

#: Raw API bodies, for debugging one run rather than for citing it. Under
#: `data/interim/`, which `.gitignore` excludes: they are large, and they carry
#: nothing the validated rows do not.
RAW = INTERIM / "llm_raw"

#: The Batch API's documented terminal states.
BATCH_TERMINAL = frozenset({"completed", "failed", "expired", "cancelled"})

#: The provider's own hard ceiling on one response, which
#: `lib.annotate.output_ceiling` clamps to. 100k sits under Luna's 128k.
MAX_OUTPUT_TOKENS = 100_000

EMPTY_USAGE = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}




# --- The API, kept behind functions so the import stays lazy -----------------


def client(timeout: float = 900.0):
    """An SDK client. Imported here, so CI never needs the package installed."""
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=timeout)


def _transient(error: BaseException) -> bool:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )

    return isinstance(
        error, RateLimitError | APIConnectionError | APITimeoutError | InternalServerError
    )


def with_backoff(call: Callable[[], object], *, attempts: int = 6, base: float = 2.0) -> object:
    """Retry only what the API says is worth retrying, with growing waits."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:
            if attempt == attempts - 1 or not _transient(error):
                raise
            time.sleep(base * 2**attempt + random.uniform(0, 1))
    raise RuntimeError("unreachable")


def output_text(body: dict[str, object]) -> str:
    """The single text output of one Responses API result.

    Refusals and truncation are raised as parse failures rather than smoothed
    over: both mean this speech has no annotation, and saying which one it was
    is the difference between a fixable run and a mysterious one.
    """
    status = str(body.get("status", ""))
    if status == "incomplete":
        details = body.get("incomplete_details")
        reason = details.get("reason", "unknown") if isinstance(details, dict) else "unknown"
        raise ValueError(f"response incomplete ({reason})")
    chunks = []
    for item in body.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise ValueError(f"model refused: {content.get('refusal', '')}"[:300])
            if content.get("type") == "output_text":
                chunks.append(str(content.get("text", "")))
    if not chunks:
        raise ValueError(f"no text output (status {status or 'unknown'})")
    return "".join(chunks)


def usage_of(body: dict[str, object]) -> dict[str, int]:
    """Reported tokens, or zeros. Never estimated."""
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return dict(EMPTY_USAGE)
    details = usage.get("output_tokens_details")
    reasoning = details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(reasoning or 0),
    }


# --- Batch mode --------------------------------------------------------------


def batch_input(
    path: Path, speeches: Sequence[Speech], build: Builder, model: str, effort: str
) -> int:
    """One `/v1/responses` request per speech, one JSON object per line."""
    lines = [
        json.dumps(
            {
                "custom_id": speech.custom_id,
                "method": "POST",
                "url": "/v1/responses",
                "body": llm.request_body(
                    build(speech),
                    model=model,
                    reasoning_effort=effort,
                    max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
                ),
            },
            ensure_ascii=False,
        )
        for speech in speeches
    ]
    artifacts.atomic_write_text(path, "\n".join(lines) + "\n")
    return len(lines)


def submit(
    api: object,
    speeches: Sequence[Speech],
    build: Builder,
    *,
    run_id: str,
    model: str,
    effort: str,
    raw: Path,
) -> tuple[list[str], int]:
    """Upload and create one batch per chunk, returning the ids and what they hold.

    The request count comes back with the ids because it is the only place it
    is known: a chunk that raised before `batches.create` returned sent
    nothing, and a manifest that recorded the intention would be counting a
    request nobody made. The Gemini run's 7,966 is what that costs.
    """
    identifiers = []
    sent = 0
    chunks = [
        speeches[start : start + BATCH_CHUNK] for start in range(0, len(speeches), BATCH_CHUNK)
    ]
    for number, chunk in enumerate(chunks, start=1):
        path = raw / f"batch-{number:03d}.input.jsonl"
        count = batch_input(path, chunk, build, model, effort)

        def upload(path: Path = path) -> object:
            # Reopened per attempt: a retry over a consumed stream uploads an
            # empty file, and the batch that follows would be silently empty.
            with path.open("rb") as stream:
                return api.files.create(file=stream, purpose="batch")

        uploaded = with_backoff(upload)

        def create(input_file_id: str = uploaded.id, chunk_number: int = number) -> object:
            return api.batches.create(
                input_file_id=input_file_id,
                endpoint="/v1/responses",
                completion_window="24h",
                metadata={"run_id": run_id, "chunk": str(chunk_number)},
            )

        batch = with_backoff(create)
        identifiers.append(str(batch.id))
        sent += count
        console.info(f"batch {number}/{len(chunks)}: {batch.id} ({count} requests)")
    return identifiers, sent


def poll(api: object, batch_ids: Sequence[str], *, seconds: int, raw: Path) -> Outcome:
    """Wait for every batch, then read its output and error files."""
    pending = list(batch_ids)
    finished: dict[str, object] = {}
    while pending:
        for batch_id in list(pending):

            def retrieve(identifier: str = batch_id) -> object:
                return api.batches.retrieve(identifier)

            batch = with_backoff(retrieve)
            if batch.status in BATCH_TERMINAL:
                counts = getattr(batch, "request_counts", None)
                detail = f" ({counts.completed} returned, {counts.failed} failed)" if counts else ""
                console.info(f"{batch_id}: {batch.status}{detail}")
                finished[batch_id] = batch
                pending.remove(batch_id)
        if pending:
            console.info(f"{len(pending)} batch(es) still running; next check in {seconds}s")
            time.sleep(seconds)

    outcome = Outcome()
    for batch_id, batch in finished.items():
        for attribute, suffix in (("output_file_id", "output"), ("error_file_id", "errors")):
            file_id = getattr(batch, attribute, None)
            if not file_id:
                continue

            def download(identifier: str = str(file_id)) -> object:
                return api.files.content(identifier)

            content = with_backoff(download)
            payload = content.text if hasattr(content, "text") else content.read().decode("utf-8")
            artifacts.atomic_write_text(raw / f"{batch_id}.{suffix}.jsonl", payload)
            read_results(payload, outcome, batch_id=batch_id)
        if batch.status != "completed":
            console.warn(f"{batch_id} ended as {batch.status}")
    return outcome


def read_results(payload: str, outcome: Outcome, *, batch_id: str) -> None:
    """Split one batch output file into usable bodies and recorded failures."""
    for line in payload.splitlines():
        if not line.strip():
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError as error:
            outcome.failures.append(
                {"custom_id": "", "reason": f"batch line is not JSON: {error}", "batch": batch_id}
            )
            continue
        custom_id = str(result.get("custom_id", ""))
        response = result.get("response") or {}
        status = response.get("status_code")
        if result.get("error") or status != 200:
            reason = result.get("error") or f"HTTP {status}"
            outcome.failures.append(
                {"custom_id": custom_id, "reason": str(reason)[:300], "batch": batch_id}
            )
            continue
        outcome.responses[custom_id] = response.get("body") or {}


# --- Live mode ---------------------------------------------------------------


def live(
    api: object,
    speeches: Sequence[Speech],
    build: Builder,
    *,
    model: str,
    effort: str,
    workers: int,
    raw: Path,
) -> Outcome:
    """Direct Responses API calls, a bounded number of them at a time."""
    outcome = Outcome(requests=len(speeches))

    def ask(speech: Speech) -> tuple[str, dict[str, object] | None, str]:
        body = llm.request_body(
            build(speech),
            model=model,
            reasoning_effort=effort,
            max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
        )

        def call() -> object:
            return api.responses.create(**body)

        try:
            response = with_backoff(call)
        except Exception as error:  # recorded as a failure, not retried further
            return speech.custom_id, None, f"{type(error).__name__}: {error}"[:300]
        return speech.custom_id, response.model_dump(mode="json"), ""

    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, (custom_id, body, error) in enumerate(pool.map(ask, speeches), start=1):
            if body is None:
                outcome.failures.append({"custom_id": custom_id, "reason": error, "batch": "live"})
            else:
                outcome.responses[custom_id] = body
                records.append(
                    json.dumps(
                        {"custom_id": custom_id, "response": {"status_code": 200, "body": body}},
                        ensure_ascii=False,
                    )
                )
            if done % 25 == 0 or done == len(speeches):
                console.info(f"{done:,}/{len(speeches):,} speeches answered")
    if records:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        artifacts.atomic_write_text(raw / f"live-{stamp}.jsonl", "\n".join(records) + "\n")
    return outcome


# --- Turning responses into rows ---------------------------------------------


def harvest(
    outcome: Outcome,
    scope: dict[str, Speech],
    meta: llm.RunMeta,
    referents: set[str],
    paths: dict[str, Path],
    already: frozenset[str] = frozenset(),
) -> dict[str, int]:
    """Validate, locate the evidence, and append. One bad speech loses one speech.

    `already` names the speeches whose rows are on disk. A `--poll` reads every
    batch the manifest records, not only the ones still outstanding, so a
    resumed run downloads answers that were written on an earlier pass;
    appending them a second time corrupts no label — the answers are identical —
    but it doubles the file, and every count taken from it afterwards is wrong.
    `usage.row_problems` would then refuse the run rather than repair it, which
    is the right refusal about a fault that should not have happened.

    16 gained this guard at commit 2fbd205, under load, and 14 did not, because
    the batch path it was found on is the one 14 had already finished with. It
    is the same parameter, doing the same thing, and the two harvests differ now
    only in how a provider names a token.
    """
    rows: list[dict[str, object]] = []
    failures = list(outcome.failures)
    invalid = relocated = 0
    totals = dict(EMPTY_USAGE)

    for custom_id, body in outcome.responses.items():
        speech = scope.get(custom_id)
        if speech is None:
            failures.append({"custom_id": custom_id, "reason": "not a speech in this run"})
            continue
        if speech.filename in already:
            continue
        for key, value in usage_of(body).items():
            totals[key] += value
        try:
            labels = llm.validate_response(
                output_text(body),
                ordinals=[item.ordinal for item in speech.occurrences],
                referents=referents,
            )
            annotated = llm.annotation_rows(speech.occurrences, speech.body, labels, meta)
            for row in annotated:
                llm.validate_row(row, referents)
        except (ValueError, KeyError) as error:
            failures.append({"custom_id": custom_id, "reason": f"{type(error).__name__}: {error}"})
            continue
        invalid += sum(1 for row in annotated if not row["evidence_valid"])
        relocated += sum(1 for row in annotated if row["evidence_relocated"])
        rows.extend(annotated)

    written = llm.append_rows(paths["annotations"], rows) if rows else 0
    if failures:
        llm.append_rows(
            paths["failures"],
            [
                {**failure, "run_id": meta.run_id, "recorded_at": meta.annotated_at}
                for failure in failures
            ],
        )
    return {
        "written": written,
        "failures": len(failures),
        "evidence_invalid": invalid,
        "evidence_relocated": relocated,
        **totals,
    }


# --- Orchestration -----------------------------------------------------------


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    if "OPENAI_API_KEY" not in os.environ:
        console.fail(
            "OPENAI_API_KEY is not set",
            [
                "this step calls a paid API by hand; CI and the deploy never run it",
                "export the key in your shell — it is never written to any artefact",
            ],
        )

    directory = RUNS / args.run_id
    paths = {
        "manifest": directory / "manifest.json",
        "annotations": directory / "annotations.jsonl",
        "failures": directory / "failures.jsonl",
    }

    console.step("Reading the prompt and the controlled referents")
    pack = llm.load_prompt(PROMPT)
    # Current identifiers only, on both paths: the table the model is shown and
    # the set its answers are checked against are the same list, so a retired
    # category cannot be chosen and cannot be accepted if it somehow is.
    referent_list = audit.read_referent_list(REFERENTS)
    referents = referent_list.current
    table = llm.render_referents(llm.read_referent_table(REFERENTS))
    referents_sha256 = artifacts.sha256(REFERENTS)
    console.info(f"prompt version {pack.version}, sha256 {pack.sha256[:12]}")
    console.info(
        f"referent list v{referent_list.version}: {len(referents)} offered, "
        f"sha256 {referents_sha256[:12]}"
    )

    previous = annotate.read_manifest(paths["manifest"])
    annotate.refuse_mismatch(previous, args.run_id, args.model, pack.sha256)

    console.step("Enumerating the term")
    everything, speeches, lexicon_version = annotate.gather(args.limit)
    scope = {speech.custom_id: speech for speech in speeches}
    planned_occurrences = sum(len(speech.occurrences) for speech in speeches)
    enumerated = [item for speech in everything for item in speech.occurrences]

    meta = llm.RunMeta(
        run_id=args.run_id,
        model=args.model,
        prompt_version=pack.version,
        prompt_sha256=pack.sha256,
        reasoning_effort=args.reasoning_effort,
        lexicon_version=str(lexicon_version),
        referents_version=str(referent_list.version),
        term=TERM,
        annotated_at=datetime.now(UTC).date().isoformat(),
    )

    console.step("Choosing what still has to be asked")
    already = llm.completed(
        paths["annotations"], enumerated, prompt_sha256=pack.sha256, model=args.model
    )
    remaining = [speech for speech in speeches if speech.filename not in already]
    refused = {str(row.get("custom_id", "")) for row in llm.read_rows(paths["failures"])}
    if args.retry_failures:
        remaining = [speech for speech in remaining if speech.custom_id in refused]
        console.info(f"--retry-failures: {len(remaining):,} previously refused speeches")
    console.info(f"{len(already):,} speeches already annotated, {len(remaining):,} to go")

    # Every custom_id this run has already had an answer for: the speeches whose
    # rows are on disk, and the speeches whose answers were refused. A --poll
    # re-downloads both, and counting either again is how a manifest comes to
    # report more answers than it ever sent requests.
    answered = frozenset(
        {speech.custom_id for speech in speeches if speech.filename in already} | refused
    )

    raw = RAW / args.run_id
    raw.mkdir(parents=True, exist_ok=True)

    def build(speech: Speech) -> llm.SpeechRequest:
        return llm.build_request(speech.meta, speech.body, speech.occurrences, pack, table)

    direct = args.live or args.retry_failures
    mode = "poll" if args.poll else ("live" if direct else "batch")
    api = client()
    batch_ids: list[str] = []

    if args.poll:
        batch_ids = [str(value) for value in previous.get("batch_ids") or []]
        if not batch_ids:
            console.fail("--poll: the manifest records no batch ids to poll")
        console.step(f"Polling {len(batch_ids)} batch(es)")
        outcome = poll(api, batch_ids, seconds=args.poll_seconds, raw=raw)
    elif not remaining:
        console.step("Nothing left to ask")
        outcome = Outcome()
    elif direct:
        console.step(f"Asking {len(remaining):,} speeches directly ({args.concurrency} at a time)")
        outcome = live(
            api,
            remaining,
            build,
            model=args.model,
            effort=args.reasoning_effort,
            workers=args.concurrency,
            raw=raw,
        )
    else:
        console.step(f"Submitting {len(remaining):,} speeches to the Batch API")
        batch_ids, sent = submit(
            api,
            remaining,
            build,
            run_id=args.run_id,
            model=args.model,
            effort=args.reasoning_effort,
            raw=raw,
        )
        # Before a single result exists: an interrupted run must be resumable
        # with --poll rather than resubmitted and paid for a second time. The
        # count is what `submit` actually created jobs for, so a submission that
        # stopped halfway records the half it paid for.
        annotate.write_manifest(
            paths["manifest"],
            previous,
            meta=meta,
            referents_sha256=referents_sha256,
            mode=mode,
            limit=args.limit,
            batch_ids=batch_ids,
            planned_requests=len(speeches),
            planned_occurrences=planned_occurrences,
            requests=sent,
            returned=0,
            complete=len(already),
            written=len(llm.read_rows(paths["annotations"])),
            parse_failures=0,
            evidence_invalid=0,
            evidence_relocated=0,
            usage=dict(EMPTY_USAGE),
        )
        console.info(f"batch ids recorded in {rel(paths['manifest'])}")
        previous = annotate.read_manifest(paths["manifest"])
        console.step(f"Polling {len(batch_ids)} batch(es)")
        outcome = poll(api, batch_ids, seconds=args.poll_seconds, raw=raw)
        outcome.requests = 0  # the batches were counted when they were created

    console.step("Validating and writing")
    tally = harvest(outcome, scope, meta, referents, paths, already=frozenset(already))
    console.info(f"{tally['written']:,} rows appended to {rel(paths['annotations'])}")
    if tally["failures"]:
        console.warn(f"{tally['failures']} speeches refused; see {rel(paths['failures'])}")

    rows = llm.read_rows(paths["annotations"])
    per_speech: dict[str, int] = {}
    for row in rows:
        name = str(row.get("filename", ""))
        per_speech[name] = per_speech.get(name, 0) + 1
    covered = {
        speech.filename
        for speech in speeches
        if per_speech.get(speech.filename, 0) >= len(speech.occurrences)
    }
    outstanding = len(
        {str(row.get("custom_id", "")) for row in llm.read_rows(paths["failures"])}
        & {speech.custom_id for speech in speeches if speech.filename not in covered}
    )

    manifest = annotate.write_manifest(
        paths["manifest"],
        previous,
        meta=meta,
        referents_sha256=referents_sha256,
        mode=mode,
        limit=args.limit,
        batch_ids=batch_ids,
        planned_requests=len(speeches),
        planned_occurrences=planned_occurrences,
        requests=outcome.requests,
        returned=annotate.fresh_returns(outcome.responses, answered),
        complete=len(covered),
        written=len(rows),
        parse_failures=outstanding,
        evidence_invalid=sum(1 for row in rows if not row.get("evidence_valid")),
        evidence_relocated=sum(1 for row in rows if row.get("evidence_relocated")),
        usage={key: tally[key] for key in EMPTY_USAGE},
    )

    console.step("Run")
    located = len(rows) - int(manifest["evidence_invalid"])
    console.table(
        [
            ("run", manifest["run_id"]),
            ("model", manifest["model"]),
            ("reasoning effort", manifest["reasoning_effort"]),
            ("prompt", f"v{manifest['prompt_version']} {manifest['prompt_sha256'][:12]}"),
            ("speeches", f"{len(covered):,} of {len(speeches):,} complete"),
            ("occurrences", f"{len(rows):,} of {planned_occurrences:,} annotated"),
            ("refused", f"{outstanding} speeches"),
            ("evidence located", f"{located:,} of {len(rows):,}"),
            ("of those relocated", f"{manifest['evidence_relocated']:,}"),
            ("requests", f"{manifest['requests']['sent']:,} sent over "
             f"{len(manifest['passes'])} pass(es)"),
            ("tokens", json.dumps(manifest["usage"])),
            ("status", manifest["status"]),
        ]
    )
    if manifest["status"] == "complete":
        console.info(
            f"commit {rel(directory)}, then put {args.run_id} in {rel(CURRENT_RUN)} to publish it"
        )
    else:
        console.info(f"resume with --poll --run-id {args.run_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="e.g. 2026-09-05-luna-v1")
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "exact API model id, recorded verbatim in every row — for this study "
            "`gpt-5.6-luna`; never the `gpt-5.6` alias, which routes to Sol"
        ),
    )
    # The documented set for the GPT-5.6 family (developers.openai.com, model page
    # for gpt-5.6-luna, checked 2026-08-30). Closed on purpose: a new effort level
    # arriving in the API becomes a reviewable diff here, not a silent pass-through.
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=("none", "low", "medium", "high", "xhigh", "max"),
        help="reasoning effort, default high",
    )
    parser.add_argument("--limit", type=int, help="pilot: the first N genocide-bearing speeches")
    parser.add_argument("--live", action="store_true", help="direct calls instead of the Batch API")
    parser.add_argument("--poll", action="store_true", help="resume: poll the manifest's batch ids")
    parser.add_argument(
        "--retry-failures", action="store_true", help="re-ask only the refused speeches, live"
    )
    parser.add_argument("--poll-seconds", type=int, default=60, help="seconds between batch checks")
    parser.add_argument("--concurrency", type=int, default=4, help="live calls in flight")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
