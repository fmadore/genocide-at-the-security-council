"""The registry, the chunking policy and the pooling that follows it.

Torch and sentence-transformers are cluster-only, so `load_model` is not
exercised here. Everything that decides *what text the model sees* and *what is
done with the vectors it returns* is plain numpy, and that is the part where a
mistake produces a plausible artefact rather than a crash: a truncated speech
still yields a perfectly well-formed vector.

The tokenizer is faked. Its contract with `plan_chunks` is small — call it with a
list of strings, get `input_ids` back, and be able to `decode` them — so a stub
tests the policy without pulling in a 600 MB model.
"""

from __future__ import annotations

import numpy as np
import pytest
import yaml
from lib import embeddings


class FakeTokenizer:
    """One token per word, decoding back to the words joined by spaces."""

    def __init__(self) -> None:
        self.vocabulary: list[str] = []
        self.calls = 0

    def __call__(self, texts, add_special_tokens=True, verbose=True):
        self.calls += 1
        ids = []
        for text in texts:
            row = []
            for word in text.split():
                if word not in self.vocabulary:
                    self.vocabulary.append(word)
                row.append(self.vocabulary.index(word))
            ids.append(row)
        return {"input_ids": ids}

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(self.vocabulary[i] for i in ids)


# --- The registry ----------------------------------------------------------


def write_registry(tmp_path, payload: dict):
    path = tmp_path / "embedding_models.yml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


MINIMAL = {
    "version": 1,
    "default": "small",
    "models": {
        "small": {"repo": "org/small", "dimensions": 8, "max_tokens": 16, "batch_size": 2}
    },
}


def test_the_shipped_registry_loads() -> None:
    registry = embeddings.load_registry()
    assert registry.default in registry.models
    for spec in registry.models.values():
        assert spec.dimensions > 0
        assert spec.max_tokens > embeddings.CHUNK_OVERLAP
        assert spec.note, f"{spec.key} should say why it is in the registry"


def test_defaults_are_filled_in(tmp_path) -> None:
    registry = embeddings.load_registry(write_registry(tmp_path, MINIMAL))
    assert registry.models["small"].revision == "main"
    assert registry.models["small"].torch_dtype == "float32"


def test_a_default_naming_a_missing_model_is_rejected(tmp_path) -> None:
    payload = {**MINIMAL, "default": "absent"}
    with pytest.raises(ValueError, match="not one of the models"):
        embeddings.load_registry(write_registry(tmp_path, payload))


def test_an_incomplete_entry_is_rejected(tmp_path) -> None:
    payload = {**MINIMAL, "models": {"small": {"repo": "org/small"}}}
    with pytest.raises(ValueError, match="missing"):
        embeddings.load_registry(write_registry(tmp_path, payload))


def test_an_empty_registry_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        embeddings.load_registry(write_registry(tmp_path, {**MINIMAL, "models": {}}))


# --- Chunking --------------------------------------------------------------


def test_short_documents_are_left_whole() -> None:
    plan = embeddings.plan_chunks(["a b c", "d e"], FakeTokenizer(), max_tokens=512)
    assert plan.pieces == ["a b c", "d e"]
    assert plan.chunked_rows == 0
    assert list(plan.owner) == [0, 1]


def test_the_tokenizer_is_not_consulted_for_short_documents() -> None:
    """106,302 tokenizer passes to discover 106,000 short speeches is a waste of
    a GPU reservation."""
    tokenizer = FakeTokenizer()
    embeddings.plan_chunks(["a b", "c d"], tokenizer, max_tokens=1024)
    assert tokenizer.calls == 0


def test_a_long_document_is_split_with_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(100))
    plan = embeddings.plan_chunks([text], FakeTokenizer(), max_tokens=40, overlap=10)
    assert plan.chunked_rows == 1
    assert len(plan.pieces) > 1
    assert (plan.owner == 0).all()
    # Consecutive windows share their overlap, so no sentence falls in a seam.
    assert plan.pieces[0].split()[-10:] == plan.pieces[1].split()[:10]


def test_a_split_document_keeps_all_of_its_text() -> None:
    text = " ".join(f"w{i}" for i in range(100))
    plan = embeddings.plan_chunks([text], FakeTokenizer(), max_tokens=40, overlap=10)
    seen = {word for piece in plan.pieces for word in piece.split()}
    assert seen == set(text.split())


def test_chunking_does_not_emit_an_empty_tail() -> None:
    text = " ".join(f"w{i}" for i in range(80))
    plan = embeddings.plan_chunks([text], FakeTokenizer(), max_tokens=40, overlap=10)
    assert all(piece.strip() for piece in plan.pieces)


def test_an_overlap_wider_than_the_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="smaller than the window"):
        embeddings.plan_chunks(["a"], FakeTokenizer(), max_tokens=10, overlap=10)


# --- Pooling ---------------------------------------------------------------


def test_an_unchunked_document_keeps_its_direction() -> None:
    plan = embeddings.plan_chunks(["a b"], FakeTokenizer(), max_tokens=512)
    vectors = np.array([[3.0, 4.0]])
    pooled = embeddings.pool(vectors, plan, rows=1)
    assert pooled == pytest.approx(np.array([[0.6, 0.8]]))


def test_pooling_weights_by_tokens_not_by_chunk() -> None:
    """A 200-token tail must not count as much as the 8,000 tokens before it."""
    plan = embeddings.Plan(
        pieces=["long", "tail"],
        owner=np.array([0, 0]),
        weight=np.array([900.0, 100.0]),
        chunked_rows=1,
    )
    pooled = embeddings.pool(np.array([[1.0, 0.0], [0.0, 1.0]]), plan, rows=1)
    assert pooled[0][0] > pooled[0][1] * 8


def test_pooled_vectors_are_unit_length() -> None:
    plan = embeddings.Plan(
        pieces=["a", "b", "c"],
        owner=np.array([0, 0, 1]),
        weight=np.array([1.0, 1.0, 1.0]),
        chunked_rows=1,
    )
    pooled = embeddings.pool(np.random.default_rng(0).normal(size=(3, 5)), plan, rows=2)
    assert np.linalg.norm(pooled, axis=1) == pytest.approx(np.ones(2))


def test_a_row_with_no_pieces_is_an_error() -> None:
    """Silently emitting a zero vector would put a speech at the origin, equally
    close to everything."""
    plan = embeddings.Plan(
        pieces=["a"], owner=np.array([0]), weight=np.array([1.0]), chunked_rows=0
    )
    with pytest.raises(ValueError, match="no pieces"):
        embeddings.pool(np.ones((1, 3)), plan, rows=2)


def test_a_vector_count_mismatch_is_an_error() -> None:
    plan = embeddings.plan_chunks(["a", "b"], FakeTokenizer(), max_tokens=512)
    with pytest.raises(ValueError, match="vectors for"):
        embeddings.pool(np.ones((1, 3)), plan, rows=2)


def test_normalising_leaves_a_zero_row_alone() -> None:
    out = embeddings.l2_normalise(np.array([[0.0, 0.0], [3.0, 4.0]]))
    assert out[0] == pytest.approx(np.zeros(2))
    assert out[1] == pytest.approx(np.array([0.6, 0.8]))


# --- Neighbours ------------------------------------------------------------


def corpus() -> np.ndarray:
    return embeddings.l2_normalise(
        np.array([[1.0, 0.0], [0.95, 0.05], [0.0, 1.0], [-1.0, 0.0]])
    )


def test_neighbours_come_back_in_descending_similarity() -> None:
    """Without `exclude`, a vector present in the corpus matches itself first —
    which is why 06 always passes the query positions as `exclude`."""
    vectors = corpus()
    indices, scores = embeddings.top_neighbours(vectors[[0]], vectors, k=4)
    assert list(indices[0]) == [0, 1, 2, 3]
    assert list(scores[0]) == sorted(scores[0], reverse=True)
    assert scores[0][0] == pytest.approx(1.0)


def test_a_speech_is_not_its_own_neighbour() -> None:
    vectors = corpus()
    indices, _ = embeddings.top_neighbours(
        vectors[[0]], vectors, k=1, exclude=np.array([0])
    )
    assert indices[0][0] != 0


def test_k_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        embeddings.top_neighbours(corpus()[[0]], corpus(), k=0)


# --- Storage ---------------------------------------------------------------


def test_float16_storage_is_accepted_for_unit_vectors() -> None:
    vectors = embeddings.l2_normalise(np.random.default_rng(1).normal(size=(50, 32)))
    stored = embeddings.store_dtype(vectors, "float16")
    assert stored.dtype == np.float16
    assert np.abs(stored.astype(np.float64) - vectors).max() < 1e-3


def test_float16_storage_is_refused_when_it_would_lose_too_much() -> None:
    """float16 spaces values around 3,000 about two apart. Unit vectors are
    nowhere near that, which is the point — the check is cheap and would catch a
    caller who stored something other than a normalised vector."""
    with pytest.raises(ValueError, match="float16 storage would lose"):
        embeddings.store_dtype(np.full((2, 2), 3000.7), "float16")


def test_an_unknown_storage_dtype_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported storage dtype"):
        embeddings.store_dtype(np.zeros((2, 2)), "int8")
