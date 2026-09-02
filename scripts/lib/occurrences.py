"""Enumerate one term's occurrences with both of their stable identities.

Three later steps — the gold sample (13), the model annotation run (14) and
the usage aggregation (15) — all need the same enumeration 03 and 08 already
perform: every regex match of a lexicon term over every speech body, in speech
order. Each writes or joins per-occurrence records, so a private re-reading of
the regex in any of them would be a second definition of what an occurrence
*is*. This module is the single one they share.

Two identifiers per occurrence, because the project already uses both:

- ``occurrence_id`` — the SHA-256 identity from :mod:`lib.audit`, computed over
  body-relative offsets and the digest of the body, exactly as 03's audit
  candidates do;
- ``line_id`` — the human-readable KWIC id ``<filename-stem>#<ordinal>`` from
  08, with the ordinal counted per speech, one-based, in match order.

Agreement with 03/08 is asserted by the callers against the documented totals
(docs/CORPUS.md §8) at run time, not assumed here.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import audit
from . import text as text_lib
from .lexicon import Term


@dataclass(frozen=True)
class Occurrence:
    """One match of one term in one speech body."""

    index: object  #: the speech's index label in the source frame
    filename: str  #: ``UNSC_1992_SPV.3137_spch0009.txt`` — joins speaker.tsv
    line_id: str  #: ``UNSC_1992_SPV.3137_spch0009#1`` — joins the KWIC files
    ordinal: int  #: one-based position of this match within its speech
    start: int  #: body-relative offset, the coordinate audit IDs use
    end: int
    start_text: int  #: whole-text offset, the coordinate the reader view uses
    end_text: int
    keyword: str  #: the matched text, whitespace-flattened as in a KWIC line
    source_sha256: str  #: digest of the body — changes when the source does
    occurrence_id: str  #: :func:`lib.audit.occurrence_id` over all of the above


def enumerate_term(speeches: pd.DataFrame, bodies: pd.Series, term: Term) -> list[Occurrence]:
    """Every occurrence of ``term``, in speech order then match order.

    ``speeches`` needs ``filename`` and ``body_start``; ``bodies`` is the
    matching series from :func:`lib.frames.body`. Matching runs on the body
    through `Term.spans`, never the raw text and never the bare regex, so a
    term inside a form of address cannot appear and an anchored term yields
    only the occurrences its anchor kept — which is what keeps these rows equal
    in number to 03's ``n_<term>`` sums and 08's line counts.
    """
    if missing := sorted({"filename", "body_start"} - set(speeches.columns)):
        raise KeyError(f"enumerate_term() needs columns: {', '.join(missing)}")

    found: list[Occurrence] = []
    for index, body in bodies.items():
        matches = term.spans(body)
        if not matches:
            continue
        filename = str(speeches.at[index, "filename"])
        body_start = int(speeches.at[index, "body_start"])
        stem = filename.removesuffix(".txt")
        digest = audit.source_sha256(body)
        for ordinal, (start, end) in enumerate(matches, start=1):
            _, keyword, _ = text_lib.window(body, start, end)
            found.append(
                Occurrence(
                    index=index,
                    filename=filename,
                    line_id=f"{stem}#{ordinal}",
                    ordinal=ordinal,
                    start=start,
                    end=end,
                    start_text=body_start + start,
                    end_text=body_start + end,
                    keyword=keyword,
                    source_sha256=digest,
                    occurrence_id=audit.occurrence_id(
                        filename, term.name, start, end, keyword, digest
                    ),
                )
            )
    return found


def frame(occurrences: list[Occurrence]) -> pd.DataFrame:
    """The same enumeration as a DataFrame, one row per occurrence."""
    return pd.DataFrame([vars(occurrence) for occurrence in occurrences])
