"""R9's nested reading sets and meeting-level vocabulary inventory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
from lib import scopes

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "meeting_export", ROOT / "scripts" / "09_export_speeches.py"
)
assert SPEC and SPEC.loader
meeting_export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(meeting_export)


def corpus() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "meeting_symbol": ["A", "A", "B", "C"],
            "has_genocide": [True, False, False, False],
            "has_ethnic_cleansing": [False, True, True, False],
            "has_crimes_against_humanity": [False, False, True, False],
            "has_war_crimes": [False, False, False, False],
        }
    )


def test_scopes_are_nested_reading_sets_with_one_fixed_source() -> None:
    rows = scopes.summary(corpus())

    assert [(row["id"], row["speeches"]) for row in rows] == [
        ("word", 1),
        ("vocabulary", 3),
        ("debate", 2),
    ]
    assert [(row["id"], row["meetings"]) for row in rows] == [
        ("word", 1),
        ("vocabulary", 2),
        ("debate", 1),
    ]


def test_scope_predicate_refuses_a_missing_flag() -> None:
    try:
        scopes.speech_masks(corpus().drop(columns="has_war_crimes"))
    except ValueError as error:
        assert "has_war_crimes" in str(error)
    else:
        raise AssertionError("a partial scope predicate was accepted")


def test_meeting_inventory_counts_each_speech_once_and_names_delegations() -> None:
    speeches = [
        {
            "country": "France",
            "iso3": "FRA",
            "group": "P5",
            "type": "member",
            "hits": {"genocide": [[2, 10]], "war_crimes": [[20, 30]]},
        },
        {
            "country": "France",
            "iso3": "FRA",
            "group": "P5",
            "type": "member",
            "hits": {"ethnic_cleansing": [[4, 21]]},
        },
        {
            "country": "Rwanda",
            "iso3": "RWA",
            "group": "Elected",
            "type": "member",
            "hits": {},
        },
    ]

    assert meeting_export.meeting_scope_counts(speeches) == {
        "word": 1,
        "vocabulary": 2,
        "debate": 3,
    }
    assert meeting_export.delegations(speeches) == [
        {
            "country": "France",
            "iso3": "FRA",
            "group": "P5",
            "type": "member",
            "speeches": 2,
            "terms": ["ethnic_cleansing", "genocide", "war_crimes"],
        },
        {
            "country": "Rwanda",
            "iso3": "RWA",
            "group": "Elected",
            "type": "member",
            "speeches": 1,
            "terms": [],
        },
    ]
