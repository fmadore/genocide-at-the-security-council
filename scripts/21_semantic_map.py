"""Project validated speech embeddings and publish original-vector neighbours.

Run after 06_embed.py. CPU-only; no model inference or clustering labels.
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, embeddings, frames, semantic, topics
from lib.paths import DERIVED, EMBEDDINGS, ROOT, SPEECHES_FLAGGED


def project(vectors: np.ndarray, seed: int, neighbours: int = 30):
    from pynndescent import NNDescent
    from umap import UMAP

    if len(vectors) <= neighbours:
        raise ValueError("projection needs more speeches than graph neighbours")
    graph = NNDescent(vectors, metric="cosine", n_neighbors=neighbours, random_state=seed, n_jobs=1)
    indices, distances = graph.neighbor_graph
    if (indices < 0).any() or not np.isfinite(distances).all():
        raise ValueError("approximate graph is incomplete")
    print("Neighbour graph built", flush=True)
    coordinates = UMAP(n_neighbors=neighbours, min_dist=.1, metric="cosine", random_state=seed,
                       n_jobs=1, precomputed_knn=(indices, distances, graph)).fit_transform(vectors)
    if not np.isfinite(coordinates).all():
        raise ValueError("projection contains invalid coordinates")
    queries = np.sort(np.random.default_rng(seed).choice(len(vectors), min(128, len(vectors)), replace=False))
    exact, _ = embeddings.top_neighbours(vectors[queries], vectors, k=10, exclude=queries)
    recalls = []
    for query, actual in zip(queries, exact, strict=True):
        candidates = [int(i) for i in indices[query] if i != query][:10]
        recalls.append(len(set(candidates) & set(actual)) / 10)
    evaluation = topics.projection_agreement(vectors, coordinates, seed=seed, max_points=1000)
    evaluation["measured_against"] = "original normalized speech embeddings"
    evaluation["ann_recall_at_10"] = round(float(np.mean(recalls)), 4)
    evaluation["ann_exact_query_sample"] = len(queries)
    # Poor ANN is a failed artifact, not a plausible-looking map.
    if evaluation["ann_recall_at_10"] < .8:
        raise ValueError(f"ANN recall below .8: {evaluation['ann_recall_at_10']}")
    return coordinates, indices, distances, evaluation


def run(directory: Path, seed: int) -> None:
    speeches = frames.read(SPEECHES_FLAGGED, columns=["row_id", "text", "body_start", "year", "country_org", "agenda_item_manual", "has_genocide"])
    speeches = speeches.rename(columns={"agenda_item_manual": "agenda"})
    vectors, source = semantic.load_vectors(directory, speeches)
    # float16 storage introduces slight norm error; cosine and exact dot-product
    # validation must refer to precisely the same normalized representation.
    vectors = embeddings.l2_normalise(vectors)
    coordinates, indices, distances, evaluation = project(vectors, seed)
    records = semantic.neighbour_records(speeches, indices, distances)
    countries = sorted(speeches.country_org.fillna("Unknown affiliation").unique())
    agendas = sorted(speeches.agenda.fillna("Unknown agenda").astype(str).unique())
    country_ids, agenda_ids = {v: i for i, v in enumerate(countries)}, {v: i for i, v in enumerate(agendas)}
    points = [[str(row.row_id), round(float(x), 4), round(float(y), 4), int(row.year),
               country_ids[str(row.country_org)] if row.country_org in country_ids else country_ids["Unknown affiliation"],
               agenda_ids[str(row.agenda)] if str(row.agenda) in agenda_ids else agenda_ids["Unknown agenda"], bool(row.has_genocide)]
              for row, (x, y) in zip(speeches.itertuples(), coordinates, strict=True)]
    meta = artifacts.provenance(ROOT, "21_semantic_map.py", inputs=[SPEECHES_FLAGGED, directory / "manifest.json"],
                                configs=[Path(__file__), ROOT / "scripts/lib/semantic.py", ROOT / "scripts/lib/topics.py"], extra={
        "schema": 1, "seed": seed, "model_repo": source["model_repo"], "model_revision": source["model_revision"],
        "projection": "UMAP", "metric": "cosine", "n_neighbors": 30, "min_dist": .1,
        "packages": {name: version(name) for name in ("numpy", "umap-learn", "pynndescent", "scikit-learn")},
        "evaluation": evaluation, "speeches": len(speeches), "neighbour_shards": 256,
        "neighbours": "Approximate cosine neighbours in the original embedding space; self excluded",
        "point_columns": ["id", "x", "y", "year", "country", "agenda", "genocide"],
    })
    with artifacts.atomic_directory(DERIVED / "semantic") as staged:
        artifacts.atomic_write_json(staged / "map.json", {"meta": meta, "countries": countries, "agendas": agendas, "points": points})
        (staged / "neighbours").mkdir()
        shards = [{} for _ in range(256)]
        for position, row in enumerate(points):
            shards[position % 256][row[0]] = records[row[0]]
        for number, shard in enumerate(shards):
            artifacts.atomic_write_json(staged / "neighbours" / f"{number}.json", shard)
        meta["files"] = {path.relative_to(staged).as_posix(): artifacts.sha256(path) for path in sorted(staged.rglob("*.json"))}
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    print(f"Semantic map ready: {len(points):,} speeches; {evaluation}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", type=Path, default=EMBEDDINGS / "qwen3-0.6b")
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args()
    run(args.embeddings, args.seed)
