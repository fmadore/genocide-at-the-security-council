"""What a committed model run says about how the Council uses one word.

`14_llm_annotate.py` writes one label set per occurrence and never aggregates
them; `15_usage.py` reads a run, joins it to the corpus and writes the two
artefacts the usage view is drawn from. Everything between those two sentences —
the counting, the withholding, the agreement arithmetic — lives here, in plain
numpy and pandas, so that it can be tested on constructed rows by a machine with
no corpus, no run and no key. That is the same division `lib.llm` makes against
the API, and for the same reason: a run costs money and cannot be repeated by CI
to find out whether the aggregation was right.

Four decisions are made here rather than in the step, because they are what the
published numbers mean:

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

**Agreement is computed, not imported.** Cohen's kappa and the per-class F1 table
are eleven lines of arithmetic each, and writing them out means the formula is in
the repository beside the number it produced instead of inside a dependency that
would have to be installed on the deploy runner to rebuild a research artefact.
Every one of them returns ``None`` rather than a number when the input is
degenerate, because "kappa could not be computed on one category" and "the coders
agreed by chance" are different findings.

**A second opinion is not a second measurement.** A comparison run is a different
model answering the same questionnaire about the same occurrences, and the
functions that read one are counted over the *overlap* — the occurrences both
runs reached — on raw labels with no eligibility filter, because the verdict the
filter is cut from is itself one of the things being compared. Where two models
agree, what has been measured is the stability of a label across instruments; the
human gold sample stays the only calibration in this module.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Final

import numpy as np
import pandas as pd

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

#: The codebook's stance vocabulary, in the codebook's order rather than sorted.
#: Every stance block writes all seven, zero-filled: an absent key would make
#: "this speaker never denied anything" indistinguishable from "this speaker's
#: denials were not counted", and no consumer can tell those apart from JSON.
STANCES: Final[tuple[str, ...]] = (
    "asserts",
    "attributes_or_reports",
    "rejects_or_denies",
    "hypothetical_or_conditional",
    "neutral_legal_reference",
    "unclear",
    "not_applicable",
)

#: Referent identifiers that name nothing. `other` is deliberately not here.
UNASSIGNED: Final[frozenset[str]] = frozenset({"unclear", "not_applicable"})

#: The three dated firsts :func:`diffusion_rows` records for a delegation and a
#: referent, in the order the curves are read in: that it used the word about the
#: case at all, that it asserted the characterisation, that it refused it. Two of
#: the three are stances and one is not, which is the point — a delegation can
#: reach a case long before it takes a position on it.
MILESTONES: Final[tuple[str, ...]] = ("mention", "asserts", "rejects_or_denies")

#: The fields one label per occurrence, and therefore the ones kappa and a
#: confusion table are defined on. `function` is multi-label and is reported as a
#: Jaccard overlap by the note instead; see :func:`jaccard`.
SINGLE_LABEL_FIELDS: Final[tuple[str, ...]] = ("verdict", "quotation", "stance", "referent")

#: Every field a second opinion is compared on, in the order `lib.llm` writes
#: them into a row and :func:`contested_rows` lists them. The four above plus
#: `function`, which is here because a reader looking at a disagreement wants all
#: five labels and not the ones a statistic happens to be defined on.
COMPARED_FIELDS: Final[tuple[str, ...]] = (
    "verdict",
    "quotation",
    "stance",
    "function",
    "referent",
)

#: The one member of :data:`COMPARED_FIELDS` carrying several labels at once, and
#: therefore the one compared as a set rather than as a string.
MULTI_LABEL_FIELD: Final = "function"

#: The value of each single-label field that means "I decline to decide". The
#: abstention rate is a measurement of the run, not a defect in it: the prompt
#: tells the model that an honest abstention beats a guess.
ABSTENTIONS: Final[dict[str, str]] = {
    "verdict": "uncertain",
    "quotation": "unclear",
    "stance": "unclear",
    "referent": "unclear",
}

#: The two coders of `annotations/genocide/annotations.csv`, and the coder name
#: an adjudicated row carries. Initials rather than names, as the file uses.
CODERS: Final[tuple[str, str]] = ("FM", "JG")
ADJUDICATOR: Final = "adjudicated"

#: Columns a joined model row must carry to be aggregated here.
REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "occurrence_id",
    "country_org",
    "verdict",
    "stance",
    "referent",
    "evidence_valid",
)


# --- Small conversions -------------------------------------------------------


def _text(value: object) -> str:
    """A cell as a stripped string. Missing and blank are the same thing here.

    Through `pd.isna` rather than a `None` check, because the parquet spells a
    missing ISO code three ways depending on how the column was read — `None`,
    `float('nan')`, `pd.NA` — and only the first of them is falsy. `str(pd.NA)` is
    the string `"<NA>"`, which would sail through every emptiness test below and
    end up published as a country code.
    """
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass  # an array or a list: not missing, and not something str() ruins
    return str(value).strip()


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


def _round(value: float | None, digits: int = 6) -> float | None:
    """A plain Python float, or None. numpy scalars do not survive json.dumps."""
    return None if value is None else round(float(value), digits)


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


def stance_counts(rows: pd.DataFrame) -> dict[str, int]:
    """All seven stance keys, zero-filled, over whatever rows are handed in."""
    counts = dict.fromkeys(STANCES, 0)
    if rows.empty:
        return counts
    for label, count in rows["stance"].map(_text).value_counts().items():
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
                "stance_unclear",
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
        "stance_unclear": int((rows["stance"].map(_text) == "unclear").sum()),
    }


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
    out: list[dict[str, object]] = []
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
    rows: pd.DataFrame, referents: Sequence[Mapping[str, object]]
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
    out = [
        {
            "id": _text(referent["id"]),
            "label": _text(referent.get("label")),
            "kind": _text(referent.get("kind")),
            "iso3": _text(referent.get("iso3")),
            "years": _text(referent.get("years")),
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
) -> list[dict[str, object]]:
    """Sparse actor x referent cells over assigned rows, with a stance breakdown.

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
        cells.append(
            {
                "actor": str(actor),
                "referent": str(referent),
                "count": len(group),
                "stances": stance_counts(group),
            }
        )
    cells.sort(
        key=lambda cell: (
            actor_rank.get(str(cell["actor"]), len(actor_rank)),
            referent_rank.get(str(cell["referent"]), len(referent_rank)),
        )
    )
    return cells


def stance_rows(
    rows: pd.DataFrame,
    actor_order: Sequence[str],
    minimum: int = MINIMUM_OCCURRENCES,
) -> list[dict[str, object]]:
    """Per speaker: the stance composition of its eligible occurrences.

    Cut from *eligible* rather than from assigned rows, because a speaker can
    reject the characterisation without the passage naming a case clearly enough
    to be assigned one, and dropping those would make the denial figure quietly
    smaller than the corpus supports.

    `share_rejects` is withheld — written as null — below `minimum`, while the
    seven counts are written at every denominator. `sufficient` here is
    therefore eligible >= minimum, which is not the same flag as the one on the
    actor block: they guard different denominators and can disagree.
    """
    if rows.empty:
        return []
    eligible = eligible_mask(rows)
    kept = rows.loc[eligible]
    grouped = {str(name): group for name, group in kept.groupby(kept["country_org"].map(_text))}
    out: list[dict[str, object]] = []
    for actor in actor_order:
        group = grouped.get(actor)
        counts = stance_counts(group) if group is not None else dict.fromkeys(STANCES, 0)
        total = int(sum(counts.values()))
        enough = total >= minimum
        out.append(
            {
                "actor": actor,
                "eligible": total,
                "sufficient": bool(enough),
                "stances": counts,
                "share_rejects": (
                    _round(counts["rejects_or_denies"] / total) if enough and total else None
                ),
            }
        )
    return out


def diffusion_rows(
    rows: pd.DataFrame, referent_order: Sequence[str]
) -> list[dict[str, object]]:
    """When each delegation first invoked each referent, and in which direction.

    An **event** is a dated first. Per (referent, speaker) pair there are up to
    three of them, one per :data:`MILESTONES` entry: `mention` is that speaker's
    first assigned occurrence of the referent whatever stance it carried,
    `asserts` its first occurrence stanced `asserts`, `rejects_or_denies` its
    first stanced `rejects_or_denies`. One occurrence legitimately produces two
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
            _text(row["stance"]),
        )
        for row in kept.to_dict(orient="records")
    )
    events: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for date, line_id, referent, actor, stance in ordered:
        for milestone in MILESTONES:
            if milestone != "mention" and stance != milestone:
                continue
            if (referent, actor, milestone) in seen:
                continue
            seen.add((referent, actor, milestone))
            events.setdefault(referent, []).append(
                {
                    "date": date,
                    "actor": actor,
                    "milestone": milestone,
                    "stance": stance,
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


def aggregate(
    rows: pd.DataFrame,
    referents: Sequence[Mapping[str, object]],
    minimum: int = MINIMUM_OCCURRENCES,
) -> dict[str, object]:
    """The four data blocks of `usage.json`, in one pass over one frame."""
    actors = actor_rows(rows, minimum)
    referent_block = referent_rows(rows, referents)
    actor_order = [str(actor["country_org"]) for actor in actors]
    referent_order = [str(referent["id"]) for referent in referent_block]
    return {
        "referents": referent_block,
        "actors": actors,
        "matrix": matrix_rows(rows, actor_order, referent_order),
        "stance_by_actor": stance_rows(rows, actor_order, minimum),
    }


# --- Agreement ---------------------------------------------------------------


def _pairs(left: Sequence[object], right: Sequence[object]) -> tuple[list[str], list[str]]:
    if len(left) != len(right):
        raise ValueError("Agreement is computed over paired labels of equal length.")
    return [_text(value) for value in left], [_text(value) for value in right]


def observed_agreement(left: Sequence[object], right: Sequence[object]) -> float | None:
    """The share of pairs that carry the same label.

        p_o = (1/n) * sum_i [ a_i == b_i ]

    None on an empty comparison: zero pairs agreeing zero times is not 0%.
    """
    a, b = _pairs(left, right)
    if not a:
        return None
    return _round(sum(x == y for x, y in zip(a, b, strict=True)) / len(a))


def cohens_kappa(left: Sequence[object], right: Sequence[object]) -> float | None:
    """Chance-corrected agreement between two raters over one field.

        p_e    = sum_c ( n_a(c)/n ) * ( n_b(c)/n )
        kappa  = ( p_o - p_e ) / ( 1 - p_e )

    Returns None when the statistic is not defined rather than a number that
    looks like one. That happens whenever `1 - p_e` is zero, which is the
    degenerate case both raters used a single category throughout: they agreed
    completely, chance predicts complete agreement, and there is no room left for
    the correction to measure anything. Reporting 0.0 there would say the two
    coders agreed no better than chance, which is the opposite of what happened.
    """
    a, b = _pairs(left, right)
    if not a:
        return None
    total = len(a)
    labels = set(a) | set(b)
    if len(labels) < 2:
        return None
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / total
    expected = sum((a.count(label) / total) * (b.count(label) / total) for label in labels)
    if math.isclose(expected, 1.0):
        return None
    return _round((observed - expected) / (1 - expected))


def per_class(
    reference: Sequence[object], predicted: Sequence[object]
) -> list[dict[str, object]]:
    """Precision, recall, F1 and support for every label either side used.

        precision_c = tp_c / ( tp_c + fp_c )
        recall_c    = tp_c / ( tp_c + fn_c )
        f1_c        = 2 * precision_c * recall_c / ( precision_c + recall_c )

    Support is counted on the *reference* side, which is what makes a class with
    support 0 legible: the model used a label the humans never did. A zero
    denominator yields 0.0 rather than None, because at this level the quantity
    is defined and empty — nothing of that class was predicted, so nothing of it
    was predicted correctly.
    """
    a, b = _pairs(reference, predicted)
    out: list[dict[str, object]] = []
    for label in sorted(set(a) | set(b)):
        true_positive = sum(x == label and y == label for x, y in zip(a, b, strict=True))
        predicted_total = b.count(label)
        support = a.count(label)
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        )
        out.append(
            {
                "label": label,
                "precision": _round(precision),
                "recall": _round(recall),
                "f1": _round(f1),
                "support": int(support),
            }
        )
    return out


def classification(
    reference: Sequence[object],
    predicted: Sequence[object],
    *,
    abstention: str | None = None,
) -> dict[str, object] | None:
    """Accuracy, macro-F1, the abstention rate, and the per-class table.

        accuracy   = (1/n) * sum_i [ ref_i == pred_i ]
        macro_f1   = mean over classes of f1_c
        abstention = (1/n) * sum_i [ pred_i == the field's abstention label ]

    Macro-F1 is None on a degenerate comparison — one category across both sides
    — where it would be the F1 of the only class and would say nothing about a
    classifier's ability to tell classes apart. None is returned for the whole
    block when there is nothing to compare.
    """
    a, b = _pairs(reference, predicted)
    if not a:
        return None
    classes = per_class(a, b)
    degenerate = len(set(a) | set(b)) < 2
    return {
        "n": len(a),
        "accuracy": _round(sum(x == y for x, y in zip(a, b, strict=True)) / len(a)),
        "macro_f1": (
            None
            if degenerate
            else _round(float(np.mean([float(row["f1"]) for row in classes])))
        ),
        "abstention_rate": _round(
            (b.count(abstention) / len(b)) if abstention is not None else 0.0
        ),
        "classes": classes,
    }


def jaccard(left: Sequence[object], right: Sequence[object]) -> float | None:
    """Mean set overlap for the one multi-label field, `function`.

        J(A, B) = |A intersect B| / |A union B|,  with J(empty, empty) = 1

    Kappa is not defined on a multi-label field and a strict string comparison
    would score "accusation|accountability" against "accountability" as a total
    disagreement, so the note reports this instead and the artefact reports
    nothing. Labels arrive pipe-joined, as `lib.llm` writes them.
    """
    a, b = _pairs(left, right)
    if not a:
        return None
    scores = []
    for x, y in zip(a, b, strict=True):
        first = {part for part in x.split("|") if part}
        second = {part for part in y.split("|") if part}
        union = first | second
        scores.append(1.0 if not union else len(first & second) / len(union))
    return _round(float(np.mean(scores)))


# --- The gold sample ---------------------------------------------------------


def nonempty(annotations: pd.DataFrame) -> pd.DataFrame:
    """Rows a coder has actually written in.

    `annotations/genocide/annotations.csv` is committed with a header and no
    rows, and a spreadsheet that has been opened and saved may leave blank ones
    behind. `lib.audit.merge` drops them the same way, and this has to agree with
    it or the two would disagree about how much coding has been done.
    """
    if annotations.empty:
        return annotations
    filled = annotations.astype("string").fillna("").apply(
        lambda row: row.str.len().gt(0).any(), axis=1
    )
    return annotations.loc[filled]


def reference_labels(annotations: pd.DataFrame) -> dict[str, dict[str, str]]:
    """The human label the model is scored against, per occurrence and field.

    An adjudicated row wins outright: it exists precisely because the two coders
    disagreed and a decision was taken. Otherwise the reference is the label the
    two coders independently agreed on, field by field. A field they disagree on
    with no adjudication is left out rather than resolved by a rule — picking one
    coder would make the model's score depend on which of them it happens to
    resemble, and averaging two categorical labels is not a thing.
    """
    coded = nonempty(annotations)
    if coded.empty:
        return {}
    by_occurrence: dict[str, dict[str, dict[str, str]]] = {}
    for row in coded.to_dict(orient="records"):
        occurrence = _text(row.get("occurrence_id"))
        coder = _text(row.get("coder"))
        if occurrence and coder:
            by_occurrence.setdefault(occurrence, {})[coder] = {
                field: _text(row.get(field)) for field in SINGLE_LABEL_FIELDS
            }

    reference: dict[str, dict[str, str]] = {}
    for occurrence, coders in by_occurrence.items():
        if ADJUDICATOR in coders:
            reference[occurrence] = dict(coders[ADJUDICATOR])
            continue
        first, second = (coders.get(name) for name in CODERS)
        if not first or not second:
            continue
        agreed = {
            field: first[field] for field in SINGLE_LABEL_FIELDS if first[field] == second[field]
        }
        if agreed:
            reference[occurrence] = agreed
    return reference


def human_agreement(annotations: pd.DataFrame) -> list[dict[str, object]]:
    """Observed agreement and kappa between the two coders, per single-label field.

    Over the occurrences both coders have independently coded, adjudication
    ignored: this measures how far apart the codebook leaves two readers, and
    folding the adjudicated decision back in would measure how well they agree
    after being made to agree.
    """
    coded = nonempty(annotations)
    if coded.empty:
        return []
    first_coder, second_coder = CODERS
    first = {
        _text(row["occurrence_id"]): row
        for row in coded.to_dict(orient="records")
        if _text(row.get("coder")) == first_coder
    }
    second = {
        _text(row["occurrence_id"]): row
        for row in coded.to_dict(orient="records")
        if _text(row.get("coder")) == second_coder
    }
    shared = sorted(set(first) & set(second))
    if not shared:
        return []
    out: list[dict[str, object]] = []
    for field in SINGLE_LABEL_FIELDS:
        left = [_text(first[key].get(field)) for key in shared]
        right = [_text(second[key].get(field)) for key in shared]
        out.append(
            {
                "field": field,
                "observed": observed_agreement(left, right),
                "kappa": cohens_kappa(left, right),
                "n": len(shared),
            }
        )
    return out


def model_vs_human(
    annotations: pd.DataFrame, model: pd.DataFrame
) -> list[dict[str, object]]:
    """The model scored against the human reference, per single-label field.

    Joined on `occurrence_id`, which is the identity `lib.occurrences` builds
    over the span and the digest of the speech body, so a row can only match when
    both sides read the same text.
    """
    reference = reference_labels(annotations)
    if not reference or model.empty:
        return []
    predicted = {
        _text(row["occurrence_id"]): row for row in model.to_dict(orient="records")
    }
    out: list[dict[str, object]] = []
    for field in SINGLE_LABEL_FIELDS:
        keys = sorted(
            key for key, labels in reference.items() if field in labels and key in predicted
        )
        scored = classification(
            [reference[key][field] for key in keys],
            [_text(predicted[key].get(field)) for key in keys],
            abstention=ABSTENTIONS[field],
        )
        if scored is not None:
            out.append({"field": field, **scored})
    return out


def function_jaccard(annotations: pd.DataFrame, model: pd.DataFrame) -> float | None:
    """The multi-label overlap the note reports and the artefact does not.

    The reference is the adjudicated `function` where one exists and the two
    coders' identical string otherwise, which is the same rule
    :func:`reference_labels` applies to the single-label fields.
    """
    coded = nonempty(annotations)
    if coded.empty or model.empty:
        return None
    by_occurrence: dict[str, dict[str, str]] = {}
    for row in coded.to_dict(orient="records"):
        occurrence, coder = _text(row.get("occurrence_id")), _text(row.get("coder"))
        if occurrence and coder:
            by_occurrence.setdefault(occurrence, {})[coder] = _text(row.get("function"))
    predicted = {_text(row["occurrence_id"]): _text(row.get("function")) for row in
                 model.to_dict(orient="records")}

    left, right = [], []
    for occurrence, coders in sorted(by_occurrence.items()):
        if occurrence not in predicted:
            continue
        if ADJUDICATOR in coders:
            agreed = coders[ADJUDICATOR]
        else:
            first, second = (coders.get(name) for name in CODERS)
            if first is None or second is None or first != second:
                continue
            agreed = first
        left.append(agreed)
        right.append(predicted[occurrence])
    return jaccard(left, right) if left else None


def gold_block(
    annotations: pd.DataFrame,
    model: pd.DataFrame,
    *,
    sample_size: int,
    unique_occurrences: int,
    comparison: pd.DataFrame | None = None,
) -> dict[str, object]:
    """The whole `gold` block, including its state.

    `state` is read off the file rather than declared anywhere: nothing coded is
    `not_started`, every sampled occurrence coded by both coders is `complete`,
    and everything between is `in_progress`. The agreement tables are empty lists
    until they can be computed, so a consumer renders "not yet" from an empty
    array rather than from a null it has to special-case.

    `comparison`, when given, is a second run's rows, scored against the same
    human reference by the same computation. Two models scored against one gold
    sample is the only place in this artefact where the word "accuracy" is
    defensible about either of them: everything the `comparison` block reports is
    the two models against each other, which measures neither.
    """
    coded = nonempty(annotations)
    identifiers = (
        coded["occurrence_id"].map(_text) if not coded.empty else pd.Series(dtype=object)
    )
    names = coded["coder"].map(_text) if not coded.empty else pd.Series(dtype=object)
    by_coder = {
        name: set(identifiers[names == name]) for name in sorted(set(names)) if name
    }
    double = len(by_coder.get(CODERS[0], set()) & by_coder.get(CODERS[1], set()))

    if coded.empty:
        state = "not_started"
    elif unique_occurrences and double >= unique_occurrences:
        state = "complete"
    else:
        state = "in_progress"

    return {
        "sample_size": int(sample_size),
        "unique_occurrences": int(unique_occurrences),
        "coders": [
            {"coder": name, "rows": int((names == name).sum())} for name in sorted(by_coder)
        ],
        "double_coded": int(double),
        "adjudicated": int((names == ADJUDICATOR).sum()) if not coded.empty else 0,
        "human_agreement": human_agreement(annotations),
        "model_vs_human": model_vs_human(annotations, model),
        "model_vs_human_comparison": (
            [] if comparison is None else model_vs_human(annotations, comparison)
        ),
        "state": state,
    }


# --- The second opinion ------------------------------------------------------


def _records(
    rows: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Either shape a run arrives in, as a list of mappings.

    The published run reaches this module as a frame joined to the corpus and a
    comparison run as the list of dicts `lib.llm.read_rows` returns. Neither is
    converted into the other: five string columns is all a comparison reads, and
    building a frame around 6,092 raw rows to read them would copy the run for
    nothing.
    """
    if isinstance(rows, pd.DataFrame):
        return [] if rows.empty else rows.to_dict(orient="records")
    return list(rows)


def _compared(
    rows: pd.DataFrame | Sequence[Mapping[str, object]],
) -> dict[str, dict[str, str]]:
    """One run's compared labels, normalised, keyed by occurrence identity.

    Keyed on `occurrence_id` — the identity `lib.occurrences` builds over the
    span and the digest of the speech body — so two runs can only be compared
    where they read the same text. A row carrying no identity is dropped rather
    than compared against whatever else the blank key collides with.
    """
    return {
        identifier: {field: _text(row.get(field)) for field in COMPARED_FIELDS}
        for row in _records(rows)
        if (identifier := _text(row.get("occurrence_id")))
    }


def _multi(value: str) -> frozenset[str]:
    """A pipe-joined multi-label field as the set of labels it means."""
    return frozenset(part for part in value.split("|") if part)


def _same(field: str, left: str, right: str) -> bool:
    """Whether two runs said the same thing about one field of one occurrence.

    String equality for the four single-label fields, set equality for
    `function`: the labels arrive pipe-joined in whatever order a model emitted
    them, so `accusation_or_qualification|accountability` and
    `accountability|accusation_or_qualification` are one judgement written two
    ways and not a disagreement. Order and repetition carry no meaning in that
    field and must not be allowed to manufacture a contested occurrence.
    """
    if field == MULTI_LABEL_FIELD:
        return _multi(left) == _multi(right)
    return left == right


def comparison_overlap(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[str]:
    """The occurrences both runs annotated, sorted by identity.

    Everything a comparison reports is counted over this set and over nothing
    else. Two runs that reached different parts of the corpus have nothing to
    disagree about there, and counting an absence as a disagreement would make
    the run that stopped early look like the more contested one.

    **No eligibility filter.** Everywhere else in this module a discourse label
    is counted only when the verdict was `true_positive` and the evidence was
    located. Here the verdict is one of the things being compared, and the
    occurrence one model called a true positive while the other refused the match
    outright is precisely the disagreement worth reading; filtering on either
    run's verdict would drop it.
    """
    first, second = _compared(published), _compared(comparison)
    return sorted(set(first) & set(second))


def comparison_fields(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Per single-label field: how far the two runs agree over the overlap.

    `observed` and `kappa` are the two statistics :func:`human_agreement` reports
    between the two human coders, computed by the same functions and returning
    None on the same degenerate inputs, so that the two tables can be read
    against each other. `contested` is the count of overlapping occurrences the
    two runs label differently, which is the number a reader can go and look at.

    `function` is absent: kappa is not defined on a multi-label field, and the
    overlap on it is reported by :func:`comparison_function_jaccard` instead. An
    empty list where the two runs overlap nowhere, as `human_agreement` returns
    one where no occurrence has been coded twice.
    """
    first, second = _compared(published), _compared(comparison)
    shared = sorted(set(first) & set(second))
    if not shared:
        return []
    out: list[dict[str, object]] = []
    for field in SINGLE_LABEL_FIELDS:
        left = [first[key][field] for key in shared]
        right = [second[key][field] for key in shared]
        out.append(
            {
                "field": field,
                "n": len(shared),
                "observed": observed_agreement(left, right),
                "kappa": cohens_kappa(left, right),
                "contested": int(
                    sum(not _same(field, x, y) for x, y in zip(left, right, strict=True))
                ),
            }
        )
    return out


def comparison_function_jaccard(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> float | None:
    """Mean set overlap on `function` between two runs, over the overlap.

    The same statistic :func:`function_jaccard` reports against the human
    reference, between the two machines instead. None where the two runs overlap
    nowhere, because zero pairs overlapping zero times is not 0%.
    """
    first, second = _compared(published), _compared(comparison)
    shared = sorted(set(first) & set(second))
    return jaccard(
        [first[key][MULTI_LABEL_FIELD] for key in shared],
        [second[key][MULTI_LABEL_FIELD] for key in shared],
    )


def contested_rows(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> dict[str, tuple[list[str], dict[str, str] | None]]:
    """Per overlapping occurrence: what the two runs differ on, and what the other said.

    The fields are listed in :data:`COMPARED_FIELDS` order — the order `lib.llm`
    writes them into a row — so a reader moving between two artefacts meets them
    in one order. The second element carries the comparison run's own five labels
    in full, so that whoever has been told an occurrence is contested can see
    what the other reading was without loading a second run; it is None exactly
    where the two runs agree on everything, because a reading identical to the
    published one is not an alternative to it.

    An occurrence only one run reached is **absent** from the mapping rather than
    present with an empty list. `15_usage.py` writes `contested: []` for it, which
    is what "compared and agreed" also looks like from the outside; the `overlap`
    count in the comparison block is what tells those two apart.
    """
    first, second = _compared(published), _compared(comparison)
    out: dict[str, tuple[list[str], dict[str, str] | None]] = {}
    for key in sorted(set(first) & set(second)):
        differing = [
            field
            for field in COMPARED_FIELDS
            if not _same(field, first[key][field], second[key][field])
        ]
        out[key] = (differing, dict(second[key]) if differing else None)
    return out


def comparison_block(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
    *,
    run_id: str = "",
    model: str = "",
    run_date: str = "",
    reasoning_effort: str = "",
    prompt_sha256: str = "",
) -> dict[str, object]:
    """The whole `comparison` block, including its state.

    Written from one place in both states, so the block a consumer reads when no
    counter-instrument has been run carries the same keys as the one it reads
    when one has: `state` is `none`, the strings are empty, the counts are zero
    and `fields` is an empty array — the idiom :func:`gold_block` uses to leave
    its agreement tables empty until they can be computed. A null block would
    make every consumer special-case its absence, and the absence is the ordinary
    case.

    The counts that describe the *run* — how many occurrences it annotated, how
    often it abstained, how much of its evidence could not be located — are over
    all of its rows, as `15_usage.py` measures the published run's. The counts
    that describe the *comparison* are over the overlap alone. Both are written,
    because a run that annotated half the corpus and agreed on all of it is not
    the same finding as one that annotated all of it and agreed on half.

    None of this is a validation. Two models agreeing is the same questionnaire
    answered twice by two machines with overlapping training: it measures how
    stable a label is across instruments and says nothing about whether either
    one is right. The gold sample is the only calibration in this artefact.
    """
    contested = contested_rows(published, comparison)
    rows = _records(comparison)
    return {
        "state": "computed" if rows else "none",
        "run_id": run_id,
        "model": model,
        "run_date": run_date,
        "reasoning_effort": reasoning_effort,
        "prompt_sha256": prompt_sha256,
        "occurrences_annotated": len(rows),
        "overlap": len(contested),
        "evidence_invalid": int(sum(not bool(row.get("evidence_valid")) for row in rows)),
        "abstention": {
            "verdict_uncertain": int(
                sum(_text(row.get("verdict")) == "uncertain" for row in rows)
            ),
            "referent_unclear": int(
                sum(_text(row.get("referent")) == "unclear" for row in rows)
            ),
            "stance_unclear": int(
                sum(_text(row.get("stance")) == "unclear" for row in rows)
            ),
        },
        "fields": comparison_fields(published, comparison),
        "function_jaccard": comparison_function_jaccard(published, comparison),
        "function_contested": int(
            sum(MULTI_LABEL_FIELD in fields for fields, _ in contested.values())
        ),
        "contested_any": int(sum(bool(fields) for fields, _ in contested.values())),
    }


# --- Refusals over a run's rows ----------------------------------------------


def row_problems(
    rows: Sequence[Mapping[str, object]], enumerated: Mapping[str, str]
) -> list[str]:
    """Every reason a run's rows cannot be joined to this enumeration.

    `enumerated` maps occurrence_id to the digest of the speech body it was found
    in. Three failures:

    - a row naming an occurrence the enumeration does not have;
    - a row whose `source_sha256` differs from the enumerated one, so the same
      span in the same file is now in a different text;
    - the same occurrence annotated twice, which would double-count it.

    The first two mean the corpus or the lexicon moved underneath a run that has
    already been paid for. The third means the run file was appended to twice,
    which `lib.llm.completed` is meant to prevent and which cannot be repaired
    here: the two rows may carry different labels, and there is no rule for
    choosing between them that is not a coin toss.

    Returned rather than raised, so the caller can report all of them at once
    instead of one per run.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        identifier = _text(row.get("occurrence_id"))
        if identifier not in enumerated:
            problems.append(
                f"{identifier[:12] or '(blank)'}... names an occurrence this enumeration "
                "does not have"
            )
            continue
        digest = _text(row.get("source_sha256"))
        if digest != enumerated[identifier]:
            problems.append(
                f"{identifier[:12]}... was annotated against body {digest[:12]}..., "
                f"the corpus now holds {enumerated[identifier][:12]}..."
            )
        if identifier in seen:
            problems.append(f"{identifier[:12]}... is annotated more than once")
        seen.add(identifier)
    return problems
