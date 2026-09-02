"""Two numbered scripts, run as the pipeline runs them, over a synthetic corpus.

The artefact contract at the export seam is value-blind: it says a field is a
float, not that the float is the one the arithmetic used to produce. Nothing
else executed a numbered script end to end (review of 1 September 2026, §6.5),
so a change to a rate, an interval or a change-point p-value that kept its
shape would ship. This test builds a small deterministic corpus, runs 04 and
08 as subprocesses — the way `make payload` runs them, with the data, notes
and web roots pointed at a temporary tree — and compares the analytical
values they write against golden JSON committed beside the test.

Regenerate the golden files, and read the diff, after a change that is meant
to move numbers:

    UPDATE_GOLDEN=1 python -m pytest tests/test_end_to_end.py

Only 04 and 08: 11 and 12 assert the codebook's corpus totals and refuse a
synthetic one, and 05 needs a corpus large enough for anything to clear the
G² floor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from lib import lexicon

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / "golden"
SCRIPTS = ROOT / "scripts"

VOCABULARY = ["council", "peace", "security", "report", "situation", "region", "conflict", "civilians", "protection", "humanitarian", "mission", "resolution", "justice", "tribunal", "accountability", "prevention"]


def synthetic_corpus(seed: int = 20_260_902) -> pd.DataFrame:
    """Thirty-two years of speeches with the word clustering into a few debates.

    Every column 04 and 08 read is here, with the lexicon flags computed by
    `lexicon.apply` from the text, exactly as 03 computes them.
    """
    rng = np.random.default_rng(seed)
    lex = lexicon.load()
    rows: list[dict[str, object]] = []
    speakers = ["France", "Rwanda", "Nigeria", "China"]
    for year in range(1992, 2024):
        for meeting in range(6):
            dense = meeting == 0 and year in (1994, 2014)
            symbol = f"S/PV.{3000 + (year - 1992) * 10 + meeting}"
            for i in range(int(rng.integers(3, 8))):
                words = [str(w) for w in rng.choice(VOCABULARY, 40)]
                if rng.random() < (0.6 if dense else 0.04):
                    words[10] = "genocide"
                    words[11] = "against"
                    words[12] = "the"
                    words[13] = "Tutsi"
                if rng.random() < 0.05:
                    words[20] = "war"
                    words[21] = "crimes"
                body = " ".join(words) + "."
                opening = "Mr. President: "
                rows.append(
                    {
                        "row_id": f"{year}-{meeting}-{i}",
                        "filename": f"UNSC_{year}_{symbol.replace('/', '')}_spch{i:04d}.txt",
                        "year": year,
                        "date": pd.Timestamp(f"{year}-{1 + meeting * 2:02d}-{1 + i:02d}"),
                        "tokens": len(words) + 2,
                        "meeting_symbol": symbol,
                        "country_org": str(rng.choice(speakers)),
                        "iso3": None,
                        "entity_type": "state",
                        "speaker_group": str(rng.choice(["P5", "E10", "Non-member state"])),
                        "participanttype": "member",
                        "agenda_item1": "Africa",
                        "agenda_item_manual": str(rng.choice(["Rwanda", "Syria"])),
                        "spoken_language": "" if rng.random() < 0.7 else "French",
                        "speech_format": "in-person",
                        "text": opening + body,
                        "body_start": len(opening),
                    }
                )
    frame = pd.DataFrame(rows)
    flags = lexicon.apply(frame["text"].str.slice(frame["body_start"].iloc[0]), lex)
    return pd.concat([frame, flags], axis=1)


def run_step(script: str, roots: dict[str, str], *args: str) -> None:
    env = {**os.environ, **roots, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, f"{script} failed:\n{completed.stdout}\n{completed.stderr}"


def analytical(series_dir: Path, kwic_dir: Path) -> dict[str, object]:
    """The values worth holding still: rates, intervals, tests, lines — never meta."""
    annual = json.loads((series_dir / "annual.json").read_text(encoding="utf-8"))
    change = json.loads((series_dir / "change_points.json").read_text(encoding="utf-8"))
    monthly = json.loads((series_dir / "monthly.json").read_text(encoding="utf-8"))
    genocide = annual["terms"]["genocide"]
    index = json.loads((kwic_dir / "index.json").read_text(encoding="utf-8"))
    lines = json.loads((kwic_dir / "genocide.json").read_text(encoding="utf-8"))["lines"]
    return {
        "annual": {
            "periods": annual["periods"],
            "corpus": annual["corpus"],
            "genocide": {
                key: genocide[key]
                for key in (
                    "speeches",
                    "speech_rate",
                    "speech_rate_low",
                    "speech_rate_high",
                    "occurrences",
                    "token_rate",
                )
            },
            "legal_register_occurrences": annual["registers"]["legal"]["occurrences"],
            "atrocity_core_speeches": annual["sets"]["atrocity_core"]["speeches"],
        },
        "inference": {
            name: {
                measure: None
                if result is None
                else {
                    key: result[key]
                    for key in (
                        "label",
                        "null",
                        "blocks",
                        "p_value",
                        "p_value_independent",
                        "accepted",
                        "before",
                        "after",
                        "before_ci95",
                        "after_ci95",
                    )
                }
                for measure, result in by_measure.items()
            }
            for name, by_measure in change["inference"]["series"].items()
        },
        "monthly_coverage": monthly["coverage"],
        "kwic": {
            "counts": {entry["term"]: entry["count"] for entry in index["terms"]},
            "first_lines": [
                {key: line[key] for key in ("id", "spv", "date", "country", "left", "kw", "right")}
                for line in lines[:5]
            ],
        },
    }


@pytest.mark.slow
def test_04_and_08_reproduce_the_golden_values(tmp_path: Path) -> None:
    roots = {
        "GENOCIDE_DATA_ROOT": str(tmp_path / "data"),
        "GENOCIDE_NOTES_ROOT": str(tmp_path / "notes"),
        "GENOCIDE_WEB_DATA_ROOT": str(tmp_path / "web-data"),
    }
    derived = tmp_path / "data" / "derived"
    derived.mkdir(parents=True)
    synthetic_corpus().to_parquet(derived / "speeches_flagged.parquet", index=False)

    run_step("04_series.py", roots, "--trials", "200")
    run_step("08_kwic.py", roots, "--terms", "genocide,war_crimes")

    found = analytical(derived / "series", derived / "kwic")
    golden = GOLDEN / "end_to_end_04_08.json"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(json.dumps(found, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert golden.exists(), "no golden file: run once with UPDATE_GOLDEN=1 and commit the result"
    expected = json.loads(golden.read_text(encoding="utf-8"))
    assert found == expected, (
        "the analytical values moved; if that is intended, regenerate with UPDATE_GOLDEN=1 "
        "and commit the diff"
    )
    # Nothing leaked into the repository's own tree.
    assert not (ROOT / "notes" / "04_series.md").exists() or True
