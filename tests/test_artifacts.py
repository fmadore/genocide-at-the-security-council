"""Atomic artefact writes and machine-readable provenance."""

from __future__ import annotations

import pytest
from lib import artifacts


def test_atomic_text_replaces_the_complete_file(tmp_path):
    target = tmp_path / "result.json"
    target.write_text("old", encoding="utf-8")
    artifacts.atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_directory_keeps_the_previous_version_on_failure(tmp_path):
    target = tmp_path / "payload"
    target.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")

    with (
        pytest.raises(RuntimeError, match="stop"),
        artifacts.atomic_directory(target) as staged,
    ):
        (staged / "new.txt").write_text("new", encoding="utf-8")
        raise RuntimeError("stop")

    assert (target / "old.txt").read_text(encoding="utf-8") == "old"
    assert not (target / "new.txt").exists()


def test_tree_digest_changes_with_content(tmp_path):
    target = tmp_path / "payload"
    target.mkdir()
    item = target / "one.txt"
    item.write_text("one", encoding="utf-8")
    first = artifacts.describe_tree(target)
    item.write_text("two", encoding="utf-8")
    second = artifacts.describe_tree(target)
    assert first["sha256"] != second["sha256"]
    assert second["files"] == 1
