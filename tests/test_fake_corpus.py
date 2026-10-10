"""The shared fake corpus has the columns the pipeline writes and reads.

`conftest.make_speeches` is what every hand-built corpus in the tests goes
through, so it is held at both ends: every column it fills is one 01 and 02
actually write, on the adapter's own contract fixture, and every column a step
or a `lib` module declares it reads is one it fills. A column renamed in 02
fails here rather than passing quietly in every test that built its own frame.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest
from conftest import SPEECH_DEFAULTS, make_speeches
from lib import actors, council, kwic, lexical, lexicon, sakamoto
from test_build_sakamoto import meeting_source, speech_source

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def declared_readers() -> dict[str, list[str]]:
    """Every corpus column list the pipeline declares, by who declares it.

    The numbered steps each name the columns they read as a module-level
    `COLUMNS`; `lib` adds the ones its own functions check for. A lexicon
    column (`has_genocide`) is 03's, not 02's, and is left out.
    """
    readers: dict[str, list[str]] = {
        "lib.kwic.REQUIRED": list(kwic.REQUIRED),
        "lib.actors.REQUIRED_COLUMNS": list(actors.REQUIRED_COLUMNS),
        "lib.actors.COLUMNS": list(actors.COLUMNS),
    }
    for path in sorted(SCRIPTS.glob("[0-9]*.py")):
        columns = getattr(importlib.import_module(path.stem), "COLUMNS", None)
        if columns is not None:
            readers[path.name] = [
                column for column in columns if not column.startswith((lexicon.HAS, "n_"))
            ]
    return readers


def normalised_source() -> pd.DataFrame:
    """What 01 and 02 write, run on the adapter's contract fixture."""
    normalise = importlib.import_module("02_normalise")
    meetings = sakamoto.adapt_meetings(meeting_source())
    speeches = sakamoto.adapt_speeches(speech_source(), meetings)
    normalise.normalise_text(speeches)
    speeches = normalise.attach_entities(speeches)
    return normalise.attach_speaker_group(speeches)


def test_every_column_a_step_reads_is_in_the_fake_corpus() -> None:
    missing = {
        reader: sorted(set(columns) - set(SPEECH_DEFAULTS))
        for reader, columns in declared_readers().items()
        if set(columns) - set(SPEECH_DEFAULTS)
    }
    assert not missing, f"columns read but not in conftest.SPEECH_DEFAULTS: {missing}"


def test_every_column_of_the_fake_corpus_is_read_by_something() -> None:
    read = {column for columns in declared_readers().values() for column in columns}
    assert not set(SPEECH_DEFAULTS) - read, "columns nothing declares it reads"


def test_every_column_of_the_fake_corpus_is_one_02_writes() -> None:
    written = set(normalised_source().columns)
    assert not set(SPEECH_DEFAULTS) - written, (
        f"not written by 01 and 02: {sorted(set(SPEECH_DEFAULTS) - written)}"
    )


def test_an_unknown_column_is_refused() -> None:
    with pytest.raises(KeyError, match="spoken_language"):
        make_speeches([{"year": 1994, "spoken_language": "French"}])


def test_derived_columns_are_derived_as_the_pipeline_derives_them() -> None:
    frame = make_speeches(
        [
            {"text": "Mr. President: Never again, said the Council.", "body_start": 15},
            {"speaker_group": council.PERMANENT, "country_org": "China"},
            {"speaker_group": council.UN_GROUP, "entity_type": "un", "country_org": "Secretariat"},
        ]
    )
    assert frame["words"].tolist()[0] == lexical.word_count(["Never again, said the Council."])[0]
    assert (frame["tokens"] > frame["words"]).all()
    assert frame["source_permanent_member"].tolist() == [False, True, False]
    assert frame["participanttype"].tolist() == ["Guest", "Council member", "UN official"]
    assert council.drift(frame) == []
    assert frame["row_id"].is_unique and frame["filename"].is_unique


def test_an_impossible_seat_is_refused() -> None:
    """A permanent member that is not a state cannot come out of 02."""
    with pytest.raises(ValueError):
        make_speeches([{"speaker_group": council.PERMANENT, "entity_type": "igo"}])


def test_flagged_counts_the_lexicon_as_03_does() -> None:
    frame = make_speeches(
        [{"text": "Mr. President: genocide, and again genocide.", "body_start": 15}, {}],
        flagged=True,
    )
    assert frame["n_genocide"].tolist() == [2, 0]
    assert frame["has_genocide"].tolist() == [True, False]
