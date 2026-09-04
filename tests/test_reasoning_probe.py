"""The reasoning ladder decision, without a model server or socket."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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
    result = probe.assess_ladder(
        [row("low", 10), row("low", 20), row("high", 100), row("high", 120)],
        ["low", "high"],
    )
    assert result["passed"] is True
    assert [item["median_reasoning_tokens"] for item in result["levels"]] == [15.0, 110.0]


def test_a_flat_ladder_is_explicitly_refused() -> None:
    result = probe.assess_ladder([row("low", 10), row("high", 10)], ["low", "high"])
    assert result["passed"] is False


def test_a_missing_level_cannot_be_mistaken_for_a_ladder() -> None:
    with pytest.raises(ValueError, match="no observations for high"):
        probe.assess_ladder([row("low", 10)], ["low", "high"])
