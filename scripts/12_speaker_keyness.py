"""Per-speaker matched keyness: what one delegation says that the room does not.

Reads speeches_flagged.parquet and writes
data/derived/countries/speaker_keyness.json plus a findings note.

`docs/PLAN.md` §3 asks an actor profile for "agenda composition and matched
keyness with minimum-sample disclosure", and §7 refuses to let a visual precede
the table it depicts. 05 computes matched keyness for lexicon slices — genocide
speeches against comparable speeches that do not use the word — which is a
different question from this one and cannot be cut into it. This step builds the
per-speaker table. It draws nothing.

Each of a speaker's speeches is paired with a speech from the same year, agenda
item and speaker group given by somebody else, and the two vocabularies are
compared. The unmatched comparison — the same target against the whole corpus —
is written beside it, because that is the reading the matching is supposed to
improve on and the pair is what shows whether it did.

What the step is careful about, in each case a way for this table to be wrong
while looking right:

- a table over a handful of pairs reads exactly like a profile, so keywords are
  withheld below `keyness.MIN_PAIRS` — written as null, never omitted;
- so does a table over a great many pairs that are a small and non-random part
  of what a speaker said, which the first gate does not catch: the UN
  Secretariat is the only speaker in its speaker group, and the pairing found
  partners for 123 of its 4,709 speeches. `keyness.MIN_COVERAGE` is the second
  gate, `coverage` is published for every speaker either way, and
  `withheld_because` says which one closed;
- `speaker_group` is one of the matching keys and 02 freezes it into the corpus,
  so an edit to `config/council_membership.csv` since would silently change what
  "comparable" means; `council.drift` stops the run instead;
- counting through a matrix is an optimisation, and an optimisation that changed
  the numbers would be invisible here, so `tests/test_keyness.py` asserts the
  matrix returns what `lexical.vocabulary` returns and that the stratum code
  partitions the corpus exactly as the three columns it stands for do.

Usage:
    python scripts/12_speaker_keyness.py [--limit 40] [--repetitions 10]
    python scripts/12_speaker_keyness.py --speakers 5   # a quick look

Requires an x64 Python 3.12 — pyarrow publishes no 32-bit wheel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, council, frames, keyness, lexical
from lib.paths import (
    COUNCIL_MEMBERSHIP,
    COUNTRIES,
    EXPECTED_SPEECHES,
    ROOT,
    SPEECHES_FLAGGED,
    STOPWORDS,
    ensure_dirs,
    rel,
    write_note,
)

#: Columns read from the corpus. The text is needed — this step counts it — but
#: the ninety lexicon columns are not.
COLUMNS = [
    "row_id",
    "year",
    "country_org",
    "agenda_item_manual",
    "speaker_group",
    # `council.drift` recomputes speaker_group from config, and needs the same
    # inputs 02 had to do it: entity_type is how the UN Secretariat is told from
    # a state that happens never to have sat.
    "entity_type",
    "tokens",
    "text",
    "body_start",
]

OUTPUT = COUNTRIES / "speaker_keyness.json"

#: RIGHT SINGLE QUOTATION MARK, named by code point exactly as `lexical.TOKEN_RE`
#: names it: the OCR carries both apostrophes, they are identical on screen, and
#: the tokeniser keeps them apart on purpose.
CURLY = chr(0x2019)


def load_corpus() -> pd.DataFrame:
    """Read the corpus, refusing to continue on anything that would mislead."""
    speeches = frames.read(SPEECHES_FLAGGED, columns=COLUMNS)

    if len(speeches) != EXPECTED_SPEECHES:
        console.fail(
            "the corpus does not match the codebook total this table is cut from",
            [
                f"{len(speeches):,} speeches, expected {EXPECTED_SPEECHES:,}",
                "re-run 01_build_parquet.py through 03_lexicon.py",
            ],
        )
    if problems := council.drift(speeches):
        console.fail(
            "config/council_membership.csv has changed since 02_normalise.py last ran, "
            "so speaker_group — one of the matching keys — no longer means what the "
            "corpus says it means",
            [*problems, "re-run 02_normalise.py and everything after it"],
        )
    if not speeches.index.equals(pd.RangeIndex(len(speeches))):
        # The matrix addresses documents by position and the pairing returns
        # index labels. They are the same numbers only while this holds.
        console.fail("the corpus must carry a positional index for the matrix to align")
    return speeches


def eligible(speeches: pd.DataFrame, minimum: int) -> pd.Series:
    """Speakers with enough speeches to be *capable* of clearing the minimum.

    A necessary condition, not the test: pairs can only be fewer than speeches,
    so a speaker below the minimum here cannot reach it after matching. The
    sufficient test is on pairs and lives in `lib.keyness`, where it is one
    decision rather than one per caller.
    """
    counts = speeches["country_org"].value_counts()
    return counts[counts >= minimum]


def build_speakers(
    speeches: pd.DataFrame,
    matrix: keyness.DocumentTerms,
    stratum_column: str,
    reference,
    reference_total: int,
    stopwords: frozenset[str],
    candidates: pd.Series,
    *,
    seed: int,
    limit: int,
    repetitions: int,
    minimum: int,
    min_coverage: float,
) -> list[dict[str, object]]:
    """One block per candidate speaker, in descending order of speeches given."""
    rows: list[dict[str, object]] = []
    for position, (name, held) in enumerate(candidates.items(), start=1):
        block = keyness.speaker_keyness(
            speeches,
            matrix,
            str(name),
            stratum_column,
            reference,
            reference_total,
            stopwords,
            seed=seed,
            limit=limit,
            repetitions=repetitions,
            minimum=minimum,
            min_coverage=min_coverage,
        )
        block = {
            "country_org": str(name),
            **block,
            "agenda": keyness.agenda_composition(speeches, name),
        }
        rows.append(block)
        top = block["keywords"] or []
        console.info(
            f"{position:>3}/{len(candidates)} {str(name)[:28]:28s} "
            f"{int(held):>6,} speeches  {block['pairs']:>6,} pairs  "
            f"{float(block['coverage']):>6.1%}  "
            + (
                ", ".join(str(row["word"]) for row in top[:6])
                if top
                else "withheld: " + ", ".join(block["withheld_because"])
            )
        )
    return rows


def build_note(payload: dict, speakers: list[dict[str, object]], withheld: int) -> str:
    drawn = [s for s in speakers if s["sufficient"]]
    coverages = pd.Series([float(s["coverage"]) for s in drawn])

    def profile(block: dict) -> list[str]:
        keywords = block["keywords"] or []
        return [
            f"| {block['country_org']} | {block['pairs']:,} | {float(block['coverage']):.0%} | "
            + ", ".join(
                f"`{row['word']}`{'\\*' if row['self_reference'] else ''}" for row in keywords[:8]
            )
            + " |"
        ]

    ranked = sorted(drawn, key=lambda s: -int(s["pairs"]))
    worst = sorted(drawn, key=lambda s: float(s["coverage"]))[:5]

    def removed(block: dict) -> float:
        """How far the top unmatched keywords fall once the occasion is held."""
        matched = {row["word"]: float(row["log_ratio"]) for row in block["keywords"] or []}
        pairs = [
            float(row["log_ratio"]) - matched.get(str(row["word"]), 0.0)
            for row in (block["keywords_unmatched"] or [])[:15]
        ]
        return float(pd.Series(pairs).median()) if pairs else 0.0

    drops = pd.Series([removed(block) for block in drawn])
    top_rows = [row for block in drawn for row in (block["keywords"] or [])[:8]]
    self_marked = sum(1 for row in top_rows if row["self_reference"])
    by_reason = {
        reason: sum(1 for s in speakers if reason in s["withheld_because"])
        for reason in ("pairs", "coverage")
    }
    # The tokeniser keeps both apostrophes on purpose — the OCR carries both and
    # they are identical on screen — so a possessive can hold two rows. Counted
    # rather than corrected: the fix would be in `lexical.TOKEN_RE`, which every
    # published table in 05 is already counted with.
    curly = sum(
        1 for block in drawn for row in (block["keywords"] or []) if CURLY in str(row["word"])
    )

    return (
        "\n".join(
            [
                "# 12 — Per-speaker matched keyness",
                "",
                "What one delegation says that the room did not, with the occasion held",
                "constant. Each of a speaker's speeches is paired with a speech from the same",
                f"**{'**, **'.join(payload['matched_on'])}** given by somebody else; the",
                "comparison is between those two sets of words.",
                "",
                f"- **{len(drawn)} of {payload['speakers_considered']:,} speakers** clear both "
                "gates and are published.",
                f"- Withheld after pairing: **{withheld:,}** — {by_reason['pairs']:,} for "
                f"fewer than {payload['minimum_pairs']:,} matched pairs, "
                f"{by_reason['coverage']:,} for coverage under "
                f"{payload['minimum_coverage']:.0%} of their own speeches.",
                f"- The other {payload['speakers_total'] - payload['speakers_considered']:,} "
                "speakers never reached the minimum in speeches and were not paired at all.",
                f"- Coverage across the published speakers runs from "
                f"{coverages.min():.0%} to {coverages.max():.0%}, median {coverages.median():.0%}.",
                f"- Seed {payload['seed']}, {payload['repetitions']} stability repetitions, "
                f"top {payload['limit']} rows per table.",
                "",
                "## What the matching removes",
                "",
                "The same target against the whole corpus, unmatched, is not a second result:",
                "it is the reading this table exists to improve on. Across published speakers",
                f"the median top-15 effect size falls by **{drops.median():.2f}** on the log2",
                "scale once year, agenda item and speaker group are held constant — a factor",
                f"of {2 ** drops.median():.1f} in rate. What survives is diction; what",
                "disappears was the file the delegation happened to be heard on.",
                "",
                "## Every delegation's strongest keyword is often its own name",
                "",
                f"**{self_marked} of {len(top_rows)}** rows in the top eight of a published",
                "table are a word from the speaker's own canonical name — `kingdom`, `states`,",
                "`federation`. That is a fact about the register rather than noise, so the rows",
                "are marked with an asterisk below and flagged in the artefact, and none of them",
                "is removed. The flag is mechanical and partial by design: it cannot catch",
                "`french` or `beijing`, which do not appear in the names they belong to, so an",
                "unmarked row is not a guarantee.",
                "",
                "## The largest speakers",
                "",
                "| Speaker | Pairs | Coverage | Strongest keywords, matched |",
                "|---|---:|---:|---|",
                *[line for block in ranked[:15] for line in profile(block)],
                "",
                "\\* a word from the speaker's own name.",
                "",
                f"One tokenising artefact is visible in that table and is left as it is: "
                f"{curly} published rows carry a curly apostrophe, so `brazil's` and "
                f"`brazil{CURLY}s` are two rows holding a share of the evidence they "
                "jointly support. The OCR carries both characters and they are identical "
                "on screen. "
                "Folding them would mean editing the tokeniser every published table in 05 "
                "is already counted with, which is a larger change than this step is "
                "entitled to make.",
                "",
                "## Where the matching struggled",
                "",
                "Low coverage means most of a speaker's speeches had no comparable partner —",
                "usually because it speaks from a position few others share, or in debates it",
                "dominates. These rows are published, and are the ones to read last.",
                "",
                "| Speaker | Pairs | Coverage | Strongest keywords, matched |",
                "|---|---:|---:|---|",
                *[line for block in worst for line in profile(block)],
                "",
                "## What this is not",
                "",
                "A keyword is a word this delegation used at a different rate from comparable",
                "speakers on the same occasion. It is not a position, a policy or a belief, and",
                "the table says nothing about why a word was used — a delegation that names a",
                "conflict often may be prosecuting it, deploring it, or chairing the debate on",
                "it. The concordance is where a word becomes a reading.",
                "",
            ]
        )
        + "\n"
    )


def run(
    seed: int,
    limit: int,
    repetitions: int,
    minimum: int,
    min_coverage: float,
    speakers: int,
) -> None:
    ensure_dirs()

    stopwords = lexical.load_stopwords()
    console.step("Reading the corpus")
    speeches = load_corpus()

    console.step("Counting every speech once")
    matrix = keyness.build(frames.body(speeches))
    reference = matrix.counter(speeches.index.to_numpy())
    reference_total = sum(reference.values())
    console.info(
        f"{matrix.documents:,} documents, {len(matrix.words):,} types, "
        f"{matrix.entries:,} entries, {reference_total:,} tokens"
    )

    console.step("Strata")
    stratum = keyness.strata(speeches)
    speeches = speeches.assign(stratum=stratum)
    console.info(
        f"{stratum.nunique():,} distinct "
        f"{' + '.join(keyness.MATCH_ON)} strata over {len(speeches):,} speeches"
    )

    candidates = eligible(speeches, minimum)
    if speakers:
        candidates = candidates.head(speakers)
    console.step(f"Keyness for {len(candidates):,} candidate speakers")
    rows = build_speakers(
        speeches,
        matrix,
        "stratum",
        reference,
        reference_total,
        stopwords,
        candidates,
        seed=seed,
        limit=limit,
        repetitions=repetitions,
        minimum=minimum,
        min_coverage=min_coverage,
    )

    published = sum(1 for row in rows if row["sufficient"])
    withheld = len(rows) - published
    total_speakers = int(speeches["country_org"].nunique())
    console.info(
        f"{published:,} speakers published, {withheld:,} considered and withheld, "
        f"{total_speakers - len(rows):,} never paired"
    )

    console.step("Writing")
    payload = {
        "matched_on": keyness.MATCH_ON,
        "minimum_pairs": minimum,
        "minimum_coverage": min_coverage,
        "minimum_coverage_rule": (
            "The share of its own speeches a speaker must have found partners for "
            "before its table is published. The UN Secretariat is why this threshold "
            "exists: it is the only speaker in its group, so partners were found for "
            "2.6% of its 4,709 speeches — comfortably above the minimum number of "
            "pairs, and still a table describing a lopsided fortieth of its record. "
            "The threshold is set by hand rather than calculated, and coverage is "
            "published for every speaker so that a reader can disagree with where it "
            "was drawn."
        ),
        "minimum_pairs_rule": (
            "The number of pairs a speaker needs before its table is published. The "
            "figure is carried over from the minimum used elsewhere on the Actors page "
            "rather than calculated here: publishing a table for a speaker whose rates "
            "that page withholds would describe a delegation beside a blank. The "
            f"statistical guard sits on each row instead — a word needs {lexical.MIN_COUNT} "
            "occurrences in the speaker's own speeches before it is reported at all. "
            "Counted in pairs rather than speeches, because pairs are what the "
            "comparison is built from."
        ),
        "control_rule": (
            "Each of the speaker's speeches is paired with one delivered by somebody "
            "else in the same year, on the same agenda item and from the same speaker "
            "group. No speech is used twice. Where a group holds fewer such speeches "
            "than the speaker gave, the shortfall is reported rather than filled from "
            "elsewhere, and the coverage figure says how much of the speaker's record "
            "the comparison actually rests on."
        ),
        "unmatched_rule": (
            "This reading sets the same speaker against the whole corpus instead of "
            "against comparable speeches. It is the comparison the pairing exists to "
            "improve on, published so a reader can see what holding the occasion "
            "constant removed. A word whose effect collapses belonged to the occasion; "
            "a word that holds up belongs to the speaker."
        ),
        "reading_rule": (
            "A word appears here because this speaker used it at a different rate from "
            "comparable speakers on the same occasion. That is not a position, a policy "
            "or a belief, and it says nothing about whether the speaker approved or "
            "objected."
        ),
        "self_reference_rule": (
            "An asterisk marks a word taken from the speaker's own official name. "
            "Every delegation says its own name constantly, and those rows would "
            "otherwise fill the top of every table. They are marked rather than "
            "removed. The check is mechanical and therefore partial: it catches "
            "'russian' and 'federation' for the Russian Federation, and misses 'french' "
            "and 'beijing', which do not appear in the names they belong to. An "
            "unmarked row is not a guarantee that the word is not the speaker naming "
            "itself."
        ),
        "seed": seed,
        "repetitions": repetitions,
        "limit": limit,
        "corpus_tokens": reference_total,
        "corpus_types": len(matrix.words),
        "speakers_total": total_speakers,
        "speakers_considered": len(rows),
        "speakers_published": published,
        "speakers_withheld": withheld,
        "speakers": rows,
    }
    meta = artifacts.provenance(
        ROOT,
        "12_speaker_keyness.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[STOPWORDS, COUNCIL_MEMBERSHIP],
        extra={
            "stopwords": len(stopwords),
            "min_count": lexical.MIN_COUNT,
            "minimum_pairs": minimum,
            "minimum_coverage": min_coverage,
            "seed": seed,
        },
    )
    # One file, written in place: `countries/` already holds 11's table, and
    # `artifacts.atomic_directory` replaces a directory wholesale.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    artifacts.atomic_write_json(OUTPUT, {"meta": meta, **payload})
    console.info(f"wrote {rel(OUTPUT)}  ({OUTPUT.stat().st_size / 1e3:,.0f} kB)")

    note = write_note("12_speaker_keyness.md", build_note(payload, rows, withheld))
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20_260_807, help="control-sampling seed")
    parser.add_argument("--limit", type=int, default=keyness.LIMIT, help="rows per table")
    parser.add_argument(
        "--repetitions",
        type=int,
        default=10,
        help="extra seeds used for the keyword stability interval; 0 to skip",
    )
    parser.add_argument(
        "--minimum",
        type=int,
        default=keyness.MIN_PAIRS,
        help="matched pairs a speaker needs before its keywords are published",
    )
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=keyness.MIN_COVERAGE,
        help="share of its own speeches a speaker must have matched to be published",
    )
    parser.add_argument(
        "--speakers",
        type=int,
        default=0,
        help="profile only the N largest candidates — a quick look, not a release run",
    )
    args = parser.parse_args()
    run(
        args.seed,
        args.limit,
        args.repetitions,
        args.minimum,
        args.minimum_coverage,
        args.speakers,
    )


if __name__ == "__main__":
    main()
