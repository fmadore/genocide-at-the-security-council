"""Catch input/client failures before loading GPU weights."""
import importlib.util
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("annotation_preflight", ROOT / "scripts/preflight_annotation.py")
assert spec and spec.loader
step = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step)


def test_stale_corpus_rejected_even_for_smoke(tmp_path, monkeypatch):
    path = tmp_path / "normalized.parquet"
    pq.write_table(pa.table({column: ["a", "b"] for column in step.annotate.COLUMNS}), path)
    monkeypatch.setattr(step, "EXPECTED_SPEECHES", 3)
    with pytest.raises(ValueError, match="Stale corpus"):
        step.check_corpus(path)
    monkeypatch.setattr(step, "EXPECTED_SPEECHES", 2)
    step.check_corpus(path)
    pq.write_table(pa.table({"text": ["a", "b"]}), path)
    with pytest.raises(ValueError, match="missing columns"):
        step.check_corpus(path)


def test_missing_cached_shard_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setenv("VLLM_MODEL_ID", "test/model")
    monkeypatch.setenv("VLLM_MODEL_REVISION", "revision")
    snapshot = tmp_path / "hub/models--test--model/snapshots/revision"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    (snapshot / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"a": "shard.safetensors"}}))
    with pytest.raises(ValueError, match="missing shards"):
        step.check_weights()
    (snapshot / "shard.safetensors").write_bytes(b"fixture")
    step.check_weights()


def test_offline_sdk_preflight(monkeypatch):
    pytest.importorskip("openai")
    pytest.importorskip("httpx")
    monkeypatch.setenv("VLLM_MODEL_ID", "test/model")
    monkeypatch.setenv("VLLM_REASONING_EFFORT", "xhigh")
    monkeypatch.setenv("VLLM_REASONING_LOCATION", "chat_template_kwargs")
    step.check_sdk()
