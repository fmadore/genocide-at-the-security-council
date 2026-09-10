from collections import Counter

import numpy as np
import pytest
from lib import uncertainty


def test_shared_meeting_weights_preserve_constant_rate_ratio():
    a = {str(i): np.array([2 * (i + 1), 100 * (i + 1)]) for i in range(20)}
    b = {str(i): np.array([i + 1, 100 * (i + 1)]) for i in range(20)}
    row = uncertainty.bootstrap_ratios(a, b, ["word"], repetitions=200)[0]
    assert row["low"] == pytest.approx(1)
    assert row["high"] == pytest.approx(1)
    assert row["valid_repetitions"] == 200


def test_splitting_speeches_does_not_split_resampling_units():
    whole = uncertainty.meeting_blocks([Counter(word=2, other=4)], ["A"], ["word"])
    split = uncertainty.meeting_blocks([Counter(word=1, other=2)] * 2, ["A"] * 2, ["word"])
    np.testing.assert_array_equal(whole["A"], split["A"])


def test_structural_zero_has_no_artificial_half_count_interval():
    a = {str(i): np.array([2, 100]) for i in range(20)}
    b = {str(i): np.array([0, 100]) for i in range(20)}
    row = uncertainty.bootstrap_ratios(a, b, ["word"], repetitions=200)[0]
    assert row["low"] is row["high"] is None
    assert "support" in row["withheld_because"]


def test_bootstrap_reproducible_and_rejects_invalid_counts():
    a = {str(i): np.array([i + 1, 100]) for i in range(20)}
    b = {str(i): np.array([20 - i, 100]) for i in range(20)}
    assert uncertainty.bootstrap_ratios(a, b, ["w"], repetitions=200) == uncertainty.bootstrap_ratios(a, b, ["w"], repetitions=200)
    a["0"] = np.array([101, 100])
    with pytest.raises(ValueError, match="invalid"):
        uncertainty.bootstrap_ratios(a, b, ["w"], repetitions=200)
