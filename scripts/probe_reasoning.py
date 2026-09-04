"""Demonstrate a served model's reasoning ladder before an annotation run.

The probe sends the same small set of corpus speeches at every declared level,
records latency and reported reasoning tokens, and refuses a flat ladder. Its
artefact lives under ``data/interim``: it is operational evidence, never a
model annotation and never input to a published figure.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import annotate, artifacts, audit, console, llm
from lib.paths import INTERIM, ROOT, rel

STORE = ROOT / "model_annotations" / annotate.TERM
PROMPT = STORE / "PROMPT.md"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"
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


def assess_ladder(rows: list[dict[str, object]], levels: list[str]) -> dict[str, object]:
    """Summarise the paired probe and say whether its reasoning depth varies."""
    summary = []
    medians = []
    for level in levels:
        selected = [row for row in rows if row["level"] == level]
        reasoning = [int(row["reasoning_tokens"]) for row in selected]
        latency = [float(row["latency_seconds"]) for row in selected]
        if not selected:
            raise ValueError(f"reasoning probe has no observations for {level}")
        median_reasoning = statistics.median(reasoning)
        medians.append(median_reasoning)
        summary.append(
            {
                "level": level,
                "requests": len(selected),
                "median_reasoning_tokens": median_reasoning,
                "median_latency_seconds": round(statistics.median(latency), 3),
            }
        )
    return {"levels": summary, "passed": len(set(medians)) > 1}


def run(args: argparse.Namespace) -> None:
    if args.speeches < 1:
        console.fail("--speeches must be at least 1")
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
    }
    if destination.is_file():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if all(existing.get(key) == value for key, value in identity.items()) and existing.get(
            "passed"
        ):
            console.info(f"reusing passed reasoning probe {rel(destination)}")
            return

    step = annotation_step()
    pack = llm.load_prompt(PROMPT)
    referent_list = audit.read_referent_list(REFERENTS)
    referents = referent_list.current
    table = llm.render_referents(llm.read_referent_table(REFERENTS))
    _, speeches, _ = annotate.gather(args.speeches)
    api = step.client()
    observations: list[dict[str, object]] = []

    for level in levels:
        console.step(f"Probing reasoning level {level}")
        for speech in speeches:
            request = llm.build_request(speech.meta, speech.body, speech.occurrences, pack, table)
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
            response = api.responses.create(**body).model_dump(mode="json")
            elapsed = time.perf_counter() - started
            llm.validate_response(
                step.output_text(response),
                ordinals=[item.ordinal for item in speech.occurrences],
                referents=referents,
            )
            usage = step.usage_of(response)
            observations.append(
                {
                    "level": level,
                    "custom_id": speech.custom_id,
                    "latency_seconds": round(elapsed, 3),
                    "reasoning_tokens": usage["reasoning_tokens"],
                    "output_tokens": usage["output_tokens"],
                }
            )

    assessment = assess_ladder(observations, levels)
    artefact = {
        **identity,
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt_sha256": pack.sha256,
        "sampling": {"temperature": args.temperature, "top_p": args.top_p},
        "observations": observations,
        **assessment,
    }
    artifacts.atomic_write_json(destination, artefact, indent=1)
    if not assessment["passed"]:
        console.fail(
            "Reasoning ladder is flat; refusing the annotation run",
            [f"every level reported the same median reasoning length; see {rel(destination)}"],
        )
    console.info(f"reasoning ladder demonstrated in {rel(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--reasoning-location", required=True, choices=("request", "chat_template_kwargs"))
    parser.add_argument("--levels", required=True, help="comma-separated ladder, from lowest to highest")
    parser.add_argument("--speeches", type=int, default=3)
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--top-p", type=float, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
