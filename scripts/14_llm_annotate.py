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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, audit, console, frames, lexicon, llm
from lib import occurrences as occurrences_lib
from lib.paths import INTERIM, MODEL_ANNOTATIONS, ROOT, SPEECHES_NORM, ensure_dirs, rel

TERM = "genocide"

#: docs/CORPUS.md §8, reproduced exactly by 03 and by `lib.occurrences`. A run
#: that enumerates anything else is annotating a different corpus, and its rows
#: could not be joined to the published counts. Only `--limit` may leave this
#: unmet, and the manifest records the limit that did.
DOCUMENTED_SPEECHES = 3_273
DOCUMENTED_OCCURRENCES = 6_092

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
RUNS = STORE / "runs"
CURRENT_RUN = STORE / "current_run.txt"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"

#: Raw API bodies, for debugging one run rather than for citing it. Under
#: `data/interim/`, which `.gitignore` excludes: they are large, and they carry
#: nothing the validated rows do not.
RAW = INTERIM / "llm_raw"

#: Columns this step needs. The normalised frame is 99 columns and 389 MB of
#: text; reading all of it to use eight of them is a minute of nothing.
COLUMNS = [
    "filename",
    "body_start",
    "text",
    "date",
    "meeting_symbol",
    "country_org",
    "agenda_item_manual",
    "participanttype",
]

#: Requests per batch file. The API's own ceilings are far higher; this is about
#: how much is in flight behind one id when something goes wrong, and about
#: getting the first rows onto disk within hours rather than at the end.
BATCH_CHUNK = 400

#: The Batch API's documented terminal states.
BATCH_TERMINAL = frozenset({"completed", "failed", "expired", "cancelled"})

#: A generous ceiling on one speech's answer. Reasoning tokens count against
#: this in the Responses API, so at effort `high` the bound has to cover the
#: thinking as well as the JSON. A truncated response loses a whole speech to a
#: parse failure, which costs more than the headroom.
BASE_OUTPUT_TOKENS = 12_000
PER_OCCURRENCE_TOKENS = 1_200
MAX_OUTPUT_TOKENS = 100_000

EMPTY_USAGE = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}


@dataclass(frozen=True)
class Speech:
    """One speech in scope, with everything a request and its rows need."""

    filename: str
    custom_id: str
    body: str
    meta: dict[str, object]
    occurrences: list[occurrences_lib.Occurrence]


@dataclass
class Outcome:
    """What one pass returned, before anything is written."""

    responses: dict[str, dict[str, object]] = field(default_factory=dict)
    failures: list[dict[str, object]] = field(default_factory=list)
    submitted: int = 0


Builder = Callable[[Speech], llm.SpeechRequest]


# --- Reading what is to be annotated ----------------------------------------


def gather(limit: int | None) -> tuple[list[Speech], list[Speech], int]:
    """Every genocide-bearing speech, in corpus order, with its occurrences.

    Returns the whole enumeration and the slice this run is asking about. The
    two differ only under `--limit`, and both are needed: the scope says what to
    ask, while the resume check has to see every occurrence the corpus has, or a
    pilot re-run would read rows from a fuller run as evidence that the corpus
    had moved.
    """
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)
    lex = lexicon.load()
    console.info(f"lexicon version {lex.version} ({lex.updated})")

    found = occurrences_lib.enumerate_term(speeches, bodies, lex.terms[TERM])
    grouped: dict[object, list[occurrences_lib.Occurrence]] = {}
    for occurrence in found:
        grouped.setdefault(occurrence.index, []).append(occurrence)
    console.info(f"{len(found):,} occurrences in {len(grouped):,} speeches")

    if limit is None and (
        len(found) != DOCUMENTED_OCCURRENCES or len(grouped) != DOCUMENTED_SPEECHES
    ):
        console.fail(
            "The enumeration does not reproduce the documented figures",
            [
                f"speeches {len(grouped):,} vs {DOCUMENTED_SPEECHES:,}",
                f"occurrences {len(found):,} vs {DOCUMENTED_OCCURRENCES:,}",
                "run 03 and read docs/VALIDATION.md before spending an API call",
            ],
        )

    everything = []
    for index, items in grouped.items():
        row = speeches.loc[index]
        filename = str(row["filename"])
        everything.append(
            Speech(
                filename=filename,
                custom_id=filename.removesuffix(".txt"),
                body=str(bodies.loc[index]),
                meta={column: row[column] for column in COLUMNS if column != "text"},
                occurrences=items,
            )
        )
    scope = everything
    if limit is not None:
        scope = everything[:limit]
        console.warn(f"--limit {limit}: {len(scope):,} speeches, a pilot and not the corpus")
    return everything, scope, lex.version


def output_ceiling(speech: Speech) -> int:
    return min(
        MAX_OUTPUT_TOKENS,
        BASE_OUTPUT_TOKENS + PER_OCCURRENCE_TOKENS * len(speech.occurrences),
    )


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
                    max_output_tokens=output_ceiling(speech),
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
) -> list[str]:
    """Upload and create one batch per chunk, returning the ids as they appear."""
    identifiers = []
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
        console.info(f"batch {number}/{len(chunks)}: {batch.id} ({count} requests)")
    return identifiers


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
    outcome = Outcome(submitted=len(speeches))

    def ask(speech: Speech) -> tuple[str, dict[str, object] | None, str]:
        body = llm.request_body(
            build(speech),
            model=model,
            reasoning_effort=effort,
            max_output_tokens=output_ceiling(speech),
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
) -> dict[str, int]:
    """Validate, locate the evidence, and append. One bad speech loses one speech."""
    rows: list[dict[str, object]] = []
    failures = list(outcome.failures)
    invalid = 0
    totals = dict(EMPTY_USAGE)

    for custom_id, body in outcome.responses.items():
        speech = scope.get(custom_id)
        if speech is None:
            failures.append({"custom_id": custom_id, "reason": "not a speech in this run"})
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
        rows.extend(annotated)

    written = llm.append_rows(paths["annotations"], rows) if rows else 0
    if failures:
        llm.append_rows(
            paths["failures"],
            [{**failure, "run_id": meta.run_id, "recorded_at": meta.annotated_at} for failure in failures],
        )
    return {"written": written, "failures": len(failures), "evidence_invalid": invalid, **totals}


# --- The manifest ------------------------------------------------------------


def read_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(
    path: Path,
    previous: dict[str, object],
    *,
    meta: llm.RunMeta,
    referents_sha256: str,
    mode: str,
    limit: int | None,
    batch_ids: Sequence[str],
    planned_requests: int,
    planned_occurrences: int,
    submitted: int,
    returned: int,
    complete: int,
    written: int,
    parse_failures: int,
    evidence_invalid: int,
    usage: dict[str, int],
) -> dict[str, object]:
    """One manifest per run, rewritten atomically after every pass.

    Counts that describe effort — requests submitted and returned, tokens — add
    to what a previous pass recorded, because a resumed run did that work too.
    Counts that describe the artefact — occurrences written, speeches complete,
    parse failures still outstanding — are measured from the files on disk, so
    they cannot drift from what the run actually contains.
    """
    before = previous.get("requests") if isinstance(previous.get("requests"), dict) else {}
    tokens = previous.get("usage") if isinstance(previous.get("usage"), dict) else {}
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    done = planned_requests > 0 and complete >= planned_requests
    manifest = {
        "run_id": meta.run_id,
        "term": meta.term,
        "model": meta.model,
        "reasoning_effort": meta.reasoning_effort,
        "prompt_version": meta.prompt_version,
        "prompt_sha256": meta.prompt_sha256,
        "referents_sha256": referents_sha256,
        "lexicon_version": meta.lexicon_version,
        "schema_version": llm.SCHEMA_VERSION,
        "mode": mode,
        "limit": limit,
        "created": previous.get("created", now),
        "completed": now if done else None,
        "git_commit": artifacts.git_commit(ROOT),
        "batch_ids": sorted({*(previous.get("batch_ids") or []), *batch_ids}),
        "requests": {
            "planned": planned_requests,
            "submitted": int(before.get("submitted", 0)) + submitted,
            "returned": int(before.get("returned", 0)) + returned,
            "complete": complete,
        },
        "occurrences": {"planned": planned_occurrences, "written": written},
        "parse_failures": parse_failures,
        "evidence_invalid": evidence_invalid,
        "usage": {key: int(tokens.get(key, 0)) + value for key, value in usage.items()},
        # Null, always, unless the API starts reporting a price. Tokens are
        # reported; prices are not, and a number written here from memory would
        # be a figure in a research manifest that nothing produced.
        "cost_usd": None,
        "status": "complete" if done else "in_progress",
    }
    artifacts.atomic_write_json(path, manifest, indent=1)
    return manifest


# --- Orchestration -----------------------------------------------------------


def refuse_mismatch(previous: dict[str, object], run_id: str, model: str, digest: str) -> None:
    """A run is one prompt and one model. A change to either is a new run id."""
    if previous.get("status") == "complete":
        console.fail(
            f"Run {run_id} is already complete",
            ["its manifest says so; publishing a second reading needs a new --run-id"],
        )
    if previous and str(previous.get("model")) != model:
        console.fail(
            f"Run {run_id} was started with model {previous.get('model')}",
            [f"--model {model} would mix two models in one file; use a new --run-id"],
        )
    if previous and str(previous.get("prompt_sha256")) != digest:
        console.fail(
            f"Run {run_id} was started with a different prompt",
            [
                f"manifest {str(previous.get('prompt_sha256'))[:12]}..., file {digest[:12]}...",
                "a changed prompt is a new prompt version and a new --run-id",
            ],
        )


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
    referents = audit.read_referents(REFERENTS)
    table = llm.render_referents(llm.read_referent_table(REFERENTS))
    referents_sha256 = artifacts.sha256(REFERENTS)
    console.info(f"prompt version {pack.version}, sha256 {pack.sha256[:12]}")
    console.info(f"{len(referents)} controlled referents, sha256 {referents_sha256[:12]}")

    previous = read_manifest(paths["manifest"])
    refuse_mismatch(previous, args.run_id, args.model, pack.sha256)

    console.step("Enumerating the term")
    everything, speeches, lexicon_version = gather(args.limit)
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
        term=TERM,
        annotated_at=datetime.now(UTC).date().isoformat(),
    )

    console.step("Choosing what still has to be asked")
    already = llm.completed(
        paths["annotations"], enumerated, prompt_sha256=pack.sha256, model=args.model
    )
    remaining = [speech for speech in speeches if speech.filename not in already]
    if args.retry_failures:
        refused = {str(row.get("custom_id", "")) for row in llm.read_rows(paths["failures"])}
        remaining = [speech for speech in remaining if speech.custom_id in refused]
        console.info(f"--retry-failures: {len(remaining):,} previously refused speeches")
    console.info(f"{len(already):,} speeches already annotated, {len(remaining):,} to go")

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
        batch_ids = submit(
            api,
            remaining,
            build,
            run_id=args.run_id,
            model=args.model,
            effort=args.reasoning_effort,
            raw=raw,
        )
        # Before a single result exists: an interrupted run must be resumable
        # with --poll rather than resubmitted and paid for a second time.
        write_manifest(
            paths["manifest"],
            previous,
            meta=meta,
            referents_sha256=referents_sha256,
            mode=mode,
            limit=args.limit,
            batch_ids=batch_ids,
            planned_requests=len(speeches),
            planned_occurrences=planned_occurrences,
            submitted=len(remaining),
            returned=0,
            complete=len(already),
            written=len(llm.read_rows(paths["annotations"])),
            parse_failures=0,
            evidence_invalid=0,
            usage=dict(EMPTY_USAGE),
        )
        console.info(f"batch ids recorded in {rel(paths['manifest'])}")
        previous = read_manifest(paths["manifest"])
        console.step(f"Polling {len(batch_ids)} batch(es)")
        outcome = poll(api, batch_ids, seconds=args.poll_seconds, raw=raw)

    console.step("Validating and writing")
    tally = harvest(outcome, scope, meta, referents, paths)
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

    manifest = write_manifest(
        paths["manifest"],
        previous,
        meta=meta,
        referents_sha256=referents_sha256,
        mode=mode,
        limit=args.limit,
        batch_ids=batch_ids,
        planned_requests=len(speeches),
        planned_occurrences=planned_occurrences,
        submitted=outcome.submitted,
        returned=len(outcome.responses),
        complete=len(covered),
        written=len(rows),
        parse_failures=outstanding,
        evidence_invalid=sum(1 for row in rows if not row.get("evidence_valid")),
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
