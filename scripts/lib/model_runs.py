"""The model-annotation store, and the read-only validation every reader shares.

Sampling (13), annotation (14), aggregation (15) and frame triangulation (17)
each used to name the store's files, read its pointer files and carry the
population they assert as constants of their own. They are named here once,
and the population comes from `config/lexicon.counts.json`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from . import audit, lexicon, llm
from .paths import ANNOTATIONS, INTERIM, MODEL_ANNOTATIONS, REFERENTS, rel

#: The one term the model-assisted layer covers; see Phase L in docs/PLAN.md
#: for why the scope is a single word.
TERM = "genocide"

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
#: The occurrences behind the prompt's worked examples, which 13 keeps out of
#: every gold frame; written by `tools/map_prompt_examples.py`.
PROMPT_EXAMPLES = STORE / "prompt_examples.csv"
RUNS = STORE / "runs"
#: The run the dashboard publishes, the counter-instrument read against it,
#: and the one run allowed to publish with a coverage gap. One run id each, or
#: empty; committed and changed as reviewed diffs.
CURRENT_RUN = STORE / "current_run.txt"
COMPARISON_RUN = STORE / "comparison_run.txt"
ALLOW_PARTIAL_RUN = STORE / "allow_partial_run.txt"

# `REFERENTS`, the controlled list, is shared with 03's audit and so lives in
# `lib.paths`; it is imported above and read here as `model_runs.REFERENTS`.
GOLD_ANNOTATIONS = ANNOTATIONS / TERM / "annotations.csv"
SMOKE_RUNS = INTERIM / "model_annotation_smoke"

#: The gold sample 13 draws: every candidate row, the design that weights a
#: coded unit back to the corpus, and the blinded packet a coder opens. 15
#: reports on the first two and `tools/coding_page.py` renders the third.
GOLD_CANDIDATES = INTERIM / "genocide_gold_candidates.csv"
GOLD_DESIGN = INTERIM / "genocide_gold_design.csv"
GOLD_PACKET = INTERIM / "genocide_gold_packet.csv"


def pointer(path: Path) -> str:
    """The run id a pointer file names, or the empty string."""
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def partial_allowed(run_id: str) -> bool:
    """Whether `ALLOW_PARTIAL_RUN` names this committed run.

    Read by 15 itself, so `python scripts/15_usage.py` publishes the run `make`
    publishes: the allowance used to live only in the Makefile, which turned it
    into `--allow-partial`, and running the step directly refused the published
    run. A run read by path rather than by id is never allowed this way.
    """
    return bool(run_id) and run_id == pointer(ALLOW_PARTIAL_RUN)


def population_problems(
    filenames: Iterable[str], occurrences: int, expected: tuple[int, int] | None = None
) -> list[str]:
    """Reasons an enumeration of `TERM` is not the committed one, if any.

    `expected` is `(speeches, occurrences)`; by default the committed counts,
    which 03 has already held the corpus to. A gold sample, a model run and
    their aggregation are comparable only when all three enumerate this same
    population, so it is asserted by each rather than assumed from the others.
    """
    speeches_expected, occurrences_expected = expected or lexicon.population(TERM)
    speeches = len(set(filenames))
    problems = []
    if occurrences != occurrences_expected:
        problems.append(
            f"{occurrences:,} occurrences against the {occurrences_expected:,} committed in "
            f"{rel(lexicon.LEXICON_COUNTS)}"
        )
    if speeches != speeches_expected:
        problems.append(
            f"{speeches:,} speeches against the {speeches_expected:,} committed in "
            f"{rel(lexicon.LEXICON_COUNTS)}"
        )
    return problems


def files(directory: Path) -> list[Path]:
    return [directory / "manifest.json", directory / "annotations.jsonl"]


def read(directory: Path) -> tuple[dict, list[dict]]:
    manifest_path, rows_path = files(directory)
    if (directory / "pending.json").exists():
        raise ValueError("Run has an unfinished transaction; recover it before reading")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != directory.name:
        raise ValueError("Run directory and manifest identity disagree")
    rows = llm.read_rows(rows_path)
    if not rows:
        raise ValueError("Run contains no annotations")
    validate(manifest, rows)
    return manifest, rows


def validate(manifest: dict, rows: list[dict]) -> None:
    seen = set()
    for row in rows:
        identifier = row.get("occurrence_id")
        if not identifier or identifier in seen:
            raise ValueError(f"Missing or duplicate occurrence_id: {identifier}")
        seen.add(identifier)
        if "referents_version" in row and str(row["referents_version"]) != str(manifest.get("referents_version", "")):
            raise ValueError("Row/manifest mismatch in referents_version")
        for field in ("run_id", "term", "model", "reasoning_effort", "prompt_sha256", "prompt_version", "schema_version", "lexicon_version"):
            if str(row.get(field, "")) != str(manifest.get(field, "")):
                raise ValueError(f"Row/manifest mismatch in {field}")


def resolved(directory: Path) -> list[dict]:
    manifest, rows = read(directory)
    referents = audit.read_referent_list(REFERENTS)
    lex = lexicon.load()
    library = llm.load_prompt_library(PROMPT)
    if library.by_digest(str(manifest.get("prompt_sha256", ""))) is None:
        raise ValueError("Run prompt digest is not in the prompt archive")
    output = []
    for row in rows:
        llm.validate_row(row, referents.all, appending=False)
        if not lex.compatible(str(row["term"]), str(row["lexicon_version"])):
            raise ValueError("Run uses an incompatible lexicon")
        if not referents.compatible(str(row["referent"]), str(row.get("referents_version", "1"))):
            raise ValueError("Run uses an incompatible referent")
        translated = llm.resolve_row(row)
        translated["referent"] = referents.resolve(str(translated["referent"]))
        output.append(translated)
    return output
