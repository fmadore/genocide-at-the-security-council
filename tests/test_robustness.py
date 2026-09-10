"""Check meeting deletion against literal speech removal, including shared meetings."""

from collections import Counter

import pytest
from lib import lexical, robustness


def test_deletions_equal_literal_recount():
    targets = [Counter(war=10, peace=3), Counter(war=2, peace=8), Counter(peace=4)]
    controls = [Counter(war=1, peace=9), Counter(war=8, peace=2)]
    meetings = [["A", "A", "B"], ["A", "C"]]
    rows, deletions = robustness.meeting_influence(targets, controls, *meetings, ["war", "peace"])
    assert len(deletions) == 3
    for row in rows:
        arms = []
        for documents, names in zip([targets, controls], meetings, strict=True):
            counts = Counter()
            for document, name in zip(documents, names, strict=True):
                if name != row["meeting"]:
                    counts.update(document)
            arms.append(counts)
        a, b = [arm[row["word"]] for arm in arms]
        sizes = [sum(arm.values()) for arm in arms]
        assert row["target"] == a
        assert row["control"] == b
        assert row["log_ratio"] == pytest.approx(lexical.log_ratio(a, b, *sizes))
        assert row["eligible"] == (a >= 5 and abs(lexical.log_likelihood(a, b, *sizes)) >= 10.83)


def test_empty_arm_is_excluded_and_absent_word_is_null():
    rows, deletions = robustness.meeting_influence(
        [Counter(war=5), Counter(peace=5)], [Counter(peace=5)],
        ["A", "B"], ["B"], ["war"],
    )
    assert len(rows) == 1
    assert rows[0]["log_ratio"] is None
    assert not rows[0]["eligible"]
    assert deletions[1]["exclusion"] == "empty arm after deletion"


@pytest.mark.parametrize("meeting", [None, "", "  "])
def test_missing_meeting_refused(meeting):
    with pytest.raises(ValueError, match="meeting symbol"):
        robustness.meeting_influence([Counter(war=5)], [], [meeting], [], ["war"])


def test_misaligned_input_refused():
    with pytest.raises(ValueError):
        robustness.meeting_influence([Counter(war=5)], [], [], [], ["war"])


def test_legacy_rule_preserves_actual_regression():
    text = "'genocide' R2P secretary-general"
    assert robustness.LEGACY_TOKEN_RE.findall(text.lower()) == ["genocide'", "r", "p", "secretary-general"]
    assert lexical.TOKEN_RE.findall(text.lower()) == ["genocide", "r2p", "secretary-general"]


def test_tokenizer_outer_join_does_not_invent_missing_ranks():
    rows = robustness.tokenizer_comparison(
        [{"word": "genocide", "log_ratio": 3}],
        [{"word": "genocide'", "log_ratio": 4}],
    )
    assert rows[0]["legacy_rank"] is None
    assert rows[1]["current_rank"] is None
    assert rows[1]["legacy_rank"] == 1


def test_summary_counts_undefined_effects_and_sign_reversals():
    primary = [{"word": "war", "target": 20, "reference": 10}]
    effects = [
        {"word": "war", "meeting": "A", "log_ratio": None, "eligible": False},
        {"word": "war", "meeting": "B", "log_ratio": -1, "eligible": True},
        {"word": "war", "meeting": "C", "log_ratio": 2, "eligible": True},
    ]
    row = robustness.influence_summary(primary, effects, [100, 100])[0]
    assert row["valid_deletions"] == 3
    assert row["defined_effects"] == row["eligible_deletions"] == 2
    assert row["sign_reversals"] == 1
    assert row["largest_change_meeting"] == "B"
    assert (row["loo_min"], row["loo_max"]) == (-1, 2)
    empty = robustness.influence_summary(primary, [], [100, 100])[0]
    assert empty["loo_min"] is None
    assert empty["largest_change_meeting"] is None
