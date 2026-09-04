"""The named R8 comparison corpus written by step 04."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
from lib import series

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("series_step", ROOT / "scripts" / "04_series.py")
assert SPEC and SPEC.loader
step = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(step)


def corpus() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": ["a", "b", "c", "d"],
            "year": [2000, 2000, 2000, 2001],
            "words": [100, 100, 100, 100],
            "tokens": [110, 110, 110, 110],
            "meeting_symbol": ["A", "A", "B", "C"],
            "has_genocide": [False, True, False, False],
            "has_ethnic_cleansing": [True, False, False, False],
            "has_crimes_against_humanity": [True, True, False, False],
            "has_war_crimes": [False, False, False, True],
        }
    )


def test_genocide_free_atrocity_is_a_union_of_speeches_not_term_counts() -> None:
    speeches = corpus()
    periods = series.period(speeches, "year")
    totals = series.denominators(speeches, periods)
    block = step.comparison_corpora(speeches, periods, totals)["genocide_free_atrocity"]

    # The first speech carries two member phrases but enters once; the second
    # carries one member but is excluded because it also says genocide.
    assert block["speeches"] == [1, 1]
    assert block["speech_rate"] == [round(1 / 3, 6), 1.0]
    assert block["members"] == list(step.GENOCIDE_FREE_ATROCITY_TERMS)
    assert block["excludes"] == ["genocide"]


def test_comparison_corpus_refuses_a_missing_membership_column() -> None:
    speeches = corpus().drop(columns="has_war_crimes")
    periods = series.period(speeches, "year")
    totals = series.denominators(speeches, periods)

    try:
        step.comparison_corpora(speeches, periods, totals)
    except ValueError as error:
        assert "has_war_crimes" in str(error)
    else:
        raise AssertionError("missing corpus predicate column was accepted")
