"""Normalise the corpus: aliases, case, form of address, speaker groups.

Reads data/derived/speeches.parquet and writes speeches_norm.parquet with the
columns every later step depends on:

    country_org      canonical, after config/country_aliases.csv
    entity_type      state / igo / un / ngo / civil_society / academia / company / other
    iso3, lat, lon   states only, from config/entities.csv
    un_regional_group
    speaker_group    P5 / E10 / Non-member state / UN / Non-state, per year
    text             line endings normalised to LF
    body_start       where the speech begins, past the form of address
    words            words in the body, by lib.lexical.TOKEN_RE
    spoken_language  read off "(spoke in French)", where recorded

`words` is the denominator of every "per 100,000 words" figure the site
publishes, and it is counted here, once, so that nothing downstream counts it
again. It is not the codebook's `tokens` column, which is quanteda's count over
the full text with punctuation and numbers in it and stays beside it as
provenance: the two differ by 12.7%, and dividing by the wrong one is what made
every published rate 11.3% low (review of 1 September 2026, §3.3).

The run stops rather than writing a plausible-looking artefact if a speaker is
missing from the crosswalk, or if the Council roster does not add up.

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
from lib import artifacts, console, council, entities, frames, language, lexical, text
from lib.paths import (
    COUNCIL_MEMBERSHIP,
    COUNTRY_ALIASES,
    ENTITIES,
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
    """Normalise line endings, locate the form of address, count words, read
    the language.

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

    resolved = addresses.map(lambda a: text.spoken_language(a.address))
    speeches["spoken_language"] = resolved.map(lambda r: r[0]).astype("string")
    speeches["delivery_language"] = language.delivery_language(speeches)

    return {
        "addressed": int(addresses.map(lambda a: a.matched).sum()),
        "languages": int(speeches["spoken_language"].notna().sum()),
        "fuzzy": int(resolved.map(lambda r: r[1]).sum()),
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
    """Canonicalise speakers and join the crosswalk, failing on any unknown."""
    aliases = entities.load_aliases()
    raw_distinct = speeches["country_org"].nunique()
    speeches["country_org"] = entities.canonicalise(speeches["country_org"], aliases)
    console.info(
        f"country_org: {raw_distinct:,} distinct -> {speeches['country_org'].nunique():,} "
        f"after {len(aliases)} aliases"
    )

    crosswalk = entities.load_entities()
    if problems := entities.validate(crosswalk):
        console.fail("config/entities.csv is not internally consistent", problems)
    if problems := entities.validate_coverage(speeches["country_org"], crosswalk):
        console.fail("the crosswalk does not cover every speaker", problems)

    joined = entities.attach(speeches, crosswalk)
    if int(joined["entity_type"].isna().sum()):
        console.fail("entity_type is null after the join, which should be impossible")
    return joined


def attach_speaker_group(speeches: pd.DataFrame) -> pd.DataFrame:
    """Derive P5 / E10 / non-member / UN / non-state, per speech-year."""
    membership = council.membership_by_year()
    first, last = int(speeches["year"].min()), int(speeches["year"].max())

    if problems := council.validate(membership, first, last):
        console.fail("config/council_membership.csv does not add up", problems)
    in_period = membership[membership["year"].between(first, last)]
    if problems := council.validate_against_corpus(in_period, speeches):
        console.fail("the Council roster disagrees with the corpus", problems)

    speeches["speaker_group"] = council.speaker_group(speeches, membership)
    return speeches


def build_note(speeches: pd.DataFrame, counts: dict[str, int], case_changes) -> str:
    total = len(speeches)
    groups = speeches["speaker_group"].value_counts()
    types = speeches["entity_type"].value_counts()
    languages = speeches["delivery_language"].value_counts()

    lines = [
        "# 02 — Normalise",
        "",
        f"{total:,} speeches, {speeches['country_org'].nunique():,} canonical speakers.",
        "",
        "## Words",
        "",
        f"- **{counts['words']:,}** words in the speech bodies, counted with",
        "  `lib.lexical.TOKEN_RE` — the same rule the keyness tables and the collocate",
        "  windows are built on. This is the denominator of every *per 100,000 words*",
        "  figure the site publishes.",
        f"- The codebook's `tokens` column holds {counts['tokens']:,} over the full",
        f"  texts, punctuation and numbers included: {counts['tokens'] / counts['words']:.1%}",
        "  of the word count. It stays in the table as provenance and is asserted by 01;",
        "  it is not divided by. Dividing by it is what put every published rate",
        f"  {1 - counts['words'] / counts['tokens']:.1%} below the label it carried until",
        "  2 September 2026.",
        "",
        "## Form of address",
        "",
        f"- Matched in **{counts['addressed']:,}** speeches "
        f"({counts['addressed'] / total:.2%}).",
        f"- The remaining {total - counts['addressed']:,} open straight into prose and are "
        "left untruncated. Most belong to the separate VTC record format rather than being "
        "continuations.",
        "",
        "## Delivery language",
        "",
        f"- Recovered for **{counts['languages']:,}** speeches "
        f"({counts['languages'] / total:.1%}) from `(spoke in …)` markers.",
        f"- {counts['fuzzy']:,} needed approximate matching against OCR damage; every case "
        "is listed in `docs/VALIDATION.md`.",
        "- Missing markers in in-person verbatim records are classified as inferred English.",
        "- VTC records carry no delivery-language marker and remain `Unknown (VTC)`.",
        "",
        "| Language | Speeches |",
        "|---|---:|",
        *[f"| {lang} | {n:,} |" for lang, n in languages.head(10).items()],
        "",
        "## Speaker groups",
        "",
        "| Group | Speeches | Share |",
        "|---|---:|---:|",
        *[f"| {g} | {n:,} | {n / total:.1%} |" for g, n in groups.items()],
        "",
        "## Entity types",
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
        f"delivery language recovered for {counts['languages']:,} "
        f"({counts['fuzzy']:,} by approximate match)"
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

    console.step("Attaching the entity crosswalk")
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
        configs=[COUNTRY_ALIASES, ENTITIES, COUNCIL_MEMBERSHIP],
        extra={
            "outputs": [artifacts.describe_file(SPEECHES_NORM, ROOT)],
            "speeches": len(speeches),
            # Both, and named apart: the denominator this step counted and the
            # codebook figure it is not.
            "words": int(speeches["words"].sum()),
            "codebook_tokens": int(speeches["tokens"].sum()),
            "delivery_languages": {
                str(name): int(value)
                for name, value in speeches["delivery_language"].value_counts().items()
            },
        },
    )
    artifacts.atomic_write_json(MANIFESTS / "02_normalise.json", manifest, indent=1)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    normalise()


if __name__ == "__main__":
    main()
