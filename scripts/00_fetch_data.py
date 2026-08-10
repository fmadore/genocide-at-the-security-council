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
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.artifacts import atomic_write_json
from lib.paths import DATASET_VERSION, DATAVERSE, DOI, RAW

# The pipeline reads only these three. docs.RData / docs_meta.RData are
# redundant R serialisations of the same content (119 MB) — opt in with --all.
REQUIRED = {"speeches.tar", "speaker.tsv", "meta.tsv"}
USER_AGENT = (
    "genocide-at-the-security-council/1.0 "
    "(+https://github.com/fmadore/genocide-at-the-security-council)"
)


def dataverse_request(url: str, *, accept: str) -> urllib.request.Request:
    """Identify this project to Dataverse instead of using urllib's blocked default."""
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )


def dataset_version(version: str) -> dict:
    """Read one explicit published dataset version, including its file list."""
    query = urlencode({"persistentId": DOI, "excludeFiles": "false"})
    url = f"{DATAVERSE}/api/datasets/:persistentId/versions/{quote(version)}?{query}"
    request = dataverse_request(url, accept="application/json")
    with urllib.request.urlopen(request, timeout=60) as resp:
        payload = json.load(resp)
    return payload["data"]


def expected_md5(data_file: dict) -> str:
    checksum = data_file.get("checksum") or {}
    if str(checksum.get("type", "")).upper() == "MD5":
        return str(checksum.get("value", ""))
    return str(data_file.get("md5", ""))


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
    request = dataverse_request(url, accept="application/octet-stream")
    with urllib.request.urlopen(request, timeout=120) as resp, tmp.open("wb") as out:
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
    ap.add_argument(
        "--latest",
        action="store_true",
        help=f"opt into the latest published version instead of pinned {DATASET_VERSION}",
    )
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    requested = ":latest-published" if args.latest else DATASET_VERSION
    version = dataset_version(requested)
    actual = f"{version['versionNumber']}.{version['versionMinorNumber']}"
    if not args.latest and actual != DATASET_VERSION:
        raise RuntimeError(f"requested dataset {DATASET_VERSION}, API returned {actual}")
    print(f"Dataset {DOI} version {actual}\nTarget  {RAW}\n")

    selected = []
    for entry in version["files"]:
        df = entry["dataFile"]
        name = df["filename"]
        if not args.all and name not in REQUIRED:
            print(f"  skip     {name}  (use --all)")
            continue

        dest = RAW / name
        expected = expected_md5(df)
        selected.append(
            {
                "id": df["id"],
                "filename": name,
                "bytes": df["filesize"],
                "md5": expected,
            }
        )

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

    atomic_write_json(
        RAW / "dataset-manifest.json",
        {
            "doi": DOI,
            "server": DATAVERSE,
            "version": actual,
            "requested": requested,
            "files": selected,
        },
        indent=1,
    )
    print("\nWrote data/raw/dataset-manifest.json")
    print("Done. Next: python scripts/01_build_parquet.py")


if __name__ == "__main__":
    main()
