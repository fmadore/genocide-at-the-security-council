"""Samples of occurrences that record the probability each row was drawn with.

Every draw ranks a frame by a seeded hash of each occurrence's identity, so a
sample does not depend on row order and is redrawn exactly from its seed. Each
selected row carries its frame, seed, frame size and digest and its inclusion
probability: what a reader needs to weight an estimate, or to know that a frame
was never meant to estimate anything. 03's lexicon audit and 13's gold sample
both draw from here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Final

import pandas as pd

PROBABILITY: Final = "probability"
COVERAGE: Final = "coverage"
NEGATIVE: Final = "negative_high_recall"


def candidate_id(occurrence: str, sampling_frame: str) -> str:
    """Identity for one occurrence's place in a named sampling frame."""
    return hashlib.sha256(f"{occurrence}\x1f{sampling_frame}".encode()).hexdigest()


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _rank(value: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}\x1f{value}".encode()).hexdigest()


def probability_sample(
    frame: pd.DataFrame, size: int, seed: int, sampling_frame: str
) -> pd.DataFrame:
    """A row-order-independent equal-probability sample of occurrences."""
    if size < 1:
        raise ValueError("Sample size must be positive.")
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    population = len(frame)
    draw = min(size, population)
    ranked = frame.assign(
        _draw=frame["occurrence_id"].map(lambda value: _rank(str(value), seed))
    ).sort_values(["_draw", "occurrence_id"])
    selected = ranked.head(draw).drop(columns="_draw").copy()
    probability = draw / population if population else 0.0
    selected["sampling_frame"] = sampling_frame
    selected["strategy"] = "simple random occurrence sample"
    selected["seed"] = seed
    selected["frame_size"] = population
    selected["sample_size"] = draw
    selected["inclusion_probability"] = probability
    selected["sampling_weight"] = 1 / probability if probability else float("nan")
    selected["stratum_size"] = population
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected["frame_sha256"] = frame_digest
    selected["sample_sha256"] = _digest(
        [sampling_frame, str(seed), frame_digest, *selected["occurrence_id"].astype(str).tolist()]
    )
    selected["candidate_id"] = selected["occurrence_id"].map(
        lambda value: candidate_id(str(value), sampling_frame)
    )
    return selected.sort_values(["term", "filename", "start"]).reset_index(drop=True)


def stratified_sample(
    frame: pd.DataFrame,
    sizes: Mapping[str, int | None],
    seed: int,
    sampling_frame: str,
    *,
    stratum_column: str = "stratum",
    strategy: str = "disproportionate stratified occurrence sample",
) -> pd.DataFrame:
    """A fixed number of occurrences from each named stratum, at its own probability.

    :func:`probability_sample` gives every occurrence the same chance and is the
    frame an unbiased estimate is computed from. This is the other kind: the
    strata are chosen precisely because they are rare or contested, each is
    sampled at a rate of its own, and the rates differ by two orders of
    magnitude. Nothing drawn here estimates a corpus quantity, and the
    `inclusion_probability` it records is what says so — a reader who wants an
    estimate weights by it, and a reader who wants per-class recall on
    `rejects_or_denies` reads the stratum unweighted and is right to.

    `sizes` maps a stratum name to how many to draw from it, or to None for a
    census — all of it, at probability 1, which is what a stratum of 134 rows
    that the whole design exists to measure deserves. A stratum smaller than its
    size is likewise taken whole; a stratum named in `sizes` and absent from the
    frame contributes nothing and is not an error, because a design written
    against two model runs must survive a run that found none of something.

    Rows whose stratum is blank or absent from `sizes` are outside the frame and
    are not drawn. The stratum column is expected to be *disjoint* — one stratum
    per occurrence, assigned in a precedence the caller decides — because
    overlapping strata make the inclusion probability of a row the union of
    several draws, and nothing downstream could reconstruct it from what is
    recorded here.
    """
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected: list[pd.DataFrame] = []
    for name, size in sizes.items():
        if size is not None and size < 1:
            raise ValueError(f"Stratum {name!r} asks for {size} occurrences.")
        stratum = frame.loc[frame[stratum_column].astype(str) == name]
        if stratum.empty:
            continue
        population = len(stratum)
        draw = population if size is None else min(size, population)
        ranked = stratum.assign(
            _draw=stratum["occurrence_id"].map(lambda value: _rank(str(value), seed))
        ).sort_values(["_draw", "occurrence_id"])
        chosen = ranked.head(draw).drop(columns="_draw").copy()
        chosen["stratum_size"] = population
        chosen["sample_size"] = draw
        chosen["inclusion_probability"] = draw / population
        chosen["sampling_weight"] = population / draw
        selected.append(chosen)

    if not selected:
        return frame.iloc[0:0].copy()
    sample = pd.concat(selected, ignore_index=True)
    sample["sampling_frame"] = sampling_frame
    sample["strategy"] = strategy
    sample["seed"] = seed
    sample["frame_size"] = len(frame)
    sample["frame_sha256"] = frame_digest
    sample["sample_sha256"] = _digest(
        [sampling_frame, str(seed), frame_digest, *sample["occurrence_id"].astype(str).tolist()]
    )
    sample["candidate_id"] = sample["occurrence_id"].map(
        lambda value: candidate_id(str(value), sampling_frame)
    )
    return sample.sort_values([stratum_column, "filename", "start"]).reset_index(drop=True)


def coverage_inclusion(
    frame: pd.DataFrame, size: int, *, strata: tuple[str, ...] = ("term", "period")
) -> pd.Series:
    """Every occurrence's probability of entering :func:`coverage_sample`.

    One anchor per stratum at `1 / stratum size`, then a simple random fill of
    what is left: a unit is included as its stratum's anchor or, failing that,
    by the fill. The same arithmetic `coverage_sample` records for the rows it
    draws, computed for every row of the frame, which is what a design-weighted
    estimate over several frames needs.
    """
    if frame.empty:
        return pd.Series(dtype=float, index=frame.index)
    stratum_sizes = frame.groupby(list(strata))["occurrence_id"].transform("size")
    strata_total = frame.groupby(list(strata)).ngroups
    remaining_total = len(frame) - strata_total
    fill_draws = min(max(size - strata_total, 0), remaining_total)
    fill_probability = fill_draws / remaining_total if remaining_total else 0.0
    anchor = 1 / stratum_sizes
    return anchor + (1 - anchor) * fill_probability


def union_inclusion(*probabilities: pd.Series) -> pd.Series:
    """The probability of entering at least one of several independent draws.

    `1 - prod(1 - p_f)`. The frames are drawn with different seeds of the same
    hash ranking, which is what licenses treating them as independent.
    """
    missed = pd.Series(1.0, index=probabilities[0].index)
    for probability in probabilities:
        missed = missed * (1 - probability.fillna(0.0))
    return 1 - missed


def coverage_sample(
    frame: pd.DataFrame,
    size: int,
    seed: int,
    *,
    strata: tuple[str, ...] = ("term", "period"),
) -> pd.DataFrame:
    """Cover each stratum once, then fill randomly with recorded probabilities."""
    if size < 1:
        raise ValueError("Sample size must be positive.")
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    if frame.empty:
        return probability_sample(frame, size, seed, COVERAGE)

    ranked = frame.assign(
        _anchor=frame["occurrence_id"].map(lambda value: _rank(str(value), seed))
    )
    anchors = (
        ranked.sort_values(["_anchor", "occurrence_id"])
        .groupby(list(strata), sort=True)
        .head(1)
    )
    strata_total = len(anchors)
    if size < strata_total:
        raise ValueError(
            f"Coverage sample size {size} is smaller than its {strata_total} strata."
        )
    remaining = ranked.drop(index=anchors.index).assign(
        _fill=lambda rows: rows["occurrence_id"].map(
            lambda value: _rank(str(value), seed + 1)
        )
    )
    fill_draws = min(size - strata_total, len(remaining))
    selected = pd.concat(
        [anchors, remaining.sort_values(["_fill", "occurrence_id"]).head(fill_draws)]
    ).copy()
    stratum_sizes = frame.groupby(list(strata))["occurrence_id"].size()
    remaining_total = len(frame) - strata_total
    fill_probability = fill_draws / remaining_total if remaining_total else 0.0

    def inclusion(row: pd.Series) -> float:
        stratum = tuple(row[field] for field in strata)
        stratum_size = int(stratum_sizes.loc[stratum])
        anchor_probability = 1 / stratum_size
        return anchor_probability + (1 - anchor_probability) * fill_probability

    selected["stratum_size"] = selected.apply(
        lambda row: int(stratum_sizes.loc[tuple(row[field] for field in strata)]), axis=1
    )
    selected["inclusion_probability"] = selected.apply(inclusion, axis=1)
    selected["sampling_weight"] = 1 / selected["inclusion_probability"]
    selected["sampling_frame"] = COVERAGE
    selected["strategy"] = "one per term-period stratum, then simple random fill"
    selected["seed"] = seed
    selected["frame_size"] = len(frame)
    selected["sample_size"] = len(selected)
    selected["strata_total"] = strata_total
    selected["fill_draws"] = fill_draws
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected["frame_sha256"] = frame_digest
    selected["sample_sha256"] = _digest(
        [COVERAGE, str(seed), frame_digest, *selected["occurrence_id"].astype(str).tolist()]
    )
    selected["candidate_id"] = selected["occurrence_id"].map(
        lambda value: candidate_id(str(value), COVERAGE)
    )
    return (
        selected.drop(columns=["_anchor", "_fill"], errors="ignore")
        .sort_values([*strata, "filename", "start"])
        .reset_index(drop=True)
    )
