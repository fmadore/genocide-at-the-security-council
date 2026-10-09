"""Three numbered scripts, run as the pipeline runs them, over a synthetic corpus.

The artefact contract at the export seam is value-blind: it says a field is a
float, not that the float is the one the arithmetic used to produce. Nothing
else executed a numbered script end to end (review of 1 September 2026, §6.5),
so a change to a rate, an interval or a change-point p-value that kept its
shape would ship. This test builds a small deterministic corpus, runs 04, 08
and 17 as subprocesses — the way `make payload` runs them, with the data, notes
and web roots pointed at a temporary tree — and compares the analytical
values they write against golden JSON committed beside the test.

Regenerate the golden files, and read the diff, after a change that is meant
to move numbers:

    UPDATE_GOLDEN=1 python -m pytest tests/test_end_to_end.py

Only 04, 08 and 17: 11 and 12 assert the codebook's corpus totals and refuse a
synthetic one, and 05 needs a corpus large enough for anything to clear the
G² floor. 17 runs with `--no-model`, because the committed runs annotate the
real corpus's occurrence ids and would join none of a synthetic one — which is
a refusal the step makes on purpose and not something to work around here.
"""

from __future__ import annotations

import json
import math
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
                        # `words` is the denominator 04 divides by, counted on
                        # the body as 02 counts it; `tokens` is the codebook's
                        # figure over the whole text, which is larger here for
                        # the same reason it is larger in the corpus — the
                        # form of address and the full stop are tokens and not
                        # words.
                        "words": len(words),
                        "tokens": len(words) + 4,
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


#: Golden floats are compared to one part in a billion rather than to the last
#: digit: the file is written on one platform and checked on another (Windows on
#: ARM locally, Linux in CI), and a summation order that differs by a rounding
#: step is not a change in what the arithmetic says.
RELATIVE_TOLERANCE = 1e-9
#: A value that should be zero has no scale for a relative tolerance to work
#: with, so a residue this small on either side of it still counts as zero.
ABSOLUTE_TOLERANCE = 1e-12

#: Where a step that ignored the environment would write. All three are ignored
#: by git, so `git status` alone cannot see a leak into them.
OUTPUT_ROOTS = ("data", "notes", "web/static")


def mismatches(found: object, expected: object, at: str = "$") -> list[str]:
    """Every place two JSON values differ, floats within the tolerance above.

    Keys, list lengths, strings, booleans and nulls must match exactly; a float
    on either side is compared numerically, so `1` and `1.0` agree.
    """
    numeric = (int, float)
    if isinstance(expected, dict) and isinstance(found, dict):
        if set(found) != set(expected):
            return [
                f"{at}: keys differ (only found: {sorted(set(found) - set(expected))}, "
                f"only expected: {sorted(set(expected) - set(found))})"
            ]
        return [m for key in expected for m in mismatches(found[key], expected[key], f"{at}.{key}")]
    if isinstance(expected, list) and isinstance(found, list):
        if len(found) != len(expected):
            return [f"{at}: {len(found)} items, expected {len(expected)}"]
        return [m for i, pair in enumerate(zip(found, expected, strict=True)) for m in mismatches(*pair, f"{at}[{i}]")]
    if (
        isinstance(expected, numeric)
        and isinstance(found, numeric)
        and not isinstance(expected, bool)
        and not isinstance(found, bool)
        and (isinstance(expected, float) or isinstance(found, float))
    ):
        close = math.isclose(
            found, expected, rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE
        )
        return [] if close else [f"{at}: {found!r}, expected {expected!r}"]
    if type(found) is not type(expected) or found != expected:
        return [f"{at}: {found!r}, expected {expected!r}"]
    return []


def tree_state() -> tuple[str, dict[str, int]]:
    """What git can see of the checkout, and when each output directory changed.

    The pipeline writes every file by staging it and renaming it into place,
    which changes the modification time of the directory it lands in even when
    the file already existed. So the directories under the output roots, three
    levels down, are enough to see a write into them without reading the tens
    of thousands of corpus files a working copy holds there.
    """
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    times: dict[str, int] = {}

    def visit(directory: Path, depth: int) -> None:
        times[directory.relative_to(ROOT).as_posix()] = directory.stat().st_mtime_ns
        if depth == 0:
            return
        for child in directory.iterdir():
            if child.is_dir() and not child.is_symlink():
                visit(child, depth - 1)

    for name in OUTPUT_ROOTS:
        if (ROOT / name).is_dir():
            visit(ROOT / name, 3)
    return status, times


def compare_golden(found: dict[str, object], name: str) -> None:
    """Hold `found` to the committed golden file, or rewrite it on request."""
    golden = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(
            json.dumps(found, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    assert golden.exists(), "no golden file: run once with UPDATE_GOLDEN=1 and commit the result"
    expected = json.loads(golden.read_text(encoding="utf-8"))
    # Through JSON first, so a tuple and a list, or an int key and its string,
    # compare as the file will hold them.
    differences = mismatches(json.loads(json.dumps(found)), expected)
    assert not differences, (
        "the analytical values moved; if that is intended, regenerate with UPDATE_GOLDEN=1 "
        "and commit the diff:\n" + "\n".join(differences[:20])
    )


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


def analytical(series_dir: Path, kwic_dir: Path, frames_dir: Path) -> dict[str, object]:
    """The values worth holding still: rates, intervals, tests, lines — never meta."""
    annual = json.loads((series_dir / "annual.json").read_text(encoding="utf-8"))
    change = json.loads((series_dir / "change_points.json").read_text(encoding="utf-8"))
    monthly = json.loads((series_dir / "monthly.json").read_text(encoding="utf-8"))
    decomposition = json.loads((series_dir / "decomposition.json").read_text(encoding="utf-8"))
    genocide = annual["terms"]["genocide"]
    index = json.loads((kwic_dir / "index.json").read_text(encoding="utf-8"))
    lines = json.loads((kwic_dir / "genocide.json").read_text(encoding="utf-8"))["lines"]
    node_frames = json.loads((frames_dir / "frames.json").read_text(encoding="utf-8"))
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
                    # The band drawn by resampling whole meetings, which the
                    # Chronology shows instead of Wilson's.
                    "speech_rate_cluster_low",
                    "speech_rate_cluster_high",
                    "occurrences",
                    "token_rate",
                )
            },
            "genocide_free_atrocity": annual["corpora"]["genocide_free_atrocity"],
            # Held one term at a time since lexicon v5. The legal register's
            # occurrences and the atrocity core's speeches used to stand here,
            # and both were sums this project chose rather than measurements the
            # corpus offers; `war_crimes` is one of the words they were made of.
            "war_crimes": {
                key: annual["terms"]["war_crimes"][key] for key in ("speeches", "occurrences")
            },
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
        # Decade to decade, by agenda item and by speaker group: how much of the
        # change in the genocide rate is the agenda moving, and how much use.
        "decomposition": decomposition["splits"],
        "monthly_coverage": monthly["coverage"],
        "kwic": {
            "counts": {entry["term"]: entry["count"] for entry in index["terms"]},
            "first_lines": [
                {key: line[key] for key in ("id", "spv", "date", "country", "left", "kw", "right")}
                for line in lines[:5]
            ],
        },
        # The composition, its intervals and where its shares break. The
        # synthetic speeches say "genocide against the Tutsi" and sometimes
        # "war crimes", so the codebook's precedence is exercised as well as its
        # arithmetic: every occurrence matches `directed_against`, some of them
        # match `atrocity_triad` too, and the earlier frame is the one that must
        # win.
        "frames": {
            "occurrences": node_frames["occurrences"],
            "totals": node_frames["totals"],
            "morphology": node_frames["morphology"],
            "by_year": node_frames["by_year"],
            "slices": node_frames["slices"],
            "change": {
                "tested": node_frames["change"]["tested"],
                "per_test_alpha": node_frames["change"]["per_test_alpha"],
            },
        },
    }


@pytest.mark.slow
def test_04_08_and_17_reproduce_the_golden_values(tmp_path: Path) -> None:
    roots = {
        "GENOCIDE_DATA_ROOT": str(tmp_path / "data"),
        "GENOCIDE_NOTES_ROOT": str(tmp_path / "notes"),
        "GENOCIDE_WEB_DATA_ROOT": str(tmp_path / "web-data"),
    }
    derived = tmp_path / "data" / "derived"
    derived.mkdir(parents=True)
    synthetic_corpus().to_parquet(derived / "speeches_flagged.parquet", index=False)
    before = tree_state()

    run_step("04_series.py", roots, "--trials", "200")
    run_step("08_kwic.py", roots, "--terms", "genocide,war_crimes")
    run_step("17_frames.py", roots, "--trials", "200", "--no-model")

    assert tree_state() == before, "a step wrote into the repository's own tree"
    found = analytical(derived / "series", derived / "kwic", derived / "frames")
    compare_golden(found, "end_to_end_04_08.json")
