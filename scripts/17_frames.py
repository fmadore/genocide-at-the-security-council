"""Grammatical frames: what construction the word appears in, and how that moved.

Reads speeches_flagged.parquet, classifies every occurrence of `genocide` with
the codebook in `lib/node_frames.py`, and writes
data/derived/frames/frames.json and frames/occurrences.json plus a findings
note.

The review of 1 September 2026 (§3.6, item 2) asks the cheapest useful question
the concordance can answer and the frequency series cannot: the same word does
nomination, legal qualification, hedging, distancing, denial and prevention, and
none of the published figures tells those apart. 08 already stores every
occurrence; this step reads the window around each one and files it.

Three things this step is careful about, in each case a way for the table to be
wrong while looking right.

- **A share is not a count.** Every frame's share of a year or a speaker group is
  a binomial proportion with a known denominator, so it travels with its Wilson
  interval (`series.wilson_interval`), and the annual series is tested for a
  change point against a null that permutes *meetings* rather than occurrences
  (`series.meeting_blocks`, `series.rate_change_point`). One debate that used the
  word two hundred times counts as one draw. That is the machinery roadmap S1
  landed for the rate series, applied here to composition.
- **The denominator is occurrences, not speeches.** Everything on this artefact
  divides by occurrences of the node, so it describes how the word was used, not
  how often. A frame's share rising while the rate falls is a real and different
  finding, and reading one as the other is the mistake the note and the figure's
  caveat both name.
- **The residue is published.** `unframed` is a row like any other and its share
  is a series like any other, because it is not stationary: about a third of the
  1990s occurrences fall outside the codebook against a tenth of 2018's. A frame
  that gained share while the residue shrank may have gained nothing.

The triangulation against the two committed model runs is the external check the
review promises for free. Both runs label all 6,092 occurrences with `stance`
and `function`; the frames are computed from the text with no model involved, so
crossing them says where a construction and a label agree — and where a label is
doing something the construction does not support. Nothing here adjudicates: the
frames are not ground truth for the model and the model is not ground truth for
the frames.

Usage:
    python scripts/17_frames.py [--trials 2000] [--no-model]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, llm, node_frames, series
from lib import lexicon as lexicon_lib
from lib import occurrences as occurrences_lib
from lib.paths import (
    FRAMES,
    LEXICON,
    MODEL_ANNOTATIONS,
    ROOT,
    SPEECHES_FLAGGED,
    ensure_dirs,
    rel,
    write_note,
)

TERM = "genocide"

#: Columns this step reads. The frame is 130 MB and most of it is text, which is
#: needed — the window is cut from it — while the ninety lexicon columns are not.
COLUMNS = [
    "row_id",
    "filename",
    "year",
    "date",
    "meeting_symbol",
    "country_org",
    "speaker_group",
    "agenda_item_manual",
    "text",
    "body_start",
]

#: Occurrences a slice needs before its shares are published. Below this the
#: counts are written and the shares are null, on the same rule
#: `11_countries.py` withholds a rate: at n = 40 the widest Wilson interval on a
#: proportion is about ±16 points, which is coarse and says so; at n = 10 it is
#: ±31 and the ordering of seventeen frames would be noise. The number is set by
#: hand and published, so a reader can disagree with where it was drawn.
MINIMUM_OCCURRENCES = 40

#: Occurrences a frame needs across the corpus before its annual share is put
#: through the change-point test. A share that averages 0.6% over 32 years has
#: at most a handful of occurrences in most of them, and a two-rate partition of
#: that series is a description of which years happened to hold two.
MINIMUM_FOR_TEST = 250

#: Eight-year blocks. Coarser than the chronology's years because this is a
#: composition of a few thousand occurrences rather than a rate over 106,302
#: speeches: at annual grain a seventeen-way split has cells of four. Four blocks
#: divide 1992-2023 evenly and each holds over 800 occurrences.
BLOCK_YEARS = 8

STORE = MODEL_ANNOTATIONS / TERM
RUNS = STORE / "runs"
CURRENT_RUN = STORE / "current_run.txt"
COMPARISON_RUN = STORE / "comparison_run.txt"

#: The model fields a frame is crossed against. `stance` is single-label and
#: `function` is pipe-joined, as `lib.usage` documents; they are handled apart
#: for that reason and not for any other.
STANCE_FIELD = "stance"
FUNCTION_FIELD = "function"


# --- Classifying --------------------------------------------------------------


def classify_occurrences(
    speeches: pd.DataFrame, term: lexicon_lib.Term, width: int
) -> pd.DataFrame:
    """One row per occurrence: its identity, its frame, its matches, its form.

    Through `lib.occurrences.enumerate_term` rather than a private re-reading of
    the regex, so that `occurrence_id` here is the same identity 13, 14 and 15
    use and the model runs join to these rows without a second definition of what
    an occurrence is.
    """
    bodies = frames.body(speeches)
    found = occurrences_lib.enumerate_term(speeches, bodies, term)
    body_of = dict(bodies.items())

    rows = []
    for occurrence in found:
        window = node_frames.window_at(
            body_of[occurrence.index], occurrence.start, occurrence.end, width
        )
        matched = node_frames.matches(window)
        rows.append(
            {
                "index": occurrence.index,
                "line_id": occurrence.line_id,
                "occurrence_id": occurrence.occurrence_id,
                "keyword": occurrence.keyword,
                "frame": matched[0] if matched else node_frames.UNFRAMED,
                "matched": "|".join(matched),
                "n_matched": len(matched),
                "form": node_frames.morphology(occurrence.keyword),
            }
        )
    frame = pd.DataFrame(rows)
    attributes = (
        speeches.loc[frame["index"].tolist(), ["year", "meeting_symbol", "speaker_group"]]
        .reset_index(drop=True)
        .astype("object")
    )
    return pd.concat([frame.reset_index(drop=True), attributes], axis=1)


def check_against_flags(speeches: pd.DataFrame, found: int) -> list[str]:
    """The same reconciliation 08 makes, for the same reason.

    A composition that does not add up to the occurrence count published beside
    it leaves a reader with two numbers and no way to tell which is wrong.
    """
    column = f"{lexicon_lib.COUNT}{TERM}"
    if column not in speeches.columns:
        return []
    expected = int(speeches[column].sum())
    if found == expected:
        return []
    return [
        f"{found:,} occurrences classified against {expected:,} counted in "
        f"speeches_flagged.parquet"
    ]


# --- Where the composition changed --------------------------------------------


def change_block(
    occurrences: pd.DataFrame, annual: dict[str, object], trials: int, seed: int, alpha: float
) -> dict[str, object]:
    """`node_frames.share_change_points` with the prose a reader needs beside it.

    The arithmetic is in the library and the account of what it means is here,
    the way `04_series.py` wraps `series.rate_change_point`: the caveat is part
    of the artefact and has to travel with the numbers, but it is not something
    a unit test should have to import.
    """
    results, adjusted = node_frames.share_change_points(
        occurrences,
        annual,
        minimum=MINIMUM_FOR_TEST,
        trials=trials,
        seed=seed,
        alpha=alpha,
    )
    return {
        "method": (
            "Single two-rate maximum likelihood partition of a frame's share of the "
            "year's occurrences, calibrated by permuting meetings across years under a "
            "constant-share null, with the independent-occurrence bootstrap beside it"
        ),
        "null": series.NULL_MEETING_BLOCK,
        "minimum_occurrences": MINIMUM_FOR_TEST,
        "familywise_alpha": alpha,
        "per_test_alpha": adjusted,
        "correction": f"Bonferroni across {len(results)} frames large enough to test",
        "trials": trials,
        "caveat": (
            "A share can move because a frame grew or because the frames beside it "
            "shrank; these tests are one per frame and are not a test of the "
            "composition as a whole. The unframed residue is itself tested, and a "
            "frame whose split falls in the same year as the residue's is describing "
            "the codebook's reach rather than the Council's usage."
        ),
        "tested": results,
    }


# --- Triangulation against the committed model runs ---------------------------


def named_run(pointer: Path) -> str:
    """The run id a committed pointer file names, or the empty string."""
    if not pointer.is_file():
        return ""
    return pointer.read_text(encoding="utf-8").strip()


def model_rows(run_id: str) -> list[dict[str, object]]:
    return llm.read_rows(RUNS / run_id / "annotations.jsonl") if run_id else []


def triangulation(
    occurrences: pd.DataFrame, runs: list[tuple[str, list[dict]]]
) -> dict[str, object]:
    """The frames crossed against `stance` and `function`, once per run."""
    blocks = []
    for run_id, rows in runs:
        labelled = pd.DataFrame(rows)
        if labelled.empty or "occurrence_id" not in labelled.columns:
            continue
        matched = int(
            occurrences["occurrence_id"].isin(set(labelled["occurrence_id"].astype(str))).sum()
        )
        blocks.append(
            {
                "run_id": run_id,
                "model": str(labelled["model"].iloc[0]) if "model" in labelled else "",
                "rows": len(labelled),
                "matched": matched,
                "coverage": matched / len(occurrences) if len(occurrences) else None,
                "stance": node_frames.crosstab(
                    occurrences, labelled, STANCE_FIELD, multi=False
                ),
                "function": node_frames.crosstab(
                    occurrences, labelled, FUNCTION_FIELD, multi=True
                ),
            }
        )
    return {
        "rule": (
            "The frames are read off the text with no model involved and the labels are "
            "read off a model with no frame involved, so a cell where the two agree is "
            "two instruments finding the same thing and a cell where they do not is a "
            "question. Neither is the other's ground truth: the human gold sample in "
            "annotations/ is the only calibration this project has."
        ),
        "runs": blocks,
    }


# --- The note -----------------------------------------------------------------


def build_note(payload: dict, lexicon_version: str) -> str:
    total = int(payload["occurrences"])
    totals = {row["frame"]: row for row in payload["totals"]["frames"]}
    ranked = sorted(payload["totals"]["frames"], key=lambda row: -int(row["occurrences"]))
    residue = totals[node_frames.UNFRAMED]
    annual = payload["by_year"]
    residue_years = annual["frames"][node_frames.UNFRAMED]["share"]
    published = [
        (year, share)
        for year, share in zip(annual["years"], residue_years, strict=True)
        if share is not None
    ]
    # A corpus whose thinnest year clears the minimum is the ordinary case; the
    # synthetic one the end-to-end test builds is not, and a note that crashed
    # on it would make that test unable to run the step at all.
    drift = (
        f"It is also not stationary: it runs at {published[0][1]:.0%} in {published[0][0]} "
        f"and {published[-1][1]:.0%} in {published[-1][0]}, so a frame that gained share "
        "may have gained it from the residue rather than from another frame."
        if published
        else (
            "No year in this corpus holds enough occurrences for its share to be "
            "published, so whether the residue drifts cannot be said here."
        )
    )

    def frame_line(row: dict) -> str:
        gloss = next(
            entry["gloss"] for entry in payload["codebook"] if entry["frame"] == row["frame"]
        ) if row["frame"] != node_frames.UNFRAMED else (
            "No pattern in the codebook reached this occurrence."
        )
        return (
            f"| `{row['frame']}` | {row['occurrences']:,} | {row['share']:.1%} | "
            f"{row['matched']:,} | {gloss.split('.')[0]}. |"
        )

    accepted = [
        f"`{tested['frame']}` at {tested['result']['label']} "
        f"({tested['result']['before']:.1%} to {tested['result']['after']:.1%}, "
        f"p = {tested['result']['p_value']:.3f})"
        for tested in payload["change"]["tested"]
        if tested["result"] and tested["result"]["accepted"]
    ]
    model = payload["triangulation"]["runs"]

    return (
        "\n".join(
            [
                "# 17 — Grammatical frames of the node",
                "",
                f"**{total:,} occurrences** of `{TERM}` filed into "
                f"{len(node_frames.CODEBOOK)} constructions plus a residue, from a "
                f"±{payload['window']}-character window. Lexicon version "
                f"{lexicon_version}.",
                "",
                "The question is what the word is *doing*, not how often it is said. Every",
                "figure here divides by occurrences of the node, so a frame's share can rise",
                "in a year the rate falls, and that is a finding rather than a contradiction.",
                "",
                "## The distribution",
                "",
                "`matched` counts every occurrence the pattern reached, before precedence;",
                "`occurrences` counts the ones it won. The gap is where the codebook overlaps",
                "itself, and it is published because precedence is a decision a reader should",
                "be able to price.",
                "",
                "| Frame | Occurrences | Share | Matched | Act |",
                "|---|---:|---:|---:|---|",
                *[frame_line(row) for row in ranked],
                "",
                f"**{residue['occurrences']:,} occurrences "
                f"({residue['occurrences'] / total:.1%}) are unframed.** That is not a "
                "remainder to be widened away. The residue is",
                "coordination with atrocity nouns the triad does not hold (*aggression and",
                "genocide*, *massacres and genocide*), and bare definite reference whose case",
                f"was named a sentence earlier. {drift}",
                "",
                "## The wordform",
                "",
                "`\\bgenocid\\w*` folds four things into one count, which is the construct-validity",
                "point §3.4 of the review makes about `genocidaire`.",
                "",
                "| Form | Occurrences | Category |",
                "|---|---:|---|",
                *[
                    f"| `{row['form']}` | {row['occurrences']:,} | {row['category']} |"
                    for row in payload["morphology"]["forms"]
                ],
                "",
                "## Where a share changed",
                "",
                f"{payload['change']['correction']}, alpha = "
                f"{payload['change']['per_test_alpha']:.4f}, "
                f"{payload['change']['trials']:,} permutations of the meeting assignment.",
                "",
                (
                    "Accepted: " + "; ".join(accepted) + "."
                    if accepted
                    else "No frame's share survives the meeting-block null at the corrected level."
                ),
                "",
                "## Against the model runs",
                "",
                "Both runs label every occurrence with a stance and a function; the frames were",
                "read off the text with no model involved. Where the two agree, a construction",
                "and a label are two instruments finding the same thing. Where they do not, the",
                "cell is a question — and the review's largest disagreement, the",
                "report/assert boundary, is one this table can locate.",
                "",
                "| Run | Model | Matched | Triad → modal stance | Distancing → modal stance |",
                "|---|---|---:|---|---|",
                *[
                    "| `{run}` | {model} | {matched:,} | {triad} | {distancing} |".format(
                        run=block["run_id"],
                        model=block["model"],
                        matched=block["matched"],
                        triad=_modal(block, "atrocity_triad"),
                        distancing=_modal(block, "distancing"),
                    )
                    for block in model
                ],
                "",
                "**To check:** read the twenty longest-standing cells where a frame and a",
                "stance disagree — `distancing` coded `asserts`, `commemoration` coded",
                "`neutral_legal_reference` — against the concordance lines behind them. If the",
                "frame is right and the label is not, the prompt's category definitions are",
                "where §4.2 says the fix belongs; if the label is right, the pattern is here.",
                "",
            ]
        )
        + "\n"
    )


def _modal(block: dict, frame_name: str) -> str:
    """One frame's modal stance in one run, for the note's summary table."""
    for row in block["stance"]["rows"]:
        if row["frame"] == frame_name:
            if not row["modal_label"]:
                return "—"
            return f"{row['modal_label']} ({row['modal_share']:.0%})"
    return "—"


# --- The run ------------------------------------------------------------------


def run(width: int, trials: int, seed: int, alpha: float, use_model: bool) -> None:
    ensure_dirs()

    lex = lexicon_lib.load()
    if TERM not in lex.terms or not lex.terms[TERM].enabled:
        console.fail(f"'{TERM}' is not an active term in {rel(LEXICON)}")
    console.info(f"lexicon version {lex.version}, node `{TERM}` = {lex.terms[TERM].pattern}")

    console.step("Reading the flagged corpus")
    speeches = frames.read(
        SPEECHES_FLAGGED, columns=[*COLUMNS, f"{lexicon_lib.HAS}{TERM}", f"{lexicon_lib.COUNT}{TERM}"]
    )
    bearing = speeches[speeches[f"{lexicon_lib.HAS}{TERM}"]].copy()
    console.info(f"{len(bearing):,} speeches carry the node")

    console.step("Classifying every occurrence")
    occurrences = classify_occurrences(bearing, lex.terms[TERM], width)
    if problems := check_against_flags(speeches, len(occurrences)):
        console.fail("the classification disagrees with speeches_flagged.parquet", problems)
    console.info(
        f"{len(occurrences):,} occurrences, reproducing the counted total exactly"
    )

    counts = Counter(occurrences["frame"])
    matched = Counter(
        label for labels in occurrences["matched"] for label in labels.split("|") if label
    )
    for name in node_frames.FRAME_NAMES:
        console.info(
            f"{name:22s} {counts.get(name, 0):>6,}  {counts.get(name, 0) / len(occurrences):>6.1%}"
        )

    console.step("Shares, by year and by slice")
    first_year = int(occurrences["year"].min())
    annual = node_frames.annual_block(occurrences, MINIMUM_OCCURRENCES)
    period = occurrences["year"].map(
        lambda year: node_frames.period_label(int(year), first_year, BLOCK_YEARS)
    )
    slices = {
        "period": node_frames.slice_rows(occurrences, period, MINIMUM_OCCURRENCES),
        "speaker_group": node_frames.slice_rows(
            occurrences,
            occurrences["speaker_group"].astype("string").fillna("Unknown"),
            MINIMUM_OCCURRENCES,
        ),
    }
    console.info(
        f"{len(slices['period'])} periods, {len(slices['speaker_group'])} speaker groups"
    )

    console.step("Testing each large frame's share against a meeting-block null")
    change = change_block(occurrences, annual, trials, seed, alpha)
    console.info(
        f"{len(change['tested'])} frames tested, "
        f"{sum(1 for t in change['tested'] if t['result'] and t['result']['accepted'])} accepted"
    )

    console.step("Crossing the frames with the committed model runs")
    run_ids = [named_run(CURRENT_RUN), named_run(COMPARISON_RUN)] if use_model else []
    loaded = [(run_id, model_rows(run_id)) for run_id in run_ids if run_id]
    for run_id, rows in loaded:
        if not rows:
            console.warn(f"{run_id} has no rows; it is left out of the triangulation")
    model = triangulation(occurrences, [(r, rows) for r, rows in loaded if rows])
    for block in model["runs"]:
        console.info(
            f"{block['run_id']}: {block['matched']:,} of {len(occurrences):,} occurrences "
            f"joined ({block['coverage']:.1%})"
        )
        if block["matched"] == 0:
            console.fail(
                f"{block['run_id']} joins none of this corpus's occurrences",
                [
                    "the run was drawn from a different enumeration of the term",
                    "re-run 03_lexicon.py, or annotate again against this lexicon",
                ],
            )
    if not model["runs"]:
        console.warn("no model run was read; the triangulation block is written empty")

    console.step("Writing")
    forms = Counter(occurrences["keyword"].str.lower())
    payload: dict[str, object] = {
        "term": TERM,
        "pattern": lex.terms[TERM].pattern,
        "window": width,
        "occurrences": len(occurrences),
        "speeches": int(occurrences["line_id"].str.rsplit("#", n=1).str[0].nunique()),
        "minimum_occurrences": MINIMUM_OCCURRENCES,
        "minimum_occurrences_rule": (
            "Occurrences a slice needs before its shares are published. The counts are "
            "written at every denominator; below the minimum the shares are null, on the "
            "rule 11_countries.py withholds a rate. At forty occurrences the widest 95% "
            "interval on a proportion is about sixteen points, which is coarse and says "
            "so; at ten it is thirty-one and the ordering of seventeen frames would be "
            "noise."
        ),
        "precedence_rule": (
            "An occurrence can satisfy several patterns, and the first frame in codebook "
            "order wins. The order runs from citation — the word inside the name of an "
            "instrument or an office, which is not a claim about any event — through the "
            "speaker's footing on the label, the standing atrocity-crimes catalogue, the "
            "modality of the mention, to the bare nominal constructions. `matched` counts "
            "every occurrence a pattern reached before precedence was applied, so the "
            "cost of the ordering is visible rather than assumed."
        ),
        "unframed_rule": (
            "No pattern in the codebook reached the occurrence. Published as a category, "
            "and as a series, because its share is not constant: it runs at about a third "
            "in the early 1990s and a tenth in the late 2010s, so a frame that gained "
            "share over time may have gained it from the residue rather than from another "
            "frame."
        ),
        "denominator_rule": (
            "Everything here divides by occurrences of the node, not by speeches or by "
            "tokens. A frame's share says what the word was doing when it was said; it "
            "says nothing about how often it was said, and the two move independently."
        ),
        "codebook": node_frames.codebook_rows(),
        "totals": {
            "frames": node_frames.share_block(
                counts, len(occurrences), MINIMUM_OCCURRENCES, matched=matched
            ),
            "frames_per_occurrence": [
                {"matched": int(number), "occurrences": int(count)}
                for number, count in sorted(Counter(occurrences["n_matched"]).items())
            ],
        },
        "morphology": {
            "categories": [
                {
                    "category": category,
                    "occurrences": int((occurrences["form"] == category).sum()),
                }
                for category in node_frames.FORMS
            ],
            "forms": [
                {
                    "form": form,
                    "occurrences": int(count),
                    "category": node_frames.morphology(form),
                }
                for form, count in forms.most_common()
            ],
        },
        "by_year": annual,
        "slices": slices,
        "change": change,
        "triangulation": model,
    }
    meta = artifacts.provenance(
        ROOT,
        "17_frames.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[LEXICON],
        extra={
            "lexicon_version": lex.version,
            "term": TERM,
            "window": width,
            "frames": len(node_frames.CODEBOOK),
            "seed": seed,
            "trials": trials,
        },
    )

    with artifacts.atomic_directory(FRAMES) as staged:
        artifacts.atomic_write_json(staged / "frames.json", {"meta": meta, **payload})
        artifacts.atomic_write_json(
            staged / "occurrences.json",
            {
                "meta": meta,
                "term": TERM,
                "id_format": (
                    "<speech filename without .txt>#<one-based occurrence ordinal>, "
                    "as 08_kwic.py writes it"
                ),
                "occurrences": [
                    {
                        "id": row.line_id,
                        "occurrence_id": row.occurrence_id,
                        "frame": row.frame,
                        "matched": [label for label in row.matched.split("|") if label],
                        "form": row.form,
                    }
                    for row in occurrences.itertuples()
                ],
            },
        )
    for name in ("frames.json", "occurrences.json"):
        console.info(f"wrote {rel(FRAMES / name)}  ({(FRAMES / name).stat().st_size / 1e3:,.0f} kB)")

    note = write_note("17_frames.md", build_note(payload, lex.version))
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--width", type=int, default=node_frames.WIDTH, help="context characters either side"
    )
    parser.add_argument(
        "--trials", type=int, default=2_000, help="meeting permutations per change-point test"
    )
    parser.add_argument("--seed", type=int, default=20_260_902, help="permutation seed")
    parser.add_argument(
        "--alpha", type=float, default=0.05, help="family-wise level before Bonferroni"
    )
    parser.add_argument(
        "--no-model",
        action="store_true",
        help="skip the triangulation; the artefact's model block is written empty",
    )
    args = parser.parse_args()
    run(args.width, args.trials, args.seed, args.alpha, not args.no_model)


if __name__ == "__main__":
    main()
