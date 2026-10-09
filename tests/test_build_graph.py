"""Incremental recipe selection over a synthetic tree, using GNU make when available."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
KEY_ACTION = ROOT / ".github/actions/payload-cache-keys/action.yml"


def _deploy() -> tuple[dict, list[str]]:
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))
    return workflow, trigger["push"]["paths"]


def _keyed_paths() -> list[str]:
    """The tracked paths the derived key hashes beside `make payload-code`."""
    action = yaml.safe_load(KEY_ACTION.read_text(encoding="utf-8"))
    compose = next(step for step in action["runs"]["steps"] if step.get("id") == "keys")["run"]
    assert "make --no-print-directory -s payload-code" in compose
    listing = compose.split("git ls-files --", 1)[1].split("printf", 1)[0]
    return listing.replace("\\", " ").split()


def test_deploy_tracks_graph_and_contract():
    workflow, paths = _deploy()
    cache = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("id") == "keys")
    assert cache["uses"] == "./.github/actions/payload-cache-keys"
    keyed = _keyed_paths()
    for path in ["Makefile", "scripts/deps.mk", "tests/contract/payload.json"]:
        assert path in keyed
    for path in ["Makefile", "tests/contract/payload.json"]:
        assert path in paths
    assert any(step.get("run") == "python scripts/export_web.py --check"
               for step in workflow["jobs"]["build"]["steps"])


def test_the_deploy_publishes_only_after_the_checks_pass():
    workflow, _ = _deploy()
    checks = yaml.safe_load((ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8"))
    assert "workflow_call" in checks.get("on", checks.get(True))
    assert workflow["jobs"]["checks"]["uses"] == "./.github/workflows/checks.yml"
    assert "checks" in workflow["jobs"]["deploy"]["needs"]


def test_the_checks_prerender_over_exactly_what_the_deploy_saved():
    """A cache entry is found only under the key and the path list it was
    saved with, so a drift in either would quietly skip the production build."""
    workflow, _ = _deploy()
    checks = yaml.safe_load((ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8"))
    web = checks["jobs"]["web"]["steps"]
    saved = next(step for step in workflow["jobs"]["build"]["steps"] if step.get("name") == "Save the derived payload")
    restored = next(step for step in web if step.get("id") == "payload")
    assert next(step for step in web if step.get("id") == "keys")["uses"] == "./.github/actions/payload-cache-keys"
    assert restored["with"]["path"] == saved["with"]["path"]
    assert restored["with"]["key"] == saved["with"]["key"] == "${{ steps.keys.outputs.derived }}"
    assert any(step.get("run") == "npm run build" for step in web)


def _github_glob(pattern: str) -> re.Pattern[str]:
    """GitHub's path-filter globs: `**` crosses directories, `*` does not."""
    regex, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex, i = regex + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            regex, i = regex + ".*", i + 2
        elif pattern[i] == "*":
            regex, i = regex + "[^/]*", i + 1
        else:
            regex, i = regex + re.escape(pattern[i]), i + 1
    return re.compile(regex + r"\Z")


def _triggers(path: str, patterns: list[str]) -> bool:
    """Whether a push touching `path` starts the deploy; later patterns win."""
    hit = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if _github_glob(pattern.lstrip("!")).match(path):
            hit = not negated
    return hit


def _make() -> str:
    make = shutil.which("make")
    if not make:
        pytest.skip("GNU make is required; this regression runs on the Linux CI runner")
    return make


def _payload_code(make: str) -> list[str]:
    result = subprocess.run([make, "--no-print-directory", "-s", "payload-code"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.split()


def test_the_payload_code_is_each_step_with_its_generated_modules():
    """The key's Python list, checked against the graph by another route: the
    steps `make -nB payload` would run, each with its deps.mk variable."""
    make = _make()
    code = _payload_code(make)
    recipes = subprocess.run([make, "-nB", "payload"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    generated = dict(re.findall(r"^(LIB_[A-Z0-9_]+) := (.*)$",
                                (ROOT / "scripts" / "deps.mk").read_text(encoding="utf-8"), re.M))
    expected = set()
    for stem in [*re.findall(r"scripts/(\w+)\.py", recipes), "fetch_semantic"]:
        expected.add(f"scripts/{stem}.py")
        expected.update(generated["LIB_" + stem.upper()].split())
    assert set(code) == expected
    for path in ["scripts/00_fetch_data.py", "scripts/15_usage.py", "scripts/lib/usage.py"]:
        assert path in code
    for path in ["scripts/14_llm_annotate.py", "scripts/lib/annotate.py", "scripts/lib/run_store.py"]:
        assert path not in code


def test_the_deploy_trigger_covers_everything_the_key_hashes():
    """The trigger has to be a static list, so it excludes by hand what the key
    leaves out by reading the graph. A payload input it excluded would leave
    the published site stale with nothing to say so."""
    make = _make()
    _, paths = _deploy()
    keyed = [*_payload_code(make), *subprocess.run(
        ["git", "ls-files", "--", *_keyed_paths()], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()]
    assert not [path for path in keyed if not _triggers(path, paths)]
    for path in ["scripts/cluster/push_code.sh", "scripts/14_llm_annotate.py", "scripts/README.md",
                 "scripts/probe_reasoning.py", "scripts/21_semantic_map.py"]:
        assert not _triggers(path, paths), path


@pytest.mark.parametrize("changed,expected", [
    ("annotations/lexicon/referents.csv", ["03_lexicon.py", "13_gold_sample.py", "15_usage.py"]),
    ("model_annotations/genocide/current_run.txt", ["13_gold_sample.py", "15_usage.py", "17_frames.py"]),
    ("model_annotations/genocide/prompts/v2.md", ["13_gold_sample.py", "15_usage.py"]),
    ("data/derived/series/quarterly.json", ["04_series.py"]),
    ("scripts/lib/usage.py", ["15_usage.py"]),
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
            # The generated include is part of the graph, not an input to it.
            if name == "scripts/deps.mk":
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
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


def test_a_module_edit_does_not_rebuild_steps_that_cannot_run_it(tmp_path):
    """`lib/usage.py` is imported by 15 alone among the release steps; editing
    it must not re-run the corpus build that everything else waits on."""
    test_incremental_inputs_and_missing_secondary_output(tmp_path, "scripts/lib/usage.py", ["15_usage.py"])
    make = shutil.which("make")
    result = subprocess.run([make, "-n", "payload"], cwd=tmp_path, capture_output=True, text=True, check=True)
    for recipe in ["01_build_parquet.py", "02_normalise.py", "03_lexicon.py", "04_series.py"]:
        assert recipe not in result.stdout


def test_the_committed_step_dependencies_match_the_imports():
    """Pure Python, so it runs everywhere: the include cannot drift from the code."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "lib_deps.py"), "--check"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout


def test_every_step_variable_the_makefile_names_is_generated():
    """A misspelt `$(LIB_...)` expands to nothing in make, silently dropping a
    step's module prerequisites; this is the check make itself will not do."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    generated = (ROOT / "scripts" / "deps.mk").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\((LIB_[A-Z0-9_]+)\)", makefile))
    defined = set(re.findall(r"^(LIB_[A-Z0-9_]+) :=", generated, re.M))
    assert used, "the Makefile names no step variable"
    assert used <= defined, sorted(used - defined)
    assert "include scripts/deps.mk" in makefile
