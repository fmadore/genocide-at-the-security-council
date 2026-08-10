"""Atomic output and provenance helpers shared by every pipeline stage."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Replace one file only after its complete payload is on the same volume."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, payload: str) -> None:
    atomic_write_bytes(path, payload.encode("utf-8"))


def atomic_write_json(path: Path, payload: object, *, indent: int | None = None) -> None:
    separators = None if indent is not None else (",", ":")
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=indent, separators=separators),
    )


@contextmanager
def atomic_directory(target: Path) -> Iterator[Path]:
    """Build a directory beside its target, then swap it into place.

    The previous directory is restored if the final rename fails. Callers must
    complete every validation while inside the context.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    backup = target.with_name(f".{target.name}.previous")
    try:
        yield staged
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.replace(backup)
        try:
            staged.replace(target)
        except BaseException:
            if backup.exists() and not target.exists():
                backup.replace(target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if staged.exists():
            shutil.rmtree(staged)
        raise


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def describe_file(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def describe_tree(path: Path) -> dict[str, object]:
    """A stable digest over relative names and contents below a path."""
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    total = 0
    for item in files:
        relative = item.name if path.is_file() else item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        item_hash = sha256(item)
        digest.update(item_hash.encode("ascii"))
        total += item.stat().st_size
    return {"files": len(files), "bytes": total, "sha256": digest.hexdigest()}


#: Where the commit lives when `.git` does not. `scripts/cluster/push_code.sh`
#: copies the working tree without its history, so a job on the cluster has no
#: repository to ask — and every artefact it wrote recorded "unknown", against a
#: research contract that requires the generating commit. The stamp is written by
#: the push, and is git-ignored so a local copy can never be committed.
COMMIT_STAMP = ".git-commit"

#: A 40-character hex sha, optionally marked dirty. Anything else in the stamp
#: file is ignored: a manifest that names a commit must name a real one, and a
#: wrong provenance record is worse than an absent one.
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}(-dirty)?$")


def git_commit(root: Path) -> str:
    """The commit that produced an artefact, or `unknown` if it cannot be known.

    `-dirty` means the working tree carried uncommitted changes, so the sha
    locates the neighbourhood of the code that ran rather than the code itself.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    with suppress(OSError):
        stamped = (root / COMMIT_STAMP).read_text(encoding="utf-8").strip()
        if _COMMIT_RE.match(stamped):
            return stamped
    return "unknown"


def provenance(
    root: Path,
    script: str,
    *,
    inputs: list[Path] | None = None,
    configs: list[Path] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    packages = {}
    for package in ("numpy", "pandas", "pyarrow", "PyYAML"):
        with suppress(PackageNotFoundError):
            packages[package] = version(package)
    payload: dict[str, object] = {
        "script": script,
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git_commit(root),
        "python": platform.python_version(),
        "packages": packages,
        "inputs": [describe_file(path, root) for path in inputs or [] if path.exists()],
        "configs": [describe_file(path, root) for path in configs or [] if path.exists()],
    }
    if extra:
        payload.update(extra)
    return payload
