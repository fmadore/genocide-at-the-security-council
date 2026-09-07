"""What `lib.lexicon` counts, and what it refuses to count.

Until v5 this file fixed the arithmetic of the roll-ups: four terms in
`config/lexicon.yml` are declared `nested_under` another, their matches lie
inside the parent's, and a register sum holding both counted one span twice.
R7 removed the sums instead of maintaining the repair, so what these tests now
hold is the absence: `apply` writes one count and one flag per term, one pair
per derived measure, and nothing whatever that adds two terms together.

The nesting declarations survive, because the `derived` subtraction is built on
them, and so does the validation that refuses a graph which cannot describe
containment. The `intensity` ladder is new, and it is checked for the one
property that makes it a ladder: every pair of rungs is comparable.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pandas as pd
import pytest
from lib import lexicon
from lib.lexicon import Lexicon, Term


def term(
    name: str,
    pattern: str,
    register: str,
    prefilter: str,
    nested_under: str | None = None,
) -> Term:
    """One term, compiled as `load()` compiles it.

    The prefilter is not decoration: `Term.count` only runs the regex over texts
    containing one of these literals, so a term without one counts nothing.
    """
    return Term(
        name=name,
        pattern=pattern,
        tier="core",
        register=register,
        examples=(name.replace("_", " "),),
        prefilters=(prefilter,),
        nested_under=nested_under,
        regex=re.compile(pattern, re.IGNORECASE),
    )


ATROCITY = term("atrocity", r"\batrocit(?:y|ies)\b", "legal", "atroc")
MASS_ATROCITY = term(
    "mass_atrocity", r"\bmass\s+atrocit(?:y|ies)\b", "legal", "atroc", "atrocity"
)
GENOCIDE = term("genocide", r"\bgenocid\w*", "core", "genocid")
GENOCIDE_CONVENTION = term(
    "genocide_convention",
    r"\bgenocide\s+convention\b",
    "legal",
    "convention",
    "genocide",
)


@pytest.fixture(scope="module")
def lex():
    """A parent and child in one register, and a pair split across two."""
    terms = [ATROCITY, MASS_ATROCITY, GENOCIDE, GENOCIDE_CONVENTION]
    return Lexicon(version=1, updated="2026-09-01", terms={t.name: t for t in terms})


@pytest.fixture(scope="module")
def real_lex():
    return lexicon.load()


def counts(lex: Lexicon, body: str) -> pd.Series:
    """The single row `apply` produces for one speech body."""
    return lexicon.apply(pd.Series([body]), lex).iloc[0]


class TestNestingValidation:
    """The shapes containment cannot take, refused where the file is read.

    None of them exists in `config/lexicon.yml`; each would make a `derived`
    subtraction an arithmetic accident between two unrelated counts rather than
    a narrowing of the term it claims to narrow.
    """

    def test_the_committed_lexicon_passes(self, real_lex):
        lexicon.check_nesting(real_lex.terms)

    def test_a_term_nested_under_itself_is_refused(self):
        itself = term("atrocity", r"\batrocit(?:y|ies)\b", "legal", "atroc", "atrocity")
        with pytest.raises(ValueError, match="nested under themselves"):
            lexicon.check_nesting({itself.name: itself})

    def test_a_cycle_is_refused(self):
        """Containment has a direction, and a loop asserts that each of two
        terms lies inside the other."""
        first = term("crimes", r"\bcrimes?\b", "legal", "crime", "war_crimes")
        second = term("war_crimes", r"\bwar\s+crimes?\b", "legal", "crime", "crimes")
        with pytest.raises(ValueError, match="cycle"):
            lexicon.check_nesting({first.name: first, second.name: second})

    def test_an_undefined_parent_is_refused(self):
        orphan = term("mass_atrocity", r"\bmass\s+atrocit(?:y|ies)\b", "legal", "atroc", "nope")
        with pytest.raises(ValueError, match="undefined parents"):
            lexicon.check_nesting({orphan.name: orphan})


class TestNothingSumsOverTerms:
    def test_the_columns_are_exactly_two_per_term(self, lex):
        """Four terms, eight columns, and no ninth. The register sums, the set
        flags and the two lexicon totals were all written here."""
        frame = lexicon.apply(pd.Series(["there were mass atrocities"]), lex)
        assert sorted(frame.columns) == sorted(
            [f"{prefix}{name}" for name in lex.terms for prefix in (lexicon.COUNT, lexicon.HAS)]
        )

    def test_a_child_and_its_parent_are_two_independent_counts(self, lex):
        """Every 'mass atrocity' is an 'atrocity', and each term now reports
        what its own pattern matched. The overlap is a fact about the two
        patterns that a reader can see in the concordance, rather than an
        arithmetic hazard in a sum nobody can decompose."""
        row = counts(lex, "there were mass atrocities and an atrocity")
        assert row["n_atrocity"] == 2
        assert row["n_mass_atrocity"] == 1

    def test_no_roll_up_column_survives(self, lex):
        """Named one by one, because each was a published measure and a reader
        of an older payload will look for it."""
        row = counts(lex, "the Genocide Convention")
        for gone in (
            "n_register_legal",
            "has_register_legal",
            "n_register_core",
            "has_set_atrocity_core",
            "n_lexicon_total",
            "n_lexicon_terms",
        ):
            assert gone not in row.index

    def test_a_speech_with_no_match_is_all_zeros_and_all_false(self, lex):
        row = counts(lex, "the Council met this morning and adjourned")
        assert [row[c] for c in row.index if c.startswith(lexicon.COUNT)] == [0] * 4
        assert not any(row[c] for c in row.index if c.startswith(lexicon.HAS))


class TestTheRealLexicon:
    def test_mass_atrocities_is_counted_by_both_terms_that_match_it(self, real_lex):
        """`mass_atrocity` and its parent `atrocity` both match this sentence,
        and each says so on its own row."""
        row = counts(real_lex, "The Council condemned the mass atrocities committed there.")
        assert row["n_mass_atrocity"] == 1
        assert row["n_atrocity"] == 1

    def test_no_column_sums_over_more_than_one_term(self, real_lex):
        """The whole committed lexicon, not the hand-built one: 03 writes this
        frame into `speeches_flagged.parquet`, and every later step reads its
        columns by name."""
        frame = lexicon.apply(pd.Series(["genocide, war crimes and mass atrocities"]), real_lex)
        expected = {
            f"{prefix}{name}"
            for prefix in (lexicon.COUNT, lexicon.HAS)
            for name in [t.name for t in real_lex.active] + list(real_lex.derived)
        }
        assert set(frame.columns) == expected

    def test_every_declared_parent_is_itself_active(self, real_lex):
        """A child whose parent were disabled would be a narrowing of nothing,
        and the `derived` block subtracts on exactly this claim."""
        active = {t.name for t in real_lex.active}
        orphans = [
            t.name for t in real_lex.active if t.nested_under and t.nested_under not in active
        ]
        assert orphans == []


class TestTheLegalLadder:
    """`intensity`, and the one property that makes it an ordering.

    A ladder with two terms on a rung cannot answer the question it exists for
    — whether a delegation climbs it before using the word — because two of its
    steps would be the same step. The loader refuses that; these tests say what
    the committed file actually declares, since the ordering is an argument
    about the instruments and not an implementation detail.
    """

    def test_the_rungs_are_a_total_order(self, real_lex):
        ranked = {t.name: t.intensity for t in real_lex.terms.values() if t.intensity is not None}
        assert sorted(ranked.values()) == list(range(1, len(ranked) + 1))

    def test_the_ladder_is_the_one_the_instruments_support(self, real_lex):
        """Read out in full rather than spot-checked. Every rung is a claim
        about a legal instrument — see the gloss in `config/lexicon.yml` — and
        a silent reordering would change what a figure drawn from it means."""
        ranked = {t.name: t.intensity for t in real_lex.terms.values() if t.intensity is not None}
        assert ranked == {
            "genocide": 5,
            "war_crimes": 4,
            "crimes_against_humanity": 3,
            "ethnic_cleansing": 2,
            "atrocity": 1,
        }

    def test_the_committed_lexicon_passes(self, real_lex):
        lexicon.check_intensity(real_lex.terms)

    def test_two_terms_on_one_rung_are_refused(self):
        """The failure this is really about: a coder adding a sixth term and
        giving it the rung of the term it most resembles."""
        pair = {
            "atrocity": replace(ATROCITY, intensity=1),
            "mass_atrocity": replace(MASS_ATROCITY, intensity=1),
        }
        with pytest.raises(ValueError, match="not a total order"):
            lexicon.check_intensity(pair)

    def test_a_gap_in_the_rungs_is_refused(self):
        gapped = {
            "atrocity": replace(ATROCITY, intensity=1),
            "genocide": replace(GENOCIDE, intensity=3),
        }
        with pytest.raises(ValueError, match="not a total order"):
            lexicon.check_intensity(gapped)

    def test_a_lexicon_ordering_nothing_is_left_alone(self):
        """Most of the word list is not a qualification of an event and carries
        no rung; a file that ordered none of it is not thereby broken."""
        lexicon.check_intensity({"atrocity": ATROCITY, "genocide": GENOCIDE})
