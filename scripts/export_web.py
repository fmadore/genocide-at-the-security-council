"""Assemble the dashboard's payload from the analysis artefacts.

Unnumbered on purpose: this is not a step in the analysis, it is the seam
between the analysis and the application. The numbered scripts each answer a
question and write their answer to `data/derived/`, where it can be read,
diffed and archived independently of whether a web application exists. This
copies the parts the dashboard actually loads into `web/static/data/` and
writes a manifest of what it took.

    derived/series/*.json   → static/data/series/
    derived/lexical/*.json  → static/data/lexical/
    derived/kwic/*.json     → static/data/kwic/

`09_export_speeches.py` is the one exception and writes its 419 MB straight to
`web/static/data/speeches/`. Copying that twice to preserve a symmetry nobody
benefits from would cost a gigabyte of disk.

Usage:
    python scripts/export_web.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import console
from lib.paths import KWIC, LEXICAL, SERIES, WEB_DATA, ensure_dirs, rel

#: (source directory, destination name, the step that produces it).
PARTS = [
    (SERIES, "series", "04_series.py"),
    (LEXICAL, "lexical", "05_lexical.py"),
    (KWIC, "kwic", "08_kwic.py"),
]

#: Written by 09, not copied. Listed so the manifest describes the whole payload
#: rather than only the part this script moved.
IN_PLACE = [("speeches", "09_export_speeches.py"), ("meetings.json", "09_export_speeches.py")]


def copy_part(source: Path, name: str) -> tuple[int, int]:
    """Mirror one directory into the payload. Returns (files, bytes)."""
    destination = WEB_DATA / name
    if destination.exists():
        shutil.rmtree(destination)
    if not source.exists():
        console.fail(f"{rel(source)} is missing — run the step that writes it first")
    shutil.copytree(source, destination)
    files = sorted(destination.glob("*.json"))
    return len(files), sum(f.stat().st_size for f in files)


def measure(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_file():
        return 1, path.stat().st_size
    files = list(path.rglob("*.json"))
    return len(files), sum(f.stat().st_size for f in files)


def run() -> None:
    ensure_dirs()
    manifest: dict[str, object] = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parts": {},
    }
    total_files = total_bytes = 0

    console.step("Copying analysis artefacts into the payload")
    for source, name, producer in PARTS:
        files, size = copy_part(source, name)
        manifest["parts"][name] = {  # type: ignore[index]
            "files": files,
            "bytes": size,
            "produced_by": producer,
        }
        total_files += files
        total_bytes += size
        console.info(f"{name:10s} {files:>6,} files  {size / 1e6:>7.1f} MB  (from {producer})")

    console.step("Measuring what 09 wrote in place")
    for name, producer in IN_PLACE:
        files, size = measure(WEB_DATA / name)
        if not files:
            console.warn(f"{name} is missing — run {producer}; the reader view will 404")
        manifest["parts"][name] = {  # type: ignore[index]
            "files": files,
            "bytes": size,
            "produced_by": producer,
        }
        total_files += files
        total_bytes += size
        console.info(f"{name:10s} {files:>6,} files  {size / 1e6:>7.1f} MB  (from {producer})")

    manifest["files"] = total_files
    manifest["bytes"] = total_bytes
    (WEB_DATA / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    console.step("Done")
    console.info(f"{total_files:,} files, {total_bytes / 1e6:.0f} MB in {rel(WEB_DATA)}")
    console.info(f"wrote {rel(WEB_DATA / 'manifest.json')}")


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()


if __name__ == "__main__":
    main()
