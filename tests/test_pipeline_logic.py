"""Speaker-group derivation and lexicon counting, on small fixtures.

The pipeline's two pieces of real reasoning: deciding what a speaker *was* at
the moment it spoke, and counting terms without letting the form of address
inflate the total.
"""

from __future__ import annotations

import pandas as pd
import pytest
from lib import council, entities, frames, lexicon


@pytest.fixture(scope="module")
def lex():
    return lexicon.load()


@pytest.fixture
def membership():
    return pd.DataFrame(
        [
            {"year": 1994, "country_org": "France", "seat": "permanent"},
            {"year": 1994, "country_org": "Rwanda", "seat": "elected"},
            {"year": 1995, "country_org": "France", "seat": "permanent"},
            {"year": 1995, "country_org": "Rwanda", "seat": "elected"},
            {"year": 2000, "country_org": "France", "seat": "permanent"},
        ]
    )


class TestSpeakerGroup:
    def test_membership_is_read_per_year_not_per_country(self, membership):
        """Rwanda sat on the Council in 1994-1995 and nowhere else in the
        corpus. Collapsing that to one label per country would erase the
        distinction the analysis turns on."""
        speeches = pd.DataFrame(
            {
                "year": [1994, 2000],
                "country_org": ["Rwanda", "Rwanda"],
                "entity_type": ["state", "state"],
            }
        )
        groups = council.speaker_group(speeches, membership)
        assert list(groups) == [council.ELECTED, council.NON_MEMBER]

    def test_permanent_members_are_p5(self, membership):
        speeches = pd.DataFrame(
            {"year": [1994], "country_org": ["France"], "entity_type": ["state"]}
        )
        assert council.speaker_group(speeches, membership).iloc[0] == council.PERMANENT

    def test_the_un_is_its_own_group_not_a_non_member_state(self, membership):
        """country_org='UN' is the corpus's sixth-largest speaker. Filing it
        under 'non-member state' would both mislabel it and distort that group."""
        speeches = pd.DataFrame(
            {"year": [1994], "country_org": ["UN"], "entity_type": ["un"]}
        )
        assert council.speaker_group(speeches, membership).iloc[0] == council.UN_GROUP

    @pytest.mark.parametrize(
        "entity_type", ["ngo", "civil_society", "igo", "academia", "company", "other"]
    )
    def test_everything_non_state_is_non_state(self, membership, entity_type):
        speeches = pd.DataFrame(
            {"year": [2000], "country_org": ["Oxfam"], "entity_type": [entity_type]}
        )
        assert council.speaker_group(speeches, membership).iloc[0] == council.NON_STATE

    def test_every_result_is_a_declared_group(self, membership):
        speeches = pd.DataFrame(
            {
                "year": [1994, 2000, 1995, 2000],
                "country_org": ["France", "Rwanda", "Rwanda", "UN"],
                "entity_type": ["state", "state", "state", "un"],
            }
        )
        assert set(council.speaker_group(speeches, membership)) <= set(
            council.SPEAKER_GROUPS
        )


class TestCouncilValidation:
    def test_flags_a_year_with_the_wrong_number_of_seats(self, membership):
        problems = council.validate(membership, 1994, 1994)
        assert any("elected" in p for p in problems)

    def test_flags_a_member_that_never_speaks_in_its_term(self, membership):
        """Nearly always a mistyped year rather than a silent delegation."""
        spoke = pd.DataFrame({"year": [1994], "country_org": ["France"]})
        problems = council.validate_against_corpus(membership, spoke)
        assert problems and "Rwanda" in problems[0]


class TestCanonicalise:
    def test_applies_aliases_and_passes_others_through(self):
        names = pd.Series(["Türkiye", "Turkey", "Rwanda"])
        result = entities.canonicalise(names, {"Türkiye": "Turkey"})
        assert list(result) == ["Turkey", "Turkey", "Rwanda"]

    def test_coverage_check_names_the_missing_speakers(self):
        crosswalk = pd.DataFrame({"country_org": ["Rwanda"]})
        problems = entities.validate_coverage(pd.Series(["Rwanda", "Atlantis"]), crosswalk)
        assert problems and "Atlantis" in problems[0]

    def test_coverage_check_passes_when_everything_is_known(self):
        crosswalk = pd.DataFrame({"country_org": ["Rwanda", "France"]})
        assert entities.validate_coverage(pd.Series(["Rwanda"]), crosswalk) == []


class TestBody:
    def test_reconstructs_the_speech_without_its_form_of_address(self):
        frame = pd.DataFrame(
            {
                "text": ["Mr. Valle (Brazil): I thank you.", "No address here."],
                "body_start": [20, 0],
            }
        )
        assert list(frames.body(frame)) == ["I thank you.", "No address here."]

    def test_refuses_a_frame_that_has_not_been_normalised(self):
        with pytest.raises(KeyError, match="speeches_norm"):
            frames.body(pd.DataFrame({"text": ["x"]}))


class TestLexiconCounting:
    def test_counts_occurrences_not_just_presence(self, lex):
        bodies = pd.Series(["genocide, genocide and genocidal acts", "nothing here"])
        counts = lexicon.apply(bodies, lex)
        assert list(counts["n_genocide"]) == [3, 0]
        assert list(counts["has_genocide"]) == [True, False]

    def test_multiword_terms_survive_a_line_break(self, lex):
        """The records are hard-wrapped, so 'crimes against humanity' is
        routinely split across lines."""
        bodies = pd.Series(["… crimes against\nhumanity were committed …"])
        assert lexicon.apply(bodies, lex)["n_crimes_against_humanity"].iloc[0] == 1

    def test_register_rollups_sum_their_terms(self, lex):
        bodies = pd.Series(["genocide and war crimes and crimes against humanity"])
        counts = lexicon.apply(bodies, lex)
        legal = [t for t in lex.active if t.register == "legal"]
        expected = sum(counts[f"n_{t.name}"].iloc[0] for t in legal)
        assert counts["n_register_legal"].iloc[0] == expected

    def test_disabled_terms_stay_out_of_the_counts(self, lex):
        counts = lexicon.apply(pd.Series(["genecide"]), lex)
        assert "n_genocide_ocr_variants" not in counts.columns

    def test_ocr_delta_reports_what_the_tolerant_pattern_would_add(self, lex):
        bodies = pd.Series(["genecide in Bosnia", "genocide in Rwanda", "nothing"])
        report = {entry["term"]: entry for entry in lexicon.ocr_delta(bodies, lex)}
        variants = report["genocide_ocr_variants"]
        assert variants["speeches"] == 2
        assert variants["extra"] == 1  # only the misspelled one is new
