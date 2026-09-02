"""The frame codebook, its precedence, and the morphological split.

Two kinds of test live here. The first is the ordinary kind: a construction
taken from the genre goes in and the frame it should be filed under comes out.
The second is the one that keeps the codebook honest — every frame's documented
example is re-classified through the same code path the pipeline uses, so a
pattern edited without its gloss and its example fails here rather than shipping
a table whose column headings no longer describe its contents.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from lib import node_frames


def window(sentence: str) -> str:
    """A window built round the first `genocid…` in a sentence.

    Exactly what the step does, minus the corpus: the classifier never sees a
    sentence, only a marked window, and a test that fed it a bare string would
    be testing something the pipeline does not run.
    """
    match = re.search(r"genocid\w*", sentence, re.IGNORECASE)
    assert match, f"no node in {sentence!r}"
    return node_frames.window(
        sentence[: match.start()], match.group(), sentence[match.end() :]
    )


def frame_of(sentence: str) -> str:
    return node_frames.classify(window(sentence))


class TestCodebookIntegrity:
    def test_every_pattern_compiles(self):
        for frame in node_frames.CODEBOOK:
            re.compile(frame.pattern, re.IGNORECASE)
            if frame.cased:
                re.compile(frame.cased)

    def test_names_are_unique_and_do_not_collide_with_the_residue(self):
        names = [frame.name for frame in node_frames.CODEBOOK]
        assert len(names) == len(set(names))
        assert node_frames.UNFRAMED not in names

    def test_frame_names_are_the_codebook_plus_the_residue(self):
        assert node_frames.FRAME_NAMES[-1] == node_frames.UNFRAMED
        assert len(node_frames.FRAME_NAMES) == len(node_frames.CODEBOOK) + 1

    @pytest.mark.parametrize("frame", node_frames.CODEBOOK, ids=lambda f: f.name)
    def test_the_documented_example_lands_in_its_own_frame(self, frame):
        """The codebook's examples are attested, and they are also the test set.

        Each was copied out of `data/derived/kwic/genocide.json` with the line it
        came from recorded beside it. The corpus is not in the checkout, so the
        line id cannot be resolved here; what can be checked, and is what matters
        for the counts, is that the quoted construction still reaches the frame
        it is filed under after every later pattern edit.
        """
        assert frame_of(frame.example) == frame.name

    def test_every_frame_carries_a_gloss_and_an_example_line(self):
        for frame in node_frames.CODEBOOK:
            assert frame.gloss.endswith(".")
            assert re.match(r"^UNSC_\d{4}_", frame.example_id), frame.name
            assert "#" in frame.example_id

    def test_codebook_rows_number_the_precedence_from_one(self):
        rows = node_frames.codebook_rows()
        assert [row["precedence"] for row in rows] == list(range(1, len(rows) + 1))
        assert [row["frame"] for row in rows] == [f.name for f in node_frames.CODEBOOK]


class TestWindow:
    def test_the_node_is_marked_and_padded(self):
        assert node_frames.window("the crime of", "genocide", "was") == (
            f"the crime of {node_frames.NODE_OPEN}genocide{node_frames.NODE_CLOSE} was"
        )

    def test_a_guillemet_in_the_context_cannot_forge_a_boundary(self):
        """The markers are the only thing telling a pattern where the node is."""
        built = node_frames.window(f"acts of {node_frames.NODE_CLOSE}", "genocide", "")
        assert built.count(node_frames.NODE_OPEN) == 1
        assert built.count(node_frames.NODE_CLOSE) == 1

    def test_window_at_reads_the_span_out_of_a_body(self):
        body = "The Council condemned the genocide in Rwanda."
        start = body.index("genocide")
        built = node_frames.window_at(body, start, start + len("genocide"))
        assert f"{node_frames.NODE_OPEN}genocide{node_frames.NODE_CLOSE}" in built
        assert node_frames.classify(built) == "named_case"

    def test_line_breaks_are_flattened_as_the_concordance_flattens_them(self):
        body = "responsible for\ngenocide"
        start = body.index("genocide")
        built = node_frames.window_at(body, start, start + len("genocide"))
        assert "\n" not in built
        assert node_frames.classify(built) == "perpetration"


class TestFrames:
    @pytest.mark.parametrize(
        ("sentence", "expected"),
        [
            # Citation before anything it would otherwise look like: the treaty
            # title contains both "prevention of" and "the crime of".
            (
                "the Convention on the Prevention and Punishment of the Crime of Genocide",
                "legal_instrument",
            ),
            ("the Special Adviser on the Prevention of Genocide", "mandate_or_office"),
            ("the Office on Genocide Prevention", "mandate_or_office"),
            # Footing.
            ('the term "genocide" might be applicable', "distancing"),
            ("the so-called genocide in Xinjiang", "distancing"),
            ("allegations of genocide made against my country", "distancing"),
            ("those events amount to genocide", "qualification"),
            ("what is happening there is genocide", "qualification"),
            ("indicted for the crime of genocide", "crime_of"),
            ("acts of genocide have been committed", "acts_of"),
            ("the inference of genocidal intent", "intent_or_definition"),
            ("genocide denial and the glorification of war criminals", "denial_or_ideology"),
            ("the genocide occurred in Rwanda", "occurrence"),
            # Catalogue.
            ("war crimes, crimes against humanity and genocide", "atrocity_triad"),
            ("genocide, war crimes and ethnic cleansing", "atrocity_triad"),
            # Modality and role.
            ("the risk of genocide is rising", "risk_or_threat"),
            ("our obligation to prevent genocide", "prevention"),
            ("the twentieth anniversary of the genocide", "commemoration"),
            ("convicted of genocide by the Tribunal", "accountability"),
            ("genocide fugitives still at large", "accountability"),
            ("those responsible for genocide", "perpetration"),
            ("a policy of genocide", "perpetration"),
            # Bare nominal.
            ("genocide against the Tutsi", "directed_against"),
            ("the 1994 genocide in Rwanda", "named_case"),
        ],
    )
    def test_a_construction_reaches_its_frame(self, sentence, expected):
        assert frame_of(sentence) == expected

    def test_an_occurrence_no_pattern_reaches_is_unframed(self):
        assert frame_of("aggression and genocide are two powerful words") == "unframed"

    def test_the_residue_is_not_silently_dropped(self):
        assert node_frames.matches(window("aggression and genocide")) == ()


class TestPrecedence:
    def test_the_first_frame_in_codebook_order_wins(self):
        sentence = "the prevention of the crime of genocide, war crimes and ethnic cleansing"
        found = node_frames.matches(window(sentence))
        assert len(found) > 1
        assert node_frames.classify(window(sentence)) == found[0]

    def test_matches_are_returned_in_codebook_order(self):
        order = [frame.name for frame in node_frames.CODEBOOK]
        found = node_frames.matches(
            window("acts of genocide, war crimes and crimes against humanity")
        )
        assert list(found) == sorted(found, key=order.index)

    def test_a_title_is_not_counted_as_prevention(self):
        """Why citation is tier one: the office would otherwise fill that frame."""
        sentence = "the Special Adviser on the Prevention of Genocide briefed the Council"
        assert "prevention" in node_frames.matches(window(sentence))
        assert node_frames.classify(window(sentence)) == "mandate_or_office"

    def test_a_hedge_survives_the_catalogue(self):
        sentence = "alleged acts of genocide, war crimes or crimes against humanity"
        assert node_frames.classify(window(sentence)) == "distancing"


class TestGapDoesNotCrossASentence:
    def test_a_cue_in_the_previous_sentence_does_not_frame_this_one(self):
        assert frame_of("brought to justice. Genocide and other grave breaches") != (
            "accountability"
        )

    def test_a_cue_in_the_same_sentence_still_does(self):
        assert frame_of("impunity for genocide") == "accountability"


class TestMorphology:
    @pytest.mark.parametrize(
        ("form", "expected"),
        [
            ("genocide", "noun"),
            ("Genocide", "noun"),
            ("genocides", "noun"),
            ("genocidal", "adjective"),
            ("genocidally", "adjective"),
            ("genocidaire", "perpetrator_noun"),
            ("genocidaires", "perpetrator_noun"),
            # An OCR spelling the corpus actually carries once, in a 1992
            # Venezuelan intervention. It is reported, not reassigned.
            ("genocida", "other"),
        ],
    )
    def test_a_form_falls_into_its_category(self, form, expected):
        assert node_frames.morphology(form) == expected

    def test_the_perpetrator_noun_is_tested_before_the_adjective(self):
        assert node_frames.morphology("genocidaire") != "adjective"

    def test_surrounding_space_and_case_do_not_matter(self):
        assert node_frames.morphology("  Genocidaires ") == "perpetrator_noun"

    def test_every_category_is_declared(self):
        for form in ("genocide", "genocidal", "genocidaires", "genocida"):
            assert node_frames.morphology(form) in node_frames.FORMS


def occurrences(rows: list[dict]) -> pd.DataFrame:
    """The frame `17_frames.py` hands the aggregation, minus the corpus.

    One row per match, with the columns the step writes: the classification, the
    year it fell in, the meeting it was spoken in, and the speaker group.
    """
    return pd.DataFrame(rows)


class TestShareBlock:
    def test_every_frame_is_written_even_at_zero(self):
        rows = node_frames.share_block({"prevention": 3}, 10, minimum=1)
        assert [row["frame"] for row in rows] == list(node_frames.FRAME_NAMES)
        assert all("share" in row for row in rows)

    def test_the_shares_are_a_share_of_the_slice(self):
        rows = {
            row["frame"]: row
            for row in node_frames.share_block({"prevention": 3, "unframed": 7}, 10, minimum=1)
        }
        assert rows["prevention"]["share"] == pytest.approx(0.3)
        assert rows["unframed"]["share"] == pytest.approx(0.7)

    def test_the_interval_brackets_the_share_and_is_wilson(self):
        row = next(
            row
            for row in node_frames.share_block({"prevention": 3}, 10, minimum=1)
            if row["frame"] == "prevention"
        )
        assert row["share_low"] < row["share"] < row["share_high"]
        # Wilson at 3/10: [0.108, 0.603]. Wald would run to 0.584 and, at the
        # zero cell below, below nothing at all.
        assert row["share_low"] == pytest.approx(0.1078, abs=5e-4)
        assert row["share_high"] == pytest.approx(0.6032, abs=5e-4)

    def test_a_zero_cell_keeps_a_bounded_interval(self):
        row = next(
            row
            for row in node_frames.share_block({"prevention": 3}, 10, minimum=1)
            if row["frame"] == "distancing"
        )
        assert row["occurrences"] == 0
        assert row["share_low"] == 0.0
        assert row["share_high"] > 0

    def test_below_the_minimum_the_counts_stay_and_the_shares_go(self):
        rows = node_frames.share_block({"prevention": 3}, 10, minimum=40)
        row = next(row for row in rows if row["frame"] == "prevention")
        assert row["occurrences"] == 3
        assert row["share"] is None and row["share_low"] is None and row["share_high"] is None

    def test_matched_is_written_only_when_it_was_computed(self):
        assert "matched" not in node_frames.share_block({"prevention": 1}, 1, minimum=1)[0]
        rows = node_frames.share_block(
            {"prevention": 1}, 1, minimum=1, matched={"prevention": 4}
        )
        assert next(row for row in rows if row["frame"] == "prevention")["matched"] == 4


class TestSlicesAndYears:
    @pytest.fixture
    def frame(self):
        return occurrences(
            [
                {"frame": "prevention", "year": 2014, "meeting_symbol": "S/PV.1", "group": "P5"},
                {"frame": "prevention", "year": 2014, "meeting_symbol": "S/PV.1", "group": "P5"},
                {"frame": "unframed", "year": 2014, "meeting_symbol": "S/PV.1", "group": "E10"},
                {"frame": "prevention", "year": 2015, "meeting_symbol": "S/PV.2", "group": "E10"},
            ]
        )

    def test_slices_are_largest_first_and_ties_break_on_the_name(self, frame):
        rows = node_frames.slice_rows(frame, frame["group"], minimum=1)
        assert [(row["member"], row["occurrences"]) for row in rows] == [("E10", 2), ("P5", 2)]

    def test_a_thin_slice_is_marked_insufficient_but_still_counted(self, frame):
        rows = node_frames.slice_rows(frame, frame["group"], minimum=40)
        assert all(row["sufficient"] is False for row in rows)
        assert sum(row["occurrences"] for row in rows) == len(frame)

    def test_the_annual_block_covers_every_year_and_every_frame(self, frame):
        annual = node_frames.annual_block(frame, minimum=1)
        assert annual["years"] == [2014, 2015]
        assert annual["occurrences"] == [3, 1]
        assert set(annual["frames"]) == set(node_frames.FRAME_NAMES)
        assert annual["frames"]["prevention"]["occurrences"] == [2, 1]
        assert annual["frames"]["prevention"]["share"] == pytest.approx([2 / 3, 1.0])

    def test_a_year_under_the_minimum_is_withheld_not_dropped(self, frame):
        annual = node_frames.annual_block(frame, minimum=3)
        assert annual["years"] == [2014, 2015]
        assert annual["frames"]["prevention"]["occurrences"] == [2, 1]
        assert annual["frames"]["prevention"]["share"] == [pytest.approx(2 / 3), None]


class TestPeriodLabel:
    @pytest.mark.parametrize(
        ("year", "expected"),
        [
            (1992, "1992-1999"),
            (1999, "1992-1999"),
            (2000, "2000-2007"),
            (2023, "2016-2023"),
        ],
    )
    def test_a_year_falls_in_its_block(self, year, expected):
        assert node_frames.period_label(year, 1992, 8) == expected


class TestShareChangePoints:
    def _corpus(self, early: int, late: int) -> pd.DataFrame:
        """Twelve years of one meeting each, `early` then `late` hits of ten."""
        rows = []
        for offset in range(12):
            hits = early if offset < 6 else late
            for position in range(10):
                rows.append(
                    {
                        "frame": "prevention" if position < hits else "unframed",
                        "year": 1992 + offset,
                        "meeting_symbol": f"S/PV.{offset}",
                    }
                )
        return pd.DataFrame(rows)

    def test_only_frames_above_the_minimum_are_tested(self):
        corpus = self._corpus(2, 8)
        tested, _ = node_frames.share_change_points(
            corpus,
            node_frames.annual_block(corpus, minimum=1),
            minimum=1_000,
            trials=20,
            seed=1,
            alpha=0.05,
        )
        assert tested == []

    def test_the_level_is_corrected_across_the_frames_tested(self):
        corpus = self._corpus(2, 8)
        tested, adjusted = node_frames.share_change_points(
            corpus,
            node_frames.annual_block(corpus, minimum=1),
            minimum=10,
            trials=20,
            seed=1,
            alpha=0.05,
        )
        assert {row["frame"] for row in tested} == {"prevention", "unframed"}
        assert adjusted == pytest.approx(0.025)

    def test_a_real_step_is_found_where_it_was_put(self):
        corpus = self._corpus(2, 8)
        tested, _ = node_frames.share_change_points(
            corpus,
            node_frames.annual_block(corpus, minimum=1),
            minimum=10,
            trials=200,
            seed=20_260_902,
            alpha=0.05,
        )
        found = next(row for row in tested if row["frame"] == "prevention")["result"]
        assert found["label"] == "1998"
        assert found["before"] == pytest.approx(0.2)
        assert found["after"] == pytest.approx(0.8)
        assert found["null"] == "meeting_block_permutation"

    def test_the_meeting_is_the_exchangeable_unit(self):
        """Ten occurrences in one debate are one draw, not ten.

        What is asserted is the arrangement, not a number: the null that decides
        `accepted` is the one that moves whole meetings, there is one block per
        meeting rather than one per occurrence, and the older independent-draw
        p-value is kept beside it so the gap between the two can be read. The
        size of that gap on real data is what `04_series.py` reports and
        `docs/VALIDATION.md` records; on twelve clean meetings both nulls sit on
        the floor of what 200 permutations can resolve.
        """
        corpus = self._corpus(2, 8)
        tested, _ = node_frames.share_change_points(
            corpus,
            node_frames.annual_block(corpus, minimum=1),
            minimum=10,
            trials=200,
            seed=20_260_902,
            alpha=0.05,
        )
        found = next(row for row in tested if row["frame"] == "prevention")["result"]
        assert found["blocks"] == 12
        assert found["null"] == "meeting_block_permutation"
        assert found["p_value_independent"] is not None


class TestCrosstab:
    @pytest.fixture
    def frame(self):
        return occurrences(
            [
                {"frame": "commemoration", "occurrence_id": "a"},
                {"frame": "commemoration", "occurrence_id": "b"},
                {"frame": "distancing", "occurrence_id": "c"},
            ]
        )

    def test_a_single_label_field_sums_to_the_frame(self, frame):
        labelled = pd.DataFrame(
            [
                {"occurrence_id": "a", "stance": "asserts"},
                {"occurrence_id": "b", "stance": "asserts"},
                {"occurrence_id": "c", "stance": "rejects_or_denies"},
            ]
        )
        table = node_frames.crosstab(frame, labelled, "stance", multi=False)
        row = next(r for r in table["rows"] if r["frame"] == "commemoration")
        assert row["occurrences"] == row["row_total"] == 2
        assert row["modal_label"] == "asserts"
        assert row["modal_share"] == pytest.approx(1.0)

    def test_a_multi_label_field_can_exceed_the_frame_and_says_so(self, frame):
        labelled = pd.DataFrame(
            [
                {"occurrence_id": "a", "function": "commemoration|accountability"},
                {"occurrence_id": "b", "function": "commemoration"},
                {"occurrence_id": "c", "function": "accusation_or_qualification"},
            ]
        )
        table = node_frames.crosstab(frame, labelled, "function", multi=True)
        row = next(r for r in table["rows"] if r["frame"] == "commemoration")
        assert row["occurrences"] == 2
        assert row["row_total"] == 3

    def test_the_label_vocabulary_is_a_list_not_a_key_set(self, frame):
        labelled = pd.DataFrame([{"occurrence_id": "a", "stance": "asserts"}])
        table = node_frames.crosstab(frame, labelled, "stance", multi=False)
        row = table["rows"][0]
        assert isinstance(row["counts"], list)
        assert {"label", "occurrences"} == set(row["counts"][0])

    def test_an_occurrence_the_run_never_reached_is_left_out(self, frame):
        labelled = pd.DataFrame([{"occurrence_id": "a", "stance": "asserts"}])
        table = node_frames.crosstab(frame, labelled, "stance", multi=False)
        row = next(r for r in table["rows"] if r["frame"] == "distancing")
        assert row["occurrences"] == 0
        assert row["modal_label"] is None
