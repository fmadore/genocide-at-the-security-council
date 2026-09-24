"""What `lib.lexicon` counts, and what it refuses to count.

Until v5 this file fixed the arithmetic of the roll-ups: four terms in
`config/lexicon.yml` are declared `nested_under` another, their matches lie
inside the parent's, and a register sum holding both counted one span twice.
R7 removed the sums instead of maintaining the repair, so what these tests now
hold is the absence: `apply` writes one count and one flag per term, one pair
per derived measure, and nothing whatever that adds two terms together.

The nesting declarations survive, because the `derived` subtraction is built on
them, and so does the validation that refuses a graph which cannot describe
containment. Since v8 a change that only adds matches can be declared a
widening, and these tests hold what that promises: the old spans survive, an
artefact made before it stays compatible and learns it is incomplete, and a
declaration that loses a span is caught. The committed counts that 03 holds
every term to are checked here as plain values.
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


class TestDeclaredWidenings:
    """`widened_since`: a change that adds occurrences and moves none."""

    WIDE = replace(
        GENOCIDE,
        pattern=r"\bg[eé]nocid\w*",
        prefilters=("nocid",),
        pattern_since=2,
        widened_since=8,
        widened_from=r"\bgenocid\w*",
        regex=re.compile(r"\bg[eé]nocid\w*", re.IGNORECASE),
    )

    def lexicon_with(self, term: Term) -> Lexicon:
        return Lexicon(version=8, updated="2026-09-24", terms={term.name: term})

    def test_an_artefact_from_before_the_widening_stays_compatible(self):
        lex = self.lexicon_with(self.WIDE)
        assert lex.compatible("genocide", 6)
        assert not lex.complete("genocide", 6), "it misses what the widening added"
        assert lex.complete("genocide", 8)

    def test_an_artefact_from_before_the_rule_is_not(self):
        lex = self.lexicon_with(self.WIDE)
        assert not lex.compatible("genocide", 1)
        assert not lex.complete("genocide", 1)

    def test_a_version_ahead_of_the_file_is_neither(self):
        lex = self.lexicon_with(self.WIDE)
        assert not lex.compatible("genocide", 9)
        assert not lex.complete("genocide", "9")

    def test_a_real_widening_passes_on_the_corpus(self):
        bodies = pd.Series(["The genocide and the génocidaires.", "Nothing."])
        assert lexicon.check_widenings(bodies, self.lexicon_with(self.WIDE)) == []

    def test_a_declared_widening_that_loses_a_span_is_caught(self):
        """`\\bgénocid\\w*` would drop every unaccented match; declaring it a
        widening is the mistake the corpus check exists to catch."""
        narrowed = replace(
            self.WIDE,
            pattern=r"\bgénocid\w*",
            regex=re.compile(r"\bgénocid\w*", re.IGNORECASE),
        )
        bodies = pd.Series(["The genocide and the génocidaires."])
        problems = lexicon.check_widenings(bodies, self.lexicon_with(narrowed))
        assert len(problems) == 1 and "loses 1 span" in problems[0]

    def test_the_accented_form_is_counted_by_the_committed_pattern(self, real_lex):
        found = counts(real_lex, "The génocidaires and the genocidaires fled.")
        assert found["n_genocide"] == 2

    def test_the_committed_genocide_pattern_is_a_declared_widening(self, real_lex):
        genocide = real_lex.terms["genocide"]
        assert genocide.pattern_since == 2, "occurrence identities date from v2"
        assert genocide.widened_since == 8 and genocide.widened_from == r"\bgenocid\w*"
        assert real_lex.compatible("genocide", 6), "the committed Qwen run records v6"

    def test_the_default_anchor_is_the_committed_one(self, real_lex):
        assert real_lex.anchor is not None
        assert real_lex.anchor.pattern == lexicon.ANCHOR_RE.pattern
        assert real_lex.anchor.prefilter == lexicon.ANCHOR_PREFILTER

    def test_every_anchored_term_declares_the_anchor_widening(self, real_lex):
        anchored = [t for t in real_lex.terms.values() if t.anchor is not None]
        assert anchored
        assert all(t.widened_since == real_lex.anchor.widened_since for t in anchored)

    def test_an_anchored_match_beside_the_accented_form_counts(self, real_lex):
        found = counts(real_lex, "The génocidaires spread incitement on the radio.")
        assert found["n_incitement"] == 1


class TestTheRetiredLadder:
    """`intensity` was removed at v8 and a revived key is refused on load."""

    def test_the_committed_lexicon_carries_no_rung(self, real_lex):
        assert not any(hasattr(t, "intensity") for t in real_lex.terms.values())

    def test_a_revived_key_is_refused(self, tmp_path, monkeypatch):
        source = lexicon.LEXICON.read_text(encoding="utf-8")
        revived = source.replace("    widened_since: 8\n    widened_from: '\\bgenocid\\w*'\n",
                                 "    widened_since: 8\n    widened_from: '\\bgenocid\\w*'\n"
                                 "    intensity: 5\n", 1)
        assert revived != source
        path = tmp_path / "lexicon.yml"
        path.write_text(revived, encoding="utf-8")
        monkeypatch.setattr(lexicon, "LEXICON", path)
        with pytest.raises(ValueError, match="removed at v8"):
            lexicon.load(check_lock=False)


class TestCommittedCounts:
    """`config/lexicon.counts.json`, the counts 03 holds every term to."""

    def record(self, **terms: tuple[int, int]) -> dict:
        return {
            "speeches": 10,
            "terms": {
                name: {"speeches": pair[0], "occurrences": pair[1]}
                for name, pair in terms.items()
            },
        }

    def test_identical_counts_pass(self):
        assert lexicon.count_problems(self.record(a=(1, 2)), self.record(a=(1, 2))) == []

    def test_a_moved_count_is_named(self):
        problems = lexicon.count_problems(self.record(a=(1, 3)), self.record(a=(1, 2)))
        assert problems == ["'a': 1 speeches / 3 occurrences, committed 1 / 2"]

    def test_added_and_removed_terms_are_both_named(self):
        problems = lexicon.count_problems(self.record(a=(1, 2)), self.record(b=(1, 2)))
        assert "'a' is counted but not committed" in problems
        assert "'b' is committed but no longer counted" in problems

    def test_another_corpus_is_refused(self):
        other = {**self.record(a=(1, 2)), "speeches": 11}
        assert "corpus of 11 speeches" in lexicon.count_problems(other, self.record(a=(1, 2)))[0]

    def test_the_record_is_built_from_the_flag_columns(self, lex):
        frame = lexicon.apply(pd.Series(["genocide and atrocities", "nothing"]), lex)
        record = lexicon.counts_record(frame, lex, 2)
        assert record["terms"]["genocide"] == {"speeches": 1, "occurrences": 1}
        assert record["speeches"] == 2 and record["lexicon_version"] == 1

    def test_the_population_is_read_from_the_committed_file(self):
        speeches, occurrences = lexicon.population("genocide")
        assert 0 < speeches <= occurrences

    def test_every_enabled_term_is_committed(self, real_lex):
        committed = lexicon.load_counts()["terms"]
        assert set(committed) == {t.name for t in real_lex.active} | set(real_lex.derived)
