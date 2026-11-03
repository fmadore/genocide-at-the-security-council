"""Carry committed model-run rows from the v5.0 corpus to v6.0.

    python tools/carry_over_runs.py           # verify the committed table
    python tools/carry_over_runs.py --write \\
        --v5-corpus data/raw/v5.0/speeches_norm_repaired.parquet \\
        --v5-table path/to/source_repairs.json   # rebuild it; review the diff

Every committed run was asked about Sakamoto-Matsuoka v5.0. v6.0 corrected the
OCR of some 45,800 speeches, renumbered speeches where it split or merged rows,
and replaced the four records v5.0 got wrong. An occurrence's identity is built
over the digest of its speech body, so a run row whose speech changed names an
occurrence v6.0 does not have. The run files are written once and never edited
(`lib.model_runs`), so the move lives in a table beside them, which
`model_runs.read` applies to every run it reads:

- no entry: the speech is word for word the same, under the same name, and the
  row's identity is already a v6.0 occurrence;
- `remap`: the row is re-pointed at the same passage in v6.0 — new occurrence
  id, line id, filename, body offsets and body digest, with the run's own
  evidence offsets shifted by the same amount;
- `drop`: the row leaves the run, and its speech is asked again.

A speech's rows carry over only together, because the model was asked about the
whole speech in one request. They carry when the speech is found whole in the
same meeting of v6.0 (its name may have changed), or when each of its
occurrences is found exactly once in one v6.0 speech of that meeting with
`CONTEXT` characters on either side, and every evidence span any run quoted for
it, unchanged, and that speech has no other occurrence. Anything else — the
text near the word changed, the speech was split across two, v6.0 found a new
occurrence in it — drops the speech's rows. Labels are never touched.

Only the runs asked about v5.0 are carried, and the table lists them. The
August 2026 runs were asked about the corpus before v5.0 was pinned on 3
September, name no v5.0 occurrence either, and stay as they are, unread.

The table is committed at `model_annotations/genocide/carry_over.json`. It is
written once, from the v5.0 corpus the runs were read against (the repaired
`speeches_norm.parquet` of v5.0) and the v5.0 run-repair table, which
re-pointed rows at the four repairs v6.0 made unnecessary. Without `--write` the
tool needs neither: it checks that every row of every committed run, read
through the table, names an occurrence of the current corpus, once.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console, frames, lexicon, model_runs, occurrences
from lib.paths import SPEECHES_NORM, rel

OUTPUT = model_runs.RUN_CARRY_OVER

#: Characters of unchanged text required on either side of an occurrence and of
#: every evidence span quoted for it, about two sentences.
CONTEXT = 500


def meeting(filename: str) -> str:
    """`SC00869` for `SC00869-01-002.txt`: v6.0 may renumber the record's rows."""
    return filename.split("-", 1)[0]


def enumerate_corpus(path: Path) -> tuple[dict[str, str], dict[str, list[occurrences.Occurrence]]]:
    """Every speech body by filename, and the term's occurrences by filename."""
    speeches = frames.read(path, columns=["filename", "body_start", "text"])
    bodies = frames.body(speeches)
    term = lexicon.load().terms[model_runs.TERM]
    found: dict[str, list[occurrences.Occurrence]] = defaultdict(list)
    for item in occurrences.enumerate_term(speeches, bodies, term):
        found[item.filename].append(item)
    return dict(zip(speeches["filename"], bodies, strict=True)), found


def run_rows(names: list[str] | None = None) -> dict[str, list[dict]]:
    """The rows of the named committed runs, or of every one, as written."""
    return {
        path.parent.name: model_runs.read_rows(path)
        for path in sorted(model_runs.RUNS.glob("*/annotations.jsonl"))
        if names is None or path.parent.name in names
    }


def find_all(body: str, window: str) -> list[int]:
    hits, at = [], body.find(window)
    while at != -1:
        hits.append(at)
        at = body.find(window, at + 1)
    return hits


def carry_speech(
    filename: str,
    body: str,
    found: list[occurrences.Occurrence],
    spans: dict[str, tuple[int, int]],
    bodies6: dict[str, str],
    found6: dict[str, list[occurrences.Occurrence]],
    by_meeting: dict[str, list[str]],
) -> tuple[dict[str, tuple[occurrences.Occurrence, int]], str]:
    """Where one v5.0 speech's occurrences are in v6.0, or why they are not."""
    candidates = by_meeting.get(meeting(filename), [])
    if not candidates:
        return {}, f"{meeting(filename)} has no speeches in v6.0"
    whole = [name for name in candidates if bodies6[name] == body]
    if filename in whole:
        whole = [filename]
    if len(whole) == 1:
        at = {(item.start, item.end): item for item in found6.get(whole[0], [])}
        return {item.occurrence_id: (at[(item.start, item.end)], 0) for item in found}, ""

    moved: dict[str, tuple[str, int]] = {}
    for item in found:
        low, high = spans.get(item.occurrence_id, (item.start, item.end))
        low, high = max(0, min(low, item.start) - CONTEXT), max(high, item.end) + CONTEXT
        window = body[low:high]
        hits = [(name, at) for name in candidates for at in find_all(bodies6[name], window)]
        if len(hits) != 1:
            return {}, "the text around it changed in v6.0"
        name, at = hits[0]
        moved[item.occurrence_id] = (name, at - low)
    targets = {name for name, _ in moved.values()}
    if len(targets) != 1:
        return {}, "its speech is split across v6.0 speeches"
    target = targets.pop()
    at = {(item.start, item.end): item for item in found6.get(target, [])}
    if len(at) != len(found):
        return {}, f"v6.0 finds {len(at)} occurrences in {target}, against {len(found)}"
    out = {}
    for item in found:
        shift = moved[item.occurrence_id][1]
        counterpart = at.get((item.start + shift, item.end + shift))
        if counterpart is None:
            return {}, "the text around it changed in v6.0"
        out[item.occurrence_id] = (counterpart, shift)
    return out, ""


def build(v5_corpus: Path, v5_table: Path) -> str:
    old = json.loads(v5_table.read_text(encoding="utf-8"))
    runs = run_rows()

    # The rows as the v5.0 corpus read them: through the v5.0 repair table.
    repaired = {run: model_runs.carried(rows, v5_table) for run, rows in runs.items()}

    console.step("Enumerating the term in v5.0 and v6.0")
    bodies5, found5 = enumerate_corpus(v5_corpus)
    bodies6, found6 = enumerate_corpus(SPEECHES_NORM)
    owner = {item.occurrence_id: filename for filename, items in found5.items() for item in items}
    earlier = sorted(run for run, rows in repaired.items() if not any(str(r["occurrence_id"]) in owner for r in rows))
    console.info(f"left as they are, asked before v5.0: {', '.join(earlier)}")
    runs = {run: rows for run, rows in runs.items() if run not in earlier}
    repaired = {run: rows for run, rows in repaired.items() if run not in earlier}
    spans: dict[str, tuple[int, int]] = {}
    for rows in repaired.values():
        for row in rows:
            if isinstance(row.get("evidence_start"), int) and isinstance(row.get("evidence_end"), int):
                low, high = spans.get(str(row["occurrence_id"]), (row["evidence_start"], row["evidence_end"]))
                spans[str(row["occurrence_id"])] = (
                    min(low, row["evidence_start"]), max(high, row["evidence_end"])
                )

    by_meeting: dict[str, list[str]] = defaultdict(list)
    for name in bodies6:
        by_meeting[meeting(name)].append(name)
    needed = {str(row["occurrence_id"]) for rows in repaired.values() for row in rows}
    if stray := sorted(needed - set(owner)):
        console.fail("run rows name occurrences the v5.0 corpus does not have", stray[:3])

    console.step("Following each speech into v6.0")
    mapped: dict[str, tuple[occurrences.Occurrence, int]] = {}
    reasons: dict[str, str] = {}
    for filename in sorted({owner[identifier] for identifier in needed}):
        found, reason = carry_speech(
            filename, bodies5[filename], found5[filename], spans, bodies6, found6, by_meeting
        )
        if reason:
            for item in found5[filename]:
                reasons[item.occurrence_id] = f"{filename.removesuffix('.txt')}: {reason}"
        mapped.update(found)

    drop: dict[str, dict[str, str]] = {}
    remap: dict[str, dict[str, object]] = {}
    old_remap = old["remap"]
    for rows in runs.values():
        for row in rows:
            identifier, line_id = str(row["occurrence_id"]), str(row["line_id"])
            if identifier in old["drop"]:
                drop[identifier] = {"line_id": line_id, "because": old["drop"][identifier]["because"]}
                continue
            change = old_remap.get(identifier)
            repaired_id = str(change["to"]["occurrence_id"]) if change else identifier
            shift = int(change["evidence_shift"]) if change else 0
            if repaired_id in reasons:
                drop[identifier] = {"line_id": line_id, "because": reasons[repaired_id]}
                continue
            item, moved = mapped[repaired_id]
            if item.occurrence_id == identifier:
                continue
            remap[identifier] = {
                "line_id_was": line_id,
                "to": {
                    "occurrence_id": item.occurrence_id,
                    "line_id": item.line_id,
                    "filename": item.filename,
                    "start": item.start,
                    "end": item.end,
                    "source_sha256": item.source_sha256,
                },
                "evidence_shift": shift + moved,
            }
    table = {
        "schema": 1,
        "written_by": "tools/carry_over_runs.py",
        "from": "Sakamoto-Matsuoka v5.0",
        "to": "Sakamoto-Matsuoka v6.0",
        "context": CONTEXT,
        "runs": sorted(runs),
        "v5_corpus_sha256": artifacts.sha256(v5_corpus),
        "v5_table_sha256": artifacts.sha256(v5_table),
        "drop": dict(sorted(drop.items())),
        "remap": dict(sorted(remap.items())),
    }
    return json.dumps(table, indent=1, ensure_ascii=False) + "\n"


def verify() -> None:
    """Every row of every run, read through the table, is a current occurrence."""
    _, found6 = enumerate_corpus(SPEECHES_NORM)
    current = {
        item.occurrence_id: item for items in found6.values() for item in items
    }
    names = json.loads(OUTPUT.read_text(encoding="utf-8"))["runs"]
    for run, rows in run_rows(names).items():
        carried = model_runs.carried(rows, run_id=run)
        seen: set[str] = set()
        for row in carried:
            identifier = str(row["occurrence_id"])
            item = current.get(identifier)
            if item is None:
                console.fail(f"{run}: {row['line_id']} is not an occurrence of the current corpus",
                             ["run `python tools/carry_over_runs.py --write` and review the diff"])
            if identifier in seen:
                console.fail(f"{run}: two rows carry over to {row['line_id']}")
            if (row["filename"], row["start"], row["end"], row["source_sha256"]) != (
                item.filename, item.start, item.end, item.source_sha256
            ):
                console.fail(f"{run}: {row['line_id']} disagrees with its occurrence")
            seen.add(identifier)
        console.info(f"{run}: {len(carried):,} of {len(rows):,} rows carry over")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed table")
    parser.add_argument("--v5-corpus", type=Path, help="v5.0's repaired speeches_norm.parquet")
    parser.add_argument("--v5-table", type=Path, help="v5.0's model_annotations/genocide/source_repairs.json")
    args = parser.parse_args()
    if args.write:
        if args.v5_corpus is None or args.v5_table is None:
            parser.error("--write needs --v5-corpus and --v5-table")
        artifacts.atomic_write_text(OUTPUT, build(args.v5_corpus, args.v5_table))
        console.info(f"wrote {rel(OUTPUT)}")
    verify()


if __name__ == "__main__":
    console.main(main)
