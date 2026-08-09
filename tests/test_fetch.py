"""Regression tests for the Dataverse HTTP boundary."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def fetch_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "00_fetch_data.py"
    spec = importlib.util.spec_from_file_location("fetch_data", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_headers(request, fetch_module, accept: str) -> None:
    assert request.get_header("User-agent") == fetch_module.USER_AGENT
    assert request.get_header("Accept") == accept


def test_dataset_metadata_request_identifies_the_project(monkeypatch, fetch_module):
    seen = {}
    payload = {
        "data": {
            "versionNumber": 6,
            "versionMinorNumber": 1,
            "files": [],
        }
    }

    def urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)

    assert fetch_module.dataset_version("6.1") == payload["data"]
    assert seen["timeout"] == 60
    assert_headers(seen["request"], fetch_module, "application/json")


def test_file_download_identifies_the_project(monkeypatch, tmp_path, fetch_module):
    seen = {}

    def urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return io.BytesIO(b"abc")

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", urlopen)
    destination = tmp_path / "sample.tsv"

    fetch_module.download(123, destination, 3)

    assert destination.read_bytes() == b"abc"
    assert seen["timeout"] == 120
    assert_headers(seen["request"], fetch_module, "application/octet-stream")
