"""Where a model's evidence is in the speech, and whether it can be believed.

**Evidence is located, not trusted.** The model returns a quotation; this
module finds it in the speech and records the offsets, or records that it could
not. A quote that cannot be located is not an error — it is a measurement, and
`evidence_valid` is one of the numbers the pilot is evaluated on.

A `sentence-evidence` prompt asks for a first and last sentence number instead
of a quotation, which cannot be misquoted; :func:`_sentence_range` holds such
an answer inside the request's own numbering, and the span is then the
sentences' own.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Final

_WHITESPACE_RE = re.compile(r"\s+")


# --- Locating the evidence --------------------------------------------------


def _flatten(source: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed text, and where each character came from.

    `offsets[i]` is the index in `source` of `flat[i]`, so a span found in the
    flattened text maps straight back without a second search over the original.
    """
    flat: list[str] = []
    offsets: list[int] = []
    space = False
    for index, character in enumerate(source):
        if character.isspace():
            space = True
            continue
        if space and flat:
            flat.append(" ")
            offsets.append(index)
        space = False
        flat.append(character)
        offsets.append(index)
    return "".join(flat), offsets


#: Characters the record's typography and a model's transcription of it disagree
#: about, mapped to the plain form the two can be compared through.
#:
#: The Council's records are typeset with curly quotation marks and en dashes,
#: and a model asked for a verbatim span returns the passage as prose with the
#: typography normalised on the way out — so the quote is the right words and
#: not the right bytes, and an exact substring search finds nothing. NFKC folds
#: the ligatures, the non-breaking spaces and the compatibility forms; this
#: table folds what NFKC leaves alone, because Unicode holds that a curly
#: apostrophe and a straight one are different characters and is right to.
#:
#: Every replacement is one character wide, and the fold is applied character by
#: character rather than to the whole string, so a folded body indexes into the
#: same positions as the body it was folded from.
FOLDED: Final[dict[str, str]] = {
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark — the record's apostrophe
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",  # prime, which OCR reads an apostrophe as
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u201e": '"',
    "\u2033": '"',
    "\u00ab": '"',  # guillemets, from the French-language records
    "\u00bb": '"',
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash — the record's range and parenthetical dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\u00ad": "-",  # soft hyphen
}

#: Quotation marks a model wraps around the span it is reporting. Stripped from
#: the *ends of the quote* alone, in the relocating pass alone, and never from
#: the record: six of the eighteen quotes the two runs could not place are a
#: verbatim span with one quotation mark in front of it that the record does not
#: have there — the model has marked the passage as a quotation, which is a
#: statement about the passage and not part of it.
WRAPPERS: Final = "\"'\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a\u201e\u201a "


def _fold(character: str) -> str:
    """One character in the form two typographies can be compared through.

    NFKC, the table above, and lower case, in that order, and always exactly one
    character wide: a fold that changed the length would break the offset
    mapping :func:`_normalised` builds, and the offsets are what make a span
    found in the folded text a span in the real body. Anything NFKC or `lower`
    expands — the Turkish dotted capital, a handful of ligatures the corpus does
    not contain — keeps its original character rather than being expanded, which
    costs a match nobody has yet needed and cannot cost an offset.

    Lower case is here because two of the unplaced quotes differ from the record
    in exactly one letter's case, at the front, where the model has presented a
    mid-sentence clause as a sentence of its own.
    """
    folded = unicodedata.normalize("NFKC", FOLDED.get(character, character)).lower()
    return folded if len(folded) == 1 else character


def _normalised(source: str) -> tuple[str, list[int]]:
    """The folded, whitespace-collapsed text, and where each character came from.

    :func:`_flatten` with two more relaxations, each one a case the two
    committed runs actually produced:

    - every character folded by :func:`_fold`;
    - the space after a hyphen dropped, which closes the record's line-break
      hyphenation. The Council's records break words across lines and the OCR
      keeps the break, so the body holds `gender- based` and
      `Secretary- General's` where the model returns the word whole. The rule is
      applied to both sides, so a genuine dash before a word — the record's
      parenthetical em dash — is closed on both and still matches.

    `offsets[i]` is the index in `source` of the ith character of the result, as
    in :func:`_flatten`, so a span found here maps back without a second search.
    """
    text: list[str] = []
    offsets: list[int] = []
    space = False
    for index, character in enumerate(source):
        if character.isspace():
            space = True
            continue
        if space and text and text[-1] != "-":
            text.append(" ")
            offsets.append(index)
        space = False
        text.append(_fold(character))
        offsets.append(index)
    return "".join(text), offsets


def _matches(haystack: str, needle: str) -> list[int]:
    found = []
    position = haystack.find(needle)
    while position != -1:
        found.append(position)
        position = haystack.find(needle, position + 1)
    return found


def _spans(text: str, needle: str, offsets: list[int]) -> list[tuple[int, int]]:
    """Every match of `needle` in a normalised `text`, as spans in the original.

    One place rather than two, because the two normalising passes below differ
    only in how they normalise and a second copy of this arithmetic is a second
    chance to be off by one at the end of a span.
    """
    return [
        (offsets[position], offsets[position + len(needle) - 1] + 1)
        for position in _matches(text, needle)
    ]


def _choose(spans: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    """The span that best answers for the occurrence at `[start, end)`.

    Containing beats overlapping beats first-in-the-speech. A speaker who says
    "genocide" six times in one paragraph produces six occurrences whose evidence
    quotes may be identical strings; picking the first match every time would
    attach five of them to a passage they are not in.
    """
    for span in spans:
        if span[0] <= start and end <= span[1]:
            return span
    for span in spans:
        if span[0] < end and start < span[1]:
            return span
    return spans[0]


def locate_evidence(
    body: str, quote: str, occurrence_start: int, occurrence_end: int
) -> tuple[int | None, int | None, bool, bool]:
    """Where the model's quotation actually is, and whether it can be believed.

    Three passes, each admitting one more kind of difference between what the
    record says and what a model returned when asked to copy it:

    1. exact substring;
    2. runs of whitespace collapsed on both sides, which is what a model returns
       when it copies across a line break in the record;
    3. the relocating pass — :func:`_normalised` on both sides, and the model's
       own wrapping quotation marks stripped off the quote.

    The third is the review's (§4.5, item 4). Of the eighteen quotes the two
    committed runs could not place, ten are of this kind and none of them is a
    fabrication: six carry a leading quotation mark the record does not have
    there, two straddle a word the record hyphenates across a line break, and
    two differ from the record in the case of one letter. The remaining eight
    are three false positives answered with the literal string
    `not_applicable`, one quote found in a different sentence of the same
    speech, and four passages the model has genuinely paraphrased or spliced —
    and those must stay unplaced, which is what the relaxations are kept narrow
    for.

    A quote placed by the third pass is *relocated*, and the row carries the
    flag. Its offsets are as good as any other pass's; what the flag records is
    that the record's punctuation, hyphenation or capitalisation had to be
    ignored to find it, and a reader counting how far a run's evidence can be
    trusted is entitled to know how many.

    Each pass maps its match back through its own normalisation, so the offsets
    recorded are into the real body and never into a normalised copy.

    Returns `(start, end, valid, relocated)`. `valid` is true only when the
    located passage contains the occurrence's own span, which is the codebook's
    rule for a human evidence span too. A quote that is found in the wrong place
    still reports where it was found, marked invalid, because that is the more
    useful thing to look at; a quote that is nowhere in the speech returns
    `(None, None, False, False)`. Never raises: an unlocatable quote is a
    measurement of the run, not a fault in it.
    """
    if not quote.strip():
        return None, None, False, False

    relocated = False
    spans = [(position, position + len(quote)) for position in _matches(body, quote)]
    if not spans:
        flat, offsets = _flatten(body)
        needle = _WHITESPACE_RE.sub(" ", quote).strip()
        if not needle:
            return None, None, False, False
        spans = _spans(flat, needle, offsets)
    if not spans:
        folded, offsets = _normalised(body)
        needle, _ = _normalised(quote.strip(WRAPPERS))
        if not needle:
            return None, None, False, False
        spans = _spans(folded, needle, offsets)
        relocated = bool(spans)
    if not spans:
        return None, None, False, False

    start, end = _choose(spans, occurrence_start, occurrence_end)
    return start, end, start <= occurrence_start and occurrence_end <= end, relocated


# --- Evidence by sentence number -------------------------------------------


def _sentence_range(value: object, sentences: int) -> tuple[int, int]:
    """A first and last sentence number, inside the request's own numbering."""
    if not isinstance(value, Mapping) or set(value) != {"first", "last"}:
        raise ValueError(f"evidence_sentences must be {{first, last}}, not {value!r}.")
    first, last = value["first"], value["last"]
    if any(isinstance(item, bool) or not isinstance(item, int) for item in (first, last)):
        raise ValueError(f"Sentence numbers must be integers: {value!r}.")
    if not 1 <= first <= last <= sentences:
        raise ValueError(f"Sentences {first}-{last} are outside 1-{sentences} or reversed.")
    return first, last
