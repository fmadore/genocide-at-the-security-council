"""What the two pre-run probes decide, without a model server or a socket.

`probe_reasoning.py` and `probe_sampling.py` send real requests to a served
model before an annotation run. What they send and what they conclude from the
answers — whether a reasoning ladder actually climbs, which sampling settings
and speeches are compared, and how far two settings agree — is decided here, so
it can be tested on any machine. Both artefacts are operational evidence under
`data/interim/`: never a model annotation, never input to a figure.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from collections.abc import Sequence
from typing import Any

from . import annotate

# --- The reasoning ladder --------------------------------------------------


def assess_ladder(rows: list[dict[str, Any]], levels: list[str]) -> dict[str, object]:
    """Summarise the paired probe and say whether its reasoning depth varies."""
    summary = []
    medians = []
    for level in levels:
        selected = [row for row in rows if row["level"] == level]
        reasoning = [int(row["reasoning_tokens"]) for row in selected]
        latency = [float(row["latency_seconds"]) for row in selected]
        if not selected:
            raise ValueError(f"reasoning probe has no observations for {level}")
        median_reasoning = statistics.median(reasoning)
        medians.append(median_reasoning)
        summary.append(
            {
                "level": level,
                "requests": len(selected),
                "median_reasoning_tokens": median_reasoning,
                "median_latency_seconds": round(statistics.median(latency), 3),
            }
        )
    first = [int(row["reasoning_tokens"]) for row in rows if row["level"] == levels[0]]
    last = [int(row["reasoning_tokens"]) for row in rows if row["level"] == levels[-1]]
    paired = len(first) == len(last) and all(high > low for low, high in zip(first, last, strict=True))
    return {
        "levels": summary,
        "passed": paired and medians[-1] > 0 and medians[-1] == max(medians),
        "rule": "Every paired top-level response uses more reasoning tokens than its lowest-level response; the top median is positive and maximal. This is an operational screen, not statistical validation.",
    }


# --- Sampling settings -----------------------------------------------------

#: The fields whose agreement between settings is reported.
COMPARED = ("verdict", "concrete_case", "speaker_position", "referent", "quotation")


def parse_settings(text: str) -> list[dict[str, object]]:
    """`name:temperature:top_p[:top_k]`, comma-separated, at least two, names unique."""
    settings = []
    for chunk in text.split(","):
        parts = chunk.strip().split(":")
        if len(parts) not in (3, 4) or not re.fullmatch(r"[a-z][a-z0-9_-]*", parts[0]):
            raise ValueError(f"setting {chunk!r} is not name:temperature:top_p[:top_k]")
        setting: dict[str, object] = {
            "name": parts[0],
            "temperature": float(parts[1]),
            "top_p": float(parts[2]),
            "top_k": int(parts[3]) if len(parts) == 4 else None,
        }
        if setting["temperature"] < 0 or not 0 < setting["top_p"] <= 1:  # type: ignore[operator]
            raise ValueError(f"setting {chunk!r} has an invalid temperature or top_p")
        settings.append(setting)
    names = [str(setting["name"]) for setting in settings]
    if len(settings) < 2 or len(set(names)) != len(names):
        raise ValueError("at least two settings with distinct names are needed")
    return settings


def select(speeches: Sequence[annotate.Speech], count: int, seed: int) -> list[annotate.Speech]:
    """Half the longest speeches, half a seeded draw from the rest, in corpus order."""
    by_length = sorted(speeches, key=lambda speech: (-len(speech.body), speech.custom_id))
    longest = by_length[: count // 2]
    chosen = {speech.custom_id for speech in longest}

    def rank(speech: annotate.Speech) -> str:
        return hashlib.sha256(f"{seed}\x1f{speech.custom_id}".encode()).hexdigest()

    rest = sorted((speech for speech in speeches if speech.custom_id not in chosen), key=rank)
    chosen |= {speech.custom_id for speech in rest[: count - len(longest)]}
    return [speech for speech in speeches if speech.custom_id in chosen]


def agreement(
    first: dict[str, dict[int, dict[str, object]]],
    second: dict[str, dict[int, dict[str, object]]],
) -> dict[str, object]:
    """Per-field agreement over the occurrences both settings answered."""
    shared = [
        (speech, ordinal)
        for speech, labels in first.items()
        if speech in second
        for ordinal in labels
        if ordinal in second[speech]
    ]
    fields = {}
    for field in COMPARED:
        same = sum(
            1 for speech, ordinal in shared
            if first[speech][ordinal][field] == second[speech][ordinal][field]
        )
        fields[field] = round(same / len(shared), 6) if shared else None
    return {"occurrences": len(shared), "agreement": fields}
