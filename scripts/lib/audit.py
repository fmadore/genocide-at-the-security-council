"""Durable boundaries between generated audit candidates and human annotations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from . import artifacts

SCHEMA_VERSION = "1"

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


def candidate_id(occurrence: str, unit: str) -> str:
    """Identity for one occurrence's place in a named sampling frame."""
    return hashlib.sha256(f"{occurrence}\x1f{unit}".encode()).hexdigest()


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
) -> pd.DataFrame:
    """Regenerate candidates and review while never writing the human-owned file."""
    annotations = read_annotations(annotation_path)
    review = merge(candidates, annotations)
    artifacts.atomic_write_text(candidate_path, candidates.to_csv(index=False, lineterminator="\n"))
    artifacts.atomic_write_text(review_path, review.to_csv(index=False, lineterminator="\n"))
    return review
