"""Sentence segmentation and concordance extraction.

The sentence is what a researcher will paste into a paper, and the offsets are
what the reader view highlights, so both are checked against cases taken from
the genre rather than from general English: `Mr.`, `para.`, `S/PV.3453`,
`resolution 955 (1994).`, and initials in a name.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from lib import kwic
from lib.lexicon import Term

ADDRESS = "Mr. SMITH (United Kingdom): "


def term(name: str = "genocide", pattern: str = r"\bgenocid\w*") -> Term:
    return Term(
        name=name,
        pattern=pattern,
        tier="core",
        register="core",
        regex=re.compile(pattern, re.IGNORECASE),
    )


def speech(body: str, **overrides) -> pd.DataFrame:
    """One speech, with the form of address prefixed as the corpus has it."""
    row = {
        "filename": "UNSC_1994_SPV.3400_spch0007.txt",
        "meeting_symbol": "S/PV.3400",
        "date": pd.Timestamp("1994-06-08"),
        "country_org": "Rwanda",
        "iso3": "RWA",
        "speaker_group": "E10",
        "participanttype": "Mentioned",
        "agenda_item_manual": "Rwanda",
        "text": ADDRESS + body,
        "body_start": len(ADDRESS),
        "has_genocide": True,
    }
    return pd.DataFrame([row | overrides])


class TestSentenceSpans:
    def test_a_plain_pair_splits(self):
        source = "The Council met. It adjourned."
        assert [source[a:b] for a, b in kwic.sentence_spans(source)] == [
            "The Council met.",
            "It adjourned.",
        ]

    @pytest.mark.parametrize(
        "source",
        [
            "Mr. President made the point clearly.",
            "See para. 12 of the report.",
            "The U.S. representative agreed with that.",
            "Mr. B. Traore spoke after the vote.",
            "Resolution 955 of 8 Nov. 1994 established it.",
            "It is document No. 4 in the annex.",
        ],
        ids=["title", "paragraph", "acronym", "initial", "month", "number"],
    )
    def test_an_abbreviation_does_not_end_a_sentence(self, source):
        assert len(kwic.sentence_spans(source)) == 1

    def test_a_document_symbol_does_not_end_a_sentence(self):
        """`S/PV.3453` has a period followed by a digit, which is not a
        boundary, but the symbol is common enough to be worth asserting."""
        source = "As recorded in S/PV.3453 the Council was seized of the matter."
        assert len(kwic.sentence_spans(source)) == 1

    def test_a_closing_bracket_before_the_stop_still_ends_it(self):
        source = "It adopted resolution 955 (1994). The Tribunal followed."
        assert [source[a:b] for a, b in kwic.sentence_spans(source)] == [
            "It adopted resolution 955 (1994).",
            "The Tribunal followed.",
        ]

    def test_a_quotation_closing_a_sentence_stays_with_it(self):
        """The closing quote belongs to the sentence it closes, not to the next
        one — it is part of what would be quoted."""
        source = 'She said "never again." The Council listened.'
        start, end = kwic.sentence_spans(source)[0]
        assert source[start:end] == 'She said "never again."'

    def test_a_question_and_an_exclamation_both_end_sentences(self):
        source = "Was it genocide? It was! Nobody disputes that."
        assert len(kwic.sentence_spans(source)) == 3

    def test_spans_exclude_the_whitespace_between_sentences(self):
        source = "One.   Two."
        assert kwic.sentence_spans(source) == [(0, 4), (7, 11)]

    def test_text_with_no_terminal_punctuation_is_one_span(self):
        assert kwic.sentence_spans("an unterminated fragment") == [(0, 24)]

    def test_empty_text_has_no_spans(self):
        assert kwic.sentence_spans("") == []


class TestSentenceAt:
    def test_it_returns_the_sentence_containing_the_position(self):
        source = "The first one. The second mentions genocide. The third."
        assert kwic.sentence_at(source, source.index("genocide")) == (
            "The second mentions genocide."
        )

    def test_line_breaks_are_flattened(self):
        """A concordance line and a quotation both want one line of text; the
        offsets into the source are unaffected."""
        assert kwic.sentence_at("A broken\nline here.", 2) == "A broken line here."

    def test_a_position_past_the_end_falls_back_to_the_last_sentence(self):
        source = "One. Two."
        assert kwic.sentence_at(source, 999) == "Two."


class TestExtract:
    def test_offsets_point_into_the_whole_text_not_the_body(self):
        """The reader view highlights against the full speech, form of address
        included. An offset measured from the body would land 28 characters
        early on every line in the corpus."""
        frame = speech("We must call the genocide by its name.")
        line = next(kwic.extract(frame, term()))
        assert frame.loc[0, "text"][line.start : line.end] == "genocide"

    def test_matching_ignores_the_form_of_address(self):
        """03 counts on the body. If extraction counted on the raw text the two
        would disagree, and a reader would have no way to tell which was right."""
        frame = speech("Nothing here.", text="Mr. GENOCIDE (Rwanda): Nothing here.")
        frame.loc[0, "body_start"] = len("Mr. GENOCIDE (Rwanda): ")
        assert list(kwic.extract(frame, term())) == []

    def test_occurrences_are_numbered_within_the_speech(self):
        frame = speech("Genocide is genocide, whatever the genocidal intent.")
        ids = [line.id for line in kwic.extract(frame, term())]
        assert ids == [
            "UNSC_1994_SPV.3400_spch0007#1",
            "UNSC_1994_SPV.3400_spch0007#2",
            "UNSC_1994_SPV.3400_spch0007#3",
        ]

    def test_each_line_carries_its_sentence_and_its_snippet(self):
        frame = speech("A first sentence. This one names genocide. A third.")
        line = next(kwic.extract(frame, term()))
        assert line.kw == "genocide"
        assert line.sent == "This one names genocide."
        # The snippet crosses the sentence boundary on purpose: scanning wants
        # the surrounding run of text, quoting wants the sentence.
        assert line.left == "A first sentence. This one names"
        assert line.right == ". A third."

    def test_the_window_is_bounded_by_the_requested_width(self):
        frame = speech("x " * 400 + "genocide" + " y" * 400)
        line = next(kwic.extract(frame, term(), width=40))
        assert len(line.left) <= 40 and len(line.right) <= 40

    def test_metadata_travels_with_every_line(self):
        line = next(kwic.extract(speech("The genocide of 1994."), term()))
        assert (line.spv, line.date, line.country, line.iso3) == (
            "S/PV.3400",
            "1994-06-08",
            "Rwanda",
            "RWA",
        )

    def test_a_missing_iso3_becomes_null_not_nan(self):
        """json.dumps writes NaN, which is not valid JSON and which no browser
        will parse."""
        frame = speech("The genocide of 1994.", iso3=None)
        assert next(kwic.extract(frame, term())).iso3 is None

    def test_a_frame_without_the_needed_columns_is_refused(self):
        with pytest.raises(KeyError, match="extract\\(\\) needs"):
            list(kwic.extract(pd.DataFrame({"filename": ["a.txt"]}), term()))


class TestOffsets:
    """What the reader view highlights from. These have to agree with what
    `extract` counted, or the speech would light up in places the concordance
    does not list."""

    def test_spans_are_whole_text_offsets(self):
        source = ADDRESS + "The genocide of 1994."
        found = kwic.offsets(source, len(ADDRESS), [term()])
        start, end = found["genocide"][0]
        assert source[start:end] == "genocide"

    def test_the_form_of_address_is_not_searched(self):
        source = "Mr. GENOCIDE (Rwanda): Nothing here."
        assert kwic.offsets(source, len("Mr. GENOCIDE (Rwanda): "), [term()]) == {}

    def test_a_term_with_no_match_is_absent_not_empty(self):
        """An empty list per unused term would be 21 wasted keys on every one of
        106,302 speeches."""
        found = kwic.offsets(ADDRESS + "Nothing here.", len(ADDRESS), [term()])
        assert found == {}

    def test_every_occurrence_is_recorded(self):
        source = ADDRESS + "Genocide, genocide, and genocidal intent."
        assert len(kwic.offsets(source, len(ADDRESS), [term()])["genocide"]) == 3

    def test_terms_are_keyed_separately(self):
        source = ADDRESS + "genocide and war crimes"
        found = kwic.offsets(
            source, len(ADDRESS), [term(), term("war_crimes", r"\bwar\s+crimes?\b")]
        )
        assert sorted(found) == ["genocide", "war_crimes"]

    def test_offsets_agree_with_what_extract_counts(self):
        """The two run the same regexes over the same body; if they ever
        disagreed, the highlight and the concordance would tell different
        stories about the same speech."""
        body = "Genocide here, and genocidal intent there."
        frame = speech(body)
        counted = [(line.start, line.end) for line in kwic.extract(frame, term())]
        found = kwic.offsets(ADDRESS + body, len(ADDRESS), [term()])["genocide"]
        assert counted == [tuple(span) for span in found]
