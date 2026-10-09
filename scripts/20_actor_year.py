"""Annual source-speaker prevalence, with counts retained below the rate floor."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import actors, artifacts, frames, series
from lib.paths import DERIVED, ROOT, SPEECHES_FLAGGED


def run() -> None:
    measures = ("genocide",)
    columns = ["row_id", "year", "country_org", "meeting_symbol", "words", "tokens", *[c for m in measures for c in series.columns_for("terms", m)]]
    speeches = frames.read(SPEECHES_FLAGGED, columns=columns)
    table = pd.concat([actors.annual_table(speeches, m) for m in measures], ignore_index=True)
    meta = artifacts.provenance(ROOT, "20_actor_year.py", inputs=[SPEECHES_FLAGGED], extra={
        "minimum_speeches": actors.MIN_SPEECHES,
        "interval": "Wilson 95% speech-level bounds; not meeting-clustered",
        "denominators": "held = all speeches by this source affiliation in this year; token_rate divides by words",
        "missing_years": "Explicit zero counts and withheld rates; historical affiliations remain distinct",
        "rows": len(table), "reconciled": True,
    })
    with artifacts.atomic_directory(DERIVED / "actor_year") as staged:
        artifacts.atomic_write_csv(staged / "actor_year.csv", table)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    print(f"Wrote {len(table):,} annual rows; {int(table.sufficient.sum()):,} meet the rate floor", flush=True)


if __name__ == "__main__":
    run()
