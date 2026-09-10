"""Audit matched genocide keyness without replacing the published tables.

Run: python scripts/18_lexical_robustness.py [--seed 20260807] [--limit 100]
Outputs data/derived/lexical_robustness/: full deletion effects in parquet,
summary and tokenizer CSVs, selected speech IDs and a provenance manifest.
With --lemma-layer DIRECTORY, also compare validated lemmas, recording all
changed forms and stopword leaks in a separate lexical_robustness_lemma/ output.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, frames, lemmas, lexical, robustness
from lib.paths import DERIVED, ROOT, SPEECHES_FLAGGED, STOPWORDS

MATCH_ON = ["year", "agenda_item_manual", "speaker_group"]
EFFECT_COLUMNS = ["word", "meeting", "target", "control", "log_ratio", "eligible"]


def run(seed: int, limit: int, lemma_layer: Path | None = None) -> None:
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
    lemma_comparison = None
    lemma_forms = None
    lemma_meta = None
    lemma_effects = None
    lemma_summary = None
    if lemma_layer is not None:
        selected = pd.concat(arms)
        layer = lemmas.load_layer(lemma_layer, selected)
        lemma_documents = [[Counter(lemmas.decode(row)) for row in layer.loc[arm.index]] for arm in arms]
        lemma_counts = [lemmas.vocabulary(layer.loc[arm.index]) for arm in arms]
        if [sum(counts.values()) for counts in lemma_counts] != [sum(counts.values()) for counts in totals]:
            raise ValueError("surface/lemma token denominators differ")
        lemma_primary = robustness.ranked(*lemma_counts, stopwords, limit)
        lemma_comparison = [
            {key.replace("current_", "surface_").replace("legacy_", "lemma_"): value
             for key, value in row.items()}
            for row in robustness.tokenizer_comparison(
                primary, lemma_primary
            )
        ]
        lemma_forms = lemmas.mapping(frames.body(selected), layer)
        changed_forms = Counter()
        for form in lemma_forms:
            changed_forms[form["surface"]] += form["occurrences"]
        for row in lemma_comparison:
            word = row["word"]
            unchanged = totals[0][word] + totals[1][word] - changed_forms[word]
            row.update({
                "surface_target": totals[0][word], "surface_control": totals[1][word],
                "lemma_target": lemma_counts[0][word], "lemma_control": lemma_counts[1][word],
                "unchanged_surface_tokens": unchanged,
                "partly_lemmatized": changed_forms[word] > 0 and unchanged > 0,
            })
        lemma_effects, _ = robustness.meeting_influence(
            *lemma_documents, *(arm["meeting_symbol"].tolist() for arm in arms),
            [row["word"] for row in lemma_primary],
        )
        lemma_summary = robustness.influence_summary(
            lemma_primary, lemma_effects, [sum(counts.values()) for counts in lemma_counts],
        )
        lemma_meta = {
            "selected_speeches": len(selected),
            "ranked_words": len(lemma_primary),
            "exact_type_overlap": len({row["word"] for row in primary} & {row["word"] for row in lemma_primary}),
            "layer": artifacts.describe_file(lemma_layer / "manifest.json", ROOT),
            "table": artifacts.describe_file(lemma_layer / "lemmas.parquet", ROOT),
            "stopword_policy": "Same surface stoplist in both representations; all observed stopword-to-nonstopword merges reported, not silently filtered.",
            "stopword_leaks": lemmas.stopword_check(stopwords, lemma_forms),
            "comparison": "Exact type overlap of independently ranked top lists, not semantic equivalence or a rank correlation across unlike vocabularies.",
            "partial_collapse": "partly_lemmatized flags surface types with both changed and unchanged occurrences; context-sensitive tagging can leave a high-ranking residue. It does not by itself establish an error.",
            "tokens": [sum(counts.values()) for counts in lemma_counts],
        }
    effects, deletions = robustness.meeting_influence(
        *documents, *(arm["meeting_symbol"].tolist() for arm in arms),
        [row["word"] for row in primary],
    )
    effect_table = pd.DataFrame(effects, columns=EFFECT_COLUMNS)
    summary = robustness.influence_summary(primary, effects, [sum(counts.values()) for counts in totals])
    meta = artifacts.provenance(
        ROOT, "18_lexical_robustness.py", inputs=[SPEECHES_FLAGGED],
        configs=[STOPWORDS, Path(__file__), ROOT / "scripts/lib/robustness.py",
                 ROOT / "scripts/lib/lexical.py", ROOT / "scripts/lib/frames.py",
                 ROOT / "scripts/lib/lemmas.py"],
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
            "lemma_sensitivity": lemma_meta,
        },
    )
    target = DERIVED / ("lexical_robustness_lemma" if lemma_layer else "lexical_robustness")
    with artifacts.atomic_directory(target) as staged:
        pd.DataFrame(summary).to_csv(staged / "meeting_influence.csv", index=False)
        pd.DataFrame(deletions).to_csv(staged / "deletions.csv", index=False)
        effect_table.to_parquet(staged / "deletion_effects.parquet", index=False)
        pd.DataFrame(comparison).to_csv(staged / "tokenizer_comparison.csv", index=False)
        if lemma_comparison is not None:
            pd.DataFrame(lemma_comparison).to_csv(staged / "lemma_comparison.csv", index=False)
            pd.DataFrame(lemma_summary, columns=list(summary[0])).to_csv(staged / "lemma_meeting_influence.csv", index=False)
            pd.DataFrame(lemma_effects, columns=EFFECT_COLUMNS).to_parquet(staged / "lemma_deletion_effects.parquet", index=False)
            pd.DataFrame(lemma_forms, columns=[
                "surface", "lemma", "occurrences", "forms_merged_into_lemma",
            ]).to_csv(staged / "lemma_forms.csv", index=False)
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
    parser.add_argument("--lemma-layer", type=Path, help="validated step-10 output directory")
    args = parser.parse_args()
    run(args.seed, args.limit, args.lemma_layer)
