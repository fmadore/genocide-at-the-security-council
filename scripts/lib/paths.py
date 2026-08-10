"""Shared paths and small helpers.

Every script imports from here so there is exactly one definition of where
things live. Import with:

    import sys; sys.path.insert(0, str(Path(__file__).parent))
    from lib.paths import RAW, DERIVED, NOTES
"""

from __future__ import annotations

from pathlib import Path

from .artifacts import atomic_write_text

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
EVENTS = CONFIG / "events.csv"
STOPWORDS = CONFIG / "stopwords.txt"

# --- Analysis artefacts ---------------------------------------------------
# One directory per step. These are the inputs the dashboard is assembled from;
# a later export step selects and copies what web/ actually ships, so that the
# artefacts stay inspectable whether or not the application exists yet.
SERIES = DERIVED / "series"      # 04
LEXICAL = DERIVED / "lexical"    # 05
# 06 before 07: the embedding-based half of the topic comparison reads the
# vectors, so topics-then-embeddings would have made an earlier step depend on a
# later one. These comments were the other way round when the directories were
# only reserved names; nothing had been built against that order.
EMBEDDINGS = DERIVED / "embeddings"  # 06 — GPU, see docs/CLUSTER.md
TOPICS = DERIVED / "topics"      # 07 — evaluation only, not a release artefact
LEMMAS = DERIVED / "lemmas"      # 10 — the lemma layer; feeds an optional re-run of 05
# 05 again, over lemmas instead of surface forms. A separate directory, never a
# replacement: the surface tables are what the dashboard reads and what the
# docs/PLAN.md §1.1 audit is being conducted against.
LEXICAL_LEMMA = DERIVED / "lexical_lemma"
KWIC = DERIVED / "kwic"          # 08
# 11 writes per-speaker rates, which are the actor view's and any map's only
# honest source. A directory of its own rather than another file in series/:
# series/ is cut by period, this is cut by speaker, and folding the two would
# put a table nobody asked for inside an artefact everyone already reads.
COUNTRIES = DERIVED / "countries"  # 11
MANIFESTS = DERIVED / "manifests"  # machine-readable provenance, all stages

# Harvard Dataverse
DOI = "doi:10.7910/DVN/KGVSYH"
DATAVERSE = "https://dataverse.harvard.edu"
DATASET_VERSION = "6.1"

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
    atomic_write_text(path, body)
    return path


def rel(path: Path) -> str:
    """Render a path relative to the repository root, for readable logs."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)
