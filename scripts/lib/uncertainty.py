"""Conditional meeting-block bootstrap for a fixed vocabulary comparison.

The same sampled multiplicity weights both arms of each meeting. These intervals
condition on the chosen speeches and vocabulary, not on the matching or ranking
procedure. They describe a hypothetical population of exchangeable meetings;
they are not uncertainty about the recorded corpus counts or historical truth.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def meeting_blocks(documents, meetings, words: Sequence[str]) -> dict[str, np.ndarray]:
    """Word counts plus the complete token denominator, aggregated by meeting."""
    blocks = {}
    for counts, meeting in zip(documents, meetings, strict=True):
        if not isinstance(meeting, str) or not meeting.strip():
            raise ValueError("each speech needs a meeting symbol")
        block = blocks.setdefault(meeting, np.zeros(len(words) + 1, dtype=np.float64))
        block[:-1] += [counts[word] for word in words]
        block[-1] += sum(counts.values())
    return blocks


def bootstrap_ratios(
    target: dict[str, np.ndarray], control: dict[str, np.ndarray], words: Sequence[str],
    *, seed: int = 20260910, repetitions: int = 999, minimum_meetings: int = 20,
    minimum_support: int = 5,
) -> list[dict]:
    """Percentile 95% intervals, withheld for sparse support or >5% invalid draws.

    No half-count substitution: a zero word count in either sampled arm makes
    that word's draw undefined. All invalid counts remain in the output.
    Support thresholds are conservative reporting rules, not a calibration
    guarantee. Empty arms and nonfinite input are refused or explicitly withheld.
    """
    if repetitions < 200 or minimum_meetings < 2 or minimum_support < 1:
        raise ValueError("use at least 200 repetitions, 2 meetings and 1 support meeting")
    names = sorted(set(target) | set(control))
    if not names:
        raise ValueError("no meetings")
    zero = np.zeros(len(words) + 1)
    a = np.asarray([target.get(name, zero) for name in names])
    b = np.asarray([control.get(name, zero) for name in names])
    for block in (a, b):
        if (block.shape != (len(names), len(words) + 1)
                or not np.isfinite(block).all() or (block < 0).any()
                or (block[:, :-1] > block[:, -1:]).any()):
            raise ValueError("invalid meeting counts or denominators")
    support_a, support_b = (a[:, :-1] > 0).sum(axis=0), (b[:, :-1] > 0).sum(axis=0)
    arms_sufficient = min((a[:, -1] > 0).sum(), (b[:, -1] > 0).sum()) >= minimum_meetings
    eligible = (support_a >= minimum_support) & (support_b >= minimum_support) & arms_sufficient
    samples = np.full((repetitions, len(words)), np.nan)
    rng = np.random.default_rng(seed)
    if eligible.any():
        for start in range(0, repetitions, 32):
            size = min(32, repetitions - start)
            weights = rng.multinomial(len(names), np.full(len(names), 1 / len(names)), size=size)
            ta, tb = weights @ a, weights @ b
            with np.errstate(divide="ignore", invalid="ignore"):
                values = np.log2((ta[:, :-1] / ta[:, -1:]) / (tb[:, :-1] / tb[:, -1:]))
            valid = np.isfinite(values) & (ta[:, :-1] > 0) & (tb[:, :-1] > 0) & eligible
            samples[start:start + size] = np.where(valid, values, np.nan)
    rows = []
    for i, word in enumerate(words):
        values = samples[:, i]
        values = values[np.isfinite(values)]
        reason = (
            "too few meetings in an arm" if not arms_sufficient else
            "too few word-supporting meetings in an arm" if not eligible[i] else
            "more than 5% undefined draws" if len(values) < repetitions * .95 else None
        )
        low, high = np.quantile(values, [.025, .975]) if reason is None else (None, None)
        rows.append({
            "word": word, "low": float(low) if low is not None else None,
            "high": float(high) if high is not None else None,
            "target_support_meetings": int(support_a[i]), "control_support_meetings": int(support_b[i]),
            "valid_repetitions": len(values), "repetitions": repetitions,
            "withheld_because": reason,
        })
    return rows
