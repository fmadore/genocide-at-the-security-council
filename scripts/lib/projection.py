"""The 2D projection of the speech vectors: a diagnostic, not a map.

:func:`project_2d` and :func:`projection_diagnostic` build a 2D UMAP and then
measure it, and the purpose is inverted from the usual one: the figure exists to
argue *against* a thematic reading of the embedding space, not to support one.
Nothing is clustered on those coordinates and no label is derived from them; the
five-dimensional reduction in :func:`lib.topics.fit_embedding` is untouched. What
the diagnostic reports is neighbourhood purity by speaker, year and period beside
purity by topic, each against the base rate a random neighbour would give, plus
how far the picture has drifted from the space that was actually clustered. If
purity by speaker greatly exceeds purity by topic, the picture is a picture of
speakers — and §4's warning that a topic model over this space would return
agenda items dressed as themes becomes a measurement rather than an assertion.

The module imports nothing from the topic models. Step 07 scores the picture
against its topics, and step 21 measures its own projection with
:func:`projection_agreement`, which needs no topic at all.

umap-learn and matplotlib are imported inside the functions that need them, so
the test suite and CI, which install neither, can check every statistic here.
"""

from __future__ import annotations

import io
import textwrap
from collections.abc import Collection, Iterator

import numpy as np
import pandas as pd

# --- The 2D projection: a diagnostic, not a map ----------------------------
#
# Everything below builds a picture in order to argue against it. Read
# :data:`PROJECTION_PURPOSE` before reading the numbers, and note what is absent:
# no function here returns a label, and none of them is reachable from
# :func:`lib.topics.fit_embedding` or :func:`lib.topics.ctfidf`.


#: Neighbours counted when measuring what the 2D picture puts together. Large
#: enough that one coincidence cannot move the figure, small enough to describe
#: the local neighbourhood an eye actually reads off a scatter plot. Deliberately
#: not UMAP's own `n_neighbors`: scoring a projection at the size it was
#: optimised for is scoring a fit against its own objective.
PROJECTION_K = 25

#: Points the 2D-against-5D agreement is measured over. Trustworthiness needs the
#: rank of every point against every other, an n x n matrix — 400 million entries
#: at the 20,000-point frozen sample. The subsample is drawn from the run's seed
#: and its size is written into the artefact, because an approximation a reader
#: cannot see is indistinguishable from a result.
AGREEMENT_SAMPLE = 4_000

#: How a document the clustering declined to assign is named in a legend, and
#: the name a figure gives everything outside its colour budget. Both are drawn
#: in grey: neither is a category anyone should read a meaning into.
UNASSIGNED_LABEL = "unassigned"
OTHER_LABEL = "other"

#: Fixed so two runs over the same data produce the same picture, and so a figure
#: pasted into a draft can be matched back to the run that made it.
FIGURE_SIZE = (8.0, 8.0)
FIGURE_DPI = 150
MARKER_SIZE = 2.0
MARKER_ALPHA = 0.25
MUTED_COLOUR = "#b4b4b4"

#: Written into the PNG rather than a timestamp, so the bytes of a figure depend
#: on the data and not on when it was drawn. It names the function by the path
#: `lib.topics` still re-exports, so that a figure drawn now has the same bytes
#: as every figure already drawn from the same data.
FIGURE_METADATA = {"Software": "scripts/07_topics.py via lib.topics.draw_projection", "Date": None}

#: The axes are not quantities and the figure has to say so where the figure is
#: looked at, not in a methods note nobody opens.
AXIS_LABELS = (
    "UMAP dimension 1 — arbitrary units, not a quantity",
    "UMAP dimension 2 — arbitrary units, not a quantity",
)

#: Travels inside `projection.json` so the file cannot be separated from the
#: argument it belongs to.
PROJECTION_PURPOSE = (
    "Diagnostic evidence, not a result and not a map of topics. A 2D UMAP over "
    "the same frozen-sample vectors, fitted after the clustering and never used "
    "for it: no cluster is fitted on these coordinates and no topic label is "
    "derived from them. It exists as evidence *against* reading this embedding "
    "space thematically — the neighbourhood purities below measure how much of "
    "what a reader would see in the picture is the same speaker and the same "
    "occasion rather than the same subject, and the agreement block measures how "
    "far the picture has drifted from the five-dimensional space the clustering "
    "actually happened in."
)

#: Printed under every figure. docs/PLAN.md §4 and §7 both require the caveat to
#: travel with the image rather than with the prose around it.
PROJECTION_CAVEAT = (
    "Diagnostic only: no cluster is fitted on these coordinates and no topic "
    "label is derived from them. Distance and direction on a UMAP plot are not "
    "evidence of influence or of categorical separation."
)


def project_2d(
    vectors: np.ndarray,
    seed: int,
    *,
    neighbours: int = 15,
    min_dist: float = 0.1,
) -> np.ndarray:
    """A 2D UMAP over the speech vectors, for the diagnostic and nothing else.

    Separate from :func:`fit_embedding`, which reduces to five dimensions and is
    the only reduction anything is clustered in. Same vectors, same seed, same
    cosine metric, so the picture is of the run it belongs to; `min_dist` is 0.1
    rather than the clustering fit's 0.0, because a plot with every point stacked
    on its neighbours shows nothing — which is itself a reason this space must
    not be the one anything is fitted in.

    Returns coordinates. It does not return, and cannot produce, a label.
    """
    import umap

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=neighbours,
        min_dist=min_dist,
        metric="cosine",
        random_state=seed,
    )
    return np.asarray(reducer.fit_transform(vectors), dtype=np.float64)


def _distance_blocks(points: np.ndarray) -> Iterator[tuple[int, int, np.ndarray]]:
    """Squared Euclidean distances from every point to every point, by row block.

    The full matrix is n x n — 3.2 GB at the 20,000-point sample — so rows are
    produced a block at a time, sized to hold the intermediate difference array
    in a few tens of megabytes. Squared distances rather than distances: the
    square root is monotonic, so it changes no ordering and no rank, and skipping
    it removes one source of floating-point noise from a comparison of ties.
    """
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.ndim != 2:
        raise ValueError(f"expected a 2D array of coordinates, got shape {coordinates.shape}")
    n, dimensions = coordinates.shape
    block = max(1, 4_000_000 // max(n * dimensions, 1))
    for start in range(0, n, block):
        stop = min(start + block, n)
        difference = coordinates[start:stop, None, :] - coordinates[None, :, :]
        yield start, stop, np.einsum("ijk,ijk->ij", difference, difference)


def nearest_neighbours(points: np.ndarray, k: int) -> np.ndarray:
    """Indices of each point's `k` nearest neighbours, itself excluded.

    Ordered by a stable sort, so ties are broken by index rather than by whatever
    order a partition happened to leave them in: the same coordinates give the
    same neighbourhood on every machine and every numpy build.

    `k` is clamped to n-1. Asking for more neighbours than there are other points
    returns every other point rather than raising — a smoke run, a test fixture
    and a period with few speeches all reach that case long before a real sample
    does, and an IndexError hours into a job is a poor way to learn it.
    """
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.ndim != 2:
        raise ValueError(f"expected a 2D array of coordinates, got shape {coordinates.shape}")
    n = len(coordinates)
    k = max(0, min(int(k), n - 1))
    if k == 0:
        return np.empty((n, 0), dtype=np.int64)

    out = np.empty((n, k), dtype=np.int64)
    for start, stop, distance in _distance_blocks(coordinates):
        distance[np.arange(stop - start), np.arange(start, stop)] = np.inf
        out[start:stop] = np.argsort(distance, axis=1, kind="stable")[:, :k]
    return out


def _rank_matrix(points: np.ndarray) -> np.ndarray:
    """`ranks[i, j]` is how far j sits from i in the ordering: 0 for i itself.

    The nearest other point ranks 1, so the k nearest are exactly the points
    ranking k or below — which is what makes the trustworthiness sum a comparison
    against `k` and nothing else.
    """
    coordinates = np.asarray(points, dtype=np.float64)
    n = len(coordinates)
    ranks = np.empty((n, n), dtype=np.int32)
    positions = np.arange(n, dtype=np.int32)[None, :]
    for start, stop, distance in _distance_blocks(coordinates):
        distance[np.arange(stop - start), np.arange(start, stop)] = -np.inf
        order = np.argsort(distance, axis=1, kind="stable")
        np.put_along_axis(ranks[start:stop], order, positions, axis=1)
    return ranks


def neighbourhood_purity(neighbours: np.ndarray, values: object) -> dict[str, object]:
    """How often a point's neighbours share one of its attributes, against chance.

    `mean` is the average over points of the share of that point's neighbours
    carrying the same value. `base_rate` is what the same average would be if the
    neighbours were drawn uniformly from the other points: for a point whose
    value occurs c times among n, exactly (c - 1) / (n - 1).

    The two are reported together, and `lift` is their ratio, because a purity of
    0.55 is either remarkable or expected and only the second number says which.
    It is the same discipline 06 applies to its neighbour inspection, for the
    same reason.

    A missing value is a category like any other and is counted in `missing`
    rather than dropped. Dropping it would change the denominator of the base
    rate without changing the purity, which is the one way to make this
    comparison lie.
    """
    # Through a Series first, so a plain list, a numpy array and a nullable
    # pandas column all reach `factorize` as the one thing it accepts.
    column = pd.Series(values)
    codes, uniques = pd.factorize(column, use_na_sentinel=False)
    n = len(codes)
    neighbours = np.asarray(neighbours, dtype=np.int64)
    if neighbours.shape[0] != n:
        raise ValueError(
            f"{neighbours.shape[0]} neighbourhoods for {n} values — the attribute and the "
            "projection describe different documents"
        )
    k = int(neighbours.shape[1])
    missing = int(column.isna().sum())

    if n < 2 or k == 0:
        return {
            "mean": 0.0,
            "base_rate": 0.0,
            "lift": None,
            "k": k,
            "points": n,
            "distinct_values": len(uniques),
            "missing": missing,
        }

    same = codes[neighbours] == codes[:, None]
    counts = np.bincount(codes, minlength=len(uniques))
    mean = float(same.mean())
    base = float(((counts[codes] - 1) / (n - 1)).mean())
    return {
        "mean": round(mean, 4),
        "base_rate": round(base, 4),
        "lift": round(mean / base, 2) if base > 0 else None,
        "k": k,
        "points": n,
        "distinct_values": len(uniques),
        "missing": missing,
    }


def neighbour_loss(clustered: np.ndarray, projected: np.ndarray) -> float:
    """Share of each point's neighbours in one space that are absent from the other.

    The legible half of the agreement measurement, and the one worth quoting: a
    trustworthiness of 0.87 means little to a reader, whereas "two in five of the
    points the clustering called neighbours are not neighbours in the picture" is
    a sentence. Set membership only — rank order is what
    :func:`trustworthiness` is for.
    """
    clustered = np.asarray(clustered, dtype=np.int64)
    projected = np.asarray(projected, dtype=np.int64)
    if clustered.shape[0] != projected.shape[0]:
        raise ValueError(
            f"the two neighbourhoods describe different point counts: "
            f"{clustered.shape[0]} vs {projected.shape[0]}"
        )
    if clustered.shape[1] == 0:
        return 0.0
    found = (clustered[:, :, None] == projected[:, None, :]).any(axis=2)
    return float(1.0 - found.mean())


def trustworthiness(clustered: np.ndarray, projected: np.ndarray, k: int) -> float:
    """How much of the 2D neighbourhood is an artefact of the 2D fit.

    The standard measure (Venna and Kaski): every neighbour the projection gives
    a point that the original space did not is charged the number of ranks it was
    promoted by, and the total is normalised so that a projection preserving
    every k-neighbourhood scores 1.0 and the worst possible reordering scores
    0.0.

        T = 1 - 2 / (n k (2n - 3k - 1)) * sum_i sum_{j in U_i} (rank(i, j) - k)

    where U_i is the set of points among i's k nearest in the projection that are
    not among its k nearest in the original space, and rank(i, j) is j's rank
    from i in the original space, counting from 1.

    Written out in numpy rather than imported from scikit-learn for the same
    reason as :func:`adjusted_rand`: the evaluation has to be checkable in an
    environment that has neither the cluster's packages nor its data.

    `k` is clamped to the largest value the normalisation admits, k < (2n-1)/3,
    so a small sample returns a number rather than a division by zero.
    """
    high = np.asarray(clustered, dtype=np.float64)
    low = np.asarray(projected, dtype=np.float64)
    if len(high) != len(low):
        raise ValueError(
            f"the two spaces describe different point counts: {len(high)} vs {len(low)}"
        )
    n = len(high)
    if n < 3:
        return 1.0
    k = max(1, min(int(k), n - 2, (2 * n - 2) // 3))

    ranks = _rank_matrix(high)
    promoted = np.take_along_axis(ranks, nearest_neighbours(low, k), axis=1) - k
    penalty = float(np.clip(promoted, 0, None).sum())
    return 1.0 - 2.0 * penalty / (n * k * (2 * n - 3 * k - 1))


def projection_agreement(
    clustered: np.ndarray,
    projected: np.ndarray,
    *,
    seed: int,
    k: int = PROJECTION_K,
    max_points: int = AGREEMENT_SAMPLE,
) -> dict[str, object]:
    """How far the picture is from the space the clustering happened in.

    Two numbers over the same subsample: trustworthiness, and the share of each
    point's k nearest neighbours in the clustered space that are missing from its
    k nearest in the projection. Both answer the question a thematic map would
    beg — points sharing a cluster can land far apart in an independent 2D fit,
    and points sitting together in the picture need not share anything.

    The subsample is deterministic, drawn from the run's own seed, and its size
    and the corpus it came from are both in the payload: the ranks needed by
    trustworthiness are an n x n matrix, which is 400 million entries at the full
    sample, and an approximation nobody can see is indistinguishable from a
    result.
    """
    high = np.asarray(clustered, dtype=np.float64)
    low = np.asarray(projected, dtype=np.float64)
    if len(high) != len(low):
        raise ValueError(
            f"the two spaces describe different point counts: {len(high)} vs {len(low)}"
        )
    n = len(high)
    take = max(0, min(int(max_points), n))
    subsampled = take < n
    if subsampled:
        keep = np.sort(np.random.default_rng(seed).choice(n, size=take, replace=False))
        high, low = high[keep], low[keep]

    effective = max(1, min(int(k), max(len(high) - 2, 1), max((2 * len(high) - 2) // 3, 1)))
    return {
        "measured_against": "the reduction the clustering was fitted on",
        "points": len(high),
        "sample_points": int(n),
        "subsampled": bool(subsampled),
        "subsample_seed": int(seed) if subsampled else None,
        "k": effective,
        "trustworthiness": round(trustworthiness(high, low, effective), 4),
        "neighbours_lost_share": round(
            neighbour_loss(
                nearest_neighbours(high, effective), nearest_neighbours(low, effective)
            ),
            4,
        ),
        "dimensions": {"clustered": int(high.shape[1]), "projected": int(low.shape[1])},
    }


def projection_diagnostic(
    projected: np.ndarray,
    clustered: np.ndarray,
    attributes: dict[str, object],
    *,
    seed: int,
    k: int = PROJECTION_K,
    max_points: int = AGREEMENT_SAMPLE,
) -> dict[str, object]:
    """What the 2D picture groups, and whether it is even the space that was clustered.

    Two questions, both answered in numbers rather than by pointing at a figure.

    *What would a reader see?* For every point, its `k` nearest points **in the
    2D coordinates**, and the share of them sharing each attribute, beside the
    share a randomly chosen other point would share. If purity by speaker far
    exceeds purity by topic, the picture is a picture of speakers, and a
    thematic reading of it is a misreading.

    *Is the picture the space that was clustered?* Trustworthiness against the
    reduction HDBSCAN was fitted on, plus the plainer figure of how many of a
    point's neighbours there are missing here.

    Returns statistics and nothing else. There is no per-document array in the
    payload and no code path from these coordinates to a label; that is a
    property the tests assert rather than a convention.
    """
    low = np.asarray(projected, dtype=np.float64)
    high = np.asarray(clustered, dtype=np.float64)
    if len(low) != len(high):
        raise ValueError(
            f"the projection has {len(low)} points and the clustered space {len(high)}"
        )
    neighbours = nearest_neighbours(low, k)
    return {
        "diagnostic": True,
        "release_artefact": False,
        "purpose": PROJECTION_PURPOSE,
        "caveat": PROJECTION_CAVEAT,
        "points": len(low),
        "k": int(neighbours.shape[1]),
        "clustered_for_labels": False,
        "purity": {
            name: neighbourhood_purity(neighbours, values)
            for name, values in attributes.items()
        },
        "agreement": projection_agreement(
            high, low, seed=seed, k=k, max_points=max_points
        ),
    }


def group_others(values: object, limit: int, other: str = OTHER_LABEL) -> np.ndarray:
    """The `limit` most frequent values, everything else folded into one name.

    A categorical legend past a dozen entries is a colour-matching exercise, and
    a palette that recycles a hue invites a reader to see two distant groups as
    the same group. Ties are broken alphabetically so the figure does not change
    when two speakers happen to have spoken equally often.
    """
    names = pd.Series(values).astype("string").fillna(other).to_numpy(dtype=object)
    counts = pd.Series(names).value_counts()
    ranked = sorted(counts.index, key=lambda name: (-int(counts[name]), str(name)))
    keep = set(ranked[: max(int(limit), 0)])
    return np.array([name if name in keep else other for name in names], dtype=object)


def draw_projection(
    projected: np.ndarray,
    values: Collection[object],
    *,
    title: str,
    colour_label: str,
    categorical: bool,
    note: str = "",
) -> bytes:
    """One PNG of the projection, coloured by one column of the sample.

    Returns the encoded image rather than writing it, so the caller places it
    with the same atomic write as every other artefact and nothing here needs to
    know where a run's output directory is.

    The Agg backend is selected explicitly. These figures are drawn on a headless
    compute node, and a default backend that reaches for a display is a way to
    fail forty minutes into a job that had already done the expensive part.

    The ticks are removed on purpose: UMAP coordinates carry no unit, and an axis
    with numbers on it invites a reader to measure a distance that means nothing.
    The caveat and the point count are drawn into the image for the same reason
    docs/PLAN.md §7 requires a figure's filters to be — a PNG outlives the note
    it was pasted from.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import colormaps

    coordinates = np.asarray(projected, dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2:
        raise ValueError(f"a 2D projection has two columns; got shape {coordinates.shape}")
    if len(values) != len(coordinates):
        raise ValueError(
            f"{len(values)} values for {len(coordinates)} points — the colour column and "
            "the projection describe different documents"
        )

    figure, axes = plt.subplots(figsize=FIGURE_SIZE, dpi=FIGURE_DPI)
    if categorical:
        names = pd.Series(values).astype("string").fillna(OTHER_LABEL).to_numpy(dtype=object)
        counts = pd.Series(names).value_counts()
        muted = [n for n in counts.index if n in (OTHER_LABEL, UNASSIGNED_LABEL)]
        coloured = [n for n in counts.index if n not in (OTHER_LABEL, UNASSIGNED_LABEL)]
        if len(coloured) <= 20:
            palette = colormaps["tab10" if len(coloured) <= 10 else "tab20"]
            colours = [palette(i) for i in range(len(coloured))]
        else:
            palette = colormaps["turbo"]
            colours = [palette(i / max(len(coloured) - 1, 1)) for i in range(len(coloured))]
        # Muted first, so the groups a reader is meant to compare are not buried
        # under the ones the figure declined to distinguish.
        for name in muted:
            block = names == name
            axes.scatter(
                coordinates[block, 0], coordinates[block, 1], s=MARKER_SIZE,
                alpha=MARKER_ALPHA, linewidths=0, color=MUTED_COLOUR, label=str(name), zorder=1,
            )
        for colour, name in zip(colours, coloured, strict=True):
            block = names == name
            axes.scatter(
                coordinates[block, 0], coordinates[block, 1], s=MARKER_SIZE,
                alpha=MARKER_ALPHA, linewidths=0, color=colour, label=str(name), zorder=2,
            )
        legend = axes.legend(
            title=colour_label, loc="upper right", fontsize=6, title_fontsize=7,
            markerscale=6, frameon=True, borderpad=0.4,
        )
        for handle in legend.legend_handles:
            handle.set_alpha(1.0)
    else:
        quantity = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(
            dtype="float64", na_value=np.nan
        )
        drawn = axes.scatter(
            coordinates[:, 0], coordinates[:, 1], c=quantity, cmap="viridis",
            s=MARKER_SIZE, alpha=MARKER_ALPHA, linewidths=0,
        )
        bar = figure.colorbar(drawn, ax=axes, fraction=0.04, pad=0.02)
        bar.set_label(colour_label, fontsize=8)
        if bar.solids is not None:
            bar.solids.set_alpha(1.0)
        bar.ax.tick_params(labelsize=7)

    axes.set_title(title, fontsize=10)
    axes.set_xlabel(AXIS_LABELS[0], fontsize=8)
    axes.set_ylabel(AXIS_LABELS[1], fontsize=8)
    axes.set_xticks([])
    axes.set_yticks([])
    axes.set_aspect("equal", adjustable="datalim")

    caption = textwrap.fill(
        " ".join(part for part in (f"{len(coordinates):,} speeches.", note, PROJECTION_CAVEAT) if part),
        width=110,
    )
    figure.text(0.5, 0.015, caption, ha="center", va="bottom", fontsize=7)
    figure.tight_layout(rect=(0.0, 0.09, 1.0, 1.0))

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", metadata=FIGURE_METADATA)
    plt.close(figure)
    return buffer.getvalue()
