"""Annotate every `genocide` occurrence through a local vLLM server.

**This step is never run by CI and never run by the deploy.** It is the only
thing in the repository that writes model interpretations, and the GitHub Pages
build never runs it. What it produces is therefore a *committed input* —
`model_annotations/genocide/runs/<run_id>/` — read by `15_usage.py` exactly as
the human annotations under `annotations/` are read by 03. See
`model_annotations/README.md`, and docs/PLAN.md §5: no model output may
overwrite corpus text, lexicon counts or human annotations. Nothing here writes
into `annotations/`, into any parquet, or into any lexicon artefact.

The OpenAI-compatible base URL is read from `VLLM_BASE_URL` in the environment,
never from an argument. The server normally binds to loopback on the compute
node, so the annotation job needs no API key and exposes no port. The model id
is still an explicit argument because it identifies the analytical instrument.

A speech whose response fails validation contributes no rows. It is recorded in
`failures.jsonl` with the reason and left absent, because the alternative — a
repaired or retried-until-plausible annotation — is an annotation nobody wrote.
15 reports the resulting coverage gap.

Usage:
    export VLLM_BASE_URL=http://127.0.0.1:8000/v1
    python scripts/14_llm_annotate.py --run-id 2026-09-05-qwen-pilot \\
        --model Qwen/Qwen3.8-27B --reasoning-effort xhigh --limit 25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import annotate, artifacts, audit, console, llm
from lib.annotate import Builder, Outcome, Speech
from lib.paths import INTERIM, MODEL_ANNOTATIONS, ROOT, ensure_dirs, rel

#: The population, columns, ceiling and manifest live in `lib.annotate`, where
#: transport-independent run rules cannot drift from this entry point.
TERM = annotate.TERM
DOCUMENTED_SPEECHES = annotate.DOCUMENTED_SPEECHES
DOCUMENTED_OCCURRENCES = annotate.DOCUMENTED_OCCURRENCES
COLUMNS = annotate.COLUMNS

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
RUNS = STORE / "runs"
SMOKE_RUNS = INTERIM / "model_annotation_smoke"
CURRENT_RUN = STORE / "current_run.txt"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"

#: Raw API bodies, for debugging one run rather than for citing it. Under
#: `data/interim/`, which `.gitignore` excludes: they are large, and they carry
#: nothing the validated rows do not.
RAW = INTERIM / "llm_raw"

#: The server is launched with a 65,536-token context. The output bound remains
#: generous but cannot claim more room than that shared window provides.
MAX_OUTPUT_TOKENS = 65_536

EMPTY_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "cached_tokens": 0,
}


class ResponseTruncated(ValueError):
    """The server reached the output cap before an answer existed."""




# --- The API, kept behind functions so the import stays lazy -----------------


def client(timeout: float = 900.0):
    """A protocol client for the vLLM Responses endpoint.

    Imported lazily so the deterministic pipeline and CI do not install the
    optional SDK.  vLLM requires an API-key-shaped value in the OpenAI client,
    but the loopback server does not authenticate it.
    """
    from openai import OpenAI

    return OpenAI(base_url=os.environ["VLLM_BASE_URL"], api_key="not-used", timeout=timeout)


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
        if reason in {"max_output_tokens", "max_tokens"}:
            raise ResponseTruncated(f"response incomplete ({reason})")
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
    # `cached_tokens` is the share of the input served from the prompt cache and
    # billed at the cached rate. Reported, never inferred: it is the only number
    # that says whether the fixed prefix was actually cached, and a run without
    # it can only guess at what caching saved.
    inputs = usage.get("input_tokens_details")
    cached = inputs.get("cached_tokens", 0) if isinstance(inputs, dict) else 0
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(reasoning or 0),
        "cached_tokens": int(cached or 0),
    }


# --- OpenAI-compatible transport --------------------------------------------


def live(
    api: object,
    speeches: Sequence[Speech],
    build: Builder,
    *,
    model: str,
    effort: str,
    reasoning_location: str,
    temperature: float,
    top_p: float,
    workers: int,
    raw: Path,
    cache_key: str = "",
    on_result: Callable[[Outcome], None] | None = None,
) -> Outcome:
    """Direct Responses API calls, durably yielded one response at a time."""
    outcome = Outcome()

    def ask(speech: Speech) -> tuple[str, dict[str, object] | None, str]:
        body = llm.request_body(
            build(speech),
            model=model,
            reasoning_effort=effort,
            max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
            prompt_cache_key=cache_key,
            reasoning_location=reasoning_location,
            temperature=temperature,
            top_p=top_p,
        )

        try:
            response = api.responses.create(**body)
        except Exception as error:  # recorded as a failure, not retried further
            return speech.custom_id, None, f"{type(error).__name__}: {error}"[:300]
        return speech.custom_id, response.model_dump(mode="json"), ""

    raw_file = raw / f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}.jsonl"
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ask, speech): speech.custom_id for speech in speeches}
        for done, future in enumerate(as_completed(futures), start=1):
            custom_id, body, error = future.result()
            result = Outcome(requests=1)
            if body is None:
                failure = {
                    "custom_id": custom_id,
                    "kind": "transport_refusal",
                    "reason": error,
                    "batch": "live",
                }
                result.failures.append(failure)
                outcome.failures.append(failure)
            else:
                result.responses[custom_id] = body
                outcome.responses[custom_id] = body
                llm.append_rows(
                    raw_file,
                    [{"custom_id": custom_id, "response": {"status_code": 200, "body": body}}],
                )
            outcome.requests += 1
            if on_result is not None:
                on_result(result)
            if done % 25 == 0 or done == len(speeches):
                console.info(f"{done:,}/{len(speeches):,} speeches answered")
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

    `already` names speeches whose complete rows were on disk before this
    scheduler pass began. It guards a resumed run against duplicating durable
    rows. `usage.row_problems` would refuse duplicates rather than repair them,
    which is the right refusal about a fault that should not have happened.
    """
    rows: list[dict[str, object]] = []
    failures = list(outcome.failures)
    invalid = relocated = truncations = 0
    totals = dict(EMPTY_USAGE)

    for custom_id, body in outcome.responses.items():
        speech = scope.get(custom_id)
        if speech is None:
            failures.append(
                {
                    "custom_id": custom_id,
                    "kind": "validation_failure",
                    "reason": "not a speech in this run",
                }
            )
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
        except ResponseTruncated as error:
            truncations += 1
            failures.append(
                {"custom_id": custom_id, "kind": "truncation", "reason": f"truncated: {error}"}
            )
            continue
        except (ValueError, KeyError) as error:
            failures.append(
                {
                    "custom_id": custom_id,
                    "kind": "validation_failure",
                    "reason": f"{type(error).__name__}: {error}",
                }
            )
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
        "truncations": truncations,
        **totals,
    }


def runtime_record(args: argparse.Namespace) -> dict[str, object]:
    """The self-hosted facts required to reproduce a new run."""
    required = {
        "model_revision": "VLLM_MODEL_REVISION",
        "vllm_version": "VLLM_VERSION",
        "gpu_model": "VLLM_GPU_MODEL",
        "gpu_count": "VLLM_GPU_COUNT",
        "max_model_len": "VLLM_MAX_MODEL_LEN",
        "reasoning_parser": "VLLM_REASONING_PARSER",
        "quantization": "VLLM_QUANTIZATION",
        "tensor_parallel_size": "VLLM_TENSOR_PARALLEL_SIZE",
    }
    absent = [variable for variable in required.values() if not os.environ.get(variable)]
    if absent:
        console.fail(
            "The vLLM runtime record is incomplete",
            [f"missing {', '.join(absent)}", "use scripts/cluster/submit_annotate.sh"],
        )
    values = {key: os.environ[variable] for key, variable in required.items()}
    revision = values["model_revision"]
    if len(revision) != 40 or any(character not in "0123456789abcdefABCDEF" for character in revision):
        console.fail("VLLM_MODEL_REVISION must be a full 40-character commit SHA")
    return {
        "route": "openai-compatible-responses",
        "served_model": args.model,
        "model_revision": revision,
        "quantization": values["quantization"],
        "vllm_version": values["vllm_version"],
        "environments": {
            "annotator": "locked+llm-client-overlay",
            "server": "vllm",
        },
        "hardware": {
            "gpu_model": values["gpu_model"],
            "gpu_count": int(values["gpu_count"]),
        },
        "serving": {
            "max_model_len": int(values["max_model_len"]),
            "reasoning_parser": values["reasoning_parser"],
            "tensor_parallel_size": int(values["tensor_parallel_size"]),
            "prefix_caching": True,
            "speculative_decoding": None,
            "moe_backend": os.environ.get("VLLM_MOE_BACKEND") or None,
        },
        "reasoning": {
            "parameter": "reasoning_effort",
            "value": args.reasoning_effort,
            "location": args.reasoning_location,
        },
        "sampling": {"temperature": args.temperature, "top_p": args.top_p},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


# --- Orchestration -----------------------------------------------------------


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    if args.concurrency < 1:
        console.fail("--concurrency must be at least 1")
    if args.limit is not None and args.limit < 1:
        console.fail("--limit must be at least 1")
    if args.temperature < 0 or not 0 < args.top_p <= 1:
        console.fail("sampling values are invalid", ["temperature must be >= 0 and top-p in (0, 1]"])
    if args.smoke and args.limit is None:
        console.fail("--smoke requires --limit", ["a smoke run must never cover the full corpus"])
    if "VLLM_BASE_URL" not in os.environ:
        console.fail(
            "VLLM_BASE_URL is not set",
            [
                "start the pinned vLLM server before running this step",
                "export its OpenAI-compatible /v1 URL; never put the route on the command line",
            ],
        )

    directory = (SMOKE_RUNS if args.smoke else RUNS) / args.run_id
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
    runtime = runtime_record(args)
    if previous.get("runtime") not in (None, runtime):
        console.fail(
            f"Run {args.run_id} was started with a different vLLM runtime",
            ["a changed weight revision or serving configuration requires a new --run-id"],
        )

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

    # Establish the artefact counts once, then update them from each response.
    # Re-reading the full JSONL after every speech would turn a linear run into
    # a quadratic one; relying on memory alone would lose the checkpoint on a
    # walltime kill. Rows, failures and the atomic manifest are therefore all
    # flushed by `checkpoint` before the next completed future is consumed.
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
    outstanding_ids = (
        {str(row.get("custom_id", "")) for row in llm.read_rows(paths["failures"])}
        & {speech.custom_id for speech in speeches if speech.filename not in covered}
    )
    written = len(rows)
    evidence_invalid = sum(1 for row in rows if not row.get("evidence_valid"))
    evidence_relocated = sum(1 for row in rows if row.get("evidence_relocated"))
    mode = "vllm"
    source_commit = artifacts.git_commit(ROOT)
    pass_id = (
        f"{os.environ.get('SLURM_JOB_ID', 'local')}-"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    )
    manifest = previous
    total_appended = total_failures = 0

    def checkpoint(result: Outcome) -> None:
        nonlocal manifest, written, evidence_invalid, evidence_relocated
        nonlocal total_appended, total_failures
        tally = harvest(result, scope, meta, referents, paths, already=frozenset(already))
        total_appended += tally["written"]
        total_failures += tally["failures"]
        written += tally["written"]
        evidence_invalid += tally["evidence_invalid"]
        evidence_relocated += tally["evidence_relocated"]

        result_ids = {*result.responses, *(str(row.get("custom_id", "")) for row in result.failures)}
        successful: set[str] = set()
        if tally["written"]:
            for custom_id in result.responses:
                speech = scope.get(custom_id)
                if speech is not None and tally["written"] == len(speech.occurrences):
                    covered.add(speech.filename)
                    successful.add(custom_id)
        outstanding_ids.difference_update(successful)
        outstanding_ids.update(result_ids - successful)

        manifest = annotate.write_manifest(
            paths["manifest"],
            manifest,
            meta=meta,
            referents_sha256=referents_sha256,
            mode=mode,
            limit=args.limit,
            batch_ids=[],
            planned_requests=len(speeches),
            planned_occurrences=planned_occurrences,
            requests=result.requests,
            returned=annotate.fresh_returns(result.responses, answered),
            complete=len(covered),
            written=written,
            parse_failures=len(outstanding_ids),
            evidence_invalid=evidence_invalid,
            evidence_relocated=evidence_relocated,
            usage={key: tally[key] for key in EMPTY_USAGE},
            runtime=runtime,
            truncations=tally["truncations"],
            pass_id=pass_id,
            source_commit=source_commit,
        )

    api = client()
    if not remaining:
        console.step("Nothing left to ask")
        checkpoint(Outcome())
    else:
        console.step(f"Asking {len(remaining):,} speeches directly ({args.concurrency} at a time)")
        live(
            api,
            remaining,
            build,
            model=args.model,
            effort=args.reasoning_effort,
            reasoning_location=args.reasoning_location,
            temperature=args.temperature,
            top_p=args.top_p,
            workers=args.concurrency,
            raw=raw,
            on_result=checkpoint,
        )

    console.step("Validated and written")
    console.info(f"{total_appended:,} rows appended to {rel(paths['annotations'])}")
    if total_failures:
        console.warn(f"{total_failures} speeches refused; see {rel(paths['failures'])}")

    console.step("Run")
    located = written - int(manifest["evidence_invalid"])
    console.table(
        [
            ("run", manifest["run_id"]),
            ("model", manifest["model"]),
            ("reasoning effort", manifest["reasoning_effort"]),
            ("prompt", f"v{manifest['prompt_version']} {manifest['prompt_sha256'][:12]}"),
            ("speeches", f"{len(covered):,} of {len(speeches):,} complete"),
            ("occurrences", f"{written:,} of {planned_occurrences:,} annotated"),
            ("refused", f"{len(outstanding_ids)} speeches"),
            ("evidence located", f"{located:,} of {written:,}"),
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
        console.info(f"resume with --run-id {args.run_id} and the same model settings")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="e.g. 2026-09-05-qwen-pilot")
    parser.add_argument(
        "--model",
        required=True,
        help="exact served model id, recorded verbatim in every row and the manifest",
    )
    parser.add_argument(
        "--reasoning-effort",
        required=True,
        choices=("low", "medium", "high", "xhigh", "max"),
        help="model-specific requested level; no implicit default",
    )
    parser.add_argument(
        "--reasoning-location",
        required=True,
        choices=("request", "chat_template_kwargs"),
        help="where this model's template reads reasoning_effort",
    )
    parser.add_argument("--limit", type=int, help="pilot: the first N genocide-bearing speeches")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="write under data/interim/model_annotation_smoke; requires --limit",
    )
    parser.add_argument(
        "--retry-failures", action="store_true", help="re-ask only previously refused speeches"
    )
    parser.add_argument("--concurrency", type=int, default=4, help="requests in flight")
    parser.add_argument("--temperature", type=float, required=True, help="sampling temperature")
    parser.add_argument("--top-p", type=float, required=True, help="nucleus-sampling probability")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
