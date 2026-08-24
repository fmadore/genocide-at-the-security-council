"""Durable boundaries between generated audit candidates and human annotations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

import pandas as pd

from . import artifacts

SCHEMA_VERSION = "1"

PROBABILITY: Final = "probability"
COVERAGE: Final = "coverage"
NEGATIVE: Final = "negative_high_recall"

CANDIDATE_REQUIRED = frozenset(
    {
        "candidate_id",
        "occurrence_id",
        "schema_version",
        "lexicon_version",
        "unit",
        "term",
        "filename",
        "start",
        "end",
        "source_sha256",
        "sampling_frame",
        "strategy",
        "seed",
        "frame_size",
        "sample_size",
        "inclusion_probability",
        "sampling_weight",
        "frame_sha256",
        "sample_sha256",
    }
)

ANNOTATION_FIELDS = (
    "occurrence_id",
    "schema_version",
    "lexicon_version",
    "coder",
    "coded_at",
    "verdict",
    "source_checked",
    "phenomenon",
    "comment",
)


def source_sha256(text: str) -> str:
    """A digest that invalidates an occurrence identity when its source changes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def occurrence_id(
    filename: str,
    term: str,
    start: int,
    end: int,
    keyword: str,
    source_digest: str,
) -> str:
    """Stable identity for one term match in one exact version of a speech."""
    identity = "\x1f".join((filename, term, str(start), str(end), keyword, source_digest))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def candidate_id(occurrence: str, sampling_frame: str) -> str:
    """Identity for one occurrence's place in a named sampling frame."""
    return hashlib.sha256(f"{occurrence}\x1f{sampling_frame}".encode()).hexdigest()


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _rank(value: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}\x1f{value}".encode()).hexdigest()


def probability_sample(
    frame: pd.DataFrame, size: int, seed: int, sampling_frame: str
) -> pd.DataFrame:
    """A row-order-independent equal-probability sample of occurrences."""
    if size < 1:
        raise ValueError("Sample size must be positive.")
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    population = len(frame)
    draw = min(size, population)
    ranked = frame.assign(
        _draw=frame["occurrence_id"].map(lambda value: _rank(str(value), seed))
    ).sort_values(["_draw", "occurrence_id"])
    selected = ranked.head(draw).drop(columns="_draw").copy()
    probability = draw / population if population else 0.0
    selected["sampling_frame"] = sampling_frame
    selected["strategy"] = "simple random occurrence sample"
    selected["seed"] = seed
    selected["frame_size"] = population
    selected["sample_size"] = draw
    selected["inclusion_probability"] = probability
    selected["sampling_weight"] = 1 / probability if probability else float("nan")
    selected["stratum_size"] = population
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected["frame_sha256"] = frame_digest
    selected["sample_sha256"] = _digest(
        [sampling_frame, str(seed), frame_digest, *selected["occurrence_id"].astype(str).tolist()]
    )
    selected["candidate_id"] = selected["occurrence_id"].map(
        lambda value: candidate_id(str(value), sampling_frame)
    )
    return selected.sort_values(["term", "filename", "start"]).reset_index(drop=True)


def coverage_sample(
    frame: pd.DataFrame,
    size: int,
    seed: int,
    *,
    strata: tuple[str, ...] = ("term", "period"),
) -> pd.DataFrame:
    """Cover each stratum once, then fill randomly with recorded probabilities."""
    if size < 1:
        raise ValueError("Sample size must be positive.")
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    if frame.empty:
        return probability_sample(frame, size, seed, COVERAGE)

    ranked = frame.assign(
        _anchor=frame["occurrence_id"].map(lambda value: _rank(str(value), seed))
    )
    anchors = (
        ranked.sort_values(["_anchor", "occurrence_id"])
        .groupby(list(strata), sort=True)
        .head(1)
    )
    strata_total = len(anchors)
    if size < strata_total:
        raise ValueError(
            f"Coverage sample size {size} is smaller than its {strata_total} strata."
        )
    remaining = ranked.drop(index=anchors.index).assign(
        _fill=lambda rows: rows["occurrence_id"].map(
            lambda value: _rank(str(value), seed + 1)
        )
    )
    fill_draws = min(size - strata_total, len(remaining))
    selected = pd.concat(
        [anchors, remaining.sort_values(["_fill", "occurrence_id"]).head(fill_draws)]
    ).copy()
    stratum_sizes = frame.groupby(list(strata))["occurrence_id"].size()
    remaining_total = len(frame) - strata_total
    fill_probability = fill_draws / remaining_total if remaining_total else 0.0

    def inclusion(row: pd.Series) -> float:
        stratum = tuple(row[field] for field in strata)
        stratum_size = int(stratum_sizes.loc[stratum])
        anchor_probability = 1 / stratum_size
        return anchor_probability + (1 - anchor_probability) * fill_probability

    selected["stratum_size"] = selected.apply(
        lambda row: int(stratum_sizes.loc[tuple(row[field] for field in strata)]), axis=1
    )
    selected["inclusion_probability"] = selected.apply(inclusion, axis=1)
    selected["sampling_weight"] = 1 / selected["inclusion_probability"]
    selected["sampling_frame"] = COVERAGE
    selected["strategy"] = "one per term-period stratum, then simple random fill"
    selected["seed"] = seed
    selected["frame_size"] = len(frame)
    selected["sample_size"] = len(selected)
    selected["strata_total"] = strata_total
    selected["fill_draws"] = fill_draws
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected["frame_sha256"] = frame_digest
    selected["sample_sha256"] = _digest(
        [COVERAGE, str(seed), frame_digest, *selected["occurrence_id"].astype(str).tolist()]
    )
    selected["candidate_id"] = selected["occurrence_id"].map(
        lambda value: candidate_id(str(value), COVERAGE)
    )
    return (
        selected.drop(columns=["_anchor", "_fill"], errors="ignore")
        .sort_values([*strata, "filename", "start"])
        .reset_index(drop=True)
    )


def read_annotations(path: Path) -> pd.DataFrame:
    """Read the human-owned file without treating blank cells as missing values."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Human annotation file is missing: {path}. Restore the versioned file; "
            "the pipeline will not recreate it."
        )
    annotations = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing = sorted(set(ANNOTATION_FIELDS) - set(annotations.columns))
    if missing:
        raise ValueError(f"Annotation file is missing columns: {', '.join(missing)}")
    return annotations.loc[:, list(ANNOTATION_FIELDS)].copy()


def merge(candidates: pd.DataFrame, annotations: pd.DataFrame) -> pd.DataFrame:
    """Join human work to generated candidates, refusing ambiguous identities."""
    missing_candidates = sorted(CANDIDATE_REQUIRED - set(candidates.columns))
    if missing_candidates:
        raise ValueError(f"Candidate file is missing columns: {', '.join(missing_candidates)}")
    missing_annotations = sorted(set(ANNOTATION_FIELDS) - set(annotations.columns))
    if missing_annotations:
        raise ValueError(f"Annotation file is missing columns: {', '.join(missing_annotations)}")

    if candidates["candidate_id"].duplicated().any():
        raise ValueError("Candidate IDs must be unique within the generated sample.")

    if annotations.empty:
        nonempty = annotations.copy()
    else:
        has_value = annotations.astype("string").apply(
            lambda row: row.str.len().gt(0).any(), axis=1
        )
        nonempty = annotations.loc[has_value]
    if not nonempty.empty:
        for field in ("occurrence_id", "schema_version", "lexicon_version", "coder"):
            if nonempty[field].str.strip().eq("").any():
                raise ValueError(f"Every annotation row must carry {field}.")
        if nonempty.duplicated(["occurrence_id", "coder"]).any():
            raise ValueError("Each coder may annotate an occurrence only once.")

        candidate_versions = set(candidates["schema_version"].astype(str))
        annotation_versions = set(nonempty["schema_version"].astype(str))
        if annotation_versions - candidate_versions:
            raise ValueError(
                "Annotation schema is incompatible with the generated candidates: "
                f"candidates={sorted(candidate_versions)}, annotations={sorted(annotation_versions)}"
            )

        candidate_lexicons = set(candidates["lexicon_version"].astype(str))
        annotation_lexicons = set(nonempty["lexicon_version"].astype(str))
        if annotation_lexicons - candidate_lexicons:
            raise ValueError(
                "Annotation lexicon is incompatible with the generated candidates: "
                f"candidates={sorted(candidate_lexicons)}, annotations={sorted(annotation_lexicons)}"
            )

        known = set(candidates["occurrence_id"].astype(str))
        unknown = sorted(set(nonempty["occurrence_id"].astype(str)) - known)
        if unknown:
            raise ValueError(f"Annotations refer to unknown occurrence IDs: {', '.join(unknown[:5])}")

    review = candidates.merge(
        nonempty,
        on="occurrence_id",
        how="left",
        suffixes=("_candidate", "_annotation"),
        validate="many_to_many",
        sort=False,
    )
    annotation_columns = [
        column
        for column in review
        if column.endswith("_annotation") or column in ANNOTATION_FIELDS[3:]
    ]
    review.loc[:, annotation_columns] = review.loc[:, annotation_columns].fillna("")
    return review


def write_outputs(
    candidates: pd.DataFrame,
    *,
    annotation_path: Path,
    candidate_path: Path,
    review_path: Path,
    frame_paths: dict[str, Path] | None = None,
) -> pd.DataFrame:
    """Regenerate candidates and review while never writing the human-owned file."""
    annotations = read_annotations(annotation_path)
    review = merge(candidates, annotations)
    artifacts.atomic_write_text(candidate_path, candidates.to_csv(index=False, lineterminator="\n"))
    for frame, path in (frame_paths or {}).items():
        selected = candidates.loc[candidates["sampling_frame"] == frame]
        artifacts.atomic_write_text(path, selected.to_csv(index=False, lineterminator="\n"))
    artifacts.atomic_write_text(review_path, review.to_csv(index=False, lineterminator="\n"))
    return review
