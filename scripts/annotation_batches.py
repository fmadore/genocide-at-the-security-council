"""Create a fixed batch plan or assemble complete independent annotation runs."""

import argparse
import json
from pathlib import Path

from lib import annotate, annotation_batches, artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("plan")
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--size", type=int, default=250)
    join = sub.add_parser("merge")
    join.add_argument("--plan", type=Path, required=True)
    join.add_argument("--output", type=Path, required=True)
    join.add_argument("sources", type=Path, nargs="+")
    args = parser.parse_args()
    speeches, _, _ = annotate.gather(None)
    if args.command == "plan":
        if args.output.exists():
            parser.error("Plan already exists; retain it for resumptions")
        document = annotation_batches.plan(speeches, args.size)
        artifacts.atomic_write_json(args.output, document, indent=1)
        print(f"{len(document['batches'])} batches; array indices 0-{len(document['batches']) - 1}")
    else:
        annotation_batches.merge(json.loads(args.plan.read_text()), speeches, args.sources, args.output)
        print(f"Complete merged run: {args.output}")


if __name__ == "__main__":
    main()
