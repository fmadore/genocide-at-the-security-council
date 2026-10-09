"""The named R8 comparison corpus written by step 04, and what 04 reads."""

from __future__ import annotations

import importlib

import pandas as pd
from lib import lexicon, scopes, series

step = importlib.import_module("04_series")


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
    block = scopes.comparison_corpora(speeches, periods, totals)["genocide_free_atrocity"]

    # The first speech carries two member phrases but enters once; the second
    # carries one member but is excluded because it also says genocide.
    assert block["speeches"] == [1, 1]
    assert block["speech_rate"] == [round(1 / 3, 6), 1.0]
    assert block["members"] == list(scopes.GENOCIDE_FREE_ATROCITY_TERMS)
    assert block["excludes"] == ["genocide"]


def test_comparison_corpus_refuses_a_missing_membership_column() -> None:
    speeches = corpus().drop(columns="has_war_crimes")
    periods = series.period(speeches, "year")
    totals = series.denominators(speeches, periods)

    try:
        scopes.comparison_corpora(speeches, periods, totals)
    except ValueError as error:
        assert "has_war_crimes" in str(error)
    else:
        raise AssertionError("missing corpus predicate column was accepted")


def test_the_step_reads_every_measure_and_no_text() -> None:
    """04 counts speeches and words; the text is most of the parquet and unused.

    A breakdown column left out would not fail: `build_breakdowns` skips a
    column the frame lacks with a warning, so each one is held here.
    """
    lex = lexicon.load()
    read = step.read_columns(lex)
    assert "text" not in read and "body_start" not in read
    assert len(read) == len(set(read))
    for term in lex.active:
        assert {f"has_{term.name}", f"n_{term.name}"} <= set(read), term.name
    for column, _ in step.BREAKDOWNS:
        assert column in read
    assert step.CALENDAR_AGENDA_COLUMN in read
    assert {"has_genocide", *(f"has_{term}" for term in scopes.ATROCITY_TERMS)} <= set(read)
