"""Immutable speech assignments and strict assembly of independent model runs."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Sequence
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


def within(document: dict, speeches, *, widened: bool):
    """The current enumeration, cut back to the population a plan was drawn from.

    A declared lexicon widening adds occurrences and moves none, so a plan drawn
    before it still names occurrences that exist, and the ones the widening
    added were never part of the run. `widened` says the lexicon declares such a
    widening since the run's version. Anything else that separates the plan from
    the corpus — an occurrence that moved or vanished — still refuses.
    """
    planned = set(document["population"])
    current = {o.occurrence_id for s in speeches for o in s.occurrences}
    if current == planned:
        return list(speeches)
    if not widened or not planned <= current:
        raise ValueError("Batch plan does not match the current enumeration")
    kept = []
    for speech in speeches:
        occurrences = [o for o in speech.occurrences if o.occurrence_id in planned]
        if occurrences:
            kept.append(dataclasses.replace(speech, occurrences=occurrences))
    return kept


def merge(document: dict, speeches, sources: list[Path], output: Path,
          gaps: Sequence[str] = ()) -> dict:
    """Require every shard to be complete, apart from the gaps the caller names.

    A gap is a speech its batch asked about and never got an acceptable answer
    for. Each one must be named, must still be outstanding in its batch and must
    have a recorded failure, which the merged manifest repeats beside it. A
    batch with any other speech outstanding is refused, so a partial union is
    never published silently.
    """
    if output.exists():
        raise ValueError("Merge output already exists; use a fresh run id")
    if len(sources) != len(document["batches"]):
        raise ValueError("Missing or extra batch directories")
    wanted = set(gaps)
    if len(wanted) != len(gaps):
        raise ValueError("A gap is named twice")
    records: list[dict] = []
    manifests: list[dict] = []
    provenance: list[dict] = []
    accepted: list[dict] = []
    absent: set[str] = set()
    seen_batches: set = set()
    common = None
    for directory in sources:
        manifest, rows = model_runs.read(directory)
        identity = json.loads((directory / "identity.json").read_text(encoding="utf-8"))
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
        missing = [s for s in selected if s.custom_id in wanted]
        expected = {o.occurrence_id for s in selected for o in s.occurrences}
        unanswered = {o.occurrence_id for s in missing for o in s.occurrences}
        if (manifest["status"] != ("in_progress" if missing else "complete")
                or manifest["parse_failures"] != len(missing)
                or {r["occurrence_id"] for r in rows} != expected - unanswered
                or identity["selected_speeches"] != sorted(s.custom_id for s in selected)
                or identity["population"] != document["population"]
                or manifest["occurrences"]["written"] != len(rows)
                or manifest["occurrences"]["planned"] != len(expected)
                or manifest["requests"]["complete"] != len(selected) - len(missing)
                or manifest["requests"]["planned"] != len(selected)):
            raise ValueError("Batch is incomplete or coverage disagrees")
        # The last failure recorded for a speech is the reason it is still a gap.
        failures = {str(row.get("custom_id", "")): row
                    for row in model_runs.read_rows(directory / "failures.jsonl")}
        for speech in missing:
            failure = failures.get(speech.custom_id)
            if failure is None:
                raise ValueError(f"Gap {speech.custom_id} has no recorded failure")
            accepted.append({"custom_id": speech.custom_id, "batch": directory.name,
                             "occurrence_ids": sorted(o.occurrence_id for o in speech.occurrences),
                             "kind": failure.get("kind", ""), "reason": failure.get("reason", ""),
                             "recorded_at": failure.get("recorded_at", "")})
        absent |= unanswered
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
    if stray := wanted - {gap["custom_id"] for gap in accepted}:
        raise ValueError(f"Named gaps outside every batch: {', '.join(sorted(stray))}")
    if {r["occurrence_id"] for r in records} != set(document["population"]) - absent:
        raise ValueError("Merged population mismatch")
    # A batch left with a gap never records `completed`; its last pass ended it.
    ended = [m["completed"] or max(str(p["at"]) for p in m["passes"]) for m in manifests]
    merged = {**manifests[0], "run_id": output.name, "limit": None,
              "status": "partial" if accepted else "complete",
              "created": min(m["created"] for m in manifests),
              "completed": max(ended),
              "requests": {key: sum(m["requests"][key] for m in manifests)
                           for key in ("planned", "sent", "returned", "complete")},
              "occurrences": {"planned": len(document["population"]), "written": len(records)},
              "parse_failures": len(accepted),
              "gaps": sorted(accepted, key=lambda gap: gap["custom_id"]),
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
