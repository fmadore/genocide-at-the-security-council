"""Rebuild the list of passages that were read against the model's labels.

    python tools/prior_review.py          # verify the committed list
    python tools/prior_review.py --write  # rewrite it; review the diff

On 10 September 2026, 59 occurrences from the 9 September checkpoint of the Qwen
run were read against the model's labels (docs/PLAN.md, "Decisions from the
preliminary Qwen review"). Anyone who has read that review has seen the model's
label and a discussion of the passage, so a coder's reading of one of them may
no longer be independent of the model. The passages are flagged rather than
dropped (decided by FM on 9 October 2026, docs/EVALUATION_PLAN.md §4):
`13_gold_sample.py` marks the ones it draws, and `15_usage.py` reports every gold
figure with and without them.

The review's records are in `data/interim/qwen-review-sample.json`, which is not
under version control. Each names its passage by a line id, `SPEECH#ordinal`,
with the ordinal counted under lexicon 6. Lexicon 8 added the accented
*génocidaires*, which moves the ordinal of every later occurrence in a speech
that uses it, so a record is resolved here by the passage it quoted rather than
by its ordinal: the occurrence of the same speech whose window — the body from
:data:`WINDOW` characters before the match to as many after, as the review cut
it — is the record's `context`, character for character. The window holds the
matched text at a fixed place, so one comparison checks the speech, the match
and the context together. A record that does not resolve to exactly one
occurrence stops the tool.

What is committed is identity only: the checksum-based `occurrence_id`, which
does not move when the lexicon adds a form, the current `line_id`, the line id
the review recorded, and when and in which review the passage was read. No
label, evidence or rationale is copied: the list records that a passage was
read, never what was said about it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console, frames, lexicon, model_runs, occurrences
from lib.paths import INTERIM, SPEECHES_NORM, rel

OUTPUT = model_runs.PRIOR_REVIEW
SOURCE = INTERIM / "qwen-review-sample.json"
FIELDS = ["occurrence_id", "line_id", "reviewed_line_id", "reviewed_on", "source"]
REVIEWED_ON = "2026-09-10"
DESCRIPTION = "spot review of the Qwen run's labels at its 9 September 2026 checkpoint"

#: Characters of body the review kept on either side of a match.
WINDOW = 900


def records(path: Path) -> list[dict[str, str]]:
    """Each reviewed passage's line id and context, and nothing else of it."""
    if not path.is_file():
        console.fail(
            f"{rel(path)} is missing",
            ["it is not under version control and exists only where the review was run"],
        )
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return [{"id": str(item["id"]), "context": str(item["context"])} for item in loaded]


def build(source: Path) -> str:
    wanted = records(source)
    speeches = frames.read(SPEECHES_NORM, columns=["filename", "body_start", "text"])
    bodies = frames.body(speeches)
    term = lexicon.load().terms[model_runs.TERM]
    by_name = {str(name): index for index, name in speeches["filename"].items()}

    found: list[tuple[tuple[str, int], dict[str, str]]] = []
    problems: list[str] = []
    for record in wanted:
        stem = record["id"].split("#", 1)[0]
        index = by_name.get(f"{stem}.txt")
        if index is None:
            problems.append(f"{record['id']}: this corpus has no speech {stem}.txt")
            continue
        body = str(bodies.loc[index])
        matches = [
            item
            for item in occurrences.enumerate_term(
                speeches.loc[[index]], bodies.loc[[index]], term
            )
            if body[max(0, item.start - WINDOW) : item.end + WINDOW] == record["context"]
        ]
        if len(matches) != 1:
            problems.append(
                f"{record['id']}: {len(matches)} occurrences of {stem} carry its context"
            )
            continue
        (item,) = matches
        if item.line_id != record["id"]:
            console.info(f"{record['id']} is {item.line_id} under this lexicon")
        found.append(
            (
                (item.filename, item.start),
                {
                    "occurrence_id": item.occurrence_id,
                    "line_id": item.line_id,
                    "reviewed_line_id": record["id"],
                    "reviewed_on": REVIEWED_ON,
                    "source": DESCRIPTION,
                },
            )
        )
    if problems:
        console.fail("some reviewed passages do not resolve to exactly one occurrence", problems)
    rows = [row for _, row in sorted(found, key=lambda pair: pair[0])]
    if len({row["occurrence_id"] for row in rows}) != len(rows):
        console.fail("two reviewed passages resolve to the same occurrence")
    console.info(f"{len(rows)} reviewed passages, each resolved to one occurrence")
    return artifacts.csv_text(rows, fieldnames=FIELDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed list")
    parser.add_argument(
        "--source", type=Path, default=SOURCE, help="the review's records, if not in data/interim"
    )
    args = parser.parse_args()
    table = build(args.source)
    if args.write:
        artifacts.atomic_write_text(OUTPUT, table)
        console.info(f"wrote {rel(OUTPUT)}")
        return
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != table:
        console.fail(
            f"{rel(OUTPUT)} does not match the review and the corpus",
            ["run `python tools/prior_review.py --write` and review the diff"],
        )
    console.info(f"{rel(OUTPUT)} matches")


if __name__ == "__main__":
    main()
