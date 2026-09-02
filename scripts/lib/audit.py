"""Durable boundaries between generated audit candidates and human annotations."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from . import artifacts

SCHEMA_VERSION = "2"

PROBABILITY: Final = "probability"
COVERAGE: Final = "coverage"
NEGATIVE: Final = "negative_high_recall"

VERDICTS: Final = frozenset({"true_positive", "false_positive", "uncertain"})
SOURCE_CHECKED: Final = frozenset({"yes", "no"})
QUOTATIONS: Final = frozenset(
    {"not_quoted", "direct_quotation", "attributed_or_reported", "unclear", "not_applicable"}
)
STANCES: Final = frozenset(
    {
        "asserts",
        "attributes_or_reports",
        "rejects_or_denies",
        "hypothetical_or_conditional",
        "neutral_legal_reference",
        "unclear",
        "not_applicable",
    }
)
FUNCTIONS: Final = frozenset(
    {
        "accusation_or_qualification",
        "warning_or_prevention",
        "commemoration",
        "accountability",
        "institutional_title_or_mandate",
        "other",
        "unclear",
        "not_applicable",
    }
)
CONFIDENCE: Final = frozenset({"low", "medium", "high"})
DEFAULT_REFERENTS: Final = frozenset({"other", "unclear", "not_applicable"})

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
        "source_length",
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
    "quotation",
    "stance",
    "function",
    "referent",
    "evidence_start",
    "evidence_end",
    "confidence",
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


def stratified_sample(
    frame: pd.DataFrame,
    sizes: Mapping[str, int | None],
    seed: int,
    sampling_frame: str,
    *,
    stratum_column: str = "stratum",
    strategy: str = "disproportionate stratified occurrence sample",
) -> pd.DataFrame:
    """A fixed number of occurrences from each named stratum, at its own probability.

    :func:`probability_sample` gives every occurrence the same chance and is the
    frame an unbiased estimate is computed from. This is the other kind: the
    strata are chosen precisely because they are rare or contested, each is
    sampled at a rate of its own, and the rates differ by two orders of
    magnitude. Nothing drawn here estimates a corpus quantity, and the
    `inclusion_probability` it records is what says so — a reader who wants an
    estimate weights by it, and a reader who wants per-class recall on
    `rejects_or_denies` reads the stratum unweighted and is right to.

    `sizes` maps a stratum name to how many to draw from it, or to None for a
    census — all of it, at probability 1, which is what a stratum of 134 rows
    that the whole design exists to measure deserves. A stratum smaller than its
    size is likewise taken whole; a stratum named in `sizes` and absent from the
    frame contributes nothing and is not an error, because a design written
    against two model runs must survive a run that found none of something.

    Rows whose stratum is blank or absent from `sizes` are outside the frame and
    are not drawn. The stratum column is expected to be *disjoint* — one stratum
    per occurrence, assigned in a precedence the caller decides — because
    overlapping strata make the inclusion probability of a row the union of
    several draws, and nothing downstream could reconstruct it from what is
    recorded here.
    """
    if frame["occurrence_id"].duplicated().any():
        raise ValueError("A sampling frame may contain each occurrence only once.")
    frame_digest = _digest(frame["occurrence_id"].astype(str).tolist())
    selected: list[pd.DataFrame] = []
    for name, size in sizes.items():
        if size is not None and size < 1:
            raise ValueError(f"Stratum {name!r} asks for {size} occurrences.")
        stratum = frame.loc[frame[stratum_column].astype(str) == name]
        if stratum.empty:
            continue
        population = len(stratum)
        draw = population if size is None else min(size, population)
        ranked = stratum.assign(
            _draw=stratum["occurrence_id"].map(lambda value: _rank(str(value), seed))
        ).sort_values(["_draw", "occurrence_id"])
        chosen = ranked.head(draw).drop(columns="_draw").copy()
        chosen["stratum_size"] = population
        chosen["sample_size"] = draw
        chosen["inclusion_probability"] = draw / population
        chosen["sampling_weight"] = population / draw
        selected.append(chosen)

    if not selected:
        return frame.iloc[0:0].copy()
    sample = pd.concat(selected, ignore_index=True)
    sample["sampling_frame"] = sampling_frame
    sample["strategy"] = strategy
    sample["seed"] = seed
    sample["frame_size"] = len(frame)
    sample["frame_sha256"] = frame_digest
    sample["sample_sha256"] = _digest(
        [sampling_frame, str(seed), frame_digest, *sample["occurrence_id"].astype(str).tolist()]
    )
    sample["candidate_id"] = sample["occurrence_id"].map(
        lambda value: candidate_id(str(value), sampling_frame)
    )
    return sample.sort_values([stratum_column, "filename", "start"]).reset_index(drop=True)


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


@dataclass(frozen=True)
class ReferentList:
    """The controlled list and the versions that keep an older run readable.

    The list has to do two jobs at once. A *new* annotation may use only what the
    list currently offers, because a model is shown only the current identifiers
    and a coder is told to add a referent before using it. An *older* run has to
    stay readable for as long as it is committed, because two paid runs record
    v1 identifiers on 12,184 rows and renaming a case cannot be allowed to orphan
    them. Both jobs are served from one file: a retired identifier keeps its row,
    carries the version at which it stopped being offered, and names whatever it
    became.

    The version is derived rather than declared. It is the highest version any
    row mentions, so there is no file-level number that a hand-edit can forget to
    bump, and a release that only retires rows still moves it because
    `retired_in` counts too. The rejected alternative was a lock file beside
    `config/lexicon.lock.json`: it would catch a description edited without a
    `since` bump, which this does not, but it puts a generated file next to a
    human-owned one and `annotations/` is a directory no script writes into. The
    golden test over this file does that job instead.

    `since` records the version at which an identifier's *meaning* was last set,
    exactly as `pattern_since` does for a lexicon term. It is what decides
    whether a run is compatible, so editing a label to stop asserting a verdict
    leaves it alone — the identifier still covers the same passages — while
    widening a description to cover passages it did not cover before bumps it.
    `iso3` and `years` never bump it: the codebook says both are documentation
    rather than coding, so correcting a date range cannot invalidate a run.
    """

    version: int
    since: Mapping[str, int]
    retired_in: Mapping[str, int]
    superseded_by: Mapping[str, str]

    @property
    def all(self) -> set[str]:
        """Every identifier the file holds, retired ones included."""
        return set(self.since)

    @property
    def current(self) -> set[str]:
        """The identifiers a new annotation may use, and the prompt may render."""
        return {name for name in self.since if name not in self.retired_in}

    def resolve(self, identifier: str) -> str:
        """What a recorded identifier is called now.

        Following `superseded_by` until it runs out, so a run made against v1 and
        a run made against v2 can be counted in the same column. An identifier
        retired without a successor resolves to itself and is reported under its
        own name: `hypothetical_future` was retired because it is a modal
        property rather than a referent, and choosing `genocide_in_general` or
        `unclear` on its behalf would put a judgement in the model's mouth that
        the model did not make.
        """
        seen = {identifier}
        while (successor := self.superseded_by.get(identifier, "")) and successor not in seen:
            identifier = successor
            seen.add(identifier)
        return identifier

    def compatible(self, identifier: str, recorded: str | int) -> bool:
        """Could a run made against list version `recorded` have used this?

        Two ways it could not: the identifier did not yet mean what it means now,
        or it had already been retired and was therefore never rendered into that
        run's prompt. Either says the run and the manifest disagree about which
        list was in front of the model, which is a provenance failure rather than
        a counting one. A run that recorded no version at all was made against
        version 1, the only version that had no number.
        """
        version = int(recorded) if str(recorded).strip() else 1
        if self.since.get(identifier, version + 1) > version:
            return False
        retired = self.retired_in.get(identifier)
        return retired is None or retired > version


def read_referent_list(path: Path) -> ReferentList:
    """Read the controlled list with its retirements and its version.

    The identifier checks live here rather than in the caller because every
    reader of this file depends on them: an identifier with surrounding
    whitespace, a blank one or a duplicate would each fragment one referent into
    two silently, which is the failure the controlled list exists to prevent. A
    file that has not yet grown the version columns is read as version 1 with
    nothing retired, which is what it meant before they existed.
    """
    table = pd.read_csv(path, dtype="string", keep_default_na=False)
    required = {"id", "label", "description"}
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(f"Referent file is missing columns: {', '.join(missing)}")
    identifiers = table["id"].astype(str)
    if identifiers.str.strip().ne(identifiers).any():
        raise ValueError("Referent IDs must not contain surrounding whitespace.")
    if identifiers.eq("").any() or identifiers.duplicated().any():
        raise ValueError("Referent IDs must be nonempty and unique.")
    missing_defaults = sorted(DEFAULT_REFERENTS - set(identifiers))
    if missing_defaults:
        raise ValueError(
            "Referent file is missing reserved IDs: " + ", ".join(missing_defaults)
        )

    since: dict[str, int] = {}
    retired_in: dict[str, int] = {}
    superseded_by: dict[str, str] = {}
    for values in table.to_dict(orient="records"):
        name = str(values["id"])
        since[name] = _version_cell(values.get("since"), name, "since", default=1)
        if retired := _version_cell(values.get("retired_in"), name, "retired_in", default=0):
            retired_in[name] = retired
        if successor := str(values.get("superseded_by") or "").strip():
            superseded_by[name] = successor

    unknown = sorted(set(superseded_by.values()) - set(since))
    if unknown:
        raise ValueError(
            "Referent file supersedes IDs onto ones it does not hold: " + ", ".join(unknown)
        )
    stranded = sorted(name for name in superseded_by if name not in retired_in)
    if stranded:
        raise ValueError(
            "Referent file names a successor for IDs it has not retired: " + ", ".join(stranded)
        )
    return ReferentList(
        version=max([*since.values(), *retired_in.values(), 1]),
        since=since,
        retired_in=retired_in,
        superseded_by=superseded_by,
    )


def _version_cell(value: object, name: str, column: str, *, default: int) -> int:
    """One version number from the file, or the default an empty cell means."""
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit() or int(text) < 1:
        raise ValueError(f"Referent '{name}' has a non-numeric {column}: {text}")
    return int(text)


def read_referents(path: Path) -> set[str]:
    """The identifiers a new annotation may use.

    Current ones only. This is the authority the annotation schema is closed
    over, and a retired identifier is one the prompt no longer renders and a
    coder is no longer offered, so accepting it here would let a run use a
    category the instrument never showed it. Reading an *older* run is the other
    question and wants :func:`read_referent_list`, whose `all` holds the retired
    identifiers too.
    """
    return read_referent_list(path).current


def _annotation_values(row: pd.Series, field: str, allowed: frozenset[str]) -> None:
    value = str(row[field])
    if value not in allowed:
        raise ValueError(f"Unknown {field} label: {value or '(blank)'}")


def _validate_labels(
    candidates: pd.DataFrame, annotations: pd.DataFrame, referents: set[str]
) -> None:
    source = candidates.drop_duplicates("occurrence_id").set_index("occurrence_id")
    for row in annotations.itertuples(index=False):
        record = pd.Series(row._asdict())
        for field, allowed in (
            ("verdict", VERDICTS),
            ("source_checked", SOURCE_CHECKED),
            ("quotation", QUOTATIONS),
            ("stance", STANCES),
            ("confidence", CONFIDENCE),
        ):
            _annotation_values(record, field, allowed)

        functions = str(record["function"]).split("|")
        if not functions or any(value not in FUNCTIONS for value in functions):
            raise ValueError(f"Unknown function label: {record['function'] or '(blank)'}")
        if len(functions) != len(set(functions)):
            raise ValueError("Function labels must not be repeated.")
        if len(functions) > 1 and ({"unclear", "not_applicable"} & set(functions)):
            raise ValueError("unclear and not_applicable cannot be combined with other functions.")

        referent = str(record["referent"])
        if referent not in referents:
            raise ValueError(f"Unknown referent: {referent or '(blank)'}")
        if record["verdict"] == "false_positive":
            expected = {str(record[field]) for field in ("quotation", "stance", "function", "referent")}
            if expected != {"not_applicable"}:
                raise ValueError("False positives must use not_applicable discourse labels.")
        elif "not_applicable" in {
            str(record[field]) for field in ("quotation", "stance", "function", "referent")
        }:
            raise ValueError("not_applicable is reserved for false positives.")

        try:
            coded_at = str(record["coded_at"])
            if date.fromisoformat(coded_at).isoformat() != coded_at:
                raise ValueError
            evidence_start = int(str(record["evidence_start"]))
            evidence_end = int(str(record["evidence_end"]))
        except ValueError as exc:
            raise ValueError("coded_at and evidence offsets must use ISO date and integers.") from exc
        candidate = source.loc[str(record["occurrence_id"])]
        if not (
            0 <= evidence_start <= int(candidate["start"])
            and int(candidate["end"]) <= evidence_end <= int(candidate["source_length"])
        ):
            raise ValueError("Evidence span must be inside the source and contain the matched term.")


def merge(
    candidates: pd.DataFrame,
    annotations: pd.DataFrame,
    *,
    referents: set[str] | None = None,
    compatible: Callable[[str, str], bool] | None = None,
) -> pd.DataFrame:
    """Join human work to generated candidates, refusing ambiguous identities.

    `compatible` decides, per annotated row, whether the term that row was coded
    on still enumerates the same occurrences at the version it records — pass
    `Lexicon.compatible`. Candidates are regenerated at the current lexicon
    version, so without it a coded row keeps the version it was coded at and any
    bump of the lexicon would refuse the whole file. Omitted, the strict rule
    stands: an annotation may only record a version some candidate records too.
    """
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

        if compatible is None:
            candidate_lexicons = set(candidates["lexicon_version"].astype(str))
            annotation_lexicons = set(nonempty["lexicon_version"].astype(str))
            if annotation_lexicons - candidate_lexicons:
                raise ValueError(
                    "Annotation lexicon is incompatible with the generated candidates: "
                    f"candidates={sorted(candidate_lexicons)}, "
                    f"annotations={sorted(annotation_lexicons)}"
                )

        known = set(candidates["occurrence_id"].astype(str))
        unknown = sorted(set(nonempty["occurrence_id"].astype(str)) - known)
        if unknown:
            raise ValueError(f"Annotations refer to unknown occurrence IDs: {', '.join(unknown[:5])}")

        if compatible is not None:
            # Per row and per term, after the check above, so an ID nobody
            # generated is reported as unknown rather than as incompatible.
            # `occurrence_id` is built from the term, so two candidate rows for
            # one occurrence — the same match drawn into two sampling frames —
            # always name the same term.
            terms = dict(
                zip(
                    candidates["occurrence_id"].astype(str),
                    candidates["term"].astype(str),
                    strict=True,
                )
            )
            for occurrence, recorded in zip(
                nonempty["occurrence_id"].astype(str),
                nonempty["lexicon_version"].astype(str).str.strip(),
                strict=True,
            ):
                term = terms[occurrence]
                if not compatible(term, recorded):
                    raise ValueError(
                        f"Annotation of occurrence {occurrence} was coded against lexicon "
                        f"version {recorded} and '{term}' no longer enumerates it: a "
                        "coded row holds from the version its term's pattern last changed "
                        "in up to the current one."
                    )

        _validate_labels(candidates, nonempty, referents or set(DEFAULT_REFERENTS))

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
    referent_path: Path | None = None,
    compatible: Callable[[str, str], bool] | None = None,
) -> pd.DataFrame:
    """Regenerate candidates and review while never writing the human-owned file.

    `compatible` is forwarded to `merge`; see it for what the rule decides.
    """
    annotations = read_annotations(annotation_path)
    referents = read_referents(referent_path) if referent_path else set(DEFAULT_REFERENTS)
    review = merge(candidates, annotations, referents=referents, compatible=compatible)
    artifacts.atomic_write_text(candidate_path, candidates.to_csv(index=False, lineterminator="\n"))
    for frame, path in (frame_paths or {}).items():
        selected = candidates.loc[candidates["sampling_frame"] == frame]
        artifacts.atomic_write_text(path, selected.to_csv(index=False, lineterminator="\n"))
    artifacts.atomic_write_text(review_path, review.to_csv(index=False, lineterminator="\n"))
    return review
