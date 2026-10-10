"""Durable boundaries between generated audit candidates and human annotations.

The vocabulary a row is coded in is `lib.schema`'s, and the frames 03 draws are
`lib.sampling`'s; this module joins the two at the human file.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from . import artifacts, console, lexicon
from . import text as text_lib
from .sampling import COVERAGE as COVERAGE

# Every name imported with a redundant `as` is a re-export, kept importable from
# this module for the callers and tests that still reach it here; new code
# imports it from where it is defined. The `as` marks it as deliberate rather
# than as an unused import.
from .sampling import NEGATIVE, PROBABILITY, coverage_sample, probability_sample
from .sampling import candidate_id as candidate_id
from .sampling import coverage_inclusion as coverage_inclusion
from .sampling import stratified_sample as stratified_sample
from .sampling import union_inclusion as union_inclusion
from .schema import (
    ANNOTATION_FIELDS,
    CASCADE_FIELDS,
    CONCRETE_CASE,
    CONFIDENCE,
    DEFAULT_REFERENTS,
    FREE_TEXT_CASCADE_FIELDS,
    FUNCTIONS,
    OWN_STATE_ACCUSED,
    POSITIONS,
    QUOTATIONS,
    REFERENT_SOURCES,
    RESERVED_FIELDS,
    SALIENCE,
    SCHEMA_VERSION,
    SOURCE_CHECKED,
    VERDICTS,
)
from .schema import LEGACY_SCHEMA_VERSION as LEGACY_SCHEMA_VERSION
from .schema import NON_CASE_REFERENTS as NON_CASE_REFERENTS
from .schema import POSITION_FROM_STANCE as POSITION_FROM_STANCE
from .schema import STANCES as STANCES
from .schema import concrete_case_from_v1 as concrete_case_from_v1

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


def _period(year: int) -> str:
    return f"{year // 10 * 10}s"


def audit_sample(
    speeches: pd.DataFrame,
    bodies: pd.Series,
    lex: lexicon.Lexicon,
    size: int,
    seed: int,
    *,
    found: Mapping[str, Mapping[object, list[tuple[int, int]]]] | None = None,
) -> pd.DataFrame:
    """Separate probability, coverage and high-recall negative audit samples.

    `found` is :func:`lib.lexicon.find_all` over the same bodies and every term,
    enabled or not: 03 has those spans from counting, and drawing the sample
    from them rather than matching the corpus again is what guarantees the
    sample is of the occurrences that were counted.
    """
    if found is None:
        found = lexicon.find_all(bodies, lex.terms.values())
    rows: list[dict[str, object]] = []
    years = speeches["year"].to_dict()
    # Looked up per column rather than a whole row per occurrence: a row of a
    # fifty-column frame costs about a millisecond, and there are eighty
    # thousand occurrences. A speech's digest is likewise taken once.
    columns = ["filename", "meeting_symbol", "date", "country_org", "agenda_item_manual"]
    metadata = {column: speeches[column].to_dict() for column in columns}
    digests: dict[object, str] = {}

    def append(term: lexicon.Term, index: object, body: str, start: int, end: int) -> None:
        meta = {column: values[index] for column, values in metadata.items()}
        left, keyword, right = text_lib.window(body, start, end)
        source_digest = digests.get(index)
        if source_digest is None:
            source_digest = digests[index] = source_sha256(body)
        occurrence = occurrence_id(
            str(meta["filename"]), term.name, start, end, keyword, source_digest
        )
        rows.append(
            {
                "occurrence_id": occurrence,
                "schema_version": SCHEMA_VERSION,
                "lexicon_version": lex.version,
                "unit": "occurrence",
                "term": term.name,
                "tier": term.tier,
                "register": term.register,
                "period": _period(int(years[index])),
                "filename": meta["filename"],
                "meeting_symbol": meta["meeting_symbol"],
                "date": f"{meta['date']:%Y-%m-%d}",
                "country_org": meta["country_org"],
                "agenda": meta["agenda_item_manual"],
                "start": start,
                "end": end,
                "source_sha256": source_digest,
                "source_length": len(body),
                "left": left,
                "keyword": keyword,
                "right": right,
            }
        )

    for term in lex.active:
        for index, spans in found[term.name].items():
            body = bodies.at[index]
            for start, end in spans:
                append(term, index, body, start, end)
    if not rows:
        return pd.DataFrame()

    occurrences = pd.DataFrame(rows)
    probability = probability_sample(occurrences, size, seed, PROBABILITY)
    # The coverage frame promises one occurrence per term and period, so its size
    # is a property of the lexicon, not a setting: 22 terms fitted under 100, the
    # 28 of v4 make 109 strata and the deploy of 2 September 2026 stopped here.
    # Growing to the strata count keeps the promise; `coverage_sample` still
    # refuses a size it cannot honour, for a caller that names one on purpose.
    strata = occurrences.groupby(["term", "period"]).ngroups
    coverage_size = max(size, strata)
    if coverage_size > size:
        console.info(
            f"coverage sample grown from {size} to {coverage_size}: one occurrence per "
            f"term and period is {strata} strata under lexicon v{lex.version}"
        )
    coverage = coverage_sample(occurrences, coverage_size, seed + 1)

    rows.clear()
    for term in lex.disabled:
        peers = [peer for peer in lex.active if peer.tier == term.tier]
        for index, matches in found[term.name].items():
            body = bodies.at[index]
            peer_spans = [span for peer in peers for span in found[peer.name].get(index, [])]
            for start, end in matches:
                overlaps = any(
                    start < peer_end and peer_start < end
                    for peer_start, peer_end in peer_spans
                )
                if not overlaps:
                    append(term, index, body, start, end)
    negatives = pd.DataFrame(rows, columns=occurrences.columns)
    negative = probability_sample(negatives, size, seed + 2, NEGATIVE)
    return pd.concat([probability, coverage, negative], ignore_index=True)


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

    Parsed, and held to every rule of the list, by `lib.referents`; this is
    the view that keeps an older run readable. A file that has not yet grown
    the version columns is read as version 1 with nothing retired, which is
    what it meant before they existed.
    """
    # Imported here: `lib.referents` takes `ReferentList` from this module, so a
    # module-level import would be circular.
    from . import referents

    return referents.read(path).listing()


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
            ("concrete_case", CONCRETE_CASE),
            ("speaker_position", POSITIONS),
            ("referent_source", REFERENT_SOURCES),
            ("own_state_accused", OWN_STATE_ACCUSED),
            ("salience", SALIENCE),
            ("confidence", CONFIDENCE),
        ):
            _annotation_values(record, field, allowed)

        # The one decision, checked once. `concrete_case: no` and
        # `speaker_position: no_position` are two names for one finding — the
        # word is applied to no case here — and a row carrying one without the
        # other has taken the decision twice and differently, which is the fault
        # schema 3 exists to remove.
        if (record["concrete_case"] == "no") != (record["speaker_position"] == "no_position"):
            raise ValueError(
                "concrete_case 'no' and speaker_position 'no_position' are one decision: "
                f"got {record['concrete_case']!r} and {record['speaker_position']!r}."
            )
        if not str(record["rationale"]).strip():
            raise ValueError("Every annotation carries a one-sentence rationale.")

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
            expected = {str(record[field]) for field in CASCADE_FIELDS}
            if expected != {"not_applicable"}:
                raise ValueError("False positives must use not_applicable discourse labels.")
            if any(str(record[field]).strip() for field in FREE_TEXT_CASCADE_FIELDS):
                raise ValueError("False positives leave the free-text label fields empty.")
        elif "not_applicable" in {str(record[field]) for field in RESERVED_FIELDS}:
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
