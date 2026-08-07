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

# --- Canonical data -------------------------------------------------------
SPEECHES = DERIVED / "speeches.parquet"           # 01 — raw join, never edited
MEETINGS = DERIVED / "meetings.parquet"           # 01
SPEECHES_NORM = DERIVED / "speeches_norm.parquet"      # 02 — normalised
SPEECHES_FLAGGED = DERIVED / "speeches_flagged.parquet"  # 03 — lexicon columns

# --- Hand-checked analysis inputs -----------------------------------------
# These are curated artefacts under version control, not computed outputs.
# A script that consumes one must fail loudly on any value it has never seen,
# otherwise new data silently drops out of the analysis.
LEXICON = CONFIG / "lexicon.yml"
ENTITIES = CONFIG / "entities.csv"
COUNTRY_ALIASES = CONFIG / "country_aliases.csv"
COUNCIL_MEMBERSHIP = CONFIG / "council_membership.csv"

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


def rel(path: Path) -> str:
    """Render a path relative to the repository root, for readable logs."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)
