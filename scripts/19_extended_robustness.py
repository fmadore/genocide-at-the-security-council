"""Meeting influence and conditional block intervals for lexical rankings.

Run with --speakers Rwanda France for a bounded inspection; omit for all
eligible speakers. Outputs remain separate from the dashboard's primary tables.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, block_lexical, frames, keyness, lexical, lexicon, uncertainty
from lib.paths import DERIVED, LEXICON, ROOT, SPEECHES_FLAGGED, STOPWORDS


def run(repetitions: int, seed: int, speakers: list[str] | None, limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be positive")
    lex = lexicon.load()
    nodes = [lex.terms[name] for name in ["genocide", "ethnic_cleansing", "crimes_against_humanity"]]
    corpus = frames.read(SPEECHES_FLAGGED, columns=[
        "row_id", "text", "body_start", "country_org", "meeting_symbol", *keyness.MATCH_ON,
        *[f"has_{node.name}" for node in nodes],
    ])
    bodies = frames.body(corpus)
    matrix = keyness.build(bodies)
    reference = matrix.counter(np.arange(len(corpus)))
    corpus["stratum"] = keyness.strata(corpus)
    all_rows = np.arange(len(corpus))
    influence_rows, interval_rows, selections, primary_rows = [], [], [], []

    def analyse(kind, name, primary, target, control, occurrences=None):
        words = [row["word"] for row in primary]
        if not words:
            return
        primary_rows.extend({"kind": kind, "profile": name, "rank": i, **row} for i, row in enumerate(primary, 1))
        influence_rows.extend({"kind": kind, "profile": name, **row} for row in block_lexical.influence(target, control, words, occurrences))
        interval_rows.extend({"kind": kind, "profile": name, **row} for row in uncertainty.bootstrap_ratios(target, control, words, seed=seed, repetitions=repetitions))
        print(kind, name, len(words), "words", flush=True)

    stopwords = lexical.load_stopwords()
    pairs = lexical.matched_control(corpus, "has_genocide", keyness.MATCH_ON, seed)
    target_rows, control_rows = pairs.target_index.to_numpy(), pairs.control_index.to_numpy()
    a, b = matrix.counter(target_rows), matrix.counter(control_rows)
    primary = lexical.compare(a, a + b, sum(a.values()), sum(b.values()), stopwords, limit=limit)
    words = [row["word"] for row in primary]
    analyse("matched", "genocide", primary, block_lexical.blocks(matrix, corpus, target_rows, words), block_lexical.blocks(matrix, corpus, control_rows, words))
    for node in nodes:
        holders = corpus[corpus[f"has_{node.name}"]]
        tokenized = [(index, lexical.tokenise(bodies[index]), node.spans(bodies[index])) for index in holders.index]
        for width in (5, 8, 15):
            documents, meetings, occurrences = [], [], Counter()
            window = Counter()
            for index, tokens, spans in tokenized:
                counts = Counter(tokens.context(spans, width))
                documents.append(counts)
                meeting = corpus.loc[index, "meeting_symbol"]
                meetings.append(meeting)
                occurrences[meeting] += len(spans)
                window.update(counts)
            node_total = sum(occurrences.values())
            primary = lexical.compare(window, reference, sum(window.values()), sum(reference.values()) - sum(window.values()), stopwords, limit=limit, rank="log_dice", extra=lambda word, count, n=node_total: {"log_dice": lexical.log_dice(count, n, reference[word])})
            words = [row["word"] for row in primary]
            target = uncertainty.meeting_blocks(documents, meetings, words)
            whole = block_lexical.blocks(matrix, corpus, all_rows, words)
            control = {meeting: counts - target.get(meeting, np.zeros(len(words) + 1)) for meeting, counts in whole.items()}
            analyse("collocate", f"{node.name}/{width}", primary, target, control, occurrences)
    counts = corpus["country_org"].value_counts()
    selected = speakers if speakers is not None else counts[counts >= keyness.MIN_PAIRS].index.tolist()
    for speaker in selected:
        targets, controls, pairing = keyness.pair_speaker(corpus, corpus["country_org"].eq(speaker), "stratum", seed)
        sufficient = pairing.pairs >= keyness.MIN_PAIRS and pairing.coverage >= keyness.MIN_COVERAGE
        selections.append({"speaker": speaker, "pairs": pairing.pairs, "coverage": pairing.coverage, "sufficient": sufficient})
        if not sufficient:
            continue
        a, b = matrix.counter(targets.to_numpy()), matrix.counter(controls.to_numpy())
        primary = lexical.compare(a, a + b, sum(a.values()), sum(b.values()), stopwords, limit=limit)
        words = [row["word"] for row in primary]
        analyse("speaker", str(speaker), primary, block_lexical.blocks(matrix, corpus, targets.to_numpy(), words), block_lexical.blocks(matrix, corpus, controls.to_numpy(), words))
    meta = artifacts.provenance(ROOT, "19_extended_robustness.py", inputs=[SPEECHES_FLAGGED], configs=[STOPWORDS, LEXICON, Path(__file__), *[ROOT / f"scripts/lib/{name}.py" for name in ("block_lexical", "uncertainty", "lexical", "keyness", "frames", "lexicon")]], extra={
        "seed": seed, "repetitions": repetitions, "limit": limit, "speakers": speakers,
        "interval": "95% percentile meeting-block bootstrap conditional on fixed selected speeches and ranked words; same meeting weights in both arms; no rematching",
        "effect": "log2 token-rate ratio; logDice has deletion ranges only",
        "assumption": "Hypothetical exchangeable meetings, not uncertainty in the exhaustive historical corpus counts",
        "minimum_arm_meetings": 20, "minimum_word_support_meetings": 5,
        "invalid_draws": "Zero words/denominators are undefined; withhold if more than 5% undefined; no half counts in bootstrap",
    })
    with artifacts.atomic_directory(DERIVED / "extended_robustness") as staged:
        pd.DataFrame(influence_rows).to_csv(staged / "meeting_influence.csv", index=False)
        pd.DataFrame(interval_rows).to_csv(staged / "intervals.csv", index=False)
        pd.DataFrame(selections).to_csv(staged / "speaker_coverage.csv", index=False)
        pd.DataFrame(primary_rows).to_csv(staged / "rankings.csv", index=False)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=999)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--speakers", nargs="+")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    run(args.repetitions, args.seed, args.speakers, args.limit)
