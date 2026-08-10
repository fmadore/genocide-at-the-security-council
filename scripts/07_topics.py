"""Two topic models on a frozen sample, and the evidence to judge them by.

Reads speeches_flagged.parquet and data/derived/embeddings/, writes
data/derived/topics/:

    nmf.json           the count-based baseline: topics, words, parameters
    embedding.json     UMAP + HDBSCAN over the speech vectors
    evaluation.json    coherence, seed stability, k sensitivity, composition
    assignments.parquet  row_id -> topic under each model
    intrusion_task.csv   the blinded word-intrusion task, for a human
    manifest.json

**This step does not produce a release artefact.** docs/PLAN.md §4 defers topic
modelling by design and sets gates it must pass first; what runs here is the
comparison and the evaluation those gates call for, so that the decision to adopt
or drop a topic model can be made on evidence. Nothing in web/ reads this
directory, and export_web.py does not know it exists.

Read `evaluation.json` before either model's own output. A topic model always
produces topics; the question is whether they survive a change of seed, a change
of k, and a reader who has to pick the intruder word.

Usage:
    python scripts/07_topics.py [--sample 20000] [--k 25] [--seeds 5]
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, frames, lexical, topics
from lib.paths import (
    EMBEDDINGS,
    ROOT,
    SPEECHES_FLAGGED,
    STOPWORDS,
    TOPICS,
    ensure_dirs,
    rel,
    write_note,
)

COLUMNS = [
    "row_id",
    "date",
    "year",
    "speaker",
    "country_org",
    "agenda_item_manual",
    "tokens",
    "text",
    "body_start",
    "has_genocide",
]

#: A word this common is the Council's shared register rather than a subject.
#: Used to measure how much of a topic is procedure, not to remove anything —
#: removal would hide the problem instead of reporting it.
FORMULAIC_DF = 0.5

#: Values of k the baseline is checked across. Wide enough that a genuinely
#: stable structure should survive, and reported whether or not it does.
K_SWEEP = [15, 25, 40]


def load_vectors(row_ids: pd.Series) -> np.ndarray:
    """Vectors for the sampled speeches, aligned by row_id.

    Positional alignment between a parquet and an .npy is exactly the kind of
    assumption that silently produces a beautiful and meaningless result, so the
    join is made on row_id and any gap is fatal.
    """
    vectors_path = EMBEDDINGS / "vectors.npy"
    index_path = EMBEDDINGS / "index.parquet"
    if not vectors_path.exists() or not index_path.exists():
        console.fail(
            f"{rel(EMBEDDINGS)} is missing — run 06_embed.py first (it needs a GPU; "
            f"see docs/CLUSTER.md)"
        )

    index = pd.read_parquet(index_path)
    vectors = np.load(vectors_path).astype(np.float32)
    if len(index) != len(vectors):
        console.fail(f"index has {len(index):,} rows but vectors.npy has {len(vectors):,}")

    position = pd.Series(index["position"].to_numpy(), index=index["row_id"].to_numpy())
    missing = [r for r in row_ids if r not in position.index]
    if missing:
        console.fail(
            f"{len(missing):,} sampled speeches have no vector",
            [f"first missing row_id: {missing[0]}", "re-run 06_embed.py without --limit"],
        )
    return vectors[position.loc[row_ids].to_numpy()]


def formulaic_terms(documents: list[list[str]], threshold: float) -> frozenset[str]:
    """Words appearing in more than `threshold` of the sampled speeches."""
    seen: dict[str, int] = {}
    for tokens in documents:
        for word in set(tokens):
            seen[word] = seen.get(word, 0) + 1
    cut = threshold * len(documents)
    return frozenset(word for word, count in seen.items() if count > cut)


def formulaic_share(documents: list[list[str]], terms: frozenset[str]) -> np.ndarray:
    return np.array(
        [
            sum(1 for w in tokens if w in terms) / len(tokens) if tokens else 0.0
            for tokens in documents
        ]
    )


def stability(fit, positions: np.ndarray, seeds: list[int]) -> dict[str, object]:
    """Refit under resampling and compare the labellings that result.

    `fit(subset_positions, seed) -> labels`. Each run sees a 90% resample of the
    frozen sample, so the seed moves both the data and the solver. Agreement is
    the adjusted Rand index over the documents any two runs share.
    """
    runs: list[tuple[np.ndarray, np.ndarray]] = []
    for seed in seeds:
        keep = topics.resample(positions, seed)
        started = time.monotonic()
        labels = fit(positions[keep], seed)
        runs.append((keep, labels))
        assigned = int((labels != topics.UNASSIGNED).sum())
        console.info(
            f"seed {seed}: {len(set(labels.tolist())) - (1 if assigned < len(labels) else 0)} "
            f"topics, {assigned / len(labels):.1%} assigned ({time.monotonic() - started:.0f}s)"
        )

    scores = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            (keep_a, labels_a), (keep_b, labels_b) = runs[i], runs[j]
            shared = np.intersect1d(keep_a, keep_b)
            if len(shared) < 2:
                continue
            a = labels_a[np.searchsorted(keep_a, shared)]
            b = labels_b[np.searchsorted(keep_b, shared)]
            scores.append(topics.adjusted_rand(a, b))

    return {
        "seeds": seeds,
        "resample_fraction": 0.9,
        "pairs": len(scores),
        "adjusted_rand_mean": round(float(np.mean(scores)), 4) if scores else 0.0,
        "adjusted_rand_min": round(float(np.min(scores)), 4) if scores else 0.0,
        "adjusted_rand_max": round(float(np.max(scores)), 4) if scores else 0.0,
        "topic_counts": [
            len({int(v) for v in labels if v != topics.UNASSIGNED}) for _, labels in runs
        ],
        "unassigned_shares": [
            round(float((labels == topics.UNASSIGNED).mean()), 4) for _, labels in runs
        ],
    }


def model_payload(
    model: topics.TopicModel,
    sample: pd.DataFrame,
    documents: list[list[str]],
    terms: frozenset[str],
) -> dict:
    coherence = topics.npmi_coherence(model.words, documents)
    return {
        "model": model.name,
        "params": model.params,
        "topics": len(model.topics),
        "unassigned": model.unassigned,
        "unassigned_share": round(model.unassigned_share, 4),
        "coherence": coherence,
        "words": {str(label): [w for w, _ in words] for label, words in model.words.items()},
        "words_scored": {
            str(label): [{"word": w, "score": s} for w, s in words]
            for label, words in model.words.items()
        },
        "composition": topics.sensitivity(sample, model.labels, terms),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("|".join(v) if isinstance(v, list) else v) for k, v in row.items()})
    artifacts.atomic_write_text(path, buffer.getvalue())


def build_note(nmf: dict, embedding: dict, evaluation: dict, sample: pd.DataFrame) -> str:
    def word_table(payload: dict, limit: int = 10) -> list[str]:
        rows = []
        coherence = payload["coherence"]["per_topic"]
        composition = {c["topic"]: c for c in payload["composition"]["by_topic"]}
        for label in sorted(payload["words"], key=lambda x: int(x))[:limit]:
            block = composition.get(int(label), {})
            rows.append(
                f"| {label} | {block.get('documents', 0):,} | "
                f"{coherence.get(label, 0):+.3f} | "
                f"{block.get('formulaic_share', 0) or 0:.0%} | "
                f"{', '.join(f'`{w}`' for w in payload['words'][label][:8])} |"
            )
        return rows

    verdict = evaluation["verdict"]
    return "\n".join(
        [
            "# 07 — Topics: a comparison, not a result",
            "",
            "docs/PLAN.md §4 defers topic modelling until there is a research question "
            "collocates and agenda labels cannot answer. This note does not supply that "
            "question. It supplies the evidence §4 asks for, so the question can be "
            "settled on something other than a plausible-looking list of words.",
            "",
            f"Frozen sample: **{len(sample):,} speeches** of at least "
            f"{topics.MIN_TOKENS} tokens, stratified by period, seed "
            f"{evaluation['sample_seed']}. Both models see exactly these documents.",
            "",
            "## The gates, and where each model stands",
            "",
            "| Gate (§4) | Baseline (NMF) | Embedding (UMAP + HDBSCAN) |",
            "|---|---:|---:|",
            f"| Topics found | {nmf['topics']} | {embedding['topics']} |",
            f"| Left unassigned | {nmf['unassigned_share']:.1%} | {embedding['unassigned_share']:.1%} |",
            f"| Mean NPMI coherence | {nmf['coherence']['mean']:+.3f} | {embedding['coherence']['mean']:+.3f} |",
            f"| Worst topic coherence | {nmf['coherence']['min']:+.3f} | {embedding['coherence']['min']:+.3f} |",
            f"| Stability across seeds (ARI) | {evaluation['stability']['nmf']['adjusted_rand_mean']:.3f} | {evaluation['stability']['embedding']['adjusted_rand_mean']:.3f} |",
            f"| Worst pair | {evaluation['stability']['nmf']['adjusted_rand_min']:.3f} | {evaluation['stability']['embedding']['adjusted_rand_min']:.3f} |",
            "",
            "**Adjusted Rand index** is 1.0 when two runs agree completely and 0.0 when "
            "they agree no more than chance. Each run resamples 90% of the frozen sample "
            "and changes the solver's seed, so this measures whether the topics are a "
            "property of the corpus or of one particular fit.",
            "",
            "## Baseline: NMF over TF-IDF",
            "",
            "| Topic | Speeches | NPMI | Procedural | Strongest words |",
            "|---:|---:|---:|---:|---|",
            *word_table(nmf),
            "",
            "## Embedding: UMAP into HDBSCAN",
            "",
            "| Topic | Speeches | NPMI | Procedural | Strongest words |",
            "|---:|---:|---:|---:|---|",
            *word_table(embedding),
            "",
            "The *Procedural* column is the share of a topic's words that appear in more "
            f"than {FORMULAIC_DF:.0%} of the sampled speeches. A topic in the high tens is "
            "the Council's register — thanking briefers, welcoming presidencies — wearing "
            "the appearance of a theme.",
            "",
            "## Sensitivity to k",
            "",
            "| k | Topics | Unassigned | Mean NPMI |",
            "|---:|---:|---:|---:|",
            *[
                f"| {row['k']} | {row['topics']} | {row['unassigned_share']:.1%} | "
                f"{row['coherence_mean']:+.3f} |"
                for row in evaluation["k_sweep"]
            ],
            "",
            "## What is still missing",
            "",
            "- **Blinded human interpretability.** `intrusion_task.csv` holds "
            f"{evaluation['intrusion_tasks']} word-intrusion items with their answer key. "
            "It is a task, not a score: until a person has completed it, this gate is "
            "open. Generating a number here would be the same error §1.1 forbids for the "
            "lexicon audit — an automatic judgement recorded as a human verdict.",
            "- **A research question.** §4 requires one before any of this enters the "
            "release pipeline.",
            "",
            "## Reading",
            "",
            verdict,
            "",
            "No 2D projection is written here. §4 permits one as exploratory navigation "
            "only, and a map is the easiest way for a distance nobody validated to become "
            "a claim about influence.",
            "",
        ]
    ) + "\n"


def build_verdict(nmf: dict, embedding: dict, stability_scores: dict) -> str:
    """State plainly what the numbers do and do not support."""
    weakest = min(
        stability_scores["nmf"]["adjusted_rand_mean"],
        stability_scores["embedding"]["adjusted_rand_mean"],
    )
    parts = []
    if weakest < 0.4:
        parts.append(
            f"At least one model changes substantially under a 10% resample "
            f"(ARI {weakest:.2f}). Topics that move that much are properties of a fit, "
            "not of the corpus, and must not be reported as findings."
        )
    elif weakest < 0.7:
        parts.append(
            f"Stability is moderate (worst mean ARI {weakest:.2f}). Individual topics may "
            "be robust while the partition as a whole is not; any topic used in an argument "
            "needs to be shown surviving the seeds individually."
        )
    else:
        parts.append(
            f"Both models are stable under resampling (worst mean ARI {weakest:.2f}). "
            "That is necessary, not sufficient: a stable model of the Council's procedural "
            "register is stably uninformative."
        )
    better = "the embedding model" if embedding["coherence"]["mean"] > nmf["coherence"]["mean"] else "the count-based baseline"
    margin = abs(embedding["coherence"]["mean"] - nmf["coherence"]["mean"])
    parts.append(
        f"On coherence {better} leads by {margin:.3f} NPMI. A margin below roughly 0.05 is "
        "not a reason to prefer an opaque model over one whose topics can be checked "
        "against a concordance."
    )
    return " ".join(parts)


def run(sample_size: int, k: int, seeds: int, seed: int, sweep: bool) -> None:
    ensure_dirs()

    console.step("Reading the flagged corpus")
    speeches = frames.read(SPEECHES_FLAGGED, columns=COLUMNS)

    console.step("Drawing the frozen sample")
    sample = topics.frozen_sample(speeches, sample_size, seed).reset_index(drop=True)
    console.info(
        f"{len(sample):,} speeches, {topics.MIN_TOKENS}+ tokens, "
        f"{sample['year'].min()}-{sample['year'].max()}"
    )
    for label, block in topics.assign_period(sample["year"]).value_counts().sort_index().items():
        console.info(f"  {label}: {block:,}")

    console.step("Tokenising")
    stopwords = lexical.load_stopwords()
    documents = topics.tokenise(frames.body(sample).tolist(), stopwords)
    terms = formulaic_terms(documents, FORMULAIC_DF)
    sample["formulaic_share"] = formulaic_share(documents, terms)
    console.info(
        f"{len(stopwords)} stopwords; {len(terms)} words in over {FORMULAIC_DF:.0%} of speeches"
    )

    console.step("Loading speech vectors")
    vectors = load_vectors(sample["row_id"])
    console.info(f"{vectors.shape[0]:,} x {vectors.shape[1]} vectors aligned by row_id")

    positions = np.arange(len(sample), dtype=np.int64)

    console.step(f"Baseline: NMF over TF-IDF, k={k}")
    started = time.monotonic()
    nmf_model = topics.fit_nmf([documents[i] for i in positions], k, seed)
    console.info(
        f"{len(nmf_model.topics)} topics, {nmf_model.unassigned_share:.1%} unassigned "
        f"({time.monotonic() - started:.0f}s)"
    )

    console.step("Embedding: UMAP into HDBSCAN")
    started = time.monotonic()
    embedding_model = topics.fit_embedding(vectors, documents, seed)
    console.info(
        f"{len(embedding_model.topics)} topics, {embedding_model.unassigned_share:.1%} "
        f"unassigned ({time.monotonic() - started:.0f}s)"
    )

    console.step("Stability under resampling")
    console.info("NMF:")
    nmf_stability = stability(
        lambda pos, s: topics.fit_nmf([documents[i] for i in pos], k, s).labels,
        positions,
        [seed + i for i in range(seeds)],
    )
    console.info("Embedding:")
    embedding_stability = stability(
        lambda pos, s: topics.fit_embedding(vectors[pos], [documents[i] for i in pos], s).labels,
        positions,
        [seed + i for i in range(seeds)],
    )

    k_sweep = []
    if sweep:
        console.step("Sensitivity to k")
        for candidate in K_SWEEP:
            model = nmf_model if candidate == k else topics.fit_nmf(documents, candidate, seed)
            coherence = topics.npmi_coherence(model.words, documents)
            k_sweep.append(
                {
                    "k": candidate,
                    "topics": len(model.topics),
                    "unassigned_share": round(model.unassigned_share, 4),
                    "coherence_mean": coherence["mean"],
                }
            )
            console.info(
                f"k={candidate}: {len(model.topics)} topics, "
                f"NPMI {coherence['mean']:+.3f}, {model.unassigned_share:.1%} unassigned"
            )

    console.step("Building payloads")
    nmf_payload = model_payload(nmf_model, sample, documents, terms)
    embedding_payload = model_payload(embedding_model, sample, documents, terms)
    stability_scores = {"nmf": nmf_stability, "embedding": embedding_stability}
    intrusion = topics.word_intrusion(nmf_model.words, seed) + topics.word_intrusion(
        embedding_model.words, seed + 1
    )
    evaluation = {
        "sample_size": len(sample),
        "sample_seed": seed,
        "min_tokens": topics.MIN_TOKENS,
        "formulaic_document_frequency": FORMULAIC_DF,
        "stability": stability_scores,
        "k_sweep": k_sweep,
        "intrusion_tasks": len(intrusion),
        "verdict": build_verdict(nmf_payload, embedding_payload, stability_scores),
    }

    console.step("Writing")
    meta = artifacts.provenance(
        ROOT,
        "07_topics.py",
        inputs=[SPEECHES_FLAGGED, EMBEDDINGS / "vectors.npy"],
        configs=[STOPWORDS],
        extra={
            "embedding_manifest": str(rel(EMBEDDINGS / "manifest.json")),
            "sample_size": len(sample),
            "sample_seed": seed,
            "k": k,
            "stability_seeds": seeds,
            "release_artefact": False,
        },
    )
    assignments = pd.DataFrame(
        {
            "row_id": sample["row_id"].to_numpy(),
            "year": sample["year"].to_numpy(),
            "nmf_topic": nmf_model.labels,
            "embedding_topic": embedding_model.labels,
            "formulaic_share": sample["formulaic_share"].to_numpy(),
        }
    )

    with artifacts.atomic_directory(TOPICS) as staged:
        artifacts.atomic_write_json(staged / "nmf.json", {"meta": meta, **nmf_payload})
        artifacts.atomic_write_json(
            staged / "embedding.json", {"meta": meta, **embedding_payload}
        )
        artifacts.atomic_write_json(
            staged / "evaluation.json", {"meta": meta, **evaluation}, indent=2
        )
        assignments.to_parquet(staged / "assignments.parquet", index=False, compression="zstd")
        write_csv(staged / "intrusion_task.csv", intrusion)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    console.info(f"wrote {rel(TOPICS)}")

    note = write_note(
        "07_topics.md", build_note(nmf_payload, embedding_payload, evaluation, sample)
    )
    console.info(f"wrote {note.name}")
    console.step("Verdict")
    console.info(evaluation["verdict"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=20_000, help="speeches in the frozen sample")
    parser.add_argument("--k", type=int, default=25, help="topics for the NMF baseline")
    parser.add_argument("--seeds", type=int, default=5, help="refits per model for stability")
    parser.add_argument("--seed", type=int, default=20_260_809, help="base seed")
    parser.add_argument("--no-sweep", action="store_true", help="skip the k sensitivity sweep")
    args = parser.parse_args()
    run(args.sample, args.k, args.seeds, args.seed, sweep=not args.no_sweep)


if __name__ == "__main__":
    main()
