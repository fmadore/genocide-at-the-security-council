"""Draw the human gold sample the model-assisted usage layer is measured against.

`genocide` is the term that layer is built on: 6,092 occurrences in 3,273 of the
106,302 speeches. Step 14 annotates all of them with a model, and a model run is
worth exactly as much as the human sample it was scored against. This step draws
that sample — 120 occurrences by equal probability, 80 more chosen to cover every
period and cue stratum — and leaves it for two coders to work through against
`annotations/lexicon/CODEBOOK.md`.

Three properties it is built for:

- **One enumeration, checked against the published one.** The occurrences come
  from `lib.occurrences`, the module 13, 14 and 15 share, and the run refuses to
  continue unless it reproduces the 3,273 speeches / 6,092 occurrences documented
  in docs/CORPUS.md §8. A gold sample drawn from a different population than the
  one the model annotates would measure nothing.
- **Hard cases on purpose.** 4,759 of the 6,092 occurrences are plain uses; an
  equal-probability sample of 200 would contain about four rejections and none of
  several periods. Each occurrence therefore carries a `cue` read off its ±150
  character window — `rejection`, `quotation`, `commemorative`, `dense_meeting`,
  `plain` — and the coverage half of the sample guarantees every period-cue
  stratum is present. The cue is a sampling device, never a label: it says this
  window contains rejection *language*, not that the speaker rejects anything.
  The coders decide that, and the recorded inclusion probabilities are what let a
  later step weight the sample back to the population.
- **The human file is never written.** These candidates get their own annotation
  file, `annotations/genocide/annotations.csv`. 03's audit file is a different
  sample: `lib.audit.merge` refuses annotations whose occurrence is not among the
  candidates it was handed, so sharing one file would make each step reject the
  other's work.

Usage:
    python scripts/13_gold_sample.py [--probability 120] [--coverage 80] [--seed 21]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, audit, console, frames, lexicon, occurrences, text
from lib.paths import (
    INTERIM,
    LEXICON,
    MANIFESTS,
    ROOT,
    SPEECHES_NORM,
    ensure_dirs,
    rel,
    write_note,
)

TERM = "genocide"

#: docs/CORPUS.md §8, and reproduced exactly by 03 and 08. The gold sample is
#: only comparable to the model run if both enumerate this same population, so
#: these are asserted rather than reported.
DOCUMENTED_SPEECHES = 3_273
DOCUMENTED_OCCURRENCES = 6_092

#: Only the columns the sample needs. The frame is 131 MB, nearly all of it text.
COLUMNS = [
    "filename",
    "body_start",
    "text",
    "year",
    "meeting_symbol",
    "date",
    "country_org",
    "agenda_item_manual",
]

#: The seven densest meetings, docs/CORPUS.md §8.6. Together they hold a tenth of
#: the occurrences, and they are where the word is argued over at length rather
#: than mentioned in passing — the Srebrenica veto, the two Rwanda anniversaries,
#: the tribunals. A sample that missed them would miss the sustained arguments.
DENSE_MEETINGS: frozenset[str] = frozenset(
    {"S/PV.7155", "S/PV.4127", "S/PV.7481", "S/PV.8576", "S/PV.7192", "S/PV.3453", "S/PV.9069"}
)

#: Windows where the speaker is arguing about the word rather than simply using
#: it. Every pattern is anchored on the term and kept literal, and the comment
#: beside it is a real window from `data/derived/kwic/genocide.json`. The last
#: two show why this is a sampling device and not a label: an "alleged genocide
#: financier" is a person's alleged role, and a tribunal that "refuses to
#: consider the causes of the genocide" is being accused of something else
#: entirely. What the stratum guarantees is that the coders see this language.
REJECTION: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # "confirming that no genocide had taken place in Darfur" — S/PV.7963
        r"\bno genocid",
        # "the question of whether or not genocide had been committed" — S/PV.5040
        r"\bnot (?:a |an )?genocid",
        # "cooked-up lies about so-called genocide and forced labour" — S/PV.9052
        r"so-called\W*(?:\w+\W+){0,2}genocid",
        # "top fugitive and alleged genocide financier" — S/PV.5697
        r"\balleged(?:ly)? genocid",
        # "a tribunal which refuses to consider the causes of the genocide" — S/PV.3453
        r"refus\w*[^.]{0,60}genocid",
    )
)

#: Straight and curly double quotes. A quotation mark in either context window is
#: the cheapest available sign of reported or quoted speech, which the codebook
#: separates from the speaker's own formulation and which a model conflates most
#: readily. Single quotes are excluded: the corpus's apostrophes would swallow
#: the stratum whole.
QUOTATION = re.compile('["“”]')

#: The commemorative register, which the corpus reaches for every April.
COMMEMORATIVE: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # "to commemorate the twentieth anniversary of the genocide" — S/PV.7155
        r"commemorat",
        r"anniversar",
        r"remember",
        # "a minute of silence in memory of those who lost their lives" — S/PV.3513
        r"memory of",
        # "efforts to honour the victims of the genocide" — S/PV.7192
        r"hono(?:u)?r the victims",
    )
)

#: Precedence order, rarest first: a window carrying rejection language inside a
#: quotation inside a dense meeting is sampled as a rejection, because that is
#: the property the sample would otherwise be short of.
CUES: tuple[str, ...] = ("rejection", "quotation", "commemorative", "dense_meeting", "plain")

GOLD_CANDIDATES = INTERIM / "genocide_gold_candidates.csv"
GOLD_REVIEW = INTERIM / "genocide_gold_review.csv"
GOLD_PROBABILITY = INTERIM / "genocide_gold_probability.csv"
GOLD_COVERAGE = INTERIM / "genocide_gold_coverage.csv"
GOLD_ANNOTATIONS = ROOT / "annotations" / "genocide" / "annotations.csv"
# The controlled referents are shared with 03's audit: one list of cases and
# entities for the project, not one per sample.
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"


def classify_cue(left: str, keyword: str, right: str, meeting_symbol: str) -> str:
    """The stratum one occurrence belongs to, read off its own context window."""
    window = f"{left} {keyword} {right}"
    if any(pattern.search(window) for pattern in REJECTION):
        return "rejection"
    if QUOTATION.search(left) or QUOTATION.search(right):
        return "quotation"
    if any(pattern.search(window) for pattern in COMMEMORATIVE):
        return "commemorative"
    if meeting_symbol in DENSE_MEETINGS:
        return "dense_meeting"
    return "plain"


def check_population(found: list[occurrences.Occurrence]) -> list[str]:
    """Reasons the enumeration cannot be the documented one, if any."""
    problems = []
    if len(found) != DOCUMENTED_OCCURRENCES:
        problems.append(
            f"{len(found):,} occurrences against the {DOCUMENTED_OCCURRENCES:,} "
            "documented in docs/CORPUS.md §8"
        )
    speeches = len({occurrence.filename for occurrence in found})
    if speeches != DOCUMENTED_SPEECHES:
        problems.append(
            f"{speeches:,} speeches against the {DOCUMENTED_SPEECHES:,} "
            "documented in docs/CORPUS.md §8"
        )
    return problems


def _period(year: int) -> str:
    return f"{year // 10 * 10}s"


def candidate_rows(
    speeches: pd.DataFrame,
    bodies: pd.Series,
    found: list[occurrences.Occurrence],
    term: lexicon.Term,
    lex: lexicon.Lexicon,
) -> pd.DataFrame:
    """One row per occurrence, in 03's audit-candidate shape plus the cue.

    The columns are 03's, in 03's order, so the two candidate files can be read
    and diffed as one format; `cue` and `line_id` are appended rather than
    interleaved. `line_id` is the KWIC identifier, which is what lets a coder
    open the same occurrence in the concordance or the reader view.
    """
    rows: list[dict[str, object]] = []
    for occurrence in found:
        meta = speeches.loc[occurrence.index]
        body = bodies.loc[occurrence.index]
        left, keyword, right = text.window(body, occurrence.start, occurrence.end)
        rows.append(
            {
                "occurrence_id": occurrence.occurrence_id,
                "schema_version": audit.SCHEMA_VERSION,
                "lexicon_version": lex.version,
                "unit": "occurrence",
                "term": term.name,
                "tier": term.tier,
                "register": term.register,
                "period": _period(int(meta["year"])),
                "filename": occurrence.filename,
                "meeting_symbol": meta["meeting_symbol"],
                "date": f"{meta['date']:%Y-%m-%d}",
                "country_org": meta["country_org"],
                "agenda": meta["agenda_item_manual"],
                "start": occurrence.start,
                "end": occurrence.end,
                "source_sha256": occurrence.source_sha256,
                "source_length": len(body),
                "left": left,
                "keyword": keyword,
                "right": right,
                "cue": classify_cue(left, keyword, right, str(meta["meeting_symbol"])),
                "line_id": occurrence.line_id,
            }
        )
    return pd.DataFrame(rows)


def draw(candidates: pd.DataFrame, probability: int, coverage: int, seed: int) -> pd.DataFrame:
    """The two sampling frames, concatenated as 03 concatenates its three.

    An occurrence drawn by both keeps both rows: the sampling metadata differs,
    and dropping one would silently change the inclusion probability recorded
    for the other. `candidate_id` is per frame, so the rows stay distinguishable.
    """
    return pd.concat(
        [
            audit.probability_sample(candidates, probability, seed, audit.PROBABILITY),
            audit.coverage_sample(candidates, coverage, seed + 1, strata=("period", "cue")),
        ],
        ignore_index=True,
    )


def build_note(
    candidates: pd.DataFrame,
    sample: pd.DataFrame,
    probability: int,
    coverage: int,
    seed: int,
    annotated: int,
) -> str:
    population = len(candidates)
    frames_seen = {
        name: sample.loc[sample["sampling_frame"] == name]
        for name in (audit.PROBABILITY, audit.COVERAGE)
    }
    unique = int(sample["occurrence_id"].nunique())

    cue_rows = []
    for cue in CUES:
        total = int((candidates["cue"] == cue).sum())
        cue_rows.append(
            f"| `{cue}` | {total:,} | {total / population:.1%} | "
            f"{int((frames_seen[audit.PROBABILITY]['cue'] == cue).sum())} | "
            f"{int((frames_seen[audit.COVERAGE]['cue'] == cue).sum())} |"
        )

    period_rows = []
    for period in sorted(candidates["period"].unique()):
        total = int((candidates["period"] == period).sum())
        period_rows.append(
            f"| {period} | {total:,} | {total / population:.1%} | "
            f"{int((frames_seen[audit.PROBABILITY]['period'] == period).sum())} | "
            f"{int((frames_seen[audit.COVERAGE]['period'] == period).sum())} |"
        )

    strata = int(sample["strata_total"].dropna().max()) if "strata_total" in sample else 0

    return "\n".join(
        [
            "# 13 — Gold sample",
            "",
            f"**{population:,} occurrences** of `{TERM}` in "
            f"{candidates['filename'].nunique():,} speeches, the population step 14 "
            "annotates in full.",
            "Checked against the 3,273 speeches / 6,092 occurrences documented in",
            "docs/CORPUS.md §8; the run fails rather than sampling a population that",
            "disagrees with the published one.",
            "",
            "## The sample",
            "",
            "| Frame | Rows | Size | Seed |",
            "|---|---:|---:|---:|",
            f"| probability | {len(frames_seen[audit.PROBABILITY])} | {probability} | {seed} |",
            f"| coverage | {len(frames_seen[audit.COVERAGE])} | {coverage} | {seed + 1} |",
            "",
            f"{len(sample)} candidate rows over **{unique} distinct occurrences**: the two "
            f"frames overlap by {len(sample) - unique}, and both rows are kept because each "
            "records its own inclusion probability.",
            f"The coverage frame is stratified by period and cue, {strata} strata in all, one "
            "occurrence drawn from each before the random fill.",
            "",
            "## Cues",
            "",
            "The cue is read off the ±150-character window and is a sampling stratum, not a",
            "label: it records that the window contains this language, never that the speaker",
            "is doing what the name says. Coders decide that, and only the codebook's fields",
            "carry their decision.",
            "",
            "| Cue | Occurrences | % of population | Probability | Coverage |",
            "|---|---:|---:|---:|---:|",
            *cue_rows,
            "",
            "## Periods",
            "",
            "| Period | Occurrences | % of population | Probability | Coverage |",
            "|---|---:|---:|---:|---:|",
            *period_rows,
            "",
            "## Coding",
            "",
            f"Candidates are written to `{rel(GOLD_CANDIDATES)}`, and to one file per frame.",
            f"Human work belongs in `{rel(GOLD_ANNOTATIONS)}`, which this step reads and never",
            f"writes; `{rel(GOLD_REVIEW)}` is the generated join used for review.",
            f"**{annotated}** coder-occurrence rows are coded so far, out of the {unique} "
            f"occurrences each of the two coders takes independently ({2 * unique} rows when",
            "the sample is complete), following `annotations/lexicon/CODEBOOK.md`.",
            "",
        ]
    ) + "\n"


def run(probability: int, coverage: int, seed: int) -> None:
    ensure_dirs()

    console.step("Reading the normalised corpus")
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)

    console.step("Loading the lexicon")
    lex = lexicon.load()
    if TERM not in lex.terms or not lex.terms[TERM].enabled:
        console.fail(f"'{TERM}' is not an active term in {rel(LEXICON)}")
    term = lex.terms[TERM]
    console.info(f"version {lex.version} ({lex.updated}), `{TERM}` matches {term.pattern}")

    console.step("Enumerating occurrences")
    found = occurrences.enumerate_term(speeches, bodies, term)
    if problems := check_population(found):
        console.fail("the enumeration disagrees with docs/CORPUS.md §8", problems)
    console.info(
        f"{len(found):,} occurrences in "
        f"{len({occurrence.filename for occurrence in found}):,} speeches"
    )

    console.step("Classifying cues")
    candidates = candidate_rows(speeches, bodies, found, term, lex)
    console.table([(cue, f"{int((candidates['cue'] == cue).sum()):,}") for cue in CUES])

    console.step("Drawing the gold sample")
    sample = draw(candidates, probability, coverage, seed)
    unique = int(sample["occurrence_id"].nunique())
    console.info(
        f"{len(sample)} candidate rows over {unique} distinct occurrences "
        f"(seeds {seed} and {seed + 1})"
    )
    review = audit.write_outputs(
        sample,
        annotation_path=GOLD_ANNOTATIONS,
        candidate_path=GOLD_CANDIDATES,
        review_path=GOLD_REVIEW,
        frame_paths={
            audit.PROBABILITY: GOLD_PROBABILITY,
            audit.COVERAGE: GOLD_COVERAGE,
        },
        referent_path=REFERENTS,
    )
    coded = review.loc[review["coder"].astype("string").str.len().gt(0)]
    annotated = len(coded.drop_duplicates(["occurrence_id", "coder"]))
    console.info(
        f"wrote {rel(GOLD_CANDIDATES)} and {rel(GOLD_REVIEW)} ({annotated} annotations)"
    )

    console.step("Writing")
    note = write_note(
        "13_gold_sample.md",
        build_note(candidates, sample, probability, coverage, seed, annotated),
    )
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "13_gold_sample.py",
        inputs=[SPEECHES_NORM],
        configs=[LEXICON, GOLD_ANNOTATIONS, REFERENTS],
        extra={
            "outputs": [
                artifacts.describe_file(GOLD_CANDIDATES, ROOT),
                artifacts.describe_file(GOLD_REVIEW, ROOT),
                artifacts.describe_file(GOLD_PROBABILITY, ROOT),
                artifacts.describe_file(GOLD_COVERAGE, ROOT),
            ],
            "lexicon_version": lex.version,
            "term": TERM,
            "population": {
                "occurrences": len(candidates),
                "speeches": int(candidates["filename"].nunique()),
                "cues": {cue: int((candidates["cue"] == cue).sum()) for cue in CUES},
            },
            "sample": {
                "rows": len(sample),
                "occurrences": unique,
                "annotated": annotated,
                "probability": {"size": probability, "seed": seed},
                "coverage": {"size": coverage, "seed": seed + 1, "strata": ["period", "cue"]},
                "cues": {cue: int((sample["cue"] == cue).sum()) for cue in CUES},
            },
        },
    )
    artifacts.atomic_write_json(MANIFESTS / "13_gold_sample.json", manifest, indent=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probability", type=int, default=120, help="equal-probability draws")
    parser.add_argument("--coverage", type=int, default=80, help="period-cue coverage draws")
    parser.add_argument("--seed", type=int, default=21, help="sampling seed")
    args = parser.parse_args()
    run(args.probability, args.coverage, args.seed)


if __name__ == "__main__":
    main()
