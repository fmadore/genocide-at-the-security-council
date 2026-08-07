"""Concordance lines: keyword in context, and the sentence around it.

Two units per occurrence, because they answer different questions:

- a **±150-character window** with line breaks flattened, for scanning a
  thousand lines at once and seeing a pattern;
- the **full sentence**, for quoting in a paper.

Offsets are recorded against the *whole* speech text, not the body the match was
found in, so the reader view can highlight a match without re-running any regex
and without knowing where the form of address ended.

Sentence segmentation is rule-based rather than spaCy, which docs/PLAN.md §3.5
suggested. The genre is full of traps a general model has no particular
advantage on — `Mr.`, `No.`, `para.`, `U.S.`, `S/PV.7481`, `resolution 955
(1994).`, and initials like `Mr. B. Traoré` — and here the rules are visible,
unit-tested against those exact cases, and add nothing to install. If the
distribution of sentence lengths the note reports ever says otherwise, this is
one function to swap.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

import pandas as pd

from . import text as text_lib
from .lexicon import HAS, Term

#: Characters of context either side of the keyword in the display snippet.
WIDTH = 150

#: A sentence longer than this is almost certainly a segmentation failure or an
#: OCR-damaged run-on rather than a sentence. They are kept — truncating a unit
#: offered for quotation would be worse — but counted, so the note can say how
#: often it happens.
LONG_SENTENCE = 500

#: Words whose trailing period does not end a sentence. Lower-cased, with any
#: internal periods kept (`u.s`), because that is how :func:`_is_abbreviation`
#: reads the token back off the text.
ABBREVIATIONS = frozenset(
    {
        # People and offices
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "hon", "amb", "gen", "capt",
        # Reference apparatus, thick on the ground in a verbatim record
        "no", "nos", "art", "arts", "para", "paras", "pp", "p", "vol", "ch", "chap",
        "fig", "sect", "sec", "ibid", "op", "cit", "ed", "eds", "cf", "viz", "al",
        # Latin and general
        "e.g", "i.e", "etc", "approx", "incl", "min", "max", "est",
        # Bodies and companies
        "inc", "ltd", "co", "corp", "u.s", "u.n", "u.k", "a.m", "p.m",
        # Months
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sept", "sep", "oct", "nov", "dec",
    }
)

#: A candidate sentence end: terminal punctuation, any closing quotes or
#: brackets, whitespace, then something that could open a sentence.
#:
#: The OCR carries both straight and curly quotes, and the two are
#: indistinguishable in most editors, so the curly ones are named by code point
#: rather than typed into the character class.
_RIGHT_SINGLE, _RIGHT_DOUBLE = chr(0x2019), chr(0x201D)
_LEFT_SINGLE, _LEFT_DOUBLE = chr(0x2018), chr(0x201C)
_CLOSERS = "\"'" + _RIGHT_SINGLE + _RIGHT_DOUBLE + "\\)\\]"
_OPENERS = "\"'" + _LEFT_SINGLE + _LEFT_DOUBLE + "\\(\\["
_BOUNDARY_RE = re.compile(f"[.!?]+[{_CLOSERS}]*\\s+(?=[{_OPENERS}]*[A-Z0-9])")


def _is_abbreviation(source: str, dot: int) -> bool:
    """Is the period at `dot` part of an abbreviation rather than a full stop?

    Reads the token back off the text — letters and internal periods — so
    ``U.S.`` arrives as ``u.s`` and ``Mr.`` as ``mr``. A lone capital is taken
    as an initial, which catches ``Mr. B. Traoré`` without listing every letter.
    """
    start = dot
    while start > 0 and (source[start - 1].isalpha() or source[start - 1] == "."):
        start -= 1
    word = source[start:dot]
    if not word:
        return False
    if len(word) == 1 and word.isupper():
        return True
    return word.lower().strip(".") in ABBREVIATIONS


def sentence_spans(source: str) -> list[tuple[int, int]]:
    """Sentence boundaries in `source`, as ``(start, end)`` offsets.

    Spans exclude the whitespace between sentences, so ``source[start:end]`` is
    the sentence with its terminal punctuation and nothing else.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _BOUNDARY_RE.finditer(source):
        first = match.start()
        if source[first] == "." and _is_abbreviation(source, first):
            continue
        end = first + len(match.group().rstrip())
        if end > start:
            spans.append((start, end))
        start = match.end()
    if start < len(source):
        spans.append((start, len(source)))
    return spans


def sentence_at(source: str, position: int, spans: list[tuple[int, int]] | None = None) -> str:
    """The sentence containing `position`.

    Pass `spans` when several positions in the same text are wanted, so the
    segmentation is not redone per occurrence.
    """
    if spans is None:
        spans = sentence_spans(source)
    found = ""
    for start, end in spans:
        if start > position:
            break
        found = source[start:end]
        if start <= position < end:
            break
    return re.sub(r"\s+", " ", found).strip()


@dataclass(frozen=True)
class Line:
    """One occurrence of one term, with everything needed to cite it."""

    id: str  #: ``UNSC_2014_SPV.7155_spch0007#3`` — speech file, occurrence ordinal
    spv: str
    date: str
    country: str
    iso3: str | None
    group: str
    type: str
    agenda: str
    start: int  #: offset into the *whole* speech text, form of address included
    end: int
    left: str
    kw: str
    right: str
    sent: str

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "spv": self.spv,
            "date": self.date,
            "country": self.country,
            "iso3": self.iso3,
            "group": self.group,
            "type": self.type,
            "agenda": self.agenda,
            "start": self.start,
            "end": self.end,
            "left": self.left,
            "kw": self.kw,
            "right": self.right,
            "sent": self.sent,
        }


#: Columns :func:`extract` needs. Named so a caller can read only these from the
#: parquet — the full 99-column frame carries 389 MB of text it does not want
#: twice.
REQUIRED = [
    "filename",
    "meeting_symbol",
    "date",
    "country_org",
    "iso3",
    "speaker_group",
    "participanttype",
    "agenda_item_manual",
    "text",
    "body_start",
]


def extract(speeches: pd.DataFrame, term: Term, width: int = WIDTH) -> Iterator[Line]:
    """Every occurrence of `term`, in speech order.

    Matching runs on the body, so a term inside a form of address cannot be
    counted — which is what makes these lines agree with 03's totals. The
    offsets emitted are shifted back into whole-text coordinates.
    """
    if missing := [c for c in REQUIRED if c not in speeches.columns]:
        raise KeyError(f"extract() needs {', '.join(missing)}")

    flag = f"{HAS}{term.name}"
    present = speeches[speeches[flag]] if flag in speeches.columns else speeches

    for row in present.itertuples():
        offset = int(row.body_start)
        body = row.text[offset:]
        matches = list(term.regex.finditer(body))
        if not matches:
            continue

        spans = sentence_spans(body)
        stem = row.filename.removesuffix(".txt")
        for ordinal, match in enumerate(matches, start=1):
            left, keyword, right = text_lib.window(body, match.start(), match.end(), width)
            yield Line(
                id=f"{stem}#{ordinal}",
                spv=row.meeting_symbol,
                date=f"{row.date:%Y-%m-%d}",
                country=row.country_org,
                iso3=None if pd.isna(row.iso3) else row.iso3,
                group=row.speaker_group,
                type=row.participanttype,
                agenda=row.agenda_item_manual,
                start=offset + match.start(),
                end=offset + match.end(),
                left=left,
                kw=keyword,
                right=right,
                sent=sentence_at(body, match.start(), spans),
            )
