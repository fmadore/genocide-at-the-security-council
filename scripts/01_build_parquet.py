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
from lib import artifacts, frames
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

INTEGER_COLUMNS = ("year", "month", "day", "meeting_num")
BOOLEAN_COLUMNS = (
    "president",
    "secretary_general",
    "procedural",
    "permanent_member",
    "elected_member",
    "state",
    "igo",
    "un_org",
    "ngo",
)


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


def as_boolean(values: pd.Series, name: str) -> pd.Series:
    """Parse Dataverse's textual booleans and refuse unknown values."""
    lowered = values.astype("string").str.lower()
    known = {"true": True, "false": False, "1": True, "0": False}
    unknown = sorted(set(lowered.dropna()) - set(known))
    if unknown:
        raise ValueError(f"{name}: unknown boolean values: {', '.join(unknown[:5])}")
    return lowered.map(known).fillna(False).astype(bool)


def as_integer(values: pd.Series, name: str) -> pd.Series:
    parsed = pd.to_numeric(values, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{name}: {int(parsed.isna().sum())} values are not integers")
    return parsed.astype("int32")


def make_date(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame[["year", "month", "day"]], errors="coerce")


def broad_agenda(values: pd.Series) -> pd.Series:
    """Take the first Repertoire category as the one-valued dashboard facet."""
    first = values.astype("string").str.split(";").str[0].str.strip()
    return first.replace({"Thematic Issues": "Thematic"})


def participant_type(frame: pd.DataFrame) -> pd.Series:
    """Derive explicit, mutually exclusive speaking capacities."""
    result = pd.Series("Guest", index=frame.index, dtype="string")
    member = frame["permanent_member"] | frame["elected_member"]
    result.loc[member] = "Council member"
    result.loc[frame["secretary_general"] | frame["un_org"]] = "UN official"
    result.loc[frame["president"] & ~frame["procedural"]] = "Council President"
    result.loc[frame["procedural"]] = "Procedural"
    return result


def adapt_meetings(raw: pd.DataFrame) -> pd.DataFrame:
    meetings = raw.copy()
    for column in INTEGER_COLUMNS:
        meetings[column] = as_integer(meetings[column], column)
    meetings["closed"] = as_boolean(meetings["closed"], "closed")
    meetings["source_speeches_available"] = as_boolean(meetings["speeches"], "speeches")
    meetings["date"] = make_date(meetings)
    meetings["basename"] = meetings["record_id"]
    meetings["spv"] = meetings["record"]
    meetings["meeting_symbol"] = meetings["record"]
    meetings["agenda_item1"] = broad_agenda(meetings["agenda_categories"])
    meetings["agenda_item_manual"] = meetings["topic"].fillna(meetings["agenda"])
    meetings["source_word_count"] = pd.to_numeric(
        meetings["word_count"], errors="coerce"
    ).astype("Int64")
    meetings = meetings.drop(columns=["speeches", "word_count"])
    return meetings


def adapt_speeches(raw: pd.DataFrame, meetings: pd.DataFrame) -> pd.DataFrame:
    speeches = raw.copy()
    for column in (*INTEGER_COLUMNS, "order", "count"):
        speeches[column] = as_integer(speeches[column], column)
    for column in BOOLEAN_COLUMNS:
        speeches[column] = as_boolean(speeches[column], column)

    meeting_meta = meetings[
        [
            "record_id",
            "record",
            "record_url",
            "agenda_categories",
            "agenda_item1",
            "closed",
        ]
    ]
    speeches = speeches.merge(meeting_meta, on="record_id", how="left", validate="many_to_one")

    speeches["row_id"] = speeches["speech_id"]
    speeches["filename"] = speeches["speech_id"] + ".txt"
    speeches["basename"] = speeches["record_id"]
    speeches["date"] = make_date(speeches)
    speeches["speaker"] = speeches["speaker"].fillna("Unknown speaker")
    speeches["country_org"] = speeches["affiliation"].fillna("Unknown affiliation")
    state_with_cow_name = speeches["state"] & speeches["affiliation_cow"].notna()
    speeches.loc[state_with_cow_name, "country_org"] = speeches.loc[
        state_with_cow_name, "affiliation_cow"
    ]
    speeches["role"] = speeches["position"]
    speeches["participanttype"] = participant_type(speeches)
    speeches["speech_number"] = speeches["order"].astype("int32")
    speeches["tokens"] = speeches["count"].astype("int32")
    speeches["source_word_count"] = speeches["count"].astype("int32")
    speeches["text"] = speeches["speech"].fillna("")
    speeches["n_chars"] = speeches["text"].str.len().astype("int32")
    speeches["document_symbol"] = speeches["record"]
    speeches["meeting_symbol"] = speeches["record"]
    speeches["agenda_item_manual"] = speeches["topic"].fillna(speeches["agenda"])
    for column in ("agenda_item2", "agenda_item3", "agenda_item4"):
        speeches[column] = pd.Series(pd.NA, index=speeches.index, dtype="string")

    # The source contains the English transcript but has already removed the
    # printed form-of-address marker that identifies the language of delivery.
    # "Transcript" deliberately maps to Unknown in lib.language instead of
    # turning every translated intervention into inferred English.
    speeches["speech_format"] = "Transcript"
    speeches["record_speech"] = speeches["speech_id"]

    source_renames = {
        "affiliation": "source_affiliation",
        "president": "source_president",
        "secretary_general": "source_secretary_general",
        "procedural": "source_procedural",
        "affiliation_cow": "source_affiliation_cow",
        "cow_ccode": "source_cow_ccode",
        "permanent_member": "source_permanent_member",
        "elected_member": "source_elected_member",
        "state": "source_state",
        "igo": "source_igo",
        "un_org": "source_un_org",
        "ngo": "source_ngo",
        "closed": "source_closed_meeting",
    }
    speeches = speeches.rename(columns=source_renames)
    speeches = speeches.drop(columns=["speech", "count", "order", "position"])
    return speeches


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
    meetings = adapt_meetings(read_source(MEETING_FILE, MEETING_REQUIRED))
    print("Reading speeches.tsv ...")
    speeches = adapt_speeches(read_source(SPEECH_FILE, SPEECH_REQUIRED), meetings)

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
