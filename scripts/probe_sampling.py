"""Measure what the sampling settings do to truncation and to labels, before a run.

The published run decoded greedily (`temperature=0`), while the Qwen3.8-27B
model card recommends `temperature=1.0, top_p=0.95, top_k=20` for thinking
mode, and the Gemma reconnaissance truncated two speeches in twelve with most of
its output spent reasoning. Whether greedy decoding is part of why is a
question with a measurable answer, and each remedy changes the instrument, so
it is measured before an array commits to one (docs/ROADMAP.md, RV9).

The same speeches are sent under each named setting, at one reasoning level and
the run's own output ceiling. Half are the longest in the population, where a
truncation is likeliest; half are a seeded draw from the rest. Per setting the
artefact records truncations, refusals and reasoning tokens; between the first
setting and each other one, per-field agreement over the occurrences both
answered. It lives under `data/interim/model_annotation_sampling/` and is
operational evidence: never a model annotation, never input to a figure.

    python scripts/probe_sampling.py --run-id 2026-09-25-qwen-sampling \\
        --model Qwen/Qwen3.8-27B --model-revision <sha> \\
        --reasoning-location chat_template_kwargs --reasoning-effort xhigh \\
        --settings greedy:0:1,card:1.0:0.95:20 --speeches 100
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import annotate, artifacts, audit, console, llm, model_runs, probes, prompts
from lib.paths import INTERIM, rel
from lib.text import sentence_spans

OUTPUT = INTERIM / "model_annotation_sampling"
MAX_OUTPUT_TOKENS = 65_536


def annotation_step():
    """Load step 14's transport without inventing a second one."""
    path = Path(__file__).resolve().parent / "14_llm_annotate.py"
    spec = importlib.util.spec_from_file_location("vllm_annotation_sampling_transport", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def summarise(observations: list[dict[str, object]], name: str) -> dict[str, object]:
    """One setting's truncations, refusals and reasoning depth."""
    rows = [row for row in observations if row["setting"] == name]
    reasoning = [int(row["reasoning_tokens"]) for row in rows]
    return {
        "setting": name,
        "speeches": len(rows),
        "truncated": sum(1 for row in rows if row["outcome"] == "truncated"),
        "refused": sum(1 for row in rows if row["outcome"] == "refused"),
        "answered": sum(1 for row in rows if row["outcome"] == "answered"),
        "median_reasoning_tokens": statistics.median(reasoning) if reasoning else None,
        "max_reasoning_tokens": max(reasoning) if reasoning else None,
    }


def run(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
        console.fail("run-id must be a single safe directory name")
    try:
        settings = probes.parse_settings(args.settings)
    except ValueError as error:
        console.fail(str(error))
    step = annotation_step()
    pack = prompts.load_prompt(model_runs.PROMPT)
    referents = audit.read_referent_list(model_runs.REFERENTS).current
    table = llm.render_referents(llm.read_referent_table(model_runs.REFERENTS))
    everything, _, _ = annotate.gather(None)
    speeches = probes.select(everything, args.speeches, args.seed)
    console.info(f"{len(speeches)} speeches, {sum(len(s.occurrences) for s in speeches)} occurrences")

    api = step.client()
    observations: list[dict[str, object]] = []
    labels: dict[str, dict[str, dict[int, dict[str, object]]]] = {}
    for setting in settings:
        name = str(setting["name"])
        labels[name] = {}
        console.step(f"Setting {name}")
        for speech in speeches:
            request = llm.build_request(
                speech.meta, speech.body, speech.occurrences, pack, table,
                referent_ids=sorted(referents),
            )
            body = llm.request_body(
                request,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                reasoning_location=args.reasoning_location,
                max_output_tokens=annotate.output_ceiling(speech, MAX_OUTPUT_TOKENS),
                temperature=float(setting["temperature"]),  # type: ignore[arg-type]
                top_p=float(setting["top_p"]),  # type: ignore[arg-type]
                top_k=setting["top_k"],  # type: ignore[arg-type]
            )
            response = api.responses.create(**llm.sdk_request_kwargs(body)).model_dump(mode="json")
            usage = step.usage_of(response)
            outcome = "answered"
            try:
                labels[name][speech.custom_id] = llm.validate_response(
                    step.output_text(response),
                    ordinals=[item.ordinal for item in speech.occurrences],
                    referents=referents,
                    sentences=(
                        len(sentence_spans(speech.body))
                        if prompts.SENTENCE_EVIDENCE in pack.constraints
                        else 0
                    ),
                )
            except step.ResponseTruncated:
                outcome = "truncated"
            except (ValueError, KeyError):
                outcome = "refused"
            observations.append(
                {
                    "setting": name,
                    "custom_id": speech.custom_id,
                    "outcome": outcome,
                    "reasoning_tokens": usage["reasoning_tokens"],
                    "output_tokens": usage["output_tokens"],
                }
            )

    first = str(settings[0]["name"])
    artefact = {
        "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": args.model,
        "model_revision": args.model_revision,
        "reasoning_effort": args.reasoning_effort,
        "prompt_sha256": pack.sha256,
        "settings": settings,
        "speeches": [speech.custom_id for speech in speeches],
        "selection": f"half the longest, half a seeded draw (seed {args.seed})",
        "summary": [summarise(observations, str(setting["name"])) for setting in settings],
        "against_first": {
            str(setting["name"]): probes.agreement(labels[first], labels[str(setting["name"])])
            for setting in settings[1:]
        },
        "observations": observations,
        "reading": (
            "Operational evidence for choosing sampling settings. Agreement between "
            "settings is stability, not accuracy; a lower truncation rate is only a "
            "gain if the labels it produces survive the gold sample."
        ),
    }
    destination = OUTPUT / args.run_id / "sampling.json"
    artifacts.atomic_write_json(destination, artefact, indent=1)
    for row in artefact["summary"]:
        console.info(
            f"{row['setting']}: {row['truncated']} truncated, {row['refused']} refused, "
            f"median reasoning {row['median_reasoning_tokens']}"
        )
    console.info(f"wrote {rel(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument(
        "--reasoning-location", required=True,
        choices=("request", "chat_template_kwargs", "enable_thinking"),
    )
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument("--settings", required=True, help="name:temperature:top_p[:top_k],...")
    parser.add_argument("--speeches", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260925)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
