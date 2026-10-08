"""Adapt Sakamoto-Matsuoka v5 into the pipeline's canonical parquet tables.

The source distribution already contains one UTF-8 TSV row per speech and one
per Security Council meeting. This step gives those fields the stable names
used by the analysis without pretending that unavailable Schoenfeld variables
(notably delivery language and quanteda token counts) still exist.

Reads data/raw/{speeches.tsv,meetings.tsv} and writes
data/derived/{speeches,meetings}.parquet. Everything downstream reads those
parquet files and never reaches back into the raw distribution.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, frames, sakamoto
from lib.paths import (
    DERIVED,
    EXPECTED_SPEECHES,
    EXPECTED_TOKENS,
    MANIFESTS,
    MEETINGS,
    RAW,
    ROOT,
    SPEECHES,
    ensure_dirs,
    write_note,
)

SPEECH_FILE = RAW / "speeches.tsv"
MEETING_FILE = RAW / "meetings.tsv"

SPEECH_REQUIRED = {
    "speech_id",
    "record_id",
    "doc_name",
    "meeting_num",
    "year",
    "month",
    "day",
    "topic",
    "agenda",
    "order",
    "speaker",
    "affiliation",
    "position",
    "president",
    "secretary_general",
    "procedural",
    "count",
    "speech",
    "affiliation_cow",
    "cow_ccode",
    "permanent_member",
    "elected_member",
    "state",
    "igo",
    "un_org",
    "ngo",
}

MEETING_REQUIRED = {
    "record_id",
    "year",
    "month",
    "day",
    "meeting_num",
    "closed",
    "topic",
    "agenda",
    "agenda_categories",
    "pres_name",
    "pres_country",
    "speeches",
    "word_count",
    "outcome",
    "record",
    "record_url",
    "RES",
    "RES_url",
    "PRST",
    "PRST_url",
}

def read_source(path: Path, required: set[str]) -> pd.DataFrame:
    """Read a source TSV, including quoted speech fields with embedded newlines."""
    frame = pd.read_csv(
        path,
        sep="\t",
        encoding="utf-8",
        dtype="string",
        keep_default_na=False,
        na_values=["", "NULL", "NA"],
        low_memory=False,
    )
    unnamed = [column for column in frame.columns if column.startswith("Unnamed:")]
    if unnamed:
        frame = frame.drop(columns=unnamed)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path}: missing source columns: {', '.join(missing)}")
    return frame


def validate(speeches: pd.DataFrame, meetings: pd.DataFrame) -> list[str]:
    problems: list[str] = []
    if EXPECTED_SPEECHES and len(speeches) != EXPECTED_SPEECHES:
        problems.append(f"row count {len(speeches):,} != {EXPECTED_SPEECHES:,}")
    if speeches["filename"].nunique() != len(speeches):
        problems.append("filename is not unique")
    if speeches["date"].isna().any():
        problems.append(f"{int(speeches['date'].isna().sum())} unparsed speech dates")
    if meetings["date"].isna().any():
        problems.append(f"{int(meetings['date'].isna().sum())} unparsed meeting dates")
    if empty := int((speeches["n_chars"] == 0).sum()):
        problems.append(f"{empty} empty speech texts")
    if missing := int((~speeches["record_id"].isin(set(meetings["record_id"]))).sum()):
        problems.append(f"{missing} speeches have no meeting row")
    total_tokens = int(speeches["tokens"].sum())
    if EXPECTED_TOKENS and total_tokens != EXPECTED_TOKENS:
        problems.append(f"source word sum {total_tokens:,} != {EXPECTED_TOKENS:,}")
    return problems


def build() -> None:
    ensure_dirs()
    missing = [path.name for path in (SPEECH_FILE, MEETING_FILE) if not path.exists()]
    if missing:
        print(f"Missing from {RAW}: {', '.join(missing)}", file=sys.stderr)
        print("Run: python scripts/00_fetch_data.py", file=sys.stderr)
        sys.exit(1)

    print("Reading meetings.tsv ...")
    meetings = sakamoto.adapt_meetings(read_source(MEETING_FILE, MEETING_REQUIRED))
    print("Reading speeches.tsv ...")
    speeches = sakamoto.adapt_speeches(read_source(SPEECH_FILE, SPEECH_REQUIRED), meetings)

    counts = speeches.groupby("record_id").size()
    meetings["num_speeches"] = meetings["record_id"].map(counts).fillna(0).astype("int32")

    if problems := validate(speeches, meetings):
        print("\nVALIDATION FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)
    print("Validation passed.")

    frames.write(speeches, SPEECHES)
    frames.write(meetings, MEETINGS)

    summary = (
        f"{len(speeches):,} speeches | {int((meetings['num_speeches'] > 0).sum()):,} "
        f"meetings with speeches | {len(meetings):,} meeting records | "
        f"{speeches['date'].min():%Y-%m-%d} to {speeches['date'].max():%Y-%m-%d} | "
        f"{int(speeches['tokens'].sum()):,} source words"
    )
    print(f"\nWrote {SPEECHES.relative_to(DERIVED.parents[1])} "
          f"({SPEECHES.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {MEETINGS.relative_to(DERIVED.parents[1])} "
          f"({MEETINGS.stat().st_size / 1e6:.2f} MB)")
    print(f"\n{summary}")

    write_note(
        "01_build.md",
        "# 01 - Build\n\n"
        f"{summary}\n\n"
        "- Source: Sakamoto-Matsuoka, *The UNSC Meetings and Speeches*, v5.0.\n"
        "- The source English transcript starts at the speech body; no form of address "
        "was reconstructed.\n"
        "- `tokens` preserves the source's reported word count for compatibility; "
        "step 02 computes the analytical word denominator independently.\n",
    )
    manifest = artifacts.provenance(
        ROOT,
        "01_build_parquet.py",
        inputs=[SPEECH_FILE, MEETING_FILE],
        extra={
            "source": "Sakamoto-Matsuoka v5.0",
            "outputs": [
                artifacts.describe_file(SPEECHES, ROOT),
                artifacts.describe_file(MEETINGS, ROOT),
            ],
            "speeches": len(speeches),
            "meetings": len(meetings),
            "meetings_with_speeches": int((meetings["num_speeches"] > 0).sum()),
            "source_words": int(speeches["tokens"].sum()),
        },
    )
    artifacts.atomic_write_json(MANIFESTS / "01_build_parquet.json", manifest, indent=1)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()


if __name__ == "__main__":
    main()
