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

Usage:
    python scripts/13_gold_sample.py [--probability 120] [--coverage 80] [--seed 21]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, audit, console, frames, lexicon, llm, model_runs, occurrences, text
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
#: What a coder opens. See the module docstring: blinded, deduplicated, shuffled.
GOLD_PACKET = INTERIM / "genocide_gold_packet.csv"
#: The occurrences behind the prompt's worked examples, excluded from every frame.
PROMPT_EXAMPLES = model_runs.STORE / "prompt_examples.csv"
#: Every population occurrence's probability under each frame and under their
#: union, which is what lets 15 weight a coded unit however it was drawn.
GOLD_DESIGN = INTERIM / "genocide_gold_design.csv"
GOLD_PROBABILITY = INTERIM / "genocide_gold_probability.csv"
GOLD_COVERAGE = INTERIM / "genocide_gold_coverage.csv"
GOLD_ANNOTATIONS = model_runs.GOLD_ANNOTATIONS
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


def check_population(
    found: list[occurrences.Occurrence], expected: tuple[int, int] | None = None
) -> list[str]:
    """Reasons the enumeration cannot be the committed one, if any.

    The gold sample is only comparable to the model run if both enumerate this
    same population, so it is asserted rather than reported.
    """
    return model_runs.population_problems(
        (occurrence.filename for occurrence in found), len(found), expected
    )


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


# --- The disagreement-stratified frame ---------------------------------------

#: The committed model runs the second frame is cut from, named the way
#: `15_usage.py` names them: one file holding one run id, or empty.
CURRENT_RUN = model_runs.CURRENT_RUN
COMPARISON_RUN = model_runs.COMPARISON_RUN
RUNS = model_runs.RUNS

GOLD_DISAGREEMENT = INTERIM / "genocide_gold_disagreement.csv"

#: The strata of the second frame, in the precedence a candidate is assigned in,
#: and how many occurrences to draw from each. `None` is a census.
#:
#: The review of 1 September 2026 (§4.4) proposed this design and estimated the
#: strata from the two runs' marginals. Recomputed from the runs as they are,
#: four of the six agree with it to the occurrence — `rejects` 134,
#: `reports_without_position` 789, `conditional` 614, contested on
#: position or referent 1,703 — and two do not. `other` is 410 and not 641: 641 is
#: Luna's 346 plus Gemini's 295, and an occurrence both runs filed under `other`
#: is one occurrence. And the pre-onset stratum holds 42 occurrences in all —
#: Luna's 32 `gaza` rows before 2023, six `nagorno_karabakh` rows before 2020 in
#: each run, two `ukraine_2022` rows before 2022 — so the review's 40 is not a
#: draw from it but very nearly the whole of it, and it is taken whole.
#:
#: Precedence, rarest first, because the strata overlap and an occurrence has to
#: belong to exactly one of them or its inclusion probability is the union of
#: several draws and nothing downstream can reconstruct it. The order is the
#: order of scarcity, so the rare thing is never spent to fill a common
#: stratum: after precedence the six hold 134, 41, 369, 716, 519 and 636.
#:
#: Sizes: everything the runs disagree about most, and a hundred of each of the
#: three large contested strata — at n = 100 a per-class recall is estimable to
#: about ±10 points, which is what the review asks for and is the whole reason
#: the frame exists. Sixty for `other`, where the question is not a rate but
#: *which* referents the controlled list is missing, and a census of the two
#: strata small enough to have one.
DISAGREEMENT_SIZES: dict[str, int | None] = {
    "rejects": None,
    "pre_onset_referent": None,
    "other_referent": 60,
    "reports_without_position": 100,
    "conditional": 100,
    "contested_speaker_position_or_referent": 100,
}

#: The name of the second frame, beside `audit.PROBABILITY` and
#: `audit.COVERAGE`. Not added to `lib.audit`: the two there are general
#: sampling designs the lexicon audit uses too, and this one is a design over
#: two model runs of one term.
DISAGREEMENT: Final = "disagreement"

#: The third frame when only the published run exists: the same strata, read
#: off one run's labels, with nothing contested because nothing disagrees.
#: Smaller than the disagreement frame's, because every row here is a row two
#: coders must read: a hundred of the rarest class puts its precision within
#: about ten points, sixty of the others within about thirteen, and the
#: pre-onset stratum is small enough to take whole.
MODEL_STRATA: Final = "model_strata"
MODEL_STRATA_SIZES: dict[str, int | None] = {
    "rejects": 100,
    "pre_onset_referent": None,
    "other_referent": 40,
    "reports_without_position": 60,
    "conditional": 60,
}
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


def onset_years(referents: Sequence[llm.Referent]) -> dict[str, int]:
    """The first year each referent's `years` column states, where it states one.

    The codebook is explicit that `years` is documentation and not a coding
    constraint — a speaker may invoke a case before the dates the column gives,
    and the column is there so a coder recognises which situation is meant. That
    is exactly why an occurrence *outside* those years is worth a human eye: it
    is either the vocabulary being stretched, which is a finding, or a referent
    assigned from the wrong decade, which is an error. The stratum records the
    question, not an answer to it.
    """
    years: dict[str, int] = {}
    for referent in referents:
        if match := re.match(r"^(\d{4})", referent.years.strip()):
            years[referent.id] = int(match.group(1))
    return years


def classify_stratum(
    row: pd.Series,
    published: dict[str, dict[str, object]],
    comparison: dict[str, dict[str, object]],
    onsets: dict[str, int],
) -> str:
    """Which stratum of the disagreement frame one occurrence belongs to.

    In :data:`DISAGREEMENT_SIZES` order, first match wins, so the strata are
    disjoint and each row carries one inclusion probability. An occurrence
    neither run reached, or that no stratum claims, returns the empty string and
    is outside the frame.
    """
    identifier = str(row["occurrence_id"])
    first, second = published.get(identifier), comparison.get(identifier)
    # One run is enough to stratify on; two are needed only to be contested.
    if first is None or (comparison and second is None):
        return ""
    labelled = [first] if second is None else [first, second]
    positions = {str(item.get("speaker_position", "")) for item in labelled}
    referents = {str(item.get("referent", "")) for item in labelled}
    year = int(str(row["date"])[:4] or 0)

    if "rejects" in positions:
        return "rejects"
    if any(year and onsets.get(referent, 0) > year for referent in referents):
        return "pre_onset_referent"
    if "other" in referents:
        return "other_referent"
    if "reports_without_position" in positions:
        return "reports_without_position"
    if "conditional" in positions:
        return "conditional"
    if len(positions) > 1 or len(referents) > 1:
        return "contested_speaker_position_or_referent"
    return ""


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
    onsets = onset_years(referents)
    strata = candidates.apply(
        lambda row: classify_stratum(row, published, comparison, onsets), axis=1
    )
    return candidates.assign(stratum=strata), published_id, comparison_id


def draw(
    candidates: pd.DataFrame,
    probability: int,
    coverage: int,
    seed: int,
    *,
    sizes: dict[str, int | None] | None = None,
    frame: str = DISAGREEMENT,
) -> pd.DataFrame:
    """The three sampling frames, concatenated as 03 concatenates its three.

    An occurrence drawn by more than one keeps a row per frame: the sampling
    metadata differs, and dropping one would silently change the inclusion
    probability recorded for the other. `candidate_id` is per frame, so the rows
    stay distinguishable, and a coder meets the occurrence once because the
    review file is joined on `occurrence_id`.

    The third frame is the disagreement design of the review's §4.4, and it is
    kept *beside* the first two rather than replacing them. They answer
    different questions and neither answers both: the probability frame is the
    unbiased estimate of how accurate the layer is over the corpus, and it is
    the only thing here that can be, while this one buys per-class recall on the
    classes an equal-probability draw of 200 contains three of. Reported
    together they would be a number that is neither.
    """
    frames_drawn = [
        audit.probability_sample(candidates, probability, seed, audit.PROBABILITY),
        audit.coverage_sample(candidates, coverage, seed + 1, strata=("period", "cue")),
    ]
    if "stratum" in candidates and candidates["stratum"].astype(str).str.len().gt(0).any():
        two_runs = frame == DISAGREEMENT
        frames_drawn.append(
            audit.stratified_sample(
                candidates,
                sizes or (DISAGREEMENT_SIZES if two_runs else MODEL_STRATA_SIZES),
                seed + 2,
                frame,
                strategy=(
                    "disagreement strata over two committed model runs"
                    if two_runs
                    else "label strata over the published model run"
                ),
            )
        )
    return pd.concat(frames_drawn, ignore_index=True)


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


#: What the packet carries of each candidate: where the passage is and what it
#: says. The coding columns of `annotations/genocide/annotations.csv` follow,
#: blank, apart from the two administrative versions that describe the
#: candidate rather than judge it.
PACKET_PASSAGE = [
    "occurrence_id", "line_id", "filename", "meeting_symbol", "date", "country_org",
    "agenda", "start", "end", "source_sha256", "left", "keyword", "right",
]


def packet(sample: pd.DataFrame, seed: int) -> pd.DataFrame:
    """What a coder opens: each sampled occurrence once, shuffled, and blind.

    The order is a seeded hash of the occurrence id, so it mixes the frames and
    is the same on every run. Nothing that says why an occurrence was drawn —
    frame, stratum, cue, probability — is carried, and neither is any label.
    """
    unique = sample.drop_duplicates("occurrence_id")[PACKET_PASSAGE].copy()
    order = unique["occurrence_id"].map(lambda value: audit._rank(str(value), seed))
    unique = unique.assign(_order=order).sort_values("_order").drop(columns="_order")
    unique.insert(0, "position", range(1, len(unique) + 1))
    blank = [column for column in audit.ANNOTATION_FIELDS if column not in unique]
    for column in blank:
        unique[column] = ""
    unique["schema_version"] = audit.SCHEMA_VERSION
    unique["lexicon_version"] = str(sample["lexicon_version"].iloc[0]) if len(sample) else ""
    return unique.reset_index(drop=True)


def design(
    candidates: pd.DataFrame, probability: int, coverage: int, frame: str
) -> pd.DataFrame:
    """Each occurrence's inclusion probability in each frame, and in any of them.

    Until 24 September 2026 the frames were "never pooled": a rate over their
    union, unweighted, estimates nothing. Weighted, it does. Every unit's chance
    of being coded is `1 - prod(1 - p_f)` over the three independent draws, and
    a Horvitz-Thompson or Hajek estimate over *every* coded unit, weighted by
    its inverse, is design-unbiased for the corpus and uses all the coding the
    purposive frames paid for (docs/ROADMAP.md, RV14). The frames are still
    reported one by one beside it.
    """
    population = len(candidates)
    first = pd.Series(min(probability, population) / population, index=candidates.index)
    second = audit.coverage_inclusion(
        candidates, max(coverage, candidates.groupby(["period", "cue"]).ngroups),
        strata=("period", "cue"),
    )
    sizes = DISAGREEMENT_SIZES if frame == DISAGREEMENT else MODEL_STRATA_SIZES
    third = pd.Series(0.0, index=candidates.index)
    if "stratum" in candidates:
        for name, size in sizes.items():
            members = candidates["stratum"].astype(str) == name
            count = int(members.sum())
            if count:
                third[members] = (count if size is None else min(size, count)) / count
    union = audit.union_inclusion(first, second, third)
    return pd.DataFrame(
        {
            "occurrence_id": candidates["occurrence_id"],
            "pi_probability": first.round(10),
            "pi_coverage": second.round(10),
            f"pi_{frame}": third.round(10),
            "pi_union": union.round(10),
        }
    )


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
) -> str:
    population = len(candidates)
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
        console.fail("the enumeration disagrees with config/lexicon.counts.json", problems)
    console.info(
        f"{len(found):,} occurrences in "
        f"{len({occurrence.filename for occurrence in found}):,} speeches"
    )

    console.step("Classifying cues")
    candidates = candidate_rows(speeches, bodies, found, term, lex)
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
    sample = draw(candidates, probability, coverage, seed, frame=third)
    unique = int(sample["occurrence_id"].nunique())
    console.info(
        f"{len(sample)} candidate rows over {unique} distinct occurrences "
        f"(seeds {seed}, {seed + 1} and {seed + 2})"
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
    weights = design(candidates, probability, coverage, third)
    artifacts.atomic_write_text(GOLD_DESIGN, weights.to_csv(index=False, lineterminator="\n"))
    drawn = weights.loc[weights["occurrence_id"].isin(sample["occurrence_id"])]
    console.info(
        f"wrote {rel(GOLD_DESIGN)}: union inclusion probabilities from "
        f"{drawn['pi_union'].min():.4f} to {drawn['pi_union'].max():.4f} over the drawn units"
    )
    coder_packet = packet(sample, seed)
    artifacts.atomic_write_text(
        GOLD_PACKET, coder_packet.to_csv(index=False, lineterminator="\n")
    )
    console.info(f"wrote {rel(GOLD_PACKET)}: {len(coder_packet)} occurrences, blinded")

    console.step("Writing")
    note = write_note(
        "13_gold_sample.md",
        build_note(candidates, sample, probability, coverage, seed, annotated),
    )
    console.info(f"wrote {note.name}")
    manifest = artifacts.provenance(
        ROOT,
        "13_gold_sample.py",
        inputs=[SPEECHES_NORM, CURRENT_RUN, COMPARISON_RUN,
                *(path for name in (published_run, comparison_run) if name
                  for path in model_runs.files(RUNS / name))],
        configs=[LEXICON, GOLD_ANNOTATIONS, REFERENTS, PROMPT_EXAMPLES, MODEL_ANNOTATIONS / TERM / "PROMPT.md",
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
