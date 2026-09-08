#!/usr/bin/env python3
"""Offline annotation checks, usable before sbatch and before server startup."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pyarrow.parquet as pq
from lib import annotate, llm
from lib.paths import EXPECTED_SPEECHES, SPEECHES_NORM


def check_corpus(path: Path) -> None:
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows != EXPECTED_SPEECHES:
        raise ValueError(
            f"Stale corpus: {parquet.metadata.num_rows:,} speeches; expected "
            f"{EXPECTED_SPEECHES:,}. Stage the current normalized corpus before submitting."
        )
    missing = set(annotate.COLUMNS) - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"Normalized corpus missing columns: {sorted(missing)}")


def check_sdk() -> None:
    import inspect

    from openai import OpenAI

    body = llm.request_body(
        llm.SpeechRequest(filename="preflight", custom_id="preflight", system="test", user="test", ordinals=()),
        model=os.environ["VLLM_MODEL_ID"],
        reasoning_effort=os.environ["VLLM_REASONING_EFFORT"],
        reasoning_location=os.environ["VLLM_REASONING_LOCATION"],
        max_output_tokens=16,
    )
    kwargs = llm.sdk_request_kwargs(body)
    with OpenAI(api_key="offline-preflight", base_url="http://offline.invalid/v1") as api:
        inspect.signature(api.responses.create).bind(**kwargs)
    reconstructed = dict(kwargs)
    reconstructed.update(reconstructed.pop("extra_body", {}))
    if reconstructed != body:
        raise ValueError("SDK adapter changed the recorded request body")


def check_weights() -> None:
    model = os.environ["VLLM_MODEL_ID"]
    revision = os.environ["VLLM_MODEL_REVISION"]
    snapshot = Path(os.environ["HF_HOME"]) / "hub" / ("models--" + model.replace("/", "--")) / "snapshots" / revision
    if not (snapshot / "config.json").is_file():
        raise ValueError(f"Pinned model snapshot is missing: {snapshot}")
    index = snapshot / "model.safetensors.index.json"
    if index.is_file():
        shards = set(json.loads(index.read_text())["weight_map"].values())
        missing = [name for name in shards if not (snapshot / name).is_file()]
        if missing:
            raise ValueError(f"Pinned model has missing shards: {missing}")
    elif not (snapshot / "model.safetensors").is_file():
        raise ValueError(f"No safetensors weights found in {snapshot}")


def main() -> None:
    check_corpus(SPEECHES_NORM)
    check_sdk()
    check_weights()
    print(f"==> preflight passed: {EXPECTED_SPEECHES:,} speeches, SDK wire body, cached model shards")


if __name__ == "__main__":
    main()
