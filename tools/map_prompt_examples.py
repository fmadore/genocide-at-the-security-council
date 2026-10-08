"""Find the current occurrences behind the prompt's worked examples.

    python tools/map_prompt_examples.py          # verify the committed mapping
    python tools/map_prompt_examples.py --write  # rewrite it; review the diff

The model prompt teaches its labels on ten worked examples taken from the
corpus, and it cites them by the retired corpus's speech identifiers. An
occurrence whose labels the prompt dictates is not a fair test of the model, so
`13_gold_sample.py` keeps every one of them out of the gold sampling frames. It
needs their identities in *this* corpus, and this tool recovers them the only
way the prompt allows: by finding each example's evidence quotation in a speech
of the stated date and taking the `genocide` occurrences inside it.

The mapping is committed at `model_annotations/genocide/prompt_examples.csv`.
Without `--write` the tool rebuilds it and exits non-zero if the committed file
differs, so a corpus or lexicon change that moved an example is caught.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, console, frames, lexicon, llm, model_runs, occurrences
from lib.paths import SPEECHES_NORM, rel

OUTPUT = model_runs.PROMPT_EXAMPLES
FIELDS = ["prompt_version", "example", "cited_as", "date", "filename", "line_id", "occurrence_id"]

#: `1. Commemoration. UNSC_2014_SPV.7105_spch0017#3, Rwanda, 29 January 2014.`
#: followed by an `evidence_quote: "..."` that may wrap over several lines.
EXAMPLE_RE = re.compile(
    r"^\s*(?P<number>\d+)\.\s+[^.]+\.\s+(?P<cited>\S+?#\d+),[\s\S]{0,160}?(?P<date>\d{1,2} \w+ \d{4})",
    re.MULTILINE,
)
#: The curly apostrophe, which the quotations and the records use interchangeably.
CURLY = chr(0x2019)
QUOTE_RE = re.compile(r'evidence_quote:\s*"(?P<quote>[^"]+)"', re.DOTALL)


def examples(system: str) -> list[dict[str, str]]:
    """Each example's citation, date and evidence quotation, in prompt order."""
    found = []
    starts = list(EXAMPLE_RE.finditer(system))
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(system)
        quote = QUOTE_RE.search(system, match.end(), end)
        if quote is None:
            continue
        found.append(
            {
                "example": match["number"],
                "cited_as": match["cited"],
                "date": match["date"],
                "quote": " ".join(quote["quote"].split()),
            }
        )
    return found


def flatten(text: str) -> tuple[str, list[int]]:
    """Lower case without whitespace or hyphens, one apostrophe, mapped to `text`.

    The quotations were cut from the retired corpus's transcription, which
    broke words at line ends (`Secretary- General`) where this one closes them
    up (`SecretaryGeneral`); dropping both is what lets them be found here.
    """
    out, positions = [], []
    for position, character in enumerate(text):
        if character.isspace() or character == "-":
            continue
        out.append("'" if character == CURLY else character.lower())
        positions.append(position)
    return "".join(out), positions


def build() -> str:
    pack = llm.load_prompt(model_runs.PROMPT)
    wanted = examples(pack.system_template)
    if not wanted:
        console.fail("no worked examples were found in the prompt's system message")
    speeches = frames.read(SPEECHES_NORM, columns=["filename", "body_start", "text", "date"])
    bodies = frames.body(speeches)
    term = lexicon.load().terms[model_runs.TERM]
    dates = speeches["date"].dt.strftime("%-d %B %Y" if sys.platform != "win32" else "%#d %B %Y")

    rows = []
    for example in wanted:
        candidates = speeches.index[dates == example["date"]]
        hits = []
        quote, _ = flatten(example["quote"])
        for index in candidates:
            flat, positions = flatten(str(bodies.loc[index]))
            at = flat.find(quote)
            if at < 0:
                continue
            start, end = positions[at], positions[at + len(quote) - 1] + 1
            found = occurrences.enumerate_term(speeches.loc[[index]], bodies.loc[[index]], term)
            hits += [item for item in found if start <= item.start and item.end <= end]
        if not hits:
            console.fail(
                f"example {example['example']} ({example['cited_as']}) was not found",
                [f"no speech of {example['date']} contains its evidence quotation"],
            )
        for item in hits:
            rows.append(
                {
                    "prompt_version": pack.version,
                    "example": example["example"],
                    "cited_as": example["cited_as"],
                    "date": example["date"],
                    "filename": item.filename,
                    "line_id": item.line_id,
                    "occurrence_id": item.occurrence_id,
                }
            )
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed mapping")
    args = parser.parse_args()
    table = build()
    if args.write:
        artifacts.atomic_write_text(OUTPUT, table)
        console.info(f"wrote {rel(OUTPUT)}")
        return
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != table:
        console.fail(
            f"{rel(OUTPUT)} does not match the prompt and corpus",
            ["run `python tools/map_prompt_examples.py --write` and review the diff"],
        )
    console.info(f"{rel(OUTPUT)} matches")


if __name__ == "__main__":
    main()
