"""Two topic models on a frozen sample, and the evidence to judge them by.

Reads speeches_flagged.parquet and data/derived/embeddings/, writes
data/derived/topics/:

    nmf.json           the count-based baseline: topics, words, parameters
    embedding.json     UMAP + HDBSCAN over the speech vectors
    evaluation.json    coherence, seed stability, k sensitivity, composition,
                       and the calibration of the baseline's abstention
    projection.json    the 2D projection diagnostic — purity and trustworthiness
    projection_*.png   the same projection coloured by year, delegation, cluster
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

**The projection is not a map of topics and is not a step towards one.** It is
fitted after the clustering, is never clustered and never labels anything, and it
is here to be measured: if a speech's neighbours in the picture are mostly the
same delegation and the same year, then the space has recovered the occasion and
a topic model over it would return agenda items dressed as themes, which is
exactly what §4 warns of. `projection.json` reports that as neighbourhood purity
beside the base rate a random neighbour would give.

Usage:
    python scripts/07_topics.py [--sample 20000] [--k 25] [--seeds 5]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
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

#: Categories a figure distinguishes by colour before folding the rest into one
#: muted group. Past a dozen, a categorical legend is a colour-matching exercise
#: and a recycled hue invites a reader to see two distant groups as one.
FIGURE_CATEGORIES = 10

#: Written into every manifest this step produces, beside `release_artefact:
#: False`. The flag says the directory is not shipped; this says what it is for,
#: so a file that travels away from the note still carries the argument it
#: belongs to.
PURPOSE = (
    "Evaluation evidence for docs/PLAN.md §4, not a result. The 2D projection in "
    "this directory is a diagnostic whose purpose is inverted from the usual one: "
    "it is evidence against reading this embedding space thematically, by "
    "measuring how much of a speech's neighbourhood in the picture is the same "
    "speaker and the same occasion rather than the same subject. No cluster is "
    "fitted on the projection's coordinates and no topic label is derived from "
    "them."
)

#: How each purity row is named in the note. Keys are columns of the frozen
#: sample plus the two models' own labels; a share means nothing without the name
#: of what it is a share of.
PURITY_LABELS = {
    "speaker": "the same named speaker",
    "country_org": "the same delegation",
    "year": "the same year",
    "period": "the same period",
    "agenda_item_manual": "the same hand-coded agenda item",
    "nmf_topic": "the same NMF topic",
    "embedding_topic": "the same HDBSCAN cluster",
}

#: Which purity rows describe *when and who* and which describe *what about*.
#: The diagnostic's whole question is which of the two the picture separates
#: more sharply, so the split is declared here rather than inferred from the
#: numbers after they arrive.
OCCASION_ATTRIBUTES = ("speaker", "country_org", "year", "period")
SUBJECT_ATTRIBUTES = ("agenda_item_manual", "nmf_topic")


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


def neighbour_inspection() -> dict[str, object]:
    """The shares 06 measured in the full space, if they are on disk.

    07 already depends on 06's vectors; this reads the same step's other output
    for a second purpose. The projection diagnostic argues that the space has
    recovered the occasion, and 06 measured exactly that in 1,024 dimensions
    before anything was reduced — so the note can put the two side by side
    instead of asking a reader to hold one of them in their head.

    Missing or unreadable, the note simply says less. A diagnostic that refuses
    to run because a companion file is absent would make the harder half of the
    evidence hostage to the easier half.
    """
    path = EMBEDDINGS / "neighbours.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        console.warn(f"{rel(path)} could not be read; the note will omit 06's own shares")
        return {}
    wanted = (
        "targets",
        "k",
        "top1_same_speaker",
        "top1_same_year",
        "top1_also_genocide_bearing",
        "corpus_genocide_bearing_share",
    )
    return {key: payload[key] for key in wanted if key in payload}


def projection_attributes(
    sample: pd.DataFrame, nmf_labels: np.ndarray, embedding_labels: np.ndarray
) -> dict[str, object]:
    """The columns a neighbourhood in the projection is scored against.

    Occasion first, because that is what the space is suspected of having
    recovered; subject last, because the comparison between the two is the whole
    point. `country_org` is here as well as `speaker` because it is the field 06
    called "same speaker", and the two numbers have to be readable against each
    other rather than against a footnote explaining that they measure different
    things.
    """
    return {
        "speaker": sample["speaker"],
        "country_org": sample["country_org"],
        "year": sample["year"],
        "period": topics.assign_period(sample["year"]),
        "agenda_item_manual": sample["agenda_item_manual"],
        "nmf_topic": nmf_labels,
        "embedding_topic": embedding_labels,
    }


def build_figures(
    coordinates: np.ndarray, sample: pd.DataFrame, labels: np.ndarray
) -> list[tuple[str, bytes, dict[str, object]]]:
    """The three PNGs, as (filename, bytes, description).

    One per question a reader puts to a scatter plot of speeches: when, who, and
    which cluster. Year is a quantity the frozen sample carries, so it gets a
    continuous scale; delegation and cluster are categories, so they get discrete
    colours and a stated cut-off. Nothing else is coloured, because nothing else
    would survive docs/PLAN.md §7's rule that colour must not encode a quantity
    the underlying table does not support.

    The cluster figure is the one most likely to be misread, so its caption says
    where the clusters came from: five dimensions, not these two.
    """
    delegations = topics.group_others(sample["country_org"], FIGURE_CATEGORIES)
    clusters = topics.group_others(
        [
            topics.UNASSIGNED_LABEL if label == topics.UNASSIGNED else f"topic {label}"
            for label in labels
        ],
        FIGURE_CATEGORIES,
    )

    def named(values: np.ndarray) -> int:
        return len({v for v in values if v not in (topics.OTHER_LABEL, topics.UNASSIGNED_LABEL)})

    return [
        (
            "projection_year.png",
            topics.draw_projection(
                coordinates,
                sample["year"],
                title="Speech vectors projected to 2D, coloured by year",
                colour_label="Year",
                categorical=False,
            ),
            {
                "file": "projection_year.png",
                "colour": "year",
                "scale": "continuous",
                "categories": None,
            },
        ),
        (
            "projection_speaker.png",
            topics.draw_projection(
                coordinates,
                delegations,
                title="The same projection, coloured by delegation",
                colour_label="Delegation",
                categorical=True,
                note=f"The {named(delegations)} delegations with the most speeches in the "
                "frozen sample; every other delegation is one grey group.",
            ),
            {
                "file": "projection_speaker.png",
                "colour": "country_org",
                "scale": "categorical",
                "categories": named(delegations),
            },
        ),
        (
            "projection_cluster.png",
            topics.draw_projection(
                coordinates,
                clusters,
                title="The same projection, coloured by HDBSCAN cluster",
                colour_label="Cluster",
                categorical=True,
                note=f"The {named(clusters)} largest clusters; the rest, and every speech "
                "the clustering declined to assign, are grey. The clusters were fitted in "
                "the five-dimensional reduction, not in these coordinates.",
            ),
            {
                "file": "projection_cluster.png",
                "colour": "embedding_topic",
                "scale": "categorical",
                "categories": named(clusters),
                "fitted_in": "the 5D reduction, not these coordinates",
            },
        ),
    ]


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


def strongest(purity: dict, names: tuple[str, ...]) -> str:
    """The attribute of `names` whose neighbourhoods beat chance by the most.

    Lift, not the raw share: `period` has four values and `speaker` has
    thousands, so their bare purities are not comparable and the larger one is
    mostly a statement about how many categories there are.
    """
    present = [name for name in names if name in purity]
    return max(present, key=lambda name: purity[name]["lift"] or 0.0)


def projection_section(projection: dict, inspection: dict) -> list[str]:
    """The diagnostic, stated in words with the numbers inside them.

    A reader who never opens a PNG has to come away knowing what the figures
    would have shown them and what follows from it. "See the figure" is how a
    caveat gets lost.
    """
    purity = projection["purity"]
    agreement = projection["agreement"]
    k = projection["k"]
    occasion, subject = strongest(purity, OCCASION_ATTRIBUTES), strongest(
        purity, SUBJECT_ATTRIBUTES
    )
    recovered = (purity[occasion]["lift"] or 0.0) > (purity[subject]["lift"] or 0.0)

    def row(name: str) -> str:
        block = purity[name]
        lift = f"x{block['lift']:.1f}" if block["lift"] else "—"
        # Not `capitalize`, which would lowercase the rest and turn NMF and
        # HDBSCAN into words nobody in this project uses.
        label = PURITY_LABELS.get(name, name)
        return (
            f"| {label[:1].upper()}{label[1:]} | {block['mean']:.1%} | "
            f"{block['base_rate']:.1%} | {lift} | {block['distinct_values']:,} |"
        )

    finding = (
        f"**{purity[occasion]['mean']:.1%} of the {k} speeches nearest a speech in this "
        f"picture share {PURITY_LABELS[occasion]}**, against the "
        f"{purity[occasion]['base_rate']:.1%} a randomly chosen other speech would give — a "
        f"lift of {purity[occasion]['lift']:.1f}. The strongest attribute that is about "
        f"subject rather than occasion, {PURITY_LABELS[subject]}, reaches "
        f"{purity[subject]['mean']:.1%} against {purity[subject]['base_rate']:.1%}, a lift of "
        f"{purity[subject]['lift']:.1f}."
    )
    verdict = (
        "The picture therefore separates speakers and occasions more sharply than it "
        "separates subjects. A reader shown it and told it was a map of themes would in "
        "fact be reading a map of who was speaking and when — which is the §4 condition "
        "for not adopting a topic model over this space: the space has substantially "
        "recovered the occasion, and topics drawn from it are agenda items dressed as "
        "themes until something else shows otherwise."
        if recovered
        else "On this sample the subject attributes lead, which is the one outcome that "
        "would weaken the objection. It does not on its own establish anything: read it "
        "beside the stability battery and 06's neighbour inspection before treating any "
        "topic as real."
    )

    context = []
    if {"top1_same_speaker", "top1_same_year"} <= set(inspection):
        context = [
            "",
            "06 measured the same tendency in the full space, before any reduction: the "
            f"single nearest neighbour of a genocide-bearing speech is the same delegation "
            f"{inspection['top1_same_speaker']:.1%} of the time and from the same year "
            f"{inspection['top1_same_year']:.1%} of the time"
            + (
                f", and {inspection['top1_also_genocide_bearing']:.1%} of those neighbours "
                f"also carry the term against a corpus share of "
                f"{inspection['corpus_genocide_bearing_share']:.1%}"
                if {"top1_also_genocide_bearing", "corpus_genocide_bearing_share"}
                <= set(inspection)
                else ""
            )
            + ". The projection has not introduced the problem; it has made it visible.",
        ]

    return [
        "## The 2D projection, and what it is evidence against",
        "",
        "`projection.json` and three PNGs sit beside this note. They are a diagnostic, not "
        "a map of topics and not a step towards one. The projection is fitted after the "
        "clustering, from the same vectors and the same seed; **no cluster is fitted on "
        "its coordinates and no topic label is derived from them**, and the "
        "five-dimensional reduction HDBSCAN was actually fitted in is unchanged. The "
        "coordinates themselves are not written to disk: what is kept is the measurements "
        "and the pictures, so there is no column here to join back onto a speech and call "
        "a topic.",
        "",
        f"For each of the {projection['points']:,} points, its {k} nearest points **in the "
        "2D coordinates**, and how often they share an attribute — beside the share a "
        "randomly chosen other speech would give, because a purity on its own is "
        "unreadable:",
        "",
        "| Attribute shared with a neighbour | In the projection | At random | Lift | Distinct values |",
        "|---|---:|---:|---:|---:|",
        *[row(name) for name in purity],
        "",
        finding,
        "",
        verdict,
        *context,
        "",
        "The HDBSCAN row is not independent evidence, and is here as a ceiling rather than "
        "as a result: the clusters and this picture are two reductions of the same "
        "vectors, so they are bound to agree to some degree. The rows to read against the "
        "occasion rows are the hand-coded agenda item and the NMF topic, neither of which "
        "ever saw a vector.",
        "",
        "### The picture is not the space that was clustered",
        "",
        f"Trustworthiness of the 2D embedding against the {agreement['dimensions']['clustered']}D "
        f"reduction is **{agreement['trustworthiness']:.3f}**, and "
        f"**{agreement['neighbours_lost_share']:.1%}** of each point's {agreement['k']} nearest "
        f"neighbours in that reduction are absent from its {agreement['k']} nearest here. "
        + (
            f"Both are measured over {agreement['points']:,} points drawn deterministically "
            f"from the {agreement['sample_points']:,} in the frozen sample (seed "
            f"{agreement['subsample_seed']}), because the ranks the measure needs are an "
            "n-by-n matrix; the subsample is recorded rather than quietly assumed."
            if agreement["subsampled"]
            else f"Both are measured over all {agreement['points']:,} points."
        ),
        "",
        "That is the arithmetic reason a thematic map would mislead. Points the clustering "
        "called neighbours can sit far apart in the figure, and points the figure puts "
        "together can belong to different clusters, so a cluster drawn as a region of this "
        "plot would be a claim neither fit supports.",
        "",
    ]


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
    calibration = evaluation["calibration"]
    equal_abstention = evaluation["equal_abstention"]
    rule = f"the {calibration['quantile']:.0%} quantile of the same model fitted to noise"
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
            "## Where the baseline is allowed to abstain",
            "",
            "HDBSCAN can decline to assign a document; NMF cannot, unless it is given a "
            "minimum share of document-topic weight below which it says nothing. That "
            "threshold is not free. A document's share is its largest topic weight over "
            f"the sum of them, so it can never fall below 1/k = "
            f"{calibration['floor']:.4f} — and a constant chosen without reference to k "
            "is inert at one end of the sweep and binding at the other. An earlier run of "
            "this script used 0.05 and left 0.0% of documents unassigned at every seed.",
            "",
            f"The line is now drawn where the model stops beating chance: {rule}. "
            f"Every token in the sample is pooled, shuffled and dealt back into documents "
            f"of the same lengths, the same vocabulary and idf are applied, and the model "
            f"is refitted. The result is **{calibration['min_weight']:.4f}**"
            + (
                f", which leaves {nmf['unassigned_share']:.1%} of documents unassigned."
                if calibration["binds"]
                else " — the floor itself, meaning the model concentrates no more on this "
                "corpus than on randomly dealt words."
            ),
            "",
            "| Share of the best topic | Randomly dealt | This corpus |",
            "|---|---:|---:|",
            *[
                f"| {label} | {calibration['null_shares'][key]:.3f} | "
                f"{calibration['observed_shares'][key]:.3f} |"
                for key, label in [
                    ("median", "median"),
                    ("p90", "90th percentile"),
                    ("p95", "95th percentile"),
                    ("p99", "99th percentile"),
                ]
            ],
            "",
            "How much the headline depends on where that line sits:",
            "",
            "| min_weight | Unassigned |",
            "|---:|---:|",
            *[
                f"| {point['min_weight']:.4f}{' **(chosen)**' if point['chosen'] else ''} | "
                f"{point['unassigned_share']:.1%} |"
                for point in calibration["curve"]
            ],
            "",
            "Because the two models otherwise abstain at different rates, the baseline is "
            "also read a second time at HDBSCAN's own rate — same factorisation, same "
            f"topics, only the line moved. At min_weight "
            f"{equal_abstention['min_weight']:.4f} it leaves "
            f"{equal_abstention['nmf_unassigned_share']:.1%} unassigned and scores "
            f"{equal_abstention['nmf_coherence_mean']:+.3f} NPMI against the embedding "
            f"model's {equal_abstention['embedding_coherence_mean']:+.3f}. That is the "
            "comparison §4 asks for: neither model credited for a candour the other was "
            "never offered.",
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
            *projection_section(
                evaluation["projection"], evaluation.get("neighbour_inspection", {})
            ),
            "## Sensitivity to k",
            "",
            "Each k is calibrated on its own, because the floor it is calibrated against "
            "is 1/k. The `min_weight` column is a result of the run, not a setting of it.",
            "",
            "| k | Topics | min_weight (floor) | Unassigned | Mean NPMI |",
            "|---:|---:|---:|---:|---:|",
            *[
                f"| {row['k']} | {row['topics']} | {row['min_weight']:.4f} "
                f"({row['min_weight_floor']:.4f}) | {row['unassigned_share']:.1%} | "
                f"{row['coherence_mean']:+.3f} |"
                for row in evaluation["k_sweep"]
            ],
            "",
            "## What is still missing",
            "",
            "- **Blinded human interpretability.** `intrusion_task.csv` holds "
            f"{evaluation['intrusion_tasks']} word-intrusion items: an opaque id, six "
            "words and a blank. Fill `intruder_guess` with the word that does not "
            "belong, then run `scripts/score_intrusion.py` — the answers live in "
            "`intrusion_key.csv`, which is the file not to open first. Items from both "
            "models are interleaved and their ids carry no arithmetic, so the task "
            "cannot be answered from `nmf.json` instead of from the words. It is a task, "
            "not a score: until a person has completed it, this gate is open. Generating "
            "a number here would be the same error §1.1 forbids for the lexicon audit — "
            "an automatic judgement recorded as a human verdict.",
            "- **A research question.** §4 requires one before any of this enters the "
            "release pipeline.",
            "",
            "## Reading",
            "",
            verdict,
            "",
            "The 2D projection written here is a diagnostic and not the exploratory map §4 "
            "permits: it is fitted after the clustering, nothing is clustered on it, no "
            "label comes from it, and it exists so that the claim it would otherwise "
            "invite can be measured and refused. Nothing in `web/` reads this directory, "
            "and `export_web.py` does not know it exists.",
            "",
        ]
    ) + "\n"


def build_verdict(
    nmf: dict,
    embedding: dict,
    stability_scores: dict,
    calibration: dict,
    equal_abstention: dict,
) -> str:
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

    if not calibration["binds"]:
        parts.append(
            "The baseline's abstention threshold calibrated to the floor 1/k: its topic "
            "weights are no more concentrated on this corpus than on the same words dealt "
            "at random, so an NMF assignment here is a label, not evidence."
        )
    else:
        parts.append(
            f"The baseline abstains on {nmf['unassigned_share']:.1%} at a threshold "
            f"calibrated against randomly dealt text ({calibration['min_weight']:.3f}, floor "
            f"{calibration['floor']:.3f}), against {embedding['unassigned_share']:.1%} for "
            "HDBSCAN."
        )

    matched_margin = (
        equal_abstention["embedding_coherence_mean"] - equal_abstention["nmf_coherence_mean"]
    )
    parts.append(
        "Forced to the same abstention rate as HDBSCAN "
        f"({equal_abstention['nmf_unassigned_share']:.1%}), the baseline scores "
        f"{equal_abstention['nmf_coherence_mean']:+.3f} NPMI, "
        + (
            f"still {abs(matched_margin):.3f} "
            + ("behind" if matched_margin > 0 else "ahead of")
            + " the embedding model."
            if abs(matched_margin) >= 0.005
            else "level with the embedding model."
        )
        + " Any coherence gap that survives only at unequal abstention is a difference in "
        "how much each model declined to answer, not in what it found."
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
    nmf_model = topics.fit_nmf(documents, k, seed)
    calibration = nmf_model.params["calibration"]
    min_weight = float(nmf_model.params["min_weight"])
    console.info(
        f"{len(nmf_model.topics)} topics, {nmf_model.unassigned_share:.1%} unassigned "
        f"({time.monotonic() - started:.0f}s)"
    )
    console.info(
        f"min_weight calibrated to {min_weight:.4f} — the {calibration['quantile']:.0%} "
        f"quantile of the same model on the corpus dealt at random "
        f"(floor 1/k = {calibration['floor']:.4f})"
    )
    if not calibration["binds"]:
        console.warn(
            "the calibrated threshold is at the floor: this NMF concentrates no more "
            "on the corpus than on randomly dealt words, so its assignments carry no "
            "evidence of topical structure"
        )
    elif nmf_model.unassigned_share > 0.5:
        console.warn(
            f"{nmf_model.unassigned_share:.0%} of documents fall below the calibrated "
            "threshold — read the abstention curve in nmf.json before reading the topics"
        )

    console.step("Embedding: UMAP into HDBSCAN")
    started = time.monotonic()
    embedding_model = topics.fit_embedding(vectors, documents, seed)
    console.info(
        f"{len(embedding_model.topics)} topics, {embedding_model.unassigned_share:.1%} "
        f"unassigned ({time.monotonic() - started:.0f}s)"
    )

    console.step("2D projection — a diagnostic, not a map")
    started = time.monotonic()
    coordinates = topics.project_2d(vectors, seed)
    console.info(f"{len(coordinates):,} points projected ({time.monotonic() - started:.0f}s)")
    projection = topics.projection_diagnostic(
        coordinates,
        embedding_model.reduced,
        projection_attributes(sample, nmf_model.labels, embedding_model.labels),
        seed=seed,
    )
    for name, block in projection["purity"].items():
        console.info(
            f"  {name}: {block['mean']:.1%} of the {projection['k']} nearest points in the "
            f"picture share it, against {block['base_rate']:.1%} at random"
            + (f" (x{block['lift']:.1f})" if block["lift"] else "")
        )
    agreement = projection["agreement"]
    console.info(
        f"  trustworthiness against the {agreement['dimensions']['clustered']}D reduction "
        f"{agreement['trustworthiness']:.3f}; {agreement['neighbours_lost_share']:.1%} of its "
        f"{agreement['k']} nearest neighbours are absent from the projection's "
        f"({agreement['points']:,} points"
        + (f", subsampled from {agreement['sample_points']:,}" if agreement["subsampled"] else "")
        + ")"
    )
    occasion = strongest(projection["purity"], OCCASION_ATTRIBUTES)
    subject = strongest(projection["purity"], SUBJECT_ATTRIBUTES)
    if (projection["purity"][occasion]["lift"] or 0.0) > (
        projection["purity"][subject]["lift"] or 0.0
    ):
        console.warn(
            f"the projection groups by {occasion} more strongly than by {subject} "
            f"(lift {projection['purity'][occasion]['lift']:.1f} against "
            f"{projection['purity'][subject]['lift']:.1f}) — the space has substantially "
            "recovered the occasion, and topics drawn from it are agenda items dressed as "
            "themes until something else shows otherwise"
        )

    console.step("Baseline at the embedding model's abstention rate")
    matched_weight = topics.threshold_for(
        topics.dominant_share(nmf_model.weights), embedding_model.unassigned_share
    )
    matched = topics.relabel(nmf_model, documents, matched_weight)
    console.info(
        f"min_weight {matched_weight:.4f} leaves {matched.unassigned_share:.1%} unassigned "
        f"against HDBSCAN's {embedding_model.unassigned_share:.1%}"
    )

    console.step("Stability under resampling")
    console.info(f"NMF (threshold held at {min_weight:.4f}):")
    nmf_stability = stability(
        lambda pos, s: topics.fit_nmf(
            [documents[i] for i in pos], k, s, min_weight=min_weight
        ).labels,
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
        # Each k is calibrated on its own. The share floor is 1/k, so carrying one
        # threshold across the sweep would compare k=15 at a line it cannot cross
        # with k=40 at a line that bites — which is the defect this sweep exists
        # to detect, reintroduced into the instrument detecting it.
        for candidate in K_SWEEP:
            model = nmf_model if candidate == k else topics.fit_nmf(documents, candidate, seed)
            coherence = topics.npmi_coherence(model.words, documents)
            k_sweep.append(
                {
                    "k": candidate,
                    "topics": len(model.topics),
                    "unassigned_share": round(model.unassigned_share, 4),
                    "coherence_mean": coherence["mean"],
                    "min_weight": model.params["min_weight"],
                    "min_weight_floor": model.params["min_weight_floor"],
                }
            )
            console.info(
                f"k={candidate}: {len(model.topics)} topics, "
                f"NPMI {coherence['mean']:+.3f}, {model.unassigned_share:.1%} unassigned "
                f"(min_weight {model.params['min_weight']:.4f}, "
                f"floor {model.params['min_weight_floor']:.4f})"
            )

    console.step("Building payloads")
    nmf_payload = model_payload(nmf_model, sample, documents, terms)
    embedding_payload = model_payload(embedding_model, sample, documents, terms)
    stability_scores = {"nmf": nmf_stability, "embedding": embedding_stability}
    intrusion = topics.blind(
        topics.word_intrusion(nmf_model.words, seed, model="nmf")
        + topics.word_intrusion(embedding_model.words, seed + 1, model="embedding"),
        seed + 2,
    )
    matched_coherence = topics.npmi_coherence(matched.words, documents)
    equal_abstention = {
        "target": round(embedding_model.unassigned_share, 4),
        "min_weight": round(matched_weight, 6),
        "nmf_unassigned_share": round(matched.unassigned_share, 4),
        "nmf_topics": len(matched.topics),
        "nmf_coherence_mean": matched_coherence["mean"],
        "nmf_coherence_min": matched_coherence["min"],
        "embedding_coherence_mean": embedding_payload["coherence"]["mean"],
    }
    console.step("Drawing the projection")
    figures = build_figures(coordinates, sample, embedding_model.labels)
    projection["figures"] = [description for _, _, description in figures]
    for name, payload, _ in figures:
        console.info(f"{name}: {len(payload) / 1024:.0f} KB")

    evaluation = {
        "sample_size": len(sample),
        "sample_seed": seed,
        "min_tokens": topics.MIN_TOKENS,
        "formulaic_document_frequency": FORMULAIC_DF,
        "calibration": calibration,
        "equal_abstention": equal_abstention,
        "stability": stability_scores,
        "k_sweep": k_sweep,
        "projection": projection,
        "neighbour_inspection": neighbour_inspection(),
        "intrusion_tasks": len(intrusion),
        "verdict": build_verdict(
            nmf_payload, embedding_payload, stability_scores, calibration, equal_abstention
        ),
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
            "nmf_min_weight": min_weight,
            "nmf_min_weight_rule": calibration["rule"],
            "release_artefact": False,
            "diagnostic": True,
            "purpose": PURPOSE,
            "projection_clustered_for_labels": False,
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
        artifacts.atomic_write_json(
            staged / "projection.json", {"meta": meta, **projection}, indent=2
        )
        for name, payload, _ in figures:
            artifacts.atomic_write_bytes(staged / name, payload)
        assignments.to_parquet(staged / "assignments.parquet", index=False, compression="zstd")
        write_csv(staged / "intrusion_task.csv", topics.intrusion_task(intrusion))
        write_csv(staged / "intrusion_key.csv", topics.intrusion_key(intrusion))
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
