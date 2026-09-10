"""Audit matched genocide keyness without replacing the published tables.

Run: python scripts/18_lexical_robustness.py [--seed 20260807] [--limit 100]
Outputs data/derived/lexical_robustness/: full deletion effects in parquet,
summary and tokenizer CSVs, selected speech IDs and a provenance manifest.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, frames, lexical, robustness
from lib.paths import DERIVED, ROOT, SPEECHES_FLAGGED, STOPWORDS

MATCH_ON = ["year", "agenda_item_manual", "speaker_group"]


def run(seed: int, limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be positive")
    speeches = frames.read(SPEECHES_FLAGGED, columns=[
        "row_id", "text", "body_start", "meeting_symbol", "has_genocide", *MATCH_ON,
    ])
    pairs = lexical.matched_control(speeches, "has_genocide", MATCH_ON, seed)
    if not pairs.matched:
        raise ValueError("no matched speeches")
    arms = [speeches.loc[index] for index in (pairs.target_index, pairs.control_index)]
    bodies = [frames.body(arm) for arm in arms]
    documents = [lexical.document_vocabulary(body) for body in bodies]
    totals = [Counter() for _ in arms]
    for total, counts in zip(totals, documents, strict=True):
        for count in counts:
            total.update(count)
    stopwords = lexical.load_stopwords()
    primary = robustness.ranked(*totals, stopwords, limit)
    if not primary:
        raise ValueError("no primary words pass the configured floors")
    legacy = [Counter() for _ in arms]
    for total, body in zip(legacy, bodies, strict=True):
        for text in body:
            total.update(robustness.LEGACY_TOKEN_RE.findall(text.lower()))
    comparison = robustness.tokenizer_comparison(
        primary, robustness.ranked(*legacy, stopwords, limit)
    )
    effects, deletions = robustness.meeting_influence(
        *documents, *(arm["meeting_symbol"].tolist() for arm in arms),
        [row["word"] for row in primary],
    )
    effect_table = pd.DataFrame(effects)
    summary = []
    for row in primary:
        values = effect_table[effect_table["word"] == row["word"]] if effects else pd.DataFrame()
        defined = values.dropna(subset=["log_ratio"]) if effects else values
        baseline = lexical.log_ratio(
            totals[0][row["word"]], totals[1][row["word"]],
            *(sum(total.values()) for total in totals),
        )
        summary.append({
            **row, "valid_deletions": len(values), "defined_effects": len(defined),
            "eligible_deletions": int(values["eligible"].sum()) if len(values) else 0,
            "loo_min": float(defined["log_ratio"].min()) if len(defined) else None,
            "loo_max": float(defined["log_ratio"].max()) if len(defined) else None,
            "largest_change_meeting": (
                defined.loc[(defined["log_ratio"] - baseline).abs().idxmax(), "meeting"]
                if len(defined) else None
            ),
            "sign_reversals": int((defined["log_ratio"] * baseline < 0).sum())
            if len(defined) else 0,
        })
    meta = artifacts.provenance(
        ROOT, "18_lexical_robustness.py", inputs=[SPEECHES_FLAGGED],
        configs=[STOPWORDS, Path(__file__), ROOT / "scripts/lib/robustness.py",
                 ROOT / "scripts/lib/lexical.py", ROOT / "scripts/lib/frames.py"],
        extra={
            "seed": seed, "limit": limit, "matched_on": MATCH_ON,
            "matched_pairs": pairs.matched, "eligible_targets": pairs.wanted,
            "coverage": pairs.coverage, "unit": "meeting_symbol",
            "short_strata": [
                {"key": list(map(str, key)), "wanted": wanted, "found": found}
                for key, wanted, found in pairs.short_strata
            ],
            "repetitions": len(deletions),
            "excluded_deletions": sum(not row["valid"] for row in deletions),
            "method": "Delete each meeting from both fixed matched arms; no rematching.",
            "interpretation": "Descriptive influence ranges, not confidence intervals; no sampling or model uncertainty.",
            "failure_rules": "Missing meeting IDs abort; empty arms excluded; absent in both arms gives null effect.",
            "selection": "Primary top words fixed; count/G2 eligibility recomputed, ranks not recomputed on deletion.",
            "minimum_count": lexical.MIN_COUNT, "g2_floor": lexical.G2_FLOOR,
            "zero_count_rule": "Half-occurrence floor for a word present in only one arm.",
            "current_tokenizer": lexical.TOKEN_RE.pattern,
            "legacy_tokenizer": robustness.LEGACY_TOKEN_RE.pattern,
            "legacy_source": "abdc08a:scripts/lib/lexical.py (before 54df825)",
            "current_tokens": [sum(total.values()) for total in totals],
            "legacy_tokens": [sum(total.values()) for total in legacy],
            "scope": "Matched genocide speech-body keyness only; not collocates, speaker keyness, or prevalence.",
        },
    )
    target = DERIVED / "lexical_robustness"
    with artifacts.atomic_directory(target) as staged:
        pd.DataFrame(summary).to_csv(staged / "meeting_influence.csv", index=False)
        pd.DataFrame(deletions).to_csv(staged / "deletions.csv", index=False)
        effect_table.to_parquet(staged / "deletion_effects.parquet", index=False)
        pd.DataFrame(comparison).to_csv(staged / "tokenizer_comparison.csv", index=False)
        pd.DataFrame({
            "target_row_id": arms[0]["row_id"].to_numpy(),
            "control_row_id": arms[1]["row_id"].to_numpy(),
        }).to_csv(staged / "pairs.csv", index=False)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    print(f"Wrote {target}: {pairs.matched} pairs, {len(deletions)} deletions, {len(primary)} words")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    run(args.seed, args.limit)
