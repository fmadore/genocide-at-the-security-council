"""Shared paths and small helpers.

Every script imports from here so there is exactly one definition of where
things live. Import with:

    import sys; sys.path.insert(0, str(Path(__file__).parent))
    from lib.paths import RAW, DERIVED, NOTES
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"          # as downloaded from Dataverse — never modified
INTERIM = DATA / "interim"  # intermediate artefacts
DERIVED = DATA / "derived"  # canonical parquet + analysis outputs

CONFIG = ROOT / "config"
DOCS = ROOT / "docs"
NOTES = ROOT / "notes"      # Markdown findings notes emitted by scripts
WEB_DATA = ROOT / "web" / "static" / "data"  # dashboard payloads

SPEECHES = DERIVED / "speeches.parquet"
MEETINGS = DERIVED / "meetings.parquet"

# Harvard Dataverse
DOI = "doi:10.7910/DVN/KGVSYH"
DATAVERSE = "https://dataverse.harvard.edu"

# Ground truth from the codebook, asserted by the build.
EXPECTED_SPEECHES = 106_302
EXPECTED_TOKENS = 66_392_703


def ensure_dirs() -> None:
    """Create every output directory. Safe to call repeatedly."""
    for d in (RAW, INTERIM, DERIVED, NOTES, WEB_DATA):
        d.mkdir(parents=True, exist_ok=True)


def write_note(name: str, body: str) -> Path:
    """Write a Markdown findings note into notes/ and return its path."""
    NOTES.mkdir(parents=True, exist_ok=True)
    path = NOTES / name
    path.write_text(body, encoding="utf-8")
    return path
