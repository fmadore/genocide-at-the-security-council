"""Build the canonical parquet files from the raw Dataverse distribution.

Reads data/raw/{speaker.tsv, meta.tsv, speeches.tar}; repairs the two known
defects (literal newlines inside a field; the cp1252 encoding trap on Windows);
joins metadata to full text; validates against the codebook's figures; writes
data/derived/{speeches,meetings}.parquet.

Everything downstream reads the parquet, never the raw files.

Usage:
    python scripts/01_build_parquet.py

Requires the x64 Python that has pyarrow:
    C:/Users/frede/AppData/Local/Programs/Python/Python312/python.exe
"""

from __future__ import annotations

import argparse
import io
import sys
import tarfile
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.paths import (
    DERIVED,
    EXPECTED_SPEECHES,
    EXPECTED_TOKENS,
    MEETINGS,
    RAW,
    SPEECHES,
    ensure_dirs,
    write_note,
)

# Expected field counts, i.e. (number of columns - 1) tabs per logical row.
SPEAKER_TABS = 25
META_TABS = 8


def repair_lines(path: Path, n_tabs: int) -> list[str]:
    """Read a TSV whose fields may contain literal newlines.

    Meeting S/PV.5225 has a newline inside agenda_item3, splitting each of its
    36 speeches across two physical lines. Rejoin lines until the tab count
    reaches the expected field count.
    """
    text = path.read_text(encoding="utf-8")
    out: list[str] = []
    buf = ""
    for line in text.split("\n"):
        buf = line if not buf else f"{buf} {line}"
        if buf.count("\t") >= n_tabs:
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def read_tsv(path: Path, n_tabs: int) -> pd.DataFrame:
    """Read a repaired TSV as strings, with encoding and quoting forced.

    quoting=3 (QUOTE_NONE) is required: fields carry R-style doubled
    apostrophes (D''Affaires) and unescaped quotation marks. encoding='utf-8'
    is required because Windows would otherwise fall back to cp1252 and
    silently mangle every accented place name.
    """
    lines = repair_lines(path, n_tabs)
    df = pd.read_csv(
        io.StringIO("\n".join(lines)),
        sep="\t",
        quoting=3,
        dtype=str,
        na_values=["NA"],
        keep_default_na=False,
        encoding="utf-8",
    )
    df.rename(columns={df.columns[0]: "row_id"}, inplace=True)
    # Blank strings are missing values, not empty categories.
    for col in df.columns:
        df[col] = df[col].replace("", pd.NA)
    return df


def load_texts(tar_path: Path) -> dict[str, str]:
    """Stream speeches.tar into {filename: text}. ~6 s for 106,302 members."""
    texts: dict[str, str] = {}
    with tarfile.open(tar_path, "r") as tf:
        for member in tf:
            if not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            texts[member.name.split("/")[-1]] = fh.read().decode("utf-8", errors="replace")
    return texts


def validate(speeches: pd.DataFrame, meetings: pd.DataFrame, texts: dict) -> list[str]:
    """Return a list of problems; empty means the build is trustworthy."""
    problems: list[str] = []
    if len(speeches) != EXPECTED_SPEECHES:
        problems.append(f"row count {len(speeches):,} != {EXPECTED_SPEECHES:,}")
    if speeches["filename"].nunique() != len(speeches):
        problems.append("filename is not unique")
    if speeches["text"].isna().any():
        problems.append(f"{int(speeches['text'].isna().sum())} speeches have no text")
    if orphans := set(texts) - set(speeches["filename"]):
        problems.append(f"{len(orphans)} tar members absent from speaker.tsv")
    if speeches["date"].isna().any():
        problems.append(f"{int(speeches['date'].isna().sum())} unparsed dates")
    if empty := int((speeches["n_chars"] == 0).sum()):
        problems.append(f"{empty} empty texts")
    if missing := int((~speeches["basename"].isin(set(meetings["basename"]))).sum()):
        problems.append(f"{missing} speeches with no meeting row")
    total_tokens = int(speeches["tokens"].sum())
    if total_tokens != EXPECTED_TOKENS:
        problems.append(f"token sum {total_tokens:,} != codebook {EXPECTED_TOKENS:,}")
    return problems


def build() -> None:
    ensure_dirs()

    missing = [f for f in ("speaker.tsv", "meta.tsv", "speeches.tar") if not (RAW / f).exists()]
    if missing:
        print(f"Missing from {RAW}: {', '.join(missing)}", file=sys.stderr)
        print("Run: python scripts/00_fetch_data.py", file=sys.stderr)
        sys.exit(1)

    print("Reading speaker.tsv ...")
    speeches = read_tsv(RAW / "speaker.tsv", SPEAKER_TABS)
    print("Reading meta.tsv ...")
    meetings = read_tsv(RAW / "meta.tsv", META_TABS)
    print(f"  speeches={speeches.shape}  meetings={meetings.shape}")

    # Derived join key back to meta.tsv.basename
    speeches["basename"] = speeches["filename"].str.replace(r"_spch\d+\.txt$", "", regex=True)

    for col in ["year", "month", "day", "speech_number", "tokens", "types", "sentences"]:
        speeches[col] = pd.to_numeric(speeches[col], errors="coerce").astype("Int32")
    for col in ["year", "month", "day", "num_speeches"]:
        meetings[col] = pd.to_numeric(meetings[col], errors="coerce").astype("Int32")
    speeches["date"] = pd.to_datetime(speeches["date"], errors="coerce")
    meetings["date"] = pd.to_datetime(meetings["date"], errors="coerce")

    print("Streaming speeches.tar ...")
    t0 = time.time()
    texts = load_texts(RAW / "speeches.tar")
    print(f"  {len(texts):,} speech files in {time.time() - t0:.0f}s")

    speeches["text"] = speeches["filename"].map(texts)
    speeches["n_chars"] = speeches["text"].fillna("").str.len()

    if problems := validate(speeches, meetings, texts):
        print("\nVALIDATION FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print("Validation passed.")

    speeches.to_parquet(SPEECHES, index=False, compression="zstd")
    meetings.to_parquet(MEETINGS, index=False, compression="zstd")

    summary = (
        f"{len(speeches):,} speeches | {speeches['basename'].nunique():,} meetings | "
        f"{speeches['date'].min():%Y-%m-%d} to {speeches['date'].max():%Y-%m-%d} | "
        f"{int(speeches['tokens'].sum()):,} tokens"
    )
    print(f"\nWrote {SPEECHES.relative_to(DERIVED.parents[1])} "
          f"({SPEECHES.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {MEETINGS.relative_to(DERIVED.parents[1])} "
          f"({MEETINGS.stat().st_size / 1e6:.2f} MB)")
    print(f"\n{summary}")

    write_note(
        "01_build.md",
        f"# 01 — Build\n\n{summary}\n\n"
        f"- Repaired 36 rows split by a literal newline in meeting S/PV.5225\n"
        f"- Token sum matches the codebook exactly ({EXPECTED_TOKENS:,})\n"
        f"- 0 missing texts, 0 orphan tar members, 0 unparsed dates\n",
    )


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()


if __name__ == "__main__":
    main()
