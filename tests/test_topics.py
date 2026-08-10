"""The topic comparison's evaluation machinery.

The models themselves need scikit-learn and umap-learn, which live in
`requirements-cluster.txt` and are installed only on the cluster. What is tested here
is everything a reader would use to decide whether to believe a topic — the
stability index, the coherence score, the topic labelling and the sampling — all
of which is written in numpy precisely so that it can be checked anywhere.

The statistics are checked against values worked out by hand rather than against
the library that would have provided them, because "it agrees with itself" is not
a test.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from lib import topics

# --- Adjusted Rand index ---------------------------------------------------


def test_identical_labellings_score_one() -> None:
    labels = np.array([0, 0, 1, 1, 2, 2])
    assert topics.adjusted_rand(labels, labels) == pytest.approx(1.0)


def test_relabelling_does_not_change_the_score() -> None:
    """The index compares partitions, not label names."""
    a = np.array([0, 0, 1, 1, 2, 2])
    b = np.array([7, 7, 3, 3, 5, 5])
    assert topics.adjusted_rand(a, b) == pytest.approx(1.0)


def test_a_split_cluster_scores_below_one() -> None:
    a = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    b = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    score = topics.adjusted_rand(a, b)
    assert 0.0 < score < 1.0


def test_worked_example() -> None:
    """Two labellings of six items, computed by hand.

    The contingency table is [[2, 1, 0], [0, 1, 2]], so the index term is
    C(2,2) + C(2,2) = 2. Row totals 3/3 give 3 + 3 = 6; column totals 2/2/2 give
    1 + 1 + 1 = 3. With C(6,2) = 15 pairs in total:
    expected = 6*3/15 = 1.2, maximum = (6+3)/2 = 4.5,
    ARI = (2 - 1.2) / (4.5 - 1.2) = 0.2424...
    """
    a = np.array([0, 0, 0, 1, 1, 1])
    b = np.array([0, 0, 1, 1, 2, 2])
    assert topics.adjusted_rand(a, b) == pytest.approx((2 - 1.2) / (4.5 - 1.2), abs=1e-9)


def test_unassigned_counts_as_a_label() -> None:
    """Two runs agreeing that a document is noise agree about that document."""
    a = np.array([topics.UNASSIGNED, topics.UNASSIGNED, 0, 0])
    b = np.array([topics.UNASSIGNED, topics.UNASSIGNED, 5, 5])
    assert topics.adjusted_rand(a, b) == pytest.approx(1.0)


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="differ in length"):
        topics.adjusted_rand(np.array([0, 1]), np.array([0, 1, 1]))


# --- Coherence -------------------------------------------------------------


def test_words_that_always_co_occur_score_high() -> None:
    documents = [["war", "crimes", "filler"], ["war", "crimes"], ["war", "crimes", "other"]]
    result = topics.npmi_coherence({0: [("war", 1.0), ("crimes", 1.0)]}, documents)
    assert result["per_topic"]["0"] > 0.4


def test_words_that_never_co_occur_score_low() -> None:
    documents = [["war"], ["crimes"], ["war"], ["crimes"]]
    result = topics.npmi_coherence({0: [("war", 1.0), ("crimes", 1.0)]}, documents)
    assert result["per_topic"]["0"] < 0.0


def test_coherence_is_a_single_pair_worked_by_hand() -> None:
    """Four documents, two of which contain both words.

    p(joint) = (2+1)/4, p(a) = p(b) = (3+1)/4 after +1 smoothing.
    npmi = log(0.75 / 1.0) / -log(0.75)
    """
    documents = [["a", "b"], ["a", "b"], ["a"], ["b"]]
    expected = math.log(0.75 / (1.0 * 1.0)) / -math.log(0.75)
    result = topics.npmi_coherence({0: [("a", 1.0), ("b", 1.0)]}, documents)
    assert result["per_topic"]["0"] == pytest.approx(round(expected, 4), abs=1e-4)


def test_coherence_of_nothing_is_not_an_error() -> None:
    assert topics.npmi_coherence({}, [["a"]])["mean"] == 0.0


# --- Topic labelling -------------------------------------------------------


def test_ctfidf_prefers_the_distinguishing_word() -> None:
    """A word in every topic must not outrank one specific to this topic."""
    documents = [
        ["council", "council", "rwanda", "rwanda", "rwanda"],
        ["council", "council", "rwanda", "rwanda", "rwanda"],
        ["council", "council", "bosnia", "bosnia", "bosnia"],
        ["council", "council", "bosnia", "bosnia", "bosnia"],
    ]
    words = topics.ctfidf(documents, np.array([0, 0, 1, 1]), top_n=2, min_count=1)
    assert words[0][0][0] == "rwanda"
    assert words[1][0][0] == "bosnia"


def test_ctfidf_ignores_unassigned_documents() -> None:
    documents = [["a", "a"], ["b", "b"], ["zzz", "zzz"]]
    words = topics.ctfidf(
        documents, np.array([0, 1, topics.UNASSIGNED]), top_n=5, min_count=1
    )
    assert "zzz" not in {w for block in words.values() for w, _ in block}


def test_ctfidf_of_an_all_unassigned_run_is_empty() -> None:
    assert topics.ctfidf([["a"]], np.array([topics.UNASSIGNED]), min_count=1) == {}


# --- The frozen sample -----------------------------------------------------


def frame(n: int = 400) -> pd.DataFrame:
    years = np.tile(np.arange(1992, 2024), n // 32 + 1)[:n]
    return pd.DataFrame(
        {
            "row_id": [f"r{i:04d}" for i in range(n)],
            "year": years,
            "tokens": np.where(np.arange(n) % 5 == 0, 10, 500),
        }
    )


def test_the_sample_is_reproducible() -> None:
    a = topics.frozen_sample(frame(), 100, seed=7)
    b = topics.frozen_sample(frame(), 100, seed=7)
    assert list(a["row_id"]) == list(b["row_id"])


def test_a_different_seed_gives_a_different_sample() -> None:
    a = topics.frozen_sample(frame(), 100, seed=7)
    b = topics.frozen_sample(frame(), 100, seed=8)
    assert list(a["row_id"]) != list(b["row_id"])


def test_row_order_does_not_change_the_sample() -> None:
    """A parquet's row order is an implementation detail, not an input."""
    straight = topics.frozen_sample(frame(), 100, seed=7)
    shuffled = topics.frozen_sample(
        frame().sample(frac=1.0, random_state=99).reset_index(drop=True), 100, seed=7
    )
    assert sorted(straight["row_id"]) == sorted(shuffled["row_id"])


def test_short_speeches_are_excluded() -> None:
    sample = topics.frozen_sample(frame(), 100, seed=7, min_tokens=100)
    assert (sample["tokens"] >= 100).all()


def test_every_period_is_represented() -> None:
    sample = topics.frozen_sample(frame(), 200, seed=7)
    assert set(topics.assign_period(sample["year"])) == {p[0] for p in topics.PERIODS}


def test_asking_for_more_than_exists_is_capped_not_padded() -> None:
    sample = topics.frozen_sample(frame(50), 10_000, seed=7)
    assert len(sample) <= 50
    assert sample["row_id"].is_unique


def test_a_corpus_of_only_short_speeches_fails_loudly() -> None:
    short = frame().assign(tokens=5)
    with pytest.raises(ValueError, match="tokens or more"):
        topics.frozen_sample(short, 10, seed=1)


# --- Periods and resampling ------------------------------------------------


def test_periods_do_not_overlap_or_leave_gaps() -> None:
    for (_, _, end), (_, start, _) in zip(topics.PERIODS, topics.PERIODS[1:], strict=False):
        assert start == end + 1


def test_a_year_outside_the_ranges_is_labelled_not_dropped() -> None:
    assert topics.assign_period(pd.Series([1980])).iloc[0] == "outside"


def test_resample_is_deterministic_and_smaller() -> None:
    index = np.arange(100)
    first = topics.resample(index, seed=3)
    assert np.array_equal(first, topics.resample(index, seed=3))
    assert len(first) == 90
    assert len(np.unique(first)) == len(first)


# --- The intrusion task ----------------------------------------------------


def words(n_topics: int) -> dict[int, list[tuple[str, float]]]:
    return {
        t: [(f"t{t}w{i}", 1.0 - i / 10) for i in range(6)] for t in range(n_topics)
    }


def test_the_intruder_comes_from_another_topic() -> None:
    tasks = topics.word_intrusion(words(4), seed=5)
    assert tasks
    for task in tasks:
        assert task["intruder"].startswith(f"t{task['intruder_from_topic']}")
        assert task["intruder_from_topic"] != task["topic"]


def test_the_recorded_position_locates_the_intruder() -> None:
    for task in topics.word_intrusion(words(4), seed=5):
        assert task["words"][task["intruder_position"] - 1] == task["intruder"]


def test_the_task_ships_unanswered() -> None:
    """The file is a task for a human. A verdict invented here would be the
    error docs/PLAN.md §1.1 forbids for the lexicon audit."""
    assert all(task["verdict"] == "" for task in topics.word_intrusion(words(3), seed=1))


def test_one_topic_cannot_produce_an_intrusion_task() -> None:
    assert topics.word_intrusion(words(1), seed=1) == []


# --- Tokenising ------------------------------------------------------------


def test_stopwords_are_removed_and_case_is_folded() -> None:
    assert topics.tokenise(["The Council MET"], frozenset({"the"})) == [["council", "met"]]


def test_digits_are_not_words() -> None:
    """Resolution numbers and dates are not vocabulary — same rule as 05."""
    assert topics.tokenise(["resolution 1325 adopted"], frozenset()) == [
        ["resolution", "adopted"]
    ]
