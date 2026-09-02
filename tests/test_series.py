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
                    # The denominator, and the codebook figure it is not:
                    # deliberately different, so a rate that divided by the
                    # wrong one would be visible in the arithmetic below.
                    "words": 1_000,
                    "tokens": 1_200,
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

    def test_month_gives_sortable_strings(self, corpus):
        """`YYYY-MM` sorts chronologically as text, which `2000-9` would not."""
        assert series.period(corpus, "month").tolist()[:4] == [
            "2000-01",
            "2000-02",
            "2000-03",
            "2000-04",
        ]

    def test_an_unknown_frequency_is_refused(self, corpus):
        with pytest.raises(ValueError, match="unknown frequency"):
            series.period(corpus, "fortnight")

    def test_a_calendar_month_is_not_reachable_as_a_frequency(self, corpus):
        """Pooling thirty-two Junes has a different denominator from any month.
        Keeping it out of the frequency vocabulary is what stops a caller getting
        it by asking for a period and drawing the two on one scale."""
        with pytest.raises(ValueError, match="unknown frequency"):
            series.period(corpus, "month_of_year")
        assert series.month_of_year(corpus).tolist()[:4] == [1, 2, 3, 4]


class TestMonthGrid:
    def test_the_grid_is_every_month_between_two_years(self):
        grid = series.month_grid(1992, 1993)
        assert len(grid) == 24
        assert grid[0] == "1992-01"
        assert grid[11] == "1992-12"
        assert grid[-1] == "1993-12"

    def test_the_grid_sorts_as_text(self):
        grid = series.month_grid(1999, 2001)
        assert grid == sorted(grid)

    def test_a_backwards_range_is_refused(self):
        with pytest.raises(ValueError, match="before"):
            series.month_grid(2001, 2000)

    def test_a_month_nobody_spoke_in_becomes_a_row_of_zeros(self, corpus):
        """Not an absent key. On a heatmap a missing cell is drawn white, and
        white is the colour a zero has."""
        periods = series.period(corpus, "month")
        totals = series.denominators(corpus, periods, index=series.month_grid(2000, 2001))

        assert len(totals) == 24
        assert int(totals.loc["2000-01", "speeches"]) == 1
        assert int(totals.loc["2000-07", "speeches"]) == 0
        assert int(totals.loc["2000-07", "words"]) == 0


class TestWithholding:
    """A rate a denominator cannot carry is withheld, and its count is not."""

    def frame(self, corpus):
        periods = series.period(corpus, "month")
        totals = series.denominators(corpus, periods, index=series.month_grid(2000, 2001))
        measured = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")
        return measured, totals

    def test_a_short_period_keeps_its_counts_and_loses_its_rates(self, corpus):
        measured, totals = self.frame(corpus)
        out = series.withhold_below(measured, totals["speeches"], minimum=100)

        assert not out["sufficient"].any()
        assert out["speech_rate"].isna().all()
        assert out["token_rate"].isna().all()
        # The counts are facts about the record and survive the gate.
        assert int(out.loc["2000-01", "speeches"]) == 1
        assert int(out.loc["2000-01", "occurrences"]) == 3

    def test_a_period_that_clears_the_minimum_keeps_its_rates(self, corpus):
        measured, totals = self.frame(corpus)
        out = series.withhold_below(measured, totals["speeches"], minimum=1)

        assert out.loc["2000-01", "sufficient"]
        assert out.loc["2000-01", "speech_rate"] == 1.0
        # A month with no speeches at all never clears a minimum of one.
        assert not out.loc["2000-07", "sufficient"]

    def test_sufficient_is_written_for_every_row(self, corpus):
        """A consumer tests a flag rather than inferring the gate from a null,
        which is the difference between 'withheld' and 'the pipeline lost it'."""
        measured, totals = self.frame(corpus)
        out = series.withhold_below(measured, totals["speeches"], minimum=1)
        assert out["sufficient"].notna().all()
        assert len(out) == 24

    def test_a_set_has_no_token_rate_to_withhold(self, corpus):
        """`token_rate` is already NA for a union; withholding must not invent
        the column or fail for want of it."""
        periods = series.period(corpus, "month")
        totals = series.denominators(corpus, periods)
        measured = series.measure(corpus, periods, totals, "has_genocide", None)
        out = series.withhold_below(measured, totals["speeches"], minimum=1)
        assert out["token_rate"].isna().all()
        assert out["speech_rate"].notna().any()


class TestZeroCeiling:
    def test_the_minimum_is_derived_from_the_corpus_not_declared(self):
        """At the corpus prevalence a zero only means 'quieter than the Council'
        from about 96 speeches, which is where both minimums come from."""
        assert series.informative_zero_minimum(0.0308) == 96

    def test_actors_re_exports_rather_than_redefines(self):
        """Two implementations of one threshold would eventually disagree, and
        nothing in the output would say which was wrong."""
        from lib import actors

        assert actors.informative_zero_minimum is series.informative_zero_minimum
        assert actors.zero_ceiling is series.zero_ceiling


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
    def test_the_token_rate_divides_by_words_and_not_by_codebook_tokens(self, corpus):
        """§3.3 of the review of 1 September 2026. The codebook counts
        punctuation and numbers as tokens, so dividing by them put every "per
        100,000 words" figure below the label it carried. The fixture makes the
        two denominators different on purpose: 4,000 words against 4,800
        tokens, so 3 occurrences read 75 per 100,000 and never 62.5."""
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)

        assert totals["words"].tolist() == [4_000, 4_000]
        assert totals["tokens"].tolist() == [4_800, 4_800]
        out = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")
        assert out["token_rate"].tolist() == [75.0, 75.0]

    def test_the_codebook_count_is_carried_beside_the_denominator(self, corpus):
        """Kept rather than dropped: a reader comparing a rate here against the
        dataset's own documentation is entitled to both numbers."""
        totals = series.denominators(corpus, series.period(corpus, "year"))
        assert {"speeches", "words", "tokens", "meetings"} <= set(totals.columns)

    def test_rates_use_the_corpus_denominator_not_the_term(self, corpus):
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        out = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")

        assert out["speeches"].tolist() == [1, 1]
        assert out["occurrences"].tolist() == [3, 3]
        assert out["speech_rate"].tolist() == [0.25, 0.25]
        # 3 occurrences in 4,000 words = 75 per 100,000.
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

    def test_reported_means_belong_to_the_interval_that_won(self):
        values = [0.0] * 8 + [5.0] * 8 + [0.0] * 16
        found = series.change_points(values, YEARS, trials=200)
        assert found
        first = found[0]
        assert first.before == pytest.approx(
            np.mean(values[first.interval_start : first.index])
        )
        assert first.after == pytest.approx(
            np.mean(values[first.index : first.interval_stop])
        )


class TestRateChangePoint:
    def test_binomial_scan_uses_the_varying_denominators(self):
        exposure = np.asarray([100] * 16 + [1_000] * 16)
        counts = np.asarray([5] * 16 + [200] * 16)
        found = series.rate_change_point(
            counts, exposure, YEARS, family="binomial", trials=199, seed=4
        )
        assert found is not None
        assert found["label"] == "2008"
        assert found["accepted"] is True
        assert found["before"] == pytest.approx(0.05)
        assert found["after"] == pytest.approx(0.2)

    def test_poisson_scan_uses_token_exposure(self):
        exposure = np.asarray([100_000] * 32)
        counts = np.asarray([2] * 16 + [20] * 16)
        found = series.rate_change_point(
            counts, exposure, YEARS, family="poisson", trials=199, seed=5
        )
        assert found is not None
        assert found["label"] == "2008"
        assert found["accepted"] is True

    def test_constant_rate_with_growing_exposure_is_not_a_change(self):
        exposure = np.arange(100, 3_300, 100)
        counts = exposure // 20
        found = series.rate_change_point(
            counts, exposure, YEARS, family="binomial", trials=199, seed=6
        )
        assert found is None or found["accepted"] is False

    def test_binomial_counts_cannot_exceed_trials(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            series.rate_change_point(
                [2] * 8,
                [1] * 8,
                range(8),
                family="binomial",
                min_size=2,
                trials=10,
            )


class TestWilsonInterval:
    def test_the_interval_brackets_the_rate_and_stays_in_range(self):
        low, high = series.wilson_interval([0, 12, 60], [60, 60, 60])
        assert low[0] == 0.0 and high[2] == 1.0
        assert 0.0 < low[1] < 0.2 < high[1] < 1.0
        # Wald on 12/60 would give ±0.101; Wilson is asymmetric around 0.2.
        assert (0.2 - low[1]) < (high[1] - 0.2)

    def test_it_is_the_interval_the_segment_rates_already_used(self):
        left, right = series._rate_interval(12, 60, "binomial")
        low, high = series.wilson_interval(12, 60)
        assert (left, right) == pytest.approx((float(low), float(high)))

    def test_a_share_of_nothing_has_no_interval(self):
        low, high = series.wilson_interval([0], [0])
        assert np.isnan(low[0]) and np.isnan(high[0])

    def test_more_speeches_give_a_narrower_interval(self):
        low, high = series.wilson_interval([3, 300], [100, 10_000])
        assert (high[1] - low[1]) < (high[0] - low[0])

    def test_measure_carries_the_bounds_and_withholding_blanks_them(self, corpus):
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        frame = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")
        assert list(frame.columns[:4]) == [
            "speeches",
            "speech_rate",
            "speech_rate_low",
            "speech_rate_high",
        ]
        assert (frame["speech_rate_low"] <= frame["speech_rate"]).all()
        assert (frame["speech_rate"] <= frame["speech_rate_high"]).all()
        held = series.withhold_below(frame, totals["speeches"], minimum=5)
        assert held["speech_rate_low"].isna().all()
        assert held["speech_rate_high"].isna().all()
        assert (held["speeches"] == frame["speeches"]).all()

    def test_a_breakdown_row_carries_its_own_bounds(self, corpus):
        periods = series.period(corpus, "year")
        frame = series.breakdown(corpus, periods, "speaker_group", "has_genocide", "n_genocide")
        p5 = frame[frame["speaker_group"] == "P5"].iloc[0]
        low, high = series.wilson_interval(p5["speeches"], p5["held"])
        assert p5["speech_rate_low"] == pytest.approx(float(low))
        assert p5["speech_rate_high"] == pytest.approx(float(high))


class TestMeetingBlocks:
    def test_a_block_is_a_meeting_with_its_speeches_and_its_hits(self, corpus):
        periods = series.period(corpus, "year")
        blocks = series.meeting_blocks(corpus, periods, "has_genocide", None)
        assert len(blocks) == 4  # two meetings a year, two years
        assert blocks["exposure"].tolist() == [2, 2, 2, 2]
        assert blocks["count"].tolist() == [1, 0, 1, 0]
        assert blocks["period"].tolist() == [2000, 2000, 2001, 2001]

    def test_token_exposure_sums_the_meeting(self, corpus):
        periods = series.period(corpus, "year")
        blocks = series.meeting_blocks(corpus, periods, "n_genocide", "words")
        assert blocks["exposure"].tolist() == [2_000] * 4
        assert blocks["count"].tolist() == [3, 0, 3, 0]

    def test_blocks_add_back_up_to_the_series(self, corpus):
        periods = series.period(corpus, "year")
        totals = series.denominators(corpus, periods)
        frame = series.measure(corpus, periods, totals, "has_genocide", "n_genocide")
        blocks = series.meeting_blocks(corpus, periods, "has_genocide", None)
        summed = blocks.groupby("period")[["count", "exposure"]].sum()
        assert summed["count"].tolist() == frame["speeches"].tolist()
        assert summed["exposure"].tolist() == totals["speeches"].tolist()


def _clustered_corpus(dense_years: tuple[int, ...], rng: np.random.Generator):
    """32 years x 10 meetings x 20 speeches; a dense meeting says the word in
    15 of its 20 speeches, a plain one in 0 or 1. The dense meetings sit in
    `dense_years`, two per year, so the word clusters into debates rather than
    being spread thinly over the year."""
    rows = []
    for year_index in range(32):
        for meeting in range(10):
            dense = year_index in dense_years and meeting < 2
            hits = 15 if dense else int(rng.integers(0, 2))
            rows.append(
                {"period": year_index, "count": hits, "exposure": 20, "meeting": meeting}
            )
    blocks = pd.DataFrame(rows)
    aggregated = blocks.groupby("period")[["count", "exposure"]].sum()
    return blocks, aggregated["count"].to_numpy(), aggregated["exposure"].to_numpy()


class TestBlockNull:
    def test_the_block_null_is_harder_to_clear_when_the_word_clusters(self):
        blocks, counts, exposure = _clustered_corpus((12, 13, 14, 15), np.random.default_rng(1))
        found = series.rate_change_point(
            counts, exposure, YEARS, family="binomial", trials=399, seed=7, blocks=blocks
        )
        assert found is not None
        assert found["null"] == series.NULL_MEETING_BLOCK
        assert found["blocks"] == 320
        # Same statistic, same split; only the calibration differs, and the
        # clustering can only make the observed split easier to reach by chance.
        assert found["p_value"] >= found["p_value_independent"]
        assert found["p_value_independent"] == pytest.approx(1 / 400)

    def test_without_blocks_the_published_p_is_the_independent_one(self):
        _, counts, exposure = _clustered_corpus((12, 13, 14, 15), np.random.default_rng(1))
        found = series.rate_change_point(
            counts, exposure, YEARS, family="binomial", trials=199, seed=7
        )
        assert found is not None
        assert found["null"] == series.NULL_INDEPENDENT
        assert found["blocks"] is None
        assert found["p_value"] == found["p_value_independent"]

    def test_a_genuine_level_shift_survives_the_block_null(self):
        # Every meeting after the split carries more of the word: the shift is
        # in the register, not in one debate, and permuting meetings cannot
        # reproduce it.
        rows = [
            {"period": y, "count": 6 if y >= 16 else 1, "exposure": 20, "meeting": m}
            for y in range(32)
            for m in range(10)
        ]
        blocks = pd.DataFrame(rows)
        aggregated = blocks.groupby("period")[["count", "exposure"]].sum()
        found = series.rate_change_point(
            aggregated["count"].to_numpy(),
            aggregated["exposure"].to_numpy(),
            YEARS,
            family="binomial",
            trials=199,
            seed=3,
            blocks=blocks,
        )
        assert found is not None
        assert found["label"] == "2008"
        assert found["accepted"] is True
        assert found["p_value"] == pytest.approx(1 / 200)

    def test_the_same_seed_gives_the_same_block_p(self):
        blocks, counts, exposure = _clustered_corpus((5, 6, 7, 8), np.random.default_rng(2))
        run = lambda: series.rate_change_point(  # noqa: E731
            counts, exposure, YEARS, family="binomial", trials=99, seed=11, blocks=blocks
        )
        assert run() == run()

    def test_blocks_that_do_not_add_up_are_refused(self):
        blocks, counts, exposure = _clustered_corpus((5, 6, 7, 8), np.random.default_rng(2))
        with pytest.raises(ValueError, match="do not add up"):
            series.rate_change_point(
                counts + 1, exposure, YEARS, family="binomial", trials=9, blocks=blocks
            )

    def test_a_block_outside_the_series_is_refused(self):
        blocks, counts, exposure = _clustered_corpus((5, 6, 7, 8), np.random.default_rng(2))
        astray = blocks.copy()
        astray.loc[0, "period"] = 40
        with pytest.raises(ValueError, match="fall in a period"):
            series.rate_change_point(
                counts, exposure, YEARS, family="binomial", trials=9, blocks=astray
            )

    def test_poisson_blocks_carry_token_exposure(self):
        rows = [
            {"period": y, "count": 3 if y >= 16 else 0, "exposure": 5_000, "meeting": m}
            for y in range(32)
            for m in range(6)
        ]
        blocks = pd.DataFrame(rows)
        aggregated = blocks.groupby("period")[["count", "exposure"]].sum()
        found = series.rate_change_point(
            aggregated["count"].to_numpy(),
            aggregated["exposure"].to_numpy(),
            YEARS,
            family="poisson",
            trials=199,
            seed=5,
            blocks=blocks,
        )
        assert found is not None
        assert found["label"] == "2008"
        assert found["accepted"] is True
