"""Two topic models, and the evidence needed to distrust them.

docs/PLAN.md §4 does not ask for a topic model. It asks for a comparison — "at
least one transparent count-based baseline with one embedding-based approach on a
frozen sample" — and then for five kinds of evaluation before either is believed.
This module implements the comparison and the evaluation; 07_topics.py runs them
and writes the tables. Nothing here decides that a topic is real.

**The baseline is NMF over TF-IDF.** Every topic is a weighted list of words that
were literally counted, so a reader can check one against a concordance. It is
the thing the embedding model has to beat to justify itself.

**The embedding approach is UMAP into HDBSCAN**, labelled by class-based TF-IDF.
Its advantage is that it need not assign every document: HDBSCAN's noise label is
kept as topic -1 and reported as a headline number, which is the "explicit
unassigned/uncertain outcome rather than forced labels" §4 requires. NMF is given
the same escape hatch through a minimum document-topic weight, so the two models
are compared on equal terms rather than one being allowed to abstain and the
other forced to guess.

**That escape hatch has to be calibrated, not guessed.** A document's share is
its largest topic weight over the sum of them, and the largest of k numbers is
never below their mean, so the share has a hard floor at 1/k. A constant written
into the source — this module used 0.05 — is therefore unreachable at k=15
(floor 0.067), a rounding error above the floor at k=25, and a real constraint at
k=40: the same nominal threshold means three different things across the sweep it
is swept over. The first full run showed exactly what that produces, 0.0%
unassigned in every NMF fit against 15-23% for HDBSCAN. :func:`fit_nmf` now
derives the threshold from a null instead — see :func:`calibrate` — and
:func:`relabel` provides the second reading the comparison needs, both models at
the same abstention rate.

**Stability is one knob for both.** A seed drives a bootstrap resample of the
frozen sample *and* the model's own randomness, and agreement is measured with
the adjusted Rand index over the documents two runs share. This asks the question
a reader actually has — run it again, slightly differently, do the topics
survive? — rather than the easier question of whether a deterministic solver
returns its own answer twice. A model can be perfectly reproducible and still
have topics that dissolve under a 10% change of sample.

**Coherence is NPMI over this corpus**, not over an external reference. A topic
scores well when its words genuinely co-occur in Security Council speeches. That
also means a topic can score well by capturing the Council's formulaic register —
"I thank the Secretary-General for his briefing" is extremely coherent and says
nothing — which is why :func:`sensitivity` reports how much of each topic is
procedural language, and why the word-intrusion task exists for a human to catch
what a coherence number cannot.

The heavy dependencies (scikit-learn, umap-learn) are imported inside the
functions that need them. The test suite, CI and steps 00-05 install neither.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .lexical import TOKEN_RE

#: Same boundaries as the sliced tables in 05_lexical.py — round decades, chosen
#: before any result was seen. Change both together or the two chapters of the
#: analysis stop describing the same periods.
PERIODS: list[tuple[str, int, int]] = [
    ("1992-1999", 1992, 1999),
    ("2000-2009", 2000, 2009),
    ("2010-2019", 2010, 2019),
    ("2020-2023", 2020, 2023),
]

#: Documents shorter than this are procedural ("The meeting rose at 1 p.m.").
#: A quarter of the corpus is under 50 words; letting that in produces a large,
#: perfectly coherent topic of Council stage directions.
MIN_TOKENS = 120

#: Label for a document the model declines to assign.
UNASSIGNED = -1

#: Where NMF's abstention threshold is read off the null distribution. At 0.95, a
#: document is assigned only if its best topic is more concentrated than 95% of
#: documents manage under a model fitted to text with no co-occurrence structure
#: at all. Declared here, before any run, because a threshold chosen after seeing
#: which one produced an agreeable number of topics is not a threshold.
NULL_QUANTILE = 0.95

#: Thresholds the abstention curve is reported at. The point is not that any of
#: them is right: it is that a reader can see how much the headline "unassigned"
#: figure depends on where the line was drawn, instead of taking one number on
#: trust.
ABSTENTION_CURVE = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.75]


def assign_period(years: pd.Series) -> pd.Series:
    """Label each year with its period, or `outside` if the ranges miss it."""
    out = pd.Series("outside", index=years.index, dtype="object")
    for label, first, last in PERIODS:
        out[years.between(first, last)] = label
    return out


def frozen_sample(frame: pd.DataFrame, size: int, seed: int, min_tokens: int = MIN_TOKENS) -> pd.DataFrame:
    """A deterministic, period-stratified sample of substantial speeches.

    Frozen means two things. The rows depend only on (input, size, seed,
    min_tokens), so the sample can be rebuilt and cited; and the same sample
    feeds both models, so a difference between them is a difference between
    models rather than between the documents they happened to see.

    Everything is ordered by ``row_id`` before the draw. Ordering by position
    instead would make the sample a function of how the parquet happened to be
    written — reproducible on this machine, and quietly different after any step
    upstream changed its row order.

    Allocation is proportional to each period's share of eligible speeches, so
    the sample does not quietly over-represent the busy 2010s.
    """
    if size < 1:
        raise ValueError("size must be at least 1")
    if "row_id" not in frame.columns:
        raise KeyError("frozen_sample needs `row_id`; it is what makes the draw reproducible")
    eligible = frame[frame["tokens"] >= min_tokens]
    if eligible.empty:
        raise ValueError(f"no speech has {min_tokens} tokens or more")

    periods = assign_period(eligible["year"])
    take = min(size, len(eligible))
    rng = np.random.default_rng(seed)

    picked: list[pd.Index] = []
    counts = periods.value_counts()
    for label in [p[0] for p in PERIODS]:
        available = counts.get(label, 0)
        if not available:
            continue
        wanted = min(round(take * available / len(eligible)), available)
        if wanted < 1:
            continue
        # Order by row_id, not by position: the draw must be a function of the
        # corpus, not of the order a parquet writer happened to use.
        pool = eligible[periods == label].sort_values("row_id").index.to_numpy()
        picked.append(pd.Index(rng.choice(pool, size=wanted, replace=False)))

    chosen = pd.Index(np.concatenate([p.to_numpy() for p in picked]))
    return frame.loc[chosen].sort_values("row_id")


def resample(index: np.ndarray, seed: int, fraction: float = 0.9) -> np.ndarray:
    """Positions of a deterministic subsample, for the stability battery."""
    rng = np.random.default_rng(seed)
    keep = max(2, round(len(index) * fraction))
    return np.sort(rng.choice(len(index), size=keep, replace=False))


# --- Tokens and topic words ------------------------------------------------


def tokenise(texts: list[str], stopwords: frozenset[str]) -> list[list[str]]:
    """Lowercase word tokens, minus the stoplist.

    Uses the same TOKEN_RE as the lexicometry in 05, so "what counts as a word"
    has one definition across the project.
    """
    return [[w for w in TOKEN_RE.findall(text.lower()) if w not in stopwords] for text in texts]


def ctfidf(
    documents: list[list[str]], labels: np.ndarray, top_n: int = 12, min_count: int = 3
) -> dict[int, list[tuple[str, float]]]:
    """Class-based TF-IDF: the words that distinguish each topic from the rest.

    Every document of a topic is treated as one long document, and a word is
    scored by its frequency there against its frequency everywhere. Without that
    second half, every topic is labelled `council`, `security` and `states`.
    """
    per_class: dict[int, Counter[str]] = {}
    overall: Counter[str] = Counter()
    for tokens, label in zip(documents, labels, strict=True):
        if label == UNASSIGNED:
            continue
        per_class.setdefault(int(label), Counter()).update(tokens)
        overall.update(tokens)
    if not per_class:
        return {}

    sizes = {label: sum(counts.values()) for label, counts in per_class.items()}
    average = sum(sizes.values()) / len(sizes)

    out: dict[int, list[tuple[str, float]]] = {}
    for label, counts in sorted(per_class.items()):
        total = sizes[label] or 1
        scored = [
            (word, (count / total) * math.log(1 + average / overall[word]))
            for word, count in counts.items()
            if count >= min_count
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        out[label] = [(w, round(s, 6)) for w, s in scored[:top_n]]
    return out


# --- The two models --------------------------------------------------------


@dataclass(frozen=True)
class TopicModel:
    """One fitted model, in the form the evaluation needs.

    `weights` is the document-topic matrix where the model has one. It is kept so
    that a labelling can be redrawn at a different abstention threshold without
    refitting — which is what makes the equal-abstention comparison affordable,
    and what stops "we tried a few thresholds" from meaning "we ran the model
    until we liked it".
    """

    name: str
    labels: np.ndarray
    words: dict[int, list[tuple[str, float]]]
    params: dict[str, object] = field(default_factory=dict)
    weights: np.ndarray | None = None

    @property
    def topics(self) -> list[int]:
        return sorted({int(label) for label in self.labels if label != UNASSIGNED})

    @property
    def unassigned(self) -> int:
        return int((self.labels == UNASSIGNED).sum())

    @property
    def unassigned_share(self) -> float:
        return self.unassigned / len(self.labels) if len(self.labels) else 0.0


def dominant_share(weights: np.ndarray) -> np.ndarray:
    """Each document's largest topic weight as a share of its total.

    Bounded below by 1/k, because the largest of k non-negative numbers is never
    smaller than their mean. A document the model gave no weight at all — its
    vocabulary pruned away entirely — scores 0 and is unassignable, which is the
    right answer rather than a division by zero.
    """
    totals = weights.sum(axis=1)
    return np.divide(
        weights.max(axis=1), totals, out=np.zeros_like(totals, dtype=np.float64), where=totals > 0
    )


def deal_at_random(documents: list[list[str]], seed: int) -> list[list[str]]:
    """The same words, the same document lengths, no co-occurrence.

    Every token in the sample is pooled, shuffled and dealt back out into
    documents of the original lengths. Unigram frequencies and length
    distribution survive exactly; what does not survive is any tendency of two
    words to appear in the same speech, which is the only thing a topic model is
    entitled to find. Documents built this way are the null that
    :func:`calibrate` measures concentration against.
    """
    rng = np.random.default_rng(seed)
    pool = [word for tokens in documents for word in tokens]
    order = rng.permutation(len(pool))
    dealt: list[list[str]] = []
    cursor = 0
    for tokens in documents:
        window = order[cursor : cursor + len(tokens)]
        dealt.append([pool[i] for i in window])
        cursor += len(tokens)
    return dealt


def calibrate(
    shares: np.ndarray,
    null_shares: np.ndarray,
    k: int,
    quantile: float = NULL_QUANTILE,
) -> dict[str, object]:
    """Where to draw NMF's abstention line, and the evidence for drawing it there.

    The rule, fixed before the run: assign a document only when its best topic is
    more concentrated than the same model achieves on structureless text. The
    threshold is the `quantile` of the null share distribution, so it moves with
    k, with the vocabulary and with the sample, rather than being a constant that
    happens to be inert at one k and binding at another.

    Everything needed to disagree with the choice is returned alongside it: the
    floor 1/k below which no threshold can bite, the null and observed share
    distributions, and the share of documents left unassigned across a range of
    thresholds.
    """
    floor = 1.0 / k
    threshold = float(np.quantile(null_shares, quantile))

    def spread(values: np.ndarray) -> dict[str, float]:
        percentiles = np.quantile(values, [0.05, 0.5, 0.9, 0.95, 0.99])
        return {
            "p05": round(float(percentiles[0]), 4),
            "median": round(float(percentiles[1]), 4),
            "p90": round(float(percentiles[2]), 4),
            "p95": round(float(percentiles[3]), 4),
            "p99": round(float(percentiles[4]), 4),
            "mean": round(float(values.mean()), 4),
        }

    return {
        "rule": (
            f"share >= the {quantile:.0%} quantile of the same model fitted to the "
            "corpus dealt at random"
        ),
        "quantile": quantile,
        "min_weight": round(threshold, 6),
        "floor": round(floor, 6),
        "binds": bool(threshold > floor),
        "null_shares": spread(null_shares),
        "observed_shares": spread(shares),
        "unassigned_share": round(float((shares < threshold).mean()), 4),
        # The calibrated threshold joins the declared grid so the table brackets
        # it. A curve that starts above the line actually used reads as though
        # the two disagree.
        "curve": [
            {
                "min_weight": round(point, 6),
                "unassigned_share": round(float((shares < point).mean()), 4),
                "chosen": point == threshold,
            }
            for point in sorted({*ABSTENTION_CURVE, threshold})
            if point >= floor
        ],
    }


def threshold_for(shares: np.ndarray, unassigned_share: float) -> float:
    """The threshold that leaves `unassigned_share` of documents unassigned.

    Used to read the baseline at the embedding model's abstention rate. It is a
    second reading, never the primary one: a threshold defined by another model's
    noise share tells you what NMF looks like when forced to be as reticent as
    HDBSCAN, which is a fair comparison and a bad definition.
    """
    if not 0.0 <= unassigned_share < 1.0:
        raise ValueError(f"unassigned share must be in [0, 1), got {unassigned_share}")
    if unassigned_share == 0.0:
        return 0.0
    return float(np.quantile(shares, unassigned_share))


def fit_nmf(
    documents: list[list[str]],
    k: int,
    seed: int,
    *,
    min_df: int = 5,
    max_df: float = 0.5,
    max_features: int = 50_000,
    min_weight: float | None = None,
    quantile: float = NULL_QUANTILE,
) -> TopicModel:
    """NMF over TF-IDF — the transparent baseline.

    `min_weight` is the abstention: a document whose best topic carries less than
    that share of its total topic weight is left unassigned, so the baseline is
    allowed the same "I don't know" that HDBSCAN gets for free. Without it the
    comparison rewards the embedding model for a candour the baseline was never
    offered.

    Left as None it is calibrated against a null fitted on the same vocabulary —
    one extra factorisation, and the difference between a threshold and a number
    somebody once typed. Pass a float to hold it fixed, which is what the
    stability battery does: a threshold recalibrated inside every refit would
    make the adjusted Rand index measure the threshold moving as much as the
    topics moving.
    """
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectoriser = TfidfVectorizer(
        min_df=min_df,
        max_df=max_df,
        max_features=max_features,
        # The documents are pre-tokenised above; splitting on space here keeps
        # this vectoriser from applying a second, different idea of a word.
        analyzer=lambda text: text.split(),
    )
    matrix = vectoriser.fit_transform([" ".join(tokens) for tokens in documents])

    # init="random" so that `seed` genuinely moves the solution. A deterministic
    # init would make this model reproduce itself exactly, which is a different
    # and much weaker claim than the topics being robust.
    def factorise(target):
        model = NMF(n_components=k, init="random", random_state=seed, max_iter=600)
        return model.fit_transform(target), model

    weights, model = factorise(matrix)
    shares = dominant_share(weights)

    calibration: dict[str, object] | None = None
    if min_weight is None:
        # `transform`, not `fit_transform`: the null must be scored through the
        # real corpus's vocabulary and idf, or the two share distributions are
        # not measured on the same axis and the comparison means nothing.
        null = vectoriser.transform(
            [" ".join(tokens) for tokens in deal_at_random(documents, seed)]
        )
        null_weights, _ = factorise(null)
        calibration = calibrate(shares, dominant_share(null_weights), k, quantile)
        min_weight = float(calibration["min_weight"])

    labels = np.where(shares >= min_weight, weights.argmax(axis=1), UNASSIGNED).astype(np.int64)

    return TopicModel(
        name="nmf",
        labels=labels,
        words=ctfidf(documents, labels),
        params={
            "k": k,
            "seed": seed,
            "min_df": min_df,
            "max_df": max_df,
            "max_features": max_features,
            "min_weight": round(float(min_weight), 6),
            "min_weight_floor": round(1.0 / k, 6),
            "min_weight_calibrated": calibration is not None,
            "calibration": calibration,
            "vocabulary": int(matrix.shape[1]),
            "reconstruction_error": round(float(model.reconstruction_err_), 4),
        },
        weights=weights,
    )


def relabel(model: TopicModel, documents: list[list[str]], min_weight: float) -> TopicModel:
    """The same factorisation, read at a different abstention threshold.

    No refit, so this cannot become a search for a flattering result: the topics
    are fixed and only the line between "assigned" and "unassigned" moves.
    """
    if model.weights is None:
        raise ValueError(f"{model.name} keeps no document-topic weights to re-threshold")
    shares = dominant_share(model.weights)
    labels = np.where(
        shares >= min_weight, model.weights.argmax(axis=1), UNASSIGNED
    ).astype(np.int64)
    return TopicModel(
        name=model.name,
        labels=labels,
        words=ctfidf(documents, labels),
        params={**model.params, "min_weight": round(float(min_weight), 6), "calibration": None},
        weights=model.weights,
    )


def fit_embedding(
    vectors: np.ndarray,
    documents: list[list[str]],
    seed: int,
    *,
    components: int = 5,
    neighbours: int = 15,
    min_cluster_size: int = 60,
) -> TopicModel:
    """UMAP into HDBSCAN over the speech vectors, labelled by c-TF-IDF.

    The reduction is to 5 dimensions, not 2: clustering in the space built for a
    picture optimises for a picture. Any 2D map that 07 emits is a separate,
    explicitly exploratory projection — see docs/PLAN.md §4 on what a UMAP
    distance is not evidence of.
    """
    import umap
    from sklearn.cluster import HDBSCAN

    # `random_state` makes UMAP single-threaded — it warns about this — and that
    # is the trade being made deliberately: a topic model nobody can reproduce is
    # not worth the cores it saved.
    reducer = umap.UMAP(
        n_components=components,
        n_neighbors=neighbours,
        min_dist=0.0,
        metric="cosine",
        random_state=seed,
    )
    reduced = reducer.fit_transform(vectors)

    # `copy` defaults to False today and to True in scikit-learn 1.10, which the
    # supported range spans. Setting it means the same behaviour either side of
    # that change, and no clustering step that mutates its own input.
    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean", copy=True)
    labels = clusterer.fit_predict(reduced).astype(np.int64)

    return TopicModel(
        name="embedding",
        labels=labels,
        words=ctfidf(documents, labels),
        params={
            "seed": seed,
            "umap_components": components,
            "umap_neighbours": neighbours,
            "min_cluster_size": min_cluster_size,
            "dimensions": int(vectors.shape[1]),
        },
    )


# --- Evaluation ------------------------------------------------------------


def adjusted_rand(a: np.ndarray, b: np.ndarray) -> float:
    """Adjusted Rand index between two labellings of the same documents.

    Written out rather than imported so the stability battery is testable in an
    environment without scikit-learn — which is every environment except the
    cluster. Unassigned is treated as an ordinary label: two runs that agree a
    document is noise agree about that document.
    """
    if len(a) != len(b):
        raise ValueError(f"labellings differ in length: {len(a)} vs {len(b)}")
    n = len(a)
    if n < 2:
        return 1.0

    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    table = np.zeros((ai.max() + 1, bi.max() + 1), dtype=np.int64)
    np.add.at(table, (ai, bi), 1)

    def pairs(counts: np.ndarray) -> float:
        return float((counts * (counts - 1) // 2).sum())

    index = pairs(table)
    expected_a = pairs(table.sum(axis=1))
    expected_b = pairs(table.sum(axis=0))
    total = n * (n - 1) / 2
    expected = expected_a * expected_b / total
    maximum = (expected_a + expected_b) / 2
    if maximum == expected:
        return 1.0
    return float((index - expected) / (maximum - expected))


def npmi_coherence(
    topic_words: dict[int, list[tuple[str, float]]],
    documents: list[list[str]],
    top_n: int = 10,
) -> dict[str, object]:
    """C_NPMI coherence of each topic, over the documents being modelled.

    Normalised PMI over document-level co-occurrence, averaged across the pairs
    of a topic's top words. Bounded in [-1, 1]; around 0 means the words are no
    more likely together than chance. High coherence is necessary, not
    sufficient — the Council's formulaic openings are highly coherent and empty,
    which is what :func:`sensitivity` and the intrusion task are there to catch.
    """
    # A model that assigned nothing still has to report a coherence block with
    # every key the callers read. Returning a short dict here means a run that
    # abstains completely fails while writing its note, hours after the fact.
    if not topic_words:
        return {
            "per_topic": {},
            "mean": 0.0,
            "min": 0.0,
            "top_n": top_n,
            "documents": len(documents),
        }

    wanted = {w for words in topic_words.values() for w, _ in words[:top_n]}
    present = [set(tokens) & wanted for tokens in documents]
    total = max(len(documents), 1)

    counts: Counter[str] = Counter()
    for tokens in present:
        counts.update(tokens)

    joint: Counter[tuple[str, str]] = Counter()
    for tokens in present:
        ordered = sorted(tokens)
        for i, first in enumerate(ordered):
            for second in ordered[i + 1 :]:
                joint[(first, second)] += 1

    per_topic: dict[str, float] = {}
    for label, words in topic_words.items():
        terms = [w for w, _ in words[:top_n]]
        scores = []
        for i, first in enumerate(terms):
            for second in terms[i + 1 :]:
                key = (first, second) if first < second else (second, first)
                # +1 smoothing: an unobserved pair is evidence against the
                # topic, not a division by zero to be dropped from the mean.
                # Clamped at 1.0, because the smoothing can push a pair present
                # in every document past a probability of one.
                p_joint = min((joint.get(key, 0) + 1) / total, 1.0)
                p_first = min((counts.get(first, 0) + 1) / total, 1.0)
                p_second = min((counts.get(second, 0) + 1) / total, 1.0)
                if p_joint >= 1.0:
                    # Two words that share every document. NPMI tends to +1 here
                    # and the formula tends to 0/0 — a topic of Council boilerplate
                    # would otherwise end a run with a ZeroDivisionError.
                    scores.append(1.0)
                else:
                    scores.append(math.log(p_joint / (p_first * p_second)) / -math.log(p_joint))
        per_topic[str(label)] = round(float(np.mean(scores)) if scores else 0.0, 4)

    values = list(per_topic.values())
    return {
        "per_topic": per_topic,
        "mean": round(float(np.mean(values)), 4) if values else 0.0,
        "min": round(float(np.min(values)), 4) if values else 0.0,
        "top_n": top_n,
        "documents": len(documents),
    }


def sensitivity(frame: pd.DataFrame, labels: np.ndarray, formulaic: frozenset[str]) -> dict[str, object]:
    """What each topic is made of, besides its subject.

    Three ways a topic model of this corpus goes wrong without looking wrong:
    a topic that is really a length band, a topic that is really the Council's
    procedural register, and a topic that is really one year of one crisis. Each
    gets a column here so a reader can see it rather than infer it.
    """
    table = frame.assign(topic=labels)
    periods = assign_period(table["year"])
    rows = []
    for label, block in table.groupby("topic", sort=True):
        mask = table["topic"] == label
        share = periods[mask].value_counts(normalize=True)
        rows.append(
            {
                "topic": int(label),
                "documents": len(block),
                "median_tokens": int(block["tokens"].median()),
                "p90_tokens": int(block["tokens"].quantile(0.9)),
                "formulaic_share": round(float(block["formulaic_share"].mean()), 4)
                if "formulaic_share" in block
                else None,
                "dominant_period": str(share.idxmax()) if len(share) else "",
                "dominant_period_share": round(float(share.max()), 4) if len(share) else 0.0,
                "dominant_year": int(block["year"].mode().iloc[0]) if len(block) else 0,
                "genocide_bearing_share": round(float(block["has_genocide"].mean()), 4)
                if "has_genocide" in block
                else None,
            }
        )
    return {
        "formulaic_terms": len(formulaic),
        "by_topic": rows,
        "length_correlation": round(_length_correlation(table), 4),
    }


def _length_correlation(table: pd.DataFrame) -> float:
    """Spearman correlation between topic identity and speech length.

    Computed on topic *median* length against topic rank, which is a blunt
    instrument on purpose: it is a smoke alarm for "the model sorted by length",
    not a statistic anyone should report.
    """
    assigned = table[table["topic"] != UNASSIGNED]
    if assigned["topic"].nunique() < 3:
        return 0.0
    medians = assigned.groupby("topic")["tokens"].median()
    return float(medians.rank().corr(pd.Series(medians.index, index=medians.index).rank()))


def word_intrusion(
    topic_words: dict[int, list[tuple[str, float]]], seed: int, words_shown: int = 5
) -> list[dict[str, object]]:
    """A blinded interpretability task, as rows for a human to fill in.

    Each row shows a topic's top words with one word from a different topic
    mixed in. A reader who can reliably pick the intruder is a reader for whom
    the topic means something. This emits the task and its answer key; it does
    not emit a score, because the score does not exist until a person has sat
    down with the file. docs/PLAN.md §4 asks for blinded human interpretability,
    and a number invented here would be exactly the "AI review presented as a
    human verdict" §1.1 forbids.
    """
    labels = sorted(topic_words)
    if len(labels) < 2:
        return []
    rng = np.random.default_rng(seed)
    tasks = []
    for label in labels:
        own = [w for w, _ in topic_words[label][:words_shown]]
        if len(own) < words_shown:
            continue
        others = [other for other in labels if other != label]
        source = int(rng.choice(others))
        # An intruder from the *tail* of another topic: a word that is
        # characteristic of nothing much is too easy to spot.
        pool = [w for w, _ in topic_words[source] if w not in own]
        if not pool:
            continue
        intruder = str(rng.choice(pool))
        shown = [*own, intruder]
        order = rng.permutation(len(shown))
        tasks.append(
            {
                "topic": label,
                "words": [shown[i] for i in order],
                "intruder": intruder,
                "intruder_position": int(np.argmax(order == len(shown) - 1)) + 1,
                "intruder_from_topic": source,
                "verdict": "",
            }
        )
    return tasks
