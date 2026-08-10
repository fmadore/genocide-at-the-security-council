"""Per-speaker matched keyness: the counting, the pairing and the two gates.

Three of these tests exist because the module makes a claim that is cheap to
make and expensive to be wrong about: that counting through the matrix gives
what `lexical.vocabulary` gives, that a factorised stratum partitions the corpus
exactly as the three columns it stands for do, and that a speaker below either
gate is written as null rather than left out.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest
from lib import keyness, lexical

CORPUS = [
    "The Council met to consider the situation in Rwanda.",
    "Rwanda thanks the Council for its attention to genocide.",
    "France welcomes the report and supports the French proposal.",
    "The situation in Rwanda remains grave, the Council notes.",
    "France believes the European Union must act.",
    "A short intervention.",
]


def frame(speakers: list[str], years: list[int], items: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country_org": speakers,
            "year": years,
            "agenda_item_manual": items,
            "speaker_group": ["E10"] * len(speakers),
            "text": CORPUS[: len(speakers)],
        }
    )


class TestDocumentTerms:
    def test_counting_agrees_with_the_function_05_counts_with(self):
        """The whole point of the matrix: same numbers, computed once."""
        matrix = keyness.build(CORPUS)
        whole = matrix.counter(list(range(len(CORPUS))))
        assert whole == lexical.vocabulary(CORPUS)

    def test_a_subset_is_the_sum_of_its_documents(self):
        matrix = keyness.build(CORPUS)
        rows = [0, 3]
        assert matrix.counter(rows) == lexical.vocabulary([CORPUS[0], CORPUS[3]])

    def test_an_empty_selection_counts_nothing(self):
        matrix = keyness.build(CORPUS)
        assert matrix.counter([]) == Counter()

    def test_the_matrix_knows_its_own_shape(self):
        matrix = keyness.build(CORPUS)
        assert matrix.documents == len(CORPUS)
        assert matrix.entries == sum(
            len(Counter(lexical.TOKEN_RE.findall(text.lower()))) for text in CORPUS
        )


class TestStrata:
    def test_the_code_partitions_exactly_as_the_columns_do(self):
        """The optimisation is only sound if it is the same partition.

        `matched_control` groups the corpus once per speaker per seed, and the
        code exists to make that cheap. A code that merged two strata would draw
        controls from the wrong debate and nothing in the output would say so.
        """
        table = frame(
            ["A", "B", "A", "B", "C", "C"],
            [1994, 1994, 1994, 2000, 2000, 2000],
            ["Rwanda", "Rwanda", "Bosnia", "Syria", "Syria", "Syria"],
        )
        codes = keyness.strata(table)
        by_code = table.groupby(codes, sort=True).groups
        by_columns = table.groupby(keyness.MATCH_ON, sort=True).groups
        assert sorted(sorted(v) for v in by_code.values()) == sorted(
            sorted(v) for v in by_columns.values()
        )

    def test_a_missing_agenda_item_is_a_stratum_and_not_a_hole(self):
        """Two unlabelled speeches are comparable to each other."""
        table = frame(["A", "B"], [1994, 1994], [None, None])
        codes = keyness.strata(table)
        assert codes.nunique() == 1

    def test_a_missing_item_is_not_the_same_stratum_as_a_labelled_one(self):
        table = frame(["A", "B"], [1994, 1994], [None, "Rwanda"])
        assert keyness.strata(table).nunique() == 2

    def test_it_says_which_column_is_missing(self):
        with pytest.raises(KeyError, match="speaker_group"):
            keyness.strata(pd.DataFrame({"year": [1994], "agenda_item_manual": ["x"]}))


class TestSelfReference:
    def test_a_word_from_the_speakers_own_name_is_caught(self):
        assert "federation" in keyness.self_reference("Russian Federation")
        assert "russian" in keyness.self_reference("Russian Federation")

    def test_a_demonym_outside_the_name_is_not(self):
        """Stated as a limit rather than discovered as a gap: an unmarked row
        is not a guarantee that the word is not self-reference."""
        assert "french" not in keyness.self_reference("France")


class TestSpeakerKeyness:
    @pytest.fixture
    def table(self):
        """Four speeches by A and four by others, in two comparable strata."""
        speakers = ["A", "B", "A", "B", "A", "C", "A", "C"]
        years = [1994, 1994, 1994, 1994, 2000, 2000, 2000, 2000]
        items = ["Rwanda"] * 4 + ["Syria"] * 4
        built = pd.DataFrame(
            {
                "country_org": speakers,
                "year": years,
                "agenda_item_manual": items,
                "speaker_group": ["E10"] * 8,
                "text": [
                    "genocide genocide prevention council",
                    "council report situation",
                    "genocide prevention council",
                    "council situation report",
                    "genocide prevention council",
                    "council report situation",
                    "genocide genocide prevention",
                    "council situation report",
                ],
            }
        )
        return built.assign(stratum=keyness.strata(built))

    def matrix(self, table):
        return keyness.build(table["text"])

    def test_a_speaker_is_compared_against_its_own_strata(self, table):
        matrix = self.matrix(table)
        block = keyness.speaker_keyness(
            table,
            matrix,
            "A",
            "stratum",
            matrix.counter(list(table.index)),
            int(table["text"].str.split().str.len().sum()),
            frozenset(),
            seed=1,
            minimum=1,
            min_coverage=0.0,
        )
        assert block["pairs"] == 4
        assert block["coverage"] == 1.0
        assert block["sufficient"] is True
        assert block["withheld_because"] == []
        words = [row["word"] for row in block["keywords"]]
        assert "genocide" in words

    def test_below_the_pair_minimum_every_key_is_present_and_null(self, table):
        """A missing key and a measured zero are indistinguishable downstream."""
        matrix = self.matrix(table)
        block = keyness.speaker_keyness(
            table,
            matrix,
            "A",
            "stratum",
            matrix.counter(list(table.index)),
            100,
            frozenset(),
            seed=1,
            minimum=99,
            min_coverage=0.0,
        )
        assert block["sufficient"] is False
        assert block["withheld_because"] == ["pairs"]
        assert block["keywords"] is None
        assert block["keywords_unmatched"] is None
        assert block["target_tokens"] is None
        # The evidence for the refusal is still published.
        assert block["pairs"] == 4
        assert block["held"] == 4

    def test_coverage_is_a_gate_of_its_own(self, table):
        """The UN Secretariat's case: pairs enough, record unrepresentative."""
        lonely = pd.concat(
            [table, table.assign(country_org="A", stratum=999, text="alone")],
            ignore_index=True,
        )
        matrix = keyness.build(lonely["text"])
        block = keyness.speaker_keyness(
            lonely,
            matrix,
            "A",
            "stratum",
            matrix.counter(list(lonely.index)),
            200,
            frozenset(),
            seed=1,
            minimum=1,
            min_coverage=0.9,
        )
        assert block["pairs"] >= 1
        assert block["withheld_because"] == ["coverage"]
        assert block["keywords"] is None

    def test_both_gates_are_named_when_both_close(self, table):
        matrix = self.matrix(table)
        block = keyness.speaker_keyness(
            table,
            matrix,
            "A",
            "stratum",
            matrix.counter(list(table.index)),
            100,
            frozenset(),
            seed=1,
            minimum=99,
            min_coverage=1.1,
        )
        assert block["withheld_because"] == ["pairs", "coverage"]

    def test_keywords_carry_the_self_reference_mark(self):
        """A speaker whose own name is one of the words it is key for."""
        built = pd.DataFrame(
            {
                # Six of each: `lexical.MIN_COUNT` drops a word under five
                # occurrences, so a smaller fixture would test the floor instead.
                "country_org": ["Utopia", "Elsewhere"] * 6,
                "year": [1994] * 12,
                "agenda_item_manual": ["Rwanda"] * 12,
                "speaker_group": ["E10"] * 12,
                "text": ["utopia utopia council genocide", "council report situation"] * 6,
            }
        )
        built = built.assign(stratum=keyness.strata(built))
        matrix = keyness.build(built["text"])
        block = keyness.speaker_keyness(
            built,
            matrix,
            "Utopia",
            "stratum",
            matrix.counter(list(built.index)),
            200,
            frozenset(),
            seed=1,
            minimum=1,
            min_coverage=0.0,
        )
        marked = {row["word"]: row["self_reference"] for row in block["keywords"]}
        assert marked["utopia"] is True
        assert marked["genocide"] is False
        # The mark travels with both readings, not only the matched one.
        assert all("self_reference" in row for row in block["keywords_unmatched"])

    def test_the_published_draw_is_inside_its_own_interval(self, table):
        """An interval drawn from other seeds can exclude the number beside it.

        The browser showed `+1.33 [+1.38, +1.53]` for a real row, which reads as
        an error and is not one — it was an interval over draws that excluded
        the published draw. The repetitions now start at `seed`.
        """
        matrix = self.matrix(table)
        block = keyness.speaker_keyness(
            table,
            matrix,
            "A",
            "stratum",
            matrix.counter(list(table.index)),
            100,
            frozenset(),
            seed=11,
            minimum=1,
            min_coverage=0.0,
            repetitions=4,
        )
        published = {row["word"]: row["log_ratio"] for row in block["keywords"]}
        for entry in block["stability"]["keyword_log_ratio"]:
            value = published[entry["word"]]
            # The observed range, not the percentiles: at ten draws p05 is
            # interpolated above the smallest value, so a published draw that is
            # the extreme of its own sample sits outside it. That is a property
            # of the quantile, which is why the view prints low/high.
            assert entry["low"] <= value <= entry["high"], entry["word"]
            assert entry["low"] <= entry["p05"]
            assert entry["p95"] <= entry["high"]

    def test_the_same_seed_gives_the_same_table(self, table):
        matrix = self.matrix(table)
        reference = matrix.counter(list(table.index))
        run = lambda: keyness.speaker_keyness(  # noqa: E731
            table,
            matrix,
            "A",
            "stratum",
            reference,
            100,
            frozenset(),
            seed=7,
            minimum=1,
            min_coverage=0.0,
        )
        assert run()["keywords"] == run()["keywords"]


class TestAgendaComposition:
    def test_shares_are_of_the_speakers_own_speeches(self):
        table = frame(
            ["A", "A", "A", "B"],
            [1994, 1994, 2000, 2000],
            ["Rwanda", "Rwanda", "Syria", "Syria"],
        )
        block = keyness.agenda_composition(table, "A")
        assert block["held"] == 3
        assert block["items"] == 2
        assert block["top"][0] == {"item": "Rwanda", "speeches": 2, "share": pytest.approx(0.6667)}

    def test_the_tail_is_summed_rather_than_dropped(self):
        table = frame(
            ["A"] * 4 + ["B"] * 2,
            [1994] * 6,
            ["one", "two", "three", "four", "five", "six"],
        )
        block = keyness.agenda_composition(table, "A", items=2)
        assert block["other"]["speeches"] == 2
        assert sum(row["share"] for row in block["top"]) + block["other"]["share"] == 1.0

    def test_an_unlabelled_item_is_named_rather_than_dropped(self):
        table = frame(["A", "A"], [1994, 1994], [None, "Rwanda"])
        block = keyness.agenda_composition(table, "A")
        assert {row["item"] for row in block["top"]} == {"(unlabelled)", "Rwanda"}
