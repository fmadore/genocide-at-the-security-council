"""Generated lexicon-audit candidates and durable human annotations."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest
from lib import audit, lexicon
from lib.paths import ROOT

REFERENT_ID = re.compile(r"^[a-z0-9_]+$")
REFERENT_KINDS = frozenset({"case", "historical", "meta", "reserved"})


def _audit_step():
    path = Path(__file__).resolve().parents[1] / "scripts" / "03_lexicon.py"
    spec = importlib.util.spec_from_file_location("lexicon_step", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": "candidate-1",
                "occurrence_id": "occurrence-1",
                "schema_version": audit.SCHEMA_VERSION,
                "lexicon_version": 2,
                "unit": "occurrence",
                "term": "genocide",
                "filename": "speech-1.txt",
                "start": 10,
                "end": 18,
                "source_sha256": "a" * 64,
                "source_length": 100,
                "sampling_frame": audit.PROBABILITY,
                "strategy": "simple random occurrence sample",
                "seed": 12,
                "frame_size": 20,
                "sample_size": 2,
                "inclusion_probability": 0.1,
                "sampling_weight": 10.0,
                "frame_sha256": "c" * 64,
                "sample_sha256": "d" * 64,
            },
            {
                "candidate_id": "candidate-2",
                "occurrence_id": "occurrence-2",
                "schema_version": audit.SCHEMA_VERSION,
                "lexicon_version": 2,
                "unit": "speech",
                "term": "atrocity",
                "filename": "speech-2.txt",
                "start": 20,
                "end": 28,
                "source_sha256": "b" * 64,
                "source_length": 100,
                "sampling_frame": audit.COVERAGE,
                "strategy": "one per term-period stratum, then simple random fill",
                "seed": 13,
                "frame_size": 20,
                "sample_size": 2,
                "inclusion_probability": 0.2,
                "sampling_weight": 5.0,
                "frame_sha256": "c" * 64,
                "sample_sha256": "e" * 64,
            },
        ]
    )


def annotations(*rows: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=audit.ANNOTATION_FIELDS, dtype="string")


def annotation(occurrence: str, coder: str = "coder-a", **changes: str) -> dict[str, str]:
    row = {
        "occurrence_id": occurrence,
        "schema_version": audit.SCHEMA_VERSION,
        "lexicon_version": "2",
        "coder": coder,
        "coded_at": "2026-08-24",
        "verdict": "true_positive",
        "source_checked": "yes",
        "quotation": "not_quoted",
        "stance": "asserts",
        "function": "accusation_or_qualification",
        "referent": "other",
        "evidence_start": "10",
        "evidence_end": "18",
        "confidence": "high",
        "comment": "",
    }
    row.update(changes)
    return row


def test_occurrence_identity_is_stable_for_the_same_source_and_span() -> None:
    digest = audit.source_sha256("the word genocide appears here")
    first = audit.occurrence_id("speech.txt", "genocide", 9, 17, "genocide", digest)
    second = audit.occurrence_id("speech.txt", "genocide", 9, 17, "genocide", digest)
    assert first == second
    assert len(first) == 64


def test_changed_source_text_changes_the_occurrence_identity() -> None:
    before = audit.source_sha256("genocide appears here")
    after = audit.source_sha256("genocide appears over here")
    assert audit.occurrence_id("speech.txt", "genocide", 0, 8, "genocide", before) != (
        audit.occurrence_id("speech.txt", "genocide", 0, 8, "genocide", after)
    )


def test_sampling_frames_share_an_occurrence_but_not_a_candidate_identity() -> None:
    assert audit.candidate_id("occurrence", "speech") != audit.candidate_id(
        "occurrence", "occurrence"
    )


def sampling_frame() -> pd.DataFrame:
    rows = []
    strata = (
        ("a", "1990s", 4),
        ("a", "2000s", 2),
        ("b", "1990s", 3),
        ("b", "2000s", 1),
    )
    for term, period, size in strata:
        for number in range(size):
            rows.append(
                {
                    "occurrence_id": f"{term}-{period}-{number}",
                    "term": term,
                    "period": period,
                    "filename": f"speech-{term}-{period}-{number}.txt",
                    "start": number,
                }
            )
    return pd.DataFrame(rows)


def test_probability_sample_is_equal_probability_and_row_order_independent() -> None:
    frame = sampling_frame()
    first = audit.probability_sample(frame, 3, 7, audit.PROBABILITY)
    shuffled = audit.probability_sample(
        frame.sample(frac=1, random_state=99).reset_index(drop=True),
        3,
        7,
        audit.PROBABILITY,
    )
    assert set(first["occurrence_id"]) == set(shuffled["occurrence_id"])
    assert set(first["inclusion_probability"]) == {0.3}
    assert set(first["sampling_weight"]) == {10 / 3}
    assert first["frame_sha256"].nunique() == first["sample_sha256"].nunique() == 1


def test_coverage_sample_covers_every_stratum_and_records_reconstructable_weights() -> None:
    sample = audit.coverage_sample(sampling_frame(), 6, 11)
    assert set(zip(sample["term"], sample["period"], strict=True)) == {
        ("a", "1990s"),
        ("a", "2000s"),
        ("b", "1990s"),
        ("b", "2000s"),
    }
    assert set(sample["strata_total"]) == {4}
    assert set(sample["fill_draws"]) == {2}
    for row in sample.itertuples():
        expected = 1 / row.stratum_size + (1 - 1 / row.stratum_size) * (2 / 6)
        assert row.inclusion_probability == pytest.approx(expected)
        assert row.sampling_weight == pytest.approx(1 / expected)


def test_coverage_sample_refuses_to_drop_declared_strata() -> None:
    with pytest.raises(ValueError, match="smaller than its 4 strata"):
        audit.coverage_sample(sampling_frame(), 3, 11)


def test_pipeline_builds_three_distinct_frames_from_declared_patterns() -> None:
    active = lexicon.Term(
        name="genocide",
        pattern=r"\bgenocide\b",
        tier="core",
        register="core",
        examples=("genocide",),
        prefilters=("genocide",),
        regex=re.compile(r"\bgenocide\b", re.IGNORECASE),
    )
    disabled = lexicon.Term(
        name="genocide_ocr_variants",
        pattern=r"\bgen[eo]cide\b",
        tier="core",
        register="core",
        enabled=False,
        examples=("genecide",),
        prefilters=("genecide",),
        regex=re.compile(r"\bgen[eo]cide\b", re.IGNORECASE),
    )
    lex = lexicon.Lexicon(
        version=2,
        updated="2026-08-09",
        terms={active.name: active, disabled.name: disabled},
        sets={},
    )
    bodies = pd.Series(
        ["genocide here", "another genocide", "an OCR genecide"], index=[0, 1, 2]
    )
    speeches = pd.DataFrame(
        {
            "year": [1992, 2001, 1992],
            "filename": ["one.txt", "two.txt", "three.txt"],
            "meeting_symbol": ["S/PV.1", "S/PV.2", "S/PV.3"],
            "date": pd.to_datetime(["1992-01-01", "2001-01-01", "1992-02-01"]),
            "country_org": ["A", "B", "C"],
            "agenda_item_manual": ["x", "y", "z"],
        }
    )
    counts = lexicon.apply(bodies, lex)

    sample = _audit_step().audit_sample(speeches, bodies, counts, lex, size=2, seed=12)

    assert set(sample["sampling_frame"]) == {
        audit.PROBABILITY,
        audit.COVERAGE,
        audit.NEGATIVE,
    }
    negative = sample.loc[sample["sampling_frame"] == audit.NEGATIVE]
    assert negative["keyword"].tolist() == ["genecide"]
    assert negative["inclusion_probability"].tolist() == [1.0]


def test_empty_annotations_leave_one_review_row_per_candidate() -> None:
    review = audit.merge(candidates(), annotations())
    assert list(review["candidate_id"]) == ["candidate-1", "candidate-2"]
    assert review["coder"].tolist() == ["", ""]


def test_two_coders_may_independently_code_the_same_occurrence() -> None:
    labels = annotations(
        annotation("occurrence-1", "coder-a"),
        annotation("occurrence-1", "coder-b", verdict="uncertain"),
    )
    review = audit.merge(candidates(), labels)
    assert list(review.loc[review["occurrence_id"] == "occurrence-1", "coder"]) == [
        "coder-a",
        "coder-b",
    ]


def test_one_coder_cannot_label_an_occurrence_twice() -> None:
    labels = annotations(annotation("occurrence-1"), annotation("occurrence-1"))
    with pytest.raises(ValueError, match="only once"):
        audit.merge(candidates(), labels)


def test_unknown_occurrence_ids_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown occurrence IDs"):
        audit.merge(candidates(), annotations(annotation("not-in-candidates")))


def test_incompatible_annotation_schema_is_refused() -> None:
    labels = annotations(annotation("occurrence-1", schema_version="99"))
    with pytest.raises(ValueError, match="schema is incompatible"):
        audit.merge(candidates(), labels)


def test_incompatible_lexicon_version_is_refused() -> None:
    labels = annotations(annotation("occurrence-1", lexicon_version="3"))
    with pytest.raises(ValueError, match="lexicon is incompatible"):
        audit.merge(candidates(), labels)


def at_lexicon_version(version: int) -> pd.DataFrame:
    """Candidates as 03 and 13 regenerate them: at the current lexicon version.

    The annotations were coded earlier, against version 2, and keep saying so.
    """
    return candidates().assign(lexicon_version=version)


def test_a_bump_that_left_the_annotated_term_alone_still_merges() -> None:
    """Both scripts regenerate their candidates at the current version, so under
    strict equality a bump alone would refuse every coded row. What decides is
    whether the term still enumerates the same occurrences, which is what
    `Lexicon.compatible` answers."""
    review = audit.merge(
        at_lexicon_version(3),
        annotations(annotation("occurrence-1")),
        compatible=lambda term, version: True,
    )
    coded = review.loc[review["occurrence_id"] == "occurrence-1", "coder"]
    assert coded.tolist() == ["coder-a"]


def test_an_annotation_whose_term_has_moved_since_is_refused() -> None:
    """Editing `genocide`'s pattern is what the rule is there to catch: the row
    annotates occurrences the corpus no longer has."""
    with pytest.raises(ValueError, match=r"occurrence-1.+'genocide'"):
        audit.merge(
            at_lexicon_version(3),
            annotations(annotation("occurrence-1")),
            compatible=lambda term, version: False,
        )


def test_the_strict_version_rule_stands_when_no_compatibility_is_given() -> None:
    with pytest.raises(ValueError, match="lexicon is incompatible"):
        audit.merge(at_lexicon_version(3), annotations(annotation("occurrence-1")))


def test_an_unknown_occurrence_is_reported_as_unknown_not_as_incompatible() -> None:
    """Order matters in the message a coder reads: a mistyped ID is a typo, not
    a stale lexicon."""
    with pytest.raises(ValueError, match="unknown occurrence IDs"):
        audit.merge(
            at_lexicon_version(3),
            annotations(annotation("not-in-candidates")),
            compatible=lambda term, version: False,
        )


def test_unknown_controlled_label_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown stance label"):
        audit.merge(candidates(), annotations(annotation("occurrence-1", stance="agrees")))


def test_multiple_functions_use_distinct_pipe_separated_labels() -> None:
    labels = annotations(
        annotation(
            "occurrence-1",
            function="accusation_or_qualification|warning_or_prevention",
        )
    )
    review = audit.merge(candidates(), labels)
    assert review.loc[0, "function"] == "accusation_or_qualification|warning_or_prevention"


def test_false_positive_requires_not_applicable_discourse_fields() -> None:
    wrong = annotations(annotation("occurrence-1", verdict="false_positive"))
    with pytest.raises(ValueError, match="must use not_applicable"):
        audit.merge(candidates(), wrong)
    valid = annotations(
        annotation(
            "occurrence-1",
            verdict="false_positive",
            quotation="not_applicable",
            stance="not_applicable",
            function="not_applicable",
            referent="not_applicable",
        )
    )
    assert audit.merge(candidates(), valid).loc[0, "verdict"] == "false_positive"


def test_evidence_span_must_contain_the_match_and_stay_inside_the_source() -> None:
    with pytest.raises(ValueError, match="Evidence span"):
        audit.merge(
            candidates(),
            annotations(annotation("occurrence-1", evidence_start="11", evidence_end="18")),
        )


def test_coding_date_must_be_iso_and_referent_must_be_controlled() -> None:
    with pytest.raises(ValueError, match="ISO date"):
        audit.merge(candidates(), annotations(annotation("occurrence-1", coded_at="today")))
    with pytest.raises(ValueError, match="ISO date"):
        audit.merge(candidates(), annotations(annotation("occurrence-1", coded_at="20260824")))
    with pytest.raises(ValueError, match="Unknown referent"):
        audit.merge(candidates(), annotations(annotation("occurrence-1", referent="rwanda")))


def test_referent_file_requires_columns_unique_ids_and_reserved_values(tmp_path) -> None:
    path = tmp_path / "referents.csv"
    path.write_text(
        "id,label,description\nother,Other,Known\nunclear,Unclear,Unknown\n"
        "not_applicable,N/A,False positive\n",
        encoding="utf-8",
    )
    assert audit.read_referents(path) == audit.DEFAULT_REFERENTS

    path.write_text("id,label,description\nother,Other,Known\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing reserved IDs"):
        audit.read_referents(path)


def referent_path() -> Path:
    return ROOT / "annotations" / "lexicon" / "referents.csv"


def referent_table() -> pd.DataFrame:
    return pd.read_csv(referent_path(), dtype="string", keep_default_na=False)


def test_committed_referents_are_readable_and_keep_the_reserved_identifiers() -> None:
    referents = audit.read_referents(referent_path())
    assert referents >= audit.DEFAULT_REFERENTS
    assert len(referents) > len(audit.DEFAULT_REFERENTS)


def test_committed_referent_ids_use_one_spelling_convention() -> None:
    identifiers = referent_table()["id"].tolist()
    assert [value for value in identifiers if not REFERENT_ID.fullmatch(value)] == []
    assert len(set(identifiers)) == len(identifiers)


def test_committed_referents_declare_a_kind_and_reserve_the_defaults() -> None:
    table = referent_table()
    assert "kind" in table.columns
    unknown = sorted(set(table["kind"]) - REFERENT_KINDS)
    assert unknown == []
    reserved = table.loc[table["id"].isin(audit.DEFAULT_REFERENTS), "kind"]
    assert len(reserved) == len(audit.DEFAULT_REFERENTS)
    assert set(reserved) == {"reserved"}


def test_duplicate_generated_candidate_ids_are_refused() -> None:
    duplicate = pd.concat([candidates(), candidates().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Candidate IDs must be unique"):
        audit.merge(duplicate, annotations())


def test_writing_generated_outputs_does_not_change_human_annotations(tmp_path) -> None:
    annotation_path = tmp_path / "annotations.csv"
    candidate_path = tmp_path / "candidates.csv"
    review_path = tmp_path / "review.csv"
    probability_path = tmp_path / "probability.csv"
    coverage_path = tmp_path / "coverage.csv"
    original = annotations(annotation("occurrence-1")).to_csv(index=False, lineterminator="\n")
    annotation_path.write_text(original, encoding="utf-8")

    audit.write_outputs(
        candidates(),
        annotation_path=annotation_path,
        candidate_path=candidate_path,
        review_path=review_path,
        frame_paths={
            audit.PROBABILITY: probability_path,
            audit.COVERAGE: coverage_path,
        },
    )

    assert annotation_path.read_text(encoding="utf-8") == original
    assert "candidate-1" in candidate_path.read_text(encoding="utf-8")
    assert "coder-a" in review_path.read_text(encoding="utf-8")
    assert "candidate-1" in probability_path.read_text(encoding="utf-8")
    assert "candidate-2" in coverage_path.read_text(encoding="utf-8")


def test_invalid_annotations_leave_previous_generated_outputs_intact(tmp_path) -> None:
    annotation_path = tmp_path / "annotations.csv"
    candidate_path = tmp_path / "candidates.csv"
    review_path = tmp_path / "review.csv"
    original = annotations(annotation("unknown")).to_csv(index=False, lineterminator="\n")
    annotation_path.write_text(original, encoding="utf-8")
    candidate_path.write_text("previous candidates\n", encoding="utf-8")
    review_path.write_text("previous review\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown occurrence IDs"):
        audit.write_outputs(
            candidates(),
            annotation_path=annotation_path,
            candidate_path=candidate_path,
            review_path=review_path,
        )

    assert annotation_path.read_text(encoding="utf-8") == original
    assert candidate_path.read_text(encoding="utf-8") == "previous candidates\n"
    assert review_path.read_text(encoding="utf-8") == "previous review\n"
