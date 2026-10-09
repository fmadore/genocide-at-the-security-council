"""Draw the human gold sample the model-assisted usage layer is measured against.

`genocide` is the term that layer is built on, with the population committed
in `config/lexicon.counts.json`. Step 14 annotates all of it with a model, and a
model run is worth exactly as much as the human sample it was scored against.
This step draws that sample — 120 occurrences by equal probability, 80 more
chosen to cover every period and cue stratum, and a third frame cut from the
published run's labels (or from where two runs disagree, once there are two) —
and leaves it for two coders to work through against
`annotations/lexicon/CODEBOOK.md`.

**Three frames, reported separately.** The probability frame is the unbiased
estimate: every occurrence had the same chance, so a rate computed over it and
weighted by its recorded probabilities is a rate about the corpus. The coverage
frame guarantees that every period and every usage cue is seen at all. The
disagreement frame, added after the review of 1 September 2026 (§4.4), is a
deliberate over-sample of what the two runs read differently — all 134
occurrences either called `rejects`, all 41 whose referent predates
the case it names, and a hundred each of the three large contested strata — and
exists because an equal-probability draw of 200 contains about three rejections
and cannot say anything per class. Nothing in it estimates a corpus quantity,
its inclusion probabilities differ by a factor of seven, and pooling it with the
probability frame would give a number that is neither. Every row records the
probability that put it there, so the two can never be pooled by accident.

Three properties it is built for:

- **One enumeration, checked against the published one.** The occurrences come
  from `lib.occurrences`, the module 13, 14 and 15 share, and the run refuses to
  continue unless it reproduces the committed population in
  `config/lexicon.counts.json`. A gold sample drawn from a different population than the
  one the model annotates would measure nothing.
- **Hard cases on purpose.** Most occurrences are plain uses; an
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

The disagreement frame reads `model_annotations/genocide/` — the run named in
`current_run.txt` and the counter-instrument named in `comparison_run.txt` — and
reads nothing else from them. **A model label is a sampling stratum here in
exactly the sense the cue is**: it says this occurrence is worth a coder's time,
never what the coder should write. Where only the published run exists, the
third frame is the *model-stratified* one instead: the same strata read off one
run, so the rare classes are measurable before a second instrument exists
(docs/ROADMAP.md, RV13).

Two further guarantees (RV10, RV11). The coders work from a **blinded packet**,
`genocide_gold_packet.csv`: one row per occurrence in a seeded shuffle, with the
passage and blank coding columns and nothing else — no frame, no cue, no
stratum, no inclusion probability, because a stratum named `rejects` is the
model's answer printed beside the question. The frames stay in the candidate and
review files, which are the key. And the ten occurrences the prompt's worked
examples are cut from (`model_annotations/genocide/prompt_examples.csv`) are
outside every frame: their labels are dictated to the model, so they cannot
test it.

The 59 passages read against the Qwen run's labels on 10 September 2026
(`annotations/genocide/prior_review.csv`) are treated the other way: they stay
in every frame, because the sample stays as drawn, and the ones drawn are
flagged (decided by FM on 9 October 2026, docs/EVALUATION_PLAN.md §4). A
`prior_review` column marks them in the candidate and design files, and never
in the packet; step 15 reports every gold figure with and without them.

Usage:
    python scripts/13_gold_sample.py [--probability 120] [--coverage 80] [--seed 21]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    artifacts,
    audit,
    console,
    frames,
    gold_sample,
    lexicon,
    llm,
    model_runs,
    occurrences,
)
from lib.paths import (
    INTERIM,
    LEXICON,
    MANIFESTS,
    MODEL_ANNOTATIONS,
    ROOT,
    SPEECHES_NORM,
    ensure_dirs,
    rel,
    write_note,
)

TERM = model_runs.TERM

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

#: The sampling design — the cues, the strata and their sizes, the frames, the
#: design and the packet — lives in `lib.gold_sample`, where it is tested on
#: constructed candidates. This step reads the corpus and the runs, draws, and
#: writes the files.
CUES = gold_sample.CUES
DISAGREEMENT = gold_sample.DISAGREEMENT
DISAGREEMENT_SIZES = gold_sample.DISAGREEMENT_SIZES
MODEL_STRATA = gold_sample.MODEL_STRATA
MODEL_STRATA_SIZES = gold_sample.MODEL_STRATA_SIZES

GOLD_CANDIDATES = model_runs.GOLD_CANDIDATES
GOLD_REVIEW = INTERIM / "genocide_gold_review.csv"
#: What a coder opens. See the module docstring: blinded, deduplicated, shuffled.
GOLD_PACKET = model_runs.GOLD_PACKET
#: The occurrences behind the prompt's worked examples, excluded from every frame.
PROMPT_EXAMPLES = model_runs.PROMPT_EXAMPLES
#: The passages read against a model's labels before coding: flagged, never excluded.
PRIOR_REVIEW = model_runs.PRIOR_REVIEW
PRIOR_REVIEW_FLAG = model_runs.PRIOR_REVIEW_FLAG
#: Every population occurrence's probability under each frame and under their
#: union, which is what lets 15 weight a coded unit however it was drawn.
GOLD_DESIGN = model_runs.GOLD_DESIGN
GOLD_PROBABILITY = INTERIM / "genocide_gold_probability.csv"
GOLD_COVERAGE = INTERIM / "genocide_gold_coverage.csv"
GOLD_ANNOTATIONS = model_runs.GOLD_ANNOTATIONS
# The controlled referents are shared with 03's audit: one list of cases and
# entities for the project, not one per sample.
REFERENTS = model_runs.REFERENTS


# --- The disagreement-stratified frame ---------------------------------------

#: The committed model runs the second frame is cut from, named the way
#: `15_usage.py` names them: one file holding one run id, or empty.
CURRENT_RUN = model_runs.CURRENT_RUN
COMPARISON_RUN = model_runs.COMPARISON_RUN
RUNS = model_runs.RUNS

GOLD_DISAGREEMENT = INTERIM / "genocide_gold_disagreement.csv"
GOLD_MODEL_STRATA = INTERIM / "genocide_gold_model_strata.csv"


def read_run(run_id: str) -> dict[str, dict[str, object]]:
    """One committed run's rows, keyed by occurrence, or nothing.

    Read by identity rather than by position, and never merged with anything:
    the runs are read here to *stratify* a sample of occurrences the humans will
    code independently, and a model label is a sampling stratum in exactly the
    sense the cue already is — it says this occurrence is worth a coder's time,
    never what the coder should write.

    Every row is read through `lib.llm.resolve_row`, so a run coded against
    annotation schema 2 and a run coded against 3 are stratified by the same
    vocabulary. The strata are pure renames across that boundary — a
    `rejects` row is a `rejects` row and the same occurrence — so the
    frame sizes recorded in `docs/VALIDATION.md` are unchanged by the move; what
    would change them is reading two schemas as though one of them meant the
    other, which is what this prevents.
    """
    if not run_id:
        return {}
    path = RUNS / run_id / "annotations.jsonl"
    if not path.is_file():
        console.fail(f"Named run {rel(path)} does not exist; clear the pointer or restore the run")
    return {str(row["occurrence_id"]): row for row in model_runs.resolved(path.parent)}


named_run = model_runs.pointer


def stratify(
    candidates: pd.DataFrame, referents: Sequence[llm.Referent]
) -> tuple[pd.DataFrame, str, str]:
    """The candidate frame with a `stratum` column, and the two runs it came from.

    The column is empty everywhere when no run is published, which is the state
    the repository was in before 31 August and the state a fresh clone is in
    after `data/` is rebuilt: the disagreement frame is then empty, the
    probability and coverage frames are unaffected, and the note says as much.
    """
    published_id, comparison_id = named_run(CURRENT_RUN), named_run(COMPARISON_RUN)
    published, comparison = read_run(published_id), read_run(comparison_id)
    population = set(candidates["occurrence_id"].astype(str))
    candidates.attrs["model_overlap"] = {
        "published_rows": len(published), "comparison_rows": len(comparison),
        "published_matched": len(population & published.keys()),
        "comparison_matched": len(population & comparison.keys()),
        "paired_matched": len(population & published.keys() & comparison.keys()),
        "population": len(population),
    }
    if not published:
        return candidates.assign(stratum=""), published_id, comparison_id
    onsets = gold_sample.onset_years(referents)
    strata = candidates.apply(
        lambda row: gold_sample.classify_stratum(row, published, comparison, onsets), axis=1
    )
    return candidates.assign(stratum=strata), published_id, comparison_id


def prompt_example_ids(found: Sequence[occurrences.Occurrence]) -> set[str]:
    """The prompt's worked examples, as occurrence ids of this enumeration.

    Refuses a mapping naming an occurrence the corpus no longer has: the
    exclusion would then silently exclude nothing.
    """
    if not PROMPT_EXAMPLES.is_file():
        console.fail(
            f"{rel(PROMPT_EXAMPLES)} is missing",
            ["run `python tools/map_prompt_examples.py --write` and commit it"],
        )
    listed = set(
        pd.read_csv(PROMPT_EXAMPLES, dtype="string", keep_default_na=False)["occurrence_id"]
    )
    present = {occurrence.occurrence_id for occurrence in found}
    if missing := sorted(listed - present):
        console.fail(
            f"{rel(PROMPT_EXAMPLES)} names occurrences this corpus does not have",
            [*missing[:5], "run `python tools/map_prompt_examples.py --write` and review it"],
        )
    return listed


def prior_review_ids(found: Sequence[occurrences.Occurrence]) -> set[str]:
    """The passages read against a model's labels before coding, as ids of this enumeration.

    Refuses a list naming an occurrence the corpus no longer has, for the reason
    :func:`prompt_example_ids` does: the flag would then silently flag nothing.
    """
    if not PRIOR_REVIEW.is_file():
        console.fail(
            f"{rel(PRIOR_REVIEW)} is missing",
            ["restore it from version control; `tools/prior_review.py` rebuilds it"],
        )
    listed = set(
        pd.read_csv(PRIOR_REVIEW, dtype="string", keep_default_na=False)["occurrence_id"]
    )
    present = {occurrence.occurrence_id for occurrence in found}
    if missing := sorted(listed - present):
        console.fail(
            f"{rel(PRIOR_REVIEW)} names occurrences this corpus does not have",
            [*missing[:5], "run `python tools/prior_review.py` to see which passages moved"],
        )
    return listed


def stratum_rows(candidates: pd.DataFrame, sample: pd.DataFrame) -> list[str]:
    """The disagreement frame's own table: what it holds and at what probability."""
    drawn = sample.loc[sample["sampling_frame"] == DISAGREEMENT]
    if drawn.empty:
        return [
            "No committed run pair, so no disagreement frame. `current_run.txt` and",
            "`comparison_run.txt` name the two runs it is cut from; both must exist.",
        ]
    rows = [
        "| Stratum | In the corpus | Drawn | Inclusion probability |",
        "|---|---:|---:|---:|",
    ]
    for name in DISAGREEMENT_SIZES:
        part = drawn.loc[drawn["stratum"] == name]
        if part.empty:
            rows.append(f"| `{name}` | 0 | 0 | — |")
            continue
        size = int(part["stratum_size"].iloc[0])
        probability = float(part["inclusion_probability"].iloc[0])
        rows.append(f"| `{name}` | {size:,} | {len(part)} | {probability:.3f} |")
    return rows


def build_note(
    candidates: pd.DataFrame,
    sample: pd.DataFrame,
    probability: int,
    coverage: int,
    seed: int,
    annotated: int,
    *,
    reviewed: int = 0,
) -> str:
    population = len(candidates)
    flagged = int(sample.drop_duplicates("occurrence_id")[PRIOR_REVIEW_FLAG].sum())
    frames_seen = {
        name: sample.loc[sample["sampling_frame"] == name]
        for name in (audit.PROBABILITY, audit.COVERAGE, DISAGREEMENT)
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
            "Checked against the population committed in `config/lexicon.counts.json`;",
            "the run fails rather than sampling a population that disagrees with it.",
            "The ten occurrences behind the prompt's worked examples are outside every",
            "frame, and coders work from the blinded `genocide_gold_packet.csv`.",
            "",
            "## The sample",
            "",
            "| Frame | Rows | Size | Seed |",
            "|---|---:|---:|---:|",
            f"| probability | {len(frames_seen[audit.PROBABILITY])} | {probability} | {seed} |",
            f"| coverage | {len(frames_seen[audit.COVERAGE])} | {coverage} | {seed + 1} |",
            f"| disagreement | {len(frames_seen[DISAGREEMENT])} | per stratum, below | "
            f"{seed + 2} |",
            "",
            f"{len(sample)} candidate rows over **{unique} distinct occurrences**: the "
            f"frames overlap by {len(sample) - unique}, and every row is kept because each "
            "records its own inclusion probability.",
            f"The coverage frame is stratified by period and cue, {strata} strata in all, one "
            "occurrence drawn from each before the random fill.",
            "",
            "## The disagreement frame",
            "",
            "Cut from the two committed model runs, over the occurrences both reached. A",
            "model label is a sampling stratum here in exactly the sense the cue is: it says",
            "this occurrence is worth a coder's time, never what the coder should write. The",
            "strata are disjoint and assigned in the order below, rarest first, so every row",
            "carries one inclusion probability.",
            "",
            "**Report it separately from the probability frame.** That one is an unbiased",
            "estimate of accuracy over the corpus and is weighted by its own probabilities;",
            "this one is a deliberate over-sample of the rare and the contested, and the",
            "per-class recall it buys is read unweighted. Pooled they would be neither.",
            "",
            *stratum_rows(candidates, sample),
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
            f"**{flagged}** of the {unique} occurrences are among the {reviewed} passages read",
            "against the Qwen run's labels on 10 September 2026, before coding began",
            f"(`{rel(PRIOR_REVIEW)}`). They stay in the sample as drawn: the `{PRIOR_REVIEW_FLAG}`",
            "column marks them in the candidate and design files and never in the packet, and",
            "step 15 reports every gold figure with and without them.",
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
    if problems := gold_sample.check_population(found):
        console.fail("the enumeration disagrees with config/lexicon.counts.json", problems)
    console.info(
        f"{len(found):,} occurrences in "
        f"{len({occurrence.filename for occurrence in found}):,} speeches"
    )

    console.step("Classifying cues")
    candidates = gold_sample.candidate_rows(speeches, bodies, found, term, lex)
    examples = prompt_example_ids(found)
    candidates = candidates.loc[~candidates["occurrence_id"].isin(examples)].reset_index(
        drop=True
    )
    console.info(
        f"{len(examples)} occurrences behind the prompt's worked examples are outside "
        f"every frame; {len(candidates):,} remain"
    )
    console.table([(cue, f"{int((candidates['cue'] == cue).sum()):,}") for cue in CUES])

    console.step("Reading the committed runs the second frame is cut from")
    candidates, published_run, comparison_run = stratify(
        candidates, llm.read_referent_table(REFERENTS)
    )
    third = DISAGREEMENT if published_run and comparison_run else MODEL_STRATA
    if published_run:
        console.info(
            f"published {published_run}"
            + (f", comparison {comparison_run}" if comparison_run else ", no comparison")
            + f": the third frame is `{third}`"
        )
        sizes = DISAGREEMENT_SIZES if third == DISAGREEMENT else MODEL_STRATA_SIZES
        console.table(
            [(name, f"{int((candidates['stratum'] == name).sum()):,}") for name in sizes]
        )
    else:
        console.warn("no run is published; the third frame will be empty")

    console.step("Drawing the gold sample")
    sample = gold_sample.draw(candidates, probability, coverage, seed, frame=third)
    unique = int(sample["occurrence_id"].nunique())
    console.info(
        f"{len(sample)} candidate rows over {unique} distinct occurrences "
        f"(seeds {seed}, {seed + 1} and {seed + 2})"
    )
    # Read only now, so the list cannot reach the draw: it marks the sample drawn.
    reviewed = prior_review_ids(found)
    sample = gold_sample.flag_prior_review(sample, reviewed)
    flagged = int(sample.drop_duplicates("occurrence_id")[PRIOR_REVIEW_FLAG].sum())
    console.info(
        f"{flagged} of them are among the {len(reviewed)} passages read against a model's "
        f"labels before coding; `{PRIOR_REVIEW_FLAG}` marks them, outside the packet"
    )
    review = audit.write_outputs(
        sample,
        annotation_path=GOLD_ANNOTATIONS,
        candidate_path=GOLD_CANDIDATES,
        review_path=GOLD_REVIEW,
        frame_paths={
            audit.PROBABILITY: GOLD_PROBABILITY,
            audit.COVERAGE: GOLD_COVERAGE,
            DISAGREEMENT: GOLD_DISAGREEMENT,
            MODEL_STRATA: GOLD_MODEL_STRATA,
        },
        referent_path=REFERENTS,
        # A coded row survives a bump that did not touch `genocide`; see
        # `Lexicon.compatible`.
        compatible=lex.compatible,
    )
    coded = review.loc[review["coder"].astype("string").str.len().gt(0)]
    annotated = len(coded.drop_duplicates(["occurrence_id", "coder"]))
    console.info(
        f"wrote {rel(GOLD_CANDIDATES)} and {rel(GOLD_REVIEW)} ({annotated} annotations)"
    )
    weights = gold_sample.flag_prior_review(
        gold_sample.design(candidates, probability, coverage, third), reviewed
    )
    artifacts.atomic_write_text(GOLD_DESIGN, weights.to_csv(index=False, lineterminator="\n"))
    drawn = weights.loc[weights["occurrence_id"].isin(sample["occurrence_id"])]
    console.info(
        f"wrote {rel(GOLD_DESIGN)}: union inclusion probabilities from "
        f"{drawn['pi_union'].min():.4f} to {drawn['pi_union'].max():.4f} over the drawn units"
    )
    coder_packet = gold_sample.packet(sample, seed)
    artifacts.atomic_write_text(
        GOLD_PACKET, coder_packet.to_csv(index=False, lineterminator="\n")
    )
    console.info(f"wrote {rel(GOLD_PACKET)}: {len(coder_packet)} occurrences, blinded")

    console.step("Writing")
    note = write_note(
        "13_gold_sample.md",
        build_note(
            candidates, sample, probability, coverage, seed, annotated, reviewed=len(reviewed)
        ),
    )
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "13_gold_sample.py",
        inputs=[SPEECHES_NORM, CURRENT_RUN, COMPARISON_RUN,
                *(path for name in (published_run, comparison_run) if name
                  for path in model_runs.files(RUNS / name))],
        configs=[LEXICON, GOLD_ANNOTATIONS, REFERENTS, PROMPT_EXAMPLES, PRIOR_REVIEW,
                 MODEL_ANNOTATIONS / TERM / "PROMPT.md",
                 *sorted((MODEL_ANNOTATIONS / TERM / "prompts").glob("*.md"))],
        extra={
            "model_overlap": candidates.attrs.get("model_overlap", {}),
            "outputs": [
                artifacts.describe_file(GOLD_CANDIDATES, ROOT),
                artifacts.describe_file(GOLD_REVIEW, ROOT),
                artifacts.describe_file(GOLD_PROBABILITY, ROOT),
                artifacts.describe_file(GOLD_COVERAGE, ROOT),
                artifacts.describe_file(GOLD_DISAGREEMENT, ROOT),
                artifacts.describe_file(GOLD_MODEL_STRATA, ROOT),
                artifacts.describe_file(GOLD_PACKET, ROOT),
                artifacts.describe_file(GOLD_DESIGN, ROOT),
            ],
            "excluded_prompt_examples": sorted(examples),
            "prior_review": {
                "listed": len(reviewed),
                "in_sample": flagged,
                "flagged": sorted(
                    sample.loc[sample[PRIOR_REVIEW_FLAG], "occurrence_id"].astype(str).unique()
                ),
            },
            "third_frame": third,
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
                "disagreement": {
                    "seed": seed + 2,
                    "published_run": published_run,
                    "comparison_run": comparison_run,
                    "sizes": {
                        name: ("all" if size is None else size)
                        for name, size in DISAGREEMENT_SIZES.items()
                    },
                    "strata": {
                        name: int((candidates["stratum"] == name).sum())
                        for name in DISAGREEMENT_SIZES
                    },
                    "drawn": int((sample["sampling_frame"] == DISAGREEMENT).sum()),
                },
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
