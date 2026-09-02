"""Roll-ups over a lexicon that declares nesting.

Four terms in `config/lexicon.yml` are declared `nested_under` another: their
matches lie inside the parent's. Adding both to one occurrence sum would count
one span twice, and that sum is published as a register's occurrence count and
token rate (04_series) and as `n_lexicon_total` (09_export_speeches). These
tests fix the arithmetic on a hand-built lexicon, where the expected numbers can
be counted by eye, and then check the real one behaves the same way.
"""

from __future__ import annotations

import re

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

#: Three levels of containment, which `config/lexicon.yml` does not have today:
#: every "grave war crime" is a "war crime" and every "war crime" a "crime".
CRIMES = term("crimes", r"\bcrimes?\b", "legal", "crime")
WAR_CRIMES = term("war_crimes", r"\bwar\s+crimes?\b", "legal", "crime", "crimes")
GRAVE_WAR_CRIMES = term(
    "grave_war_crimes", r"\bgrave\s+war\s+crimes?\b", "legal", "grave", "war_crimes"
)

#: Everything the tests resolve a parent through. `summable` walks the chain
#: here, not inside the list it is given, which is what makes a grandchild
#: whose parent is absent from a sum still drop out of it.
TABLE = {
    t.name: t
    for t in (
        ATROCITY,
        MASS_ATROCITY,
        GENOCIDE,
        GENOCIDE_CONVENTION,
        CRIMES,
        WAR_CRIMES,
        GRAVE_WAR_CRIMES,
    )
}


@pytest.fixture(scope="module")
def lex():
    """A parent and child in one register, and a pair split across two."""
    terms = [ATROCITY, MASS_ATROCITY, GENOCIDE, GENOCIDE_CONVENTION]
    return Lexicon(
        version=1,
        updated="2026-09-01",
        terms={t.name: t for t in terms},
        sets={"atrocity_core": ["genocide", "mass_atrocity"]},
    )


@pytest.fixture(scope="module")
def real_lex():
    return lexicon.load()


def counts(lex: Lexicon, body: str) -> pd.Series:
    """The single row `apply` produces for one speech body."""
    return lexicon.apply(pd.Series([body]), lex).iloc[0]


class TestSummable:
    def test_a_child_without_its_parent_is_kept(self):
        """Nothing else in that sum covers it, which is how a nested term still
        counts in full in a register its parent does not belong to."""
        assert lexicon.summable([MASS_ATROCITY], TABLE) == [MASS_ATROCITY]

    def test_a_child_summed_beside_its_parent_is_dropped(self):
        assert lexicon.summable([ATROCITY, MASS_ATROCITY], TABLE) == [ATROCITY]

    def test_the_given_order_survives(self):
        """Callers turn the result straight into a list of column names."""
        given = [GENOCIDE, MASS_ATROCITY, ATROCITY, GENOCIDE_CONVENTION]
        assert lexicon.summable(given, TABLE) == [GENOCIDE, ATROCITY]

    def test_a_grandchild_is_dropped_when_the_middle_term_is_absent(self):
        """The reason the chain is walked through the whole table: `war_crimes`
        may be out of this sum — another register, or disabled — and every grave
        war crime is still a crime, so keeping both would count it twice."""
        assert lexicon.summable([CRIMES, GRAVE_WAR_CRIMES], TABLE) == [CRIMES]

    def test_a_whole_chain_keeps_only_its_root(self):
        assert lexicon.summable([CRIMES, WAR_CRIMES, GRAVE_WAR_CRIMES], TABLE) == [CRIMES]

    def test_a_chain_without_its_root_keeps_the_highest_member_present(self):
        assert lexicon.summable([WAR_CRIMES, GRAVE_WAR_CRIMES], TABLE) == [WAR_CRIMES]

    def test_an_empty_list_is_empty(self):
        assert lexicon.summable([], TABLE) == []


class TestNestingValidation:
    """The shapes `summable` cannot describe, refused where the file is read.

    None of them exists in `config/lexicon.yml`; each would silently drop terms
    from the roll-ups if it ever did.
    """

    def test_the_committed_lexicon_passes(self, real_lex):
        lexicon.check_nesting(real_lex.terms)

    def test_a_term_nested_under_itself_is_refused(self):
        itself = term("atrocity", r"\batrocit(?:y|ies)\b", "legal", "atroc", "atrocity")
        with pytest.raises(ValueError, match="nested under themselves"):
            lexicon.check_nesting({itself.name: itself})

    def test_a_cycle_is_refused(self):
        """Each term would be dropped as covered by the other, and the whole
        loop would vanish from every sum."""
        first = term("crimes", r"\bcrimes?\b", "legal", "crime", "war_crimes")
        second = term("war_crimes", r"\bwar\s+crimes?\b", "legal", "crime", "crimes")
        with pytest.raises(ValueError, match="cycle"):
            lexicon.check_nesting({first.name: first, second.name: second})

    def test_an_undefined_parent_is_refused(self):
        orphan = term("mass_atrocity", r"\bmass\s+atrocit(?:y|ies)\b", "legal", "atroc", "nope")
        with pytest.raises(ValueError, match="undefined parents"):
            lexicon.check_nesting({orphan.name: orphan})


class TestNestedRollups:
    def test_a_child_and_parent_in_one_register_count_one_span_once(self, lex):
        """Every 'mass atrocity' is an 'atrocity'. Both terms are in the legal
        register, so adding both would report three occurrences where a reader
        of the record can point at two."""
        row = counts(lex, "there were mass atrocities and an atrocity")
        assert row["n_atrocity"] == 2
        assert row["n_mass_atrocity"] == 1
        assert row["n_register_legal"] == 2
        assert row["has_register_legal"]
        assert row["n_lexicon_total"] == 2

    def test_a_child_counts_in_full_in_a_register_its_parent_is_absent_from(self, lex):
        """`genocide` is core and `genocide_convention` legal, so the legal sum
        has nothing to double-count; the total, which holds both, does."""
        row = counts(lex, "the Genocide Convention")
        assert row["n_genocide"] == 1
        assert row["n_genocide_convention"] == 1
        assert row["n_register_core"] == 1
        assert row["n_register_legal"] == 1
        assert row["n_lexicon_total"] == 1

    def test_distinct_terms_present_still_counts_the_child(self, lex):
        """`n_lexicon_terms` counts terms, not spans: a speech naming the
        Convention has used two of them."""
        assert counts(lex, "the Genocide Convention")["n_lexicon_terms"] == 2

    def test_a_speech_with_no_match_is_all_zeros_and_all_false(self, lex):
        row = counts(lex, "the Council met this morning and adjourned")
        assert [row[c] for c in row.index if c.startswith(lexicon.COUNT)] == [0] * 8
        assert not any(row[c] for c in row.index if c.startswith(lexicon.HAS))


class TestTheRealLexicon:
    def test_mass_atrocities_is_one_occurrence_of_the_legal_register(self, real_lex):
        """`mass_atrocity` and its parent `atrocity` are both legal terms, and
        nothing else in the lexicon matches this sentence."""
        row = counts(real_lex, "The Council condemned the mass atrocities committed there.")
        assert row["n_mass_atrocity"] == 1
        assert row["n_atrocity"] == 1
        assert row["n_register_legal"] == 1
        assert row["n_lexicon_total"] == 1

    def test_every_declared_parent_is_itself_active(self, real_lex):
        """A child whose parent were disabled would be dropped from no sum and
        would stand in for the parent's span alone. Nothing in the config does
        that today; this says so out loud."""
        active = {t.name for t in real_lex.active}
        orphans = [
            t.name for t in real_lex.active if t.nested_under and t.nested_under not in active
        ]
        assert orphans == []
