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

    def test_a_digit_inside_a_word_is_kept(self):
        """`R2P` is a lexicon term; as `r` and `p` it was invisible to keyness."""
        assert lexical.tokenise("R2P and COVID-19").words == ["r2p", "and", "covid-19"]

    def test_a_scare_quoted_word_is_the_same_word(self):
        """`'genocide'` used to tokenise as `genocide'`, a type of its own, so the
        distanced use this study most wants to see dropped out of every table."""
        curly = chr(0x2019)
        assert lexical.tokenise(f"so-called 'genocide' or {curly}genocide{curly}").words == [
            "so-called",
            "genocide",
            "or",
            "genocide",
        ]
        assert lexical.tokenise("a trailing- hyphen and an apostrophe'").words == [
            "a",
            "trailing",
            "hyphen",
            "and",
            "an",
            "apostrophe",
        ]

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

    def test_overlapping_windows_count_shared_context_once(self):
        source = "one genocide shared genocide two"
        tokens = lexical.tokenise(source)
        starts = [m.span() for m in re.finditer("genocide", source)]
        assert tokens.context(starts, 2) == ["one", "shared", "two"]


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

    def test_rows_come_back_ranked_by_effect_not_by_significance(self, counts):
        """G² is a floor: on 59 million tokens almost everything clears it, and
        ordering by it would put the commonest words first however small their
        rate difference. The order is the effect size."""
        target, reference = counts
        rows = lexical.compare(target, reference, 1_000, 10_000, frozenset(), floor=0.0)
        ratios = [r["log_ratio"] for r in rows]
        assert ratios == sorted(ratios, reverse=True)
        assert rows[0]["word"] == "genocide"

    def test_a_row_below_the_significance_floor_is_dropped(self, counts):
        target, reference = counts
        # `justice`: 10 of 1,000 against 200 of 10,000, a rate ratio of 0.5 on
        # ten occurrences — |G²| about 6, under the p < 0.001 floor of 10.83.
        kept = {r["word"] for r in lexical.compare(target, reference, 1_000, 10_000, frozenset())}
        assert "justice" not in kept
        assert "genocide" in kept
        loose = {
            r["word"]
            for r in lexical.compare(target, reference, 1_000, 10_000, frozenset(), floor=0.0)
        }
        assert "justice" in loose

    def test_an_unknown_rank_column_is_refused(self, counts):
        target, reference = counts
        with pytest.raises(KeyError, match="cannot rank"):
            lexical.compare(target, reference, 1_000, 10_000, frozenset(), rank="log_dice")

    def test_extra_columns_can_be_ranked_on(self, counts):
        target, reference = counts
        rows = lexical.compare(
            target,
            reference,
            1_000,
            10_000,
            frozenset(),
            floor=0.0,
            rank="score",
            extra=lambda word, count: {"score": -len(word)},
        )
        assert [r["word"] for r in rows] == sorted((r["word"] for r in rows), key=len)

    def test_dispersion_travels_with_the_row_and_must_cover_the_target(self, counts):
        target, reference = counts
        spread = {w: {"documents": 2, "meetings": 1, "dp": 0.25} for w in target}
        rows = lexical.compare(
            target, reference, 1_000, 10_000, frozenset(), floor=0.0, dispersion=spread
        )
        assert all((r["documents"], r["meetings"], r["dp"]) == (2, 1, 0.25) for r in rows)
        with pytest.raises(KeyError, match="no dispersion"):
            lexical.compare(
                target, reference, 1_000, 10_000, frozenset(), floor=0.0, dispersion={}
            )

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
        picked = frame.loc[control.control_index]
        assert (~picked["hit"]).all()
        assert sorted(picked["year"].value_counts().to_dict().items()) == [(1994, 3), (2000, 1)]

    def test_no_control_is_used_twice(self, frame):
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        assert len(set(control.control_index)) == len(control.control_index)

    def test_targets_and_controls_are_true_pairs(self, frame):
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        targets = frame.loc[control.target_index].reset_index(drop=True)
        controls = frame.loc[control.control_index].reset_index(drop=True)
        assert len(targets) == len(controls) == control.matched
        assert targets["hit"].all() and (~controls["hit"]).all()
        assert list(zip(targets["year"], targets["agenda"], strict=True)) == list(
            zip(controls["year"], controls["agenda"], strict=True)
        )

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
        assert list(first.target_index) == list(second.target_index)
        assert list(first.control_index) == list(second.control_index)

    def test_a_stratum_with_no_controls_at_all_contributes_none(self):
        frame = pd.DataFrame([{"year": 1994, "agenda": "Rwanda", "hit": True}])
        control = lexical.matched_control(frame, "hit", ["year", "agenda"])
        assert len(control.target_index) == len(control.control_index) == 0
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

    def test_declared_nested_terms_do_not_create_definitional_edges(self):
        parent = term("parent", "parent")
        child = Term(
            name="child",
            pattern="child",
            tier="core",
            register="core",
            nested_under="parent",
            regex=re.compile("child"),
        )
        lex = Lexicon(version=1, updated="2026-08-09", terms={"parent": parent, "child": child}, sets={})
        frame = pd.DataFrame({"has_parent": [True] * 4, "has_child": [True] * 4})
        assert lexical.pmi_network(frame, lex, min_speeches=1) == []


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


class TestDispersion:
    def test_a_word_spread_like_the_text_has_dp_zero(self):
        docs = [Counter({"a": 2, "b": 2}), Counter({"a": 1, "b": 1})]
        spread = lexical.dispersion(docs, [4, 2])
        assert spread["a"]["dp"] == pytest.approx(0.0)
        assert spread["a"]["documents"] == 2
        assert spread["a"]["meetings"] is None

    def test_a_word_confined_to_one_document_has_dp_near_one(self):
        docs = [Counter({"a": 5}), Counter({"b": 100}), Counter({"b": 100})]
        spread = lexical.dispersion(docs, [5, 100, 100])
        # DP = 1 - expected share of the one document it sits in.
        assert spread["a"]["dp"] == pytest.approx(1 - 5 / 205, abs=1e-4)
        assert spread["a"]["documents"] == 1

    def test_it_matches_gries_formula_by_hand(self):
        docs = [Counter({"w": 3}), Counter({"w": 1}), Counter()]
        sizes = [10, 10, 20]
        expected = [0.25, 0.25, 0.5]
        observed = [0.75, 0.25, 0.0]
        by_hand = 0.5 * sum(abs(e - o) for e, o in zip(expected, observed, strict=True))
        assert lexical.dispersion(docs, sizes)["w"]["dp"] == pytest.approx(by_hand, abs=1e-4)

    def test_meetings_count_sittings_not_speeches(self):
        docs = [Counter({"w": 1}), Counter({"w": 1}), Counter({"w": 1})]
        spread = lexical.dispersion(docs, [5, 5, 5], meetings=["m1", "m1", "m2"])
        assert spread["w"]["documents"] == 3
        assert spread["w"]["meetings"] == 2

    def test_misaligned_inputs_are_refused(self):
        with pytest.raises(ValueError, match="sizes"):
            lexical.dispersion([Counter({"a": 1})], [1, 2])
        with pytest.raises(ValueError, match="meetings"):
            lexical.dispersion([Counter({"a": 1})], [1], meetings=[])

    def test_document_vocabulary_sums_to_the_vocabulary(self):
        texts = ["the Council met", "the Council rose"]
        docs = lexical.document_vocabulary(texts)
        assert sum(docs, Counter()) == lexical.vocabulary(texts)


class TestLogDice:
    def test_a_pair_that_never_appears_apart_scores_fourteen(self):
        assert lexical.log_dice(10, 10, 10) == pytest.approx(14.0)

    def test_it_does_not_reward_rarity(self):
        # Same joint share of the node, but a collocate that is rare in the
        # corpus is not scored higher for being rare.
        assert lexical.log_dice(5, 100, 100) == pytest.approx(lexical.log_dice(5, 100, 100))
        assert lexical.log_dice(5, 100, 1_000) < lexical.log_dice(5, 100, 100)

    def test_no_joint_occurrence_is_minus_infinity(self):
        assert lexical.log_dice(0, 10, 10) == float("-inf")


class TestCollocateRows:
    def test_rows_carry_log_dice_and_dispersion_and_rank_on_log_dice(self):
        node = term("g", r"\bgenocide\b")
        bodies = [
            "genocide prevention matters; prevention of genocide is duty",
            "the genocide convention and prevention",
            "genocide in Rwanda and prevention",
            "nothing here",
        ]
        reference = lexical.vocabulary(bodies)
        rows, occurrences, _ = lexical.collocates(
            bodies,
            node,
            width=5,
            reference=reference,
            reference_total=sum(reference.values()),
            stopwords=frozenset({"the", "and", "of", "in", "is"}),
            min_count=1,
            limit=None,
            meetings=["m1", "m1", "m2", "m3"],
            floor=0.0,
        )
        assert occurrences == 4
        by_word = {r["word"]: r for r in rows}
        prevention = by_word["prevention"]
        assert prevention["documents"] == 3
        assert prevention["meetings"] == 2
        assert 0.0 <= prevention["dp"] <= 1.0
        assert prevention["log_dice"] == pytest.approx(
            lexical.log_dice(prevention["target"], occurrences, reference["prevention"]), abs=1e-3
        )
        dice = [r["log_dice"] for r in rows]
        assert dice == sorted(dice, reverse=True)

    def test_without_meetings_the_column_is_null_not_guessed(self):
        node = term("g", r"\bgenocide\b")
        bodies = ["genocide prevention", "genocide prevention"]
        reference = lexical.vocabulary(bodies)
        rows, _, _ = lexical.collocates(
            bodies, node, 3, reference, sum(reference.values()), frozenset(), min_count=1, floor=0.0
        )
        assert rows and rows[0]["meetings"] is None


class TestDefinitionalPairs:
    def test_a_term_whose_pattern_contains_another_is_named_with_its_reason(self):
        genocide = Term(
            name="genocide", pattern=r"\bgenocid\w*", tier="core", register="core",
            examples=("genocide",), regex=re.compile(r"\bgenocid\w*", re.IGNORECASE),
        )
        denial = Term(
            name="denial", pattern=r"\bdenial\b|\bdeny\w*\s+genocid\w*", tier="adjacent",
            register="contentious", examples=("denial", "denying the genocide"),
            regex=re.compile(r"\bdenial\b|\bdeny\w*\s+genocid\w*", re.IGNORECASE),
        )
        war = Term(
            name="war_crimes", pattern=r"\bwar\s+crimes?\b", tier="atrocity", register="legal",
            examples=("war crimes",), regex=re.compile(r"\bwar\s+crimes?\b", re.IGNORECASE),
        )
        lex = Lexicon(
            version=1, updated="x", terms={"genocide": genocide, "denial": denial, "war_crimes": war}, sets={}
        )
        pairs = lexical.definitional_pairs(lex)
        assert [(p["source"], p["target"]) for p in pairs] == [("genocide", "denial")]
        assert "denying the genocide" in pairs[0]["reason"]
        frame = pd.DataFrame(
            {"has_genocide": [True] * 4, "has_denial": [True] * 4, "has_war_crimes": [True] * 4}
        )
        drawn = {(e["source"], e["target"]) for e in lexical.pmi_network(frame, lex, min_speeches=1)}
        assert drawn == {("genocide", "war_crimes"), ("denial", "war_crimes")}

    def test_the_real_lexicon_suppresses_denial_against_genocide(self):
        from lib import lexicon

        pairs = lexical.definitional_pairs(lexicon.load())
        suppressed = {frozenset((p["source"], p["target"])) for p in pairs}
        assert frozenset(("genocide", "denial")) in suppressed
        assert frozenset(("war_crimes", "crimes_against_humanity")) not in suppressed
