"""Normalise the corpus: source affiliations, text and speaker groups.

Reads data/derived/speeches.parquet and writes speeches_norm.parquet with the
columns every later step depends on:

    country_org      source affiliation (COW-normalised by the source for states)
    entity_type      state / igo / un / ngo / other, from source flags
    speaker_group    P5 / E10 / Non-member state / UN / Non-state, from source flags
    text             line endings normalised to LF
    body_start       where the speech begins, past a form of address
    words            words in the body, by lib.lexical.words

The source records no delivery language, and none is derived: the retired
corpus's `(spoke in French)` markers are absent from these transcripts, and an
`Unknown` on every speech was published as though it were a reading.

`words` is the denominator of every "per 100,000 words" figure the site
publishes, and it is counted here, once, so that nothing downstream counts it
again. It is not the codebook's `tokens` column, which is quanteda's count over
the full text with punctuation and numbers in it and stays beside it as
provenance: the two differ by 12.7%, and dividing by the wrong one is what made
every published rate 11.3% low (review of 1 September 2026, §3.3).

No hand-curated speaker alias, entity crosswalk or membership roster changes
the canonical data. Geographic fields remain nullable enrichment slots.

Usage:
    python scripts/02_normalise.py

Requires an x64 Python 3.12 — pyarrow publishes no 32-bit wheel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, council, entities, frames, lexical, text
from lib.paths import (
    EXPECTED_WORDS,
    MANIFESTS,
    ROOT,
    SPEECHES,
    SPEECHES_NORM,
    ensure_dirs,
    write_note,
)

#: Categorical fields with case collisions (docs/CORPUS.md §5.3).
CASE_NORMALISED = [
    "participanttype",
    "topic",
    "agenda_item1",
    "agenda_item2",
    "agenda_item3",
    "agenda_item4",
    "agenda_item_manual",
]


def normalise_text(speeches: pd.DataFrame) -> dict[str, int]:
    """Normalise line endings, locate the form of address, count words.

    Mutates `speeches` in place and returns counts for the findings note.
    """
    speeches["text"] = speeches["text"].map(text.normalise_line_endings)

    addresses = speeches["text"].map(text.split_address)
    speeches["body_start"] = addresses.map(lambda a: a.body_start).astype("int32")

    # Over the body rather than the whole text, because the body is what the
    # lexicon counts in: a rate whose numerator excluded the form of address
    # and whose denominator included it would understate itself by the length
    # of thirty years of "Mr. Levitte (France) (spoke in French):".
    speeches["words"] = pd.Series(
        lexical.word_count(frames.body(speeches)), index=speeches.index
    ).astype("int32")

    return {
        "addressed": int(addresses.map(lambda a: a.matched).sum()),
        "words": int(speeches["words"].sum()),
        "tokens": int(speeches["tokens"].sum()),
    }


def normalise_case(speeches: pd.DataFrame) -> list[tuple[str, int, int]]:
    """Collapse case variants in the categorical fields. Returns before/after."""
    changes = []
    for column in CASE_NORMALISED:
        if column not in speeches.columns:
            continue
        before = speeches[column].nunique()
        speeches[column] = text.modal_case(speeches[column])
        after = speeches[column].nunique()
        if before != after:
            changes.append((column, before, after))
    return changes


def attach_entities(speeches: pd.DataFrame) -> pd.DataFrame:
    """Attach the affiliation category supplied by the source dataset."""
    return entities.attach_source_metadata(speeches)


def attach_speaker_group(speeches: pd.DataFrame) -> pd.DataFrame:
    """Derive P5 / E10 / non-member / UN / non-state from source flags."""
    speeches["speaker_group"] = council.speaker_group(speeches)
    return speeches


def build_note(speeches: pd.DataFrame, counts: dict[str, int], case_changes) -> str:
    total = len(speeches)
    groups = speeches["speaker_group"].value_counts()
    types = speeches["entity_type"].value_counts()

    lines = [
        "# 02 — Normalise",
        "",
        f"{total:,} speeches, {speeches['country_org'].nunique():,} source affiliations.",
        "",
        "## Words",
        "",
        f"- **{counts['words']:,}** words in the speech bodies, counted with",
        "  `lib.lexical.words` — the same rule the keyness tables and the collocate",
        "  windows are built on. This is the denominator of every *per 100,000 words*",
        "  figure the site publishes.",
        f"- The source's `count` field totals {counts['tokens']:,}; it is retained as",
        "  `source_word_count`/`tokens` for provenance but is not the analytical",
        "  denominator.",
        "",
        "## Form of address",
        "",
        f"- Matched in **{counts['addressed']:,}** speeches "
        f"({counts['addressed'] / total:.2%}).",
        f"- The remaining {total - counts['addressed']:,} open straight into prose and are "
        "left untruncated. The source distributes speech bodies without the printed address,",
        "  so the matches are opening salutations rather than speaker labels; correcting them",
        "  changes embedded bodies and waits on the next embedding run (docs/ROADMAP.md, RV2).",
        "",
        "## Delivery language",
        "",
        "The source records none, and none is derived or published.",
        "",
        "## Speaker groups",
        "",
        "| Group | Speeches | Share |",
        "|---|---:|---:|",
        *[f"| {g} | {n:,} | {n / total:.1%} |" for g, n in groups.items()],
        "",
        "## Entity types",
        "",
        "These categories come directly from the dataset flags. `un_org` takes precedence",
        "over `igo`, because UN bodies carry both flags in the source; an unflagged",
        "affiliation remains `other`.",
        "",
        "| Type | Speeches | Distinct entities |",
        "|---|---:|---:|",
        *[
            f"| {t} | {n:,} | "
            f"{speeches.loc[speeches['entity_type'] == t, 'country_org'].nunique():,} |"
            for t, n in types.items()
        ],
        "",
        "## Case collisions collapsed",
        "",
    ]
    if case_changes:
        lines += [
            "| Field | Before | After |",
            "|---|---:|---:|",
            *[f"| `{c}` | {b:,} | {a:,} |" for c, b, a in case_changes],
        ]
    else:
        lines.append("None found.")
    return "\n".join(lines) + "\n"


def normalise() -> None:
    ensure_dirs()

    console.step("Reading the canonical parquet")
    speeches = frames.read(SPEECHES)

    console.step("Normalising text")
    counts = normalise_text(speeches)
    console.info(
        f"form of address matched in {counts['addressed']:,} speeches "
        f"({counts['addressed'] / len(speeches):.2%})"
    )
    console.info(
        f"{counts['words']:,} words in the bodies against {counts['tokens']:,} "
        f"codebook tokens ({counts['words'] / counts['tokens']:.1%})"
    )
    # Asserted for the same reason 01 asserts the codebook's token sum: this is
    # the denominator of every published rate, and a tokeniser edit or a
    # re-fetched corpus that moved it would move every one of those rates
    # without moving anything a reader could see.
    if counts["words"] != EXPECTED_WORDS:
        console.fail(
            "the word count is not the one lib.paths declares",
            [
                f"{counts['words']:,} words, expected {EXPECTED_WORDS:,}",
                "if the corpus or lib.lexical.TOKEN_RE changed on purpose, update "
                "EXPECTED_WORDS and say so in docs/VALIDATION.md",
            ],
        )

    console.step("Normalising categorical fields")
    case_changes = normalise_case(speeches)
    if case_changes:
        console.table([(c, f"{b:,} -> {a:,}") for c, b, a in case_changes])
    else:
        console.info("no case collisions found")

    console.step("Attaching source affiliation categories")
    speeches = attach_entities(speeches)
    console.table(
        [(t, f"{n:,}") for t, n in speeches["entity_type"].value_counts().items()]
    )

    console.step("Deriving speaker groups")
    speeches = attach_speaker_group(speeches)
    console.table(
        [(g, f"{n:,}") for g, n in speeches["speaker_group"].value_counts().items()]
    )

    console.step("Writing")
    frames.write(speeches, SPEECHES_NORM)
    note = write_note("02_normalise.md", build_note(speeches, counts, case_changes))
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "02_normalise.py",
        inputs=[SPEECHES],
        configs=[],
        extra={
            "outputs": [artifacts.describe_file(SPEECHES_NORM, ROOT)],
            "speeches": len(speeches),
            # Both, and named apart: the denominator this step counted and the
            # codebook figure it is not.
            "words": int(speeches["words"].sum()),
            "codebook_tokens": int(speeches["tokens"].sum()),
            "addressed": counts["addressed"],
        },
    )
    artifacts.atomic_write_json(MANIFESTS / "02_normalise.json", manifest, indent=1)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    normalise()


if __name__ == "__main__":
    main()
