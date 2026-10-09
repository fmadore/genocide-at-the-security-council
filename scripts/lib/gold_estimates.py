"""The human gold sample: the reference label, and what is measured against it.

`13_gold_sample.py` draws the sample and two coders fill
`annotations/genocide/annotations.csv`; this module reads that file beside a
model run and builds the `gold` block `15_usage.py` publishes. It is the one
place in the usage layer where a model is scored against people rather than
against another model, so every rule that decides what a score is computed over
— which rows count as coded, what the reference label is when the coders
disagree, how a coded unit is weighted back to the corpus — is written here and
tested on constructed rows, by a machine with no corpus and no run.
"""

from __future__ import annotations

import math
from typing import Any, Final

import numpy as np
import pandas as pd

from .agreement import (
    FIELD_CATEGORIES,
    SINGLE_LABEL_FIELDS,
    _round,
    _text,
    chance_corrected,
    classification,
    jaccard,
    krippendorff_alpha_masi,
    per_label_kappa,
)
from .usage_comparison import MULTI_LABEL_FIELD, _same

#: The value of each single-label field that means "I decline to decide". The
#: abstention rate is a measurement of the run, not a defect in it: the prompt
#: tells the model that an honest abstention beats a guess.
ABSTENTIONS: Final[dict[str, str]] = {
    "verdict": "uncertain",
    "quotation": "unclear",
    "concrete_case": "unclear",
    "speaker_position": "unclear",
    "referent": "unclear",
}

#: The two coders of `annotations/genocide/annotations.csv`, and the coder name
#: an adjudicated row carries. Initials rather than names, as the file uses.
CODERS: Final[tuple[str, str]] = ("FM", "JG")
ADJUDICATOR: Final = "adjudicated"


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


def reference_coverage(annotations: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Per field: how much of the double-coded sample produced a reference label.

    :func:`reference_labels` scores the model only where the two coders agreed
    or an adjudicator decided, which is right — averaging two categorical labels
    is not a thing, and picking one coder would make the model's score depend on
    which of them it happens to resemble — but it is also the *easy subset*, and
    it is a different subset for every field. The review of 1 September 2026
    (§4.5, item 6) is blunt about what that means: an accuracy of 0.9 on position
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
    different fields — position most, referent least — so the denominators differ
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


#: Coded units with a reference label a weighted or corrected figure needs
#: before it is published; below it the block says `waiting` and why.
MINIMUM_GOLD: Final = 30

#: The fields whose shares the dashboard draws, and which are corrected.
CORRECTED_FIELDS: Final[tuple[str, ...]] = ("concrete_case", "speaker_position")


def _hajek(values: np.ndarray, probabilities: np.ndarray) -> tuple[float, float]:
    """A Hajek mean and its standard error under Poisson sampling.

    `sum(y / pi) / sum(1 / pi)`, with the linearised variance
    `sum((1 - pi) / pi**2 * (y - mean)**2) / (sum(1 / pi))**2`. The frames are
    fixed-size draws, not Poisson ones, so the error is slightly conservative.
    """
    weights = 1 / probabilities
    total = float(weights.sum())
    mean = float((weights * values).sum() / total)
    variance = float(((1 - probabilities) / probabilities**2 * (values - mean) ** 2).sum()) / total**2
    return mean, math.sqrt(max(variance, 0.0))


def _gold_units(
    annotations: pd.DataFrame, model: pd.DataFrame, design: pd.DataFrame, field: str
) -> pd.DataFrame:
    """Coded units with a reference label, a model label and a design weight."""
    reference = reference_labels(annotations)
    rows = [
        {"occurrence_id": occurrence, "human": labels[field]}
        for occurrence, labels in reference.items()
        if field in labels
    ]
    if not rows or model.empty or design.empty or field not in model:
        return pd.DataFrame(columns=["occurrence_id", "human", "model", "pi_union"])
    units = pd.DataFrame(rows)
    labels = model[["occurrence_id", field]].rename(columns={field: "model"})
    labels["occurrence_id"] = labels["occurrence_id"].map(_text)
    labels["model"] = labels["model"].map(_text)
    units = units.merge(labels, on="occurrence_id", how="inner")
    weights = design[["occurrence_id", "pi_union"]].copy()
    weights["occurrence_id"] = weights["occurrence_id"].map(_text)
    weights["pi_union"] = pd.to_numeric(weights["pi_union"], errors="coerce")
    units = units.merge(weights, on="occurrence_id", how="inner")
    return units.loc[units["pi_union"] > 0]


def weighted_accuracy(
    annotations: pd.DataFrame, model: pd.DataFrame, design: pd.DataFrame
) -> list[dict[str, object]]:
    """Model accuracy per field, over every coded unit, weighted to the corpus.

    The per-frame tables say how the model does on each design's units; this
    says what share of the corpus it labels as the coders would, using every
    coded unit at the weight its union inclusion probability gives it. Withheld
    below :data:`MINIMUM_GOLD` units.
    """
    out = []
    for field in (*SINGLE_LABEL_FIELDS,):
        units = _gold_units(annotations, model, design, field)
        n = len(units)
        entry: dict[str, object] = {"field": field, "units": n}
        if n < MINIMUM_GOLD:
            out.append({**entry, "state": "waiting", "estimate": None, "low": None, "high": None})
            continue
        correct = (units["human"] == units["model"]).to_numpy(dtype=float)
        mean, error = _hajek(correct, units["pi_union"].to_numpy(dtype=float))
        out.append(
            {
                **entry,
                "state": "computed",
                "estimate": _round(mean),
                "low": _round(max(0.0, mean - 1.96 * error)),
                "high": _round(min(1.0, mean + 1.96 * error)),
            }
        )
    return out


def corrected_shares(
    annotations: pd.DataFrame, model: pd.DataFrame, design: pd.DataFrame
) -> list[dict[str, object]]:
    """Corpus shares of each label, the model's corrected by the gold sample.

    Prediction-powered inference (Angelopoulos et al., 2023): the model's share
    over every annotated occurrence, plus the design-weighted mean of
    `human - model` over the coded units, which removes the model's bias as far
    as the sample can measure it. The interval adds the two variances. Where
    the model is right the correction is near zero and the interval narrow;
    where it is wrong the correction says by how much. The published matrix
    and profiles stay the model's own; this block is what may be *cited* about
    the corpus once enough units are coded.
    """
    out = []
    for field in CORRECTED_FIELDS:
        units = _gold_units(annotations, model, design, field)
        labels = model[field].map(_text) if field in model else pd.Series(dtype=object)
        total = len(labels)
        categories = sorted(set(labels) | set(units["human"]))
        block: dict[str, object] = {"field": field, "units": len(units), "occurrences": total}
        if len(units) < MINIMUM_GOLD or not total:
            out.append({**block, "state": "waiting", "categories": []})
            continue
        probabilities = units["pi_union"].to_numpy(dtype=float)
        rows = []
        for category in categories:
            share = float((labels == category).mean())
            difference = (units["human"] == category).to_numpy(dtype=float) - (
                units["model"] == category
            ).to_numpy(dtype=float)
            rectifier, error = _hajek(difference, probabilities)
            corrected = share + rectifier
            spread = 1.96 * math.sqrt(error**2 + share * (1 - share) / total)
            rows.append(
                {
                    "category": category,
                    "model_share": _round(share),
                    "corrected_share": _round(min(1.0, max(0.0, corrected))),
                    "low": _round(max(0.0, corrected - spread)),
                    "high": _round(min(1.0, corrected + spread)),
                }
            )
        out.append({**block, "state": "computed", "categories": rows})
    return out


def gold_block(
    annotations: pd.DataFrame,
    model: pd.DataFrame,
    *,
    sample_size: int,
    unique_occurrences: int,
    comparison: pd.DataFrame | None = None,
    candidates: pd.DataFrame | None = None,
    design: pd.DataFrame | None = None,
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
        "weighted_accuracy": (
            [] if design is None else weighted_accuracy(annotations, model, design)
        ),
        "corrected_shares": (
            [] if design is None else corrected_shares(annotations, model, design)
        ),
        "minimum_gold": MINIMUM_GOLD,
        "state": state,
    }
