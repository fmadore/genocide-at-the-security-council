"""A second model run read against the published one.

**A second opinion is not a second measurement.** A comparison run is a different
model answering the same questionnaire about the same occurrences, and the
functions that read one are counted over the *overlap* — the occurrences both
runs reached — on raw labels with no eligibility filter, because the verdict the
filter is cut from is itself one of the things being compared. Where two models
agree, what has been measured is the stability of a label across instruments; the
human gold sample, in `lib.gold_estimates`, stays the only calibration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

import pandas as pd

from .agreement import (
    FIELD_CATEGORIES,
    SINGLE_LABEL_FIELDS,
    _multi,
    _text,
    chance_corrected,
    jaccard,
    krippendorff_alpha_masi,
    per_class,
    per_label_kappa,
)

#: Every field a second opinion is compared on, in the order `lib.llm` writes
#: them into a row and :func:`contested_rows` lists them. The single-label
#: fields plus `function`, which is here because a reader looking at a
#: disagreement wants all six labels and not the ones a statistic happens to be
#: defined on.
COMPARED_FIELDS: Final[tuple[str, ...]] = (
    "verdict",
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
)

#: The one member of :data:`COMPARED_FIELDS` carrying several labels at once, and
#: therefore the one compared as a set rather than as a string.
MULTI_LABEL_FIELD: Final = "function"


# --- The second opinion ------------------------------------------------------


def _records(
    rows: pd.DataFrame | Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Either shape a run arrives in, as a list of mappings.

    The published run reaches this module as a frame joined to the corpus and a
    comparison run as the list of dicts `lib.model_runs.read_rows` returns.
    Neither is converted into the other: five string columns is all a comparison
    reads, and building a frame around 6,092 raw rows to read them would copy
    the run for nothing.
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
    in one order. The second element carries the comparison run's own six labels
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
            "position_unclear": int(
                sum(_text(row.get("speaker_position")) == "unclear" for row in rows)
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
