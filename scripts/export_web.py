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
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, console, contract, semantic_release
from lib.paths import (
    CONTRACT,
    COUNTRIES,
    DERIVED,
    FRAMES,
    KWIC,
    LEXICAL,
    ROOT,
    SERIES,
    SPEAKER_KEYNESS,
    SPEECHES_FLAGGED,
    USAGE,
    WEB_DATA,
    ensure_dirs,
    rel,
)

#: (source directories, destination name, the step that produces them).
#:
#: Several sources may share one destination, and `countries/` does: 11 writes
#: the rates and 12 the per-speaker keyness. They are separate directories under
#: `data/derived/` because `atomic_directory` owns whatever it swaps, and they
#: are one directory here because that is the shape the dashboard reads.
PARTS = [
    ((SERIES,), "series", "04_series.py"),
    ((LEXICAL,), "lexical", "05_lexical.py"),
    ((KWIC,), "kwic", "08_kwic.py"),
    ((COUNTRIES, SPEAKER_KEYNESS), "countries", "11_countries.py + 12_speaker_keyness.py"),
    # 15 aggregates a committed model run. Unlike every other part here, its
    # input is not the corpus alone: `model_annotations/` is a versioned input
    # the deploy reads and can never regenerate, which is why the workflow now
    # keys its cache on that directory too.
    ((USAGE,), "usage", "15_usage.py"),
    ((FRAMES,), "frames", "17_frames.py"),
    ((DERIVED / "actor_year",), "actor_year", "20_actor_year.py"),
    ((DERIVED / "semantic",), "semantic", "21_semantic_map.py"),
]

#: Written by 09, not copied. Listed so the manifest describes the whole payload
#: rather than only the part this script moved.
IN_PLACE = [
    ("speeches", "09_export_speeches.py"),
    ("meetings.json", "09_export_speeches.py"),
    ("scopes.json", "09_export_speeches.py"),
]


def copy_part(sources: Sequence[Path], name: str, *, root: Path | None = None) -> dict[str, object]:
    """Atomically mirror one or more directories into one payload directory.

    Every source is copied into the same staging directory and swapped in once.
    Copying them one at a time would mean one `atomic_directory` per source, and
    the second swap would delete what the first had just published — which is
    the fault this grouping exists to make unrepresentable, one level up from
    where it originally bit.
    """
    destination = (root or WEB_DATA) / name
    if name == "semantic":
        source = sources[0]
        if not source.exists():
            with artifacts.atomic_directory(destination) as staged:
                artifacts.atomic_write_json(staged / "map.json", {"status": "pending", "schema": 1})
            return artifacts.describe_tree(destination)
        # The artifact records its original Parquet bytes. Arrow versions can
        # serialize identical content differently. Only a pin bound to this
        # exact manifest may authorize comparison by canonical speech content.
        content_sha256 = None
        pin_path = ROOT / "config/semantic-release.json"
        if pin_path.is_file():
            pin = json.loads(pin_path.read_text(encoding="utf-8"))
            if artifacts.sha256(source / "manifest.json") == pin.get("manifest_sha256"):
                content_sha256 = pin.get("corpus_content_sha256")
        semantic_release.validate(source, SPEECHES_FLAGGED, content_sha256=content_sha256)
    for source in sources:
        if not source.exists():
            console.fail(f"{rel(source)} is missing — run the step that writes it first")
    with artifacts.atomic_directory(destination) as staged:
        for source in sources:
            shutil.copytree(source, staged, dirs_exist_ok=True)
    return artifacts.describe_tree(destination)


def measure(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"files": 0, "bytes": 0, "sha256": None}
    return artifacts.describe_tree(path)


def check_contract(root: Path | None = None) -> None:
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
    problems, absent = contract.check(root or WEB_DATA, promised)
    if absent:
        # Not a warning. The contract is the list of artefacts the dashboard
        # loads, so a payload missing one is a payload a view cannot render —
        # and a warning is exactly what let 19 artefacts ship as though they
        # were 20, with the actor view's keyness figure fetching a file that
        # was not there.
        console.fail(
            "the payload is missing artefacts the contract declares",
            [f"{name} — run the step that writes it, then export again" for name in sorted(absent)],
        )
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


def check_no_aggregates(root: Path | None = None) -> None:
    """Refuse a payload that publishes a measure summed over several terms.

    R7's rule, enforced where every other payload-wide rule is enforced rather
    than left to a reviewer noticing a familiar-looking key. The shape check
    above would pass a revived `registers` block without complaint — it is a
    well-formed object, and the contract deliberately treats a lexicon-keyed
    collection as opaque so that adding a term is not a breaking change. This is
    the check that reads what is in it.

    A population is not an aggregate and is not caught: R8's genocide-free
    corpus and R9's reading sets select speeches with a predicate over several
    terms and count each speech once. See `contract.roll_ups`.
    """
    found = contract.aggregates(root or WEB_DATA)
    if found:
        console.fail(
            "the payload carries a measure summed over more than one term",
            [
                *found[:20],
                *([f"... and {len(found) - 20} more"] if len(found) > 20 else []),
                "The site publishes one measure per term and the reader composes the "
                "group — see item R7 in docs/PLAN.md.",
            ],
        )
    console.info("no measure in the payload sums over more than one term")


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
    with artifacts.atomic_directory(WEB_DATA) as staged:
        # 09 owns these artifacts. Copy them into the candidate release before
        # validation; no live directory is changed until the entire candidate passes.
        for name, _ in IN_PLACE:
            source = WEB_DATA / name
            if not source.exists():
                console.fail(f"{rel(source)} is missing; run 09_export_speeches.py")
            if source.is_dir():
                shutil.copytree(source, staged / name)
            else:
                shutil.copy2(source, staged / name)
        assemble(staged)


def assemble(destination: Path) -> None:
    # `parts` gets its own name and its own type. Built inside an untyped
    # `dict[str, object]`, every write to it needed a `type: ignore[index]`,
    # which silences the checker by asserting something the code did not know.
    parts: dict[str, dict[str, object]] = {}
    # Stamped when the export starts, as it always was: the manifest says when
    # the payload was made, and the copy below can take minutes.
    generated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_files = total_bytes = 0

    console.step("Copying analysis artefacts into the payload")
    for sources, name, producer in PARTS:
        measured = copy_part(sources, name, root=destination)
        files, size = int(measured["files"]), int(measured["bytes"])
        parts[name] = {**measured, "produced_by": producer}
        total_files += files
        total_bytes += size
        console.info(f"{name:10s} {files:>6,} files  {size / 1e6:>7.1f} MB  (from {producer})")

    console.step("Measuring what 09 wrote in place")
    for name, producer in IN_PLACE:
        measured = measure(destination / name)
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
    check_contract(destination)
    check_no_aggregates(destination)

    manifest = {
        "generated": generated,
        "git_commit": artifacts.git_commit(ROOT),
        "parts": parts,
        "files": total_files,
        "bytes": total_bytes,
    }
    artifacts.atomic_write_json(destination / "manifest.json", manifest, indent=1)
    console.step("Done")
    console.info(f"{total_files:,} files, {total_bytes / 1e6:.0f} MB in {rel(WEB_DATA)}")
    console.info(f"wrote {rel(WEB_DATA / 'manifest.json')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify existing payload shapes and manifest hashes without writing")
    mode.add_argument(
        "--update-contract",
        action="store_true",
        help=(
            "rewrite tests/contract/payload.json from the payload that is already built, "
            "instead of exporting. Use when a shape change is intended, and read the diff."
        ),
    )
    args = parser.parse_args()
    if args.check:
        check_contract()
        check_no_aggregates()
        manifest = json.loads((WEB_DATA / "manifest.json").read_text(encoding="utf-8"))
        for name, described in manifest["parts"].items():
            if name not in {part for _, part, _ in PARTS} | {part for part, _ in IN_PLACE}:
                console.fail(f"unknown payload part {name}")
            actual = measure(WEB_DATA / name)
            if any(actual[key] != described[key] for key in ("files", "bytes", "sha256")):
                console.fail(f"payload manifest disagrees with {name}; rebuild before publishing")
        expected = {part for _, part, _ in PARTS} | {part for part, _ in IN_PLACE}
        if set(manifest["parts"]) != expected:
            console.fail("payload manifest has an incomplete part inventory")
        for key in ("files", "bytes"):
            if manifest[key] != sum(part[key] for part in manifest["parts"].values()):
                console.fail(f"payload manifest {key} total disagrees with its parts")
        return
    if args.update_contract:
        update_contract()
        return
    run()


if __name__ == "__main__":
    main()
