"""Re-point committed model-run rows at the speeches the source repairs changed.

    python tools/remap_run_rows.py          # verify the committed table
    python tools/remap_run_rows.py --write  # rewrite it; review the diff

`config/source_repairs.yml` drops a duplicated meeting record and splits a
speech that ran on into the next speaker's turn. A committed run was asked
about the corpus before those repairs, so some of its rows name an occurrence
that no longer exists: one inside a dropped record, or one whose passage moved
into the speech a split created. The run files are written once and never
edited (`lib.model_runs`), so the change lives in a table beside them, which
`model_runs.read` applies to every run it reads:

- `drop`: rows in a dropped record, which leave the run with the record;
- `remap`: rows in a split speech, re-pointed at the same passage in its new
  speech — new occurrence id, line id, filename, body offsets and body digest,
  and each run's own evidence offsets shifted by the same amount.

Labels are never touched. The table is committed at
`model_annotations/genocide/source_repairs.json`. Without `--write` the tool
rebuilds it from the repaired corpus and exits non-zero if the committed file
differs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console, frames, lexicon, model_runs, occurrences
from lib.paths import SOURCE_REPAIRS, SPEECHES_NORM, rel

OUTPUT = model_runs.RUN_REPAIRS


def stem(filename: str) -> str:
    return filename.removesuffix(".txt")


def record(filename: str) -> str:
    return stem(filename).rsplit("-", 1)[0]


def build() -> str:
    repairs = yaml.safe_load(SOURCE_REPAIRS.read_text(encoding="utf-8"))
    dropped = {str(item["record_id"]): str(item["duplicate_of"]) for item in repairs.get("drop_records") or []}
    splits = {f"{item['speech_id']}.txt": item for item in repairs.get("split_speeches") or []}
    copied = {
        str(speech): str(original)
        for item in repairs.get("drop_speeches") or []
        for speech, original in item["pairs"].items()
    }
    trimmed = {f"{item['speech_id']}.txt": int(item["at"]) for item in repairs.get("trim_speeches") or []}

    wanted = set(splits) | {f"{item['new']['speech_id']}.txt" for item in splits.values()}
    speeches = frames.read(SPEECHES_NORM, columns=["filename", "body_start", "text"])
    if leftover := sorted(
        name for name in speeches["filename"] if record(name) in dropped or stem(name) in copied
    ):
        console.fail(f"{SPEECHES_NORM.name} still holds dropped speeches", leftover[:3])
    speeches = speeches[speeches["filename"].isin(wanted)]
    if set(speeches["filename"]) != wanted:
        console.fail("the repaired speeches are not in the corpus", sorted(wanted - set(speeches["filename"])))
    term = lexicon.load().terms[model_runs.TERM]
    found = {
        (item.filename, item.start): item
        for item in occurrences.enumerate_term(speeches, frames.body(speeches), term)
    }

    drop: dict[str, dict[str, str]] = {}
    remap: dict[str, dict[str, object]] = {}
    for run in sorted(path.parent for path in model_runs.RUNS.glob("*/annotations.jsonl")):
        for row in model_runs.read_rows(run / "annotations.jsonl"):
            identifier, filename = str(row["occurrence_id"]), str(row["filename"])
            if record(filename) in dropped:
                drop[identifier] = {
                    "line_id": str(row["line_id"]),
                    "because": f"{record(filename)} is dropped as a copy of {dropped[record(filename)]}",
                }
                continue
            if stem(filename) in copied:
                drop[identifier] = {
                    "line_id": str(row["line_id"]),
                    "because": f"{stem(filename)} is dropped as a copy of {copied[stem(filename)]}",
                }
                continue
            if filename in trimmed and int(row["start"]) >= trimmed[filename]:
                drop[identifier] = {
                    "line_id": str(row["line_id"]),
                    "because": f"{stem(filename)} is trimmed at character {trimmed[filename]:,}",
                }
                continue
            split = splits.get(filename)
            if split is None:
                continue
            start, end = int(row["start"]), int(row["end"])
            if start >= int(split["at"]):
                target, shift = f"{split['new']['speech_id']}.txt", int(split["at"]) + len(split["label"])
            else:
                target, shift = filename, 0
            item = found.get((target, start - shift))
            if item is None or item.end != end - shift:
                console.fail(f"{row['line_id']} has no counterpart in {target}")
            remap[identifier] = {
                "line_id_was": str(row["line_id"]),
                "to": {
                    "occurrence_id": item.occurrence_id,
                    "line_id": item.line_id,
                    "filename": item.filename,
                    "start": item.start,
                    "end": item.end,
                    "source_sha256": item.source_sha256,
                },
                "evidence_shift": -shift,
            }
    table = {
        "schema": 1,
        "written_by": "tools/remap_run_rows.py",
        "source_repairs_sha256": artifacts.sha256(SOURCE_REPAIRS),
        "drop": dict(sorted(drop.items())),
        "remap": dict(sorted(remap.items())),
    }
    return json.dumps(table, indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed table")
    args = parser.parse_args()
    table = build()
    if args.write:
        artifacts.atomic_write_text(OUTPUT, table)
        console.info(f"wrote {rel(OUTPUT)}")
        return
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != table:
        console.fail(
            f"{rel(OUTPUT)} does not match the source repairs and the corpus",
            ["run `python tools/remap_run_rows.py --write` and review the diff"],
        )
    console.info(f"{rel(OUTPUT)} matches")


if __name__ == "__main__":
    main()
