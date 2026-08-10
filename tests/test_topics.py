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

import importlib.util
import inspect
import json
import math
from pathlib import Path

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


def test_words_sharing_every_document_score_one_rather_than_dividing_by_zero() -> None:
    """Council boilerplate co-occurs everywhere; NPMI's limit there is +1."""
    documents = [["thank", "briefing"], ["thank", "briefing"], ["thank", "briefing"]]
    result = topics.npmi_coherence({0: [("thank", 1.0), ("briefing", 1.0)]}, documents)
    assert result["per_topic"]["0"] == pytest.approx(1.0)


def test_coherence_always_reports_the_same_keys() -> None:
    """A model that assigned nothing must not crash the note writer hours later."""
    empty = topics.npmi_coherence({}, [["a"]])
    scored = topics.npmi_coherence({0: [("a", 1.0), ("b", 1.0)]}, [["a", "b"], ["a"]])
    assert set(empty) == set(scored)


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


# --- The abstention threshold ----------------------------------------------


def test_the_dominant_share_can_never_fall_below_one_over_k() -> None:
    """The property that made a hard-coded 0.05 inert at k=25 and impossible at k=15."""
    rng = np.random.default_rng(0)
    for k in (5, 15, 25, 40):
        weights = rng.random((200, k))
        assert topics.dominant_share(weights).min() >= 1.0 / k - 1e-12


def test_a_document_with_no_weight_at_all_scores_zero_not_nan() -> None:
    shares = topics.dominant_share(np.array([[0.0, 0.0], [1.0, 3.0]]))
    assert shares[0] == 0.0
    assert shares[1] == pytest.approx(0.75)


def test_dealing_at_random_preserves_lengths_and_vocabulary() -> None:
    documents = [["a", "b", "c"], ["a", "a"], ["d", "e", "f", "g"]]
    dealt = topics.deal_at_random(documents, seed=3)
    assert [len(d) for d in dealt] == [3, 2, 4]
    assert sorted(w for d in dealt for w in d) == sorted(w for d in documents for w in d)


def test_dealing_at_random_is_reproducible_and_actually_shuffles() -> None:
    documents = [[f"w{i}"] * 4 for i in range(40)]
    assert topics.deal_at_random(documents, 5) == topics.deal_at_random(documents, 5)
    assert topics.deal_at_random(documents, 5) != documents


def test_calibration_reads_the_threshold_off_the_null_not_the_corpus() -> None:
    """The rule: assign only what beats what the model does on dealt-out words."""
    null_shares = np.linspace(0.1, 0.5, 101)
    observed = np.linspace(0.3, 0.9, 101)
    result = topics.calibrate(observed, null_shares, k=25, quantile=0.95)
    assert result["min_weight"] == pytest.approx(np.quantile(null_shares, 0.95), abs=1e-6)
    assert result["floor"] == pytest.approx(0.04)
    assert result["binds"] is True


def test_a_model_no_better_than_noise_is_reported_as_not_binding() -> None:
    """If the corpus concentrates no more than dealt-out words, say so."""
    shares = np.full(50, 0.25)
    result = topics.calibrate(shares, shares.copy(), k=4, quantile=0.95)
    assert result["floor"] == pytest.approx(0.25)
    assert result["binds"] is False


def test_the_curve_never_offers_a_threshold_below_the_floor() -> None:
    result = topics.calibrate(np.linspace(0.2, 0.9, 50), np.linspace(0.2, 0.4, 50), k=5)
    assert result["curve"]
    assert all(point["min_weight"] >= result["floor"] for point in result["curve"])


def test_the_curve_is_monotonic_in_the_threshold() -> None:
    result = topics.calibrate(np.linspace(0.1, 0.9, 200), np.linspace(0.1, 0.3, 200), k=25)
    shares = [point["unassigned_share"] for point in result["curve"]]
    assert shares == sorted(shares)


def test_threshold_for_hits_the_requested_abstention_rate() -> None:
    shares = np.linspace(0.0, 1.0, 1001)
    cut = topics.threshold_for(shares, 0.2)
    assert float((shares < cut).mean()) == pytest.approx(0.2, abs=0.01)


def test_asking_for_no_abstention_assigns_everything() -> None:
    shares = np.array([0.0, 0.4, 0.9])
    assert float((shares < topics.threshold_for(shares, 0.0)).mean()) == 0.0


def test_an_impossible_abstention_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        topics.threshold_for(np.array([0.5]), 1.0)


def test_relabelling_moves_the_line_without_refitting() -> None:
    weights = np.array([[9.0, 1.0], [6.0, 4.0], [5.1, 4.9]])
    documents = [["alpha", "alpha"], ["beta", "beta"], ["gamma", "gamma"]]
    model = topics.TopicModel(
        name="nmf",
        labels=np.array([0, 0, 0]),
        words={},
        params={"k": 2, "min_weight": 0.5},
        weights=weights,
    )
    strict = topics.relabel(model, documents, 0.8)
    assert strict.labels.tolist() == [0, topics.UNASSIGNED, topics.UNASSIGNED]
    assert strict.params["k"] == 2
    assert np.shares_memory(strict.weights, weights)


def test_relabelling_a_model_without_weights_fails_loudly() -> None:
    model = topics.TopicModel(name="embedding", labels=np.array([0, 1]), words={})
    with pytest.raises(ValueError, match="no document-topic weights"):
        topics.relabel(model, [["a"], ["b"]], 0.5)


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


# --- Neighbourhoods in the projection ---------------------------------------
#
# The diagnostic in scripts/07_topics.py exists to argue against reading the
# embedding space thematically, so its arithmetic has to be checkable without
# umap, without matplotlib and without a run. Everything below is worked out by
# hand or constructed so the right answer is exact.


def test_a_point_is_never_its_own_neighbour() -> None:
    """The error that would silently add 1/k to every purity figure."""
    points = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    found = topics.nearest_neighbours(points, 2)
    assert (found != np.arange(len(points))[:, None]).all()


def test_the_neighbours_are_the_near_ones_in_order() -> None:
    """Four points on a line at 0, 1, 4 and 9. The one at 4 is nearer the one at
    1 (distance 3) than the one at 0 (4) or at 9 (5), in that order."""
    points = np.array([[0.0], [1.0], [4.0], [9.0]])
    assert topics.nearest_neighbours(points, 2).tolist() == [[1, 2], [0, 2], [1, 0], [2, 1]]


def test_asking_for_more_neighbours_than_exist_returns_the_rest() -> None:
    """A smoke run, a thin period and a test fixture all reach this before a real
    sample does; an IndexError hours into a job is a poor way to find out."""
    points = np.array([[0.0], [1.0], [2.0]])
    found = topics.nearest_neighbours(points, 50)
    assert found.shape == (3, 2)
    assert sorted(found[0].tolist()) == [1, 2]


def test_one_point_has_no_neighbours_and_that_is_not_an_error() -> None:
    assert topics.nearest_neighbours(np.array([[0.0, 0.0]]), 3).shape == (1, 0)


def test_ties_are_broken_by_index_so_two_machines_agree() -> None:
    """Four points on a square: every neighbour distance ties, so the ordering is
    the sort's alone and must be the stable one."""
    square = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    assert topics.nearest_neighbours(square, 3)[0].tolist() == [1, 2, 3]


# --- Neighbourhood purity ---------------------------------------------------


def test_purity_is_one_when_every_neighbour_shares_the_attribute() -> None:
    neighbours = np.array([[1, 2], [0, 2], [0, 1]])
    result = topics.neighbourhood_purity(neighbours, ["France", "France", "France"])
    assert result["mean"] == pytest.approx(1.0)


def test_purity_is_zero_when_no_neighbour_shares_the_attribute() -> None:
    neighbours = np.array([[2, 3], [2, 3], [0, 1], [0, 1]])
    result = topics.neighbourhood_purity(neighbours, ["a", "a", "b", "b"])
    assert result["mean"] == pytest.approx(0.0)


def test_purity_over_the_whole_corpus_is_exactly_the_base_rate() -> None:
    """A neighbourhood of every other point is the unmixed definition of chance.

    Constructed rather than sampled: a shuffled set would converge to the base
    rate, and a test that converges is a test that fails one run in fifty.
    """
    values = ["a"] * 7 + ["b"] * 5 + ["c"] * 3
    n = len(values)
    everyone = np.array([[j for j in range(n) if j != i] for i in range(n)])
    result = topics.neighbourhood_purity(everyone, values)
    assert result["mean"] == pytest.approx(result["base_rate"], abs=1e-9)
    assert result["lift"] == pytest.approx(1.0)


def test_purity_worked_by_hand() -> None:
    """Five speeches, three by `a` and two by `b`, two neighbours each.

    Shares: 2/2, 1/2, 0/2, 1/2, 1/2 -> mean 2.5/5 = 0.5.
    Base rate: an `a` point has 2 of the other 4 sharing its value (0.5), a `b`
    point has 1 of 4 (0.25), so (3*0.5 + 2*0.25)/5 = 0.4.
    Lift 0.5 / 0.4 = 1.25.
    """
    neighbours = np.array([[1, 2], [0, 3], [3, 4], [4, 0], [3, 0]])
    result = topics.neighbourhood_purity(neighbours, ["a", "a", "a", "b", "b"])
    assert result["mean"] == pytest.approx(0.5)
    assert result["base_rate"] == pytest.approx(0.4)
    assert result["lift"] == pytest.approx(1.25)


def test_the_base_rate_falls_as_the_attribute_gets_finer() -> None:
    """Why the note reports lift and not the bare share: `period` has four values
    and `speaker` has thousands, and their raw purities are not comparable."""
    neighbours = np.array([[1, 2], [0, 2], [0, 1], [4, 5], [3, 5], [3, 4]])
    coarse = topics.neighbourhood_purity(neighbours, ["x", "x", "x", "y", "y", "y"])
    fine = topics.neighbourhood_purity(neighbours, list("abcdef"))
    assert coarse["base_rate"] > fine["base_rate"]
    assert fine["base_rate"] == pytest.approx(0.0)


def test_a_missing_value_is_a_category_and_is_counted() -> None:
    """1,115 speeches carry no named speaker. Dropping them would change the base
    rate's denominator without changing the purity, which is the one way to make
    this comparison lie."""
    neighbours = np.array([[1, 2], [0, 2], [0, 1]])
    result = topics.neighbourhood_purity(neighbours, [None, None, "France"])
    assert result["missing"] == 2
    assert result["distinct_values"] == 2


def test_purity_rejects_an_attribute_of_the_wrong_length() -> None:
    with pytest.raises(ValueError, match="different documents"):
        topics.neighbourhood_purity(np.array([[1], [0]]), ["a", "b", "c"])


# --- Agreement between the picture and the space that was clustered ---------


def test_neighbour_loss_is_zero_when_the_neighbourhoods_match() -> None:
    same = np.array([[1, 2], [0, 2], [0, 1]])
    assert topics.neighbour_loss(same, same.copy()) == pytest.approx(0.0)


def test_neighbour_loss_is_one_when_they_share_nothing() -> None:
    clustered = np.array([[1, 2], [2, 3]])
    projected = np.array([[4, 5], [5, 6]])
    assert topics.neighbour_loss(clustered, projected) == pytest.approx(1.0)


def test_neighbour_loss_ignores_the_order_within_a_neighbourhood() -> None:
    """Set membership only; rank order is what trustworthiness is for."""
    clustered = np.array([[1, 2, 3]])
    assert topics.neighbour_loss(clustered, np.array([[3, 2, 1]])) == pytest.approx(0.0)


def test_neighbour_loss_worked_by_hand() -> None:
    """Two points, three neighbours each, one shared in the first row and two in
    the second: (2/3 + 1/3) / 2 = 0.5 lost."""
    clustered = np.array([[1, 2, 3], [4, 5, 6]])
    projected = np.array([[1, 7, 8], [4, 5, 9]])
    assert topics.neighbour_loss(clustered, projected) == pytest.approx(0.5)


def test_a_projection_that_preserves_the_ordering_is_perfectly_trustworthy() -> None:
    rng = np.random.default_rng(11)
    space = rng.normal(size=(30, 4))
    assert topics.trustworthiness(space, space.copy(), 5) == pytest.approx(1.0)


def test_a_rescaled_projection_is_still_perfectly_trustworthy() -> None:
    """Trustworthiness is about rank, not distance: doubling every coordinate
    changes no neighbourhood and must change no score."""
    rng = np.random.default_rng(12)
    space = rng.normal(size=(30, 3))
    assert topics.trustworthiness(space, space * 7.0, 5) == pytest.approx(1.0)


def test_a_scrambled_projection_scores_far_lower() -> None:
    """Twelve points on a line, projected by a multiplicative shuffle that sends
    each point's true neighbours across the picture."""
    high = np.array([[float(i)] for i in range(12)])
    low = np.array([[float((i * 5) % 12)] for i in range(12)])
    assert topics.trustworthiness(high, low, 3) < 0.7
    assert topics.trustworthiness(high, high.copy(), 3) == pytest.approx(1.0)


def test_trustworthiness_worked_by_hand() -> None:
    """Six points, k = 1, every distance distinct so nothing depends on a tie.

    In the high space each point's single projected neighbour sits at high rank
    2, 3, 2, 5, 5 and 2, so the promotions (rank - k) are 1, 2, 1, 4, 4 and 1,
    summing to 13. With n = 6 and k = 1 the normaliser is
    n*k*(2n - 3k - 1) = 6*1*8 = 48, so T = 1 - 2*13/48 = 11/24.
    """
    high = np.array([[0.0], [1.0], [3.0], [7.0], [15.0], [31.0]])
    low = np.array([[0.0], [56.0], [11.0], [41.0], [23.0], [33.0]])
    assert topics.trustworthiness(high, low, 1) == pytest.approx(11 / 24, abs=1e-12)


def test_trustworthiness_clamps_k_rather_than_dividing_by_zero() -> None:
    """The normaliser vanishes at k = (2n-1)/3, which a default k of 25 passes
    for any sample under 38 points."""
    rng = np.random.default_rng(13)
    space = rng.normal(size=(6, 2))
    assert 0.0 <= topics.trustworthiness(space, space + 0.5, 25) <= 1.0


def test_trustworthiness_rejects_two_spaces_of_different_sizes() -> None:
    with pytest.raises(ValueError, match="different point counts"):
        topics.trustworthiness(np.zeros((4, 2)), np.zeros((5, 2)), 2)


def test_the_agreement_block_records_the_subsample_it_used() -> None:
    """docs/PLAN.md's rule against a silent approximation: if the measure ran on
    part of the sample, the artefact says so and says how much."""
    rng = np.random.default_rng(14)
    high = rng.normal(size=(60, 4))
    low = rng.normal(size=(60, 2))
    block = topics.projection_agreement(high, low, seed=3, k=5, max_points=20)
    assert block["subsampled"] is True
    assert block["points"] == 20
    assert block["sample_points"] == 60
    assert block["subsample_seed"] == 3
    assert block["dimensions"] == {"clustered": 4, "projected": 2}


def test_the_agreement_subsample_is_reproducible() -> None:
    rng = np.random.default_rng(15)
    high, low = rng.normal(size=(50, 3)), rng.normal(size=(50, 2))
    first = topics.projection_agreement(high, low, seed=9, k=4, max_points=20)
    second = topics.projection_agreement(high, low, seed=9, k=4, max_points=20)
    assert first == second


def test_no_subsample_is_reported_when_none_was_taken() -> None:
    rng = np.random.default_rng(16)
    high, low = rng.normal(size=(20, 3)), rng.normal(size=(20, 2))
    block = topics.projection_agreement(high, low, seed=9, k=4, max_points=500)
    assert block["subsampled"] is False
    assert block["subsample_seed"] is None
    assert block["points"] == 20


# --- The diagnostic payload, and what may not be in it ----------------------


def projection_pair(n: int = 40) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(17)
    return rng.normal(size=(n, 2)), rng.normal(size=(n, 5))


def test_the_diagnostic_reports_every_attribute_it_was_given() -> None:
    low, high = projection_pair()
    payload = topics.projection_diagnostic(
        low,
        high,
        {
            "country_org": ["France", "Rwanda"] * 20,
            "year": list(range(1992, 2032)),
            "embedding_topic": np.arange(40) % 4,
        },
        seed=5,
        k=6,
        max_points=40,
    )
    assert set(payload["purity"]) == {"country_org", "year", "embedding_topic"}
    assert payload["k"] == 6
    assert payload["points"] == 40


def test_the_diagnostic_reports_statistics_not_coordinates() -> None:
    """The guard that matters: nothing in the artefact is per-document, so there
    is no column here for anyone to join onto a speech and call a topic. A
    payload carrying 20,000 coordinates would be a map, whatever the note said.
    """
    low, high = projection_pair()
    payload = topics.projection_diagnostic(
        low, high, {"country_org": ["France", "Rwanda"] * 20}, seed=5, k=6, max_points=40
    )

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            assert len(value) != len(low), "the payload carries one entry per document"
            for item in value:
                walk(item)

    walk(payload)
    assert json.loads(json.dumps(payload))["points"] == 40


def test_the_diagnostic_carries_the_argument_it_belongs_to() -> None:
    """A file that travels away from the note must still say what it is for, and
    what it is evidence against."""
    low, high = projection_pair()
    payload = topics.projection_diagnostic(low, high, {}, seed=5, k=6, max_points=40)
    assert payload["diagnostic"] is True
    assert payload["release_artefact"] is False
    assert payload["clustered_for_labels"] is False
    assert "evidence" in payload["purpose"]
    assert "no topic label is derived" in payload["purpose"]


def test_the_diagnostic_rejects_two_spaces_of_different_sizes() -> None:
    with pytest.raises(ValueError, match="the projection has"):
        topics.projection_diagnostic(np.zeros((4, 2)), np.zeros((5, 5)), {}, seed=1)


# --- The projection never reaches a labelling path --------------------------


def body(function: object) -> str:
    """A function's source with its docstring removed.

    The guards below ask what the code does, and every one of these functions
    explains in prose that it does not cluster or label. Searching the docstring
    for the word would find the promise instead of the breach.
    """
    source = inspect.getsource(function)
    doc = inspect.getdoc(function)
    if doc:
        for line in doc.splitlines():
            source = source.replace(line.strip(), "")
    return source


def test_the_helper_reads_the_code_and_not_the_promise() -> None:
    """`body` is load-bearing for the two guards below, so it is checked too."""
    assert "clustering in the space built for a picture" not in body(topics.fit_embedding)
    assert "HDBSCAN(" in body(topics.fit_embedding)


def test_the_clustering_still_happens_in_five_dimensions() -> None:
    """docs/PLAN.md §4: clustering in the space built for a picture optimises for
    a picture. Adding the picture must not have quietly moved the clustering
    into it."""
    signature = inspect.signature(topics.fit_embedding)
    assert signature.parameters["components"].default == 5
    source = body(topics.fit_embedding)
    assert "n_components=components" in source
    assert "project_2d" not in source


def test_the_projection_is_fitted_in_two_dimensions_and_only_there() -> None:
    source = body(topics.project_2d)
    assert "n_components=2" in source
    assert "HDBSCAN" not in source


def test_no_label_is_derived_from_the_projection() -> None:
    """No function that touches the 2D coordinates may reach a clusterer or the
    labelling that names a topic. This is the property the whole diagnostic
    depends on, so it is asserted rather than left to the docstrings."""
    forbidden = ("ctfidf", "HDBSCAN", "fit_predict", "TopicModel", "argmax")
    for function in (
        topics.project_2d,
        topics.projection_diagnostic,
        topics.projection_agreement,
        topics.neighbourhood_purity,
        topics.trustworthiness,
        topics.draw_projection,
        topics.group_others,
    ):
        source = body(function)
        for name in forbidden:
            assert name not in source, f"{function.__name__} reaches {name}"


def test_the_clustered_reduction_is_kept_but_never_labelled() -> None:
    """`TopicModel.reduced` exists so the diagnostic can compare the picture
    against the fit that produced the clusters. It must not become a second
    source of labels."""
    model = topics.TopicModel(name="embedding", labels=np.array([0, 1]), words={})
    assert model.reduced is None
    source = inspect.getsource(topics.relabel)
    assert "reduced=model.reduced" in source


# --- Figures ----------------------------------------------------------------


def test_group_others_keeps_the_most_frequent_and_folds_the_rest() -> None:
    values = ["a"] * 5 + ["b"] * 4 + ["c"] * 3 + ["d"] * 2 + ["e"]
    grouped = topics.group_others(values, 2)
    assert set(grouped) == {"a", "b", topics.OTHER_LABEL}
    assert list(grouped).count(topics.OTHER_LABEL) == 6


def test_group_others_breaks_ties_alphabetically_not_by_arrival() -> None:
    """A figure that changes because two delegations spoke equally often is a
    figure nobody can cite."""
    values = ["zulu", "zulu", "alpha", "alpha", "mike"]
    assert set(topics.group_others(values, 1)) == {"alpha", topics.OTHER_LABEL}


def test_group_others_keeps_everything_when_the_budget_is_large() -> None:
    values = ["a", "b", "c"]
    assert set(topics.group_others(values, 10)) == {"a", "b", "c"}


def test_group_others_names_a_missing_value_rather_than_dropping_it() -> None:
    grouped = topics.group_others(["a", "a", None], 5)
    assert len(grouped) == 3
    assert topics.OTHER_LABEL in set(grouped)


def test_the_figures_state_what_a_umap_axis_is_not() -> None:
    """docs/PLAN.md §7: the caveat travels with the image, because a PNG outlives
    the note it was pasted from."""
    assert all("not a quantity" in label for label in topics.AXIS_LABELS)
    assert "no topic label is derived" in topics.PROJECTION_CAVEAT
    assert "not evidence of influence" in topics.PROJECTION_CAVEAT


def test_the_figures_are_drawn_without_a_display() -> None:
    """A backend that reaches for a window is a way to fail forty minutes into a
    job on a headless compute node, after the expensive part is already done."""
    source = inspect.getsource(topics.draw_projection)
    assert 'matplotlib.use("Agg")' in source
    assert source.index('matplotlib.use("Agg")') < source.index("import matplotlib.pyplot")


def test_the_figures_are_deterministic_by_construction() -> None:
    """Fixed size and resolution, and no timestamp in the PNG: two runs over the
    same data must produce the same bytes."""
    assert topics.FIGURE_SIZE == (8.0, 8.0)
    assert topics.FIGURE_DPI == 150
    assert topics.FIGURE_METADATA["Date"] is None


# --- What 07 writes about the projection ------------------------------------
#
# The step is loaded by path, the way `test_neighbours.py` loads 06: the
# numbered scripts are orchestrators rather than importable modules. Nothing
# below imports scikit-learn, umap or matplotlib — 07 keeps all three inside the
# functions that use them, which is the condition CI runs under.


@pytest.fixture(scope="module")
def step():
    path = Path(__file__).resolve().parents[1] / "scripts" / "07_topics.py"
    spec = importlib.util.spec_from_file_location("topics_step", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def purity_block(mean: float, base: float, distinct: int) -> dict:
    return {
        "mean": mean,
        "base_rate": base,
        "lift": round(mean / base, 2),
        "k": 25,
        "points": 20_000,
        "distinct_values": distinct,
        "missing": 0,
    }


def projection_payload(agenda: float = 0.19, agenda_base: float = 0.05) -> dict:
    """A diagnostic in the shape 07 writes, with occasion ahead of subject.

    The speaker row is the strongest by lift (0.31 against a base of 0.004, so
    77.5), and the strongest subject row is the hand-coded agenda item at 3.8.
    Raising the agenda row past 77.5 is what flips the verdict.
    """
    return {
        "diagnostic": True,
        "release_artefact": False,
        "purpose": topics.PROJECTION_PURPOSE,
        "caveat": topics.PROJECTION_CAVEAT,
        "points": 20_000,
        "k": 25,
        "clustered_for_labels": False,
        "purity": {
            "speaker": purity_block(0.31, 0.004, 5_200),
            "country_org": purity_block(0.42, 0.02, 601),
            "year": purity_block(0.24, 0.033, 32),
            "period": purity_block(0.61, 0.28, 4),
            "agenda_item_manual": purity_block(agenda, agenda_base, 99),
            "nmf_topic": purity_block(0.14, 0.06, 25),
            "embedding_topic": purity_block(0.71, 0.09, 18),
        },
        "agreement": {
            "measured_against": "the reduction the clustering was fitted on",
            "points": 4_000,
            "sample_points": 20_000,
            "subsampled": True,
            "subsample_seed": 20_260_809,
            "k": 25,
            "trustworthiness": 0.812,
            "neighbours_lost_share": 0.437,
            "dimensions": {"clustered": 5, "projected": 2},
        },
    }


INSPECTION = {
    "targets": 3_273,
    "k": 10,
    "top1_same_speaker": 0.5536,
    "top1_same_year": 0.4717,
    "top1_also_genocide_bearing": 0.4189,
    "corpus_genocide_bearing_share": 0.0308,
}


def test_the_note_carries_the_numbers_rather_than_pointing_at_the_figure(step) -> None:
    """A reader who never opens a PNG has to come away with the finding. "See the
    figure" is how a caveat gets lost."""
    note = "\n".join(step.projection_section(projection_payload(), INSPECTION))
    assert "31.0%" in note, "the leading occasion purity"
    assert "0.4%" in note, "the base rate it is read against"
    assert "77.5" in note, "the lift"
    assert "the same named speaker" in note
    assert "19.0%" in note, "the strongest subject purity"
    assert "see the figure" not in note.lower()


def test_the_note_says_the_space_recovered_the_occasion(step) -> None:
    note = "\n".join(step.projection_section(projection_payload(), INSPECTION))
    assert "recovered the occasion" in note
    assert "agenda items dressed as themes" in note


def test_the_note_changes_its_verdict_when_subject_leads(step) -> None:
    """The one outcome that would weaken the objection has to be reported as
    such, not swallowed by a verdict written before the run."""
    note = "\n".join(
        step.projection_section(projection_payload(agenda=0.9, agenda_base=0.005), INSPECTION)
    )
    assert "recovered the occasion" not in note
    assert "weaken the objection" in note


def test_the_note_reads_06_beside_the_projection(step) -> None:
    """The same tendency measured before any reduction. Without it a reader can
    dismiss the diagnostic as an artefact of squashing 1,024 dimensions to two."""
    note = "\n".join(step.projection_section(projection_payload(), INSPECTION))
    assert "55.4%" in note
    assert "47.2%" in note
    assert "3.1%" in note


def test_the_note_survives_a_missing_neighbour_inspection(step) -> None:
    """06's summary is read opportunistically; a diagnostic that refuses to write
    itself because a companion file is absent is a diagnostic nobody gets."""
    note = "\n".join(step.projection_section(projection_payload(), {}))
    assert "55.4%" not in note
    assert "recovered the occasion" in note


def test_the_note_states_how_far_the_picture_is_from_the_clustering(step) -> None:
    note = "\n".join(step.projection_section(projection_payload(), INSPECTION))
    assert "0.812" in note
    assert "43.7%" in note
    assert "4,000" in note and "20,000" in note, "the subsample must be disclosed"


def test_the_note_refuses_the_reading_the_picture_invites(step) -> None:
    note = "\n".join(step.projection_section(projection_payload(), INSPECTION))
    assert "no topic label is derived from them" in note
    assert "not a map of topics" in note
    assert "ceiling" in note, "the HDBSCAN row must be marked as circular"


def test_the_full_note_is_written_without_a_missing_key(step) -> None:
    """The note is built after hours of fitting. Every earlier failure of this
    kind — a coherence block short of a key, a calibration curve that started
    above the line — surfaced as a KeyError at the very end of a run."""
    note = step.build_note(
        model_payload_stub(), model_payload_stub(), evaluation_stub(), pd.DataFrame(index=range(7))
    )
    assert "# 07 — Topics: a comparison, not a result" in note
    assert "## The 2D projection, and what it is evidence against" in note
    assert note.endswith("\n")


def model_payload_stub() -> dict:
    return {
        "topics": 3,
        "unassigned_share": 0.18,
        "coherence": {"mean": 0.11, "min": -0.02, "per_topic": {"0": 0.2}},
        "words": {"0": ["rwanda", "genocide"]},
        "composition": {"by_topic": [{"topic": 0, "documents": 9, "formulaic_share": 0.3}]},
    }


def evaluation_stub() -> dict:
    spread = {"median": 0.2, "p90": 0.3, "p95": 0.35, "p99": 0.4, "mean": 0.25, "p05": 0.1}
    return {
        "sample_seed": 1,
        "calibration": {
            "quantile": 0.95,
            "floor": 0.04,
            "min_weight": 0.35,
            "binds": True,
            "null_shares": spread,
            "observed_shares": spread,
            "curve": [{"min_weight": 0.35, "unassigned_share": 0.2, "chosen": True}],
        },
        "equal_abstention": {
            "min_weight": 0.3,
            "nmf_unassigned_share": 0.18,
            "nmf_coherence_mean": 0.1,
            "embedding_coherence_mean": 0.11,
        },
        "stability": {
            "nmf": {"adjusted_rand_mean": 0.5, "adjusted_rand_min": 0.4},
            "embedding": {"adjusted_rand_mean": 0.6, "adjusted_rand_min": 0.5},
        },
        "k_sweep": [
            {
                "k": 25,
                "topics": 3,
                "min_weight": 0.35,
                "min_weight_floor": 0.04,
                "unassigned_share": 0.18,
                "coherence_mean": 0.11,
            }
        ],
        "projection": projection_payload(),
        "neighbour_inspection": INSPECTION,
        "intrusion_tasks": 6,
        "verdict": "Stability is moderate.",
    }


def test_the_step_declares_what_its_directory_is_for(step) -> None:
    """`release_artefact: False` says the directory is not shipped; the purpose
    string says what it is for, so a file that travels away from this note still
    carries the argument it belongs to."""
    assert "evidence against" in step.PURPOSE
    assert "no topic label is derived" in step.PURPOSE


def test_every_attribute_scored_is_an_attribute_the_note_can_name(step) -> None:
    """A purity row with no label reaches the note as a raw column name, which is
    how `country_org` would arrive looking like a bug rather than a delegation."""
    sample = pd.DataFrame(
        {
            "speaker": ["Hannay", None, "Kagame"],
            "country_org": ["United Kingdom", "France", "Rwanda"],
            "year": [1994, 2004, 2014],
            "agenda_item_manual": ["Rwanda", "Rwanda", "Sudan"],
        }
    )
    attributes = step.projection_attributes(sample, np.array([0, 0, 1]), np.array([-1, 1, 1]))
    assert set(attributes) == set(step.PURITY_LABELS)
    assert set(step.OCCASION_ATTRIBUTES) | set(step.SUBJECT_ATTRIBUTES) <= set(attributes)
    for values in attributes.values():
        assert len(values) == len(sample)


def test_the_occasion_and_subject_split_is_declared_before_the_run(step) -> None:
    """Choosing which rows count as `occasion` after seeing which ones won would
    make the finding unfalsifiable."""
    assert set(step.OCCASION_ATTRIBUTES) & set(step.SUBJECT_ATTRIBUTES) == set()
    assert "embedding_topic" not in step.SUBJECT_ATTRIBUTES, "the HDBSCAN row is circular"
    for name in (*step.OCCASION_ATTRIBUTES, *step.SUBJECT_ATTRIBUTES):
        assert name in step.PURITY_LABELS
