"""The sampling experiment's pure parts: settings, selection, agreement."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from lib import annotate, llm

ROOT = Path(__file__).resolve().parents[1]


def _probe():
    spec = importlib.util.spec_from_file_location("sampling_probe", ROOT / "scripts" / "probe_sampling.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _probe()


def speech(name: str, length: int) -> annotate.Speech:
    return annotate.Speech(
        filename=f"{name}.txt", custom_id=name, body="x" * length, meta={}, occurrences=()
    )


def test_settings_are_parsed_and_checked() -> None:
    settings = probe.parse_settings("greedy:0:1,card:1.0:0.95:20")
    assert settings[1] == {"name": "card", "temperature": 1.0, "top_p": 0.95, "top_k": 20}
    assert settings[0]["top_k"] is None
    for bad in ["greedy:0:1", "a:0:1,a:1:1", "a:0:2,b:1:1", "A:0:1,b:1:1"]:
        with pytest.raises(ValueError):
            probe.parse_settings(bad)


def test_selection_takes_the_longest_half_and_a_seeded_rest() -> None:
    speeches = [speech(f"s{i:02d}", i) for i in range(20)]
    chosen = probe.select(speeches, 6, 7)
    names = {item.custom_id for item in chosen}
    assert {"s19", "s18", "s17"} <= names and len(chosen) == 6
    assert {item.custom_id for item in probe.select(speeches[::-1], 6, 7)} == names
    assert [item.custom_id for item in chosen] == sorted(item.custom_id for item in chosen)


def test_agreement_is_over_the_occurrences_both_answered() -> None:
    label = dict.fromkeys(probe.COMPARED, "x")
    first = {"a": {1: label, 2: label}, "b": {1: label}}
    second = {"a": {1: {**label, "referent": "y"}}, "c": {1: label}}
    result = probe.agreement(first, second)
    assert result["occurrences"] == 1
    assert result["agreement"]["referent"] == 0.0
    assert result["agreement"]["verdict"] == 1.0


def test_top_k_travels_as_a_vllm_extension_and_only_when_set() -> None:
    request = llm.SpeechRequest(filename="f", custom_id="f", system="s", user="u", ordinals=(1,))
    plain = llm.request_body(request, model="m", reasoning_effort="high", max_output_tokens=5)
    assert "top_k" not in plain
    body = llm.request_body(request, model="m", reasoning_effort="high", max_output_tokens=5, top_k=20)
    assert llm.sdk_request_kwargs(body)["extra_body"] == {"top_k": 20}
