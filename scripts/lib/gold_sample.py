"""The gold sample's design: cues, strata, the three frames and the coder's packet.

`13_gold_sample.py` reads the corpus and the committed runs and writes the
sample. Everything it decides on the way — which cue a window carries, which
stratum the model's labels put an occurrence in, what each frame draws and at
what inclusion probability, what the blinded packet may show a coder — lives
here, so it can be tested on constructed candidates by a machine with no corpus
and no run. The argument for the design — three frames reported separately, and
a model label that is a sampling stratum and never an answer — is made in that
step's docstring and is not repeated here.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from typing import Final

import pandas as pd

from . import lexicon, llm, model_runs, occurrences, sampling, schema, text

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
                "schema_version": schema.SCHEMA_VERSION,
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

#: The name of the second frame, beside `sampling.PROBABILITY` and
#: `sampling.COVERAGE`. Not added to `lib.sampling`: the two there are general
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
        sampling.probability_sample(candidates, probability, seed, sampling.PROBABILITY),
        sampling.coverage_sample(candidates, coverage, seed + 1, strata=("period", "cue")),
    ]
    if "stratum" in candidates and candidates["stratum"].astype(str).str.len().gt(0).any():
        two_runs = frame == DISAGREEMENT
        frames_drawn.append(
            sampling.stratified_sample(
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
    order = unique["occurrence_id"].map(lambda value: sampling._rank(str(value), seed))
    unique = unique.assign(_order=order).sort_values("_order").drop(columns="_order")
    unique.insert(0, "position", range(1, len(unique) + 1))
    blank = [column for column in schema.ANNOTATION_FIELDS if column not in unique]
    for column in blank:
        unique[column] = ""
    unique["schema_version"] = schema.SCHEMA_VERSION
    unique["lexicon_version"] = str(sample["lexicon_version"].iloc[0]) if len(sample) else ""
    return unique.reset_index(drop=True)


def flag_prior_review(frame: pd.DataFrame, reviewed: Collection[str]) -> pd.DataFrame:
    """`frame` with one more column, true where the passage was read before coding.

    `reviewed` is `annotations/genocide/prior_review.csv`'s occurrence ids:
    passages whose model labels were read and discussed before the gold sample
    was coded, so that a coder's reading of them may not be independent of the
    model. They are flagged and not dropped (docs/EVALUATION_PLAN.md §4), and
    every gold figure is reported with and without them.

    The column is set after the draw, so it cannot move one: the sample stays as
    drawn. It is appended last, so every column the candidate and design files
    already carry keeps its place and its bytes. :func:`packet` never carries it,
    for the reason it carries no frame or stratum: it tells a coder something
    about the passage that the passage does not.
    """
    reviewed_ids = {str(identifier) for identifier in reviewed}
    flagged = frame["occurrence_id"].astype(str).isin(reviewed_ids)
    return frame.assign(**{model_runs.PRIOR_REVIEW_FLAG: flagged})


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
    second = sampling.coverage_inclusion(
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
    union = sampling.union_inclusion(first, second, third)
    return pd.DataFrame(
        {
            "occurrence_id": candidates["occurrence_id"],
            "pi_probability": first.round(10),
            "pi_coverage": second.round(10),
            f"pi_{frame}": third.round(10),
            "pi_union": union.round(10),
        }
    )
