import json

import numpy as np
import pandas as pd
import pytest
from lib import artifacts, lemmas, semantic


def fixture(tmp_path):
    speeches = pd.DataFrame({"row_id": ["a", "b"], "text": ["hello", "world"], "body_start": [0, 0]})
    np.save(tmp_path / "vectors.npy", np.eye(2, dtype=np.float32))
    pd.DataFrame({"row_id": ["b", "a"], "position": [0, 1], "body_sha256": [lemmas.body_hash("world"), lemmas.body_hash("hello")]}).to_parquet(tmp_path / "index.parquet")
    meta = {"embedding_schema": 2, "limit": 0, "speeches": 2, "dimensions": 2,
            "vectors_sha256": artifacts.sha256(tmp_path / "vectors.npy"), "index_sha256": artifacts.sha256(tmp_path / "index.parquet")}
    (tmp_path / "manifest.json").write_text(json.dumps(meta))
    return speeches


def test_aligns_verified_vectors_by_id(tmp_path):
    speeches = fixture(tmp_path)
    vectors, _ = semantic.load_vectors(tmp_path, speeches)
    np.testing.assert_array_equal(vectors, [[0, 1], [1, 0]])


def test_rejects_stale_bodies(tmp_path):
    speeches = fixture(tmp_path)
    speeches.loc[0, "text"] = "changed"
    with pytest.raises(ValueError, match="stale"):
        semantic.load_vectors(tmp_path, speeches)


def test_rejects_corrupt_vectors(tmp_path):
    speeches = fixture(tmp_path)
    np.save(tmp_path / "vectors.npy", np.ones((2, 2)))
    with pytest.raises(ValueError, match="checksum"):
        semantic.load_vectors(tmp_path, speeches)


def test_neighbours_exclude_self_sort_and_deduplicate():
    speeches = pd.DataFrame({"row_id": ["a", "b", "c"]})
    indices = np.array([[0, 2, 1, 1], [1, 0, 2, 0], [2, 1, 0, 1]])
    distances = np.array([[0, .4, .2, .2], [0, .2, .5, .2], [0, .5, .4, .5]])
    records = semantic.neighbour_records(speeches, indices, distances)
    assert records["a"] == [["b", .8], ["c", .6]]
    indices[0, 1] = -1
    with pytest.raises(ValueError, match="invalid neighbour"):
        semantic.neighbour_records(speeches, indices, distances)


# --- Local fidelity: the neighbourhood a reader of the map actually looks at ---


def _unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def test_local_fidelity_with_every_point_a_query_is_trustworthiness_itself() -> None:
    """The two must be one measurement, or the new figure means something else."""
    from lib import projection

    rng = np.random.default_rng(7)
    high = _unit(rng.normal(size=(60, 8)))
    low = rng.normal(size=(60, 2))
    found = projection.local_fidelity(high, low, seed=1, k=5, queries=60)
    assert found["query_seed"] is None
    assert found["trustworthiness"] == pytest.approx(
        projection.trustworthiness(high, low, 5), abs=1e-4
    )
    assert found["neighbours_lost_share"] == pytest.approx(
        projection.neighbour_loss(
            projection.nearest_neighbours(high, 5), projection.nearest_neighbours(low, 5)
        ),
        abs=1e-4,
    )


def test_a_map_that_keeps_every_neighbourhood_loses_nothing() -> None:
    from lib import projection

    rng = np.random.default_rng(3)
    plane = rng.normal(size=(80, 2))
    found = projection.local_fidelity(plane, plane * 3.0, seed=1, k=6, queries=20)
    assert found["neighbours_lost_share"] == 0.0
    assert found["trustworthiness"] == 1.0
    assert found["queries"] == 20 and found["points"] == 80


def test_local_fidelity_looks_among_all_points_and_the_subsample_figure_does_not() -> None:
    """Two tight clusters laid out correctly, each scrambled inside.

    The subsample figure finds a point's "neighbours" among a few dozen drawn
    points, which here are its cluster-mates, and calls the map faithful. A
    point's real nearest neighbours are lost, and only a search over every
    point says so.
    """
    from lib import projection

    rng = np.random.default_rng(11)
    centres = np.repeat(np.array([[0.0, 0.0], [100.0, 0.0]]), 400, axis=0)
    high = centres + rng.normal(size=(800, 2))
    low = centres + rng.normal(size=(800, 2))  # same clusters, unrelated positions inside
    coarse = projection.projection_agreement(high, low, seed=5, k=10, max_points=40)
    local = projection.local_fidelity(high, low, seed=5, k=10, queries=200)
    assert local["neighbours_lost_share"] > 0.9
    assert local["neighbours_lost_share"] > coarse["neighbours_lost_share"] + 0.3


def test_local_fidelity_refuses_two_spaces_of_different_sizes() -> None:
    from lib import projection

    with pytest.raises(ValueError, match="different point counts"):
        projection.local_fidelity(np.zeros((5, 3)), np.zeros((4, 2)), seed=1)
