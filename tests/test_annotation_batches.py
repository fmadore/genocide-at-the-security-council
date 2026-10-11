import copy
import dataclasses
import json
from types import SimpleNamespace

import pytest
from lib import annotation_batches as batches
from lib import run_store


def population():
    return [SimpleNamespace(custom_id=f"s{i}", occurrences=[SimpleNamespace(occurrence_id=f"o{i}")])
            for i in range(7)]


def test_partition_is_bounded_disjoint_complete_and_stable():
    speeches = population()
    document = batches.plan(speeches, 3)
    assert document == batches.plan(speeches, 3)
    selected = [batches.select(document, speeches, i) for i in range(3)]
    assert max(map(len, selected)) <= 3
    assert sorted(s.custom_id for group in selected for s in group) == [s.custom_id for s in speeches]
    bad = copy.deepcopy(document)
    bad["batches"][1][0] = bad["batches"][0][0]
    with pytest.raises(ValueError, match="partition"):
        batches.select(bad, speeches, 0)
    with pytest.raises(ValueError, match="partition"):
        batches.select(document, speeches[:-1], 0)
    with pytest.raises(ValueError, match="index"):
        batches.select(document, speeches, -1)


def shards(tmp_path):
    speeches = population()
    document = batches.plan(speeches, 3)
    paths = []
    for index in range(3):
        selected = batches.select(document, speeches, index)
        path = tmp_path / f"batch-{index}"
        path.mkdir()
        settings = {"model": "test", "prompt_sha256": "p", "prompt_version": 3,
                        "referents_sha256": "r", "referents_version": "2", "schema_version": "3.1",
                        "lexicon_version": 6, "runtime": {"model_revision": "pinned"},
                        "reasoning_effort": "max", "term": "genocide"}
        identity = {**settings, "run_id": path.name, "probe_sha256": "probe", "population": document["population"],
                    "selected_speeches": sorted(s.custom_id for s in selected),
                    "batch": {"plan_sha256": run_store.digest(document), "index": index}}
        manifest = {**settings, "run_id": path.name, "identity_sha256": run_store.digest(identity),
                    "probe_sha256": "probe", "status": "complete", "parse_failures": 0,
                    "created": "2026-09-09", "completed": "2026-09-10", "passes": [],
                    "requests": dict.fromkeys(("planned", "sent", "returned", "complete"), len(selected)),
                    "occurrences": {"planned": len(selected), "written": len(selected)},
                    "usage": {"output_tokens": 10}, "evidence_invalid": 0,
                    "evidence_relocated": 0, "truncation_count": 0}
        rows = [{**settings, "run_id": path.name, "occurrence_id": s.occurrences[0].occurrence_id}
                for s in selected]
        (path / "manifest.json").write_text(json.dumps(manifest))
        (path / "identity.json").write_text(json.dumps(identity))
        (path / "annotations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        paths.append(path)
    return document, speeches, paths


def test_merge_preserves_sources_and_accounts_for_complete_union(tmp_path):
    document, speeches, paths = shards(tmp_path)
    before = (paths[0] / "annotations.jsonl").read_bytes()
    merged = batches.merge(document, speeches, paths, tmp_path / "assembled")
    assert merged["requests"]["complete"] == 7
    assert merged["occurrences"]["written"] == 7
    assert merged["usage"]["output_tokens"] == 30
    assert len(merged["assembly"]["sources"]) == 3
    assert (paths[0] / "annotations.jsonl").read_bytes() == before
    with pytest.raises(ValueError, match="exists"):
        batches.merge(document, speeches, paths, tmp_path / "assembled")


@pytest.mark.parametrize("fault", ["missing", "duplicate", "incomplete", "runtime", "rows"])
def test_merge_refuses_bad_shards_without_writing_output(tmp_path, fault):
    document, speeches, paths = shards(tmp_path)
    if fault == "missing":
        paths.pop()
    elif fault == "duplicate":
        paths[1] = paths[0]
    elif fault == "rows":
        with (paths[0] / "annotations.jsonl").open("a") as stream:
            stream.write((paths[0] / "annotations.jsonl").read_text(encoding="utf-8").splitlines()[0] + "\n")
    else:
        path = paths[0] / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if fault == "incomplete":
            manifest["status"] = "in_progress"
        else:
            manifest["runtime"] = {"model_revision": "different"}
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        batches.merge(document, speeches, paths, tmp_path / "assembled")
    assert not (tmp_path / "assembled").exists()


def leave_gap(path, speech_id, failure=True):
    """Turn one batch into a run that never answered `speech_id`."""
    rows = [json.loads(line) for line in (path / "annotations.jsonl").read_text(encoding="utf-8").splitlines()]
    kept = [row for row in rows if row["occurrence_id"] != "o" + speech_id[1:]]
    (path / "annotations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in kept))
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(status="in_progress", parse_failures=1, completed=None,
                    passes=[{"at": "2026-10-10T07:13:57Z"}])
    manifest["requests"]["complete"] -= 1
    manifest["occurrences"]["written"] -= 1
    (path / "manifest.json").write_text(json.dumps(manifest))
    if failure:
        (path / "failures.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (
            {"custom_id": speech_id, "kind": "truncation", "reason": "first", "recorded_at": "2026-09-24"},
            {"custom_id": speech_id, "kind": "validation_failure", "reason": "last", "recorded_at": "2026-10-10"},
        )))


def test_merge_keeps_a_named_gap_with_its_last_recorded_failure(tmp_path):
    document, speeches, paths = shards(tmp_path)
    leave_gap(paths[0], "s0")
    merged = batches.merge(document, speeches, paths, tmp_path / "assembled", ["s0"])
    assert merged["status"] == "partial"
    assert merged["parse_failures"] == 1
    assert merged["requests"]["complete"] == 6
    assert merged["occurrences"] == {"planned": 7, "written": 6}
    assert merged["completed"] == "2026-10-10T07:13:57Z"
    [gap] = merged["gaps"]
    assert gap == {"custom_id": "s0", "batch": "batch-0", "occurrence_ids": ["o0"],
                   "kind": "validation_failure", "reason": "last", "recorded_at": "2026-10-10"}
    written = (tmp_path / "assembled" / "annotations.jsonl").read_text(encoding="utf-8")
    assert '"o0"' not in written


def test_a_complete_merge_lists_no_gaps(tmp_path):
    document, speeches, paths = shards(tmp_path)
    merged = batches.merge(document, speeches, paths, tmp_path / "assembled")
    assert merged["status"] == "complete"
    assert merged["gaps"] == []


@pytest.mark.parametrize("fault", ["unnamed", "answered", "stranger", "twice", "unrecorded"])
def test_merge_refuses_a_gap_that_is_not_named_outstanding_and_recorded(tmp_path, fault):
    document, speeches, paths = shards(tmp_path)
    leave_gap(paths[0], "s0", failure=fault != "unrecorded")
    gaps = {"unnamed": [], "answered": ["s0", "s1"], "stranger": ["s0", "s99"],
            "twice": ["s0", "s0"], "unrecorded": ["s0"]}[fault]
    with pytest.raises(ValueError):
        batches.merge(document, speeches, paths, tmp_path / "assembled", gaps)
    assert not (tmp_path / "assembled").exists()


@dataclasses.dataclass(frozen=True)
class Speech:
    custom_id: str
    occurrences: list


def test_within_drops_only_what_a_declared_widening_added():
    occurrence = lambda name: SimpleNamespace(occurrence_id=name)  # noqa: E731
    before = [Speech("s0", [occurrence("o0")]), Speech("s1", [occurrence("o1")])]
    document = batches.plan(before, 1)
    after = [Speech("s0", [occurrence("o0"), occurrence("o0b")]), Speech("s1", [occurrence("o1")]),
             Speech("s2", [occurrence("o2")])]
    assert batches.within(document, before, widened=False) == before
    with pytest.raises(ValueError, match="current enumeration"):
        batches.within(document, after, widened=False)
    cut = batches.within(document, after, widened=True)
    assert [(s.custom_id, [o.occurrence_id for o in s.occurrences]) for s in cut] == [
        ("s0", ["o0"]), ("s1", ["o1"])]
    assert batches.select(document, cut, 0)[0].custom_id == "s0"
    moved = [Speech("s0", [occurrence("o0x")]), Speech("s1", [occurrence("o1")])]
    with pytest.raises(ValueError, match="current enumeration"):
        batches.within(document, moved, widened=True)
