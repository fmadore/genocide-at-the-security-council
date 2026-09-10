"""Annual source-speaker prevalence, with counts retained below the rate floor."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import actors, artifacts, frames, series
from lib.paths import DERIVED, ROOT, SPEECHES_FLAGGED


def annual_table(speeches: pd.DataFrame, measure: str, minimum: int = actors.MIN_SPEECHES) -> pd.DataFrame:
    if minimum < 1 or speeches.empty:
        raise ValueError("a positive minimum and a nonempty corpus are required")
    if speeches[["row_id", "year", "country_org", "meeting_symbol"]].isna().any().any() or speeches.row_id.duplicated().any():
        raise ValueError("annual tables require unique speech IDs and complete grouping fields")
    has, count = series.columns_for("terms", measure)
    speakers = sorted(speeches.country_org.unique())
    tables = []
    for year in range(int(speeches.year.min()), int(speeches.year.max()) + 1):
        selected = speeches[speeches.year.eq(year)]
        table = actors.by_country(selected, has, count).reindex(speakers)
        for column in ("held", "words", "tokens", "meetings", "speeches", "occurrences"):
            table[column] = table[column].fillna(0).astype(int)
        table = actors.withhold_below(table, minimum)
        table["withheld_reason"] = ["no speeches" if n == 0 else "below minimum" if n < minimum else "" for n in table.held]
        if int(table.held.sum()) != len(selected) or int(table.speeches.sum()) != int(selected[has].sum()) or int(table.occurrences.sum()) != int(selected[count].sum()) or int(table.words.sum()) != int(selected.words.sum()):
            raise ValueError(f"annual totals do not reconcile for {year}")
        tables.append(table.assign(year=year, measure=measure).reset_index(names="country_org"))
    return pd.concat(tables, ignore_index=True)


def run() -> None:
    measures = ("genocide_qualification", "genocide")
    columns = ["row_id", "year", "country_org", "meeting_symbol", "words", "tokens", *[c for m in measures for c in series.columns_for("terms", m)]]
    speeches = frames.read(SPEECHES_FLAGGED, columns=columns)
    table = pd.concat([annual_table(speeches, m) for m in measures], ignore_index=True)
    meta = artifacts.provenance(ROOT, "20_actor_year.py", inputs=[SPEECHES_FLAGGED], configs=[Path(__file__), ROOT / "scripts/lib/actors.py", ROOT / "scripts/lib/series.py"], extra={
        "minimum_speeches": actors.MIN_SPEECHES,
        "interval": "Wilson 95% speech-level bounds; not meeting-clustered",
        "denominators": "held = all speeches by this source affiliation in this year; token_rate divides by words",
        "missing_years": "Explicit zero counts and withheld rates; historical affiliations remain distinct",
        "rows": len(table), "reconciled": True,
    })
    with artifacts.atomic_directory(DERIVED / "actor_year") as staged:
        table.to_csv(staged / "actor_year.csv", index=False)
        artifacts.atomic_write_json(staged / "manifest.json", meta, indent=2)
    print(f"Wrote {len(table):,} annual rows; {int(table.sufficient.sum()):,} meet the rate floor", flush=True)


if __name__ == "__main__":
    run()
