"""`tools/carry_over_runs.py`: which runs a rebuild of the table carries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "carry_over_runs", ROOT / "tools" / "carry_over_runs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _tool()


def test_a_rebuild_carries_the_runs_the_table_lists(tmp_path: Path, monkeypatch) -> None:
    table = tmp_path / "carry_over.json"
    table.write_text(json.dumps({"runs": ["2026-09-08-qwen-131k"]}), encoding="utf-8")
    monkeypatch.setattr(tool, "OUTPUT", table)
    assert tool.carried_runs() == ["2026-09-08-qwen-131k"]


def test_without_a_table_every_run_is_a_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tool, "OUTPUT", tmp_path / "missing.json")
    assert tool.carried_runs() is None


def test_the_committed_table_carries_no_run_asked_about_v6() -> None:
    runs = tool.carried_runs()
    assert runs is not None
    assert all(not name.startswith("2026-11") for name in runs)
