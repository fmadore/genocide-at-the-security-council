"""Integrity of the hand-checked files in config/.

These run against the real config, not fixtures, and need no data. They are the
cheap guard on the three artefacts a human edits by hand: a bad alias, an
unknown entity type or a mistyped Council term shows up here rather than
halfway through a pipeline run.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import pytest
from lib import council, entities, lexicon, series
from lib.paths import (
    COUNCIL_MEMBERSHIP,
    COUNTRY_ALIASES,
    ENTITIES,
    EVENTS,
    LEXICON,
    LEXICON_LOCK,
)

CORPUS_FIRST_YEAR = 1992
CORPUS_LAST_YEAR = 2023

#: What a verbatim record does to a phrase that will not fit on one line. The
#: patterns join words with `\s+`, which spans every one of these; a prefilter
#: is a plain substring test, which spans none of them.
WHITESPACE_RUNS = ("\n", "  ", " \t ", "\n  ")


def as_the_record_might_hold_it(example: str) -> list[str]:
    """The example wrapped, indented and shouted, as well as verbatim."""
    return [
        example,
        example.upper(),
        *(example.replace(" ", run) for run in WHITESPACE_RUNS),
    ]


def in_a_sentence_that_qualifies(example: str) -> str:
    """The example put where an anchored term is allowed to count it.

    An anchored term counts nothing outside a sentence that also says
    `genocid*`, so its examples have to be carried into one before any property
    about *how many* it counts can be tested. One sentence, with the node word
    after the example rather than before it, so the anchor is not doing the
    work a leading word would do for a pattern that happens to start with a
    boundary.
    """
    return f"They spoke of {example} in the genocide."


class TestFilesExist:
    @pytest.mark.parametrize(
        "path", [LEXICON, LEXICON_LOCK, ENTITIES, COUNTRY_ALIASES, COUNCIL_MEMBERSHIP, EVENTS]
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
    """The committed lexicon, checked against its lock.

    `load()` checks the lock unless told not to, so every test taking this
    fixture is also standing on a lock that describes the file.
    """
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
    """The primary-sourced chart overlay."""

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

    def test_every_event_has_a_primary_source(self, events):
        assert (events["source"].str.len() > 0).all()
        assert events["source_url"].str.startswith("https://").all()

    def test_dates_are_sorted_on_load(self, events):
        """Downstream code renders them in order without re-sorting."""
        assert events["date"].is_monotonic_increasing


class TestLexicon:
    def test_every_pattern_compiles(self, lex):
        assert len(lex.terms) > 0

    def test_every_pattern_matches_its_declared_examples(self, lex):
        for term in lex.terms.values():
            assert term.examples, term.name
            for example in term.examples:
                assert term.regex.search(example), f"{term.name}: {example}"

    def test_every_example_passes_a_literal_prefilter(self, lex):
        for term in lex.terms.values():
            assert term.prefilters, term.name
            for example in term.examples:
                assert any(literal.lower() in example.lower() for literal in term.prefilters)

    def test_no_prefilter_contains_whitespace(self, lex):
        """A multi-word literal cannot be found in a phrase the record broke
        across a line, so the fast path would drop the match instead of the
        speech."""
        for term in lex.terms.values():
            for literal in term.prefilters:
                assert not any(char.isspace() for char in literal), f"{term.name}: {literal!r}"

    def test_every_prefilter_is_ascii(self, lex):
        """The fast path is upper-case containment, the pattern runs under
        `re.IGNORECASE`, and the two agree only on ASCII: `re.IGNORECASE` folds
        U+0130 'İ' to 'i' where upper-casing does not."""
        for term in lex.terms.values():
            for literal in term.prefilters:
                assert literal.isascii(), f"{term.name}: {literal!r}"

    def test_the_prefilter_never_loses_a_match_to_whitespace(self, lex):
        """The property the prefilter exists under: it may only make counting
        faster, never change what is counted. Checked against the term's own
        matching rule run directly on the same text — `Term.spans`, not the
        bare regex, because for an anchored term the two differ by design —
        over the whitespace a verbatim record actually contains."""
        for term in lex.terms.values():
            texts = [
                text
                for example in term.examples
                for raw in as_the_record_might_hold_it(example)
                for text in ([raw] if term.anchor is None else [raw, in_a_sentence_that_qualifies(raw)])
            ]
            counted = term.count(pd.Series(texts))
            for text, count in zip(texts, counted, strict=True):
                assert count == len(term.spans(text)), f"{term.name}: {text!r}"

    def test_an_anchored_term_counts_nothing_outside_a_genocide_sentence(self, lex):
        """What the anchor is for. The same words in a sentence that does not
        say the node word are a different agenda's words, and the review of
        1 September 2026 §3.4 is the record of how much of the commemorative
        and contentious registers they were."""
        anchored = [term for term in lex.active if term.anchor is not None]
        assert anchored, "v4 anchors seven terms; something has been dropped"
        for term in anchored:
            for example in term.examples:
                assert term.spans(f"The Council recalled {example} that day.") == []
                assert term.spans(in_a_sentence_that_qualifies(example))

    def test_an_anchor_does_not_reach_across_a_sentence_boundary(self, lex):
        """A sentence, not a paragraph and not a window. The neighbouring
        sentence saying the word is what a co-occurrence measure would count
        and what this deliberately does not."""
        term = lex.terms["commemoration"]
        assert term.spans("We marked the anniversary. It was a genocide.") == []
        assert term.spans("We marked the anniversary of the genocide. It was grave.")

    def test_every_anchor_is_one_the_loader_knows(self, lex):
        """A mistyped anchor would silently mean 'none' and inflate the term."""
        for term in lex.terms.values():
            assert term.anchor is None or term.anchor in lexicon.ANCHORS, term.name

    def test_every_pattern_records_the_version_it_last_changed_in(self, lex):
        """`pattern_since` is what lets a gold sample or a committed model run
        survive a version bump that did not touch the term it is keyed to."""
        for term in lex.terms.values():
            assert isinstance(term.pattern_since, int), term.name
            assert 1 <= term.pattern_since <= lex.version, term.name

    def test_a_term_is_compatible_with_every_version_since_its_pattern_changed(self, lex):
        term = lex.terms["genocide"]
        assert lex.compatible("genocide", term.pattern_since)
        assert lex.compatible("genocide", lex.version)
        assert not lex.compatible("genocide", term.pattern_since - 1)
        assert not lex.compatible("genocide", lex.version + 1)

    def test_tiers_and_registers_are_populated(self, lex):
        for term in lex.terms.values():
            assert term.tier
            assert term.register

    def test_sets_reference_defined_terms(self, lex):
        for name, members in lex.sets.items():
            missing = [m for m in members if m not in lex.terms]
            assert missing == [], f"set '{name}' references {missing}"

    def test_nested_terms_reference_defined_parents(self, lex):
        for term in lex.terms.values():
            assert term.nested_under is None or term.nested_under in lex.terms

    def test_the_core_term_matches_its_own_word(self, lex):
        regex = lex.terms["genocide"].regex
        for word in ("genocide", "Genocide", "genocidal", "genocides"):
            assert regex.search(word), word

    def test_the_core_term_leaves_the_actor_label_to_its_own_term(self, lex):
        """§3.4 of the review: `\\bgenocid\\w*` folded an actor label for the
        ex-FAR and Interahamwe into the count of the word as qualification of
        an event, and the two model runs disagree on exactly those cases."""
        for word in ("genocidaire", "genocidaires", "Genocidaires"):
            assert not lex.terms["genocide"].regex.search(word), word
            assert lex.terms["genocidaires"].regex.search(word), word

    def test_the_two_core_patterns_partition_the_old_union(self, lex):
        """What keeps v3's headline count reportable: the patterns are
        disjoint and between them they match what `\\bgenocid\\w*` matched, so
        `n_genocide + n_genocidaires` is the number the old column held."""
        union = re.compile(r"\bgenocid\w*", re.IGNORECASE)
        genocide, actors = lex.terms["genocide"], lex.terms["genocidaires"]
        for word in ("genocide", "genocidal", "genocides", "genocidaire", "genocidaires"):
            assert len(union.findall(word)) == len(genocide.regex.findall(word)) + len(
                actors.regex.findall(word)
            ), word

    def test_the_repaired_terms_no_longer_match_what_the_review_found(self, lex):
        """The five noisy terms of §3.4, each against the phrase that was
        driving its series."""
        assert not lex.terms["holocaust"].regex.search("a nuclear holocaust")
        assert not lex.terms["holocaust"].regex.search("an atomic holocaust")
        assert lex.terms["holocaust"].regex.search("the Holocaust")
        assert not lex.terms["tribunals"].regex.search(
            "the International Tribunal for the Law of the Sea"
        )
        assert lex.terms["tribunals"].regex.search("the International Residual Mechanism")
        assert lex.terms["tribunals"].regex.search(
            "the Mechanism for International Criminal Tribunals"
        )
        # `denial` and the rest are repaired by the anchor rather than by the
        # pattern, so the phrase is tested through the whole matching rule.
        assert lex.terms["denial"].spans("the denial of humanitarian access") == []
        assert lex.terms["denial"].spans("Serbia denied that the genocide occurred")
        assert lex.terms["survivors"].spans("survivors of sexual violence") == []
        assert lex.terms["glorification"].spans("the glorification of terrorism") == []
        assert lex.terms["commemoration"].spans(
            "the anniversary of resolution 1325"
        ) == []

    def test_denial_catches_the_inflections_the_old_pattern_missed(self, lex):
        """`deny\\w*` matched *denying* and missed *denies* and *denied*,
        which is where most of the denying in this corpus is done."""
        for form in ("denies", "denied", "denying", "denial", "denials"):
            assert lex.terms["denial"].regex.search(form), form

    def test_the_added_terms_are_present_and_match_their_phrase(self, lex):
        """The five §3.4 asks for, each by the phrase it was asked for."""
        expected = {
            "massacre": "the Boipatong massacre",
            "mass_killing": "the mass killings in Srebrenica",
            "icj": "the International Court of Justice",
            "intent_to_destroy": "with intent to destroy the group, genocide",
            "incitement": "incitement to commit genocide",
        }
        for name, phrase in expected.items():
            assert name in lex.terms, name
            assert lex.terms[name].spans(phrase), name

    def test_the_core_register_is_no_longer_a_copy_of_one_term(self, lex):
        """Housekeeping from §3.4: `core` held only `genocide`, so
        `has_register_core` said exactly what `has_genocide` said."""
        members = [term.name for term in lex.by_register()["core"]]
        assert len(members) > 1, members

    def test_the_header_names_every_register_the_file_uses(self, lex):
        """The other half of the housekeeping: the header claimed four
        discursive families while the file carried six, so a reader who
        trusted it would have looked for two registers that were never
        described. Enumerating them there is what keeps the claim checkable."""
        header = LEXICON.read_text(encoding="utf-8").split("\nversion:")[0]
        missing = sorted(r for r in lex.by_register() if r not in header)
        assert missing == [], f"the header does not name {missing}"

    def test_ocr_variants_are_held_back_by_default(self, lex):
        """Folding OCR noise into the headline count silently would overstate
        how much of it there is."""
        assert "genocide_ocr_variants" in lex.terms
        assert not lex.terms["genocide_ocr_variants"].enabled
        assert "genocide_ocr_variants" not in {t.name for t in lex.active}


def a_term(name: str, pattern: str, pattern_since: int) -> lexicon.Term:
    """One term, as `load()` would have built it."""
    return lexicon.Term(
        name=name,
        pattern=pattern,
        tier="core",
        register="core",
        pattern_since=pattern_since,
        examples=(name,),
        prefilters=(name,),
        regex=re.compile(pattern, re.IGNORECASE),
    )


def a_lock(version: int, terms: dict[str, lexicon.Term]) -> dict[str, object]:
    """The lock `tools/lock_lexicon.py` would write for `terms`."""
    return {
        "version": version,
        "terms": {
            name: {
                "pattern_since": term.pattern_since,
                "pattern_sha256": lexicon.pattern_sha256(term.pattern),
            }
            for name, term in sorted(terms.items())
        },
    }


class TestLexiconLock:
    """`pattern_since` is a claim about a pattern; the lock is what holds it.

    Editing a pattern and leaving its `pattern_since` behind would let 15
    aggregate a committed model run enumerated from the regex that is no longer
    in the file. The lock records each pattern's digest beside the version it is
    declared to date from, and `load()` refuses a lexicon it no longer describes.
    """

    def test_the_committed_lock_describes_the_committed_lexicon(self, lex):
        """`load()` already checked this — the point here is that a failure
        names the lock and the command that rewrites it."""
        lock = json.loads(LEXICON_LOCK.read_text(encoding="utf-8"))
        lexicon.check_lock(lex.terms, lex.version, lock)
        assert lock["version"] == lex.version
        assert set(lock["terms"]) == set(lex.terms), "every term is locked, disabled included"

    def test_an_edited_pattern_with_a_stale_pattern_since_is_refused(self):
        """The case the lock exists for."""
        terms = {"genocide": a_term("genocide", r"\bgenocid\w*", 2)}
        lock = a_lock(3, terms)
        edited = {"genocide": a_term("genocide", r"\bgenocid\w*|\bshoah\b", 2)}
        with pytest.raises(ValueError, match="pattern of 'genocide' changed"):
            lexicon.check_lock(edited, 3, lock)

    def test_an_edited_pattern_passes_only_once_the_lock_is_rewritten(self):
        """Bumping `pattern_since` is half of it: the lock still records the old
        digest until the tool is run, and that is what the message asks for."""
        old = a_lock(3, {"genocide": a_term("genocide", r"\bgenocid\w*", 2)})
        bumped = {"genocide": a_term("genocide", r"\bgenocid\w*|\bshoah\b", 3)}
        with pytest.raises(ValueError, match="pattern of 'genocide' changed"):
            lexicon.check_lock(bumped, 3, old)
        lexicon.check_lock(bumped, 3, a_lock(3, bumped))

    def test_a_pattern_since_edited_on_its_own_is_refused(self):
        """The declaration moved and the pattern did not, which the lock also
        knows about: one of the two is wrong."""
        terms = {"genocide": a_term("genocide", r"\bgenocid\w*", 2)}
        moved = {"genocide": a_term("genocide", r"\bgenocid\w*", 3)}
        with pytest.raises(ValueError, match="declares pattern_since 3"):
            lexicon.check_lock(moved, 3, a_lock(3, terms))

    def test_a_term_missing_from_the_lock_is_refused(self):
        terms = {"genocide": a_term("genocide", r"\bgenocid\w*", 2)}
        lock = a_lock(3, terms)
        terms["holocaust"] = a_term("holocaust", r"\bholocaust\b", 3)
        with pytest.raises(ValueError, match="does not lock"):
            lexicon.check_lock(terms, 3, lock)

    def test_a_locked_term_the_lexicon_dropped_is_refused(self):
        terms = {"genocide": a_term("genocide", r"\bgenocid\w*", 2)}
        lock = a_lock(3, {**terms, "holocaust": a_term("holocaust", r"\bholocaust\b", 3)})
        with pytest.raises(ValueError, match="no longer defines"):
            lexicon.check_lock(terms, 3, lock)

    def test_a_version_mismatch_is_refused(self):
        """A lock left behind by a bump describes a file that no longer exists,
        whatever it says about the patterns."""
        terms = {"genocide": a_term("genocide", r"\bgenocid\w*", 2)}
        with pytest.raises(ValueError, match="locks lexicon version 2"):
            lexicon.check_lock(terms, 3, a_lock(2, terms))
