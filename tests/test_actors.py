"""The per-country table, on fixtures.

This is the artefact a map would be drawn from, and every way it can be wrong is
a way that leaves it looking right. A dropped speaker still yields a complete-
looking table of correct rates. A guessed ISO3 still renders. A rate over three
speeches still sorts to the top of a legend. So the cases below are the specific
failures rather than the happy path: an untyped speaker, a blank code, a
denominator one short of the threshold, a historical state sharing a living one's
code, a year the declared periods do not cover.

Rates are worked out by hand here rather than compared with what the code
returns, for the reason `tests/test_topics.py` gives: "it agrees with itself" is
not a test. Nothing here reads a parquet — CI has no `data/`.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from lib import actors, council

# --- Fixtures --------------------------------------------------------------
#
# Two speakers with hand-chosen counts, so every rate below can be checked
# against arithmetic done on paper:
#
#   Loud   200 speeches, 10 with the term, 12 occurrences, 100,000 words
#   Quiet    5 speeches,  2 with the term,  3 occurrences,   1,000 words
#
# Loud is the country that speaks constantly and rarely says the word; Quiet is
# the one that appeared twice and said it once. On a raw count Loud leads; on a
# rate Quiet leads by a factor of eight, and it should never be drawn.


def speech(
    row: int, country: str, year: int, words: int, *, term: bool, count: int = 0
) -> dict[str, object]:
    return {
        "row_id": f"r{row}",
        "year": year,
        "country_org": country,
        "meeting_symbol": f"S/PV.{year}",
        "words": words,
        # The codebook count, never a denominator: a fifth larger, so a rate
        # that divided by it would not land on the round numbers below.
        "tokens": words * 6 // 5,
        "has_genocide": term,
        "n_genocide": count,
    }


def corpus() -> pd.DataFrame:
    rows = [
        speech(i, "Loud", 2000 + i % 4, 500, term=i < 10, count=2 if i < 2 else (1 if i < 10 else 0))
        for i in range(200)
    ]
    rows += [
        speech(1000 + i, "Quiet", 1995, 200, term=i < 2, count=2 if i == 0 else (1 if i == 1 else 0))
        for i in range(5)
    ]
    return pd.DataFrame(rows)


def mixed_corpus() -> pd.DataFrame:
    """The same, plus the two speakers a map gets wrong.

    `Secretariat` is a placeless institution; `Old Federation` is a state that no
    longer exists and carries its successor's code, as Yugoslavia and Zaire do in
    `config/entities.csv`.
    """
    extra = [
        speech(2000 + i, "Old Federation", 1995, 300, term=i == 0, count=1 if i == 0 else 0)
        for i in range(3)
    ]
    extra += [speech(3000 + i, "Secretariat", 2005, 400, term=False) for i in range(2)]
    return pd.concat([corpus(), pd.DataFrame(extra)], ignore_index=True)


def crosswalk() -> pd.DataFrame:
    """One of each kind the real file holds, including the awkward ones."""
    return pd.DataFrame(
        [
            {
                "country_org": "Loud",
                "entity_type": "state",
                "iso3": "LDA",
                "un_regional_group": "African Group",
                "lat": 1.5,
                "lon": 2.5,
            },
            {
                "country_org": "Quiet",
                "entity_type": "state",
                "iso3": "QTA",
                "un_regional_group": "Asia-Pacific Group",
                "lat": -3.25,
                "lon": 4.75,
            },
            {
                "country_org": "Secretariat",
                "entity_type": "un",
                "iso3": None,
                "un_regional_group": "",
                "lat": None,
                "lon": None,
            },
            {
                "country_org": "Old Federation",
                "entity_type": "state",
                "iso3": "LDA",  # the successor's code — see the real SRB and COD
                "un_regional_group": "Eastern European Group",
                "lat": 1.5,
                "lon": 2.5,
            },
        ]
    )


# --- Reconciliation --------------------------------------------------------


def test_the_table_adds_back_up_to_the_corpus_it_was_cut_from() -> None:
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    assert actors.reconcile(frame, corpus(), "has_genocide", "n_genocide", "test") == []
    assert int(frame["held"].sum()) == 205
    assert int(frame["speeches"].sum()) == 12
    assert int(frame["occurrences"].sum()) == 15


def test_a_dropped_speaker_is_caught_by_the_total_not_by_inspection() -> None:
    """The failure this table is most exposed to. Every remaining rate is still
    correct and the table still looks complete; the total is the only witness."""
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    short = frame.drop(index="Quiet")
    problems = actors.reconcile(short, corpus(), "has_genocide", "n_genocide", "all")
    assert problems
    assert "speeches held" in problems[0]
    assert "-5" in problems[0]


def test_a_speaker_missing_from_the_crosswalk_stops_the_table() -> None:
    """02_normalise.py refuses to run on an untyped speaker; so does this. The
    alternative is a join that drops the row and a total that is quietly short."""
    with pytest.raises(KeyError, match="absent from the crosswalk"):
        actors.describe_speakers(corpus(), crosswalk().drop(index=1))


def test_the_named_speaker_appears_in_the_refusal() -> None:
    """A failure that does not say which speaker is a failure you cannot fix."""
    with pytest.raises(KeyError, match="Quiet"):
        actors.describe_speakers(corpus(), crosswalk().drop(index=1))


def test_the_period_slices_add_up_to_the_whole() -> None:
    frame = corpus()
    slices = actors.periods(1992, 2023)
    computed = {
        window.key: actors.by_country(
            frame[window.mask(frame["year"])], "has_genocide", "n_genocide"
        )
        for window in slices
    }
    assert actors.reconcile_periods(computed, slices) == []


def test_a_period_that_loses_rows_is_reported() -> None:
    frame = corpus()
    slices = actors.periods(1992, 2023)
    computed = {
        window.key: actors.by_country(
            frame[window.mask(frame["year"])], "has_genocide", "n_genocide"
        )
        for window in slices
    }
    computed["1992-1999"] = computed["1992-1999"].drop(index="Quiet")
    problems = actors.reconcile_periods(computed, slices)
    assert any(p.startswith("held:") for p in problems)


def test_a_set_measure_reconciles_without_an_occurrence_count() -> None:
    """A union has no occurrence count — summing its members would count a
    speech saying both 'genocide' and 'war crimes' twice — so the check has to
    skip that row rather than compare a column of nulls to zero."""
    frame = corpus().assign(has_set=lambda f: f["has_genocide"])
    computed = actors.by_country(frame, "has_set", None)
    assert actors.reconcile(computed, frame, "has_set", None, "set") == []
    assert computed["occurrences"].isna().all()


# --- Denominators ----------------------------------------------------------


def test_the_rate_divides_by_the_speakers_own_speeches() -> None:
    """Worked by hand: Loud says the word in 10 of its own 200 speeches, Quiet in
    2 of its own 5. Dividing either by the corpus total would give 4.9% and 1.0%
    and reverse the ranking."""
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    assert frame.loc["Loud", "speech_rate"] == pytest.approx(10 / 200)
    assert frame.loc["Quiet", "speech_rate"] == pytest.approx(2 / 5)


def test_the_token_rate_divides_by_the_speakers_own_words() -> None:
    """Loud: 12 occurrences in 200 x 500 = 100,000 words = 12 per 100,000.

    Not by its codebook tokens, which the fixture makes a fifth larger: that
    is the §3.3 error, and dividing by them would read 10 per 100,000."""
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    assert frame.loc["Loud", "words"] == 100_000
    assert frame.loc["Loud", "token_rate"] == pytest.approx(12.0)
    # Quiet: 3 occurrences in 5 x 200 = 1,000 words = 300 per 100,000.
    assert frame.loc["Quiet", "token_rate"] == pytest.approx(300.0)


def test_the_loud_country_leads_on_counts_and_trails_on_rates() -> None:
    """The whole argument for publishing both. A map coloured by count and a map
    coloured by rate are different maps, and neither is the other's summary."""
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    assert frame["speeches"].idxmax() == "Loud"
    assert frame["speech_rate"].idxmax() == "Quiet"


def test_the_counts_survive_so_a_reader_can_see_the_denominator() -> None:
    """A rate with no denominator beside it is a claim with no evidence beside
    it. `held` is what lets a reader discount the top of the table."""
    frame = actors.withhold_below(
        actors.by_country(corpus(), "has_genocide", "n_genocide"), minimum=100
    )
    quiet = frame.loc["Quiet"]
    assert quiet["held"] == 5
    assert quiet["speeches"] == 2
    assert quiet["occurrences"] == 3
    assert pd.isna(quiet["speech_rate"])


def test_a_speaker_absent_from_a_period_gets_no_row_rather_than_a_zero() -> None:
    """A zero denominator is not a zero rate, and a row carrying one invites a
    division nobody wrote."""
    frame = corpus()
    nineties = frame[frame["year"].between(1992, 1999)]
    computed = actors.by_country(nineties, "has_genocide", "n_genocide")
    assert computed.index.tolist() == ["Quiet"]


# --- The minimum sample ----------------------------------------------------


def test_one_speech_below_the_threshold_is_withheld() -> None:
    """Off-by-one here is what puts a two-speech country on a map."""
    frame = pd.DataFrame(
        {"held": [99], "words": [1], "speeches": [1], "speech_rate": [0.5], "token_rate": [1.0]},
        index=["Borderline"],
    )
    out = actors.withhold_below(frame, minimum=100)
    assert not bool(out.loc["Borderline", "sufficient"])
    assert pd.isna(out.loc["Borderline", "speech_rate"])


def test_exactly_at_the_threshold_is_published() -> None:
    frame = pd.DataFrame(
        {"held": [100], "words": [1], "speeches": [1], "speech_rate": [0.5], "token_rate": [1.0]},
        index=["Borderline"],
    )
    out = actors.withhold_below(frame, minimum=100)
    assert bool(out.loc["Borderline", "sufficient"])
    assert out.loc["Borderline", "speech_rate"] == pytest.approx(0.5)


def test_withholding_blanks_the_rate_and_keeps_the_count() -> None:
    """The distinction the artefact rests on: a count is a fact, a rate is an
    estimate, and only the estimate needs a sample."""
    frame = actors.withhold_below(
        actors.by_country(corpus(), "has_genocide", "n_genocide"), minimum=100
    )
    assert frame.loc["Quiet", "held"] == 5
    assert pd.isna(frame.loc["Quiet", "speech_rate"])
    assert pd.isna(frame.loc["Quiet", "token_rate"])
    assert bool(frame.loc["Loud", "sufficient"])


def test_the_threshold_is_where_a_zero_starts_to_mean_something() -> None:
    """MIN_SPEECHES is not a preference. At the corpus's own prevalence of about
    3.1%, seeing no term-bearing speech in fewer than ~96 tries is consistent
    with the Council average, so a blank country below that says nothing."""
    assert actors.informative_zero_minimum(0.0308) == 96
    assert actors.informative_zero_minimum(0.0308) <= actors.MIN_SPEECHES


def test_the_zero_ceiling_is_near_the_three_over_n_rule_of_thumb() -> None:
    for n in (50, 100, 500):
        assert actors.zero_ceiling(n) == pytest.approx(3 / n, rel=0.05)


def test_the_zero_ceiling_and_its_inverse_agree() -> None:
    """The threshold is derived, so the derivation is checked in both directions."""
    for rate in (0.01, 0.0308, 0.10):
        n = actors.informative_zero_minimum(rate)
        assert actors.zero_ceiling(n) <= rate
        assert actors.zero_ceiling(n - 1) > rate


def test_a_rarer_term_demands_a_larger_sample() -> None:
    assert actors.informative_zero_minimum(0.001) > actors.informative_zero_minimum(0.03)


def test_an_impossible_prevalence_is_refused() -> None:
    with pytest.raises(ValueError, match="strictly between"):
        actors.informative_zero_minimum(0.0)


def test_zero_ceiling_of_nothing_claims_nothing() -> None:
    assert actors.zero_ceiling(0) == 1.0


# --- Codes, centroids and what may be drawn --------------------------------


def described() -> dict[str, dict[str, object]]:
    return {s["country_org"]: s for s in actors.describe_speakers(mixed_corpus(), crosswalk())}


def test_a_non_state_gets_no_code_no_group_and_no_point_on_the_globe() -> None:
    """There is nowhere the UN Secretariat is. An empty string here would be
    falsy enough to pass a check and truthy enough to survive a join."""
    secretariat = described()["Secretariat"]
    assert secretariat["iso3"] is None
    assert secretariat["un_regional_group"] is None
    assert secretariat["centroid"] is None
    assert secretariat["mappable"] is False


def test_a_blank_code_is_read_as_missing_not_as_a_value() -> None:
    """`""` and `"  "` are how a hand-edited CSV expresses "no code". Neither may
    reach the artefact as a string, or every uncoded speaker joins to the same
    polygon."""
    assert actors._text("") is None
    assert actors._text("   ") is None
    assert actors._text(None) is None
    assert actors._text(float("nan")) is None
    assert actors._text("SRB") == "SRB"


def test_a_state_keeps_its_code_and_its_centroid() -> None:
    loud = described()["Loud"]
    assert loud["iso3"] == "LDA"
    assert loud["centroid"] == [1.5, 2.5]
    assert loud["mappable"] is True


def test_a_coded_state_with_no_centroid_is_not_mappable() -> None:
    """Not "has coordinates" but "is a state, has a code, has a centroid". A
    consumer that filters on the coordinate alone would have to guess what a
    null means."""
    table = crosswalk()
    table.loc[table["country_org"] == "Loud", ["lat", "lon"]] = None
    placeless = {s["country_org"]: s for s in actors.describe_speakers(mixed_corpus(), table)}
    assert placeless["Loud"]["centroid"] is None
    assert placeless["Loud"]["mappable"] is False


def test_a_speaker_never_borrows_another_speakers_centroid() -> None:
    """The failure mode a forward-fill or a merge on a partial key produces: a
    placeless speaker inheriting the row above it."""
    placed = {name: row["centroid"] for name, row in described().items()}
    assert placed["Secretariat"] is None
    assert placed["Loud"] == [1.5, 2.5]
    assert placed["Quiet"] == [-3.25, 4.75]


def test_the_speaker_block_records_the_span_a_speaker_was_heard_over() -> None:
    """A historical state's last year is the fact that explains its ISO3 sharing
    a living state's, and a reader should not have to scan the rows to find it."""
    old = described()["Old Federation"]
    assert (old["first_year"], old["last_year"]) == (1995, 1995)
    assert old["speeches"] == 3


# --- Historical states -----------------------------------------------------


def test_a_historical_state_stays_its_own_row() -> None:
    """Yugoslavia, Serbia and Montenegro and Serbia all answer to SRB, and Zaire
    to COD. Merging them would build a denominator no state ever had; they are
    kept apart, and this pins that decision so it cannot be reversed silently."""
    frame = actors.by_country(mixed_corpus(), "has_genocide", "n_genocide")
    assert "Old Federation" in frame.index
    assert "Loud" in frame.index
    assert frame.loc["Old Federation", "held"] == 3
    assert frame.loc["Loud", "held"] == 200


def test_a_shared_code_is_reported_rather_than_resolved() -> None:
    """The artefact publishes the ambiguity instead of picking a winner. A
    consumer joining on ISO3 has to decide; leaving the decision implicit means
    whichever row was drawn last wins, and nothing says so."""
    collisions = actors.iso3_collisions(list(described().values()))
    assert collisions == {"LDA": ["Loud", "Old Federation"]}


def test_a_historical_state_is_not_merged_into_its_successors_denominator() -> None:
    """The successor keeps its own denominator. If the two were folded together,
    Loud's 200 speeches would become 203 and its rate would move."""
    frame = actors.by_country(mixed_corpus(), "has_genocide", "n_genocide")
    assert frame.loc["Loud", "held"] == 200
    assert frame.loc["Loud", "speech_rate"] == pytest.approx(10 / 200)


def test_a_code_carried_by_one_speaker_is_not_a_collision() -> None:
    collisions = actors.iso3_collisions(actors.describe_speakers(corpus(), crosswalk()))
    assert collisions == {}


def test_speakers_with_no_code_are_never_collided_with_each_other() -> None:
    """Two uncoded speakers share the absence of a code, not a code."""
    speakers = [
        {"country_org": "Secretariat", "iso3": None},
        {"country_org": "Civil Society", "iso3": None},
        {"country_org": "Blank", "iso3": ""},
    ]
    assert actors.iso3_collisions(speakers) == {}


# --- Periods ---------------------------------------------------------------


def test_periods_do_not_overlap_or_leave_gaps() -> None:
    for (_, end), (start, _) in zip(actors.DECADES, actors.DECADES[1:], strict=False):
        assert start == end + 1


def test_the_first_and_last_year_of_the_corpus_land_where_expected() -> None:
    years = pd.Series([1992, 2023])
    labelled = [
        window.key
        for year in years
        for window in actors.periods(1992, 2023)
        if window.key != actors.WHOLE and window.mask(pd.Series([year])).iloc[0]
    ]
    assert labelled == ["1992-1999", "2020-2023"]


def test_a_year_outside_the_declared_periods_is_named_not_dropped() -> None:
    """`topics.assign_period` labels such a year `outside` because a topic model
    can still report that bucket. Here there is no bucket to report it in: the
    year would count in the whole-corpus row and in none of the period rows, and
    the two would stop adding up. So it stops the run, and the message names the
    year rather than the count."""
    problems = actors.check_coverage(pd.Series([1992, 2024]))
    assert len(problems) == 1
    assert "2024" in problems[0]


def test_a_year_in_two_periods_is_refused_as_well() -> None:
    """Double-counting is the same failure with the opposite sign, and an
    overlapping edit to DECADES is easier to make than a gap."""
    overlapping = ((1992, 2000), (2000, 2009))
    problems = actors.check_coverage(pd.Series([2000]), overlapping)
    assert problems and "2 periods" in problems[0]


def test_a_covered_corpus_reports_nothing() -> None:
    assert actors.check_coverage(pd.Series([1992, 2005, 2019, 2023])) == []


def test_the_whole_corpus_slice_comes_first_and_spans_everything() -> None:
    slices = actors.periods(1992, 2023)
    assert slices[0].key == actors.WHOLE
    assert (slices[0].first_year, slices[0].last_year) == (1992, 2023)
    assert len(slices) == 1 + len(actors.DECADES)


# --- Crosswalk drift -------------------------------------------------------


def with_attributes(frame: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    return frame.merge(table, on="country_org", how="left")


def test_an_unedited_crosswalk_reports_no_drift() -> None:
    frame = with_attributes(corpus(), crosswalk())
    assert actors.crosswalk_drift(frame, crosswalk()) == []


def test_a_crosswalk_edited_since_02_ran_is_caught() -> None:
    """02 freezes entity_type and the centroid into the corpus. If config/ moved
    afterwards, this table would be built from the new file while the rest of
    the payload still carries the old one, and neither would say so."""
    frame = with_attributes(corpus(), crosswalk())
    moved = crosswalk()
    moved.loc[moved["country_org"] == "Loud", "iso3"] = "XXX"
    problems = actors.crosswalk_drift(frame, moved)
    assert problems and "Loud" in problems[0] and "iso3" in problems[0]


def test_a_moved_centroid_is_caught_and_a_rounding_wobble_is_not() -> None:
    frame = with_attributes(corpus(), crosswalk())
    nudged = crosswalk()
    nudged.loc[nudged["country_org"] == "Quiet", "lat"] = -3.25 + 1e-9
    assert actors.crosswalk_drift(frame, nudged) == []
    nudged.loc[nudged["country_org"] == "Quiet", "lat"] = -3.5
    assert actors.crosswalk_drift(frame, nudged)


def test_two_missing_values_are_treated_as_agreeing() -> None:
    """The Secretariat has no code in either file, and that is agreement rather
    than a difference between two nulls."""
    frame = with_attributes(corpus(), crosswalk())
    assert actors.crosswalk_drift(frame, crosswalk()) == []


# --- Who held a seat when they spoke ---------------------------------------
#
# `Loud` speaks 200 times: 120 while holding an elected seat and 80 from
# outside one. `Quiet` speaks 5 times, all of them as a non-member. The
# Secretariat speaks twice and can never hold a seat at all. The point of the
# split is that no single membership label is true of `Loud`, which is the case
# `lib.council` opens by naming and the one a shaded map would erase.


def seated_corpus() -> pd.DataFrame:
    frame = mixed_corpus()
    groups = {
        "Loud": [council.ELECTED] * 120 + [council.NON_MEMBER] * 80,
        "Quiet": [council.NON_MEMBER] * 5,
        "Old Federation": [council.NON_MEMBER] * 3,
        "Secretariat": [council.UN_GROUP] * 2,
    }
    seen: dict[str, int] = {}
    assigned = []
    for name in frame["country_org"]:
        index = seen.get(name, 0)
        seen[name] = index + 1
        assigned.append(groups[name][index])
    return frame.assign(speaker_group=assigned)


def test_the_composition_sums_to_the_speakers_own_denominator() -> None:
    frame = actors.standing(seated_corpus())
    assert int(frame.loc["Loud", "held"]) == 200
    assert int(frame.loc["Loud", council.ELECTED]) == 120
    assert int(frame.loc["Loud", council.NON_MEMBER]) == 80
    assert int(frame.loc["Loud", council.PERMANENT]) == 0
    assert frame.loc["Loud", list(actors.SEATED)].sum() == 120


def test_seated_counts_only_the_two_charter_memberships() -> None:
    """The UN Secretariat is among the corpus's largest speakers and has never
    sat on the Council; an invited NGO has not either. Neither is a non-member
    state, which is why all five counts are published and not just the sum."""
    frame = actors.standing(seated_corpus())
    assert int(frame.loc["Secretariat", "seated"]) == 0
    assert int(frame.loc["Secretariat", council.UN_GROUP]) == 2
    assert int(frame.loc["Secretariat", council.NON_MEMBER]) == 0
    assert actors.SEATED == (council.PERMANENT, council.ELECTED)


def test_a_share_of_a_known_set_is_written_where_a_rate_would_be_withheld() -> None:
    """`Quiet` has five speeches: far below the minimum, so its term rate is
    withheld. Its seated share is not, and the distinction is the point. "None
    of the five speeches it gave was from a seat" is exactly true at n=5; "40%
    of its speeches used the word" is an estimate that n=5 cannot carry."""
    frame = actors.standing(seated_corpus())
    assert frame.loc["Quiet", "seated_share"] == 0.0
    assert frame.loc["Loud", "seated_share"] == pytest.approx(120 / 200)

    measured = actors.withhold_below(
        actors.by_country(seated_corpus(), "has_genocide", "n_genocide")
    )
    assert not measured.loc["Quiet", "sufficient"]
    assert pd.isna(measured.loc["Quiet", "speech_rate"])


def test_an_undeclared_speaker_group_stops_the_run() -> None:
    """Reindexing it away would leave five counts that no longer sum to the
    denominator printed beside them, and every check downstream compares
    totals."""
    frame = seated_corpus()
    frame.loc[frame.index[0], "speaker_group"] = "Observer"
    with pytest.raises(ValueError, match="Observer"):
        actors.standing(frame)


def test_a_speech_with_no_group_stops_the_run() -> None:
    frame = seated_corpus()
    frame.loc[frame.index[0], "speaker_group"] = None
    with pytest.raises(ValueError, match="speaker_group"):
        actors.standing(frame)


def test_a_frame_without_the_group_column_is_refused() -> None:
    with pytest.raises(KeyError, match="speaker_group"):
        actors.standing(mixed_corpus())


def test_a_dropped_speaker_is_caught_by_the_composition_total() -> None:
    speeches = seated_corpus()
    frame = actors.standing(speeches)
    assert actors.reconcile_standing(frame, speeches, "test") == []
    problems = actors.reconcile_standing(frame.drop(index="Quiet"), speeches, "test")
    assert problems and "speeches held" in problems[0]


def test_a_group_lost_between_the_counts_and_the_total_is_caught() -> None:
    """The other way this goes wrong: nothing is missing from the table, but a
    speaker's five counts stop adding up to the denominator beside them."""
    speeches = seated_corpus()
    frame = actors.standing(speeches)
    frame.loc["Loud", council.NON_MEMBER] = 0
    problems = actors.reconcile_standing(frame, speeches, "test")
    assert any("do not sum to its denominator" in problem for problem in problems)


def test_every_group_is_written_including_the_zeros() -> None:
    """An absent key would mean zero here while it means "withheld, never
    computed" one block away in `measures`, and nothing in the JSON would say
    which."""
    rows = {
        row["country_org"]: row
        for row in actors.standing_as_rows(actors.standing(seated_corpus()), "all")
    }
    assert set(rows["Quiet"]["groups"]) == set(council.SPEAKER_GROUPS)
    assert rows["Quiet"]["groups"][council.PERMANENT] == 0
    assert rows["Quiet"]["seated"] == 0
    assert rows["Loud"]["period"] == "all"
    assert json.loads(json.dumps(rows["Loud"]))["groups"][council.ELECTED] == 120


# --- Membership drift ------------------------------------------------------


def roster() -> pd.DataFrame:
    """Two seat-years, in the shape `membership_by_year` returns."""
    return pd.DataFrame(
        [
            {"year": 1995, "country_org": "Quiet", "seat": "elected"},
            {"year": 2000, "country_org": "Loud", "seat": "permanent"},
        ]
    )


def typed(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.assign(
        entity_type=frame["country_org"].map(
            {"Loud": "state", "Quiet": "state", "Old Federation": "state", "Secretariat": "un"}
        )
    )


def test_a_roster_matching_the_frozen_column_reports_no_drift() -> None:
    speeches = typed(mixed_corpus())
    speeches = speeches.assign(speaker_group=council.speaker_group(speeches, roster()))
    assert council.drift(speeches, roster()) == []


def test_a_roster_edited_since_02_ran_is_caught() -> None:
    """02 freezes the group into the parquet and every later step reads that
    column, which is the right dependency and also the one that hides an edit:
    a corrected term would change nothing anybody could see."""
    speeches = typed(mixed_corpus())
    speeches = speeches.assign(speaker_group=council.speaker_group(speeches, roster()))
    # A term added in a year Loud actually speaks. Added in a year it does not
    # would change nothing, and the check would be right to stay silent.
    corrected = pd.concat(
        [roster(), pd.DataFrame([{"year": 2001, "country_org": "Loud", "seat": "elected"}])],
        ignore_index=True,
    )
    problems = council.drift(speeches, corrected)
    assert problems and "Loud" in problems[0]
    assert council.NON_MEMBER in problems[0] and council.ELECTED in problems[0]


def test_a_corpus_without_the_frozen_column_has_nothing_to_drift_from() -> None:
    assert council.drift(typed(mixed_corpus()), roster()) == []


# --- Serialisation ---------------------------------------------------------


def rows_for(minimum: int) -> list[dict[str, object]]:
    frame = actors.withhold_below(
        actors.by_country(corpus(), "has_genocide", "n_genocide"), minimum
    )
    return actors.as_rows(frame, "all")


def test_a_withheld_rate_serialises_as_null_and_never_as_nan() -> None:
    """json.dumps writes bare NaN, which is not JSON and which every strict
    parser at the fetch boundary rejects."""
    payload = json.dumps(rows_for(100))
    assert "NaN" not in payload
    restored = json.loads(payload)
    assert any(row["speech_rate"] is None for row in restored)
    assert all(row["held"] is not None for row in restored)


def test_every_row_carries_its_denominator_and_its_verdict() -> None:
    for row in rows_for(100):
        assert row["held"] is not None
        assert isinstance(row["sufficient"], bool)
        assert row["sufficient"] == (row["held"] >= 100)


def test_a_set_measure_emits_no_occurrence_fields_at_all() -> None:
    """Absent rather than null: a set has no occurrence count to withhold, and a
    null would read as one that was suppressed."""
    frame = corpus().assign(has_set=lambda f: f["has_genocide"])
    rows = actors.as_rows(actors.withhold_below(actors.by_country(frame, "has_set", None)), "all")
    assert rows
    for row in rows:
        assert "occurrences" not in row
        assert "token_rate" not in row


def test_rates_are_rounded_to_the_precision_the_series_artefacts_use() -> None:
    """Six places on a share, four on a per-100k rate — the same as 04, so the
    two artefacts do not quote the same figure differently."""
    rows = {row["country_org"]: row for row in rows_for(1)}
    assert rows["Loud"]["speech_rate"] == round(10 / 200, 6)
    assert rows["Loud"]["token_rate"] == round(12.0, 4)


def test_the_row_names_the_period_it_belongs_to() -> None:
    frame = actors.by_country(corpus(), "has_genocide", "n_genocide")
    rows = actors.as_rows(actors.withhold_below(frame), "2000-2009")
    assert {row["period"] for row in rows} == {"2000-2009"}


def test_a_frame_without_the_required_columns_is_refused() -> None:
    with pytest.raises(KeyError, match="by_country needs"):
        actors.by_country(corpus().drop(columns=["words"]), "has_genocide", "n_genocide")


def test_the_declared_minimum_is_a_plain_integer() -> None:
    """It is quoted in the artefact's metadata, in the note and in the comparison
    `held >= minimum`. A bool is an int in Python, and `True` would compare as 1
    and admit every speaker in the corpus."""
    assert isinstance(actors.MIN_SPEECHES, int)
    assert not isinstance(actors.MIN_SPEECHES, bool)
