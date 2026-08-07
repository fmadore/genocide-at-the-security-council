"""Collocation, keyness and the co-occurrence network.

These produce the tables a reader will treat as findings, so the statistics are
checked against values worked out by hand, and the control-set sampling is
checked for the two ways it could quietly lie: drawing a control from outside
the stratum, or reusing one.
"""

from __future__ import annotations

import math
import re
from collections import Counter

import pandas as pd
import pytest
from lib import lexical
from lib.lexicon import Lexicon, Term


def term(name: str, pattern: str) -> Term:
    return Term(
        name=name,
        pattern=pattern,
        tier="core",
        register="core",
        regex=re.compile(pattern, re.IGNORECASE),
    )


class TestTokenise:
    def test_words_are_lower_cased(self):
        assert lexical.tokenise("The COUNCIL Met").words == ["the", "council", "met"]

    def test_digits_are_not_vocabulary(self):
        """Resolution numbers and dates would swamp any table they entered."""
        assert lexical.tokenise("resolution 955 of 1994").words == ["resolution", "of"]

    def test_internal_apostrophes_and_hyphens_are_kept(self):
        assert lexical.tokenise("the Secretary-General's report").words == [
            "the",
            "secretary-general's",
            "report",
        ]

    def test_offsets_point_back_into_the_source(self):
        source = "the Council met"
        tokens = lexical.tokenise(source)
        pairs = zip(tokens.words, tokens.starts, strict=True)
        assert [source[s : s + len(w)].lower() for w, s in pairs] == tokens.words


class TestAround:
    def test_the_node_is_not_its_own_collocate(self):
        source = "one two genocide three four"
        tokens = lexical.tokenise(source)
        span = (source.index("genocide"), source.index("genocide") + len("genocide"))
        assert "genocide" not in tokens.around(span, 2)

    def test_the_window_takes_from_both_sides(self):
        source = "a b c genocide d e f"
        tokens = lexical.tokenise(source)
        span = (source.index("genocide"), source.index("genocide") + len("genocide"))
        assert tokens.around(span, 2) == ["b", "c", "d", "e"]

    def test_a_window_at_the_edge_is_truncated_not_wrapped(self):
        source = "genocide d e"
        tokens = lexical.tokenise(source)
        assert tokens.around((0, 8), 5) == ["d", "e"]

    def test_a_multi_word_node_excludes_all_of_its_own_tokens(self):
        """`crimes against humanity` is three tokens. Counting two of them as
        collocates of the third would put the term at the top of its own table."""
        source = "the crimes against humanity were"
        tokens = lexical.tokenise(source)
        span = (source.index("crimes"), source.index("humanity") + len("humanity"))
        assert tokens.around(span, 3) == ["the", "were"]


class TestLogLikelihood:
    def test_a_word_at_the_same_rate_in_both_scores_zero(self):
        assert lexical.log_likelihood(10, 100, 1_000, 10_000) == pytest.approx(0.0)

    def test_over_representation_is_positive_and_under_negative(self):
        assert lexical.log_likelihood(50, 100, 1_000, 10_000) > 0
        assert lexical.log_likelihood(2, 100, 1_000, 10_000) < 0

    def test_it_matches_the_formula(self):
        a, b, target, reference = 30, 70, 1_000, 9_000
        total = target + reference
        expected = 2 * (
            a * math.log(a / (target * (a + b) / total))
            + b * math.log(b / (reference * (a + b) / total))
        )
        assert lexical.log_likelihood(a, b, target, reference) == pytest.approx(expected)

    def test_a_word_absent_from_both_scores_zero(self):
        assert lexical.log_likelihood(0, 0, 1_000, 1_000) == 0.0

    def test_an_empty_corpus_does_not_divide_by_zero(self):
        assert lexical.log_likelihood(5, 5, 0, 100) == 0.0


class TestLogRatio:
    def test_a_doubled_rate_is_one_bit(self):
        assert lexical.log_ratio(20, 10, 1_000, 1_000) == pytest.approx(1.0)

    def test_a_word_absent_from_the_reference_uses_half_an_occurrence(self):
        """An infinite ratio is unplottable. The floor is a stated convention,
        not a measurement."""
        assert lexical.log_ratio(10, 0, 1_000, 1_000) == pytest.approx(math.log2(10 / 0.5))


class TestCompare:
    @pytest.fixture
    def counts(self):
        target = Counter({"genocide": 20, "the": 500, "rare": 2, "justice": 10})
        reference = target + Counter({"genocide": 30, "the": 9_500, "justice": 200})
        return target, reference

    def test_the_target_is_subtracted_from_its_reference(self, counts):
        """The reference is the whole corpus, so the two sides of the table
        would otherwise overlap and every statistic would be understated."""
        target, reference = counts
        rows = {r["word"]: r for r in lexical.compare(target, reference, 1_000, 10_000, frozenset())}
        assert rows["genocide"]["reference"] == 30

    def test_stopwords_are_dropped(self, counts):
        target, reference = counts
        rows = lexical.compare(target, reference, 1_000, 10_000, frozenset({"the"}))
        assert "the" not in {r["word"] for r in rows}

    def test_rare_words_are_dropped(self, counts):
        target, reference = counts
        rows = lexical.compare(target, reference, 1_000, 10_000, frozenset(), min_count=5)
        assert "rare" not in {r["word"] for r in rows}

    def test_rows_come_back_ranked(self, counts):
        target, reference = counts
        rows = lexical.compare(target, reference, 1_000, 10_000, frozenset())
        assert [r["g2"] for r in rows] == sorted((r["g2"] for r in rows), reverse=True)

    def test_the_limit_is_applied_after_ranking(self, counts):
        target, reference = counts
        rows = lexical.compare(target, reference, 1_000, 10_000, frozenset(), limit=1)
        assert len(rows) == 1
        assert rows[0]["word"] == "genocide"


class TestMatchedControl:
    @pytest.fixture
    def frame(self):
        """Two strata. 1994 has three targets and three possible controls;
        2000 has two targets and only one control available."""
        rows = []
        for i in range(3):
            rows.append({"year": 1994, "agenda": "Rwanda", "hit": True, "tag": f"t94-{i}"})
        for i in range(3):
            rows.append({"year": 1994, "agenda": "Rwanda", "hit": False, "tag": f"c94-{i}"})
        for i in range(2):
            rows.append({"year": 2000, "agenda": "Syria", "hit": True, "tag": f"t00-{i}"})
        rows.append({"year": 2000, "agenda": "Syria", "hit": False, "tag": "c00-0"})
        return pd.DataFrame(rows)

    def test_controls_come_from_the_target_stratum(self, frame):
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        picked = frame.loc[control.index]
        assert (~picked["hit"]).all()
        assert sorted(picked["year"].value_counts().to_dict().items()) == [(1994, 3), (2000, 1)]

    def test_no_control_is_used_twice(self, frame):
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        assert len(set(control.index)) == len(control.index)

    def test_a_stratum_that_cannot_be_filled_is_reported(self, frame):
        """A debate where nearly everyone said the word. Silently under-covering
        it would bias the whole table towards the crisis years."""
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        assert control.short_strata == [((2000, "Syria"), 2, 1)]
        assert control.matched == 4
        assert control.wanted == 5
        assert control.coverage == pytest.approx(0.8)

    def test_the_same_seed_draws_the_same_controls(self, frame):
        first = lexical.matched_control(frame, "hit", ["year", "agenda"], seed=3)
        second = lexical.matched_control(frame, "hit", ["year", "agenda"], seed=3)
        assert list(first.index) == list(second.index)

    def test_a_stratum_with_no_controls_at_all_contributes_none(self):
        frame = pd.DataFrame([{"year": 1994, "agenda": "Rwanda", "hit": True}])
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        assert len(control.index) == 0
        assert control.coverage == 0.0


class TestPmiNetwork:
    def lex(self, *names) -> Lexicon:
        return Lexicon(
            version=1,
            updated="2026-08-07",
            terms={n: term(n, n) for n in names},
            sets={},
        )

    def test_two_terms_that_always_travel_together(self):
        frame = pd.DataFrame(
            {"has_a": [True, True, False, False], "has_b": [True, True, False, False]}
        )
        edge = lexical.pmi_network(frame, self.lex("a", "b"), min_speeches=1)[0]
        assert edge["speeches"] == 2
        assert edge["pmi"] == pytest.approx(1.0)
        assert edge["npmi"] == pytest.approx(1.0)

    def test_independent_terms_score_zero(self):
        frame = pd.DataFrame(
            {"has_a": [True, True, False, False], "has_b": [True, False, True, False]}
        )
        edge = lexical.pmi_network(frame, self.lex("a", "b"), min_speeches=1)[0]
        assert edge["pmi"] == pytest.approx(0.0)

    def test_a_thin_edge_is_dropped(self):
        frame = pd.DataFrame(
            {"has_a": [True, True, False], "has_b": [True, False, False]}
        )
        assert lexical.pmi_network(frame, self.lex("a", "b"), min_speeches=5) == []

    def test_normalised_pmi_stays_within_bounds(self):
        frame = pd.DataFrame(
            {
                "has_a": [True] * 30 + [False] * 70,
                "has_b": [True] * 10 + [False] * 90,
                "has_c": [False] * 50 + [True] * 50,
            }
        )
        edges = lexical.pmi_network(frame, self.lex("a", "b", "c"), min_speeches=1)
        assert all(-1.0 <= float(e["npmi"]) <= 1.0 for e in edges)

    def test_an_empty_frame_yields_no_edges(self):
        empty = pd.DataFrame({"has_a": pd.Series(dtype=bool), "has_b": pd.Series(dtype=bool)})
        assert lexical.pmi_network(empty, self.lex("a", "b")) == []


class TestStopwords:
    def test_the_real_list_loads_and_holds_only_function_words(self):
        """The file's own header commits to this. A genre word creeping in
        would answer the collocate question by assumption."""
        words = lexical.load_stopwords()
        assert "the" in words and "of" in words
        for genre_word in ("council", "security", "resolution", "genocide", "president"):
            assert genre_word not in words

    def test_comments_and_blank_lines_are_ignored(self):
        words = lexical.load_stopwords()
        assert not any(w.startswith("#") or not w for w in words)
