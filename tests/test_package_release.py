"""`tools/package_release.py`: the archives, the checksums, the refusals."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest
from lib import console

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("package_release", ROOT / "tools" / "package_release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _tool()


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    derived = tmp_path / "data" / "derived"
    (derived / "series").mkdir(parents=True)
    (derived / "series" / "annual.json").write_text("{}", encoding="utf-8")
    (derived / "speeches_norm.parquet").write_bytes(b"corpus")
    site = tmp_path / "web" / "build"
    site.mkdir(parents=True)
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(tool, "DERIVED", derived)
    monkeypatch.setattr(tool, "SITE", site)
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    return tmp_path


def test_the_derived_tables_leave_the_corpus_out_unless_asked(tree: Path) -> None:
    made = tool.package("v0.1.0", with_speeches=False, gold=False, dist=tree / "dist")
    names = {path.name for path in made}
    assert names == {"derived-tables-v0.1.0.zip", "site-v0.1.0.zip"}
    with zipfile.ZipFile(tree / "dist" / "derived-tables-v0.1.0.zip") as zipped:
        assert zipped.namelist() == ["derived/series/annual.json"]


def test_the_checksums_are_what_sha256sum_reads(tree: Path) -> None:
    made = tool.package("v0.1.0", with_speeches=True, gold=False, dist=tree / "dist")
    lines = (tree / "dist" / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    for path, line in zip(made, lines, strict=True):
        assert line == f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"


def test_a_release_is_packaged_once(tree: Path) -> None:
    tool.package("v0.1.0", with_speeches=False, gold=False, dist=tree / "dist")
    with pytest.raises(console.Refusal, match="exists"):
        tool.package("v0.1.0", with_speeches=False, gold=False, dist=tree / "dist")


def test_a_tag_that_is_not_a_version_is_refused(tree: Path) -> None:
    with pytest.raises(console.Refusal, match="release tag"):
        tool.package("latest", with_speeches=False, gold=False, dist=tree / "dist")


def test_the_cited_hashes_come_from_the_meta_blocks(tmp_path: Path) -> None:
    for relative in tool.CITED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"meta": {"analysis_hash": f"hash-{path.stem}"}}), encoding="utf-8")
    assert tool.cited_hashes(tmp_path) == {
        "series/annual.json": "hash-annual",
        "kwic/genocide.json": "hash-genocide",
        "usage/usage.json": "hash-usage",
    }
