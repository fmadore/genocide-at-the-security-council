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
