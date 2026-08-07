"""Download the raw corpus from Harvard Dataverse into data/raw/.

The dataset is CC0 and addressed by DOI, so it is never committed to git — this
script makes the repository self-bootstrapping. Files already present with the
right MD5 are skipped.

Usage:
    python scripts/00_fetch_data.py               # the 3 files the pipeline needs
    python scripts/00_fetch_data.py --all         # including the two .RData files
    python scripts/00_fetch_data.py --force       # re-download regardless of MD5
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.paths import DATAVERSE, DOI, RAW  # noqa: E402

# The pipeline reads only these three. docs.RData / docs_meta.RData are
# redundant R serialisations of the same content (119 MB) — opt in with --all.
REQUIRED = {"speeches.tar", "speaker.tsv", "meta.tsv"}


def dataset_files() -> list[dict]:
    """List the files of the latest published version via the Dataverse API."""
    url = f"{DATAVERSE}/api/datasets/:persistentId/?persistentId={DOI}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        import json

        payload = json.load(resp)
    return payload["data"]["latestVersion"]["files"]


def md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def download(file_id: int, dest: Path, size: int) -> None:
    url = f"{DATAVERSE}/api/access/datafile/{file_id}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    done = 0
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            pct = 100 * done / size if size else 0
            print(f"\r    {done / 1e6:>8.1f} / {size / 1e6:.1f} MB  ({pct:5.1f}%)", end="")
    print()
    tmp.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="also fetch the .RData files")
    ap.add_argument("--force", action="store_true", help="re-download even if MD5 matches")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Dataset {DOI}\nTarget  {RAW}\n")

    for entry in dataset_files():
        df = entry["dataFile"]
        name = df["filename"]
        if not args.all and name not in REQUIRED:
            print(f"  skip     {name}  (use --all)")
            continue

        dest = RAW / name
        expected = df.get("md5", "")

        if dest.exists() and not args.force:
            if expected and md5(dest) == expected:
                print(f"  ok       {name}  ({dest.stat().st_size / 1e6:.1f} MB)")
                continue
            print(f"  stale    {name}  — MD5 mismatch, re-downloading")

        print(f"  fetching {name}  ({df['filesize'] / 1e6:.1f} MB)")
        download(df["id"], dest, df["filesize"])

        if expected and md5(dest) != expected:
            print(f"    MD5 MISMATCH after download for {name}", file=sys.stderr)
            sys.exit(1)

    print("\nDone. Next: python scripts/01_build_parquet.py")


if __name__ == "__main__":
    main()
