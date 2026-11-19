"""Package a release's files, with their checksums and the hashes the notes cite.

    python tools/package_release.py v0.1.0                    # derived tables and site
    python tools/package_release.py v0.1.0 --with-speeches    # and the speech parquets
    python tools/package_release.py v0.1.0 --gold             # and the gold sample files

Run in the clean clone `docs/RELEASING.md` builds the release from, after
`make payload`, `export_web.py --release` and `npm --prefix web run build`. It
writes into `dist/`:

- `derived-tables-<tag>.zip`: `data/derived/`, without the speech parquets
  unless `--with-speeches` says so (they are the corpus, which has its own DOI);
- `site-<tag>.zip`: `web/build/`, the static site as built;
- `gold-sample-<tag>.zip` with `--gold`: every `genocide_gold_*.csv` step 13
  writes and the annotation file;
- `SHA256SUMS.txt`: one line per archive, in the format `sha256sum -c` reads.

It prints the `analysis_hash` of the three artefacts the release notes cite
(step 6 of RELEASING), read from their `meta` blocks. It refuses to package
what is not there and never overwrites an archive: a release is made once.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from collections.abc import Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import console, model_runs
from lib.artifacts import read_json
from lib.paths import DERIVED, INTERIM, ROOT, rel

DIST = ROOT / "dist"
SITE = ROOT / "web" / "build"
WEB_DATA = ROOT / "web" / "static" / "data"

#: The speech tables: the corpus itself, packaged only on request.
SPEECH_TABLES = ("speeches.parquet", "speeches_norm.parquet", "speeches_flagged.parquet")

#: The artefacts whose `analysis_hash` the release notes quote.
CITED = ("series/annual.json", "kwic/genocide.json", "usage/usage.json")

def gold_files() -> list[Path]:
    """The gold sample as drawn (every `genocide_gold_*.csv` step 13 writes:
    candidates, frames, design, packet, review) and as coded."""
    drawn = sorted(INTERIM.glob("genocide_gold_*.csv"))
    return [*drawn, model_runs.GOLD_ANNOTATIONS] if drawn else []


def files_under(root: Path, skip: Iterable[str] = ()) -> list[Path]:
    """Every file below `root`, sorted, less those named in `skip`."""
    left_out = set(skip)
    return sorted(
        path for path in root.rglob("*") if path.is_file() and path.name not in left_out
    )


def archive(target: Path, files: list[Path], base: Path) -> Path:
    """Zip `files` under their paths relative to `base`, refusing to overwrite."""
    if target.exists():
        raise console.Refusal(f"{rel(target)} exists", ["a release is packaged once; remove it first"])
    if not files:
        raise console.Refusal(f"nothing to put in {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".zip.partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in files:
            zipped.write(path, path.relative_to(base).as_posix())
    partial.replace(target)
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def checksums(archives: list[Path]) -> str:
    """`SHA256SUMS.txt`: `<hash>  <name>`, two spaces, as `sha256sum -c` reads it."""
    return "".join(f"{sha256(path)}  {path.name}\n" for path in archives)


def cited_hashes(root: Path = WEB_DATA) -> dict[str, str]:
    """The `analysis_hash` of each artefact the release notes quote."""
    out = {}
    for relative in CITED:
        path = root / relative
        if not path.is_file():
            raise console.Refusal(f"{rel(path)} is missing", ["run make payload first"])
        meta = read_json(path)
        found = meta.get("meta", {}).get("analysis_hash") if isinstance(meta, dict) else None
        if not found:
            raise console.Refusal(f"{rel(path)} carries no analysis_hash")
        out[relative] = str(found)
    return out


def package(tag: str, *, with_speeches: bool, gold: bool, dist: Path = DIST) -> list[Path]:
    if not re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", tag):
        raise console.Refusal(f"{tag!r} is not a release tag such as v0.1.0")
    if not DERIVED.is_dir():
        raise console.Refusal(f"{rel(DERIVED)} is missing", ["run make payload first"])
    if not (SITE / "index.html").is_file():
        raise console.Refusal(f"{rel(SITE)} is not built", ["run npm --prefix web run build first"])
    made = [
        archive(
            dist / f"derived-tables-{tag}.zip",
            files_under(DERIVED, () if with_speeches else SPEECH_TABLES),
            DERIVED.parent,
        ),
        archive(dist / f"site-{tag}.zip", files_under(SITE), SITE.parent),
    ]
    if gold:
        files = gold_files()
        if not files or not model_runs.GOLD_ANNOTATIONS.is_file():
            raise console.Refusal("the gold sample is not there", ["run make payload first"])
        made.append(archive(dist / f"gold-sample-{tag}.zip", files, ROOT))
    (dist / "SHA256SUMS.txt").write_text(checksums(made), encoding="utf-8", newline="\n")
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="the release tag, such as v0.1.0")
    parser.add_argument("--with-speeches", action="store_true", help="include the speech parquets")
    parser.add_argument("--gold", action="store_true", help="include the gold sample files")
    args = parser.parse_args()
    hashes = cited_hashes()
    made = package(args.tag, with_speeches=args.with_speeches, gold=args.gold)
    for path in made:
        console.info(f"wrote {rel(path)}  {path.stat().st_size / 1e6:,.1f} MB")
    console.info(f"wrote {rel(DIST / 'SHA256SUMS.txt')}")
    console.step("analysis_hash for the release notes")
    console.table([(name, value) for name, value in hashes.items()])


if __name__ == "__main__":
    console.main(main)
