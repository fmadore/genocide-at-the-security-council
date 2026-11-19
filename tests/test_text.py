"""The form of address, the delivery language, and case collisions.

The cases here are all real strings taken from the corpus, including the OCR
damage: they are the reason each branch of scripts/lib/text.py exists.
"""

from __future__ import annotations

import pandas as pd
import pytest
from lib import text


class TestSplitAddress:
    @pytest.mark.parametrize(
        "speech, address",
        [
            ("The President: I welcome…", "The President:"),
            (
                "Mr. Levitte (France) (spoke in French): Je remercie…",
                "Mr. Levitte (France) (spoke in French):",
            ),
            ("The PRESIDENT (interpretation from Spanish): Doy…", "The PRESIDENT (interpretation from Spanish):"),
            ("The Secretary-General: Thank you…", "The Secretary-General:"),
            ("The Deputy Secretary-General: I thank…", "The Deputy Secretary-General:"),
            ("Judge Meron (spoke in French): It is always…", "Judge Meron (spoke in French):"),
            ("President Chiluba: First of all…", "President Chiluba:"),
            ("Sir Jeremy Greenstock (United Kingdom): We welcome…", "Sir Jeremy Greenstock (United Kingdom):"),
            ("Mrs. Mele Colifa (Equatorial Guinea) (spoke in Spanish): Gracias…", "Mrs. Mele Colifa (Equatorial Guinea) (spoke in Spanish):"),
            # OCR fuses the honorific to the name.
            ("Mr.Elarahy: I should like…", "Mr.Elarahy:"),
            ("ArchbishopChullikatt: My delegation…", "ArchbishopChullikatt:"),
        ],
    )
    def test_recognises_real_forms_of_address(self, speech, address):
        assert text.split_address(speech).address == address

    def test_body_starts_after_the_colon_and_whitespace(self):
        speech = "Mr. Valle (Brazil):   I thank the President."
        assert text.body_of(speech) == "I thank the President."

    @pytest.mark.parametrize(
        "speech",
        [
            "I thank the President for organizing today's important debate.",
            "We thank Special Envoy Martin Griffiths; the Office for the Coordination…",
            "Climate change is a complex phenomenon: it has many consequences.",
            "Mexico thanks the Niger for convening this debate.",
        ],
    )
    def test_leaves_continuation_speeches_untouched(self, speech):
        """About 5% of speeches open straight into prose. Truncating those
        would delete real words, so a miss must be a no-op."""
        split = text.split_address(speech)
        assert not split.matched
        assert split.body_start == 0
        assert text.body_of(speech) == speech

    def test_does_not_run_past_the_address(self):
        speech = "Mr. Smith (Canada): The genocide in Rwanda: a retrospective."
        assert text.split_address(speech).address == "Mr. Smith (Canada):"


class TestModalCase:
    def test_collapses_onto_the_most_frequent_spelling(self):
        values = pd.Series(
            ["The President"] * 5 + ["The PRESIDENT"] + ["Guest"] * 2
        )
        assert set(text.modal_case(values).unique()) == {"The President", "Guest"}

    def test_keeps_genuinely_distinct_labels_apart(self):
        values = pd.Series(["Rwanda", "Burundi", "Rwanda"])
        assert set(text.modal_case(values).unique()) == {"Rwanda", "Burundi"}

    def test_tolerates_missing_values(self):
        values = pd.Series(["Peacebuilding", None, "peacebuilding"])
        result = text.modal_case(values)
        assert result.iloc[0] == result.iloc[2] == "Peacebuilding"
        assert pd.isna(result.iloc[1])


class TestWindow:
    def test_splits_around_the_keyword_and_flattens_newlines(self):
        body = "the crime of\ngenocide was\ncommitted"
        left, keyword, right = text.window(body, 13, 21, width=40)
        assert keyword == "genocide"
        assert left == "the crime of"
        assert right == "was committed"

    def test_clips_at_the_start_of_the_text(self):
        left, keyword, _ = text.window("genocide happened", 0, 8, width=50)
        assert left == ""
        assert keyword == "genocide"


class TestNormaliseLineEndings:
    def test_converts_crlf_and_lone_cr(self):
        assert text.normalise_line_endings("a\r\nb\rc\nd") == "a\nb\nc\nd"


class TestSentenceBounds:
    """The evidence span the coding page records around a match."""

    def test_an_abbreviation_does_not_cut_the_sentence(self) -> None:
        body = "First point. Mr. Smith said the U.N. saw genocide in S/PV.3137 there. Next one."
        start = body.index("genocide")
        left, right = text.sentence_bounds(body, start, start + len("genocide"))
        assert body[left:right] == "Mr. Smith said the U.N. saw genocide in S/PV.3137 there."

    def test_the_span_stops_at_a_line_break(self) -> None:
        body = "A heading without a stop\nThe genocide was planned. Then more."
        start = body.index("genocide")
        left, right = text.sentence_bounds(body, start, start + 8)
        assert body[left:right] == "The genocide was planned."

    def test_a_match_across_two_sentences_takes_both(self) -> None:
        body = "One. It was a geno. Cide indeed. Three."
        start = body.index("geno")
        end = body.index("Cide") + 4
        left, right = text.sentence_bounds(body, start, end)
        assert body[left:right] == "It was a geno. Cide indeed."

    def test_the_span_always_holds_the_match(self) -> None:
        body = "genocide"
        assert text.sentence_bounds(body, 0, 8) == (0, 8)
        body = "Last words: genocide"
        assert text.sentence_bounds(body, 12, 20) == (0, 20)
