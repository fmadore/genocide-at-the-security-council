import numpy as np
import pandas as pd
import pytest
from lib import block_lexical, keyness, lexical


def test_meeting_blocks_keep_the_full_vocabulary_denominator():
    matrix = keyness.build(pd.Series(["peace peace war", "war today", "peace"] ))
    frame = pd.DataFrame({"meeting_symbol": ["m", "m", "n"]})
    result = block_lexical.blocks(matrix, frame, np.array([0, 1, 2]), ["peace"])
    np.testing.assert_array_equal(result["m"], [2, 5])
    np.testing.assert_array_equal(result["n"], [1, 1])


def test_shared_meeting_deletion_matches_direct_recount():
    a = {"m": np.array([4, 10]), "n": np.array([10, 30]), "o": np.array([2, 20])}
    b = {"m": np.array([1, 20]), "n": np.array([3, 30]), "o": np.array([1, 10])}
    row = block_lexical.influence(a, b, ["peace"])[0]
    effects = []
    for excluded in a:
        left = sum((v for k, v in a.items() if k != excluded))
        right = sum((v for k, v in b.items() if k != excluded))
        effects.append(lexical.log_ratio(left[0], right[0], left[1], right[1]))
    assert row["loo_min"] == pytest.approx(min(effects))
    assert row["loo_max"] == pytest.approx(max(effects))
    assert row["valid_deletions"] == 3
