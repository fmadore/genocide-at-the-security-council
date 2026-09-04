"""Contract tests for the Sakamoto-Matsuoka source adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def build_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "01_build_parquet.py"
    spec = importlib.util.spec_from_file_location("build_sakamoto", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def meeting_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "record_id": ["SC00001-01"],
            "year": ["1946"],
            "month": ["1"],
            "day": ["17"],
            "meeting_num": ["1"],
            "closed": ["False"],
            "topic": ["Opening of the Security Council"],
            "agenda": ["Adoption of the agenda"],
            "agenda_categories": ["Thematic Issues; Other"],
            "pres_name": ["Mr. Makin"],
            "pres_country": ["Australia"],
            "speeches": ["True"],
            "word_count": ["42"],
            "outcome": ["--"],
            "record": ["S/PV.1"],
            "record_url": ["https://undocs.org/en/S/PV.1"],
            "RES": [pd.NA],
            "RES_url": [pd.NA],
            "PRST": [pd.NA],
            "PRST_url": [pd.NA],
        }
    )


def speech_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "speech_id": ["SC00001-01-001", "SC00001-01-002"],
            "record_id": ["SC00001-01", "SC00001-01"],
            "doc_name": ["S_PV.1", "S_PV.1"],
            "meeting_num": ["1", "1"],
            "year": ["1946", "1946"],
            "month": ["1", "1"],
            "day": ["17", "17"],
            "topic": ["Opening", "Opening"],
            "agenda": ["Adoption", "Adoption"],
            "order": ["1", "2"],
            "speaker": ["Mr. Makin", "Mr. Stettinius"],
            "affiliation": ["Australia", "United States"],
            "position": [pd.NA, pd.NA],
            "president": ["True", "False"],
            "secretary_general": ["False", "False"],
            "procedural": ["True", "False"],
            "count": ["12", "30"],
            "speech": ["I declare the Council constituted.", "We support the agenda."],
            "affiliation_cow": ["Australia", "United States of America"],
            "cow_ccode": ["900", "2"],
            "permanent_member": ["False", "True"],
            "elected_member": ["True", "False"],
            "state": ["True", "True"],
            "igo": ["False", "False"],
            "un_org": ["False", "False"],
            "ngo": ["False", "False"],
        }
    )


def test_adapter_preserves_source_ids_and_body_text(build_module):
    meetings = build_module.adapt_meetings(meeting_source())
    speeches = build_module.adapt_speeches(speech_source(), meetings)

    assert speeches["row_id"].tolist() == ["SC00001-01-001", "SC00001-01-002"]
    assert speeches["filename"].tolist() == [
        "SC00001-01-001.txt",
        "SC00001-01-002.txt",
    ]
    assert speeches["meeting_symbol"].tolist() == ["S/PV.1", "S/PV.1"]
    assert speeches["text"].iloc[0] == "I declare the Council constituted."
    assert speeches["speech_format"].eq("Transcript").all()


def test_adapter_derives_honest_participant_types(build_module):
    meetings = build_module.adapt_meetings(meeting_source())
    speeches = build_module.adapt_speeches(speech_source(), meetings)

    assert speeches["participanttype"].tolist() == ["Procedural", "Council member"]
    assert speeches["source_procedural"].tolist() == [True, False]
    assert speeches["source_affiliation"].tolist() == ["Australia", "United States"]


def test_meeting_adapter_keeps_all_records_and_first_broad_category(build_module):
    meetings = build_module.adapt_meetings(meeting_source())

    assert meetings.loc[0, "basename"] == "SC00001-01"
    assert meetings.loc[0, "spv"] == "S/PV.1"
    assert meetings.loc[0, "agenda_item1"] == "Thematic"
    assert meetings.loc[0, "source_word_count"] == 42


def test_unknown_boolean_is_refused(build_module):
    with pytest.raises(ValueError, match="unknown boolean"):
        build_module.as_boolean(pd.Series(["perhaps"]), "closed")
