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
        examples=(prefilter,),
        prefilters=(prefilter,),
        nested_under=nested_under,
        regex=re.compile(pattern, re.IGNORECASE),
    )


ATROCITY = term("atrocity", r"\batrocit(?:y|ies)\b", "legal", "atroc")
MASS_ATROCITY = term(
    "mass_atrocity", r"\bmass\s+atrocit(?:y|ies)\b", "legal", "mass atroc", "atrocity"
)
GENOCIDE = term("genocide", r"\bgenocid\w*", "core", "genocid")
GENOCIDE_CONVENTION = term(
    "genocide_convention",
    r"\bgenocide\s+convention\b",
    "legal",
    "genocide convention",
    "genocide",
)


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
        assert lexicon.summable([MASS_ATROCITY]) == [MASS_ATROCITY]

    def test_a_child_summed_beside_its_parent_is_dropped(self):
        assert lexicon.summable([ATROCITY, MASS_ATROCITY]) == [ATROCITY]

    def test_the_given_order_survives(self):
        """Callers turn the result straight into a list of column names."""
        given = [GENOCIDE, MASS_ATROCITY, ATROCITY, GENOCIDE_CONVENTION]
        assert lexicon.summable(given) == [GENOCIDE, ATROCITY]

    def test_an_empty_list_is_empty(self):
        assert lexicon.summable([]) == []


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
