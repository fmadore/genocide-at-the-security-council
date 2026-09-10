"""Descriptive sensitivity of a fixed matched keyness comparison.

These are influence diagnostics, not confidence intervals. Deleting a meeting
removes its selected speeches from both arms, without drawing new controls.
This isolates the meeting's contribution; remaining arms need not be balanced.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from . import lexical

# Exact rule from abdc08a, before the tokenizer repair in 54df825.
LEGACY_TOKEN_RE = re.compile("[a-z][a-z'" + chr(0x2019) + "-]*")


def ranked(target: Counter, control: Counter, stopwords: frozenset[str], limit: int = 100):
    return lexical.compare(
        target, target + control, sum(target.values()), sum(control.values()),
        stopwords, limit=limit,
    )


def meeting_influence(
    target_documents: Sequence[Counter],
    control_documents: Sequence[Counter],
    target_meetings: Sequence[str],
    control_meetings: Sequence[str],
    words: Sequence[str],
) -> tuple[list[dict], list[dict]]:
    """All leave-one-meeting-out effects for preselected words, plus exclusions.

    Invalid replicates (an empty arm) are explicitly excluded. Absence of a word
    from both arms yields no effect, not a ratio of two artificial half-counts.
    Eligibility is recomputed using the primary count and G² floors, but words
    are not reselected. No percentile here has a sampling interpretation.
    """
    totals = [Counter(), Counter()]
    blocks: dict[str, list[Counter]] = {}
    for arm, (documents, meetings) in enumerate(
        ((target_documents, target_meetings), (control_documents, control_meetings))
    ):
        for counts, meeting in zip(documents, meetings, strict=True):
            if not isinstance(meeting, str) or not meeting.strip():
                raise ValueError("every selected speech needs a nonempty meeting symbol")
            totals[arm].update(counts)
            blocks.setdefault(meeting, [Counter(), Counter()])[arm].update(counts)
    sizes = [sum(counts.values()) for counts in totals]
    effects, deletions = [], []
    for meeting, removed in sorted(blocks.items()):
        remaining = [sizes[i] - sum(removed[i].values()) for i in range(2)]
        valid = all(size > 0 for size in remaining)
        deletions.append({
            "meeting": meeting, "target_tokens": remaining[0],
            "control_tokens": remaining[1], "valid": valid,
            "exclusion": None if valid else "empty arm after deletion",
        })
        if not valid:
            continue
        for word in words:
            a, b = [totals[i][word] - removed[i][word] for i in range(2)]
            g2 = lexical.log_likelihood(a, b, *remaining)
            effects.append({
                "word": word, "meeting": meeting, "target": a, "control": b,
                "log_ratio": lexical.log_ratio(a, b, *remaining) if a + b else None,
                "eligible": a >= lexical.MIN_COUNT and abs(g2) >= lexical.G2_FLOOR,
            })
    return effects, deletions


def tokenizer_comparison(current: list[dict], legacy: list[dict]) -> list[dict]:
    """Full outer join of ranked lists; missing ranks mean not selected."""
    left = {row["word"]: (rank, row) for rank, row in enumerate(current, 1)}
    right = {row["word"]: (rank, row) for rank, row in enumerate(legacy, 1)}
    return [
        {
            "word": word,
            "current_rank": left[word][0] if word in left else None,
            "legacy_rank": right[word][0] if word in right else None,
            "current_log_ratio": left[word][1]["log_ratio"] if word in left else None,
            "legacy_log_ratio": right[word][1]["log_ratio"] if word in right else None,
        }
        for word in dict.fromkeys([*left, *right])
    ]


def influence_summary(primary: list[dict], effects: list[dict], totals: Sequence[int]) -> list[dict]:
    """Summarise deletions in one pass, retaining undefined effects as failures.

    Group once rather than scanning the full deletion table for every keyword.
    Tied largest changes retain the first (meeting-sorted) deletion.
    """
    grouped = defaultdict(list)
    for effect in effects:
        grouped[effect["word"]].append(effect)
    rows = []
    for row in primary:
        values = grouped[row["word"]]
        defined = [value for value in values if value["log_ratio"] is not None]
        baseline = lexical.log_ratio(row["target"], row["reference"], *totals)
        rows.append({
            **row, "valid_deletions": len(values), "defined_effects": len(defined),
            "eligible_deletions": sum(value["eligible"] for value in values),
            "loo_min": min((value["log_ratio"] for value in defined), default=None),
            "loo_max": max((value["log_ratio"] for value in defined), default=None),
            "largest_change_meeting": max(
                defined, key=lambda value: abs(value["log_ratio"] - baseline),
            )["meeting"] if defined else None,
            "sign_reversals": sum(value["log_ratio"] * baseline < 0 for value in defined),
        })
    return rows
