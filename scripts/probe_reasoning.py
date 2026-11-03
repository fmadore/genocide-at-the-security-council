"""Demonstrate a served model's reasoning ladder before an annotation run.

The probe sends the same small set of corpus speeches at every declared level,
records latency and reported reasoning tokens, and refuses a flat ladder. Its
artefact lives under ``data/interim``: it is operational evidence, never a
model annotation and never input to a published figure.

The speeches are the first `--speeches` genocide-bearing speeches in corpus
order, from a pool that holds `--spares` more. A speech whose answer is cut
off at the output limit at any level is skipped, recorded under `skipped`
with the level, and the next in the pool takes its place; any other invalid
answer still stops the probe. Gemma, thinking at temperature 0, can reason
until the limit on one particular text (on v6.0's SC00211-01-007, the first in
the corpus, it did): that says something about the speech, which the run then
records as a failure, not about whether the ladder works. The pool, not the
speeches that were answered, is what the probe's identity and step 14 bind.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import annotate, artifacts, audit, console, llm, model_runs, probes, prompts, run_store
from lib.paths import INTERIM, rel
from lib.text import sentence_spans

STORE = model_runs.STORE
PROMPT = model_runs.PROMPT
REFERENTS = model_runs.REFERENTS
PROBES = INTERIM / "model_annotation_probes"
MAX_OUTPUT_TOKENS = 65_536


def annotation_step():
    """Load the numeric entry point without inventing a second transport."""
    path = Path(__file__).resolve().parent / "14_llm_annotate.py"
    spec = importlib.util.spec_from_file_location("vllm_annotation_probe_transport", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
        console.fail("run-id must be a single safe directory name")
    if args.speeches < 1:
        console.fail("--speeches must be at least 1")
    if args.spares < 0:
        console.fail("--spares cannot be negative")
    levels = [level.strip() for level in args.levels.split(",") if level.strip()]
    if len(levels) < 2 or len(levels) != len(set(levels)):
        console.fail("The reasoning probe needs at least two distinct levels")
    destination = PROBES / args.run_id / "probe.json"
    identity = {
        "model": args.model,
        "model_revision": args.model_revision,
        "reasoning_location": args.reasoning_location,
        "levels_requested": levels,
        "speeches_per_level": args.speeches,
        "candidates": args.speeches + args.spares,
    }
    step = annotation_step()
    pack = prompts.load_prompt(PROMPT)
    referent_list = audit.read_referent_list(REFERENTS)
    referents = referent_list.current
    table = llm.render_referents(llm.read_referent_table(REFERENTS))
    _, speeches, _ = annotate.gather(args.speeches + args.spares)
    runtime_args = argparse.Namespace(**vars(args), reasoning_effort=levels[-1])
    identity.update({
        "prompt_sha256": pack.sha256,
        "referents_sha256": artifacts.sha256(REFERENTS),
        "schema_version": llm.SCHEMA_VERSION,
        "runtime": step.runtime_record(runtime_args),
        "population": [item.occurrence_id for speech in speeches for item in speech.occurrences],
        "requests": [
            llm.request_body(
                llm.build_request(
                    speech.meta, speech.body, speech.occurrences, pack, table,
                    referent_ids=sorted(referents),
                ),
                model=args.model, reasoning_effort=level,
                reasoning_location=args.reasoning_location,
                max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
                temperature=args.temperature, top_p=args.top_p,
            )
            for level in levels for speech in speeches
        ],
    })
    identity["requests_sha256"] = run_store.digest(identity.pop("requests"))
    identity_sha256 = run_store.digest(identity)
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing.get("identity_sha256") == identity_sha256 and existing.get("passed"):
            console.info(f"reusing passed reasoning probe {rel(destination)}")
            return
    api = step.client()
    observations: list[dict[str, object]] = []
    used: list[str] = []
    skipped: list[dict[str, object]] = []

    # Speech by speech, every level in turn, so that a speech cut off at one
    # level leaves no observation behind at the others.
    for speech in speeches:
        if len(used) == args.speeches:
            break
        console.step(f"Probing {speech.custom_id} at {', '.join(levels)}")
        answered: list[dict[str, object]] = []
        for level in levels:
            request = llm.build_request(
                speech.meta, speech.body, speech.occurrences, pack, table,
                referent_ids=sorted(referents),
            )
            body = llm.request_body(
                request,
                model=args.model,
                reasoning_effort=level,
                reasoning_location=args.reasoning_location,
                max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
                temperature=args.temperature,
                top_p=args.top_p,
            )
            started = time.perf_counter()
            response = api.responses.create(**llm.sdk_request_kwargs(body)).model_dump(mode="json")
            elapsed = time.perf_counter() - started
            usage = step.usage_of(response)
            try:
                text = step.output_text(response)
            except step.ResponseTruncated as error:
                console.warn(f"{speech.custom_id} cut off at {level}; the next speech takes its place")
                skipped.append({"custom_id": speech.custom_id, "level": level, "reason": str(error),
                                "output_tokens": usage["output_tokens"]})
                break
            llm.validate_response(
                text,
                ordinals=[item.ordinal for item in speech.occurrences],
                referents=referents,
                sentences=(
                    len(sentence_spans(speech.body))
                    if prompts.SENTENCE_EVIDENCE in pack.constraints
                    else 0
                ),
            )
            answered.append(
                {
                    "level": level,
                    "custom_id": speech.custom_id,
                    "latency_seconds": round(elapsed, 3),
                    "reasoning_tokens": usage["reasoning_tokens"],
                    "output_tokens": usage["output_tokens"],
                }
            )
        else:
            observations.extend(answered)
            used.append(speech.custom_id)
    if len(used) < args.speeches:
        console.fail(
            f"only {len(used)} of {args.speeches} probe speeches were answered without being cut off",
            [f"{item['custom_id']} at {item['level']}" for item in skipped],
        )

    assessment = probes.assess_ladder(observations, levels)
    artefact = {
        **identity,
        "identity_sha256": identity_sha256,
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt_sha256": pack.sha256,
        "sampling": {"temperature": args.temperature, "top_p": args.top_p},
        "speeches": used,
        "skipped": skipped,
        "observations": observations,
        **assessment,
    }
    artifacts.atomic_write_json(destination, artefact, indent=1)
    if not assessment["passed"]:
        console.fail(
            "Reasoning ladder does not demonstrate the requested top setting; refusing the annotation run",
            [f"paired depth did not increase consistently, or the top median was not maximal; see {rel(destination)}"],
        )
    console.info(f"reasoning ladder demonstrated in {rel(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--reasoning-location", required=True, choices=("request", "chat_template_kwargs", "enable_thinking"))
    parser.add_argument("--levels", required=True, help="comma-separated ladder, from lowest to highest")
    parser.add_argument("--speeches", type=int, default=3)
    parser.add_argument("--spares", type=int, default=2,
                        help="speeches beyond --speeches that may stand in for one cut off")
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--top-p", type=float, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
