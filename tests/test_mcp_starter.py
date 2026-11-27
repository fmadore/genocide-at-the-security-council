"""Tests for the stdlib-only data client and SKILL.md in examples/mcp-starter/."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STARTER_DIR = ROOT / "examples" / "mcp-starter"


def _load_client_module():
    spec = importlib.util.spec_from_file_location("mcp_starter_client", STARTER_DIR / "client.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_fixture_data(root: Path) -> Path:
    _write_json(
        root / "manifest.json",
        {"generated": "2026-11-27T00:00:00Z", "git_commit": "abc123", "parts": {}},
    )
    _write_json(
        root / "series" / "annual.json",
        {
            "meta": {"analysis_hash": "hash-series"},
            "periods": [1994, 1995],
            "corpus": {"speeches": [1000, 1200], "words": [500000, 600000]},
            "record": {"first_date": "1946-01-17", "last_date": "2026-06-23"},
            "sufficient": [True, True],
            "minimum_speeches": 125,
            "terms": {
                "genocide": {
                    "speeches": [80, 40],
                    "occurrences": [150, 70],
                    "speech_rate": [0.08, 0.033],
                    "speech_rate_low": [0.06, 0.02],
                    "speech_rate_high": [0.10, 0.05],
                    "speech_rate_cluster_low": [0.05, 0.015],
                    "speech_rate_cluster_high": [0.11, 0.055],
                    "token_rate": [30.0, 11.7],
                }
            },
        },
    )
    _write_json(
        root / "kwic" / "genocide.json",
        {
            "meta": {"analysis_hash": "hash-kwic"},
            "term": "genocide",
            "count": 2,
            "lines": [
                {
                    "id": "SC03377-01-004#1",
                    "spv": "S/PV.3377",
                    "date": "1994-05-16",
                    "country": "New Zealand",
                    "group": "E10",
                    "type": "Council member",
                    "agenda": "The situation concerning Rwanda",
                    "kw": "genocide",
                    "sent": "Acts of genocide are occurring in Rwanda.",
                },
                {
                    "id": "SC07155-01-007#1",
                    "spv": "S/PV.7155",
                    "date": "2014-04-16",
                    "country": "Rwanda",
                    "group": "E10",
                    "type": "Council member",
                    "agenda": "Prevention of genocide",
                    "kw": "genocide",
                    "sent": "Twenty years after the genocide against the Tutsi.",
                },
            ],
        },
    )
    meeting_path = root / "speeches" / "SC03377-01.json.gz"
    meeting_path.parent.mkdir(parents=True, exist_ok=True)
    meeting_payload = {
        "basename": "SC03377-01",
        "spv": "S/PV.3377",
        "date": "1994-05-16",
        "agenda": "The situation concerning Rwanda",
        "speeches": [
            {
                "id": "SC03377-01-004",
                "speaker": "Mr. KEATING",
                "country": "New Zealand",
                "text": "Acts of genocide are occurring in Rwanda. The Council must act.",
            }
        ],
    }
    meeting_path.write_bytes(gzip.compress(json.dumps(meeting_payload).encode("utf-8")))
    _write_json(
        root / "usage" / "occurrences.json",
        {
            "meta": {
                "run_id": "2026-11-03-qwen-131k",
                "model": "Qwen/Qwen3.8-27B",
                "comparison_run": "2026-11-03-gemma4",
            },
            "occurrences": [
                {
                    "id": "SC03377-01-004#1",
                    "occurrence_id": "deadbeef",
                    "verdict": "true_positive",
                    "referent": "rwanda_1994",
                    "speaker_position": "asserts",
                    "evidence_valid": True,
                    "contested": ["speaker_position"],
                    "alt": {"speaker_position": "reports_without_position"},
                }
            ],
        },
    )
    return root


def test_parse_meeting_basename_and_validation() -> None:
    mod = _load_client_module()
    assert mod.parse_meeting_basename("SC03377-01") == "SC03377-01"
    assert mod.parse_meeting_basename("SC03377-01-004") == "SC03377-01"
    assert mod.parse_meeting_basename("SC03377-01-004#1") == "SC03377-01"
    with pytest.raises(ValueError):
        mod.parse_meeting_basename("../etc/passwd")
    with pytest.raises(ValueError):
        mod.validate_term("../secrets")


def test_local_client_queries_and_epistemic_labels(tmp_path: Path) -> None:
    mod = _load_client_module()
    data_dir = _build_fixture_data(tmp_path / "data")
    client = mod.UnscDataClient(data_dir=data_dir)

    catalog = client.get_catalog()
    assert catalog["mode"] == "local"
    assert catalog["epistemic_rules"]

    series = client.get_annual_series(term="genocide", start_year=1994, end_year=1994)
    assert series["epistemic_layer"] == "computed_from_record"
    assert series["validated"] is True
    assert len(series["rows"]) == 1
    assert series["rows"][0]["occurrences"] == 150

    kwic = client.search_concordance(term="genocide", country="New Zealand", year=1994)
    assert kwic["total_matching_filters"] == 1
    assert kwic["matches"][0]["meeting_basename"] == "SC03377-01"

    speech = client.get_speech("SC03377-01-004#1")
    assert speech["spv"] == "S/PV.3377"
    assert "The Council must act." in speech["speech"]["text"]

    labels = client.get_model_labels("SC03377-01-004#1")
    assert labels["epistemic_layer"] == "model_derived_unvalidated"
    assert labels["validated"] is False
    assert "UNVALIDATED" in labels["warning"]
    assert labels["labels"]["contested"] == ["speaker_position"]


def test_starter_skill_file_has_valid_frontmatter() -> None:
    text = (STARTER_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: unsc-genocide-research" in text
    assert "description:" in text
    assert "10.7910/DVN/CKPTRB" in text
