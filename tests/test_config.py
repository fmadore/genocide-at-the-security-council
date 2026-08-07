"""Integrity of the hand-checked files in config/.

These run against the real config, not fixtures, and need no data. They are the
cheap guard on the three artefacts a human edits by hand: a bad alias, an
unknown entity type or a mistyped Council term shows up here rather than
halfway through a pipeline run.
"""

from __future__ import annotations

import pytest
from lib import council, entities, lexicon, series
from lib.paths import COUNCIL_MEMBERSHIP, COUNTRY_ALIASES, ENTITIES, EVENTS, LEXICON

CORPUS_FIRST_YEAR = 1992
CORPUS_LAST_YEAR = 2023


class TestFilesExist:
    @pytest.mark.parametrize(
        "path", [LEXICON, ENTITIES, COUNTRY_ALIASES, COUNCIL_MEMBERSHIP, EVENTS]
    )
    def test_present(self, path):
        assert path.exists(), f"{path} is missing"


@pytest.fixture(scope="module")
def crosswalk():
    return entities.load_entities()


@pytest.fixture(scope="module")
def aliases():
    return entities.load_aliases()


@pytest.fixture(scope="module")
def membership():
    return council.membership_by_year()


@pytest.fixture(scope="module")
def lex():
    return lexicon.load()


@pytest.fixture(scope="module")
def events():
    return series.load_events()


class TestEntities:
    def test_is_internally_consistent(self, crosswalk):
        assert entities.validate(crosswalk) == []

    def test_every_row_has_a_known_type(self, crosswalk):
        assert set(crosswalk["entity_type"]) <= entities.ENTITY_TYPES

    def test_states_are_mappable(self, crosswalk):
        states = crosswalk[crosswalk["entity_type"] == "state"]
        assert states["iso3"].notna().all()
        assert states["lat"].between(-90, 90).all()
        assert states["lon"].between(-180, 180).all()

    def test_non_states_carry_no_centroid(self, crosswalk):
        """A fake centroid would put a point on the map that asserts something
        untrue about where an NGO is."""
        non_states = crosswalk[crosswalk["entity_type"] != "state"]
        assert non_states["lat"].isna().all()
        assert non_states["lon"].isna().all()

    def test_p5_are_present_and_typed_as_states(self, crosswalk):
        p5 = {
            "China",
            "France",
            "Russian Federation",
            "United Kingdom Of Great Britain And Northern Ireland",
            "United States Of America",
        }
        rows = crosswalk[crosswalk["country_org"].isin(p5)]
        assert len(rows) == 5
        assert set(rows["entity_type"]) == {"state"}


class TestAliases:
    def test_no_alias_maps_to_itself(self, aliases):
        assert [a for a, c in aliases.items() if a == c] == []

    def test_no_alias_chains(self, aliases):
        """A canonical form must not itself be an alias, or the result would
        depend on the order the map is applied in."""
        assert [c for c in aliases.values() if c in aliases] == []

    def test_every_canonical_form_is_in_the_crosswalk(self, aliases):
        known = set(entities.load_entities()["country_org"])
        assert sorted(set(aliases.values()) - known) == []


class TestCouncilMembership:
    def test_seats_add_up_across_the_corpus_period(self, membership):
        """Five permanent and ten elected, every year — fixed by the Charter,
        so a year that does not add up is a typo in the config."""
        assert council.validate(membership, CORPUS_FIRST_YEAR, CORPUS_LAST_YEAR) == []

    def test_members_are_named_as_the_corpus_names_them(self, membership):
        known = set(entities.load_entities()["country_org"])
        unknown = sorted(set(membership["country_org"]) - known)
        assert unknown == [], f"not in config/entities.csv: {unknown}"

    def test_seat_values_are_closed(self, membership):
        assert set(membership["seat"]) == {"permanent", "elected"}


class TestEvents:
    """The chart overlay. Its dates are unverified (docs/VALIDATION.md §5), so
    these tests check only what can be checked mechanically — that every row is
    well-formed and lands somewhere the corpus can show it."""

    def test_it_loads(self, events):
        assert len(events) > 0

    def test_every_event_falls_inside_the_corpus_period(self, events):
        """An annotation outside 1992-2023 would be drawn off the end of every
        axis in the dashboard, or silently dropped."""
        assert events["year"].between(CORPUS_FIRST_YEAR, CORPUS_LAST_YEAR).all()

    def test_kinds_are_closed(self, events):
        """`kind` drives the legend and the colour, so a typo becomes a
        seventh category nobody has styled."""
        assert set(events["kind"]) <= series.EVENT_KINDS

    def test_no_two_events_share_a_date_and_label(self, events):
        assert not events.duplicated(subset=["date", "label"]).any()

    def test_every_event_is_labelled(self, events):
        assert (events["label"].str.len() > 0).all()

    def test_dates_are_sorted_on_load(self, events):
        """Downstream code renders them in order without re-sorting."""
        assert events["date"].is_monotonic_increasing


class TestLexicon:
    def test_every_pattern_compiles(self, lex):
        assert len(lex.terms) > 0

    def test_tiers_and_registers_are_populated(self, lex):
        for term in lex.terms.values():
            assert term.tier
            assert term.register

    def test_sets_reference_defined_terms(self, lex):
        for name, members in lex.sets.items():
            missing = [m for m in members if m not in lex.terms]
            assert missing == [], f"set '{name}' references {missing}"

    def test_the_core_term_matches_its_own_word(self, lex):
        regex = lex.terms["genocide"].regex
        for word in ("genocide", "Genocide", "genocidal", "genocides", "genocidaires"):
            assert regex.search(word), word

    def test_ocr_variants_are_held_back_by_default(self, lex):
        """Folding OCR noise into the headline count silently would overstate
        how much of it there is."""
        assert "genocide_ocr_variants" in lex.terms
        assert not lex.terms["genocide_ocr_variants"].enabled
        assert "genocide_ocr_variants" not in {t.name for t in lex.active}
