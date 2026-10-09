"""Agreement between two readings of the same occurrences.

Two coders, the human reference and a model, two model runs: every comparison
the usage layer publishes is one of these statistics over two equal-length lists
of labels. They sit below the modules that use them — `lib.usage`,
`lib.gold_estimates` and `lib.usage_comparison` — together with the two cell
conversions those modules and `lib.usage_refusals` share, so that none of them
has to import another to read a label as a string.

**Agreement is computed, not imported.** Cohen's kappa and the per-class F1 table
are eleven lines of arithmetic each, and writing them out means the formula is in
the repository beside the number it produced instead of inside a dependency that
would have to be installed on the deploy runner to rebuild a research artefact.
Every one of them returns ``None`` rather than a number when the input is
degenerate, because "kappa could not be computed on one category" and "the coders
agreed by chance" are different findings.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

import numpy as np
import pandas as pd

#: The minority share below which Cohen's kappa is withheld rather than
#: published. Set at one per cent by the review of 1 September 2026 (§4.5,
#: item 5), which found `verdict` carrying a bare 0.000: both instruments called
#: all but six of 6,092 occurrences a true positive, chance agreement under
#: those marginals is 0.998, and dividing 99.9% agreement by the 0.2% left over
#: produces a number that reads as "no better than chance" about the most
#: stable field in the run. `confidence` fails the same test from the other
#: side, Gemini having written `high` 99.06% of the time. The three fields that
#: carry information — quotation, position, referent — clear the floor by an order
#: of magnitude in both runs, so nothing informative is suppressed by it.
KAPPA_MINORITY_FLOOR: Final = 0.01

#: How many categories the codebook declares for each single-label field, which
#: is what :func:`pabak` corrects against.
#:
#: Written out rather than read from `lib.audit` and the referent table, and
#: held to those by `tests/test_usage.py`, because these numbers have to be
#: *fixed*: a chance correction that moved when a referent was added would make
#: two runs of the same instrument incomparable across a vocabulary revision.
#: When the codebook does move, the test fails, and updating this is part of
#: the same reviewed diff. Referent list v2 is such a move: 29 became 40, being
#: the 41 identifiers the file now holds less the one it retires, because the
#: correction is against what a coder or a model was actually offered.
FIELD_CATEGORIES: Final[dict[str, int]] = {
    "verdict": 3,
    "quotation": 5,
    "concrete_case": 4,
    "speaker_position": 7,
    "referent": 40,
}

#: Reference occurrences a class needs before its precision, recall and F1 are
#: published rather than withheld with its counts.
#:
#: Twenty, the same denominator :data:`lib.usage.MINIMUM_OCCURRENCES` guards a share at
#: and for the same reason: below it the widest 95% interval on a rate is about
#: ±22 points and the quantity cannot be read. The review's finding (§4.5,
#: item 8) is what makes this a floor rather than a caption: averaging F1 over
#: the union of classes gives every label a model used and the reference never
#: did an F1 of zero, and with 29 referent classes against a 200-row sample the
#: macro figure is mostly those zeros. The counts are written at every support,
#: because "the humans placed three occurrences here and the model found two of
#: them" is a fact worth reading; the rates are not.
CLASS_SUPPORT_FLOOR: Final = 20

#: The fields one label per occurrence, and therefore the ones kappa and a
#: confusion table are defined on. `function` is multi-label and is reported as a
#: Jaccard overlap by the note instead; see :func:`jaccard`.
SINGLE_LABEL_FIELDS: Final[tuple[str, ...]] = (
    "verdict",
    "quotation",
    "concrete_case",
    "speaker_position",
    "referent",
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


def _round(value: float | None, digits: int = 6) -> float | None:
    """A plain Python float, or None. numpy scalars do not survive json.dumps."""
    return None if value is None else round(float(value), digits)


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


def minority_share(left: Sequence[object], right: Sequence[object]) -> float | None:
    """How much of each rater's work fell outside its own commonest label, at worst.

    Per rater: one minus the share of the label it used most. Returned as the
    smaller of the two, because a chance-corrected statistic is degenerate as
    soon as *one* side is a constant with a rounding error on it — the
    correction divides by what is left after chance, and one flat margin is
    enough to make that almost nothing.

    None on an empty comparison. This is the quantity :data:`KAPPA_MINORITY_FLOOR`
    is a floor on, and it is published beside kappa so a reader can see why a
    kappa was withheld rather than being told that it was.
    """
    a, b = _pairs(left, right)
    if not a:
        return None
    shares = []
    for side in (a, b):
        counts: dict[str, int] = {}
        for label in side:
            counts[label] = counts.get(label, 0) + 1
        shares.append(1.0 - max(counts.values()) / len(side))
    return _round(min(shares))


def pabak(
    left: Sequence[object], right: Sequence[object], *, categories: int = 2
) -> float | None:
    """Prevalence-adjusted, bias-adjusted kappa over `categories` categories.

        PABAK = ( k * p_o - 1 ) / ( k - 1 )

    Byrt, Bishop and Carlin (1993) for the two-category case, where it reduces
    to `2 * p_o - 1`; the k-category form is the same argument carried through.
    It is kappa's formula with the observed marginals replaced by uniform ones,
    which is exactly the assumption to make where the marginals are the problem:
    for `verdict`, both runs called all but six of 6,092 occurrences a true
    positive, chance agreement under those marginals is 0.998, and kappa divides
    the run's 99.9% agreement by the 0.002 that is left. PABAK says instead what
    the agreement is worth against a coin toss over the codebook's own
    categories, which is a defensible thing to publish where kappa is not.

    `categories` is the codebook's declared count for the field, from
    :data:`FIELD_CATEGORIES`, and never the number of labels this particular
    sample happened to contain. Counting the observed ones would make the
    statistic move with the draw: a gold sample of 200 that missed four rare
    referents would report a *higher* PABAK for the referent field than one that
    caught them, having done no better.

    Gwet's AC1 was the alternative and is deliberately not here. Its chance term
    is built from the mean of the two raters' marginals, which is the property
    that makes it stable under an unbalanced prevalence — but it is also
    computed over the categories *observed*, and on a 200-row gold sample of a
    29-category referent field the set of observed categories is itself a draw.
    PABAK on a fixed k moves only with the agreement; AC1 here would move with
    which rare referents the sample happened to catch, and this artefact has one
    small sample and no way to tell those two movements apart.

    None on an empty comparison or on fewer than two categories, where the
    denominator vanishes and the quantity is not defined.
    """
    if categories < 2:
        return None
    observed = observed_agreement(left, right)
    if observed is None:
        return None
    return _round((categories * observed - 1) / (categories - 1))


def chance_corrected(
    left: Sequence[object], right: Sequence[object], *, categories: int
) -> dict[str, object]:
    """The agreement statistics for one field, with kappa withheld where it lies.

    Four values: the observed agreement, kappa, PABAK, and the minority share
    kappa was judged on. `kappa` is None and `kappa_withheld` is true when that
    share falls below :data:`KAPPA_MINORITY_FLOOR` — the field is one label with
    a rounding error, kappa's correction is dividing by almost nothing, and the
    0.000 it returns for `verdict` reads as "no better than chance" about two
    instruments that agreed on 6,086 of 6,092 occurrences. Withholding it and
    publishing PABAK beside it says the true thing in the space where the false
    one was.

    Withheld and undefined are distinguished: a kappa that could not be computed
    at all — one category across both raters, or nothing to compare — comes back
    with `kappa_withheld` false, because nothing was suppressed.
    """
    share = minority_share(left, right)
    withheld = share is not None and share < KAPPA_MINORITY_FLOOR
    return {
        "observed": observed_agreement(left, right),
        "kappa": None if withheld else cohens_kappa(left, right),
        "kappa_withheld": bool(withheld),
        "minority_share": share,
        "pabak": pabak(left, right, categories=categories),
    }


# --- The multi-label field ---------------------------------------------------


def _multi(value: str) -> frozenset[str]:
    """A pipe-joined multi-label field as the set of labels it means."""
    return frozenset(part for part in value.split("|") if part)


def _masi_similarity(first: frozenset[str], second: frozenset[str]) -> float:
    """Passonneau's MASI: Jaccard weighted by how far one set contains the other.

        MASI(A, B) = J(A, B) * M(A, B)

        M = 1     identical
          = 2/3   one a proper subset of the other
          = 1/3   they intersect and each holds something the other does not
          = 0     disjoint

    Measuring Agreement on Set-valued Items (Passonneau 2006), written out here
    for the same reason kappa is: the formula belongs in the repository beside
    the number it produced. Two empty sets are identical and score 1, which is
    the convention :func:`jaccard` already follows — a codebook where both
    coders declined to assign a function is agreement, not a division by zero.
    """
    if first == second:
        return 1.0
    union = first | second
    if not union:
        return 1.0
    intersection = first & second
    if not intersection:
        return 0.0
    overlap = len(intersection) / len(union)
    monotonicity = 2 / 3 if (first < second or second < first) else 1 / 3
    return overlap * monotonicity


def masi_distance(first: frozenset[str], second: frozenset[str]) -> float:
    """One minus the MASI similarity: the distance Krippendorff's alpha needs."""
    return 1.0 - _masi_similarity(first, second)


def krippendorff_alpha_masi(
    left: Sequence[object], right: Sequence[object]
) -> float | None:
    """Krippendorff's alpha over the multi-label field, under the MASI distance.

        D_o    = (1/n) * sum over units u of  delta( a_u, b_u )
        D_e    = 1 / (2n(2n-1)) * sum over ordered k != l of  delta( v_k, v_l )
        alpha  = 1 - D_o / D_e

    over the 2n set-valued labels the two coders wrote, pooled. This is the
    general coincidence-matrix definition specialised to exactly two coders with
    nothing missing, which is what this study's `function` column is; the
    specialisation is written out rather than the general form built, because a
    coincidence matrix over set-valued categories would be a table of 2^8 rows
    to answer a question about n of them.

    Alpha rather than a mean Jaccard because :func:`jaccard` has no chance
    correction at all: eight function labels of which two are near-universal
    give a comfortable mean overlap between coders who are barely reading.
    Alpha's expected disagreement is computed from the sets the coders actually
    used, so a field where everyone writes `accusation_or_qualification` cannot
    score well by writing it again.

    Labels arrive pipe-joined, as `lib.llm` writes them. None where there is
    nothing to compare, and None where expected disagreement is zero — every
    label pooled is the same set, so there is no disagreement for the statistic
    to explain and the ratio is undefined rather than perfect.
    """
    a, b = _pairs(left, right)
    if not a:
        return None
    first = [_multi(value) for value in a]
    second = [_multi(value) for value in b]
    observed = float(
        np.mean([masi_distance(x, y) for x, y in zip(first, second, strict=True)])
    )
    pooled: dict[frozenset[str], int] = {}
    for value in first + second:
        pooled[value] = pooled.get(value, 0) + 1
    total = sum(pooled.values())
    if total < 2:
        return None
    # Over the *distinct* label sets, weighted by how often each was written,
    # which is Krippendorff's coincidence matrix written out. The pairwise form
    # is the same number and is quadratic in the number of occurrences: on the
    # 6,092 of this corpus it is 148 million set comparisons, and there are
    # about thirty distinct sets.
    types = list(pooled)
    expected = sum(
        pooled[one] * pooled[other] * masi_distance(one, other)
        for one in types
        for other in types
        if one != other
    ) / (total * (total - 1))
    if math.isclose(expected, 0.0):
        return None
    return _round(1 - observed / expected)


def per_label_kappa(
    left: Sequence[object], right: Sequence[object]
) -> list[dict[str, object]]:
    """Cohen's kappa on each `function` label taken as its own yes/no decision.

    One alpha over the whole field says how far apart two readings are; it does
    not say *which* label they are apart on, and the review of 1 September 2026
    found the disagreement concentrated in one place — about 520 occurrences
    differ only on whether `accusation_or_qualification` accompanies
    `accountability`, while `commemoration` and `institutional_title_or_mandate`
    agree to within 0.83 and 0.87. A per-label table is what makes that visible,
    and it is the table a prompt revision is written against.

    Every label either side used, sorted, with the count each side gave it and
    the kappa of the two indicator vectors. `left` and `right` are the two
    readings in the order they were handed in — the two coders, or the reference
    and the model — because a label one side applies twice as often as the other
    is a finding about the codebook and the direction of it matters. `kappa` is
    null where the statistic is undefined: a label both sides put on every unit,
    or on none, leaves one category and no chance agreement to correct.
    """
    a, b = _pairs(left, right)
    if not a:
        return []
    first = [_multi(value) for value in a]
    second = [_multi(value) for value in b]
    labels = sorted({label for value in first + second for label in value})
    out: list[dict[str, object]] = []
    for label in labels:
        mine = ["yes" if label in value else "no" for value in first]
        theirs = ["yes" if label in value else "no" for value in second]
        out.append(
            {
                "label": label,
                "left": int(mine.count("yes")),
                "right": int(theirs.count("yes")),
                "observed": observed_agreement(mine, theirs),
                "kappa": cohens_kappa(mine, theirs),
            }
        )
    return out


def per_class(
    reference: Sequence[object],
    predicted: Sequence[object],
    *,
    floor: int = CLASS_SUPPORT_FLOOR,
) -> list[dict[str, Any]]:
    """Precision, recall, F1 and the counts behind them, for every label either side used.

        precision_c = tp_c / ( tp_c + fp_c )
        recall_c    = tp_c / ( tp_c + fn_c )
        f1_c        = 2 * precision_c * recall_c / ( precision_c + recall_c )

    Support is counted on the *reference* side, which is what makes a class with
    support 0 legible: the model used a label the humans never did.

    **The three rates are withheld below `floor` and the counts are not.** A
    class the reference placed three times can be described — "the humans put
    three occurrences here and the model found two of them" — but it cannot be
    *measured*: recall over a denominator of three moves in thirds, and an F1
    computed on it is a number with an interval wider than the scale it sits on.
    Publishing it invited exactly the reading the review of 1 September 2026
    caught (§4.5, item 8), where 29 referent classes against a 200-row sample
    turned a macro average into an average of empty ones. `measurable` says
    which side of the floor a class fell on, so a consumer renders the counts
    for the rest instead of a blank.

    A zero denominator above the floor cannot happen for `recall` — support is
    at least `floor` — and yields 0.0 for `precision`, because at that level the
    quantity is defined and empty: nothing of that class was predicted, so
    nothing of it was predicted correctly.
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
        measurable = support >= floor
        out.append(
            {
                "label": label,
                "precision": _round(precision) if measurable else None,
                "recall": _round(recall) if measurable else None,
                "f1": _round(f1) if measurable else None,
                "support": int(support),
                "predicted": int(predicted_total),
                "correct": int(true_positive),
                "measurable": bool(measurable),
            }
        )
    return out


def classification(
    reference: Sequence[object],
    predicted: Sequence[object],
    *,
    abstention: str | None = None,
    floor: int = CLASS_SUPPORT_FLOOR,
) -> dict[str, object] | None:
    """Accuracy, two aggregate F1s, the abstention rate, and the per-class table.

        accuracy    = (1/n) * sum_i [ ref_i == pred_i ]
        macro_f1    = mean of f1_c over classes with support_c >= floor
        weighted_f1 = sum_c support_c * f1_c / sum_c support_c
        abstention  = (1/n) * sum_i [ pred_i == the field's abstention label ]

    **Two aggregates, because they answer two questions and neither answers
    both.** Macro-F1 asks how well the classes are told apart when each counts
    once; it is the right question, and it is the one the review found being
    answered wrongly (§4.5, item 8) — averaged over the union of classes, every
    label a model used that the reference never did contributed an F1 of zero,
    and with 29 referent classes against a 200-row sample the figure was mostly
    those zeros. It is computed here over the classes that clear `floor` alone,
    and is None when none of them does, which for `referent` on a 200-row sample
    is the ordinary case: at most `rwanda_1994`, `genocide_in_general` and
    `bosnia_srebrenica` reach twenty.

    Weighted-F1 asks instead how well the field is labelled over the population
    as it is, each class counting for as many occurrences as it holds. That is
    the defensible aggregate for `referent`, and the one to read there: the
    referent distribution is genuinely long-tailed — three cases carry two
    thirds of the corpus — and a reader of this artefact wants to know how much
    of the corpus is labelled correctly, not how the instrument would fare on a
    corpus with equal numbers of Rwanda and Holodomor. Its own weakness is
    stated by the same sentence: it can be high while every rare class is wrong,
    which is what the per-class counts are there to show.

    `classes_measured` and `classes_withheld` count the two sides of the floor,
    so a macro figure is never read without the number of classes it is over.
    Macro-F1 is None on a degenerate comparison too — one category across both
    sides — where it would be the F1 of the only class and would say nothing
    about telling classes apart; weighted-F1 is 1.0 there, correctly, because
    every occurrence in the population was labelled right. None is returned for
    the whole block when there is nothing to compare.
    """
    a, b = _pairs(reference, predicted)
    if not a:
        return None
    classes = per_class(a, b, floor=floor)
    degenerate = len(set(a) | set(b)) < 2
    measured = [] if degenerate else [row for row in classes if row["measurable"]]
    supported = [row for row in classes if int(row["support"]) > 0]
    support_total = sum(int(row["support"]) for row in supported)
    return {
        "n": len(a),
        "accuracy": _round(sum(x == y for x, y in zip(a, b, strict=True)) / len(a)),
        "macro_f1": (
            _round(float(np.mean([float(row["f1"]) for row in measured])))
            if measured
            else None
        ),
        "weighted_f1": (
            _round(
                sum(_f1(row) * int(row["support"]) for row in supported) / support_total
            )
            if support_total
            else None
        ),
        "support_floor": int(floor),
        "classes_measured": len(measured),
        "classes_withheld": len([row for row in supported if not row["measurable"]]),
        "abstention_rate": _round(
            (b.count(abstention) / len(b)) if abstention is not None else 0.0
        ),
        "classes": classes,
    }


def _f1(row: Mapping[str, Any]) -> float:
    """One class's F1, recomputed where the table withheld it.

    `weighted_f1` is defined over every class the reference used, including the
    ones below the floor, because a support-weighted mean that dropped them
    would be a mean over a population it had quietly shrunk. The floor governs
    what is *published* per class, not what the aggregate is computed from, and
    the two would otherwise disagree about the same rows.
    """
    correct = int(row["correct"])
    support = int(row["support"])
    predicted = int(row["predicted"])
    return 2 * correct / (support + predicted) if (support + predicted) else 0.0


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
