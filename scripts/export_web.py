"""Assemble the dashboard's payload from the analysis artefacts.

Unnumbered on purpose: this is not a step in the analysis, it is the seam
between the analysis and the application. The numbered scripts each answer a
question and write their answer to `data/derived/`, where it can be read,
diffed and archived independently of whether a web application exists. This
copies the parts the dashboard actually loads into `web/static/data/` and
writes a manifest of what it took.

    derived/series/*.json     → static/data/series/
    derived/lexical/*.json    → static/data/lexical/
    derived/kwic/*.json       → static/data/kwic/
    derived/countries/*.json  → static/data/countries/
    derived/usage/*.json      → static/data/usage/
    derived/frames/*.json     → static/data/frames/

`09_export_speeches.py` is the one exception and writes its 425 MB straight to
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
from lib import artifacts, console, contract
from lib.paths import (
    CONTRACT,
    COUNTRIES,
    FRAMES,
    KWIC,
    LEXICAL,
    ROOT,
    SERIES,
    USAGE,
    WEB_DATA,
    ensure_dirs,
    rel,
)

#: (source directory, destination name, the step that produces it).
PARTS = [
    (SERIES, "series", "04_series.py"),
    (LEXICAL, "lexical", "05_lexical.py"),
    (KWIC, "kwic", "08_kwic.py"),
    # Two producers write here: 11 the rates, 12 the per-speaker keyness. Named
    # as both rather than as the first, so the manifest does not credit one
    # step's provenance to the other's file.
    (COUNTRIES, "countries", "11_countries.py + 12_speaker_keyness.py"),
    # 15 aggregates a committed model run. Unlike every other part here, its
    # input is not the corpus alone: `model_annotations/` is a versioned input
    # the deploy reads and can never regenerate, which is why the workflow now
    # keys its cache on that directory too.
    (USAGE, "usage", "15_usage.py"),
    (FRAMES, "frames", "17_frames.py"),
]

#: Written by 09, not copied. Listed so the manifest describes the whole payload
#: rather than only the part this script moved.
IN_PLACE = [("speeches", "09_export_speeches.py"), ("meetings.json", "09_export_speeches.py")]


def copy_part(source: Path, name: str) -> dict[str, object]:
    """Atomically mirror one directory into the payload and describe it."""
    destination = WEB_DATA / name
    if not source.exists():
        console.fail(f"{rel(source)} is missing — run the step that writes it first")
    with artifacts.atomic_directory(destination) as staged:
        shutil.copytree(source, staged, dirs_exist_ok=True)
    return artifacts.describe_tree(destination)


def measure(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"files": 0, "bytes": 0, "sha256": None}
    return artifacts.describe_tree(path)


def check_contract() -> None:
    """Refuse to publish a payload the dashboard was not written for.

    The seam is the honest place for this. Everything upstream asserts its own
    output against its own inputs; nothing asserted that the shape reaching the
    application is the shape the application reads, because that contract lived
    in three hand-kept copies across two languages. It now lives in
    `tests/contract/payload.json`, and this is where it is enforced — on real
    data, on every build, including the one GitHub Pages publishes from.

    What it catches is a field renamed, moved or no longer written. It does not
    check ranges, alignment or any of the substantive refusals
    `web/src/lib/data.ts` makes at the fetch boundary; those belong there, where
    a reader can be told why a figure will not be drawn.
    """
    if not CONTRACT.exists():
        console.fail(
            f"{rel(CONTRACT)} is missing — the payload has no declared shape to be checked "
            f"against. Regenerate it with `python scripts/export_web.py --update-contract`."
        )
    promised = json.loads(CONTRACT.read_text(encoding="utf-8"))
    problems, absent = contract.check(WEB_DATA, promised)
    for name in absent:
        console.warn(f"{name} is not in the payload, so its shape was not checked")
    if problems:
        console.fail(
            f"the payload no longer matches {rel(CONTRACT)}",
            [
                *problems[:20],
                *(
                    [f"... and {len(problems) - 20} more"]
                    if len(problems) > 20
                    else []
                ),
                "If the change is intended, re-run with --update-contract and review the diff.",
            ],
        )
    console.info(f"{len(promised) - len(absent)} artefacts match {rel(CONTRACT)}")


def update_contract() -> None:
    """Rewrite the declared shape from the payload that is actually there.

    Deliberately a separate, explicit run rather than something the export does
    when it notices a mismatch. A contract a script rewrites to match whatever
    it just produced asserts nothing; the change has to arrive as a diff a
    person reads.
    """
    shapes = contract.payload_skeleton(WEB_DATA)
    missing = [name for name in [*contract.TRACKED, contract.SPEECH_SAMPLE] if name not in shapes]
    if missing:
        console.fail(
            "refusing to declare a shape for a payload that is not fully built",
            [f"{name} is absent" for name in missing],
        )
    artifacts.atomic_write_text(
        CONTRACT, json.dumps(shapes, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    )
    console.info(f"wrote {rel(CONTRACT)}  ({len(shapes)} artefacts) — review the diff")


def run() -> None:
    ensure_dirs()
    # `parts` gets its own name and its own type. Built inside an untyped
    # `dict[str, object]`, every write to it needed a `type: ignore[index]`,
    # which silences the checker by asserting something the code did not know.
    parts: dict[str, dict[str, object]] = {}
    # Stamped when the export starts, as it always was: the manifest says when
    # the payload was made, and the copy below can take minutes.
    generated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_files = total_bytes = 0

    console.step("Copying analysis artefacts into the payload")
    for source, name, producer in PARTS:
        measured = copy_part(source, name)
        files, size = int(measured["files"]), int(measured["bytes"])
        parts[name] = {**measured, "produced_by": producer}
        total_files += files
        total_bytes += size
        console.info(f"{name:10s} {files:>6,} files  {size / 1e6:>7.1f} MB  (from {producer})")

    console.step("Measuring what 09 wrote in place")
    for name, producer in IN_PLACE:
        measured = measure(WEB_DATA / name)
        files, size = int(measured["files"]), int(measured["bytes"])
        if not files:
            console.warn(f"{name} is missing — run {producer}; the reader view will 404")
        parts[name] = {**measured, "produced_by": producer}
        total_files += files
        total_bytes += size
        console.info(f"{name:10s} {files:>6,} files  {size / 1e6:>7.1f} MB  (from {producer})")

    # Before the manifest, not after: the manifest is what marks a payload
    # complete, and a payload the dashboard cannot read is not one.
    console.step("Checking the payload against the shape the dashboard reads")
    check_contract()

    manifest = {
        "generated": generated,
        "git_commit": artifacts.git_commit(ROOT),
        "parts": parts,
        "files": total_files,
        "bytes": total_bytes,
    }
    artifacts.atomic_write_json(WEB_DATA / "manifest.json", manifest, indent=1)
    console.step("Done")
    console.info(f"{total_files:,} files, {total_bytes / 1e6:.0f} MB in {rel(WEB_DATA)}")
    console.info(f"wrote {rel(WEB_DATA / 'manifest.json')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-contract",
        action="store_true",
        help=(
            "rewrite tests/contract/payload.json from the payload that is already built, "
            "instead of exporting. Use when a shape change is intended, and read the diff."
        ),
    )
    args = parser.parse_args()
    if args.update_contract:
        update_contract()
        return
    run()


if __name__ == "__main__":
    main()
