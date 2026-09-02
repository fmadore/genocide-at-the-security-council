"""Shared paths and small helpers.

Every script imports from here so there is exactly one definition of where
things live. Import with:

    import sys; sys.path.insert(0, str(Path(__file__).parent))
    from lib.paths import RAW, DERIVED, NOTES
"""

from __future__ import annotations

import os
from pathlib import Path

from .artifacts import atomic_write_text

ROOT = Path(__file__).resolve().parents[2]


def _root(variable: str, default: Path) -> Path:
    """A directory root, overridable from the environment.

    Only the end-to-end test in `tests/test_end_to_end.py` sets these: it runs
    the numbered scripts as subprocesses over a synthetic corpus and must not
    write into the repository's own `data/`, `notes/` or `web/static/data/`.
    Everything else leaves them unset and gets the tree the docs describe.
    """
    value = os.environ.get(variable)
    return Path(value).resolve() if value else default


DATA = _root("GENOCIDE_DATA_ROOT", ROOT / "data")
RAW = DATA / "raw"          # as downloaded from Dataverse — never modified
INTERIM = DATA / "interim"  # intermediate artefacts
DERIVED = DATA / "derived"  # canonical parquet + analysis outputs

CONFIG = ROOT / "config"
DOCS = ROOT / "docs"
NOTES = _root("GENOCIDE_NOTES_ROOT", ROOT / "notes")  # Markdown findings notes emitted by scripts
WEB_DATA = _root("GENOCIDE_WEB_DATA_ROOT", ROOT / "web" / "static" / "data")  # dashboard payloads

# The shape the dashboard is written against, committed and reviewed as a diff.
# `export_web.py` checks the payload against it at the seam; see lib/contract.py.
CONTRACT = ROOT / "tests" / "contract" / "payload.json"

# --- Canonical data -------------------------------------------------------
SPEECHES = DERIVED / "speeches.parquet"           # 01 — raw join, never edited
MEETINGS = DERIVED / "meetings.parquet"           # 01
SPEECHES_NORM = DERIVED / "speeches_norm.parquet"      # 02 — normalised
SPEECHES_FLAGGED = DERIVED / "speeches_flagged.parquet"  # 03 — lexicon columns

# --- Durable annotation stores --------------------------------------------
# Both are version-controlled inputs the pipeline reads and never rebuilds.
# `annotations/` is human-owned: no script writes there (see annotations/README.md).
# `model_annotations/` holds committed model runs: 14 writes a run once, by hand;
# every later step treats it as read-only input, like the human file.
ANNOTATIONS = ROOT / "annotations"
MODEL_ANNOTATIONS = ROOT / "model_annotations"

# --- Hand-checked analysis inputs -----------------------------------------
# These are curated artefacts under version control, not computed outputs.
# A script that consumes one must fail loudly on any value it has never seen,
# otherwise new data silently drops out of the analysis.
LEXICON = CONFIG / "lexicon.yml"
# Digests of the lexicon's patterns beside the version each is declared to date
# from, so an edited pattern whose `pattern_since` was left behind fails at
# `lexicon.load()` rather than validating artefacts cut from the old regex.
# Written by tools/lock_lexicon.py and committed beside the config it locks.
LEXICON_LOCK = CONFIG / "lexicon.lock.json"
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
# 15 joins the committed model run to the corpus and aggregates it for the
# usage view. Everything in it is derived from model_annotations/ plus the
# flagged parquet, so it rebuilds anywhere those two exist.
USAGE = DERIVED / "usage"          # 15
# 17 files every occurrence of the node under the construction it appears in.
# Beside kwic/ rather than inside it: 08's directory is one file per term and is
# read a term at a time, while this is one term cut every way at once, and the
# export copies a directory wholesale.
FRAMES = DERIVED / "frames"        # 17
MANIFESTS = DERIVED / "manifests"  # machine-readable provenance, all stages

# Harvard Dataverse
DOI = "doi:10.7910/DVN/KGVSYH"
DATAVERSE = "https://dataverse.harvard.edu"
DATASET_VERSION = "6.1"

# Ground truth from the codebook, asserted by the build. `EXPECTED_TOKENS` is
# quanteda's count over the full text of every speech, punctuation and numbers
# included, and it is kept as provenance: reproducing it is what says the tar
# and the TSV describe the same corpus. It is *not* the denominator of a rate —
# see `EXPECTED_WORDS`.
EXPECTED_SPEECHES = 106_302
EXPECTED_TOKENS = 66_392_703

# Words in the speech bodies, counted with `lib.lexical.TOKEN_RE` and asserted
# by 02. This is the denominator every "per 100,000 words" figure divides by.
#
# Until 2 September 2026 those figures divided by `EXPECTED_TOKENS` instead
# (review of 1 September 2026, §3.3). Two things were wrong with that. The
# codebook's tokens include punctuation and numbers, so the denominator was
# 12.7% larger than the number of words and every published rate was 11.3%
# below what its own label claimed; and the label said "words", which was not
# what had been counted. Of the two remedies the review named — count words
# once, or relabel the unit "tokens (codebook)" — this is the first, because
# the numerator is a count of words in speech bodies and the language page
# already reports its universe in these same units. Relabelling would have left
# a rate whose numerator and denominator came from different tokenisers and
# different texts.
EXPECTED_WORDS = 58_904_180


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
