"""Incremental recipe selection over a synthetic tree, using GNU make when available."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_deploy_tracks_graph_and_contract():
    source = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(source)
    trigger = workflow.get("on", workflow.get(True))
    cache = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("id") == "keys")
    for path in ["Makefile", "tests/contract/payload.json"]:
        assert path in trigger["push"]["paths"]
        assert f"'{path}'" in cache["run"]
    assert any(step.get("run") == "python scripts/export_web.py --check"
               for step in workflow["jobs"]["build"]["steps"])


@pytest.mark.parametrize("changed,expected", [
    ("annotations/lexicon/referents.csv", ["03_lexicon.py", "13_gold_sample.py", "15_usage.py"]),
    ("model_annotations/genocide/current_run.txt", ["13_gold_sample.py", "15_usage.py", "17_frames.py"]),
    ("model_annotations/genocide/prompts/v2.md", ["13_gold_sample.py", "15_usage.py"]),
    ("data/derived/series/quarterly.json", ["04_series.py"]),
])
def test_incremental_inputs_and_missing_secondary_output(tmp_path, changed, expected):
    make = shutil.which("make")
    if not make:
        pytest.skip("GNU make is required; this regression runs on the Linux CI runner")
    source = (ROOT / "Makefile").read_text(encoding="utf-8")
    # Materialize explicit files and wildcard members from the real tree, not
    # a second hand-written graph. Replace recipes with touch-free echo for -n.
    tracked = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    for name in tracked:
        path = ROOT / name
        relative = Path(name)
        if path.is_file() and relative.parts[0] in {"scripts", "config", "annotations", "model_annotations", "tests"}:
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            os.utime(target, (100, 100))
    # make -pn supplies the expanded targets of grouped rules.
    (tmp_path / "Makefile").write_text(source, encoding="utf-8")
    database = subprocess.run([make, "-pn", "payload"], cwd=tmp_path, capture_output=True, text=True, check=False).stdout
    for name in re.findall(r"^(data/[^:$\s]+|web/static/data/[^:$\s]+):", database, re.M):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        os.utime(target, (200, 200))
    baseline = subprocess.run([make, "-n", "payload"], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert not any(recipe in baseline.stdout for recipe in expected)
    target = tmp_path / changed
    if changed.startswith("data/"):
        target.unlink()
    else:
        os.utime(target, (300, 300))
    result = subprocess.run([make, "-n", "payload"], cwd=tmp_path, capture_output=True, text=True, check=True)
    for recipe in expected:
        assert recipe in result.stdout
