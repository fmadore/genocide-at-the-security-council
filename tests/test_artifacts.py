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


def test_atomic_path_leaves_the_previous_file_and_no_debris_on_failure(tmp_path):
    # The property `frames.write` now borrows rather than re-implementing: a
    # writer that dies part-way must leave the last complete artefact in place,
    # because the next stage cannot tell a truncated parquet from a short one.
    target = tmp_path / "speeches.parquet"
    target.write_bytes(b"complete")

    with pytest.raises(RuntimeError, match="stop"), artifacts.atomic_path(target) as temp:
        temp.write_bytes(b"half a file")
        raise RuntimeError("stop")

    assert target.read_bytes() == b"complete"
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


# --- Recording the commit outside a repository -----------------------------
#
# The cluster receives the working tree without `.git`, so `git rev-parse` there
# answers nothing and every manifest a GPU step wrote said "unknown".


SHA = "0123456789abcdef0123456789abcdef01234567"


def test_the_stamp_names_the_commit_when_there_is_no_repository(tmp_path):
    (tmp_path / artifacts.COMMIT_STAMP).write_text(f"{SHA}\n", encoding="utf-8")
    assert artifacts.git_commit(tmp_path) == SHA


def test_an_uncommitted_tree_is_recorded_as_dirty(tmp_path):
    """The sha then locates the neighbourhood of the code, not the code."""
    (tmp_path / artifacts.COMMIT_STAMP).write_text(f"{SHA}-dirty\n", encoding="utf-8")
    assert artifacts.git_commit(tmp_path) == f"{SHA}-dirty"


@pytest.mark.parametrize(
    "content", ["", "unknown", "not-a-sha", "0123abc", f"{SHA} extra", f"{SHA}-DIRTY"]
)
def test_a_stamp_that_is_not_a_commit_is_refused(tmp_path, content):
    """A manifest naming a wrong commit is worse than one naming none."""
    (tmp_path / artifacts.COMMIT_STAMP).write_text(content, encoding="utf-8")
    assert artifacts.git_commit(tmp_path) == "unknown"


def test_no_repository_and_no_stamp_is_unknown(tmp_path):
    assert artifacts.git_commit(tmp_path) == "unknown"


def test_provenance_carries_the_stamped_commit(tmp_path):
    (tmp_path / artifacts.COMMIT_STAMP).write_text(SHA, encoding="utf-8")
    assert artifacts.provenance(tmp_path, "07_topics.py")["git_commit"] == SHA


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
