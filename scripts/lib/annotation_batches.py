"""Immutable speech assignments and strict assembly of independent model runs."""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import artifacts, model_runs, run_store


def plan(speeches, size: int) -> dict:
    if size < 1 or not speeches:
        raise ValueError("Batch size and population must be positive")
    # Round-robin by corpus order spreads early/late speeches across batches.
    count = math.ceil(len(speeches) / size)
    ids = [speech.custom_id for speech in speeches]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate speech identifiers")
    return {
        "version": 1,
        "population": sorted(o.occurrence_id for s in speeches for o in s.occurrences),
        "batches": [ids[index::count] for index in range(count)],
    }


def select(document: dict, speeches, index: int):
    batches = document["batches"]
    ids = [identifier for batch in batches for identifier in batch]
    actual = {s.custom_id: s for s in speeches}
    population = sorted(o.occurrence_id for s in speeches for o in s.occurrences)
    if (document.get("version") != 1 or not batches or any(not b for b in batches)
            or len(ids) != len(set(ids)) or set(ids) != set(actual)
            or document["population"] != population):
        raise ValueError("Batch plan does not partition the current corpus exactly")
    if not 0 <= index < len(batches):
        raise ValueError("Batch index outside plan")
    return [actual[identifier] for identifier in batches[index]]


def merge(document: dict, speeches, sources: list[Path], output: Path) -> dict:
    """Require every complete shard; never silently publish a partial union."""
    if output.exists():
        raise ValueError("Merge output already exists; use a fresh run id")
    if len(sources) != len(document["batches"]):
        raise ValueError("Missing or extra batch directories")
    records, manifests, provenance, seen_batches = [], [], [], set()
    common = None
    for directory in sources:
        manifest, rows = model_runs.read(directory)
        identity = json.loads((directory / "identity.json").read_text())
        if run_store.digest(identity) != manifest.get("identity_sha256"):
            raise ValueError("Batch identity digest mismatch")
        for key in ("run_id", "runtime", "prompt_sha256", "referents_sha256", "schema_version", "probe_sha256"):
            if identity.get(key) != manifest.get(key):
                raise ValueError("Batch manifest and identity disagree")
        batch = identity.get("batch", {})
        index = batch.get("index", -1)
        if batch.get("plan_sha256") != run_store.digest(document) or index in seen_batches:
            raise ValueError("Wrong plan or duplicate batch")
        selected = select(document, speeches, index)
        expected = {o.occurrence_id for s in selected for o in s.occurrences}
        if (manifest["status"] != "complete" or manifest["parse_failures"]
                or {r["occurrence_id"] for r in rows} != expected
                or identity["selected_speeches"] != sorted(s.custom_id for s in selected)
                or identity["population"] != document["population"]
                or manifest["occurrences"]["written"] != len(rows)
                or manifest["occurrences"]["planned"] != len(expected)
                or manifest["requests"]["complete"] != len(selected)
                or manifest["requests"]["planned"] != len(selected)):
            raise ValueError("Batch is incomplete or coverage disagrees")
        fields = ("model", "prompt_sha256", "prompt_version", "referents_sha256",
                  "referents_version", "schema_version", "lexicon_version", "runtime",
                  "reasoning_effort", "term")
        settings = {key: manifest[key] for key in fields}
        if common is not None and common != settings:
            raise ValueError("Batch instruments or runtimes differ")
        common = settings
        seen_batches.add(index)
        records.extend({**row, "run_id": output.name} for row in rows)
        manifests.append(manifest)
        provenance.append({"run_id": directory.name, "identity_sha256": run_store.digest(identity),
                           "manifest_sha256": artifacts.sha256(directory / "manifest.json"),
                           "annotations_sha256": artifacts.sha256(directory / "annotations.jsonl"),
                           "probe_sha256": manifest["probe_sha256"]})
    if {r["occurrence_id"] for r in records} != set(document["population"]):
        raise ValueError("Merged population mismatch")
    merged = {**manifests[0], "run_id": output.name, "limit": None,
              "created": min(m["created"] for m in manifests),
              "completed": max(m["completed"] for m in manifests),
              "requests": {key: sum(m["requests"][key] for m in manifests)
                           for key in ("planned", "sent", "returned", "complete")},
              "occurrences": {"planned": len(records), "written": len(records)},
              "usage": {key: sum(m["usage"][key] for m in manifests) for key in manifests[0]["usage"]},
              "passes": [p for m in manifests for p in m["passes"]],
              "assembly": {"plan_sha256": run_store.digest(document), "sources": provenance}}
    for key in ("evidence_invalid", "evidence_relocated", "truncation_count"):
        merged[key] = sum(m[key] for m in manifests)
    # An assembly is a derived immutable run, not a live resumable writer.
    for key in ("identity_sha256", "probe_sha256", "git_commit"):
        merged.pop(key, None)
    model_runs.validate(merged, records)
    with artifacts.atomic_directory(output) as staged:
        artifacts.atomic_write_json(staged / "manifest.json", merged, indent=1)
        artifacts.atomic_write_json(staged / "batch-plan.json", document, indent=1)
        artifacts.atomic_write_text(staged / "annotations.jsonl", "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in sorted(records, key=lambda r: r["occurrence_id"])))
        # Preserve rejected attempts as history, even when retries succeeded.
        artifacts.atomic_write_text(staged / "failures.jsonl", "".join(
            (p / "failures.jsonl").read_text(encoding="utf-8")
            for p in sources if (p / "failures.jsonl").exists()))
    return merged
