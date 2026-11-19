"""The coding page's import: a coder's export folded into the annotation file."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from lib import console, schema

ROOT = Path(__file__).resolve().parents[1]


def _page():
    spec = importlib.util.spec_from_file_location("coding_page", ROOT / "tools" / "coding_page.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


page = _page()


def row(occurrence: str, coder: str = "RA1", **values: str) -> dict[str, str]:
    record = dict.fromkeys(schema.ANNOTATION_FIELDS, "")
    record.update(occurrence_id=occurrence, coder=coder, rationale="One sentence.")
    record.update(values)
    return record


def frame(*rows: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=list(schema.ANNOTATION_FIELDS), dtype="string")


def test_an_excel_saved_export_is_read_despite_its_byte_order_mark(tmp_path: Path) -> None:
    path = tmp_path / "export.csv"
    frame(row("a#1")).to_csv(path, index=False, encoding="utf-8-sig")
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    read = page.read_export(path)
    assert list(read.columns) == list(schema.ANNOTATION_FIELDS)
    assert read["occurrence_id"].tolist() == ["a#1"]


def test_a_file_the_page_did_not_write_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    pd.DataFrame({"occurrence_id": ["a#1"]}).to_csv(path, index=False)
    with pytest.raises(console.Refusal, match="not a file exported"):
        page.read_export(path)


def test_new_rows_are_added_and_unchanged_rows_skipped() -> None:
    existing = frame(row("a#1"))
    combined, counts = page.combine(existing, frame(row("a#1"), row("b#1")), replace=False)
    assert counts == {"added": 1, "unchanged": 1, "revised": 0}
    assert combined["occurrence_id"].tolist() == ["a#1", "b#1"]


def test_a_revision_is_refused_unless_asked_for() -> None:
    existing = frame(row("a#1", comment="first"))
    revised = frame(row("a#1", comment="second"))
    with pytest.raises(console.Refusal, match="revise a reading"):
        page.combine(existing, revised, replace=False)
    combined, counts = page.combine(existing, revised, replace=True)
    assert counts["revised"] == 1
    assert combined["comment"].tolist() == ["second"]


def test_two_coders_reading_one_passage_are_two_rows() -> None:
    combined, counts = page.combine(frame(row("a#1", "RA1")), frame(row("a#1", "RA2")), replace=False)
    assert counts["added"] == 1
    assert len(combined) == 2


def test_an_export_reading_one_passage_twice_is_refused() -> None:
    with pytest.raises(console.Refusal, match="twice"):
        page.combine(frame(), frame(row("a#1"), row("a#1", comment="again")), replace=False)


def test_nothing_is_written_when_a_row_fails_the_annotation_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "annotations.csv"
    frame().to_csv(target, index=False)
    before = target.read_bytes()
    candidates = tmp_path / "candidates.csv"
    candidates.write_text("occurrence_id\na#1\n", encoding="utf-8")
    export = tmp_path / "export.csv"
    frame(row("a#1")).to_csv(export, index=False)

    monkeypatch.setattr(page.model_runs, "GOLD_ANNOTATIONS", target)
    monkeypatch.setattr(page.model_runs, "GOLD_CANDIDATES", candidates)
    monkeypatch.setattr(page.lexicon, "load", lambda: type("L", (), {"compatible": None})())
    monkeypatch.setattr(page.audit, "read_referents", lambda path: set())

    def refuse(*args: object, **kwargs: object) -> None:
        raise ValueError("Unknown verdict label: (blank)")

    monkeypatch.setattr(page.audit, "merge", refuse)
    with pytest.raises(console.Refusal, match="does not pass"):
        page.import_export(export, write=True, replace=False)
    assert target.read_bytes() == before


def test_a_passing_export_is_written_only_with_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "annotations.csv"
    frame().to_csv(target, index=False)
    candidates = tmp_path / "candidates.csv"
    candidates.write_text("occurrence_id\na#1\n", encoding="utf-8")
    export = tmp_path / "export.csv"
    frame(row("a#1")).to_csv(export, index=False)

    monkeypatch.setattr(page.model_runs, "GOLD_ANNOTATIONS", target)
    monkeypatch.setattr(page.model_runs, "GOLD_CANDIDATES", candidates)
    monkeypatch.setattr(page.lexicon, "load", lambda: type("L", (), {"compatible": None})())
    monkeypatch.setattr(page.audit, "read_referents", lambda path: set())
    monkeypatch.setattr(page.audit, "merge", lambda *args, **kwargs: None)

    page.import_export(export, write=False, replace=False)
    assert pd.read_csv(target, dtype="string").empty
    page.import_export(export, write=True, replace=False)
    written = pd.read_csv(target, dtype="string", keep_default_na=False)
    assert list(written.columns) == list(schema.ANNOTATION_FIELDS)
    assert written["occurrence_id"].tolist() == ["a#1"]
