import json

import export_web
import pytest


def test_missing_semantic_data_has_an_explicit_waiting_state(tmp_path):
    target = tmp_path / "web"
    target.mkdir()
    result = export_web.copy_part([tmp_path / "absent"], "semantic", root=target)
    assert result["files"] == 1
    assert json.loads((target / "semantic/map.json").read_text())["status"] == "pending"


def test_partial_semantic_data_is_an_error_not_a_waiting_state(tmp_path, monkeypatch):
    pin = tmp_path / "semantic-release.json"
    pin.write_text(json.dumps({"schema": 1, "url": "https://github.com/fmadore/genocide-at-the-security-council/releases/download/x/y.zip"}))
    monkeypatch.setattr(export_web, "SEMANTIC_PIN", pin)
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"files": {"map.json": "wrong"}}))
    with pytest.raises(ValueError, match="incomplete"):
        export_web.copy_part([source], "semantic", root=tmp_path / "web")
