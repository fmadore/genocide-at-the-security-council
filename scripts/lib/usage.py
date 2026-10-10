"""What a committed model run says about how the Council uses one word.

`14_llm_annotate.py` writes one label set per occurrence and never aggregates
them; `15_usage.py` reads a run, joins it to the corpus and writes the two
artefacts the usage view is drawn from. Everything between those two sentences —
the counting, the withholding, the agreement arithmetic — lives in `lib`, in plain
numpy and pandas, so that it can be tested on constructed rows by a machine with
no corpus, no run and no key. That is the same division `lib.llm` makes against
the model server, and for the same reason: a run needs a GPU and cannot be repeated by CI
to find out whether the aggregation was right.

This module holds the counting. The agreement statistics are in
`lib.agreement`, the gold sample's reference labels and estimates in
`lib.gold_estimates`, and the reading of a second run against the published one
in `lib.usage_comparison`; each states the decision that governs it. Two
decisions are made here rather than in the step, because they are what the
published counts mean:

**Eligible, then assigned.** A row is *eligible* when the model called the match a
true positive **and** its evidence quotation was located around the match
(`evidence_valid`). Eligibility is the gate on every discourse figure: a label
attached to a quotation nobody could find in the speech is not evidence about the
speech. A row is *assigned* when it is eligible **and** carries a referent that
names something — anything except `unclear` and `not_applicable`. `other` counts
as assigned: the model has said the passage has an identifiable referent that the
controlled list does not yet hold, and dropping it would understate how much of
the corpus is about something.

**A count is a fact and a share is an estimate.** Below
:data:`MINIMUM_OCCURRENCES` a speaker's `share_rejects` is written as null rather
than as a small number, exactly as `11_countries.py` withholds a rate below its
own minimum. The counts are always written. The argument for the threshold is in
`notes/11_countries.md`; the number differs because the denominator does.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

import pandas as pd

from . import series

# Every name imported with a redundant `as` is a re-export, kept importable from
# this module for the callers and tests that still reach it here; new code
# imports it from where it is defined. The `as` marks it as deliberate rather
# than as an unused import.
from .agreement import CLASS_SUPPORT_FLOOR as CLASS_SUPPORT_FLOOR
from .agreement import FIELD_CATEGORIES as FIELD_CATEGORIES
from .agreement import KAPPA_MINORITY_FLOOR as KAPPA_MINORITY_FLOOR
from .agreement import SINGLE_LABEL_FIELDS as SINGLE_LABEL_FIELDS
from .agreement import _round, _text
from .agreement import chance_corrected as chance_corrected
from .agreement import classification as classification
from .agreement import cohens_kappa as cohens_kappa
from .agreement import jaccard as jaccard
from .agreement import krippendorff_alpha_masi as krippendorff_alpha_masi
from .agreement import masi_distance as masi_distance
from .agreement import minority_share as minority_share
from .agreement import observed_agreement as observed_agreement
from .agreement import pabak as pabak
from .agreement import per_class as per_class
from .agreement import per_label_kappa as per_label_kappa
from .gold_estimates import ABSTENTIONS as ABSTENTIONS
from .gold_estimates import ADJUDICATOR as ADJUDICATOR
from .gold_estimates import CODERS as CODERS
from .gold_estimates import CORRECTED_FIELDS as CORRECTED_FIELDS
from .gold_estimates import MINIMUM_GOLD as MINIMUM_GOLD
from .gold_estimates import corrected_shares as corrected_shares
from .gold_estimates import frame_rows as frame_rows
from .gold_estimates import function_jaccard as function_jaccard
from .gold_estimates import gold_block as gold_block
from .gold_estimates import human_agreement as human_agreement
from .gold_estimates import human_function_agreement as human_function_agreement
from .gold_estimates import model_vs_human as model_vs_human
from .gold_estimates import nonempty as nonempty
from .gold_estimates import reference_coverage as reference_coverage
from .gold_estimates import reference_labels as reference_labels
from .gold_estimates import weighted_accuracy as weighted_accuracy
from .usage_comparison import COMPARED_FIELDS as COMPARED_FIELDS
from .usage_comparison import MULTI_LABEL_FIELD as MULTI_LABEL_FIELD
from .usage_comparison import comparison_block as comparison_block
from .usage_comparison import comparison_fields as comparison_fields
from .usage_comparison import comparison_function_alpha as comparison_function_alpha
from .usage_comparison import comparison_function_jaccard as comparison_function_jaccard
from .usage_comparison import comparison_function_labels as comparison_function_labels
from .usage_comparison import comparison_overlap as comparison_overlap
from .usage_comparison import comparison_referents as comparison_referents
from .usage_comparison import contested_rows as contested_rows
from .usage_refusals import row_problems as row_problems

#: Annotated occurrences a speaker needs before a *share* of them is published.
#:
#: Twenty, not the hundred `lib.actors.MIN_SPEECHES` uses, because the two guard
#: different denominators. There the denominator is a speaker's whole output and
#: the quantity is the rate at which a rare word appears in it, so the threshold
#: is set where an observed zero starts to mean "quieter than the Council"
#: (notes/11_countries.md derives it from the 3.1% corpus prevalence). Here the
#: denominator is already the speaker's genocide-bearing occurrences and the
#: quantity is a composition of them, so nothing is being detected against a rare
#: base rate: the question is only whether the proportion is steady enough to
#: rank. At n = 20 the widest 95% interval on a proportion is about ±22 points,
#: which is coarse and honestly so; at n = 10 it is ±31 and the ordering would be
#: noise. The counts are published at every denominator either way.
MINIMUM_OCCURRENCES: Final = 20

#: The false discovery rate the rejection flag is held to.
#:
#: `separated` says a speaker rejects the characterisation more often than the
#: rest of the Council does. Each speaker with enough eligible occurrences is
#: tested once — one-sided and exact, against the share of every *other*
#: speaker's eligible occurrences that reject — and the ninety-odd tests are
#: read together under Benjamini-Hochberg at this level, so that among the
#: flagged speakers about one in twenty is expected to be a draw from the same
#: urn rather than one in twenty of all of them. Until 24 September 2026 the
#: reference was a constant, 1.74%, measured on the retired corpus's runs; the
#: published run's own rate is 2.7%, and four speakers were flagged only
#: because the constant was stale (docs/ROADMAP.md, RV1).
FDR_LEVEL: Final = 0.05

#: The codebook's position vocabulary, in the codebook's order rather than
#: sorted. Every position block writes all seven, zero-filled: an absent key
#: would make
#: "this speaker never denied anything" indistinguishable from "this speaker's
#: denials were not counted", and no consumer can tell those apart from JSON.
POSITIONS: Final[tuple[str, ...]] = (
    "asserts",
    "reports_without_position",
    "rejects",
    "conditional",
    "no_position",
    "unclear",
    "not_applicable",
)

#: Referent identifiers that name nothing. `other` is deliberately not here.
UNASSIGNED: Final[frozenset[str]] = frozenset({"unclear", "not_applicable"})

#: The three dated firsts :func:`diffusion_rows` records for a delegation and a
#: referent, in the order the curves are read in: that it used the word about the
#: case at all, that it asserted the characterisation, that it refused it. Two of
#: the three are positions and one is not, which is the point — a delegation can
#: reach a case long before it takes a position on it.
MILESTONES: Final[tuple[str, ...]] = ("mention", "asserts", "rejects")

#: Columns a joined model row must carry to be aggregated here.
REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "occurrence_id",
    "country_org",
    "verdict",
    "concrete_case",
    "speaker_position",
    "referent",
    "evidence_valid",
)


# --- Small conversions -------------------------------------------------------


def _date(value: object) -> str:
    """A cell as an ISO calendar date, or blank.

    Both spellings reach here. The normalised corpus holds `date` as a
    datetime64, so a joined row carries a `pd.Timestamp`; a frame written by hand
    in a test carries the string the artefact will publish. A timestamp is
    formatted rather than stringified because `str()` on one appends a midnight
    nobody observed, and this value is written into the artefact verbatim and
    compared against others as a string.
    """
    text = _text(value)
    if not text:
        return ""
    return f"{value:%Y-%m-%d}" if isinstance(value, datetime) else text


def _modal(values: Iterable[object]) -> str:
    """The most frequent value, ties broken lexically.

    Lexical rather than by first appearance: the tie-break has to be a property
    of the values and not of the row order, or the same run read from a
    differently sorted frame would publish a different group for a speaker that
    briefed from a seat as often as from outside one.
    """
    counts: dict[str, int] = {}
    for value in values:
        label = _text(value)
        if label:
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    top = max(counts.values())
    return sorted(label for label, count in counts.items() if count == top)[0]


def _first(values: Iterable[object]) -> str | None:
    """The first nonblank value, or None. A blank code is missing, not a value.

    `lib.actors._text` makes the same argument about ISO 3166: an empty string
    is falsy enough to pass a truthiness check and truthy enough to survive a
    join, and it puts a speaker with no code onto whatever the empty key matches.
    """
    for value in values:
        if text := _text(value):
            return text
    return None


# --- The two definitions everything else is counted over ---------------------


def eligible_mask(rows: pd.DataFrame) -> pd.Series:
    """Rows whose discourse labels may be counted at all.

    Eligible = verdict `true_positive` **and** `evidence_valid`. Both halves
    matter: a false positive carries no discourse labels by the codebook's
    cascade, and a row whose evidence quotation could not be located in the
    speech is a label with nothing behind it.
    """
    if rows.empty:
        return pd.Series(dtype=bool, index=rows.index)
    verdict = rows["verdict"].map(_text) == "true_positive"
    valid = rows["evidence_valid"].map(bool)
    return verdict & valid


def assigned_mask(rows: pd.DataFrame) -> pd.Series:
    """Eligible rows that name a referent.

    `other` counts as assigned — the model has said the passage is about
    something the controlled list does not hold yet — while `unclear` and
    `not_applicable` do not.
    """
    if rows.empty:
        return pd.Series(dtype=bool, index=rows.index)
    named = ~rows["referent"].map(_text).isin(UNASSIGNED)
    return eligible_mask(rows) & named


def position_counts(rows: pd.DataFrame) -> dict[str, int]:
    """All seven position keys, zero-filled, over whatever rows are handed in."""
    counts = dict.fromkeys(POSITIONS, 0)
    if rows.empty:
        return counts
    for label, count in rows["speaker_position"].map(_text).value_counts().items():
        if label in counts:
            counts[label] = int(count)
    return counts


def funnel(rows: pd.DataFrame) -> dict[str, int]:
    """The counts the note reports as a funnel, from annotated down to assigned."""
    if rows.empty:
        return dict.fromkeys(
            (
                "annotated",
                "true_positive",
                "false_positive",
                "uncertain",
                "evidence_invalid",
                "eligible",
                "referent_unclear",
                "referent_other",
                "assigned",
                "position_unclear",
            ),
            0,
        )
    verdict = rows["verdict"].map(_text)
    referent = rows["referent"].map(_text)
    eligible = eligible_mask(rows)
    return {
        "annotated": len(rows),
        "true_positive": int((verdict == "true_positive").sum()),
        "false_positive": int((verdict == "false_positive").sum()),
        "uncertain": int((verdict == "uncertain").sum()),
        "evidence_invalid": int((~rows["evidence_valid"].map(bool)).sum()),
        "eligible": int(eligible.sum()),
        "referent_unclear": int((referent == "unclear").sum()),
        "referent_other": int((referent == "other").sum()),
        "assigned": int(assigned_mask(rows).sum()),
        "position_unclear": int((rows["speaker_position"].map(_text) == "unclear").sum()),
    }


# --- What produced the labels ------------------------------------------------


def model_block(
    manifest: dict[str, Any],
    run_id: str,
    prompt_digest: str,
    rows: pd.DataFrame,
    total: int,
) -> dict[str, object]:
    """What produced these labels, and how much of the run is countable.

    Counts that describe the artefact — how many occurrences carry a row, how
    many abstained, how much evidence could not be located — are measured from
    the rows rather than copied from the manifest, so they cannot drift from
    what is actually published here. Counts that describe the *effort* — requests
    made, tokens spent, speeches that failed to parse — only the run knows, and
    they are read from its manifest.
    """
    stamp = str(manifest.get("completed") or manifest.get("created") or "")
    usage_record, requests_record = manifest.get("usage"), manifest.get("requests")
    tokens = usage_record if isinstance(usage_record, dict) else {}
    requests = requests_record if isinstance(requests_record, dict) else {}
    verdict = rows["verdict"].astype(str)
    runtime = manifest.get("runtime")
    if runtime is not None:
        if not isinstance(runtime, dict):
            raise ValueError("Run manifest runtime must be an object.")
        if not str(runtime.get("model_revision", "")).strip():
            raise ValueError("Self-hosted run manifest has no model_revision.")
    block = {
        "id": str(manifest.get("model", "")),
        "run_id": run_id or str(manifest.get("run_id", "")),
        "run_date": stamp[:10],
        # A string, because it is an identifier rather than a quantity: nothing
        # here adds prompt versions up or compares them as numbers.
        "prompt_version": str(manifest.get("prompt_version", "")),
        # Missing means v1: the first two committed runs predate the explicit
        # field but carry the v1 list digest and identifiers.
        "referents_version": str(manifest.get("referents_version", "") or "1"),
        "prompt_sha256": prompt_digest,
        "reasoning_effort": str(manifest.get("reasoning_effort", "")),
        # `sent`, and `submitted` only where a manifest predates the recount.
        # The old key counted intentions — the Gemini run recorded 7,966 over a
        # corpus of 3,273 — and the view prints this figure as "Requests", so
        # reading the old key first would publish the number the review found.
        # `tools/recount_run.py` writes `sent`; a run whose raw record is gone
        # keeps `submitted`, and `docs/VALIDATION.md` §7 says which are which.
        "requests": int(requests.get("sent", requests.get("submitted", 0)) or 0),
        "requests_recounted": "sent" in requests,
        "occurrences_total": int(total),
        "occurrences_annotated": len(rows),
        "parse_failures": int(manifest.get("parse_failures", 0) or 0),
        "evidence_invalid": int((~rows["evidence_valid"].map(bool)).sum()),
        "abstention": {
            "verdict_uncertain": int((verdict == "uncertain").sum()),
            "referent_unclear": int((rows["referent"].astype(str) == "unclear").sum()),
            "position_unclear": int((rows["speaker_position"].astype(str) == "unclear").sum()),
        },
        "tokens": {
            "input": int(tokens.get("input_tokens", 0) or 0),
            "output": int(tokens.get("output_tokens", 0) or 0),
        },
    }
    if runtime is not None:
        block["runtime"] = runtime
        block["truncation_count"] = int(manifest.get("truncation_count", 0) or 0)
    return block


# --- The actor, referent and matrix blocks -----------------------------------


def actor_rows(rows: pd.DataFrame, minimum: int = MINIMUM_OCCURRENCES) -> list[dict[str, object]]:
    """One row per speaker, sorted by assigned occurrences then by name.

    `group` is the speaker's modal `speaker_group` across its own
    genocide-bearing rows and not a label on the speaker: `lib.council` is
    explicit that P5/E10/non-member is a property of a *speech*, and Rwanda spoke
    as an elected member in 1994 and as a non-member for most of the corpus. One
    value is published here because the matrix has one row per speaker, and the
    honest reading of it is "most of these occurrences were spoken from here".

    `sufficient` on this block governs whether a share may be *displayed* beside
    the speaker in the matrix: it is assigned >= minimum, the denominator the
    matrix cells are cut from.
    """
    if missing := sorted(set(REQUIRED_COLUMNS) - set(rows.columns)):
        raise KeyError(f"actor_rows() needs columns: {', '.join(missing)}")

    eligible = eligible_mask(rows)
    assigned = assigned_mask(rows)
    out: list[dict[str, Any]] = []
    for name, group in rows.groupby(rows["country_org"].map(_text), sort=True):
        out.append(
            {
                "country_org": str(name),
                "iso3": _first(group.get("iso3", pd.Series(dtype=object))),
                "group": _modal(group.get("speaker_group", pd.Series(dtype=object))),
                "entity_type": _first(group.get("entity_type", pd.Series(dtype=object))) or "",
                "occurrences": len(group),
                "eligible": int(eligible.loc[group.index].sum()),
                "assigned": int(assigned.loc[group.index].sum()),
                "sufficient": bool(int(assigned.loc[group.index].sum()) >= minimum),
            }
        )
    out.sort(key=lambda row: (-int(row["assigned"]), str(row["country_org"])))
    return out


def referent_rows(
    rows: pd.DataFrame, referents: Sequence[Mapping[str, Any]]
) -> list[dict[str, object]]:
    """The controlled list with each referent's assigned occurrence count.

    Every row of `annotations/lexicon/referents.csv` is written, including the
    ones this run never used and the reserved identifiers. `unclear` and
    `not_applicable` are never assigned by construction and therefore always show
    zero; `other` is, and its count is how much of the corpus is about a case the
    controlled list does not hold yet. A referent absent from the artefact would
    read as "not in the vocabulary" rather than "in the vocabulary and never
    invoked", and those are different findings about a corpus.
    """
    counts = (
        rows.loc[assigned_mask(rows), "referent"].map(_text).value_counts()
        if not rows.empty
        else pd.Series(dtype=int)
    )
    out: list[dict[str, Any]] = [
        {
            "id": _text(referent["id"]),
            "label": _text(referent.get("label")),
            "description": _text(referent.get("description")),
            "kind": _text(referent.get("kind")),
            "iso3": _text(referent.get("iso3")),
            "years": _text(referent.get("years")),
            "since": int(referent.get("since", 1) or 1),
            "retired_in": (
                int(referent["retired_in"])
                if referent.get("retired_in") not in (None, "")
                else None
            ),
            "occurrences": int(counts.get(_text(referent["id"]), 0)),
            # A withdrawn category, kept so an older run's counts have somewhere
            # to land. On a run made after the retirement it is empty, and the
            # view needs the flag to tell that apart from a case no delegation
            # ever raised.
            "retired": bool(referent.get("retired", False)),
            "superseded_by": _text(referent.get("superseded_by")),
        }
        for referent in referents
    ]
    out.sort(key=lambda row: (-int(row["occurrences"]), str(row["id"])))
    return out


def matrix_rows(
    rows: pd.DataFrame,
    actor_order: Sequence[str],
    referent_order: Sequence[str],
    contested: frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    """Sparse actor x referent cells over assigned rows, with a position breakdown.

    Sparse because the product is 200 speakers by 40 referents and all but a few
    hundred cells are empty; a dense grid would be six times the payload and
    would say nothing a missing key does not. The order is the two blocks' own
    order, so a consumer that renders the matrix never has to sort it again and
    cannot sort it differently.
    """
    if rows.empty:
        return []
    actor_rank = {name: position for position, name in enumerate(actor_order)}
    referent_rank = {name: position for position, name in enumerate(referent_order)}
    kept = rows.loc[assigned_mask(rows)]
    cells: list[dict[str, object]] = []
    for (actor, referent), group in kept.groupby(
        [kept["country_org"].map(_text), kept["referent"].map(_text)], sort=False
    ):
        disputed = (
            int(group["occurrence_id"].map(_text).isin(contested).sum()) if contested else 0
        )
        cells.append(
            {
                "actor": str(actor),
                "referent": str(referent),
                "count": len(group),
                "contested": disputed,
                "positions": position_counts(group),
            }
        )
    cells.sort(
        key=lambda cell: (
            actor_rank.get(str(cell["actor"]), len(actor_rank)),
            referent_rank.get(str(cell["referent"]), len(referent_rank)),
        )
    )
    return cells


def position_rows(
    rows: pd.DataFrame,
    actor_order: Sequence[str],
    minimum: int = MINIMUM_OCCURRENCES,
) -> list[dict[str, object]]:
    """Per speaker: the position composition of its eligible occurrences.

    Cut from *eligible* rather than from assigned rows, because a speaker can
    reject the characterisation without the passage naming a case clearly enough
    to be assigned one, and dropping those would make the denial figure quietly
    smaller than the corpus supports.

    `share_rejects` is withheld — written as null — below `minimum`, while the
    seven counts are written at every denominator. `sufficient` here is
    therefore eligible >= minimum, which is not the same flag as the one on the
    actor block: they guard different denominators and can disagree.

    A published share carries its 95% Wilson interval, for reading, and the
    result of a test, for ranking: `base_rejects` is the share of every *other*
    speaker's eligible occurrences that reject, `p_value` the exact one-sided
    binomial probability of this many rejections or more at that rate, and
    `q_value` its Benjamini-Hochberg adjustment over every speaker with a
    published share. `separated` is `q_value <= FDR_LEVEL`, and it is the flag a
    consumer must rank on: a share of 1 in 24 looks like more than the room, and
    it is a draw the room would produce often.
    """
    if rows.empty:
        return []
    eligible = eligible_mask(rows)
    kept = rows.loc[eligible]
    grouped = {str(name): group for name, group in kept.groupby(kept["country_org"].map(_text))}
    everything = position_counts(kept)
    all_rejects, all_eligible = int(everything["rejects"]), int(sum(everything.values()))
    out: list[dict[str, Any]] = []
    for actor in actor_order:
        group = grouped.get(actor)
        counts = position_counts(group) if group is not None else dict.fromkeys(POSITIONS, 0)
        total = int(sum(counts.values()))
        enough = total >= minimum
        rejects = int(counts["rejects"])
        interval = share_interval(rejects, total) if enough and total else (None, None)
        others = all_eligible - total
        base = (all_rejects - rejects) / others if others else None
        p_value = (
            binomial_upper_tail(rejects, total, base)
            if enough and total and base is not None
            else None
        )
        out.append(
            {
                "actor": actor,
                "eligible": total,
                "sufficient": bool(enough),
                "positions": counts,
                "share_rejects": (
                    _round(rejects / total) if enough and total else None
                ),
                "share_low": interval[0],
                "share_high": interval[1],
                "base_rejects": _round(base) if enough and base is not None else None,
                "p_value": _round(p_value, 8) if p_value is not None else None,
            }
        )
    tested = [row for row in out if row["p_value"] is not None]
    adjusted = benjamini_hochberg([float(row["p_value"]) for row in tested])
    for row, q_value in zip(tested, adjusted, strict=True):
        row["q_value"] = _round(q_value, 8)
    for row in out:
        row.setdefault("q_value", None)
        row["separated"] = bool(row["q_value"] is not None and row["q_value"] <= FDR_LEVEL)
    return out


def binomial_upper_tail(successes: int, trials: int, rate: float) -> float:
    """P(X >= successes) for X ~ Binomial(trials, rate), exactly.

    Summed in log space from the observed count upwards, so a speaker with a
    few hundred eligible occurrences costs a few hundred terms and no
    dependency. The degenerate rates are answered directly: at a rate of zero
    any rejection is impossible, at one every trial rejects.
    """
    if successes <= 0:
        return 1.0
    if successes > trials:
        return 0.0
    if rate <= 0:
        return 0.0
    if rate >= 1:
        return 1.0
    log_rate, log_rest = math.log(rate), math.log1p(-rate)
    terms = [
        math.lgamma(trials + 1)
        - math.lgamma(k + 1)
        - math.lgamma(trials - k + 1)
        + k * log_rate
        + (trials - k) * log_rest
        for k in range(successes, trials + 1)
    ]
    peak = max(terms)
    return min(1.0, math.exp(peak) * sum(math.exp(term - peak) for term in terms))


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values, in the order given.

    The q-value of the i-th smallest of m p-values is the smallest
    `p_(j) * m / j` over j >= i, capped at one: the false discovery rate at
    which that test would first be called.
    """
    m = len(p_values)
    if not m:
        return []
    order = sorted(range(m), key=lambda index: p_values[index])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        index = order[rank - 1]
        running = min(running, p_values[index] * m / rank)
        adjusted[index] = min(running, 1.0)
    return adjusted


def share_interval(successes: int, total: int) -> tuple[float | None, float | None]:
    """The 95% Wilson interval on a share, as two plain floats or two Nones.

    `lib.series.wilson_interval` is the one implementation of this arithmetic on
    the site, written for the chronology's rates; it is imported rather than
    rewritten so a share on `/usage` and a rate on `/chronology` cannot come to
    bracket themselves differently. It answers elementwise over arrays, so the
    scalars are unwrapped here and a zero denominator — where it returns NaN on
    both sides, no interval being the honest answer for a share of nothing —
    comes back as a pair of Nones.
    """
    if total <= 0:
        return None, None
    low, high = series.wilson_interval(successes, total)
    return _round(float(low)), _round(float(high))


def diffusion_rows(
    rows: pd.DataFrame, referent_order: Sequence[str]
) -> list[dict[str, object]]:
    """When each delegation first invoked each referent, and in which direction.

    An **event** is a dated first. Per (referent, speaker) pair there are up to
    three of them, one per :data:`MILESTONES` entry: `mention` is that speaker's
    first assigned occurrence of the referent whatever position it carried,
    `asserts` its first occurrence positioned `asserts`, `rejects` its
    first positioned `rejects`. One occurrence legitimately produces two
    events — a delegation's first word about a case was also, often, its first
    assertion of it — and both are written rather than collapsed, because the
    curves drawn from them are counted separately and a reader comparing "spoke
    of it" against "asserted it" needs the two to be commensurable.

    **First** is the minimum by `(date, line_id)`, both compared as strings. The
    dates are ISO calendar dates, so lexical order is chronological order, and
    the KWIC line id breaks a same-day tie by a property of the occurrence rather
    than by the order the frame happens to arrive in. Cut from *assigned* rows,
    as the matrix is: a passage naming no case cannot be a first mention of one.
    `other` is assigned and therefore carries events, and is a bucket rather than
    a case; whoever renders it should say so.

    **Absence is not refusal.** Only delegations that spoke can appear, and this
    corpus records the Security Council alone: membership rotates, most states
    are heard only when a debate is opened to non-members, and a state missing
    from a curve is very often a state that had no floor to take. A curve counts
    speakers in this corpus and says nothing about the ones outside it.

    Raises `ValueError` on an assigned row with no date. A first event is a dated
    event, and there is no date to fall back on that would not be invented.
    """
    if missing := sorted((set(REQUIRED_COLUMNS) | {"date", "line_id"}) - set(rows.columns)):
        raise KeyError(f"diffusion_rows() needs columns: {', '.join(missing)}")
    if rows.empty:
        return []

    kept = rows.loc[assigned_mask(rows)]
    if kept.empty:
        return []
    if undated := sorted(
        _text(row["line_id"])
        for row in kept.to_dict(orient="records")
        if not _date(row["date"])
    ):
        raise ValueError(
            "a diffusion event is a dated event, and these assigned rows carry no date: "
            + ", ".join(undated[:8])
            + (f", and {len(undated) - 8} more" if len(undated) > 8 else "")
        )

    # Ordered once, then read through: the first row of the sorted stream that
    # matches a (referent, actor, milestone) key *is* that milestone's first.
    ordered = sorted(
        (
            _date(row["date"]),
            _text(row["line_id"]),
            _text(row["referent"]),
            _text(row["country_org"]),
            _text(row["speaker_position"]),
        )
        for row in kept.to_dict(orient="records")
    )
    events: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for date, line_id, referent, actor, speaker_position in ordered:
        for milestone in MILESTONES:
            if milestone != "mention" and speaker_position != milestone:
                continue
            if (referent, actor, milestone) in seen:
                continue
            seen.add((referent, actor, milestone))
            events.setdefault(referent, []).append(
                {
                    "date": date,
                    "actor": actor,
                    "milestone": milestone,
                    "speaker_position": speaker_position,
                    "id": line_id,
                }
            )

    milestone_rank = {name: position for position, name in enumerate(MILESTONES)}
    referent_rank = {name: position for position, name in enumerate(referent_order)}
    out: list[dict[str, object]] = []
    for referent in sorted(
        events, key=lambda name: (referent_rank.get(name, len(referent_rank)), name)
    ):
        entries = events[referent]
        entries.sort(
            key=lambda event: (
                str(event["date"]),
                str(event["id"]),
                milestone_rank[str(event["milestone"])],
            )
        )
        out.append({"id": referent, "events": entries})
    return out


def exposure_rows(
    rows: pd.DataFrame, speeches: pd.DataFrame
) -> dict[str, list[dict[str, str]]]:
    """Per referent, when each delegation first sat in a debate that named it.

    A diffusion curve counts first mentions, and its height means nothing
    without the number of delegations that could have mentioned the case: a
    state never invited to a Council debate on Darfur did not decline to say
    *genocide* about it. This is that risk set. A delegation is exposed to a
    referent from the first meeting in which any assigned occurrence names it
    and the delegation also spoke, whatever it said (docs/ROADMAP.md, RV20).

    `speeches` is the whole corpus's `filename`, `meeting_symbol`,
    `country_org` and `date`; `rows` the joined model rows.
    """
    kept = rows.loc[assigned_mask(rows)] if not rows.empty else rows
    if kept.empty:
        return {}
    meeting_of = dict(zip(speeches["filename"], speeches["meeting_symbol"], strict=True))
    named = (
        kept.assign(_meeting=kept["filename"].map(meeting_of))
        .groupby(kept["referent"].map(_text))["_meeting"]
        .agg(lambda values: set(values.dropna()))
    )
    floor = speeches[["meeting_symbol", "country_org", "date"]]
    out: dict[str, list[dict[str, str]]] = {}
    for referent, meetings in named.items():
        present = floor.loc[floor["meeting_symbol"].isin(meetings)]
        first = present.groupby(present["country_org"].map(_text))["date"].min()
        out[str(referent)] = [
            {"actor": actor, "date": _date(date)}
            for actor, date in sorted(first.items(), key=lambda item: (_date(item[1]), item[0]))
            if actor
        ]
    return out


def aggregate(
    rows: pd.DataFrame,
    referents: Sequence[Mapping[str, object]],
    minimum: int = MINIMUM_OCCURRENCES,
    contested: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """The four data blocks of `usage.json`, in one pass over one frame.

    `contested` is the identities a second instrument read differently, and it
    reaches the matrix so that each cell can say how much of itself is disputed.
    Empty where no comparison run was made, which writes a zero on every cell —
    the same reading the `comparison` block's own `state` gives at the top of
    the artefact, and one a consumer must not read as agreement.
    """
    actors = actor_rows(rows, minimum)
    referent_block = referent_rows(rows, referents)
    actor_order = [str(actor["country_org"]) for actor in actors]
    referent_order = [str(referent["id"]) for referent in referent_block]
    return {
        "referents": referent_block,
        "actors": actors,
        "matrix": matrix_rows(rows, actor_order, referent_order, contested),
        "position_by_actor": position_rows(rows, actor_order, minimum),
    }
