"""The genocide gold sample: cue strata, a repeatable draw, and the refusal."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest
from conftest import make_speeches
from lib import audit, frames, lexicon, model_runs, occurrences, sampling
from lib import gold_sample as gold

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
    speeches = make_speeches(
        {
            "filename": f"speech-{number}.txt",
            "text": ADDRESS + body,
            "body_start": len(ADDRESS),
            "year": year,
            "meeting_symbol": symbol,
            "date": f"{year}-04-07",
            "country_org": "Rwanda",
            "agenda_item_manual": "Rwanda",
        }
        for number, (body, year, symbol, _) in enumerate(SPEECHES)
    )
    return speeches, frames.body(speeches)


def built() -> pd.DataFrame:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    lex = lexicon.Lexicon(version=2, updated="2026-08-09", terms={"genocide": term()})
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
    assert set(sample["sampling_frame"]) == {sampling.PROBABILITY, sampling.COVERAGE}


def test_the_coverage_frame_holds_every_period_cue_stratum() -> None:
    candidates = built()
    coverage = gold.draw(candidates, 3, 5, 21).pipe(
        lambda sample: sample.loc[sample["sampling_frame"] == sampling.COVERAGE]
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
        assert sorted(rows["sampling_frame"]) == sorted([sampling.PROBABILITY, sampling.COVERAGE])
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
    sample = sampling.stratified_sample(
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
    first = sampling.stratified_sample(candidates, sizes, 21, gold.DISAGREEMENT)
    again = sampling.stratified_sample(candidates, sizes, 21, gold.DISAGREEMENT)
    shuffled = sampling.stratified_sample(
        candidates.sample(frac=1, random_state=5).reset_index(drop=True),
        sizes,
        21,
        gold.DISAGREEMENT,
    )
    other_seed = sampling.stratified_sample(candidates, sizes, 22, gold.DISAGREEMENT)
    assert first["occurrence_id"].tolist() == again["occurrence_id"].tolist()
    assert set(first["occurrence_id"]) == set(shuffled["occurrence_id"])
    assert set(first["occurrence_id"]) != set(other_seed["occurrence_id"])


def test_a_repository_with_no_published_run_pair_draws_only_the_first_two_frames() -> None:
    candidates = strata_frame().assign(stratum="")
    sample = gold.draw(candidates, 3, 5, 21)
    assert set(sample["sampling_frame"]) == {sampling.PROBABILITY, sampling.COVERAGE}


def test_the_three_frames_keep_one_row_and_one_probability_each() -> None:
    candidates = strata_frame().assign(
        stratum=["rejects"] * 4 + ["other_referent"] * 4
    )
    sample = gold.draw(candidates, 8, 5, 21, sizes={"rejects": None})
    assert set(sample["sampling_frame"]) == {
        sampling.PROBABILITY,
        sampling.COVERAGE,
        gold.DISAGREEMENT,
    }
    assert not sample["candidate_id"].duplicated().any()
    for _, rows in sample.groupby("occurrence_id"):
        assert rows["sampling_frame"].nunique() == len(rows)

# --- The refusal ----------------------------------------------------------


def test_a_population_that_is_not_the_committed_one_is_refused() -> None:
    speeches, bodies = corpus()
    problems = gold.check_population(occurrences.enumerate_term(speeches, bodies, term()))
    assert len(problems) == 2
    assert all("config/lexicon.counts.json" in problem for problem in problems)


def test_the_committed_population_passes_without_comment() -> None:
    speeches, bodies = corpus()
    found = occurrences.enumerate_term(speeches, bodies, term())
    expected = (len({item.filename for item in found}), len(found))
    assert gold.check_population(found, expected) == []


# --- One published run, a blinded packet, the prompt's examples -------------


def test_one_run_is_enough_to_stratify_on() -> None:
    """Without a comparison the rare classes are still reachable; only
    `contested` needs two instruments."""

    def single(occurrence: str) -> str:
        row = strata_frame().set_index("occurrence_id").loc[occurrence]
        row = row.rename(occurrence).to_frame().T.assign(occurrence_id=occurrence).iloc[0]
        return gold.classify_stratum(row, PUBLISHED, {}, ONSETS)

    assert single("occ-rejects") == "rejects"
    assert single("occ-preonset") == "pre_onset_referent"
    assert single("occ-hypothetical") == "conditional"
    assert single("occ-contested") == "", "one run cannot be contested"
    assert single("occ-unreached") == ""


def test_the_single_run_frame_is_named_for_what_it_is() -> None:
    candidates = strata_frame().assign(
        stratum=["rejects", "pre_onset_referent", "", "", "", "", "", ""]
    )
    sample = gold.draw(candidates, 2, 2, 21, frame=gold.MODEL_STRATA)
    third = sample.loc[sample["sampling_frame"] == gold.MODEL_STRATA]
    assert set(third["occurrence_id"]) == {"occ-rejects", "occ-preonset"}
    assert (third["strategy"] == "label strata over the published model run").all()


def test_the_packet_carries_no_reason_an_occurrence_was_drawn() -> None:
    sample = gold.draw(built(), 3, 5, 21)
    packet = gold.packet(sample, 21)
    leaks = {"sampling_frame", "stratum", "cue", "inclusion_probability", "sampling_weight",
             "strategy", "frame_size", "stratum_size", "candidate_id"}
    assert not leaks & set(packet.columns)
    assert packet["occurrence_id"].is_unique
    assert set(packet["occurrence_id"]) == set(sample["occurrence_id"])
    assert (packet["verdict"] == "").all() and (packet["coder"] == "").all()
    assert packet["position"].tolist() == list(range(1, len(packet) + 1))


def test_the_packet_order_is_seeded_and_mixes_the_frames() -> None:
    sample = gold.draw(built(), 3, 5, 21)
    assert gold.packet(sample, 21)["occurrence_id"].tolist() == gold.packet(
        sample.iloc[::-1], 21
    )["occurrence_id"].tolist()


def test_the_prior_review_flag_marks_a_drawn_sample_and_moves_nothing() -> None:
    """Set after the draw and appended last: every column the files already had
    keeps its place and its values, so the sample stays as drawn."""
    candidates = built()
    sample = gold.draw(candidates, 3, 5, 21)
    reviewed = {*sample["occurrence_id"].iloc[:2], "an-occurrence-the-sample-missed"}
    flagged = gold.flag_prior_review(sample, reviewed)
    assert list(flagged.columns) == [*sample.columns, model_runs.PRIOR_REVIEW_FLAG]
    pd.testing.assert_frame_equal(flagged[list(sample.columns)], sample)
    marked = flagged.loc[flagged[model_runs.PRIOR_REVIEW_FLAG], "occurrence_id"]
    assert set(marked) == set(sample["occurrence_id"].iloc[:2])

    design = gold.design(candidates, 3, 5, gold.MODEL_STRATA)
    weighted = gold.flag_prior_review(design, reviewed)
    pd.testing.assert_frame_equal(weighted[list(design.columns)], design)
    assert int(weighted[model_runs.PRIOR_REVIEW_FLAG].sum()) == 2


def test_the_packet_never_says_a_passage_was_read_before() -> None:
    sample = gold.draw(built(), 3, 5, 21)
    flagged = gold.flag_prior_review(sample, set(sample["occurrence_id"]))
    packet = gold.packet(flagged, 21)
    assert model_runs.PRIOR_REVIEW_FLAG not in packet.columns
    pd.testing.assert_frame_equal(packet, gold.packet(sample, 21))


def test_the_prompt_examples_are_the_committed_mapping() -> None:
    mapping = pd.read_csv(model_runs.PROMPT_EXAMPLES, dtype="string", keep_default_na=False)
    assert len(mapping) == 10 and mapping["occurrence_id"].is_unique
    assert set(mapping["example"]) == {str(number) for number in range(1, 11)}


def test_the_prior_review_list_carries_identities_and_nothing_else() -> None:
    """The 59 passages read against Qwen's labels on 10 September 2026: an
    identity per passage, never a label, and the two whose ordinal lexicon 8
    moved recorded under both line ids (docs/EVALUATION_PLAN.md §4)."""
    listed = pd.read_csv(model_runs.PRIOR_REVIEW, dtype="string", keep_default_na=False)
    assert list(listed.columns) == [
        "occurrence_id", "line_id", "reviewed_line_id", "reviewed_on", "source",
    ]
    assert len(listed) == 59
    assert listed["occurrence_id"].is_unique and listed["reviewed_line_id"].is_unique
    assert (listed["occurrence_id"].str.fullmatch(r"[0-9a-f]{64}")).all()
    assert set(listed["reviewed_on"]) == {"2026-09-10"}
    moved = listed.loc[listed["line_id"] != listed["reviewed_line_id"]]
    assert dict(zip(moved["reviewed_line_id"], moved["line_id"], strict=True)) == {
        "SC04429-01-009#5": "SC04429-01-009#6",
        "SC05697-01-040#1": "SC05697-01-040#2",
    }


def test_the_coding_page_offers_exactly_the_codebook_vocabularies() -> None:
    spec = importlib.util.spec_from_file_location(
        "coding_page", Path(__file__).resolve().parents[1] / "tools" / "coding_page.py"
    )
    page = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(page)
    page.check_vocabularies()  # exits non-zero on any difference
    template = (Path(__file__).resolve().parents[1] / "tools" / "coding_page.html").read_text(
        encoding="utf-8"
    )
    assert template.count("/*DATA*/null") == 1
    for leak in ("sampling_frame", "stratum", "cue", "inclusion_probability"):
        assert leak not in template
