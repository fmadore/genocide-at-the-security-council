"""Encoding speeches as vectors: the model registry, chunking, and pooling.

Three decisions live here, and each is one a reader is entitled to question.

**Which model.** `config/embedding_models.yml` is a hand-edited analysis input,
not a flag. Swapping the encoder changes every distance downstream, so the choice
is versioned beside the lexicon rather than left in someone's shell history. The
declared dimensionality is asserted against the model that actually loads.

**What to do with long speeches.** A transformer truncates silently at its
context window: hand it a 40-minute intervention and it will return a vector for
the opening and discard the argument. Speeches above the window are therefore cut
into overlapping token windows and recombined by a token-weighted mean, so the
whole text contributes in proportion to its length. The corpus makes this cheap —
at an 8,192-token window only a few hundred of 106,302 speeches need it at all —
but the alternative is an artefact that is quietly wrong about its longest and
most substantial speeches. Every chunk count is written to the index, so the
affected rows can be excluded from any analysis that would rather not trust them.

**What "close" means.** Vectors are L2-normalised after pooling, so the inner
product is the cosine. Nothing here interprets that distance: two speeches with a
high cosine used similar language, which is not a claim about influence, position
or shared meaning. 07 and docs/PLAN.md §4 carry that caveat into the outputs.

GPU inference in reduced precision is not bit-reproducible: the same speech on an
H100 and an L40 can differ in the last decimals, and a batch boundary can move a
value too. That is why :func:`environment` records the device, the driver, the
dtype and the resolved package versions into every manifest — a rerun is checked
against those, not assumed to be identical.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .paths import CONFIG, rel

#: The registry. Kept beside config/lexicon.yml because it is the same kind of
#: object: an input a human curates, versioned, whose change invalidates results.
REGISTRY = CONFIG / "embedding_models.yml"

#: Overlap between consecutive windows of a chunked speech, in tokens. Enough to
#: carry a sentence across the seam so neither window begins mid-clause.
CHUNK_OVERLAP = 128

#: Word-to-token inflation used to decide which speeches are even *candidates*
#: for chunking. Deliberately generous: guessing high costs one tokenizer pass
#: over a few extra documents, guessing low silently truncates a speech.
TOKEN_INFLATION = 2.0


@dataclass(frozen=True)
class ModelSpec:
    """One entry in the registry."""

    key: str
    repo: str
    revision: str
    dimensions: int
    max_tokens: int
    batch_size: int
    torch_dtype: str
    licence: str
    note: str
    tokenizer_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Registry:
    version: int
    default: str
    models: dict[str, ModelSpec]


def load_registry(path: Path | None = None) -> Registry:
    """Read and validate `config/embedding_models.yml`."""
    path = path or REGISTRY
    if not path.exists():
        raise FileNotFoundError(f"{rel(path)} is missing")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    for key in ("version", "default", "models"):
        if key not in raw:
            raise ValueError(f"{rel(path)}: missing top-level `{key}`")
    if not isinstance(raw["models"], dict) or not raw["models"]:
        raise ValueError(f"{rel(path)}: `models` must be a non-empty mapping")

    models: dict[str, ModelSpec] = {}
    for key, entry in raw["models"].items():
        missing = {"repo", "dimensions", "max_tokens", "batch_size"} - set(entry)
        if missing:
            raise ValueError(f"{rel(path)}: model `{key}` is missing {', '.join(sorted(missing))}")
        models[key] = ModelSpec(
            key=key,
            repo=str(entry["repo"]),
            revision=str(entry.get("revision", "main")),
            dimensions=int(entry["dimensions"]),
            max_tokens=int(entry["max_tokens"]),
            batch_size=int(entry["batch_size"]),
            torch_dtype=str(entry.get("torch_dtype", "float32")),
            licence=str(entry.get("licence", "unknown")),
            note=str(entry.get("note", "")).strip(),
            tokenizer_kwargs=dict(entry.get("tokenizer_kwargs") or {}),
        )

    if raw["default"] not in models:
        raise ValueError(f"{rel(path)}: default `{raw['default']}` is not one of the models")
    return Registry(version=int(raw["version"]), default=str(raw["default"]), models=models)


# --- Chunking --------------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    """Which piece of text belongs to which speech.

    ``pieces`` is what gets encoded; ``owner[i]`` is the row that piece *i* came
    from and ``weight[i]`` its token count. Documents short enough to fit the
    window appear exactly once, so the common case costs nothing.
    """

    pieces: list[str]
    owner: np.ndarray
    weight: np.ndarray
    chunked_rows: int

    def __len__(self) -> int:
        return len(self.pieces)


def plan_chunks(texts: list[str], tokenizer, max_tokens: int, overlap: int = CHUNK_OVERLAP) -> Plan:
    """Split only the documents that exceed the context window.

    The tokenizer is consulted for the candidates alone. Tokenising 106,302
    speeches to discover that 106,000 of them are short is a waste of a GPU
    reservation; a word count with a generous inflation factor picks the
    candidates, and the exact test is applied only to those.
    """
    if overlap >= max_tokens:
        raise ValueError(f"overlap {overlap} must be smaller than the window {max_tokens}")

    pieces: list[str] = []
    owner: list[int] = []
    weight: list[float] = []
    chunked = 0

    candidates = [
        i for i, text in enumerate(texts) if text.count(" ") * TOKEN_INFLATION > max_tokens
    ]
    exact: dict[int, list[int]] = {}
    if candidates:
        encoded = tokenizer(
            [texts[i] for i in candidates], add_special_tokens=False, verbose=False
        )["input_ids"]
        exact = dict(zip(candidates, encoded, strict=True))

    for i, text in enumerate(texts):
        ids = exact.get(i)
        if ids is None or len(ids) <= max_tokens:
            pieces.append(text)
            owner.append(i)
            # An unchunked document weighs its own length, so that pooling is
            # the same operation whether or not a document was split.
            weight.append(float(len(ids)) if ids is not None else float(max(text.count(" "), 1)))
            continue

        chunked += 1
        step = max_tokens - overlap
        for start in range(0, len(ids), step):
            window = ids[start : start + max_tokens]
            if not window:
                break
            pieces.append(tokenizer.decode(window, skip_special_tokens=True))
            owner.append(i)
            weight.append(float(len(window)))
            if start + max_tokens >= len(ids):
                break

    return Plan(
        pieces=pieces,
        owner=np.asarray(owner, dtype=np.int64),
        weight=np.asarray(weight, dtype=np.float64),
        chunked_rows=chunked,
    )


def pool(vectors: np.ndarray, plan: Plan, rows: int) -> np.ndarray:
    """Token-weighted mean of a document's pieces, then L2-normalise.

    Weighting by tokens rather than averaging the chunks equally keeps a 200-token
    tail from counting as much as the 8,000-token argument before it.
    """
    if len(vectors) != len(plan):
        raise ValueError(f"{len(vectors)} vectors for {len(plan)} pieces")
    summed = np.zeros((rows, vectors.shape[1]), dtype=np.float64)
    totals = np.zeros(rows, dtype=np.float64)
    np.add.at(summed, plan.owner, vectors.astype(np.float64) * plan.weight[:, None])
    np.add.at(totals, plan.owner, plan.weight)
    if not totals.all():
        raise ValueError("a row received no pieces — every speech must be encoded")
    return l2_normalise(summed / totals[:, None])


def l2_normalise(vectors: np.ndarray) -> np.ndarray:
    """Scale each row to unit length, leaving an all-zero row alone."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1.0, norms)


# --- Encoding --------------------------------------------------------------


def load_model(spec: ModelSpec, device: str | None = None):
    """Load a SentenceTransformer for a registry entry, asserting its shape.

    Imported lazily: the test suite, CI and steps 00-05 never touch torch, and
    importing it costs several seconds and a CUDA context.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    dtype = getattr(torch, spec.torch_dtype, None)
    if dtype is None:
        raise ValueError(f"unknown torch dtype `{spec.torch_dtype}` for model `{spec.key}`")
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    # bfloat16/float16 on a CPU node is a trap: it loads, runs ~20x slower than
    # float32, and the run looks like it is merely queued behind something.
    if device == "cpu" and dtype is not torch.float32:
        dtype = torch.float32

    # sentence-transformers 5.7 renamed `tokenizer_kwargs` to `processor_kwargs`.
    # The registry keeps the older name because what it carries — `padding_side`
    # — is a tokenizer setting, whatever the library calls the argument.
    model = SentenceTransformer(
        spec.repo,
        revision=spec.revision,
        device=device,
        model_kwargs={"dtype": dtype},
        processor_kwargs=dict(spec.tokenizer_kwargs) or None,
    )
    model.max_seq_length = spec.max_tokens

    # Renamed in 5.7 as well; the old name still works but warns. Ask for the
    # new one and fall back, so the supported range installs cleanly either way.
    dimension = getattr(model, "get_embedding_dimension", None) or (
        model.get_sentence_embedding_dimension
    )
    actual = int(dimension())
    if actual != spec.dimensions:
        raise ValueError(
            f"model `{spec.key}` produced {actual}-dimensional vectors but "
            f"{rel(REGISTRY)} declares {spec.dimensions} — fix the registry before "
            f"writing an artefact that claims the wrong shape"
        )
    return model


def environment(spec: ModelSpec, device: str) -> dict[str, object]:
    """Everything needed to judge whether a rerun matches this run."""
    packages: dict[str, str] = {}
    for package in ("torch", "transformers", "sentence-transformers", "scikit-learn", "umap-learn"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            continue

    payload: dict[str, object] = {
        "model_key": spec.key,
        "model_repo": spec.repo,
        "model_revision": spec.revision,
        "model_licence": spec.licence,
        "dimensions": spec.dimensions,
        "max_tokens": spec.max_tokens,
        "batch_size": spec.batch_size,
        "torch_dtype": spec.torch_dtype,
        "device": device,
        "gpu_packages": packages,
        "slurm_job": os.environ.get("SLURM_JOB_ID", ""),
    }
    try:
        import torch

        payload["cuda_runtime"] = torch.version.cuda or ""
        if torch.cuda.is_available():
            payload["gpu_name"] = torch.cuda.get_device_name(0)
            major, minor = torch.cuda.get_device_capability(0)
            payload["gpu_capability"] = f"{major}.{minor}"
    except ImportError:
        pass
    return payload


# --- Neighbours ------------------------------------------------------------


def top_neighbours(
    query: np.ndarray, corpus: np.ndarray, k: int, exclude: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Cosine top-k of each query row against the corpus.

    Both sides are unit vectors, so the dot product is the cosine. The corpus is
    106,302 x 1,024; a full similarity matrix would be 45 GB, so queries are
    processed in blocks and only the top k survive each block.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    indices = np.empty((len(query), k), dtype=np.int64)
    scores = np.empty((len(query), k), dtype=np.float32)
    block = max(1, 2_000_000 // max(len(corpus), 1))

    for start in range(0, len(query), block):
        stop = min(start + block, len(query))
        sim = query[start:stop] @ corpus.T
        if exclude is not None:
            sim[np.arange(stop - start), exclude[start:stop]] = -np.inf
        part = np.argpartition(-sim, kth=k - 1, axis=1)[:, :k]
        ordered = np.take_along_axis(part, np.argsort(-np.take_along_axis(sim, part, 1), 1), 1)
        indices[start:stop] = ordered
        scores[start:stop] = np.take_along_axis(sim, ordered, 1).astype(np.float32)
    return indices, scores


def store_dtype(vectors: np.ndarray, dtype: str) -> np.ndarray:
    """Cast for storage, checking the cast does not destroy the vectors.

    float16 halves 435 MB to 218 MB at a relative error around 5e-4, which is far
    below any distance this project would call a difference. It is still checked
    rather than assumed.
    """
    if dtype == "float32":
        return vectors.astype(np.float32)
    if dtype != "float16":
        raise ValueError(f"unsupported storage dtype `{dtype}`")
    cast = vectors.astype(np.float16)
    error = float(np.abs(cast.astype(np.float32) - vectors).max())
    if error > 1e-2:
        raise ValueError(f"float16 storage would lose {error:.4f} per component; use float32")
    return cast
