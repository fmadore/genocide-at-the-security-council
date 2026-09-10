import json

import export_web
import pytest


def test_missing_semantic_data_has_an_explicit_waiting_state(tmp_path):
    target = tmp_path / "web"
    target.mkdir()
    result = export_web.copy_part([tmp_path / "absent"], "semantic", root=target)
    assert result["files"] == 1
    assert json.loads((target / "semantic/map.json").read_text())["status"] == "pending"


def test_partial_semantic_data_is_an_error_not_a_waiting_state(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"files": {"map.json": "wrong"}}))
    with pytest.raises(ValueError, match="incomplete"):
        export_web.copy_part([source], "semantic", root=tmp_path / "web")
