"""Read-only validation shared by sampling, triangulation and aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from . import audit, lexicon, llm
from .paths import ANNOTATIONS, MODEL_ANNOTATIONS


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
    referents = audit.read_referent_list(ANNOTATIONS / "lexicon" / "referents.csv")
    lex = lexicon.load()
    library = llm.load_prompt_library(MODEL_ANNOTATIONS / "genocide" / "PROMPT.md")
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
