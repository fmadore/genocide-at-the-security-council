"""Step 04's payload: the R8 comparison corpus, what 04 reads, and the one
withholding rule its year, quarter, month and breakdown cells share."""

from __future__ import annotations

import importlib

import pandas as pd
import pytest
from conftest import OPENING, make_speeches
from lib import council, lexicon, scopes, series, series_payload

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
    for column, _ in series_payload.BREAKDOWNS:
        assert column in read
    assert series_payload.CALENDAR_AGENDA_COLUMN in read
    assert {"has_genocide", *(f"has_{term}" for term in scopes.ATROCITY_TERMS)} <= set(read)


# --- One withholding rule at every grain ------------------------------------
#
# A small corpus whose arithmetic can be done by hand. 2000 holds six speeches,
# three in February and three in August, two of them using the word; 2001 holds
# two in March, one using it, and a single speech by an elected member that
# also uses it. Under a minimum of four, 2000 is drawn and 2001 is withheld.

SAYS = OPENING + "The genocide in the region must be prevented."
SILENT = OPENING + "I thank you for convening this meeting."


def thin_corpus() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for i in range(6):
        permanent = i % 2 == 1
        rows.append(
            {
                "year": 2000,
                "date": f"2000-{'02' if i < 3 else '08'}-1{i}",
                "meeting_symbol": f"S/PV.{10 + i // 2}",
                "text": SAYS if i in (0, 3) else SILENT,
                "speaker_group": council.PERMANENT if permanent else council.NON_MEMBER,
                "country_org": "France" if permanent else "Chad",
            }
        )
    for i, text in enumerate((SAYS, SILENT)):
        rows.append(
            {
                "year": 2001,
                "date": f"2001-03-0{5 + i}",
                "meeting_symbol": "S/PV.20",
                "text": text,
                "speaker_group": council.NON_MEMBER,
                "country_org": "Chad",
            }
        )
    rows.append(
        {
            "year": 2001,
            "date": "2001-03-07",
            "meeting_symbol": "S/PV.20",
            "text": SAYS,
            "speaker_group": council.ELECTED,
            "country_org": "Ghana",
        }
    )
    return make_speeches(rows, flagged=True)


class TestBuildSeriesWithholding:
    def build(self, **kwargs):
        return series_payload.build_series(thin_corpus(), lexicon.load(), "year", **kwargs)

    def test_a_thin_year_keeps_its_counts_and_loses_every_rate(self) -> None:
        payload, _ = self.build(minimum=4)
        genocide = payload["terms"]["genocide"]

        assert payload["periods"] == [2000, 2001]
        assert payload["sufficient"] == [True, False]
        assert payload["minimum_speeches"] == 4
        assert payload["corpus"]["speeches"] == [6, 3]
        # The counts are facts about the record and are written either way.
        assert genocide["speeches"] == [2, 2]
        assert genocide["occurrences"] == [2, 2]
        assert genocide["speech_rate"] == [round(2 / 6, 6), None]
        for key in (
            "speech_rate_low",
            "speech_rate_high",
            "speech_rate_cluster_low",
            "speech_rate_cluster_high",
            "token_rate",
        ):
            assert genocide[key][0] is not None, key
            assert genocide[key][1] is None, key
        # The comparison corpus follows the same rule.
        assert payload["corpora"]["genocide_free_atrocity"]["speech_rate"][1] is None

    def test_the_computed_frames_are_not_withheld(self) -> None:
        """The change-point pass needs a series without holes."""
        _, computed = self.build(minimum=4)
        frame = computed["terms"]["genocide"]
        assert frame.loc[2001, "speech_rate"] == pytest.approx(2 / 3)
        assert "sufficient" not in frame.columns

    def test_without_a_minimum_nothing_is_withheld(self) -> None:
        payload, _ = self.build()
        assert "sufficient" not in payload and "minimum_speeches" not in payload
        assert payload["terms"]["genocide"]["speech_rate"][1] == round(2 / 3, 6)

    def test_the_record_dates_are_the_corpus_bounds(self) -> None:
        payload, _ = self.build(minimum=4)
        assert payload["record"] == {"first_date": "2000-02-10", "last_date": "2001-03-07"}

    def test_a_quarter_nobody_spoke_in_is_zeros_and_insufficient(self) -> None:
        payload, _ = series_payload.build_series(
            thin_corpus(),
            lexicon.load(),
            "quarter",
            index=series.quarter_grid("2000Q1", "2001Q1"),
            minimum=3,
        )
        assert payload["periods"] == ["2000Q1", "2000Q2", "2000Q3", "2000Q4", "2001Q1"]
        assert payload["corpus"]["speeches"] == [3, 0, 3, 0, 3]
        assert payload["corpus"]["meetings"][1] == 0
        assert payload["sufficient"] == [True, False, True, False, True]
        genocide = payload["terms"]["genocide"]
        assert genocide["speeches"][1] == 0 and genocide["occurrences"][1] == 0
        assert genocide["speech_rate"][1] is None
        assert genocide["speech_rate_cluster_high"][1] is None
        assert genocide["speech_rate"][0] == round(1 / 3, 6)


class TestBreakdownWithholding:
    def rows(self, minimum: int) -> list[dict[str, object]]:
        out = series_payload.build_breakdowns(thin_corpus(), "year", 5, minimum)
        assert out["minimum_speeches"] == minimum
        return out["measures"]["genocide"]["speaker_group"]["rows"]  # type: ignore[index]

    def test_a_cell_of_one_speech_that_used_the_word_has_no_rate(self) -> None:
        """One of one is 100%, and that is what set a chart's axis to 100%."""
        cell = next(r for r in self.rows(3) if r["category"] == council.ELECTED)
        assert (cell["held"], cell["speeches"], cell["occurrences"]) == (1, 1, 1)
        assert cell["sufficient"] is False
        for key in ("speech_rate", "speech_rate_low", "speech_rate_high", "token_rate"):
            assert cell[key] is None, key

    def test_a_cell_at_the_minimum_keeps_its_rate(self) -> None:
        cell = next(
            r for r in self.rows(3) if r["period"] == 2000 and r["category"] == council.PERMANENT
        )
        assert cell["held"] == 3
        assert cell["sufficient"] is True
        assert cell["speech_rate"] == round(1 / 3, 6)
        assert cell["token_rate"] is not None


class TestMonthlyRecord:
    def test_the_record_and_the_months_outside_it(self) -> None:
        """The grid runs over whole years; the record need not."""
        monthly = series_payload.build_monthly(thin_corpus(), lexicon.load(), 3)
        assert monthly["record"] == {
            "first_date": "2000-02-10",
            "last_date": "2001-03-07",
            "first_period": "2000-02",
            "last_period": "2001-03",
        }
        coverage = monthly["coverage"]
        assert coverage["months"] == 24
        # January 2000 before the record, April to December 2001 after it.
        assert coverage["months_outside_record"] == 1 + 9
        assert coverage["months_observed"] == 3
