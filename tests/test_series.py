"""Series construction and change-point detection, on fixtures.

The change-point pass is the one piece of statistical machinery in the pipeline,
and its output will be read as a date — "the discourse shifted in 2013". So it is
tested on series whose answer is known by construction: a step function has to be
found at the step, noise has to yield nothing, and a series that is only growing
has to be reported as what it is rather than as a regime change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from lib import series

YEARS = list(range(1992, 2024))


@pytest.fixture
def corpus():
    """Four speeches per year across two speaker groups, with known counts."""
    rows = []
    for year in (2000, 2001):
        for i in range(4):
            rows.append(
                {
                    "row_id": f"{year}-{i}",
                    "year": year,
                    "date": pd.Timestamp(f"{year}-0{1 + i}-15"),
                    "tokens": 1_000,
                    "meeting_symbol": f"S/PV.{year}{i // 2}",
                    "speaker_group": "P5" if i < 2 else "E10",
                    "has_genocide": i == 0,
                    "n_genocide": 3 if i == 0 else 0,
                }
            )
    return pd.DataFrame(rows)


class TestPeriods:
    def test_year_gives_integers_not_periods(self, corpus):
        """A pandas Period does not survive json.dumps."""
        assert series.period(corpus, "year").tolist() == [2000] * 4 + [2001] * 4

    def test_quarter_gives_sortable_strings(self, corpus):
        """January, February and March land in Q1; April opens Q2."""
        assert series.period(corpus, "quarter").tolist()[:4] == [
            "2000Q1",
            "2000Q1",
            "2000Q1",
            "2000Q2",
        ]

    def test_an_unknown_frequency_is_refused(self, corpus):
        with pytest.raises(ValueError, match="unknown frequency"):
            series.period(corpus, "fortnight")


class TestColumns:
    def test_terms_registers_and_sets_each_have_their_prefix(self):
        assert series.columns_for("terms", "genocide") == ("has_genocide", "n_genocide")
        assert series.columns_for("registers", "legal") == (
            "has_register_legal",
            "n_register_legal",
        )

    def test_a_set_has_no_count_column(self):
        """A set is a union. Summing its members would count a speech saying
        both 'genocide' and 'war crimes' twice."""
        assert series.columns_for("sets", "rome_triad") == ("has_set_rome_triad", None)

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(ValueError, match="unknown measure kind"):
            series.columns_for("clusters", "x")


class TestMeasure:
    def test_rates_use_the_corpus_denominator_not_the_term(self, corpus):
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        out = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")

        assert out["speeches"].tolist() == [1, 1]
        assert out["occurrences"].tolist() == [3, 3]
        assert out["speech_rate"].tolist() == [0.25, 0.25]
        # 3 occurrences in 4,000 tokens = 75 per 100,000.
        assert out["token_rate"].tolist() == [75.0, 75.0]

    def test_a_set_reports_speeches_and_withholds_occurrences(self, corpus):
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        out = series.measure(corpus, periods, totals, "has_genocide", None)

        assert out["speech_rate"].tolist() == [0.25, 0.25]
        assert out["occurrences"].isna().all()
        assert out["token_rate"].isna().all()

    def test_a_period_with_no_hits_stays_in_the_series(self, corpus):
        """Dropping it would put a gap in the chart where a zero belongs."""
        corpus.loc[corpus["year"] == 2001, ["has_genocide", "n_genocide"]] = [False, 0]
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        out = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")

        assert out.index.tolist() == [2000, 2001]
        assert out["speeches"].tolist() == [1, 0]


class TestBreakdown:
    def test_each_category_divides_by_its_own_denominator(self, corpus):
        periods = series.period(corpus, "year")
        out = series.breakdown(corpus, periods, "speaker_group", "has_genocide", "n_genocide")

        p5 = out[(out["period"] == 2000) & (out["speaker_group"] == "P5")].iloc[0]
        e10 = out[(out["period"] == 2000) & (out["speaker_group"] == "E10")].iloc[0]
        assert (p5["held"], p5["speeches"], p5["speech_rate"]) == (2, 1, 0.5)
        assert (e10["held"], e10["speeches"], e10["speech_rate"]) == (2, 0, 0.0)

    def test_the_tail_folds_by_volume_not_by_hits(self, corpus):
        """Folding by term hits would promote a category that was mentioned once
        into the top table and drop a large one that was never mentioned."""
        corpus.loc[corpus.index[0], "speaker_group"] = "Rare"
        periods = series.period(corpus, "year")
        out = series.breakdown(
            corpus, periods, "speaker_group", "has_genocide", "n_genocide", top=1
        )
        assert set(out["speaker_group"]) == {"E10", "Other"}


class TestSplitPlan:
    def test_a_series_too_short_to_split_plans_nothing(self):
        assert len(series.plan_splits(5, min_size=3)) == 0

    def test_the_plan_covers_sub_intervals_not_just_the_whole_series(self):
        """The difference between this and classic binary segmentation. Without
        the inner intervals a bump is invisible."""
        plan = series.plan_splits(12, min_size=3)
        spans = {(int(a), int(b)) for a, b in zip(plan.starts, plan.stops, strict=True)}
        assert (0, 12) in spans
        assert (0, 6) in spans and (6, 12) in spans

    def test_every_planned_segment_respects_min_size(self):
        plan = series.plan_splits(20, min_size=4)
        assert (plan.left >= 4).all() and (plan.right >= 4).all()

    def test_a_long_series_falls_back_to_a_bounded_ladder(self):
        """Exhaustive enumeration is cubic. The cap keeps a 128-point quarterly
        series from costing more than the answer is worth."""
        plan = series.plan_splits(128, min_size=4, max_intervals=500)
        spans = {(int(a), int(b)) for a, b in zip(plan.starts, plan.stops, strict=True)}
        assert (0, 128) in spans
        assert len(spans) <= 500

    def test_planning_is_deterministic(self):
        """The permutation null is calibrated on the plan, so the plan cannot
        vary between the observed statistic and its own null."""
        first = series.plan_splits(24, min_size=4)
        second = series.plan_splits(24, min_size=4)
        assert np.array_equal(first.splits, second.splits)


class TestGains:
    def test_a_flat_series_gains_nothing(self):
        plan = series.plan_splits(20, min_size=4)
        assert series.best_split(np.ones(20), plan) == (-1, 0.0)

    def test_the_step_is_found_at_the_step(self):
        plan = series.plan_splits(20, min_size=3)
        at, gain = series.best_split(np.array([0.0] * 10 + [5.0] * 10), plan)
        assert at == 10
        assert gain > 0

    def test_gain_matches_the_residual_sums_it_claims_to_remove(self):
        """The vectorised form is an algebraic identity, not an approximation."""
        values = np.array([1.0, 1.0, 1.0, 4.0, 4.0, 4.0])
        plan = series.plan_splits(6, min_size=3)

        def rss(chunk):
            return float(((chunk - chunk.mean()) ** 2).sum())

        at, gain = series.best_split(values, plan)
        assert gain == pytest.approx(rss(values) - rss(values[:at]) - rss(values[at:]))

    def test_a_plan_for_another_length_is_refused(self):
        with pytest.raises(ValueError, match="values against a plan"):
            series.gains(np.ones(10), series.plan_splits(20, min_size=4))


class TestChangePoints:
    def test_a_clean_step_is_dated_and_described(self):
        values = [1.0] * 16 + [6.0] * 16
        breaks = series.change_points(values, YEARS, trials=200)

        assert [b.label for b in breaks] == ["2008"]
        assert breaks[0].before == pytest.approx(1.0)
        assert breaks[0].after == pytest.approx(6.0)
        assert breaks[0].ratio == pytest.approx(6.0)

    def test_pure_noise_yields_nothing(self):
        noise = np.random.default_rng(7).normal(size=32)
        assert series.change_points(noise, YEARS, trials=500) == []

    def test_a_constant_series_yields_nothing(self):
        assert series.change_points([2.0] * 32, YEARS, trials=200) == []

    def test_a_bump_is_found_at_both_of_its_edges(self):
        """The case classic binary segmentation misses. A series that rises and
        falls back has no informative split of the whole, so a whole-segment
        search finds nothing and never recurses; scanning sub-intervals finds
        both edges. This corpus is bump-shaped, so the distinction is not
        academic."""
        values = [1.0] * 11 + [5.0] * 10 + [1.0] * 11
        breaks = series.change_points(values, YEARS, trials=300)
        assert [b.label for b in breaks] == ["2003", "2013"]

    def test_a_monotone_two_step_is_found_in_order(self):
        values = [1.0] * 11 + [4.0] * 10 + [9.0] * 11
        breaks = series.change_points(values, YEARS, trials=300)
        assert [b.label for b in breaks] == ["2003", "2013"]

    def test_a_pure_trend_is_reported_as_a_break(self):
        """Not a bug, a documented limitation: the permutation null is
        'these values in no order', which a monotone ramp violates without any
        regime change. The artefact ships this caveat next to the numbers."""
        breaks = series.change_points(np.arange(32.0), YEARS, trials=300)
        assert breaks, "the ramp is expected to trip the test — see the caveat"

    def test_the_smallest_p_value_is_bounded_by_the_trial_count(self):
        """A permutation test cannot report zero; 1/(trials+1) is the floor."""
        breaks = series.change_points([1.0] * 16 + [99.0] * 16, YEARS, trials=99)
        assert breaks[0].p_value == pytest.approx(1 / 100)

    def test_the_same_seed_gives_the_same_answer(self):
        values = [1.0] * 16 + [3.0] * 16
        first = series.change_points(values, YEARS, trials=200, seed=1)
        second = series.change_points(values, YEARS, trials=200, seed=1)
        assert [b.as_dict() for b in first] == [b.as_dict() for b in second]

    def test_min_size_keeps_breaks_off_the_ends(self):
        """A break in the second year of a 32-year series is an outlier, not a
        regime. min_size is what stops one being reported as one."""
        values = [9.0] + [1.0] * 31
        assert series.change_points(values, YEARS, min_size=4, trials=300) == []

    def test_mismatched_labels_are_refused(self):
        with pytest.raises(ValueError, match="values against"):
            series.change_points([1.0, 2.0, 3.0], ["a", "b"])
