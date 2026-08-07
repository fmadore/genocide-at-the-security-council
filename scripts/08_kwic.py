"""Concordance: every occurrence of every lexicon term, in context.

Reads speeches_flagged.parquet and writes one JSON file per term to
data/derived/kwic/, plus an index and a findings note.

This is the artefact that turns the dashboard from a set of charts into a
research instrument: it is what a bar, a year or a country leads *to*. Every
line carries the ±150-character snippet for scanning, the full sentence for
quoting, the `S/PV` symbol for citing, and the offsets that let the reader view
highlight the match in the whole speech without re-running a regex.

One file per term because the sizes are lopsided — `impunity` is fifty times
`genocide_convention` — and the dashboard should fetch what the reader asked for
rather than everything.

Usage:
    python scripts/08_kwic.py [--terms genocide,war_crimes] [--width 150]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import console, frames, kwic, lexicon
from lib.paths import (
    KWIC,
    SPEECHES_FLAGGED,
    ensure_dirs,
    rel,
    write_note,
)


def columns_needed(lex: lexicon.Lexicon) -> list[str]:
    """Only what the extraction reads. The frame is 131 MB; most of it is text."""
    return [*kwic.REQUIRED, *(f"{lexicon.HAS}{term.name}" for term in lex.active)]


def write_term(
    speeches: pd.DataFrame, term: lexicon.Term, width: int, meta: dict
) -> dict[str, object]:
    """Extract and write one term's lines. Returns its index entry."""
    lines = [line.as_dict() for line in kwic.extract(speeches, term, width)]
    path = KWIC / f"{term.name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "meta": meta,
                "term": term.name,
                "pattern": term.pattern,
                "tier": term.tier,
                "register": term.register,
                "count": len(lines),
                # `file` is not stored per line: it is `id` up to the '#', plus
                # '.txt'. At 70,000 lines that redundancy is megabytes.
                "id_format": "<speech filename without .txt>#<occurrence ordinal>",
                "lines": lines,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    sentences = pd.Series([len(line["sent"]) for line in lines], dtype="int64")
    size = path.stat().st_size
    return {
        "term": term.name,
        "tier": term.tier,
        "register": term.register,
        "file": path.name,
        "count": len(lines),
        "speeches": len({line["id"].rsplit("#", 1)[0] for line in lines}),
        "bytes": size,
        "sentence_median": int(sentences.median()) if len(sentences) else 0,
        "sentence_p95": int(sentences.quantile(0.95)) if len(sentences) else 0,
        "sentence_max": int(sentences.max()) if len(sentences) else 0,
        "long_sentences": int((sentences > kwic.LONG_SENTENCE).sum()),
    }


def check_against_flags(speeches: pd.DataFrame, entries: list[dict]) -> list[str]:
    """Every line must be accounted for by 03's counts.

    A concordance that does not add up to the totals published beside it is
    worse than no concordance: the reader has no way to tell which number is
    wrong. This is the check that makes the two agree by construction.
    """
    problems = []
    for entry in entries:
        column = f"{lexicon.COUNT}{entry['term']}"
        if column not in speeches.columns:
            continue
        expected = int(speeches[column].sum())
        if entry["count"] != expected:
            problems.append(
                f"{entry['term']}: {entry['count']:,} lines against "
                f"{expected:,} counted occurrences in speeches_flagged.parquet"
            )
    return problems


def build_note(entries: list[dict], lex: lexicon.Lexicon, width: int) -> str:
    total = sum(e["count"] for e in entries)
    total_bytes = sum(e["bytes"] for e in entries)
    ranked = sorted(entries, key=lambda e: -e["count"])
    worst = max(entries, key=lambda e: e["long_sentences"]) if entries else None

    return "\n".join(
        [
            "# 08 — Concordance",
            "",
            f"**{total:,} lines** across {len(entries)} terms, "
            f"{total_bytes / 1e6:.1f} MB, one file per term in `data/derived/kwic/`.",
            f"Lexicon version {lex.version}. Window ±{width} characters, plus the full "
            "sentence.",
            "",
            "Line counts are asserted against the occurrence counts in "
            "`speeches_flagged.parquet`; the run fails rather than shipping a concordance",
            "that disagrees with the totals published next to it.",
            "",
            "## Lines per term",
            "",
            "| Term | Register | Lines | Speeches | Size |",
            "|---|---|---:|---:|---:|",
            *[
                f"| `{e['term']}` | {e['register']} | {e['count']:,} | {e['speeches']:,} | "
                f"{e['bytes'] / 1e6:.1f} MB |"
                for e in ranked
            ],
            "",
            "## Sentence segmentation",
            "",
            "The sentence is the citable unit, so its quality is worth watching. Rule-based,",
            "not spaCy — see the module docstring in `scripts/lib/kwic.py` for why. A very",
            f"long 'sentence' (over {kwic.LONG_SENTENCE} characters) is a segmentation",
            "failure or an OCR-damaged run-on; they are kept rather than truncated, because",
            "truncating a unit offered for quotation is worse, but they are counted here.",
            "",
            "| Term | Median | 95th pct | Max | Over "
            f"{kwic.LONG_SENTENCE} chars |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| `{e['term']}` | {e['sentence_median']:,} | {e['sentence_p95']:,} | "
                f"{e['sentence_max']:,} | {e['long_sentences']:,} "
                f"({e['long_sentences'] / e['count']:.1%}) |"
                if e["count"]
                else f"| `{e['term']}` | — | — | — | — |"
                for e in ranked
            ],
            "",
            (
                f"Worst case: `{worst['term']}`, {worst['long_sentences']:,} lines over "
                f"{kwic.LONG_SENTENCE} characters."
                if worst
                else ""
            ),
            "",
            "**To check:** read 20 of the longest sentences. If they are genuine run-on",
            "speech, nothing needs doing. If they are two sentences the splitter joined,",
            "the abbreviation list in `lib/kwic.py` is where to fix it.",
            "",
        ]
    ) + "\n"


def run(terms: list[str] | None, width: int) -> None:
    ensure_dirs()

    lex = lexicon.load()
    wanted = [t for t in lex.active if terms is None or t.name in terms]
    if terms and (unknown := sorted(set(terms) - {t.name for t in lex.active})):
        console.fail(f"not active terms in config/lexicon.yml: {', '.join(unknown)}")
    console.info(f"lexicon version {lex.version}, {len(wanted)} of {len(lex.active)} terms")

    console.step("Reading the flagged corpus")
    speeches = frames.read(SPEECHES_FLAGGED, columns=columns_needed(lex))

    meta = {
        "script": "08_kwic.py",
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lexicon_version": lex.version,
        "width": width,
    }

    console.step("Extracting concordance lines")
    entries = []
    for term in wanted:
        entry = write_term(speeches, term, width, meta)
        entries.append(entry)
        console.info(
            f"{term.name:28s} {entry['count']:>7,} lines  "
            f"{entry['speeches']:>6,} speeches  {entry['bytes'] / 1e6:>5.1f} MB"
        )

    console.step("Checking against the lexicon counts")
    if problems := check_against_flags(speeches, entries):
        console.fail("the concordance disagrees with speeches_flagged.parquet", problems)
    console.info(f"all {len(entries)} terms reproduce their occurrence count exactly")

    console.step("Writing")
    index = KWIC / "index.json"
    index.write_text(
        json.dumps({"meta": meta, "terms": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    console.info(
        f"wrote {rel(index)}  ({sum(e['count'] for e in entries):,} lines, "
        f"{sum(e['bytes'] for e in entries) / 1e6:.1f} MB across {len(entries)} files)"
    )
    note = write_note("08_kwic.md", build_note(entries, lex, width))
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", help="comma-separated subset; default is every active term")
    parser.add_argument("--width", type=int, default=kwic.WIDTH, help="context characters")
    args = parser.parse_args()
    run(args.terms.split(",") if args.terms else None, args.width)


if __name__ == "__main__":
    main()
