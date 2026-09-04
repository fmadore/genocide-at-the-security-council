"""Encode every speech as a vector, on a GPU.

Reads speeches_flagged.parquet and writes data/derived/embeddings/:

    vectors.npy      167,642 x D, float16, L2-normalised, in index order
    index.parquet    row_id per position, plus how each speech was encoded
    neighbours.json  nearest neighbours of the genocide-bearing speeches
    manifest.json    model, revision, device, driver, package versions

This is step 06 because the embedding-based half of 07 consumes it. The comments
in lib/paths.py used to number these the other way around; nothing had been built
against that order, and topics-then-embeddings would have had 07 depend on a
later step.

**What this artefact is not.** A cosine between two vectors says two speeches
used similar language. It is not a measure of agreement, influence, or shared
position, and no chart may present it as one. docs/PLAN.md §4 governs.

**Reproducibility.** Reduced-precision GPU arithmetic is not bit-exact across
devices or batch boundaries, so a rerun on a different card will not hash
identically. The manifest records device, driver, dtype and package versions;
`--device cpu --storage-dtype float32` is the reproducible-but-slow path.

Usage:
    python scripts/06_embed.py [--model qwen3-0.6b] [--limit N] [--device cuda]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, embeddings, frames
from lib.paths import (
    DERIVED,
    EMBEDDINGS,
    ROOT,
    SPEECHES_FLAGGED,
    ensure_dirs,
    rel,
    write_note,
)

#: Where a --limit run writes. `artifacts.atomic_directory` replaces its target
#: wholesale, so without this a 256-speech smoke test would silently destroy a
#: 25-GPU-minute corpus artefact and leave something that looks just like it.
SMOKE = DERIVED / "embeddings_smoke"

COLUMNS = [
    "row_id",
    "date",
    "year",
    "speaker",
    "country_org",
    "speaker_group",
    "agenda_item_manual",
    "tokens",
    "text",
    "body_start",
    "has_genocide",
]

#: Pieces handed to the encoder per call. Large enough that the GPU is busy,
#: small enough that a log line appears often enough to tell a stuck job from a
#: slow one.
REPORT_EVERY = 4096

#: Neighbours kept per genocide-bearing speech.
NEIGHBOURS = 10


def encode(model, pieces: list[str], batch_size: int) -> np.ndarray:
    """Encode in reported blocks, without a progress bar.

    A tqdm bar writes thousands of carriage returns into a Slurm .out file; a
    line per block is what someone tailing the log actually wants.
    """
    out: list[np.ndarray] = []
    done = 0
    for start in range(0, len(pieces), REPORT_EVERY):
        block = pieces[start : start + REPORT_EVERY]
        out.append(
            model.encode(
                block,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
        )
        done += len(block)
        console.info(f"encoded {done:,} / {len(pieces):,} pieces")
    return np.vstack(out).astype(np.float32)


def build_neighbours(
    vectors: np.ndarray, speeches: pd.DataFrame, k: int
) -> tuple[dict[str, object], pd.DataFrame]:
    """Nearest neighbours of every genocide-bearing speech.

    docs/PLAN.md §4 asks for this as an inspection, not a result: it is the
    cheapest way for a reader to find out whether the space has organised the
    corpus by anything they recognise before anyone builds a topic model on it.
    """
    targets = np.flatnonzero(speeches["has_genocide"].to_numpy())
    if not len(targets):
        return {"targets": 0, "k": k, "speeches": []}, pd.DataFrame()

    console.info(f"{len(targets):,} genocide-bearing speeches, {k} neighbours each")
    indices, scores = embeddings.top_neighbours(vectors[targets], vectors, k, exclude=targets)

    meta = speeches.reset_index(drop=True)
    flat = pd.DataFrame(
        {
            "row_id": np.repeat(meta["row_id"].to_numpy()[targets], k),
            "rank": np.tile(np.arange(1, k + 1), len(targets)),
            "neighbour_row_id": meta["row_id"].to_numpy()[indices.ravel()],
            "cosine": scores.ravel(),
            "neighbour_has_genocide": meta["has_genocide"].to_numpy()[indices.ravel()],
            "neighbour_year": meta["year"].to_numpy()[indices.ravel()],
            "same_year": meta["year"].to_numpy()[np.repeat(targets, k)]
            == meta["year"].to_numpy()[indices.ravel()],
            "same_speaker": meta["country_org"].to_numpy()[np.repeat(targets, k)]
            == meta["country_org"].to_numpy()[indices.ravel()],
        }
    )

    # The summary is the part worth reading: if a genocide-bearing speech's
    # nearest neighbour is nearly always another one, the space has found the
    # vocabulary; if it is nearly always the same meeting, it has found the
    # agenda instead, which is a different and much less interesting result.
    top = flat[flat["rank"] == 1]
    payload = {
        "targets": len(targets),
        "k": k,
        "top1_also_genocide_bearing": round(float(top["neighbour_has_genocide"].mean()), 4),
        "top1_same_year": round(float(top["same_year"].mean()), 4),
        "top1_same_speaker": round(float(top["same_speaker"].mean()), 4),
        "top1_cosine_median": round(float(top["cosine"].median()), 4),
        "any_k_also_genocide_bearing": round(float(flat["neighbour_has_genocide"].mean()), 4),
        "corpus_genocide_bearing_share": round(float(speeches["has_genocide"].mean()), 4),
    }
    return payload, flat


def build_note(
    spec: embeddings.ModelSpec,
    speeches: pd.DataFrame,
    plan: embeddings.Plan,
    neighbours: dict,
    environment: dict,
    elapsed: float,
) -> str:
    lift = (
        neighbours.get("top1_also_genocide_bearing", 0)
        / max(neighbours.get("corpus_genocide_bearing_share", 1) or 1, 1e-9)
    )
    return "\n".join(
        [
            "# 06 — Speech embeddings",
            "",
            f"{len(speeches):,} speeches encoded with `{spec.repo}` "
            f"({spec.dimensions} dimensions, {spec.licence}) on "
            f"{environment.get('gpu_name', environment.get('device', 'unknown'))} "
            f"in {elapsed / 60:.1f} minutes.",
            "",
            "## How the text was handled",
            "",
            f"- Window: {spec.max_tokens:,} tokens, overlap "
            f"{embeddings.CHUNK_OVERLAP}.",
            f"- {plan.chunked_rows:,} speeches exceeded the window and were encoded as "
            "overlapping chunks recombined by a token-weighted mean; the rest were encoded "
            "whole.",
            f"- {len(plan):,} pieces in total for {len(speeches):,} speeches.",
            "- The opening form of address is removed before encoding "
            "(`lib.frames.body`), so a vector is not dominated by "
            "*I thank the President for convening this meeting*.",
            "",
            "## Nearest-neighbour inspection",
            "",
            "docs/PLAN.md §4 asks for this before any topic model is trusted. For each of "
            f"the {neighbours.get('targets', 0):,} genocide-bearing speeches, its "
            f"{neighbours.get('k', 0)} closest speeches in the corpus:",
            "",
            "| Measure | Value |",
            "|---|---:|",
            f"| Nearest neighbour also uses the term | {neighbours.get('top1_also_genocide_bearing', 0):.1%} |",
            f"| Base rate across the corpus | {neighbours.get('corpus_genocide_bearing_share', 0):.1%} |",
            f"| Lift over the base rate | {lift:.1f}x |",
            f"| Nearest neighbour is the same year | {neighbours.get('top1_same_year', 0):.1%} |",
            f"| Nearest neighbour is the same speaker | {neighbours.get('top1_same_speaker', 0):.1%} |",
            f"| Median cosine to the nearest neighbour | {neighbours.get('top1_cosine_median', 0):.3f} |",
            "",
            "Read the last three rows before the first. A high same-year or same-speaker "
            "share means the space has largely recovered *the occasion* — which debate a "
            "speech belongs to — and a topic model built on it will recover agenda items "
            "wearing the costume of themes.",
            "",
            "## What this artefact does not license",
            "",
            "A cosine is a statement about language, not about politics. Two speeches "
            "close together used similar words; they need not agree, and neither one need "
            "have influenced the other. No published figure may translate this distance "
            "into a claim about position or influence.",
            "",
            "## Reproducibility",
            "",
            f"- Device `{environment.get('device')}`, dtype `{spec.torch_dtype}`, "
            f"driver via CUDA {environment.get('cuda_runtime', 'n/a')}.",
            "- Reduced-precision GPU arithmetic is not bit-exact across devices or batch "
            "boundaries. A rerun on another card will not hash identically; the manifest "
            "records what to compare against.",
            "- Packages: "
            + ", ".join(f"{k} {v}" for k, v in environment.get("gpu_packages", {}).items())
            + ".",
            "",
        ]
    ) + "\n"


def run(model_key: str | None, limit: int, device: str | None, storage: str, k: int) -> None:
    ensure_dirs()
    registry = embeddings.load_registry()
    key = model_key or registry.default
    if key not in registry.models:
        console.fail(
            f"unknown model `{key}`", [f"available: {', '.join(registry.models)}"]
        )
    spec = registry.models[key]
    console.info(f"registry version {registry.version}; model `{key}` -> {spec.repo}")

    console.step("Reading the flagged corpus")
    speeches = frames.read(SPEECHES_FLAGGED, columns=COLUMNS)
    target = EMBEDDINGS
    if limit:
        speeches = speeches.head(limit)
        target = SMOKE
        console.warn(f"--limit {limit}: a smoke test, not a corpus artefact")
        console.warn(f"writing to {rel(target)} so {rel(EMBEDDINGS)} is left alone")
    speeches = speeches.reset_index(drop=True)
    bodies = frames.body(speeches).tolist()

    console.step(f"Loading {spec.repo}")
    started = time.monotonic()
    model = embeddings.load_model(spec, device=device)
    resolved = str(model.device.type)
    console.info(f"loaded on {resolved} in {time.monotonic() - started:.1f}s")

    console.step("Planning chunks")
    plan = embeddings.plan_chunks(bodies, model.tokenizer, spec.max_tokens)
    console.info(
        f"{len(plan):,} pieces for {len(speeches):,} speeches; "
        f"{plan.chunked_rows:,} speeches needed chunking"
    )

    console.step("Encoding")
    started = time.monotonic()
    pieces = encode(model, plan.pieces, spec.batch_size)
    elapsed = time.monotonic() - started
    console.info(f"{len(pieces):,} vectors in {elapsed / 60:.1f} min")

    console.step("Pooling and normalising")
    vectors = embeddings.pool(pieces, plan, rows=len(speeches))
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        console.fail(f"vectors are not unit length (min {norms.min():.4f}, max {norms.max():.4f})")

    console.step("Nearest-neighbour inspection")
    neighbour_summary, neighbour_rows = build_neighbours(vectors, speeches, k)

    console.step("Writing")
    environment = embeddings.environment(spec, resolved)
    meta = artifacts.provenance(
        ROOT,
        "06_embed.py",
        inputs=[SPEECHES_FLAGGED],
        configs=[embeddings.REGISTRY],
        extra={
            "registry_version": registry.version,
            "speeches": len(speeches),
            "pieces": len(plan),
            "chunked_speeches": int(plan.chunked_rows),
            "chunk_overlap": embeddings.CHUNK_OVERLAP,
            "storage_dtype": storage,
            "encode_seconds": round(elapsed, 1),
            "limit": limit,
            **environment,
        },
    )

    stored = embeddings.store_dtype(vectors, storage)
    index = pd.DataFrame(
        {
            "position": np.arange(len(speeches), dtype=np.int64),
            "row_id": speeches["row_id"].to_numpy(),
            "pieces": np.bincount(plan.owner, minlength=len(speeches)).astype(np.int32),
            "encoded_tokens": np.bincount(
                plan.owner, weights=plan.weight, minlength=len(speeches)
            ).astype(np.int64),
        }
    )

    with artifacts.atomic_directory(target) as staged:
        np.save(staged / "vectors.npy", stored)
        index.to_parquet(staged / "index.parquet", index=False, compression="zstd")
        artifacts.atomic_write_json(
            staged / "neighbours.json", {"meta": meta, **neighbour_summary}
        )
        if len(neighbour_rows):
            neighbour_rows.to_parquet(
                staged / "neighbours.parquet", index=False, compression="zstd"
            )
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)

    size = (target / "vectors.npy").stat().st_size / 1e6
    console.info(f"wrote {rel(target)}  vectors {stored.shape} ({size:.0f} MB, {storage})")

    note = write_note(
        "06_embed.md",
        build_note(spec, speeches, plan, neighbour_summary, environment, elapsed),
    )
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="registry key (default: the registry default)")
    parser.add_argument("--limit", type=int, default=0, help="encode only the first N speeches")
    parser.add_argument("--device", help="cuda | cpu (default: cuda when available)")
    parser.add_argument(
        "--storage-dtype",
        default="float16",
        choices=["float16", "float32"],
        help="on-disk precision (default float16: 218 MB rather than 435 MB)",
    )
    parser.add_argument("--neighbours", type=int, default=NEIGHBOURS)
    args = parser.parse_args()
    run(args.model, args.limit, args.device, args.storage_dtype, args.neighbours)


if __name__ == "__main__":
    main()
