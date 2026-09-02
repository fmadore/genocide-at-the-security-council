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

from . import series

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

#: The corpus-wide share of eligible occurrences whose stance is
#: `rejects_or_denies`, as both committed runs measure it: 106 of 6,092, 1.7%.
#:
#: It is written here because :func:`stance_rows` needs something to test a
#: speaker's own share against. The review of 1 September 2026 (§4.5, item 11)
#: is right that :data:`MINIMUM_OCCURRENCES` alone does not make `share_rejects`
#: rankable — at n = 20 the expected count against this base rate is 0.35, so a
#: single rejection reads as 5%, five times the corpus, and the bottom of the
#: ranking is entirely that arithmetic. Raising the minimum instead would be the
#: wrong repair: at the n it would take to separate 5% from 1.7% (about 220
#: eligible occurrences) three speakers survive, and Sudan's 19 rejections in 43
#: and Serbia's 15 in 45 — the finding the column exists for — would go with the
#: noise. So the count and the share are still published at 20, and what is
#: added is the interval and the test: a share is *separated* from this base rate
#: only when the lower bound of its 95% Wilson interval clears it. Ranking is the
#: consumer's business, and the flag is what tells it which rows can be ordered.
BASE_REJECTION_SHARE: Final = 0.0174

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

#: The minority share below which Cohen's kappa is withheld rather than
#: published. Set at one per cent by the review of 1 September 2026 (§4.5,
#: item 5), which found `verdict` carrying a bare 0.000: both instruments called
#: all but six of 6,092 occurrences a true positive, chance agreement under
#: those marginals is 0.998, and dividing 99.9% agreement by the 0.2% left over
#: produces a number that reads as "no better than chance" about the most
#: stable field in the run. `confidence` fails the same test from the other
#: side, Gemini having written `high` 99.06% of the time. The three fields that
#: carry information — quotation, stance, referent — clear the floor by an order
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
    "stance": 7,
    "referent": 40,
}

#: Reference occurrences a class needs before its precision, recall and F1 are
#: published rather than withheld with its counts.
#:
#: Twenty, the same denominator :data:`MINIMUM_OCCURRENCES` guards a share at
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
    contested: frozenset[str] = frozenset(),
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
        disputed = (
            int(group["occurrence_id"].map(_text).isin(contested).sum()) if contested else 0
        )
        cells.append(
            {
                "actor": str(actor),
                "referent": str(referent),
                "count": len(group),
                "contested": disputed,
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

    A published share carries its 95% Wilson interval and one more flag,
    `separated`, which is true only when the lower bound of that interval clears
    :data:`BASE_REJECTION_SHARE`. That is the flag a consumer must rank on. A
    share of 1 in 24 is 4.2% and looks like two and a half times the corpus,
    but its interval runs from 0.7% to 20% and covers the corpus rate three
    times over; ordering it against a share of 2 in 25 orders two draws from the
    same urn. Sudan's 19 in 43 and Serbia's 15 in 45 are separated by a wide
    margin, and they stay in the table with the interval that says so.
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
        rejects = int(counts["rejects_or_denies"])
        interval = share_interval(rejects, total) if enough and total else (None, None)
        out.append(
            {
                "actor": actor,
                "eligible": total,
                "sufficient": bool(enough),
                "stances": counts,
                "share_rejects": (
                    _round(rejects / total) if enough and total else None
                ),
                "share_low": interval[0],
                "share_high": interval[1],
                "separated": bool(
                    interval[0] is not None and interval[0] > BASE_REJECTION_SHARE
                ),
            }
        )
    return out


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
) -> list[dict[str, object]]:
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


def _f1(row: Mapping[str, object]) -> float:
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


def reference_coverage(annotations: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Per field: how much of the double-coded sample produced a reference label.

    :func:`reference_labels` scores the model only where the two coders agreed
    or an adjudicator decided, which is right — averaging two categorical labels
    is not a thing, and picking one coder would make the model's score depend on
    which of them it happens to resemble — but it is also the *easy subset*, and
    it is a different subset for every field. The review of 1 September 2026
    (§4.5, item 6) is blunt about what that means: an accuracy of 0.9 on stance
    over the 81% of occurrences the coders agreed on is not an accuracy of 0.9,
    and the artefact carried no way to tell.

    So the excluded share travels with the score. `available` is the
    double-coded occurrences — both coders present, or an adjudicated row —
    `resolved` is those that yielded a reference label for this field, and
    `excluded_share` is the rest as a fraction. A field the coders never
    disagreed on excludes nothing and says so with a zero, which is a different
    reading from a null and is written as one.
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
    reference = reference_labels(annotations)
    available = [
        occurrence
        for occurrence, coders in by_occurrence.items()
        if ADJUDICATOR in coders or all(name in coders for name in CODERS)
    ]
    out: dict[str, dict[str, object]] = {}
    for field in SINGLE_LABEL_FIELDS:
        resolved = sum(field in reference.get(occurrence, {}) for occurrence in available)
        out[field] = {
            "available": len(available),
            "resolved": int(resolved),
            "excluded": len(available) - int(resolved),
            "excluded_share": (
                _round((len(available) - resolved) / len(available)) if available else None
            ),
        }
    return out


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
                "n": len(shared),
                **chance_corrected(left, right, categories=FIELD_CATEGORIES[field]),
            }
        )
    return out


def human_function_agreement(annotations: pd.DataFrame) -> dict[str, object]:
    """The two coders on `function`, which is a set and not a label.

    Three statistics, because no one of them is enough. The mean MASI-weighted
    overlap says how close the two sets usually are; Krippendorff's alpha says
    how much of that survives chance, which a mean overlap over eight labels of
    which two are near-universal does not ask; and the per-label table says
    *which* label the disagreement is in, which is the only one of the three a
    prompt or a codebook can be revised against.

    Empty — a null alpha, an empty table — until two coders have coded the same
    occurrence, in the idiom :func:`human_agreement` uses.
    """
    coded = nonempty(annotations)
    if coded.empty:
        return {"n": 0, "jaccard": None, "alpha_masi": None, "labels": []}
    first_coder, second_coder = CODERS
    sides: list[dict[str, str]] = []
    for name in (first_coder, second_coder):
        sides.append(
            {
                _text(row["occurrence_id"]): _text(row.get(MULTI_LABEL_FIELD))
                for row in coded.to_dict(orient="records")
                if _text(row.get("coder")) == name
            }
        )
    shared = sorted(set(sides[0]) & set(sides[1]))
    if not shared:
        return {"n": 0, "jaccard": None, "alpha_masi": None, "labels": []}
    left = [sides[0][key] for key in shared]
    right = [sides[1][key] for key in shared]
    return {
        "n": len(shared),
        "jaccard": jaccard(left, right),
        "alpha_masi": krippendorff_alpha_masi(left, right),
        "labels": per_label_kappa(left, right),
    }


def model_vs_human(
    annotations: pd.DataFrame, model: pd.DataFrame
) -> list[dict[str, object]]:
    """The model scored against the human reference, per single-label field.

    Joined on `occurrence_id`, which is the identity `lib.occurrences` builds
    over the span and the digest of the speech body, so a row can only match when
    both sides read the same text.

    Every row carries what :func:`reference_coverage` measured for its field, so
    that the score is never read without the share of double-coded occurrences
    it was *not* computed over. The two coders disagree at different rates on
    different fields — stance most, referent least — so the denominators differ
    row by row and the easy subset is a different subset in each. `excluded` is
    the count of occurrences that left no reference label for the field, and
    `excluded_share` the fraction of the double-coded sample that is.
    """
    reference = reference_labels(annotations)
    if not reference or model.empty:
        return []
    coverage = reference_coverage(annotations)
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
            counted = coverage.get(field, {})
            out.append(
                {
                    "field": field,
                    **scored,
                    "double_coded": int(counted.get("available", 0) or 0),
                    "excluded": int(counted.get("excluded", 0) or 0),
                    "excluded_share": counted.get("excluded_share"),
                }
            )
    return out


def function_jaccard(annotations: pd.DataFrame, model: pd.DataFrame) -> float | None:
    """The multi-label overlap the note reports and the artefact does not.

    The reference is the adjudicated `function` where one exists and the two
    coders' agreed set otherwise, which is the same rule
    :func:`reference_labels` applies to the single-label fields.

    *Agreed set*, through :func:`_same`, and not an identical string. The labels
    are pipe-joined in whatever order a coder wrote them, so
    `accusation_or_qualification|accountability` and
    `accountability|accusation_or_qualification` are one judgement written two
    ways; comparing the strings dropped the second row from the reference
    silently, while the model comparison a hundred lines below had always used
    set equality. Two rules for one field is the fault the review names (§4.5,
    item 7), and the rule that survives is the one that matches what the
    codebook says the field means.
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
            if first is None or second is None or not _same(MULTI_LABEL_FIELD, first, second):
                continue
            agreed = first
        left.append(agreed)
        right.append(predicted[occurrence])
    return jaccard(left, right) if left else None


def frame_rows(
    candidates: pd.DataFrame, annotations: pd.DataFrame
) -> list[dict[str, object]]:
    """Per sampling frame: how large it is and how much of it has been coded.

    The three frames of `13_gold_sample.py` answer different questions and are
    reported separately or not at all. The probability frame is the unbiased
    estimate of accuracy over the corpus, weighted by the probabilities it
    records; the coverage frame guarantees every period and cue is seen; the
    disagreement frame is a deliberate over-sample of the rare and the contested
    whose inclusion probabilities differ by a factor of seven, and the per-class
    recall it buys is read unweighted. Pooling them would produce a figure that
    estimates nothing, so the artefact never publishes a pooled one and this
    block is what a consumer needs to keep them apart.

    `weighted` says which of the two readings a frame takes. An equal-probability
    frame is weighted back to the corpus; a purposive one is not, because there
    is no population its rate is a rate of.
    """
    if candidates.empty or "sampling_frame" not in candidates:
        return []
    coded = nonempty(annotations)
    done = set(coded["occurrence_id"].map(_text)) if not coded.empty else set()
    out: list[dict[str, object]] = []
    for name in sorted(set(candidates["sampling_frame"].map(_text))):
        part = candidates.loc[candidates["sampling_frame"].map(_text) == name]
        identifiers = set(part["occurrence_id"].map(_text))
        out.append(
            {
                "frame": name,
                "rows": len(part),
                "occurrences": len(identifiers),
                "coded": len(identifiers & done),
                "weighted": name == "probability",
            }
        )
    return out


def gold_block(
    annotations: pd.DataFrame,
    model: pd.DataFrame,
    *,
    sample_size: int,
    unique_occurrences: int,
    comparison: pd.DataFrame | None = None,
    candidates: pd.DataFrame | None = None,
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
        "frames": [] if candidates is None else frame_rows(candidates, annotations),
        "human_agreement": human_agreement(annotations),
        "human_function": human_function_agreement(annotations),
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

    `observed`, `kappa`, `pabak` and `minority_share` are the statistics
    :func:`human_agreement` reports between the two human coders, computed by
    the same :func:`chance_corrected` and withheld on the same rule, so that the
    two tables can be read against each other. `contested` is the count of
    overlapping occurrences the two runs label differently, which is the number
    a reader can go and look at.

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
                **chance_corrected(left, right, categories=FIELD_CATEGORIES[field]),
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


def comparison_referents(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Per referent: how far the two instruments place the same occurrences there.

    :func:`per_class` with the published run as the reference, which makes the
    F1 a *cross-instrument* figure and not an accuracy: it says how reliably a
    referent survives being read by a second model, and says nothing about
    whether either model was right. The review of 1 September 2026 (§4.6) is
    what it is for — a diffusion curve for a referent the two instruments agree
    on 60% of the time is a chronology of one model's habits, and the view
    withholds it below 0.8 on this number.

    The support floor applies as everywhere else, so a referent the published
    run placed fewer than twenty times comes back with its counts and no rates,
    and is withheld for the same reason a rate at n = 3 is.
    """
    first, second = _compared(published), _compared(comparison)
    shared = sorted(set(first) & set(second))
    if not shared:
        return []
    return per_class(
        [first[key]["referent"] for key in shared],
        [second[key]["referent"] for key in shared],
    )


def comparison_function_alpha(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> float | None:
    """Krippendorff's alpha under MASI between two runs, over the overlap."""
    first, second = _compared(published), _compared(comparison)
    shared = sorted(set(first) & set(second))
    return krippendorff_alpha_masi(
        [first[key][MULTI_LABEL_FIELD] for key in shared],
        [second[key][MULTI_LABEL_FIELD] for key in shared],
    )


def comparison_function_labels(
    published: pd.DataFrame | Sequence[Mapping[str, object]],
    comparison: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Per `function` label: how far two runs agree that it applies.

    One mean overlap says how far apart two readings of the field are; it does
    not say which label they are apart on, and on this corpus almost all of it
    is in one place. The table is what a prompt revision is written against.
    """
    first, second = _compared(published), _compared(comparison)
    shared = sorted(set(first) & set(second))
    return per_label_kappa(
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
        "referents": comparison_referents(published, comparison),
        "function_alpha_masi": comparison_function_alpha(published, comparison),
        "function_labels": comparison_function_labels(published, comparison),
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
