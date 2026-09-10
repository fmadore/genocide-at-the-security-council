"""Meeting-level lexical counts from the shared sparse document matrix."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import lexical


def blocks(matrix, frame: pd.DataFrame, rows: np.ndarray, words: list[str]) -> dict[str, np.ndarray]:
    names = frame.loc[rows, "meeting_symbol"]
    if names.isna().any() or names.astype(str).str.strip().eq("").any():
        raise ValueError("every selected speech needs a meeting symbol")
    codes, labels = pd.factorize(names, sort=True)
    output = np.zeros((len(labels), len(words) + 1))
    wanted = {word: i for i, word in enumerate(words)}
    lookup = np.asarray([wanted.get(word, -1) for word in matrix.words], dtype=np.int32)
    for row, code in zip(rows, codes, strict=True):
        start, end = matrix.indptr[row:row + 2]
        counts = matrix.counts[start:end]
        cols = lookup[matrix.terms[start:end]]
        keep = cols >= 0
        np.add.at(output[code], cols[keep], counts[keep])
        output[code, -1] += counts.sum()
    return {str(label): output[i] for i, label in enumerate(labels)}


def influence(target: dict, control: dict, words: list[str], nodes: dict | None = None) -> list[dict]:
    """Deletion summaries for ratios and, for collocates, logDice.

    Counts and eligibility are recomputed after removing a meeting from both
    arms. No rematching or reranking. Undefined effects are counted explicitly.
    """
    names = sorted(set(target) | set(control))
    zero = np.zeros(len(words) + 1)
    a = np.asarray([target.get(name, zero) for name in names])
    b = np.asarray([control.get(name, zero) for name in names])
    left, right = a.sum(axis=0) - a, b.sum(axis=0) - b
    valid_arms = (left[:, -1] > 0) & (right[:, -1] > 0)
    rows = []
    for i, word in enumerate(words):
        values, dice, eligible = [], [], 0
        for j, name in enumerate(names):
            if not valid_arms[j]:
                continue
            x, y, n, m = left[j, i], right[j, i], left[j, -1], right[j, -1]
            if x + y > 0:
                values.append((lexical.log_ratio(x, y, n, m), name))
            eligible += x >= lexical.MIN_COUNT and abs(lexical.log_likelihood(x, y, n, m)) >= lexical.G2_FLOOR
            if nodes is not None and x > 0:
                remaining_nodes = sum(nodes.values()) - nodes.get(name, 0)
                if remaining_nodes > 0:
                    dice.append(lexical.log_dice(x, remaining_nodes, x + y))
        base = lexical.log_ratio(a[:, i].sum(), b[:, i].sum(), a[:, -1].sum(), b[:, -1].sum())
        rows.append({
            "word": word, "log_ratio": base,
            "valid_deletions": int(valid_arms.sum()), "defined_effects": len(values),
            "eligible_deletions": int(eligible),
            "loo_min": min((x for x, _ in values), default=None),
            "loo_max": max((x for x, _ in values), default=None),
            "largest_change_meeting": max(values, key=lambda item: abs(item[0] - base))[1] if values else None,
            "sign_reversals": sum(x * base < 0 for x, _ in values),
            "log_dice_min": min(dice, default=None), "log_dice_max": max(dice, default=None),
        })
    return rows
