"""Blind an intrusion task that was written before 07 split the file.

`07_topics.py` used to write one `intrusion_task.csv` whose columns were
`topic, words, intruder, intruder_position, intruder_from_topic, verdict` — the
answer three columns left of the blank a reader fills in, and the model and
topic label beside it, which `nmf.json` and `embedding.json` publish the word
lists for. A task answerable by subtraction is not the blinded task
`docs/PLAN.md` §4 asks for. 07 now writes a blinded `intrusion_task.csv` and a
separate `intrusion_key.csv`.

The run of 10 August 2026 predates that, and re-running 07 to regenerate a CSV
would mean another cluster job for a file this can rebuild exactly. So: read the
legacy file, attribute each item to the model it came from, and write the pair.

**Nothing is lost.** Every column of the legacy file survives into the key, plus
the `model` column the legacy file never had — the old code concatenated both
models' items and both label topics from zero, so a completed legacy task could
not say which model a reader could read. That attribution is the point of §4's
comparison, and it is recovered here by matching each item's five own words
against the topic word lists the run published, not by assuming the blocks are
in order. The tool refuses to write anything if a single item cannot be
attributed unambiguously.

    python tools/split_intrusion_task.py            # rewrites data/derived/topics/
    python tools/split_intrusion_task.py --dry-run  # report only

Afterwards, fill `intruder_guess` in `intrusion_task.csv` and run
`scripts/score_intrusion.py`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console
from lib.paths import TOPICS, rel
from lib.topics import blind, intrusion_key, intrusion_task

LEGACY_FIELDS = ("topic", "words", "intruder", "intruder_position", "intruder_from_topic")

#: File name → the `model` value items from it should carry. These are the two
#: payloads 07 writes, and the names `word_intrusion` is now called with.
MODELS = {"nmf.json": "nmf", "embedding.json": "embedding"}


def word_lists(directory: Path) -> dict[str, dict[int, list[str]]]:
    """Each model's topic → its top words, as the run published them."""
    published: dict[str, dict[int, list[str]]] = {}
    for filename, model in MODELS.items():
        path = directory / filename
        if not path.exists():
            console.fail(f"{rel(path)} is missing; the items cannot be attributed without it")
        payload = json.loads(path.read_text(encoding="utf-8"))
        # 07 serialises each topic as a plain ranked list of words; the scores
        # `word_intrusion` saw in memory are not carried into the payload.
        published[model] = {
            int(label): [str(word) for word in words] for label, words in payload["words"].items()
        }
    return published


def attribute(row: dict[str, str], published: dict[str, dict[int, list[str]]]) -> str | None:
    """Which model an item came from, or None if that is not unambiguous.

    An item shows a topic's top five words plus one intruder. Removing the
    intruder leaves exactly the five the model published for that topic, so the
    item is attributed by set equality against both models' lists at its own
    label — never by its position in the file. If both models match, or neither
    does, the item is ambiguous and the caller stops rather than guessing.
    """
    shown = [word for word in row["words"].split("|") if word]
    own = {word for word in shown if word != row["intruder"]}
    label = int(row["topic"])
    matched = [
        model
        for model, topics in published.items()
        if label in topics and set(topics[label][: len(own)]) == own
    ]
    return matched[0] if len(matched) == 1 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topics", type=Path, default=TOPICS, help="the 07 output directory")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--seed", type=int, default=0, help="shuffle seed for the item order")
    args = parser.parse_args()

    task_path = args.topics / "intrusion_task.csv"
    key_path = args.topics / "intrusion_key.csv"
    if not task_path.exists():
        console.fail(f"{rel(task_path)} does not exist")

    console.step("Reading")
    with task_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        console.fail(f"{rel(task_path)} has no rows")
    if key_path.exists():
        console.fail(f"{rel(key_path)} already exists — this task is already blinded")
    missing = [field for field in LEGACY_FIELDS if field not in rows[0]]
    if missing:
        console.fail(
            f"{rel(task_path)} is not a legacy task file (no {', '.join(missing)})",
            problems=list(rows[0]),
        )
    console.info(f"{len(rows)} legacy items")

    console.step("Attributing")
    published = word_lists(args.topics)
    items = []
    unattributed = []
    for row in rows:
        model = attribute(row, published)
        if model is None:
            unattributed.append(f"topic {row['topic']}: {row['words']}")
            continue
        items.append(
            {
                "model": model,
                "topic": int(row["topic"]),
                "words": [word for word in row["words"].split("|") if word],
                "intruder": row["intruder"],
                "intruder_position": int(row["intruder_position"]),
                "intruder_from_topic": int(row["intruder_from_topic"]),
            }
        )
    if unattributed:
        console.fail(
            f"{len(unattributed)} items match neither model's word lists, or match both. "
            "Nothing was written; re-run 07 rather than guessing.",
            problems=unattributed[:10],
        )
    for model in sorted(MODELS.values()):
        console.info(f"{model}: {sum(1 for item in items if item['model'] == model)} items")

    console.step("Blinding")
    blinded = blind(items, args.seed)
    task = intrusion_task(blinded)
    key = intrusion_key(blinded)
    # The restructure is lossless only if the key still answers every item the
    # legacy file did. Check that here rather than trusting it.
    recovered = {(str(row["topic"]), str(row["intruder"])) for row in key}
    original = {(row["topic"], row["intruder"]) for row in rows}
    if recovered != original:
        console.fail("the key does not carry every legacy item; nothing was written")
    console.info(f"{len(task)} items, answers moved to {key_path.name}")

    if args.dry_run:
        console.warn("dry run: nothing written")
        return

    console.step("Writing")
    write_csv(task_path, task)
    write_csv(key_path, key)
    console.info(f"wrote {rel(task_path)} — fill `intruder_guess`, one word per row")
    console.info(f"wrote {rel(key_path)} — do not open this one first")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Same shape 07 writes: lists pipe-joined, newlines fixed, written atomically."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("|".join(v) if isinstance(v, list) else v) for k, v in row.items()})
    artifacts.atomic_write_text(path, buffer.getvalue())


if __name__ == "__main__":
    main()
