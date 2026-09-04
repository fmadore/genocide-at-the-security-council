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


# --- The disagreement frame -----------------------------------------------


def annotated(occurrence: str, **changes: str) -> dict[str, object]:
    return {
        "occurrence_id": occurrence,
        "speaker_position": "asserts",
        "referent": "rwanda_1994",
        **changes,
    }


def strata_frame() -> pd.DataFrame:
    """One candidate per stratum, plus one the design leaves out."""
    rows = [
        ("occ-rejects", "2010-01-01"),
        ("occ-preonset", "2010-01-01"),
        ("occ-other", "2010-01-01"),
        ("occ-attributes", "2010-01-01"),
        ("occ-hypothetical", "2010-01-01"),
        ("occ-contested", "2010-01-01"),
        ("occ-agreed", "2010-01-01"),
        ("occ-unreached", "2010-01-01"),
    ]
    return pd.DataFrame(
        [
            {
                "occurrence_id": occurrence,
                "term": "genocide",
                "date": date,
                "period": "2010s",
                "cue": "plain",
                "filename": f"{occurrence}.txt",
                "start": index,
            }
            for index, (occurrence, date) in enumerate(rows)
        ]
    )


PUBLISHED = {
    "occ-rejects": annotated("occ-rejects", speaker_position="rejects"),
    "occ-preonset": annotated("occ-preonset", referent="gaza"),
    "occ-other": annotated("occ-other", referent="other"),
    "occ-attributes": annotated("occ-attributes", speaker_position="reports_without_position"),
    "occ-hypothetical": annotated("occ-hypothetical", speaker_position="conditional"),
    "occ-contested": annotated("occ-contested", referent="bosnia_srebrenica"),
    "occ-agreed": annotated("occ-agreed"),
}
COMPARISON = {
    key: annotated(key) if key != "occ-rejects" else value
    for key, value in PUBLISHED.items()
}
ONSETS = {"gaza": 2023, "rwanda_1994": 1994}


def stratum_of(occurrence: str) -> str:
    row = strata_frame().set_index("occurrence_id").loc[occurrence]
    return gold.classify_stratum(
        row.rename(occurrence).to_frame().T.assign(occurrence_id=occurrence).iloc[0],
        PUBLISHED,
        COMPARISON,
        ONSETS,
    )


def test_every_stratum_is_recognised_from_the_two_runs() -> None:
    assert stratum_of("occ-rejects") == "rejects"
    # The published run put Gaza on a 2010 speech; `years` is documentation, so
    # this is a question for a coder rather than an error the sample declares.
    assert stratum_of("occ-preonset") == "pre_onset_referent"
    assert stratum_of("occ-other") == "other_referent"
    assert stratum_of("occ-attributes") == "reports_without_position"
    assert stratum_of("occ-hypothetical") == "conditional"
    assert stratum_of("occ-contested") == "contested_speaker_position_or_referent"
    # Two runs that agree on stance and referent are outside the frame.
    assert stratum_of("occ-agreed") == ""
    # And an occurrence only one run reached has nothing to disagree about.
    assert stratum_of("occ-unreached") == ""


def test_the_strata_are_disjoint_and_the_rarest_wins() -> None:
    # One occurrence carrying four of the six properties at once. Precedence is
    # what keeps a row's inclusion probability a single number.
    published = {"occ": annotated("occ", speaker_position="rejects", referent="other")}
    comparison = {"occ": annotated("occ", speaker_position="reports_without_position", referent="gaza")}
    row = strata_frame().iloc[0].copy()
    row["occurrence_id"] = "occ"
    assert gold.classify_stratum(row, published, comparison, ONSETS) == "rejects"


def test_the_frame_records_a_probability_per_stratum_and_a_census_where_it_takes_all() -> None:
    candidates = strata_frame().assign(
        stratum=[
            "rejects",
            "pre_onset_referent",
            "other_referent",
            "other_referent",
            "other_referent",
            "reports_without_position",
            "",
            "",
        ]
    )
    sample = audit.stratified_sample(
        candidates,
        {"rejects": None, "other_referent": 2, "reports_without_position": 5},
        21,
        gold.DISAGREEMENT,
    )
    counts = sample["stratum"].value_counts().to_dict()
    assert counts == {"other_referent": 2, "rejects": 1, "reports_without_position": 1}
    census = sample.loc[sample["stratum"] == "rejects"].iloc[0]
    assert (census["inclusion_probability"], census["sampling_weight"]) == (1.0, 1.0)
    # Two of three: probability 2/3, weight 3/2, and the stratum size recorded.
    drawn = sample.loc[sample["stratum"] == "other_referent"].iloc[0]
    assert drawn["inclusion_probability"] == pytest.approx(2 / 3)
    assert drawn["sampling_weight"] == pytest.approx(3 / 2)
    assert drawn["stratum_size"] == 3
    # A stratum smaller than its size is taken whole rather than refused.
    short = sample.loc[sample["stratum"] == "reports_without_position"].iloc[0]
    assert short["inclusion_probability"] == 1.0
    # Rows outside every stratum are outside the frame.
    assert "" not in set(sample["stratum"])
    # And the frame digest is over the whole candidate set, not the draw.
    assert sample["frame_size"].unique().tolist() == [len(candidates)]


def test_the_stratified_draw_is_reproducible_from_its_seed() -> None:
    candidates = strata_frame().assign(stratum=["other_referent"] * 8)
    sizes = {"other_referent": 3}
    first = audit.stratified_sample(candidates, sizes, 21, gold.DISAGREEMENT)
    again = audit.stratified_sample(candidates, sizes, 21, gold.DISAGREEMENT)
    shuffled = audit.stratified_sample(
        candidates.sample(frac=1, random_state=5).reset_index(drop=True),
        sizes,
        21,
        gold.DISAGREEMENT,
    )
    other_seed = audit.stratified_sample(candidates, sizes, 22, gold.DISAGREEMENT)
    assert first["occurrence_id"].tolist() == again["occurrence_id"].tolist()
    assert set(first["occurrence_id"]) == set(shuffled["occurrence_id"])
    assert set(first["occurrence_id"]) != set(other_seed["occurrence_id"])


def test_a_repository_with_no_published_run_pair_draws_only_the_first_two_frames() -> None:
    candidates = strata_frame().assign(stratum="")
    sample = gold.draw(candidates, 3, 5, 21)
    assert set(sample["sampling_frame"]) == {audit.PROBABILITY, audit.COVERAGE}


def test_the_three_frames_keep_one_row_and_one_probability_each() -> None:
    candidates = strata_frame().assign(
        stratum=["rejects"] * 4 + ["other_referent"] * 4
    )
    sample = gold.draw(candidates, 8, 5, 21, sizes={"rejects": None})
    assert set(sample["sampling_frame"]) == {
        audit.PROBABILITY,
        audit.COVERAGE,
        gold.DISAGREEMENT,
    }
    assert not sample["candidate_id"].duplicated().any()
    for _, rows in sample.groupby("occurrence_id"):
        assert rows["sampling_frame"].nunique() == len(rows)

# --- The refusal ----------------------------------------------------------


def test_a_population_that_is_not_the_documented_one_is_refused() -> None:
    speeches, bodies = corpus()
    problems = gold.check_population(occurrences.enumerate_term(speeches, bodies, term()))
    assert len(problems) == 2
    assert "7,747" in problems[0] and "4,133" in problems[1]
    assert all("docs/CORPUS.md §8" in problem for problem in problems)


def test_the_documented_population_passes_without_comment(monkeypatch) -> None:
    speeches, bodies = corpus()
    monkeypatch.setattr(gold, "DOCUMENTED_OCCURRENCES", len(SPEECHES))
    monkeypatch.setattr(gold, "DOCUMENTED_SPEECHES", len(SPEECHES))
    assert gold.check_population(occurrences.enumerate_term(speeches, bodies, term())) == []
