"""The genocide gold sample: cue strata, a repeatable draw, and the refusal."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest
from lib import audit, frames, lexicon, occurrences


def _gold_step():
    path = Path(__file__).resolve().parents[1] / "scripts" / "13_gold_sample.py"
    spec = importlib.util.spec_from_file_location("gold_sample_step", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gold = _gold_step()

DENSE = "S/PV.7155"  # one of the seven meetings of docs/CORPUS.md §8.6
ORDINARY = "S/PV.9999"


def cue(left: str, right: str, meeting_symbol: str = ORDINARY, keyword: str = "genocide") -> str:
    return gold.classify_cue(left, keyword, right, meeting_symbol)


# --- The cues -------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("confirming that no", "had taken place in Darfur"),
        ("the question of whether or not", "had been committed"),
        ("cooked-up lies about so-called", "and forced labour in Xinjiang"),
        ("top fugitive and alleged", "financier remains at large"),
        ("a tribunal which refuses to consider the causes of the", "in Rwanda"),
    ],
)
def test_rejection_language_is_recognised(left: str, right: str) -> None:
    assert cue(left, right) == "rejection"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # "so-called" attaches to the group, not to the characterisation.
        ("the so-called Islamic State committed", "against the Yazidis"),
        ("no one denies the", "in Rwanda"),
        ("the Special Adviser on the Prevention of", "briefed the Council"),
    ],
)
def test_rejection_does_not_fire_on_the_word_used_plainly(left: str, right: str) -> None:
    assert cue(left, right) == "plain"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ('the Commission called it "', '" in its report'),
        ("the witness said “", "”"),
        ("he closed with the word genocide,” and sat down. The", "was denied"),
    ],
)
def test_a_double_quote_in_either_context_marks_reported_speech(left: str, right: str) -> None:
    assert cue(left, right) == "quotation"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("the Council's own report on the", "in Srebrenica"),
        ("no quotation marks anywhere near this", "at all"),
    ],
)
def test_apostrophes_are_not_quotation(left: str, right: str) -> None:
    assert cue(left, right) == "plain"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("today we commemorate the", "of 1994"),
        ("on the twentieth anniversary of the", "in Rwanda"),
        ("we remember the victims of the", "every April"),
        ("a minute of silence in memory of the victims of the", "was observed"),
        ("efforts to honour the victims of the", "have taken place"),
        ("efforts to honor the victims of the", "have taken place"),
    ],
)
def test_the_commemorative_register_is_recognised(left: str, right: str) -> None:
    assert cue(left, right) == "commemorative"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("the memorandum of understanding on", "prevention was signed"),
        ("the Council recalls its report on the", "in Rwanda"),
    ],
)
def test_the_commemorative_patterns_do_not_fire_on_neighbouring_words(
    left: str, right: str
) -> None:
    assert cue(left, right) == "plain"


def test_a_dense_meeting_is_the_stratum_of_last_resort_before_plain() -> None:
    assert cue("the", "in Rwanda was planned", DENSE) == "dense_meeting"
    assert cue("the", "in Rwanda was planned", ORDINARY) == "plain"


def test_the_rarest_cue_wins_when_a_window_carries_several() -> None:
    # Rejection language inside a quotation inside a dense meeting.
    assert cue('the Ambassador said "there was no', '" in Darfur', DENSE) == "rejection"
    # A quoted commemoration is sampled as a quotation.
    assert cue('on the anniversary he said "', '"', DENSE) == "quotation"
    # A commemoration in a dense meeting is sampled as a commemoration.
    assert cue("today we commemorate the", "of 1994", DENSE) == "commemorative"


# --- The population and the draw ------------------------------------------

PATTERN = r"\bgenocid\w*"
ADDRESS = "Mr. Levitte (France): "
SPEECHES = (
    # body, year, meeting symbol, expected cue
    ("There was no genocide, they insisted.", 1994, "S/PV.3453", "rejection"),
    ('The Commission called it "genocide" in its report.', 2004, "S/PV.5000", "quotation"),
    ("Today we commemorate the genocide of 1994.", 2014, DENSE, "commemorative"),
    ("The genocide in Rwanda was planned.", 2014, DENSE, "dense_meeting"),
    ("The genocide there continues.", 2020, "S/PV.9000", "plain"),
)


def term() -> lexicon.Term:
    return lexicon.Term(
        name="genocide",
        pattern=PATTERN,
        tier="core",
        register="core",
        examples=("genocide",),
        prefilters=("genocid",),
        regex=re.compile(PATTERN, re.IGNORECASE),
    )


def corpus() -> tuple[pd.DataFrame, pd.Series]:
    speeches = pd.DataFrame(
        {
            "filename": [f"speech-{number}.txt" for number in range(len(SPEECHES))],
            "text": [ADDRESS + body for body, *_ in SPEECHES],
            "body_start": [len(ADDRESS)] * len(SPEECHES),
            "year": [year for _, year, *_ in SPEECHES],
            "meeting_symbol": [symbol for *_, symbol, _ in SPEECHES],
            "date": pd.to_datetime([f"{year}-04-07" for _, year, *_ in SPEECHES]),
            "country_org": ["Rwanda"] * len(SPEECHES),
            "agenda_item_manual": ["Rwanda"] * len(SPEECHES),
        }
    )
    return speeches, frames.body(speeches)


def built() -> pd.DataFrame:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    lex = lexicon.Lexicon(version=2, updated="2026-08-09", terms={"genocide": term()}, sets={})
    return gold.candidate_rows(speeches, bodies, found, term(), lex)


def test_candidates_carry_the_audit_columns_plus_the_cue_and_the_kwic_id() -> None:
    candidates = built()
    assert candidates["cue"].tolist() == [expected for *_, expected in SPEECHES]
    assert candidates["period"].tolist() == ["1990s", "2000s", "2010s", "2010s", "2020s"]
    assert candidates["line_id"].tolist() == [f"speech-{n}#1" for n in range(len(SPEECHES))]
    assert {"occurrence_id", "term", "start", "end", "source_sha256", "source_length"} <= set(
        candidates.columns
    )


def test_the_drawn_sample_satisfies_what_the_merge_requires() -> None:
    sample = gold.draw(built(), 3, 5, 21)
    assert set(sample.columns) >= audit.CANDIDATE_REQUIRED
    assert set(sample["sampling_frame"]) == {audit.PROBABILITY, audit.COVERAGE}


def test_the_coverage_frame_holds_every_period_cue_stratum() -> None:
    candidates = built()
    coverage = gold.draw(candidates, 3, 5, 21).pipe(
        lambda sample: sample.loc[sample["sampling_frame"] == audit.COVERAGE]
    )
    assert set(zip(coverage["period"], coverage["cue"], strict=True)) == set(
        zip(candidates["period"], candidates["cue"], strict=True)
    )


def frame(size: int = 40) -> pd.DataFrame:
    """A synthetic candidate frame covering all twenty period-cue strata twice."""
    periods = ("1990s", "2000s", "2010s", "2020s")
    rows = []
    for number in range(size):
        rows.append(
            {
                "occurrence_id": f"occurrence-{number:03d}",
                "term": "genocide",
                "period": periods[number % len(periods)],
                "cue": gold.CUES[number % len(gold.CUES)],
                "filename": f"speech-{number:03d}.txt",
                "start": number,
            }
        )
    return pd.DataFrame(rows)


def test_the_same_seed_draws_the_same_sample_whatever_the_row_order() -> None:
    first = gold.draw(frame(), 8, 20, 21)
    again = gold.draw(frame(), 8, 20, 21)
    shuffled = gold.draw(frame().sample(frac=1, random_state=3).reset_index(drop=True), 8, 20, 21)
    assert first["candidate_id"].tolist() == again["candidate_id"].tolist()
    assert set(first["candidate_id"]) == set(shuffled["candidate_id"])


def test_an_occurrence_in_both_frames_keeps_one_row_in_each() -> None:
    # A probability draw as large as the population puts every coverage
    # occurrence in both frames, which is the overlap the real run has five of.
    sample = gold.draw(frame(), 40, 20, 21)
    assert (len(sample), sample["occurrence_id"].nunique()) == (60, 40)
    assert not sample["candidate_id"].duplicated().any()
    for _, rows in sample.loc[sample["occurrence_id"].duplicated(keep=False)].groupby(
        "occurrence_id"
    ):
        assert sorted(rows["sampling_frame"]) == sorted([audit.PROBABILITY, audit.COVERAGE])
        assert rows["candidate_id"].nunique() == 2


# --- The refusal ----------------------------------------------------------


def test_a_population_that_is_not_the_documented_one_is_refused() -> None:
    speeches, bodies = corpus()
    problems = gold.check_population(occurrences.enumerate_term(speeches, bodies, term()))
    assert len(problems) == 2
    assert "6,092" in problems[0] and "3,273" in problems[1]
    assert all("docs/CORPUS.md §8" in problem for problem in problems)


def test_the_documented_population_passes_without_comment(monkeypatch) -> None:
    speeches, bodies = corpus()
    monkeypatch.setattr(gold, "DOCUMENTED_OCCURRENCES", len(SPEECHES))
    monkeypatch.setattr(gold, "DOCUMENTED_SPEECHES", len(SPEECHES))
    assert gold.check_population(occurrences.enumerate_term(speeches, bodies, term())) == []
