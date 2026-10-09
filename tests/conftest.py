"""Make the pipeline's modules importable as `lib.*`, and build fake corpora.

`make_speeches` is the one way a test builds rows of the normalised corpus.
Before it, eight test files each wrote their own frame with the columns they
happened to need, and a column renamed in 02 would have left all eight passing
against a corpus that no longer existed. Its column list is held to what the
steps and `lib` declare they read by `tests/test_fake_corpus.py`, and it
refuses a column it does not know, so a rename now fails in one place.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import council, entities, lexical, lexicon  # noqa: E402

#: What a fake speech says when a test does not give it a text: a form of
#: address, then a body without any lexicon term in it.
OPENING = "Mr. President: "
BODY = "I thank you for convening this meeting on the situation in the region."

#: Every column of the normalised corpus that a step or a `lib` module declares
#: it reads, and the value a fake speech takes when a test does not give one.
#: `None` marks a column derived per row from the others, as 01 and 02 derive
#: it; see `make_speeches`.
SPEECH_DEFAULTS: dict[str, object] = {
    "row_id": None,
    "filename": None,
    "basename": None,
    "meeting_symbol": "S/PV.1000",
    "speech_number": None,
    "date": None,
    "year": 2000,
    "speaker": "A speaker",
    "role": "Representative",
    "country_org": "France",
    "entity_type": "state",
    "speaker_group": council.NON_MEMBER,
    "participanttype": None,
    "agenda_item1": "Africa",
    "agenda_item_manual": "The situation in the region",
    "text": OPENING + BODY,
    "body_start": len(OPENING),
    "words": None,
    "tokens": None,
    # Nullable enrichment slots: 02 writes them empty and nothing fills them.
    "iso3": pd.NA,
    "un_regional_group": pd.NA,
    "lat": float("nan"),
    "lon": float("nan"),
    # The source's own flags, which 02 reads `entity_type` and `speaker_group`
    # off. Derived from those two here unless a test sets them.
    "source_state": None,
    "source_un_org": None,
    "source_igo": None,
    "source_ngo": None,
    "source_permanent_member": None,
    "source_elected_member": None,
}

#: Which source flags each entity type stands for. The source files `un_org` as
#: a kind of `igo`, and `entities.source_entity_type` relies on that.
ENTITY_FLAGS: dict[str, tuple[str, ...]] = {
    "state": ("source_state",),
    "un": ("source_un_org", "source_igo"),
    "igo": ("source_igo",),
    "ngo": ("source_ngo",),
    "other": (),
}


def _is_measure(column: str) -> bool:
    """A lexicon column 03 adds: `has_<term>` or `n_<term>`."""
    return column.startswith((lexicon.HAS, "n_"))


def make_speeches(
    rows: Iterable[Mapping[str, object]] | Mapping[str, Sequence[object]],
    *,
    complete: bool = True,
    flagged: bool = False,
) -> pd.DataFrame:
    """A frame of the normalised corpus, one row per mapping in `rows`.

    `rows` may instead be one mapping of column names to equal-length lists,
    the shape `pd.DataFrame` takes. Each row gives the columns a test cares about; every other column of
    `SPEECH_DEFAULTS` is filled in, and derived columns are derived the way the
    pipeline derives them: `words` counted on the body by `lexical.word_count`,
    the source flags set from `entity_type` and `speaker_group`, and both of
    those recomputed by `entities.source_entity_type` and `council.speaker_group`
    and refused if they disagree, so no fake corpus can fail 11's or 12's drift
    check by accident. A key that is neither a corpus column nor a lexicon
    measure (`has_<term>`, `n_<term>`) is an error.

    `complete=False` returns only the columns the rows give, still checked by
    name, for a test about what a function does when a column is absent — the
    legacy membership roster, say, which is read only when the source flags are
    not there.

    `flagged=True` adds every active term's `has_` and `n_` columns, counted on
    the bodies by `lexicon.apply` exactly as 03 counts them.
    """
    if isinstance(rows, Mapping):
        rows = pd.DataFrame(rows).to_dict(orient="records")
    given = [dict(row) for row in rows]
    unknown = sorted(
        {key for row in given for key in row if key not in SPEECH_DEFAULTS and not _is_measure(key)}
    )
    if unknown:
        raise KeyError(f"not a column of the normalised corpus: {', '.join(unknown)}")
    if not complete:
        if flagged:
            raise ValueError("flagged=True needs the text, which complete=False may leave out")
        return pd.DataFrame(given)

    filled = []
    for position, row in enumerate(given):
        speech = {**SPEECH_DEFAULTS, **row}
        year = int(speech["year"])
        symbol = str(speech["meeting_symbol"])
        body = str(speech["text"])[int(speech["body_start"]) :]
        speech["row_id"] = row.get("row_id", f"r{position}")
        speech["filename"] = row.get(
            "filename", f"UNSC_{year}_{symbol.replace('/', '')}_spch{position:04d}.txt"
        )
        speech["basename"] = row.get("basename", symbol.replace("/", ""))
        speech["date"] = pd.Timestamp(row.get("date", f"{year}-01-01"))
        speech["words"] = row["words"] if "words" in row else lexical.word_count([body])[0]
        # The codebook's count, never a denominator: larger than `words`, as
        # punctuation and numbers make it in the corpus, so a rate that divided
        # by the wrong one would show.
        speech["tokens"] = row.get("tokens", int(speech["words"]) * 9 // 8 + 1)
        group = str(speech["speaker_group"])
        kind = str(speech["entity_type"])
        for flag in entities.SOURCE_TYPE_FLAGS:
            speech[flag] = bool(row.get(flag, flag in ENTITY_FLAGS[kind]))
        speech["source_permanent_member"] = bool(
            row.get("source_permanent_member", group == council.PERMANENT)
        )
        speech["source_elected_member"] = bool(
            row.get("source_elected_member", group == council.ELECTED)
        )
        if "participanttype" not in row:
            speech["participanttype"] = (
                "Council member"
                if group in (council.PERMANENT, council.ELECTED)
                else "UN official"
                if kind == "un"
                else "Guest"
            )
        filled.append(speech)

    frame = pd.DataFrame(filled, columns=[*SPEECH_DEFAULTS, *_measures(given)])
    numbered = frame.groupby("meeting_symbol").cumcount() + 1
    frame["speech_number"] = frame["speech_number"].fillna(numbered).astype("int32")
    for column in ("iso3", "un_regional_group"):
        frame[column] = frame[column].astype("string")
    for column in ("lat", "lon"):
        frame[column] = frame[column].astype("float64")

    if not frame.empty:
        typed = entities.source_entity_type(frame)
        if not typed.astype(str).equals(frame["entity_type"].astype(str)):
            raise ValueError("entity_type disagrees with the source flags it is read from")
        if problems := council.drift(frame):
            raise ValueError("speaker_group disagrees with the source flags: " + "; ".join(problems))

    if flagged:
        lex = lexicon.load()
        bodies = pd.Series(
            [text[start:] for text, start in zip(frame["text"], frame["body_start"], strict=True)],
            index=frame.index,
        )
        if _measures(given):
            raise ValueError("give lexicon columns or ask for flagged=True, not both")
        frame = pd.concat([frame, lexicon.apply(bodies, lex)], axis=1)
    return frame


def _measures(rows: list[dict[str, object]]) -> list[str]:
    """The lexicon columns the rows give, in the order first seen."""
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            if _is_measure(key):
                seen.setdefault(key)
    return list(seen)
