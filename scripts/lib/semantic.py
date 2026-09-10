"""Validated speech vectors and evidence-preserving semantic-map records."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import artifacts, frames, lemmas


def load_vectors(directory: Path, speeches: pd.DataFrame) -> tuple[np.ndarray, dict]:
    meta = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if meta.get("embedding_schema") != 2 or meta.get("limit"):
        raise ValueError("a complete schema-2 embedding run is required")
    for name, field in [("vectors.npy", "vectors_sha256"), ("index.parquet", "index_sha256")]:
        if artifacts.sha256(directory / name) != meta.get(field):
            raise ValueError(f"embedding checksum mismatch: {name}")
    index = pd.read_parquet(directory / "index.parquet")
    vectors = np.load(directory / "vectors.npy", mmap_mode="r", allow_pickle=False)
    if (vectors.ndim != 2 or len(index) != len(vectors)
            or vectors.shape[1] != meta.get("dimensions") or len(index) != meta.get("speeches")):
        raise ValueError("embedding shape/manifest mismatch")
    if (index["row_id"].isna().any() or index["row_id"].duplicated().any()
            or speeches["row_id"].isna().any() or speeches["row_id"].duplicated().any()
            or set(index["row_id"]) != set(speeches["row_id"])
            or not np.array_equal(index["position"], np.arange(len(index)))):
        raise ValueError("embedding/corpus row IDs or positions differ")
    bodies = frames.body(speeches)
    digests = dict(zip(speeches["row_id"], map(lemmas.body_hash, bodies), strict=True))
    if any(digests[row.row_id] != row.body_sha256 for row in index.itertuples()):
        raise ValueError("embedding speech bodies are stale")
    for start in range(0, len(vectors), 4096):
        block = vectors[start:start + 4096].astype(np.float32)
        if not np.isfinite(block).all() or not np.allclose(np.linalg.norm(block, axis=1), 1, atol=.002):
            raise ValueError("embedding vectors must be finite unit vectors")
    positions = pd.Series(index["position"].to_numpy(), index=index["row_id"])
    return np.asarray(vectors[positions.loc[speeches["row_id"]].to_numpy()], dtype=np.float32), meta


def neighbour_records(speeches: pd.DataFrame, indices: np.ndarray, distances: np.ndarray, k: int = 10) -> dict:
    """ANN candidates with explicit ranks; self-links are never emitted."""
    if k < 1 or indices.ndim != 2 or indices.shape != distances.shape or len(indices) != len(speeches):
        raise ValueError("neighbour arrays do not align with speeches")
    out = {}
    ids = speeches["row_id"].astype(str).tolist()
    for i, (candidates, scores) in enumerate(zip(indices, distances, strict=True)):
        seen = {i}
        rows = []
        for j, distance in sorted(zip(candidates, scores, strict=True), key=lambda pair: (pair[1], pair[0])):
            j = int(j)
            if j in seen:
                continue
            if j < 0 or j >= len(ids) or not np.isfinite(distance) or distance < -1e-5 or distance > 2.00001:
                raise ValueError("invalid neighbour index or distance")
            seen.add(j)
            rows.append([ids[j], round(float(np.clip(1 - distance, -1, 1)), 5)])
            if len(rows) == k:
                break
        out[ids[i]] = rows
    return out
