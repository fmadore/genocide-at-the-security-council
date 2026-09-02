"""Annotate the same 6,092 `genocide` occurrences with a second model, by hand.

**This step is never run by CI and never run by the deploy.** It is 14's sibling
and its counter-instrument: the same corpus, the same enumeration, the same
committed prompt hashed raw into every row, asked of a model from a different
laboratory. One model's reading of the Council is a reading; two independent
readings of the same 6,092 occurrences can disagree, and the size and shape of
that disagreement is a measurement — which is the whole of Phase L8. Nothing
here writes into `annotations/`, into any parquet, or into any lexicon artefact
(docs/PLAN.md §5). What it produces is a committed input,
`model_annotations/genocide/runs/<run_id>/`, read by 15 exactly as 14's run is.

The model is Google's `gemini-3.7-flash` (GA 13 August 2026; thinking levels
low/medium/high, 1,048,576-token context, 65,536-token output ceiling, Batch API
and structured output both supported — ai.google.dev/gemini-api/docs/models/
gemini-3.7-flash, checked 31 August 2026). Pass the id exactly: the id recorded
in every row is the id that was actually asked, and that is the only thing that
tells a reader of the run which of the two readings they are looking at.

The key is read from `GEMINI_API_KEY`, or from `GOOGLE_API_KEY` if that is the
one that is set — the SDK documents both and prefers `GOOGLE_API_KEY` when both
are present (ai.google.dev/gemini-api/docs/api-key), so the chosen value is
passed to the client explicitly and the run reports which variable it came from.
This repository has no dotenv loader — `.env` is shell configuration for the
cluster harness, sourced by `scripts/cluster/env.sh` and never by a Python step —
so export the variable in your shell for the length of the run. It is never
written into a manifest, a row or a log.

The default path is the **Batch API**: one `GenerateContentRequest` per speech,
chunked, submitted as a JSONL file whose `key` is the speech's custom id, with
every job name written into the manifest the moment it exists, so an interrupted
run resumes with `--poll` instead of being resubmitted and paid for twice. Batch
is half price and has a 24-hour target; a job left pending or running for 48
hours expires, which is the second reason the run is chunked — an expiry then
costs one chunk rather than the corpus.

Chunks are created one at a time, each drained before the next is created. The
Batch API meters enqueued tokens rather than jobs, and the whole corpus is about
14.2 million of them; a key with room for one chunk refuses the next with 429
while still accepting a trivial job. Draining first holds the peak at one chunk
and costs wall-clock — up to nine turnarounds in series — which is the trade the
quota imposes, not a preference. `--live` calls `generateContent` directly
with bounded concurrency, for a pilot small enough that waiting a day would be
the expensive part. Batch mechanics and the `{"key": …, "request": …}` line
format: ai.google.dev/gemini-api/docs/batch-api and github.com/google-gemini/
cookbook `quickstarts/Batch_mode.ipynb`, both checked 31 August 2026.

Google now recommends the Interactions API over `generateContent` for 3.x
models. The Batch API has no Interactions form — it is defined over
`GenerateContentRequest` — and batch is what makes 3,273 speeches affordable, so
both paths here use `generateContent`, which the 3.7 Flash model page lists as
supported. `lib.gemini`'s docstring records that choice and where it would
change.

A speech whose response fails validation contributes no rows. It is recorded in
`failures.jsonl` with the reason and left absent, because the alternative — a
repaired or retried-until-plausible annotation — is an annotation nobody wrote.
15 reports the resulting coverage gap.

Usage:
    export GEMINI_API_KEY=...
    python scripts/16_llm_annotate_gemini.py --run-id 2026-09-08-gemini-v1 \\
        --model gemini-3.7-flash [--reasoning-effort high] [--limit 25] \\
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
from lib import artifacts, audit, console, frames, gemini, lexicon, llm
from lib import occurrences as occurrences_lib
from lib.paths import INTERIM, MODEL_ANNOTATIONS, ROOT, SPEECHES_NORM, ensure_dirs, rel

TERM = "genocide"

#: docs/CORPUS.md §8, reproduced exactly by 03, by `lib.occurrences` and by 14.
#: These must equal 14's or the two runs are not two readings of one population
#: and nothing may be joined; `tests/test_gemini.py` asserts they do.
DOCUMENTED_SPEECHES = 3_273
DOCUMENTED_OCCURRENCES = 6_092

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
RUNS = STORE / "runs"
CURRENT_RUN = STORE / "current_run.txt"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"

#: Raw API bodies, for debugging one run rather than for citing it. Under
#: `data/interim/`, which `.gitignore` excludes; shared with 14 and separated by
#: run id, because a raw directory per provider would suggest the two runs are
#: different kinds of thing, and they are deliberately not.
RAW = INTERIM / "llm_raw"

#: Columns this step needs — 14's list exactly, because the request text is 14's
#: request text and a column it does not read is a column the model never sees.
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

#: Requests per batch job. Gemini's own ceiling is a 2 GB input file, far above
#: anything this corpus produces; this is about how much is in flight behind one
#: job name when something goes wrong, about the 48-hour expiry, and about
#: getting the first rows onto disk within hours rather than at the end. It is
#: also the run's peak enqueued-token footprint, because chunks are drained one
#: at a time — roughly 1.7 million tokens at this size.
BATCH_CHUNK = 400

#: A generous ceiling on one speech's answer, the same shape 14 uses so the two
#: runs are given equivalent headroom. Google does not document whether thinking
#: tokens are charged against `maxOutputTokens`, so the bound is generous and a
#: `MAX_TOKENS` finish is recorded as a refusal rather than repaired.
BASE_OUTPUT_TOKENS = 12_000
PER_OCCURRENCE_TOKENS = 1_200
MAX_OUTPUT_TOKENS = gemini.MODEL_OUTPUT_LIMIT

#: `HttpOptions.timeout` is milliseconds in `google-genai`, unlike the OpenAI
#: client's seconds. Fifteen minutes, which is a slow live call and not a hang.
REQUEST_TIMEOUT_MS = 900_000

#: Transport failures the SDK raises as plain httpx exceptions rather than as
#: `google.genai.errors` types. Matched by name so that nothing here has to
#: import httpx, which is the SDK's dependency and not this repository's.
#: httpx raises a small family of transport errors and only some of them were
#: listed here, which made the omissions invisible: a dropped connection reads
#: as `ReadError`, not `ReadTimeout`, so it fell through as permanent and killed
#: a poll outright rather than being retried. The whole of httpx's
#: `TransportError` tree is transient for this step's purposes — every call it
#: makes is either idempotent or guarded by a tighter budget — so the timeouts,
#: the network errors and the protocol errors are all named.
TRANSIENT_TRANSPORT = frozenset(
    {
        "CloseError",
        "ConnectError",
        "ConnectTimeout",
        "LocalProtocolError",
        "PoolTimeout",
        "ProxyError",
        "ReadError",
        "ReadTimeout",
        "RemoteProtocolError",
        "WriteError",
        "WriteTimeout",
    }
)


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

    Reproduced from 14 rather than imported from it: a module cannot be named
    `14_llm_annotate`, and the population the two runs annotate has to be the
    same population or their rows cannot be joined at all. The parity that
    matters — the documented figures and the columns read — is asserted by
    `tests/test_gemini.py` against 14 itself, so the duplication cannot drift
    quietly. Lifting this and the manifest into a shared `lib` module would be
    better still, and is left for a change that may edit both scripts.
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


def client(api_key: str, timeout_ms: int = REQUEST_TIMEOUT_MS):
    """An SDK client. Imported here, so CI never needs the package installed.

    The key is passed rather than left to the SDK's own environment lookup: it
    prefers `GOOGLE_API_KEY` when both variables are set, and a run must be paid
    for by the key this step said it was reading.
    """
    from google import genai

    return genai.Client(api_key=api_key, http_options={"timeout": timeout_ms})


def _transient(error: BaseException) -> bool:
    """Only what Google says is worth asking again: 429, 408 and every 5xx."""
    from google.genai import errors

    if isinstance(error, errors.ServerError):
        return True
    if isinstance(error, errors.ClientError):
        return getattr(error, "code", None) in {408, 429}
    return type(error).__name__ in TRANSIENT_TRANSPORT


#: A poll can run for hours and every call it makes is idempotent, so a network
#: interruption should cost it time rather than the run. Six attempts inside a
#: minute is the right budget for a submission, where a retry that comes too
#: late can create a second job to pay for; it is the wrong one here, and a DNS
#: outage longer than a minute killed two polls of this corpus within an hour.
#: Twelve attempts under a two-minute ceiling tolerate about a quarter of an
#: hour with no network at all.
POLL_ATTEMPTS = 12
POLL_BACKOFF_CAP = 120.0


def with_backoff(
    call: Callable[[], object],
    *,
    attempts: int = 6,
    base: float = 2.0,
    cap: float | None = None,
) -> object:
    """Retry only what the API says is worth retrying, with growing waits.

    `cap` bounds one wait so that a longer budget does not become an unbounded
    one: doubling unchecked reaches hours by the twelfth attempt, which would
    turn a passing outage into a run that appears to have hung.
    """
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:
            if attempt == attempts - 1 or not _transient(error):
                raise
            wait = base * 2**attempt
            time.sleep((wait if cap is None else min(wait, cap)) + random.uniform(0, 1))
    raise RuntimeError("unreachable")


# --- Batch mode --------------------------------------------------------------


def batch_input(path: Path, speeches: Sequence[Speech], build: Builder, effort: str) -> int:
    """One `GenerateContentRequest` per speech, one JSON object per line.

    The model is absent from every line on purpose: the Batch API takes it once,
    at job creation, and a line that named one would either be ignored or
    contradict the job.
    """
    lines = [
        json.dumps(
            gemini.batch_line(
                build(speech),
                thinking_level=effort,
                max_output_tokens=output_ceiling(speech),
            ),
            ensure_ascii=False,
        )
        for speech in speeches
    ]
    artifacts.atomic_write_text(path, "\n".join(lines) + "\n")
    return len(lines)


def merge(into: Outcome, part: Outcome) -> None:
    """Fold one chunk's returned work into the run's running total."""
    into.responses.update(part.responses)
    into.failures.extend(part.failures)
    into.submitted += part.submitted


def quota_refusal(error: BaseException) -> bool:
    """A 429 that outlived `with_backoff` — the quota itself, not a spike."""
    from google.genai import errors

    return isinstance(error, errors.ClientError) and getattr(error, "code", None) == 429


def submit_and_drain(
    api: object,
    speeches: Sequence[Speech],
    build: Builder,
    *,
    run_id: str,
    model: str,
    effort: str,
    raw: Path,
    seconds: int,
    chunk_size: int = BATCH_CHUNK,
    on_job: Callable[[list[str]], None] = lambda _names: None,
) -> tuple[list[str], Outcome]:
    """Create one job per chunk, draining each before the next is created.

    Creating all nine jobs first would need the whole corpus enqueued at once —
    about 14.2 million input tokens — and the Batch API meters *enqueued tokens*,
    not jobs or money: a paid key with room for one chunk refuses the second with
    429 while still accepting a twenty-token job, and `with_backoff` cannot wait
    that out because nothing drains while it sleeps. Draining each chunk before
    the next is created holds the peak at one chunk, which is what lets the run
    finish under an ordinary quota. The price is wall-clock — up to nine batch
    turnarounds in series rather than nine in parallel.

    `on_job` records every name the moment it exists, before the next upload is
    attempted. Creating a job is not idempotent, so a name that exists but has
    not been recorded is a job that will be paid for and cannot be polled.

    A refusal on a later chunk stops the submission instead of raising: the
    chunks already drained are returned so their answers can still be written,
    and the next invocation asks for whatever is missing. Raising here would
    throw away work already paid for and downloaded.
    """
    names: list[str] = []
    outcome = Outcome()
    chunks = [
        speeches[start : start + chunk_size] for start in range(0, len(speeches), chunk_size)
    ]
    for number, chunk in enumerate(chunks, start=1):
        path = raw / f"batch-{number:03d}.input.jsonl"
        count = batch_input(path, chunk, build, effort)

        def upload(path: Path = path, chunk_number: int = number) -> object:
            # Re-read per attempt rather than held open: a retry over a consumed
            # stream uploads an empty file, and the job that follows would be
            # silently empty. Creating a job is not idempotent, so a duplicate
            # would be a second job to pay for and not a no-op.
            # `mime_type` is passed explicitly because `mimetypes` has no entry
            # for `.jsonl` on any platform, and the SDK raises rather than
            # guessing, so a batch input file would otherwise never upload at
            # all. `jsonl` is the spelling Google's own batch documentation
            # passes (ai.google.dev/gemini-api/docs/batch-api, checked
            # 31 August 2026); the service also accepts `application/jsonl` and
            # `application/json`, and stores back whichever it was given.
            return api.files.upload(
                file=str(path),
                config={
                    "display_name": f"{run_id}-{chunk_number:03d}",
                    "mime_type": "jsonl",
                },
            )

        try:
            uploaded = with_backoff(upload)

            def create(source: str = str(uploaded.name), chunk_number: int = number) -> object:
                return api.batches.create(
                    model=model,
                    src=source,
                    config={"display_name": f"{run_id}-{chunk_number:03d}"},
                )

            job = with_backoff(create)
        except Exception as error:
            if not quota_refusal(error):
                raise
            console.warn(f"chunk {number} of {len(chunks)} refused: the batch quota is full")
            console.info("what drained is kept; run the step again to ask for the rest")
            break

        names.append(str(job.name))
        console.info(f"job {number}/{len(chunks)}: {job.name} ({count} requests)")
        on_job(list(names))
        console.step(f"Draining job {number}/{len(chunks)} before creating the next")
        merge(outcome, poll(api, [str(job.name)], seconds=seconds, raw=raw))
    return names, outcome


def poll(api: object, job_names: Sequence[str], *, seconds: int, raw: Path) -> Outcome:
    """Wait for every job, then read the result file each one points at."""
    pending = list(job_names)
    finished: dict[str, object] = {}
    while pending:
        for name in list(pending):

            def retrieve(identifier: str = name) -> object:
                return api.batches.get(name=identifier)

            job = with_backoff(retrieve, attempts=POLL_ATTEMPTS, cap=POLL_BACKOFF_CAP)
            state = gemini.job_state(job)
            if state in gemini.TERMINAL_STATES:
                console.info(f"{name}: {state}")
                finished[name] = job
                pending.remove(name)
        if pending:
            console.info(f"{len(pending)} job(s) still running; next check in {seconds}s")
            time.sleep(seconds)

    outcome = Outcome()
    for name, job in finished.items():
        state = gemini.job_state(job)
        destination = getattr(job, "dest", None)
        result_file = str(getattr(destination, "file_name", "") or "")
        if result_file:

            def download(identifier: str = result_file) -> object:
                return api.files.download(file=identifier)

            content = with_backoff(download, attempts=POLL_ATTEMPTS, cap=POLL_BACKOFF_CAP)
            payload = (
                content.decode("utf-8") if isinstance(content, bytes | bytearray) else str(content)
            )
            artifacts.atomic_write_text(raw / f"{name.split('/')[-1]}.output.jsonl", payload)
            read_results(payload, outcome, job_name=name)
        if state != "JOB_STATE_SUCCEEDED":
            error = getattr(job, "error", None)
            console.warn(f"{name} ended as {state}{f': {error}' if error else ''}")
            if not result_file:
                outcome.failures.append(
                    {"custom_id": "", "reason": f"{state}: {error}"[:300], "batch": name}
                )
    return outcome


def read_results(payload: str, outcome: Outcome, *, job_name: str) -> None:
    """Split one result file into usable responses and recorded failures."""
    for line in payload.splitlines():
        if not line.strip():
            continue
        custom_id, response, reason = gemini.read_result_line(line)
        if response is None:
            outcome.failures.append({"custom_id": custom_id, "reason": reason, "batch": job_name})
            continue
        outcome.responses[custom_id] = response


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
    """Direct `generateContent` calls, a bounded number of them at a time."""
    outcome = Outcome(submitted=len(speeches))

    def ask(speech: Speech) -> tuple[str, dict[str, object] | None, str]:
        body = gemini.request_body(
            build(speech),
            thinking_level=effort,
            max_output_tokens=output_ceiling(speech),
        )

        def call() -> object:
            return api.models.generate_content(model=model, **gemini.generate_kwargs(body))

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
                records.append(json.dumps({"key": custom_id, "response": body}, ensure_ascii=False))
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
    job the manifest records, not only the ones still outstanding, so a resumed
    run downloads answers that were written on an earlier pass; appending them a
    second time corrupts no label — the answers are identical — but it doubles
    the file, and every count taken from it afterwards is wrong.
    """
    rows: list[dict[str, object]] = []
    failures = list(outcome.failures)
    invalid = 0
    totals = dict(gemini.EMPTY_USAGE)

    for custom_id, body in outcome.responses.items():
        speech = scope.get(custom_id)
        if speech is None:
            failures.append({"custom_id": custom_id, "reason": "not a speech in this run"})
            continue
        if speech.filename in already:
            continue
        for key, value in gemini.usage_of(body).items():
            totals[key] += value
        try:
            labels = llm.validate_response(
                gemini.output_text(body),
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
            [
                {**failure, "run_id": meta.run_id, "recorded_at": meta.annotated_at}
                for failure in failures
            ],
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

    14's key set exactly, including `batch_ids` — which here hold Gemini job
    resource names of the form `batches/<n>` rather than OpenAI batch ids. A
    provider key is deliberately absent: `model` already names the provider
    beyond ambiguity, and L8's comparison reads two manifests that have to have
    one shape. `reasoning_effort` carries Google's own `thinkingLevel`.

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
        "referents_version": meta.referents_version,
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
        # Null, always. Batch is documented at half the interactive price, but
        # the API reports tokens and never a price, and a number written here
        # from a pricing page would be a figure in a research manifest that
        # nothing produced.
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


def read_key() -> tuple[str, str]:
    """The key, or a refusal in words. Before anything else is read or spent."""
    try:
        return gemini.resolve_api_key(os.environ)
    except KeyError:
        console.fail(
            "Neither GEMINI_API_KEY nor GOOGLE_API_KEY is set",
            [
                "this step calls a paid API by hand; CI and the deploy never run it",
                "export the key in your shell — it is never written to any artefact",
                "GEMINI_API_KEY is preferred; GOOGLE_API_KEY is read only as a fallback",
            ],
        )
        raise  # unreachable: console.fail exits


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    key_variable, api_key = read_key()
    console.info(f"key read from {key_variable}")

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
        referents_version=str(referent_list.version),
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
    api = client(api_key)
    batch_ids: list[str] = []

    if args.poll:
        try:
            batch_ids = gemini.job_names(previous.get("batch_ids") or [])
        except ValueError as error:
            console.fail(
                f"--poll: {rel(paths['manifest'])} records something that is not a job name",
                [str(error), "Gemini job names look like batches/123456789"],
            )
        if not batch_ids:
            console.fail("--poll: the manifest records no batch job names to poll")
        console.step(f"Polling {len(batch_ids)} job(s)")
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

        # Before a single result exists: creating a job is not idempotent, so an
        # interrupted run must be resumable with --poll rather than resubmitted
        # and paid for a second time. Called after every `create`, not after the
        # loop, because a refusal on a later chunk would otherwise leave the
        # earlier jobs running with their names written down nowhere.
        def record(names: list[str]) -> None:
            write_manifest(
                paths["manifest"],
                previous,
                meta=meta,
                referents_sha256=referents_sha256,
                mode=mode,
                limit=args.limit,
                batch_ids=names,
                planned_requests=len(speeches),
                planned_occurrences=planned_occurrences,
                submitted=len(remaining),
                returned=0,
                complete=len(already),
                written=len(llm.read_rows(paths["annotations"])),
                parse_failures=0,
                evidence_invalid=0,
                usage=dict(gemini.EMPTY_USAGE),
            )

        batch_ids, outcome = submit_and_drain(
            api,
            remaining,
            build,
            run_id=args.run_id,
            model=args.model,
            effort=args.reasoning_effort,
            raw=raw,
            seconds=args.poll_seconds,
            chunk_size=args.chunk_size,
            on_job=record,
        )
        record(batch_ids)
        console.info(f"job names recorded in {rel(paths['manifest'])}")
        previous = read_manifest(paths["manifest"])

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
        usage={key: tally[key] for key in gemini.EMPTY_USAGE},
    )

    console.step("Run")
    located = len(rows) - int(manifest["evidence_invalid"])
    console.table(
        [
            ("run", manifest["run_id"]),
            ("model", manifest["model"]),
            ("thinking level", manifest["reasoning_effort"]),
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
    parser.add_argument("--run-id", required=True, help="e.g. 2026-09-08-gemini-v1")
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "exact API model id, recorded verbatim in every row — for this study "
            f"`{gemini.MODEL_ID}`; never a `-latest` alias, which moves under the run"
        ),
    )
    # Google's own vocabulary for this knob is `thinkingLevel`; the flag keeps
    # 14's name because it is the same dial and every row records it in the same
    # `reasoning_effort` field. `minimal` is absent because 3.7 Flash rejects it.
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=gemini.THINKING_LEVELS,
        help="thinkingLevel, sent as generationConfig.thinkingConfig; default high",
    )
    parser.add_argument("--limit", type=int, help="pilot: the first N genocide-bearing speeches")
    parser.add_argument("--live", action="store_true", help="direct calls instead of the Batch API")
    parser.add_argument("--poll", action="store_true", help="resume: poll the manifest's job names")
    parser.add_argument(
        "--retry-failures", action="store_true", help="re-ask only the refused speeches, live"
    )
    parser.add_argument("--poll-seconds", type=int, default=60, help="seconds between job checks")
    # The enqueued-token quota is a moving target: it is spent by everything
    # asked of the key that day, so the size that was accepted in the morning
    # can be refused in the evening with nothing in flight at all. Tuning this
    # down is how a run finishes on what is left rather than waiting for a
    # window to reset.
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=BATCH_CHUNK,
        help=f"speeches per batch job; lower it when the quota refuses (default {BATCH_CHUNK})",
    )
    parser.add_argument("--concurrency", type=int, default=4, help="live calls in flight")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
