"""The single enumeration of a term's occurrences that 13, 14 and 15 share."""

from __future__ import annotations

import re

import pandas as pd
import pytest
from lib import audit, frames, lexicon, occurrences

ADDRESS = "Mr. Levitte (France) (spoke in French): "
BODIES = (
    "The genocide in Rwanda, and the genocidal intent behind it.",
    "Nothing of the sort was said in this speech.",
    "Genocide.",
)


def term(pattern: str = r"\bgenocid\w*") -> lexicon.Term:
    return lexicon.Term(
        name="genocide",
        pattern=pattern,
        tier="core",
        register="core",
        examples=("genocide",),
        prefilters=("genocid",),
        regex=re.compile(pattern, re.IGNORECASE),
    )


def corpus() -> tuple[pd.DataFrame, pd.Series]:
    speeches = pd.DataFrame(
        {
            "filename": ["one.txt", "two.txt", "three.txt"],
            "text": [ADDRESS + body for body in BODIES],
            "body_start": [len(ADDRESS)] * 3,
        }
    )
    return speeches, frames.body(speeches)


def test_identity_is_the_audit_id_over_body_relative_offsets() -> None:
    speeches, bodies = corpus()
    first = occurrences.enumerate_term(speeches, bodies, term())[0]
    assert first.occurrence_id == audit.occurrence_id(
        "one.txt", "genocide", 4, 12, "genocide", audit.source_sha256(BODIES[0])
    )


def test_both_coordinate_systems_select_the_matched_word() -> None:
    speeches, bodies = corpus()
    first = occurrences.enumerate_term(speeches, bodies, term())[0]
    assert (first.start, first.end) == (4, 12)
    assert bodies[0][first.start : first.end] == "genocide"
    assert first.start_text == len(ADDRESS) + 4
    assert speeches.at[0, "text"][first.start_text : first.end_text] == "genocide"


def test_ordinals_restart_per_speech_and_follow_match_order() -> None:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    assert [(item.line_id, item.keyword) for item in found] == [
        ("one#1", "genocide"),
        ("one#2", "genocidal"),
        ("three#1", "Genocide"),
    ]
    assert [item.ordinal for item in found] == [1, 2, 1]


def test_speeches_without_a_match_contribute_no_rows() -> None:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    assert "two.txt" not in {item.filename for item in found}


def test_missing_columns_are_named_rather_than_raising_deeper_in() -> None:
    speeches, bodies = corpus()
    with pytest.raises(KeyError, match="body_start, filename"):
        occurrences.enumerate_term(
            speeches.drop(columns=["filename", "body_start"]), bodies, term()
        )


def test_frame_carries_every_field_of_the_record() -> None:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    frame = occurrences.frame(found)
    assert list(frame.columns) == [
        "index",
        "filename",
        "line_id",
        "ordinal",
        "start",
        "end",
        "start_text",
        "end_text",
        "keyword",
        "source_sha256",
        "occurrence_id",
    ]
    assert len(frame) == len(found)
