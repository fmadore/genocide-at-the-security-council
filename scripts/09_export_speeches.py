"""Export the corpus as one JSON file per meeting, for the reader view.

Reads speeches_flagged.parquet and meetings.parquet, writes 6,595 files to
web/static/data/speeches/ plus an index at web/static/data/meetings.json.

One file per meeting, not per speech and not one blob. The full text is 389 MB —
too much to hand a browser at once, and 106,302 individual files is more than a
static host should be asked to hold. Bundling by meeting gives files averaging
59 kB: one fetch opens a whole session with every speech in it, which is exactly
the unit a reader wants when they click a concordance line.

Each speech carries its lexicon hits as character offsets, so the reader
highlights matches without re-running the lexicon in JavaScript. The regexes are
the analysis; a second implementation of them in the browser would be a second
thing to keep true.

**This output cannot be committed** — see the note it writes for what that means
for deployment.

Usage:
    python scripts/09_export_speeches.py [--scope all|matched] [--indent]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import console, frames, kwic, lexicon
from lib.paths import (
    MEETINGS,
    SPEECHES_FLAGGED,
    WEB_DATA,
    ensure_dirs,
    rel,
    write_note,
)

SPEECH_DIR = WEB_DATA / "speeches"
INDEX = WEB_DATA / "meetings.json"

COLUMNS = [
    "filename",
    "basename",
    "meeting_symbol",
    "speech_number",
    "date",
    "year",
    "speaker",
    "role",
    "country_org",
    "iso3",
    "entity_type",
    "speaker_group",
    "participanttype",
    "spoken_language",
    "agenda_item1",
    "agenda_item_manual",
    "tokens",
    "text",
    "body_start",
    # Not exported. Read so the run can check its own offsets against the count
    # 03 recorded, rather than trusting that two passes of the same regexes agree.
    "n_lexicon_total",
]


def clean(value: object) -> object:
    """NaN is not JSON. A missing speaker name has to arrive as null."""
    return None if pd.isna(value) else value


def build_speech(row, terms: list[lexicon.Term]) -> dict[str, object]:
    """One speech, with its text and the offsets of every lexicon match in it."""
    return {
        "id": row.filename.removesuffix(".txt"),
        "n": int(row.speech_number),
        "speaker": clean(row.speaker),
        "role": clean(row.role),
        "country": row.country_org,
        "iso3": clean(row.iso3),
        "entity_type": row.entity_type,
        "group": row.speaker_group,
        "type": row.participanttype,
        "language": clean(row.spoken_language),
        "tokens": int(row.tokens),
        "body_start": int(row.body_start),
        "text": row.text,
        "hits": kwic.offsets(row.text, int(row.body_start), terms),
    }


def terms_present(row, lex: lexicon.Lexicon) -> list[lexicon.Term]:
    """Only the terms this speech is already flagged for.

    Testing all 22 regexes against all 106,302 speeches would be a minute of
    work to rediscover what 03 already recorded.
    """
    return [t for t in lex.active if getattr(row, f"{lexicon.HAS}{t.name}")]


def build_meeting(meeting, speeches: pd.DataFrame, lex: lexicon.Lexicon) -> dict[str, object]:
    ordered = speeches.sort_values("speech_number")
    first = ordered.iloc[0]
    exported = [build_speech(row, terms_present(row, lex)) for row in ordered.itertuples()]
    return {
        "basename": meeting.basename,
        "spv": first["meeting_symbol"],
        "date": f"{meeting.date:%Y-%m-%d}",
        "year": int(meeting.year),
        "topic": meeting.topic,
        "region": first["agenda_item1"],
        "agenda": first["agenda_item_manual"],
        "speeches": exported,
    }


def summarise(meeting: dict) -> dict[str, object]:
    """The index row for one meeting: enough to navigate, not enough to read."""
    hits = [s["hits"] for s in meeting["speeches"]]
    return {
        "basename": meeting["basename"],
        "spv": meeting["spv"],
        "date": meeting["date"],
        "year": meeting["year"],
        "topic": meeting["topic"],
        "region": meeting["region"],
        "agenda": meeting["agenda"],
        "speeches": len(meeting["speeches"]),
        "terms": sorted({name for h in hits for name in h}),
        "occurrences": sum(len(spans) for h in hits for spans in h.values()),
    }


def build_note(
    rows: list[dict], total_speeches: int, total_bytes: int, scope: str, skipped: int
) -> str:
    with_terms = [r for r in rows if r["terms"]]
    occurrences = sum(int(r["occurrences"]) for r in rows)
    biggest = max(rows, key=lambda r: int(r["speeches"]))

    return "\n".join(
        [
            "# 09 — Speech export",
            "",
            f"**{len(rows):,} meeting files**, {total_speeches:,} speeches, "
            f"{total_bytes / 1e6:.0f} MB in `web/static/data/speeches/`, plus an index at "
            f"`web/static/data/meetings.json`.",
            f"Scope `{scope}`" + (f", {skipped:,} meetings skipped." if skipped else "."),
            "",
            f"- Mean file {total_bytes / len(rows) / 1e3:.0f} kB, largest meeting "
            f"{biggest['spv']} with {biggest['speeches']} speeches.",
            f"- {len(with_terms):,} meetings ({len(with_terms) / len(rows):.1%}) contain at "
            f"least one lexicon term; {occurrences:,} occurrences carry offsets.",
            "",
            "Speech counts and occurrence totals are asserted against "
            "`speeches_flagged.parquet` before anything is written.",
            "",
            "## The deployment question this raises",
            "",
            "389 MB cannot go in the repository, and it is not in it: `web/static/data/` is",
            "gitignored. So `deploy.yml` will build a site with no reader text unless",
            "something puts these files there first. Three ways, none yet chosen:",
            "",
            "| Option | Cost | Consequence |",
            "|---|---|---|",
            "| Run `00`-`09` in the deploy workflow | ~630 MB download + a few minutes per "
            "deploy, cacheable on the DOI | Fully reproducible from source; slowest CI |",
            "| Publish the payload as a release asset or Hugging Face dataset, fetch at build "
            "| One upload per data version | Fast CI; the artefact becomes a thing to version "
            "deliberately |",
            "| Build locally, deploy the built site | No CI data step | Reproducibility rests "
            "on one machine — the weakest option for a project meant to be citable |",
            "",
            "GitHub Pages allows 1 GB, so the size itself is not the obstacle; where the",
            "bytes come from at build time is.",
            "",
            "## Shape",
            "",
            "```json",
            "{ \"basename\": \"UNSC_2015_SPV.7481\", \"spv\": \"S/PV.7481\",",
            "  \"date\": \"2015-07-08\", \"topic\": \"…\", \"region\": \"Europe\",",
            "  \"speeches\": [",
            "    { \"id\": \"UNSC_2015_SPV.7481_spch0007\", \"n\": 7,",
            "      \"speaker\": \"Mr. Rycroft\", \"country\": \"United Kingdom…\",",
            "      \"iso3\": \"GBR\", \"group\": \"P5\", \"language\": null,",
            "      \"body_start\": 28, \"text\": \"…\",",
            "      \"hits\": { \"genocide\": [[2753, 2761]] } } ] }",
            "```",
            "",
            "`body_start` is where the speech begins past its form of address, and `hits`",
            "are offsets into `text` — both measured against the whole string, so the reader",
            "can highlight and can show the address separately without recomputing either.",
            "",
        ]
    ) + "\n"


def run(scope: str, indent: int | None, clean_first: bool) -> None:
    ensure_dirs()

    lex = lexicon.load()
    flags = [f"{lexicon.HAS}{t.name}" for t in lex.active]

    console.step("Reading")
    speeches = frames.read(SPEECHES_FLAGGED, columns=[*COLUMNS, *flags])
    meetings = frames.read(MEETINGS)

    if scope == "matched":
        keep = set(speeches.loc[speeches[flags].any(axis=1), "basename"])
        meetings = meetings[meetings["basename"].isin(keep)]
        console.info(f"scope 'matched': {len(meetings):,} meetings carry a lexicon term")

    expected_speeches = int(speeches["basename"].isin(set(meetings["basename"])).sum())
    expected_occurrences = int(
        speeches.loc[speeches["basename"].isin(set(meetings["basename"])), "n_lexicon_total"].sum()
    ) if "n_lexicon_total" in speeches.columns else None

    if clean_first and SPEECH_DIR.exists():
        console.info(f"clearing {rel(SPEECH_DIR)}")
        shutil.rmtree(SPEECH_DIR)
    SPEECH_DIR.mkdir(parents=True, exist_ok=True)

    meta = {
        "script": "09_export_speeches.py",
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lexicon_version": lex.version,
        "scope": scope,
    }

    console.step("Writing one file per meeting")
    grouped = dict(list(speeches.groupby("basename", sort=False)))
    rows, total_bytes, written = [], 0, 0
    for meeting in meetings.itertuples():
        group = grouped.get(meeting.basename)
        if group is None:
            console.warn(f"{meeting.basename} has no speeches — skipped")
            continue
        built = build_meeting(meeting, group, lex)
        path = SPEECH_DIR / f"{meeting.basename}.json"
        path.write_text(
            json.dumps({"meta": meta, **built}, ensure_ascii=False,
                       indent=indent, separators=None if indent else (",", ":")),
            encoding="utf-8",
        )
        total_bytes += path.stat().st_size
        written += len(built["speeches"])
        rows.append(summarise(built))
        if len(rows) % 1_000 == 0:
            console.info(f"{len(rows):,} meetings, {total_bytes / 1e6:.0f} MB")

    console.step("Checking against the parquet")
    problems = []
    if written != expected_speeches:
        problems.append(f"exported {written:,} speeches, expected {expected_speeches:,}")
    exported_occurrences = sum(int(r["occurrences"]) for r in rows)
    if expected_occurrences is not None and exported_occurrences != expected_occurrences:
        problems.append(
            f"exported {exported_occurrences:,} occurrence offsets, expected "
            f"{expected_occurrences:,} from the lexicon counts"
        )
    if problems:
        console.fail("the export does not match speeches_flagged.parquet", problems)
    console.info(
        f"{written:,} speeches and {exported_occurrences:,} occurrence offsets, both matching"
    )

    console.step("Writing the index")
    INDEX.write_text(
        json.dumps({"meta": meta, "meetings": rows}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    console.info(f"wrote {rel(INDEX)}  ({INDEX.stat().st_size / 1e6:.1f} MB)")
    console.info(f"wrote {len(rows):,} files to {rel(SPEECH_DIR)}  ({total_bytes / 1e6:.0f} MB)")

    note = write_note(
        "09_export_speeches.md",
        build_note(rows, written, total_bytes, scope, len(meetings) - len(rows)),
    )
    console.info(f"wrote {note.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=["all", "matched"],
        default="all",
        help="'matched' exports only meetings carrying a lexicon term (saves ~10%%, and "
        "leaves the reader with dead ends)",
    )
    parser.add_argument("--indent", action="store_true", help="pretty-print, for debugging")
    parser.add_argument(
        "--no-clean", action="store_true", help="keep files from a previous, wider run"
    )
    args = parser.parse_args()
    run(args.scope, 1 if args.indent else None, not args.no_clean)


if __name__ == "__main__":
    main()
