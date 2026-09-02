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


@contextmanager
def atomic_path(path: Path) -> Iterator[Path]:
    """Yield a temporary name beside `path`, then move it into place.

    A half-written artefact that carries the name of a finished one is the
    failure this whole module exists to prevent: the next stage reads it, the
    pipeline completes, and nothing anywhere says which number came from a
    truncated file. Writing beside the target and renaming makes the swap
    atomic, and the rename is on the same volume so it cannot fall back to a
    copy.

    This is the form for writers that insist on a filename — ``to_parquet``
    takes a path, not bytes — and it is what :func:`atomic_write_bytes` is built
    on, so the argument above is made once rather than in every caller that
    needs a scratch name.

    The name is reserved with an exclusive ``mkstemp`` and then unlinked,
    because a writer handed an existing empty file may refuse it or append to
    it. What re-creates it is the caller, and the callers here open with ``x``
    or hand the name to a library that creates it itself.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temp = Path(name)
    temp.unlink()
    try:
        yield temp
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Replace one file only after its complete payload is on the same volume."""
    # `x`: the name was reserved a moment ago, and an exclusive create is what
    # makes that reservation mean something rather than assuming it. The stream
    # closes before `atomic_path` renames — Windows refuses to replace a file
    # that is still open — and `fsync` runs first, so a machine that loses power
    # between the two does not leave the entry pointing at unwritten blocks.
    with atomic_path(path) as temp, temp.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_write_text(path: Path, payload: str) -> None:
    atomic_write_bytes(path, payload.encode("utf-8"))


_VOLATILE_META = frozenset({"generated", "git_commit", "analysis_hash"})


def analysis_hash(payload: dict[str, object]) -> str:
    """Hash analytical content and declared provenance, not run-local identity.

    The payload itself and the non-volatile metadata are canonical JSON. Config
    and input digests therefore remain part of the identity, while regenerating
    the same result later or from a dirty checkout does not mint a new analysis.
    """
    canonical = dict(payload)
    meta = canonical.get("meta")
    if isinstance(meta, dict):
        canonical["meta"] = {key: value for key, value in meta.items() if key not in _VOLATILE_META}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def with_analysis_hash(payload: object) -> object:
    """Return a JSON payload with a stable hash when it has nested metadata."""
    if not isinstance(payload, dict) or not isinstance(payload.get("meta"), dict):
        return payload
    prepared = dict(payload)
    prepared["meta"] = {**payload["meta"], "analysis_hash": analysis_hash(payload)}
    return prepared


def atomic_write_json(path: Path, payload: object, *, indent: int | None = None) -> None:
    separators = None if indent is not None else (",", ":")
    atomic_write_text(
        path,
        json.dumps(
            with_analysis_hash(payload),
            ensure_ascii=False,
            indent=indent,
            separators=separators,
        ),
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
        # Relative to the repository where it can be; an input outside it — the
        # end-to-end test's temporary tree — is named absolutely rather than
        # refused, because the hash beside it is what the manifest is for.
        "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix(),
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
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        tracked = subprocess.run(
            ["git", "diff-index", "--quiet", "HEAD", "--"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return f"{commit}-dirty" if tracked.returncode != 0 or untracked else commit
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
