"""Who owns which directory, and what the export refuses to publish.

`artifacts.atomic_directory` swaps a directory in whole, which is what makes a
half-written artefact impossible — and what makes a directory single-owner. Step
12 used to write its keyness table into step 11's `countries/`, so re-running 11
deleted it; the export only warned, and the payload shipped 19 artefacts while
the actor view's fourth figure fetched a file that was not there. These tests
hold the two halves of that repair: one step, one derived directory, and a seam
that fails rather than warns.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from lib.paths import COUNTRIES, DERIVED, SPEAKER_KEYNESS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
export_web = importlib.import_module("export_web")


def test_each_derived_directory_has_one_owner():
    """The invariant the swap needs, asserted rather than remembered."""
    assert SPEAKER_KEYNESS != COUNTRIES
    assert SPEAKER_KEYNESS.parent == DERIVED
    assert COUNTRIES not in SPEAKER_KEYNESS.parents


def test_step_12_writes_outside_step_11s_directory():
    """The regression itself: 12's file must not sit where 11's swap reaches."""
    twelve = importlib.import_module("12_speaker_keyness")
    assert COUNTRIES not in twelve.OUTPUT.parents


def test_one_payload_directory_may_have_several_sources():
    """`countries/` is one directory to the dashboard and two to the pipeline."""
    sources = {name: srcs for srcs, name, _ in export_web.PARTS}
    assert set(sources["countries"]) == {COUNTRIES, SPEAKER_KEYNESS}


def test_copying_several_sources_keeps_every_file(tmp_path, monkeypatch):
    """One staging directory and one swap, so no source deletes another.

    Copying each source through its own `atomic_directory` would publish the
    first and then replace it with the second — the same fault the split above
    repairs, one level up.
    """
    web = tmp_path / "payload"
    monkeypatch.setattr(export_web, "WEB_DATA", web)
    first, second = tmp_path / "a", tmp_path / "b"
    for directory, name in ((first, "rates.json"), (second, "keyness.json")):
        directory.mkdir()
        (directory / name).write_text("{}", encoding="utf-8")

    export_web.copy_part((first, second), "countries")

    written = {path.name for path in (web / "countries").iterdir()}
    assert written == {"rates.json", "keyness.json"}


def test_a_missing_declared_artefact_stops_the_export(tmp_path, monkeypatch):
    """A warning let an incomplete payload ship. The seam refuses it instead."""
    monkeypatch.setattr(export_web, "WEB_DATA", tmp_path)
    contract = tmp_path / "payload.json"
    contract.write_text('{"countries/speaker_keyness.json": {"meta": "object"}}', encoding="utf-8")
    monkeypatch.setattr(export_web, "CONTRACT", contract)

    with pytest.raises(SystemExit) as raised:
        export_web.check_contract()
    assert raised.value.code == 1
