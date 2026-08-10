"""Temporal series, and where they change.

The corpus grows 7.4x between 1992 and 2023, so a raw count is a measure of the
Council's growing verbosity before it is a measure of anything else. Every
series here therefore ships with two denominators:

    speech_rate  speeches containing the term / speeches held
    token_rate   occurrences / tokens, per 100,000

Exploratory change points are found by **binary segmentation**: split the series where the
split most reduces the residual sum of squares, keep the split only if a
permutation diagnostic says a reordering of the same values rarely does as well,
then recurse into the two halves. That exchangeability null does not represent
trend or serial dependence — a smoothly rising series will hand back a break at
its midpoint — and repeated recursive tests are not a family-wise-error guarantee.
Those caveats travel with the output. Denominator-aware modelling is provided
separately by denominator-aware binomial and Poisson likelihood scans; the
exploratory detector must not be presented as confirmatory evidence.

No `ruptures` dependency: on 32 annual points the whole search is a few
milliseconds of numpy, and a method this consequential is better read than
imported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .paths import EVENTS, rel

#: Token rates are quoted per this many tokens.
RATE_PER = 100_000

#: The closed vocabulary of `config/events.csv`. A typo becomes a new category
#: and silently splits the overlay, so the set is checked on load.
EVENT_KINDS = frozenset(
    {"atrocity", "conflict", "council", "institutional", "legal", "contested"}
)


#: How a measure of each kind maps onto the columns 03_lexicon.py wrote.
#: `sets` deliberately has no count column — see :func:`measure`.
COLUMN_PREFIX = {"terms": "", "registers": "register_", "sets": "set_"}


def columns_for(kind: str, name: str) -> tuple[str, str | None]:
    """``(has_column, count_column)`` for a measure of the given kind."""
    if kind not in COLUMN_PREFIX:
        raise ValueError(f"unknown measure kind {kind!r}; use one of {sorted(COLUMN_PREFIX)}")
    stem = f"{COLUMN_PREFIX[kind]}{name}"
    return f"has_{stem}", None if kind == "sets" else f"n_{stem}"


# --- Periods and denominators ---------------------------------------------


#: The frequencies :func:`period` understands, coarsest first.
FREQUENCIES = ("year", "quarter", "month")


def period(frame: pd.DataFrame, freq: str) -> pd.Series:
    """Label each speech with the period it falls in.

    ``year`` gives integers, ``quarter`` gives strings like ``2014Q3`` and
    ``month`` gives ``2014-07``; all three serialise straight to JSON, which a
    pandas Period does not, and all three sort chronologically as they are.
    """
    if freq == "year":
        return frame["year"].astype("int64")
    if freq == "quarter":
        return frame["date"].dt.to_period("Q").astype(str)
    if freq == "month":
        return frame["date"].dt.strftime("%Y-%m")
    raise ValueError(f"unknown frequency {freq!r}; use one of {', '.join(FREQUENCIES)}")


def month_grid(first_year: int, last_year: int) -> list[str]:
    """Every month between two years, whether or not the Council met in it.

    A grid rather than the observed months, because the figure this feeds is a
    grid: a cell with no key is drawn by whatever the consumer does with a
    missing value, and on a heatmap that is white — the colour a *zero* has. An
    unobserved month is written with a denominator of nothing and withheld by
    :func:`withhold_below` like any other short month, so "the Council did not
    meet" and "too few speeches to divide by" arrive as the same refusal rather
    than as a measurement.
    """
    if last_year < first_year:
        raise ValueError(f"{last_year} is before {first_year}")
    return [f"{year}-{month:02d}" for year in range(first_year, last_year + 1) for month in range(1, 13)]


def month_of_year(frame: pd.DataFrame) -> pd.Series:
    """The calendar month a speech falls in, 1-12, pooled across the corpus.

    Deliberately not a value :func:`period` returns. Pooling thirty-two Junes
    is a different question from any single month with a different denominator,
    and the two must not be drawn on one scale: a column read is a second
    figure beside the grid, not a margin of it. Keeping it out of the frequency
    vocabulary is what stops a caller reaching it by asking for a period.
    """
    return frame["date"].dt.month.astype("int64")


def denominators(frame: pd.DataFrame, periods: pd.Series, index=None) -> pd.DataFrame:
    """Speeches, tokens and meetings held in each period.

    This is what every rate divides by, so it is computed once from the whole
    corpus and passed down rather than re-derived per term.

    `index` reindexes onto a declared set of periods — see :func:`month_grid` —
    so that a period nobody spoke in is a row of zeros rather than an absence.
    """
    out = frame.groupby(periods, sort=True).agg(
        speeches=("row_id", "size"),
        tokens=("tokens", "sum"),
        meetings=("meeting_symbol", "nunique"),
    )
    if index is not None:
        out = out.reindex(list(index), fill_value=0)
    out.index.name = "period"
    return out


def measure(
    frame: pd.DataFrame,
    periods: pd.Series,
    totals: pd.DataFrame,
    has_column: str,
    count_column: str | None,
) -> pd.DataFrame:
    """One term's series: speeches, occurrences, and both rates.

    Reindexed onto `totals`, so a term absent from a period reads as a zero
    rather than dropping the period from the chart.

    ``count_column=None`` is for a *union* of terms — a set has no occurrence
    count of its own, because summing its members would count a speech saying
    both "genocide" and "war crimes" twice. Such a series reports speeches and
    the speech rate; occurrences and the token rate come back empty rather than
    plausible-looking.
    """
    aggregated = {"speeches": (has_column, "sum")}
    if count_column is not None:
        aggregated["occurrences"] = (count_column, "sum")

    grouped = frame.groupby(periods, sort=True).agg(**aggregated)
    grouped = grouped.reindex(totals.index, fill_value=0)

    out = pd.DataFrame(index=totals.index)
    out["speeches"] = grouped["speeches"].astype("int64")
    out["speech_rate"] = out["speeches"] / totals["speeches"]
    if count_column is None:
        out["occurrences"] = pd.NA
        out["token_rate"] = pd.NA
    else:
        out["occurrences"] = grouped["occurrences"].astype("int64")
        out["token_rate"] = out["occurrences"] / totals["tokens"] * RATE_PER
    return out


# --- Withholding a rate the denominator cannot carry -----------------------
#
# An annual series never needed this: the thinnest year in the corpus holds a
# thousand speeches. A month need not, and the shortest here holds four. The
# arithmetic below is what decides when a rate may be published at all, and it
# lives here rather than in `lib.actors` — which is where it was first written —
# because it is a fact about denominators rather than about countries. Both
# consumers declare their own threshold and derive it from the same function.


def zero_ceiling(n: int, alpha: float = 0.05) -> float:
    """Upper 95% bound on a rate when none of `n` speeches carried the term.

    Exact rather than the 3/n rule of thumb it is within a few per cent of at
    these sizes. This is the claim a blank cell on a heatmap or a blank country
    on a map is making, and the minimums built on it keep that claim honest.
    """
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


def informative_zero_minimum(rate: float, alpha: float = 0.05) -> int:
    """Smallest denominator at which a zero is evidence of running below `rate`.

    The inverse of :func:`zero_ceiling`. Feeding it the corpus's own prevalence
    turns "how many speeches is enough" from a preference into a number the data
    supplies, and lets a step check that a declared threshold still earns its
    justification after the lexicon moves.
    """
    if not 0 < rate < 1:
        raise ValueError(f"rate must lie strictly between 0 and 1, got {rate!r}")
    return max(1, math.ceil(math.log(alpha) / math.log1p(-rate)))


def withhold_below(frame: pd.DataFrame, held: pd.Series, minimum: int) -> pd.DataFrame:
    """Blank the rates a denominator this small cannot support.

    The counts stay. A month with forty speeches that carried the word once did
    exactly that, and the reader is entitled to the forty and the one; what they
    are not entitled to is 2.5%, which would sit on a heatmap beside a figure
    computed over a thousand speeches and be read off the same colour bar.

    `sufficient` is written for every row rather than only the failing ones, so
    a consumer has a flag to test instead of inferring the gate from a null —
    which is the difference between "withheld" and "the pipeline lost it".
    """
    out = frame.copy()
    out["sufficient"] = held.reindex(out.index) >= minimum
    for column in ("speech_rate", "token_rate"):
        if column in out.columns:
            out.loc[~out["sufficient"], column] = np.nan
    return out


def breakdown(
    frame: pd.DataFrame,
    periods: pd.Series,
    by: str,
    has_column: str,
    count_column: str | None,
    top: int | None = None,
    other: str = "Other",
) -> pd.DataFrame:
    """A term's series split by a categorical column.

    Long form — one row per (period, category) — because that is what both a
    stacked area chart and a crosstab want, and it keeps zero-filled cells out
    of the payload. `top` folds everything below the n most-spoken categories
    into a single row so a 99-way agenda split stays legible; the fold is by
    total speeches, not by term hits, so a rare category cannot be promoted by
    a single mention.
    """
    labels = frame[by].astype("string").fillna("Unknown")
    if top is not None and labels.nunique() > top:
        keep = set(labels.value_counts().head(top).index)
        labels = labels.where(labels.isin(keep), other)

    aggregated = {
        "held": ("row_id", "size"),
        "tokens": ("tokens", "sum"),
        "speeches": (has_column, "sum"),
    }
    if count_column is not None:
        aggregated["occurrences"] = (count_column, "sum")

    # Named before grouping so reset_index lands on `period` and `by` directly,
    # rather than on whatever column the labels happened to be derived from.
    grouped = (
        frame.groupby([periods.rename("period"), labels.rename(by)], sort=True)
        .agg(**aggregated)
        .reset_index()
    )
    grouped["speech_rate"] = grouped["speeches"] / grouped["held"]
    if count_column is None:
        grouped["occurrences"] = pd.NA
        grouped["token_rate"] = pd.NA
    else:
        grouped["token_rate"] = grouped["occurrences"] / grouped["tokens"] * RATE_PER
    return grouped


# --- Change points ---------------------------------------------------------


@dataclass(frozen=True)
class Break:
    """A detected regime shift, reported with the evidence for it."""

    index: int  #: position in the series; the break falls *before* it
    label: str  #: the period the new regime starts in
    gain: float  #: residual sum of squares removed by the split
    p_value: float  #: permutation test against a reordering of the same values
    before: float  #: mean of the segment left of the break
    after: float  #: mean of the segment right of it
    interval_start: int  #: start of the sub-interval whose gain was tested
    interval_stop: int  #: exclusive stop of that sub-interval

    @property
    def ratio(self) -> float:
        """How many times higher the series runs after the break."""
        return self.after / self.before if self.before else float("nan")

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "label": self.label,
            "gain": round(self.gain, 8),
            "p_value": round(self.p_value, 5),
            "before": self.before,
            "after": self.after,
            "ratio": self.ratio,
            "interval_start": self.interval_start,
            "interval_stop": self.interval_stop,
        }


@dataclass(frozen=True)
class SplitPlan:
    """Every (interval, split) pair a scan of an n-point series considers.

    Built once per series length and reused across permutations: the indices do
    not depend on the values, so a 2,000-trial test is 2,000 vectorised passes
    over the same arrays rather than 2,000 nested loops.
    """

    n: int
    min_size: int
    starts: np.ndarray
    splits: np.ndarray
    stops: np.ndarray
    left: np.ndarray  #: points left of each split
    right: np.ndarray  #: points right of it

    def __len__(self) -> int:
        return int(self.starts.size)


def plan_splits(n: int, min_size: int, max_intervals: int = 500) -> SplitPlan:
    """Enumerate the sub-intervals to search, and the splits inside each.

    Classic binary segmentation only ever splits a segment as a whole, which
    makes it blind to a *bump*: a series that rises and falls back has no single
    informative split, so the search stops before it ever looks inside. This
    corpus is bump-shaped — 1993-96 and 2013-15 both rise and subside — so the
    scan runs over sub-intervals too, which is Wild Binary Segmentation
    (Fryzlewicz 2014, Annals of Statistics 42(6)).

    Gains from intervals of different lengths compare directly: the reduction in
    residual sum of squares equals the squared CUSUM statistic, which already
    carries the length normalisation. Nothing further is needed to stop a long
    interval winning on size alone.

    Exhaustive while that stays under `max_intervals` — true at the 32 annual
    points this pipeline runs on — and a doubling ladder of interval lengths
    beyond it. Both are deterministic, so a series always yields the same plan
    and the permutation null is calibrated on exactly the search that produced
    the observed statistic.
    """
    if min_size < 1:
        raise ValueError("min_size must be at least 1")

    narrowest = 2 * min_size
    if n < narrowest:
        empty = np.empty(0, dtype=np.int64)
        return SplitPlan(n, min_size, empty, empty, empty, empty, empty)

    lengths: list[int] = list(range(narrowest, n + 1))
    if sum(n - length + 1 for length in lengths) > max_intervals:
        ladder, length = [], narrowest
        while length < n:
            ladder.append(length)
            length *= 2
        lengths = [*ladder, n]

    starts, splits, stops = [], [], []
    for length in lengths:
        for a in range(n - length + 1):
            b = a + length
            for t in range(a + min_size, b - min_size + 1):
                starts.append(a)
                splits.append(t)
                stops.append(b)

    start_index = np.asarray(starts, dtype=np.int64)
    split_index = np.asarray(splits, dtype=np.int64)
    stop_index = np.asarray(stops, dtype=np.int64)
    return SplitPlan(
        n=n,
        min_size=min_size,
        starts=start_index,
        splits=split_index,
        stops=stop_index,
        left=split_index - start_index,
        right=stop_index - split_index,
    )


def gains(values: np.ndarray, plan: SplitPlan) -> np.ndarray:
    """Residual sum of squares removed by each planned split.

    ``n1 * n2 / (n1 + n2) * (mean_left - mean_right) ** 2`` — algebraically the
    same quantity as ``rss(whole) - rss(left) - rss(right)``, but written from
    prefix sums so every candidate is evaluated in one vectorised pass, and
    without the cancellation that differencing two large sums of squares invites.
    """
    if values.size != plan.n:
        raise ValueError(f"{values.size} values against a plan for {plan.n}")
    if len(plan) == 0:
        return np.empty(0, dtype=float)

    cumulative = np.concatenate(([0.0], np.cumsum(values)))
    left_sum = cumulative[plan.splits] - cumulative[plan.starts]
    right_sum = cumulative[plan.stops] - cumulative[plan.splits]
    difference = left_sum / plan.left - right_sum / plan.right
    return plan.left * plan.right / (plan.left + plan.right) * difference**2


def best_candidate(values: np.ndarray, plan: SplitPlan) -> tuple[int, int, int, float]:
    """The strongest ``(start, split, stop, gain)`` in a plan."""
    found = gains(values, plan)
    if found.size == 0:
        return -1, -1, -1, 0.0
    best = int(np.argmax(found))
    gain = float(found[best])
    if gain <= 0:
        return -1, -1, -1, 0.0
    return (
        int(plan.starts[best]),
        int(plan.splits[best]),
        int(plan.stops[best]),
        gain,
    )


def best_split(values: np.ndarray, plan: SplitPlan) -> tuple[int, float]:
    """The strongest split anywhere in the plan, or ``(-1, 0.0)`` if none."""
    _, split, _, gain = best_candidate(values, plan)
    return split, gain


def permutation_p(
    values: np.ndarray, gain: float, plan: SplitPlan, trials: int, rng: np.random.Generator
) -> float:
    """How often a reordering of these values splits at least as well.

    The null is "these values in no particular order" and the statistic is the
    maximum over the whole plan, so searching more sub-intervals lifts the null
    as much as it lifts the observed value. The extra search power does not buy
    false positives.

    The observed statistic counts itself in both numerator and denominator
    (Phipson & Smyth 2010), so the smallest reportable p-value is
    ``1 / (trials + 1)`` rather than an unbelievable zero.
    """
    if gain <= 0 or len(plan) == 0:
        return 1.0
    shuffled = values.copy()
    at_least = 1
    for _ in range(trials):
        rng.shuffle(shuffled)
        if gains(shuffled, plan).max() >= gain:
            at_least += 1
    return at_least / (trials + 1)


def change_points(
    values,
    labels,
    *,
    min_size: int = 4,
    max_breaks: int = 4,
    alpha: float = 0.05,
    trials: int = 2_000,
    max_intervals: int = 500,
    seed: int = 20_260_807,
) -> list[Break]:
    """Segment a series, testing every split before accepting it.

    Greedy: take the strongest split available anywhere, test it, and only
    recurse into a segment that yielded a diagnostic split. A segment whose best
    split fails is closed, which bounds the number of follow-up tests but does not
    turn the exploratory recursion into family-wise-error-controlled inference.
    """
    raw = np.asarray(values, dtype=float)
    labels = list(labels)
    if raw.size != len(labels):
        raise ValueError(f"{raw.size} values against {len(labels)} labels")

    # Centring changes no gain but removes the cancellation that small rates
    # (~0.02) would otherwise suffer in the prefix sums.
    centred = raw - raw.mean() if raw.size else raw

    rng = np.random.default_rng(seed)
    plans: dict[int, SplitPlan] = {}
    found: list[Break] = []
    segments: list[tuple[int, int]] = [(0, raw.size)]

    def plan_for(length: int) -> SplitPlan:
        if length not in plans:
            plans[length] = plan_splits(length, min_size, max_intervals)
        return plans[length]

    while segments and len(found) < max_breaks:
        candidates = []
        for start, stop in segments:
            left, at, right, gain = best_candidate(
                centred[start:stop], plan_for(stop - start)
            )
            if at >= 0:
                candidates.append(
                    (gain, start, stop, start + left, start + at, start + right)
                )
        if not candidates:
            break

        gain, start, stop, interval_start, at, interval_stop = max(candidates)
        segments.remove((start, stop))

        # Tested once: a second call would advance the generator and report a
        # p-value other than the one the decision was made on.
        p_value = permutation_p(centred[start:stop], gain, plan_for(stop - start), trials, rng)
        if p_value > alpha:
            continue

        found.append(
            Break(
                index=at,
                label=str(labels[at]),
                gain=gain,
                p_value=p_value,
                before=float(raw[interval_start:at].mean()),
                after=float(raw[at:interval_stop].mean()),
                interval_start=interval_start,
                interval_stop=interval_stop,
            )
        )
        segments += [(start, at), (at, stop)]

    return sorted(found, key=lambda b: b.index)


# --- Denominator-aware change inference -----------------------------------


def _binomial_log_likelihood(successes: np.ndarray, trials: np.ndarray) -> float:
    total = float(trials.sum())
    if total <= 0:
        return 0.0
    probability = float(successes.sum()) / total
    probability = min(max(probability, np.finfo(float).eps), 1 - np.finfo(float).eps)
    return float(
        (successes * np.log(probability) + (trials - successes) * np.log1p(-probability)).sum()
    )


def _poisson_log_likelihood(counts: np.ndarray, exposure: np.ndarray) -> float:
    total = float(exposure.sum())
    if total <= 0:
        return 0.0
    rate = max(float(counts.sum()) / total, np.finfo(float).eps)
    # Terms independent of the fitted rate cancel in every split comparison.
    return float((counts * np.log(rate) - rate * exposure).sum())


def likelihood_gains(
    counts: np.ndarray,
    exposure: np.ndarray,
    candidates: np.ndarray,
    family: str,
) -> np.ndarray:
    """Likelihood-ratio gain for each candidate breakpoint."""
    likelihood = {
        "binomial": _binomial_log_likelihood,
        "poisson": _poisson_log_likelihood,
    }.get(family)
    if likelihood is None:
        raise ValueError("family must be 'binomial' or 'poisson'")
    null = likelihood(counts, exposure)
    return np.asarray(
        [
            2
            * (
                likelihood(counts[:split], exposure[:split])
                + likelihood(counts[split:], exposure[split:])
                - null
            )
            for split in candidates
        ],
        dtype=float,
    )


def _rate_interval(count: int, exposure: int, family: str) -> tuple[float, float]:
    """Approximate 95% interval for one aggregated segment rate."""
    if exposure <= 0:
        return float("nan"), float("nan")
    if family == "binomial":
        z = 1.959963984540054
        p = count / exposure
        denominator = 1 + z**2 / exposure
        centre = (p + z**2 / (2 * exposure)) / denominator
        margin = z * np.sqrt(p * (1 - p) / exposure + z**2 / (4 * exposure**2)) / denominator
        return max(0.0, centre - margin), min(1.0, centre + margin)
    rate = count / exposure
    if count == 0:
        return 0.0, -np.log(0.05) / exposure
    factor = np.exp(1.959963984540054 / np.sqrt(count))
    return rate / factor, rate * factor


def rate_change_point(
    counts,
    exposure,
    labels,
    *,
    family: str,
    min_size: int = 4,
    trials: int = 2_000,
    alpha: float = 0.05,
    seed: int = 20_260_807,
) -> dict[str, object] | None:
    """Test the strongest single rate change while preserving denominators.

    The bootstrap simulates the no-change model with the observed exposure in
    every period and recalculates the maximum over all candidate years. Thus
    denominator variation and breakpoint search are both represented in the
    null. ``alpha`` is supplied by the caller after across-series correction.
    """
    observed = np.asarray(counts, dtype=np.int64)
    held = np.asarray(exposure, dtype=np.int64)
    labels = list(labels)
    if observed.size != held.size or observed.size != len(labels):
        raise ValueError("counts, exposure and labels must have the same length")
    if (held <= 0).any() or (observed < 0).any():
        raise ValueError("counts must be non-negative and exposure positive")
    if family == "binomial" and (observed > held).any():
        raise ValueError("binomial successes cannot exceed trials")
    candidates = np.arange(min_size, observed.size - min_size + 1, dtype=np.int64)
    if candidates.size == 0:
        return None

    gains_found = likelihood_gains(observed, held, candidates, family)
    best_position = int(np.argmax(gains_found))
    split = int(candidates[best_position])
    gain = float(gains_found[best_position])
    if gain <= 0:
        return None

    rng = np.random.default_rng(seed)
    null_rate = float(observed.sum()) / float(held.sum())
    exceed = 1
    for _ in range(trials):
        if family == "binomial":
            simulated = rng.binomial(held, null_rate)
        else:
            simulated = rng.poisson(held * null_rate)
        if likelihood_gains(simulated, held, candidates, family).max() >= gain:
            exceed += 1
    p_value = exceed / (trials + 1)

    left_count, right_count = int(observed[:split].sum()), int(observed[split:].sum())
    left_exposure, right_exposure = int(held[:split].sum()), int(held[split:].sum())
    before, after = left_count / left_exposure, right_count / right_exposure
    return {
        "index": split,
        "label": str(labels[split]),
        "family": family,
        "gain": round(gain, 8),
        "p_value": round(p_value, 5),
        "alpha": alpha,
        "accepted": p_value <= alpha,
        "before": before,
        "before_ci95": list(_rate_interval(left_count, left_exposure, family)),
        "after": after,
        "after_ci95": list(_rate_interval(right_count, right_exposure, family)),
        "ratio": after / before if before else None,
        "counts": [left_count, right_count],
        "exposure": [left_exposure, right_exposure],
    }


# --- Event overlay ---------------------------------------------------------


def load_events() -> pd.DataFrame:
    """Read the primary-sourced chart annotations in `config/events.csv`.

    Fails on an unknown `kind` rather than letting a typo quietly become a
    seventh category that no legend accounts for.
    """
    if not EVENTS.exists():
        raise FileNotFoundError(f"{rel(EVENTS)} is missing")
    frame = pd.read_csv(EVENTS, dtype="string", keep_default_na=False)

    required = {"date", "label", "kind", "source", "source_url"}
    if missing := required - set(frame.columns):
        raise ValueError(f"{rel(EVENTS)}: missing column(s) {', '.join(sorted(missing))}")

    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    if bad := frame.loc[frame["date"].isna(), "label"].tolist():
        raise ValueError(f"{rel(EVENTS)}: unparseable date(s) for {bad}")

    if unknown := set(frame["kind"]) - EVENT_KINDS:
        raise ValueError(f"{rel(EVENTS)}: unknown kind(s) {sorted(unknown)}")

    invalid_sources = ~frame["source_url"].str.startswith("https://")
    if invalid_sources.any():
        labels = frame.loc[invalid_sources, "label"].tolist()
        raise ValueError(f"{rel(EVENTS)}: missing primary-source URL(s) for {labels}")

    frame["year"] = frame["date"].dt.year.astype("int64")
    return frame.sort_values("date").reset_index(drop=True)
