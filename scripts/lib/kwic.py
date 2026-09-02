"""Concordance lines: keyword in context, and the sentence around it.

Two units per occurrence, because they answer different questions:

- a **±150-character window** with line breaks flattened, for scanning a
  thousand lines at once and seeing a pattern;
- the **full sentence**, for quoting in a paper.

Offsets are recorded against the *whole* speech text, not the body the match was
found in, so the reader view can highlight a match without re-running any regex
and without knowing where the form of address ended.

Sentence segmentation itself lives in `lib.text` and is re-exported here: the
lexicon needs the same unit, because an anchored term is counted only in a
sentence that also says `genocid*`, and `lib.lexicon` cannot import this module
without a cycle. If the distribution of sentence lengths the note reports ever
says the rules are wrong, `lib.text.sentence_spans` is one function to swap.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import pandas as pd

from . import text as text_lib
from .lexicon import HAS, Term
from .text import LONG_SENTENCE, sentence_at, sentence_spans

#: Characters of context either side of the keyword in the display snippet.
WIDTH = 150

#: `LONG_SENTENCE`, `sentence_at` and `sentence_spans` are re-exported from
#: :mod:`lib.text`: this is where a reader of the concordance looks for them,
#: and 08's note still reports the long-sentence rate off this module. Named
#: here so the re-export is a declaration rather than an import that looks
#: unused.
__all__ = [
    "LONG_SENTENCE",
    "REQUIRED",
    "WIDTH",
    "Line",
    "extract",
    "offsets",
    "sentence_at",
    "sentence_spans",
]


@dataclass(frozen=True)
class Line:
    """One occurrence of one term, with everything needed to cite it."""

    id: str  #: ``UNSC_2014_SPV.7155_spch0007#3`` — speech file, one-based ordinal
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


def offsets(
    source: str, body_start: int, terms: Iterable[Term]
) -> dict[str, list[list[int]]]:
    """Whole-text spans of every occurrence of each term in one speech.

    The reader view highlights from these rather than re-running the lexicon in
    the browser: the regexes are the analysis, and a second implementation of
    them in JavaScript would be a second thing to keep true.

    Matching runs on the body and the spans are shifted back, so what is
    highlighted is exactly what was counted. A term with no occurrence is left
    out rather than mapped to an empty list.
    """
    body = source[body_start:]
    found: dict[str, list[list[int]]] = {}
    for term in terms:
        spans = [
            [body_start + match.start(), body_start + match.end()]
            for match in term.regex.finditer(body)
        ]
        if spans:
            found[term.name] = spans
    return found


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
