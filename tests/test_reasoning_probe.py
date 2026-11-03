"""The reasoning ladder decision, without a model server or socket."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from lib import probes

ROOT = Path(__file__).resolve().parents[1]


def _probe():
    path = ROOT / "scripts" / "probe_reasoning.py"
    spec = importlib.util.spec_from_file_location("reasoning_probe_step", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _probe()


def row(level: str, tokens: int, latency: float = 1.0) -> dict[str, object]:
    return {"level": level, "reasoning_tokens": tokens, "latency_seconds": latency}


def test_a_varying_reasoning_ladder_passes_and_preserves_each_level() -> None:
    result = probes.assess_ladder(
        [row("low", 10), row("low", 20), row("high", 100), row("high", 120)],
        ["low", "high"],
    )
    assert result["passed"] is True
    assert [item["median_reasoning_tokens"] for item in result["levels"]] == [15.0, 110.0]


def test_a_flat_ladder_is_explicitly_refused() -> None:
    result = probes.assess_ladder([row("low", 10), row("high", 10)], ["low", "high"])
    assert result["passed"] is False


def test_a_missing_level_cannot_be_mistaken_for_a_ladder() -> None:
    with pytest.raises(ValueError, match="no observations for high"):
        probes.assess_ladder([row("low", 10)], ["low", "high"])


@pytest.mark.parametrize("low,high", [(100, 0), (100, 50), (0, 0)])
def test_reversed_or_empty_reasoning_cannot_pass(low, high):
    assert not probes.assess_ladder([row("low", low), row("high", high)], ["low", "high"])["passed"]


class Truncated(ValueError):
    pass


def probe_fixture(tmp_path, monkeypatch, speeches, cut_off):
    """A probe over `speeches`, whose answers are cut off for the (speech, level) pairs in `cut_off`."""
    referents = tmp_path / "referents.csv"
    referents.write_text("list")
    pack = SimpleNamespace(sha256="prompt", constraints=frozenset())
    api = SimpleNamespace(responses=SimpleNamespace(create=lambda **body: SimpleNamespace(model_dump=lambda **_: body)))

    def output_text(body):
        if (body["body"], body["level"]) in cut_off:
            raise Truncated("response incomplete (max_output_tokens)")
        return "{}"

    step = SimpleNamespace(client=lambda: api, runtime_record=lambda _: {}, ResponseTruncated=Truncated,
                           output_text=output_text, usage_of=lambda body: {
                               "reasoning_tokens": 1 if body["level"] == "low" else 100, "output_tokens": 120})
    monkeypatch.setattr(probe, "PROBES", tmp_path / "probes")
    monkeypatch.setattr(probe, "REFERENTS", referents)
    monkeypatch.setattr(probe, "annotation_step", lambda: step)
    monkeypatch.setattr(probe.annotate, "gather", lambda limit: (speeches, speeches[:limit], 8))
    monkeypatch.setattr(probe.audit, "read_referent_list", lambda _: SimpleNamespace(current={"other"}))
    monkeypatch.setattr(probe.llm, "read_referent_table", lambda _: [])
    monkeypatch.setattr(probe.llm, "render_referents", lambda _: "table")
    monkeypatch.setattr(probe.prompts, "load_prompt", lambda _: pack)
    monkeypatch.setattr(probe.llm, "build_request", lambda meta, body, *rest, **kw: body)
    monkeypatch.setattr(probe.llm, "request_body", lambda body, **kw: {"body": body, "level": kw["reasoning_effort"]})
    monkeypatch.setattr(probe.llm, "validate_response", lambda *a, **kw: None)


def speech_named(name):
    return SimpleNamespace(meta={}, body=name, custom_id=name,
                           occurrences=[SimpleNamespace(occurrence_id=name, ordinal=1)])


def test_a_speech_cut_off_at_the_top_level_gives_way_to_a_spare(tmp_path, monkeypatch):
    import json

    pool = [speech_named(name) for name in ("first", "second", "third", "fourth")]
    probe_fixture(tmp_path, monkeypatch, pool, cut_off={("first", "high")})
    args = SimpleNamespace(run_id="fixture", model="m", model_revision="rev", reasoning_location="request",
                           levels="low,high", speeches=2, spares=2, temperature=0.0, top_p=1.0)
    probe.run(args)
    written = json.loads((tmp_path / "probes" / "fixture" / "probe.json").read_text(encoding="utf-8"))
    assert written["passed"]
    assert written["speeches"] == ["second", "third"]
    assert [(item["custom_id"], item["level"]) for item in written["skipped"]] == [("first", "high")]
    assert {row["custom_id"] for row in written["observations"]} == {"second", "third"}
    assert written["candidates"] == 4


def test_a_probe_with_too_few_answered_speeches_is_refused(tmp_path, monkeypatch):
    pool = [speech_named(name) for name in ("first", "second", "third")]
    probe_fixture(tmp_path, monkeypatch, pool, cut_off={("first", "high"), ("second", "low")})
    args = SimpleNamespace(run_id="fixture", model="m", model_revision="rev", reasoning_location="request",
                           levels="low,high", speeches=2, spares=1, temperature=0.0, top_p=1.0)
    with pytest.raises(SystemExit):
        probe.run(args)


@pytest.mark.parametrize("changed", ["temperature", "top_p", "prompt", "referents", "speech", "runtime"])
def test_passed_probe_is_reused_only_for_identical_inputs(tmp_path, monkeypatch, changed):
    args = SimpleNamespace(run_id="fixture", model="m", model_revision="rev", reasoning_location="request",
                           levels="low,high", speeches=1, spares=0, temperature=0.1, top_p=0.9)
    referents = tmp_path / "referents.csv"
    referents.write_text("original")
    pack = SimpleNamespace(sha256="prompt-one", constraints=frozenset())
    speech = SimpleNamespace(meta={}, body="original speech", custom_id="s",
                             occurrences=[SimpleNamespace(occurrence_id="one", ordinal=1)])
    runtime = {"hardware": "first"}
    api = SimpleNamespace(responses=SimpleNamespace(create=lambda **body: SimpleNamespace(model_dump=lambda **_: body)))
    step = SimpleNamespace(client=lambda: api, runtime_record=lambda _: runtime, ResponseTruncated=Truncated,
                           output_text=lambda _: "{}", usage_of=lambda body: {
                               "reasoning_tokens": 1 if body["level"] == "low" else 100,
                               "output_tokens": 120})
    monkeypatch.setattr(probe, "PROBES", tmp_path / "probes")
    monkeypatch.setattr(probe, "REFERENTS", referents)
    monkeypatch.setattr(probe, "annotation_step", lambda: step)
    monkeypatch.setattr(probe.annotate, "gather", lambda _: ([speech], [speech], 6))
    monkeypatch.setattr(probe.audit, "read_referent_list", lambda _: SimpleNamespace(current={"other"}))
    monkeypatch.setattr(probe.llm, "read_referent_table", lambda _: [])
    monkeypatch.setattr(probe.llm, "render_referents", lambda _: "table")
    monkeypatch.setattr(probe.prompts, "load_prompt", lambda _: pack)
    monkeypatch.setattr(probe.llm, "build_request", lambda meta, body, *rest, **kw: body)
    monkeypatch.setattr(probe.llm, "request_body", lambda body, **kw: {
        "body": body, "level": kw["reasoning_effort"], "temperature": kw["temperature"], "top_p": kw["top_p"]})
    monkeypatch.setattr(probe.llm, "validate_response", lambda *a, **kw: None)
    probe.run(args)
    def refuse_client():
        raise RuntimeError("fresh probe required")
    step.client = refuse_client
    probe.run(args)  # unchanged identity must not touch the client
    if changed in {"temperature", "top_p"}:
        setattr(args, changed, 0.5)
    elif changed == "prompt":
        pack.sha256 = "new-prompt"
    elif changed == "referents":
        referents.write_text("changed definition")
    elif changed == "speech":
        speech.body = "changed speech"
    else:
        runtime["hardware"] = "second"
    with pytest.raises(RuntimeError, match="fresh probe"):
        probe.run(args)
