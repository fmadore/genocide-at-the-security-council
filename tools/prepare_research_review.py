"""Build an unscored R1/R10 reading packet from archived model evidence.

This writes only to data/interim. Candidate cues select quotations for people
to read; they are never labels, an active lexicon, or a published comparison.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, llm
from lib.paths import INTERIM, MODEL_ANNOTATIONS, ROOT

CUES = {
    "armed_conflict": r"\b(?:war|armed conflict|fighting)\b",
    "persecution": r"\bpersecut\w*",
    "economic_sanctions": r"\b(?:sanctions|embargo|blockade)\b",
    "intervention_or_occupation": r"\b(?:intervention|occupation)\b",
    "colonial_rule": r"\bcoloni\w*",
    "famine_or_starvation": r"\b(?:famine|starvation|hunger)\b",
    "forced_displacement": r"\b(?:displacement|deportation|expulsion)\b",
    "multiple_referents": r"\b(?:and|both)\b",
    "terrorism": r"\bterroris\w*",
    "humanitarian": r"\bhumanitarian\b",
}


def select(rows: list[dict], limit: int = 8) -> dict[str, list[dict]]:
    packet: dict[str, list[dict]] = {cue: [] for cue in CUES}
    patterns = {cue: re.compile(pattern, re.I) for cue, pattern in CUES.items()}
    seen: dict[str, set[str]] = {cue: set() for cue in CUES}
    for row in rows:
        if not row.get("evidence_valid"):
            continue
        quote = str(row.get("evidence_quote", ""))
        identifier = str(row["occurrence_id"])
        for cue, pattern in patterns.items():
            text = str(row.get("proposed_referent", "")) if cue == "multiple_referents" else quote
            if len(packet[cue]) >= limit or identifier in seen[cue] or not pattern.search(text):
                continue
            seen[cue].add(identifier)
            packet[cue].append({key: row.get(key) for key in (
                "occurrence_id", "line_id", "run_id", "source_sha256", "evidence_quote",
                "referent", "proposed_referent", "evidence_start", "evidence_end",
            )})
    return packet


def main() -> None:
    sources = sorted((MODEL_ANNOTATIONS / "genocide" / "runs").glob("*/annotations.jsonl"))
    rows = [row for source in sources for row in llm.read_rows(source)]
    packet = select(rows)
    destination = INTERIM / "research_review" / "candidates.json"
    artifacts.atomic_write_json(destination, {
        "status": "unscored_review_candidates",
        "warning": "Historical model quotations, not current-corpus truth or approved labels. Read the source before coding. Missing cues are not evidence of absence.",
        "meta": artifacts.provenance(ROOT, "prepare_research_review.py", inputs=sources),
        "cues": CUES,
        "candidates": packet,
    }, indent=2)
    print(destination)
    for cue, candidates in packet.items():
        print(f"{cue}: {len(candidates)} candidates")


if __name__ == "__main__":
    main()
