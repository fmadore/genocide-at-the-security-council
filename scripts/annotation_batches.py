"""Create a fixed batch plan or assemble independent annotation runs into one.

A merge requires every batch to be complete. A speech that was asked and never
answered acceptably may be left out only by naming it with `--accept-gap`; the
merged manifest then lists it with the failure its batch recorded.
"""

import argparse
import json
from pathlib import Path

from lib import annotate, annotation_batches, artifacts, console, lexicon, model_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("plan")
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--size", type=int, default=250)
    make.add_argument("--top-up", metavar="RUN_ID",
                      help="plan only the speeches this committed run does not cover in full")
    join = sub.add_parser("merge")
    join.add_argument("--plan", type=Path, required=True)
    join.add_argument("--output", type=Path, required=True)
    join.add_argument("--accept-gap", action="append", default=[], metavar="SPEECH",
                      help="a speech id its batch never answered acceptably; repeat for each")
    join.add_argument("--carry", type=Path, metavar="RUN_DIR",
                      help="the committed run a top-up plan completes")
    join.add_argument("sources", type=Path, nargs="+")
    args = parser.parse_args()
    speeches, _, _ = annotate.gather(None)
    if args.command == "plan":
        if args.output.exists():
            parser.error("Plan already exists; retain it for resumptions")
        top_up = None
        if args.top_up:
            directory = model_runs.RUNS / args.top_up
            _, rows = model_runs.read(directory)
            covered = len(speeches)
            speeches = annotation_batches.uncovered(speeches, rows)
            print(f"{args.top_up} covers {covered - len(speeches):,} of {covered:,} speeches in full")
            top_up = {"run_id": args.top_up,
                      "annotations_sha256": artifacts.sha256(directory / "annotations.jsonl"),
                      "carry_over_sha256": artifacts.sha256(model_runs.RUN_CARRY_OVER)}
        document = annotation_batches.plan(speeches, args.size, top_up)
        artifacts.atomic_write_json(args.output, document, indent=1)
        print(f"{len(speeches):,} speeches, {len(document['population']):,} occurrences; "
              f"{len(document['batches'])} batches; array indices 0-{len(document['batches']) - 1}")
    else:
        document = json.loads(args.plan.read_text(encoding="utf-8"))
        # The batches agree on one lexicon version, which merge checks; a run
        # made before a declared widening is merged over the population it asked.
        version = json.loads((args.sources[0] / "manifest.json").read_text(encoding="utf-8"))["lexicon_version"]
        if "top_up" not in document:
            lex = lexicon.load()
            widened = lex.compatible(model_runs.TERM, version) and not lex.complete(model_runs.TERM, version)
            speeches = annotation_batches.within(document, speeches, widened=widened)
        merged = annotation_batches.merge(document, speeches, args.sources, args.output,
                                          args.accept_gap, carry=args.carry)
        if merged["gaps"]:
            print(f"Merged run with {len(merged['gaps'])} accepted gaps: {args.output}")
        else:
            print(f"Complete merged run: {args.output}")


if __name__ == "__main__":
    console.main(main)
