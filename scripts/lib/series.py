"""Temporal series, and where they change.

The corpus grows 7.4x between 1992 and 2023, so a raw count is a measure of the
Council's growing verbosity before it is a measure of anything else. Every
series here therefore ships with two denominators:

    speech_rate  speeches containing the term / speeches held
    token_rate   occurrences / tokens, per 100,000

Change points are found by **binary segmentation**: split the series where the
split most reduces the residual sum of squares, keep the split only if a
permutation test says a reordering of the same values rarely does as well, then
recurse into the two halves. The permutation null is "these values in no
particular order", which is the right null for *is there a regime shift?* and
the wrong one for *is there a trend* — a smoothly rising series will hand back a
break at its midpoint. That caveat travels with the output rather than being
left for a reader to trip over.

No `ruptures` dependency: on 32 annual points the whole search is a few
milliseconds of numpy, and a method this consequential is better read than
imported.
"""

from __future__ import annotations

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


def period(frame: pd.DataFrame, freq: str) -> pd.Series:
    """Label each speech with the period it falls in.

    ``year`` gives integers, ``quarter`` gives strings like ``2014Q3``; both
    serialise straight to JSON, which a pandas Period does not.
    """
    if freq == "year":
        return frame["year"].astype("int64")
    if freq == "quarter":
        return frame["date"].dt.to_period("Q").astype(str)
    raise ValueError(f"unknown frequency {freq!r}; use 'year' or 'quarter'")


def denominators(frame: pd.DataFrame, periods: pd.Series) -> pd.DataFrame:
    """Speeches, tokens and meetings held in each period.

    This is what every rate divides by, so it is computed once from the whole
    corpus and passed down rather than re-derived per term.
    """
    out = frame.groupby(periods, sort=True).agg(
        speeches=("row_id", "size"),
        tokens=("tokens", "sum"),
        meetings=("meeting_symbol", "nunique"),
    )
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


def best_split(values: np.ndarray, plan: SplitPlan) -> tuple[int, float]:
    """The strongest split anywhere in the plan, or ``(-1, 0.0)`` if none."""
    found = gains(values, plan)
    if found.size == 0:
        return -1, 0.0
    best = int(np.argmax(found))
    gain = float(found[best])
    return (int(plan.splits[best]), gain) if gain > 0 else (-1, 0.0)


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
    recurse into a segment that yielded a significant one. A segment whose best
    split fails the test is closed — its own halves are not examined, which is
    what keeps the family-wise error from running away over a 32-point series.
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
            at, gain = best_split(centred[start:stop], plan_for(stop - start))
            if at >= 0:
                candidates.append((gain, start, stop, start + at))
        if not candidates:
            break

        gain, start, stop, at = max(candidates)
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
                before=float(raw[start:at].mean()),
                after=float(raw[at:stop].mean()),
            )
        )
        segments += [(start, at), (at, stop)]

    return sorted(found, key=lambda b: b.index)


# --- Event overlay ---------------------------------------------------------


def load_events() -> pd.DataFrame:
    """Read `config/events.csv`, the hand-curated chart annotations.

    Fails on an unknown `kind` rather than letting a typo quietly become a
    seventh category that no legend accounts for.
    """
    if not EVENTS.exists():
        raise FileNotFoundError(f"{rel(EVENTS)} is missing")
    frame = pd.read_csv(EVENTS, dtype="string", keep_default_na=False)

    required = {"date", "label", "kind", "source"}
    if missing := required - set(frame.columns):
        raise ValueError(f"{rel(EVENTS)}: missing column(s) {', '.join(sorted(missing))}")

    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    if bad := frame.loc[frame["date"].isna(), "label"].tolist():
        raise ValueError(f"{rel(EVENTS)}: unparseable date(s) for {bad}")

    if unknown := set(frame["kind"]) - EVENT_KINDS:
        raise ValueError(f"{rel(EVENTS)}: unknown kind(s) {sorted(unknown)}")

    frame["year"] = frame["date"].dt.year.astype("int64")
    return frame.sort_values("date").reset_index(drop=True)
