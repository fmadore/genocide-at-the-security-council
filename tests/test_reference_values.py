"""The interval and the keyness statistic, against values computed elsewhere.

Every other test of these two checks a property — the interval brackets the
rate, the statistic grows with the difference — or rebuilds the formula it is
testing, which passes whenever the code agrees with itself. These hold them to
numbers that did not come from this repository.

**Wilson.** Newcombe (1998), "Two-sided confidence intervals for the single
proportion: comparison of seven methods", *Statistics in Medicine* 17:857-872,
Table I, method 3 (the score method without continuity correction), to the
four decimals the paper prints. Checked before they were written here against
`scipy.stats.binomtest(k, n).proportion_ci(method="wilson")` (SciPy 1.18.1)
and against the closed form with z from `statistics.NormalDist`; all three
agree to the last printed place.

**G².** The two-cell log-likelihood of Rayson and Garside (2000), "Comparing
corpora using frequency profiling", the form the UCREL calculator uses:
2 * (a ln(a / E1) + b ln(b / E2)), with E the counts expected from the pooled
rate. The values were computed with `scipy.stats.power_divergence(...,
lambda_="log-likelihood")` on the two cells, and every case was chosen so
that it also has a closed form, given beside it, that can be checked by hand.
"""

from __future__ import annotations

import math

import pytest
from lib import lexical, series

#: (successes, trials, low, high) from Newcombe (1998), Table I, method 3.
NEWCOMBE_WILSON = [
    (81, 263, 0.2553, 0.3662),
    (15, 148, 0.0624, 0.1605),
    (0, 20, 0.0000, 0.1611),
    (1, 29, 0.0061, 0.1718),
]


@pytest.mark.parametrize(("successes", "trials", "low", "high"), NEWCOMBE_WILSON)
def test_wilson_matches_newcombe_table_one(successes, trials, low, high) -> None:
    found_low, found_high = series.wilson_interval(successes, trials)
    # Half a unit in the fourth decimal, the precision the table is printed to.
    assert float(found_low) == pytest.approx(low, abs=5e-5)
    assert float(found_high) == pytest.approx(high, abs=5e-5)


@pytest.mark.parametrize(("successes", "trials", "low", "high"), NEWCOMBE_WILSON)
def test_wilson_mirrors_at_the_complement(successes, trials, low, high) -> None:
    """A share of failures has the same interval turned around, as the score
    method's symmetry in p and 1 - p says it must."""
    found_low, found_high = series.wilson_interval(trials - successes, trials)
    assert float(found_low) == pytest.approx(1 - high, abs=5e-5)
    assert float(found_high) == pytest.approx(1 - low, abs=5e-5)


def test_wilson_matches_scipy_to_full_precision() -> None:
    """The same four cases to twelve places, from SciPy's implementation."""
    scipy_values = {
        (81, 263): (0.2552885198782742, 0.36620957698280004),
        (15, 148): (0.06238639953073629, 0.16048724172330803),
        (0, 20): (0.0, 0.16112515805281935),
        (1, 29): (0.006113214292762667, 0.17175521879320282),
    }
    for (successes, trials), (low, high) in scipy_values.items():
        found_low, found_high = series.wilson_interval(successes, trials)
        assert float(found_low) == pytest.approx(low, abs=1e-12)
        assert float(found_high) == pytest.approx(high, abs=1e-12)


#: (a, b, target total, reference total, signed G², closed form).
G2_REFERENCE = [
    # E = (5, 10): 2 (10 ln 2 + 5 ln 1/2) = 10 ln 2.
    (10, 5, 1_000, 2_000, 6.931471805599453, 10 * math.log(2)),
    # Ten times the counts, ten times the statistic: 100 ln 2.
    (100, 50, 10_000, 20_000, 69.31471805599453, 100 * math.log(2)),
    # Absent from the reference: a / E1 = 100,500 / 500 = 201, so 6 ln 201.
    (3, 0, 500, 100_000, 31.819829448354454, 6 * math.log(201)),
    # Absent from the target, so negative: b / E2 = 1.01, so -80 ln 1.01.
    (0, 40, 10_000, 1_000_000, -0.7960264682534474, -80 * math.log(1.01)),
    # 05's matched keyness on the end-to-end corpus: 41 against none, 82 ln 2.
    (41, 0, 1_640, 1_640, 56.83806880591551, 82 * math.log(2)),
]


@pytest.mark.parametrize(("a", "b", "target", "reference", "value", "closed"), G2_REFERENCE)
def test_log_likelihood_matches_independent_values(a, b, target, reference, value, closed) -> None:
    assert value == pytest.approx(closed, rel=1e-12)
    assert lexical.log_likelihood(a, b, target, reference) == pytest.approx(value, rel=1e-12)


def test_equal_rates_carry_no_evidence() -> None:
    assert lexical.log_likelihood(7, 7, 1_000, 1_000) == pytest.approx(0.0, abs=1e-12)
    assert lexical.log_likelihood(0, 0, 1_000, 1_000) == 0.0


@pytest.mark.parametrize(
    ("a", "b", "target", "reference", "value"),
    [
        # (10 / 1,000) / (5 / 2,000) = 4.
        (10, 5, 1_000, 2_000, 2.0),
        # The half-occurrence floor: (3 / 500) / (0.5 / 100,000) = 1,200.
        (3, 0, 500, 100_000, math.log2(1_200)),
        # The same floor on the target side: (0.5 / 1,000,000) / (40 / 10,000).
        (0, 40, 1_000_000, 10_000, math.log2(1.25e-4)),
    ],
)
def test_log_ratio_is_the_log2_rate_ratio_with_a_half_floor(a, b, target, reference, value) -> None:
    assert lexical.log_ratio(a, b, target, reference) == pytest.approx(value, rel=1e-12)
