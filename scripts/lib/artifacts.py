"""Atomic output and provenance helpers shared by every pipeline stage."""

from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

#: Where the pipeline's own code lives. Not `provenance`'s `root`, which names
#: the tree the inputs are described against and which a test may point at a
#: temporary directory: the code that ran is always this checkout's.
LIB = Path(__file__).resolve().parent
SCRIPTS = LIB.parent
CODE_ROOT = SCRIPTS.parent


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


#: Metadata that says how an artefact came to be written rather than what it
#: holds. `code` is here with the time and the commit: a refactor that moves no
#: number must not mint a new analysis, and one that does move a number changes
#: the payload, and so the hash, by itself.
_VOLATILE_META = frozenset({"generated", "git_commit", "analysis_hash", "code"})


def analysis_hash(payload: dict[str, object]) -> str:
    """Hash analytical content and declared provenance, not run-local identity.

    The payload itself and the non-volatile metadata are canonical JSON. Config
    and input digests therefore remain part of the identity, while regenerating
    the same result later, from a dirty checkout or from edited code that
    computes the same thing does not mint a new analysis.
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


def shared_provenance(
    payload: dict[str, object], keep: Sequence[str], held_in: str
) -> dict[str, object]:
    """One of many files that share a provenance block, cut to what cites it.

    The block of inputs, configurations, packages and code is identical across
    every file one loop writes; repeated in each of 09's 9,464 meeting files it
    adds about a kilobyte of compressed payload apiece. The cut file keeps
    the `keep` keys, names the file that holds the whole block as `provenance`,
    and carries the `analysis_hash` of the uncut payload: the hash it would have
    if it held the block itself. It is checked the same way, by putting the
    block from `held_in` back as `meta` and hashing. Write the result with
    `hashed=True`, or the writer would hash the cut block instead.
    """
    meta = payload["meta"]
    if not isinstance(meta, dict):
        raise TypeError("shared_provenance needs a payload with a meta block")
    return {
        **payload,
        "meta": {
            **{key: meta[key] for key in keep if key in meta},
            "provenance": held_in,
            "analysis_hash": analysis_hash(payload),
        },
    }


def json_text(payload: object, *, indent: int | None = None, hashed: bool = False) -> str:
    """The canonical serialisation every JSON artefact is written with.

    `hashed` says the payload already carries its `analysis_hash` and must be
    written as it is: see `shared_provenance`.
    """
    separators = None if indent is not None else (",", ":")
    return json.dumps(
        payload if hashed else with_analysis_hash(payload),
        ensure_ascii=False,
        indent=indent,
        separators=separators,
    )


def atomic_write_json(path: Path, payload: object, *, indent: int | None = None) -> None:
    atomic_write_text(path, json_text(payload, indent=indent))


def atomic_write_json_gzip(
    path: Path, payload: object, *, indent: int | None = None, hashed: bool = False
) -> None:
    """Write JSON as a gzip member, byte-identical for identical content.

    `mtime=0` and a fixed level keep the bytes a function of the payload alone,
    so the export's checksums do not change on a rebuild that changed nothing.
    """
    atomic_write_bytes(
        path,
        gzip.compress(
            json_text(payload, indent=indent, hashed=hashed).encode("utf-8"),
            compresslevel=9,
            mtime=0,
        ),
    )


def csv_text(table: Any, *, fieldnames: Sequence[str] | None = None) -> str:
    """The serialisation every CSV artefact is written with: `\\n`, never `\\r\\n`.

    A data frame is written by pandas without its index; anything else is read
    as rows of mappings and written by `csv.DictWriter`, with the columns taken
    from `fieldnames` or else from the first row. Each keeps its own formatting
    of values, so a caller moved onto this writer changes no cell.

    The line ending is fixed because both writers otherwise use the platform's:
    the same table came out as different bytes on Windows and on the Linux
    deploy, and a checksum that differs across machines for identical data
    cannot say whether anything changed.
    """
    if hasattr(table, "to_csv"):
        return str(table.to_csv(index=False, lineterminator="\n"))
    rows: list[Mapping[str, object]] = list(table)
    columns = list(fieldnames) if fieldnames is not None else list(rows[0]) if rows else []
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def atomic_write_csv(
    path: Path, table: Any, *, fieldnames: Sequence[str] | None = None
) -> None:
    atomic_write_text(path, csv_text(table, fieldnames=fieldnames))


def read_json(path: Path) -> object:
    """A JSON artefact, whether it was written plain or gzipped."""
    raw = path.read_bytes()
    if path.suffix == ".gz" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


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


#: Digests already computed in this process, keyed on what would change them.
#: A step describes the 180 MB corpus in its payload's metadata and again in its
#: stage manifest; the second description should not read it a second time.
_DIGESTS: dict[tuple[str, int, int], str] = {}


def _cached_sha256(path: Path) -> str:
    status = path.stat()
    key = (str(path.resolve()), status.st_size, status.st_mtime_ns)
    if key not in _DIGESTS:
        _DIGESTS[key] = sha256(path)
    return _DIGESTS[key]


def describe_file(path: Path, root: Path) -> dict[str, object]:
    return {
        # Relative to the repository where it can be; an input outside it — the
        # end-to-end test's temporary tree — is named absolutely rather than
        # refused, because the hash beside it is what the manifest is for.
        "path": path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _cached_sha256(path),
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


def _lib_imports(path: Path, *, inside_lib: bool) -> set[str]:
    """Module names under `lib` that one file imports, wherever in it they are."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if inside_lib and node.level == 1:
                if node.module:
                    found.add(node.module.split(".")[0])
                else:
                    found.update(alias.name for alias in node.names)
            elif node.level == 0 and node.module == "lib":
                found.update(alias.name for alias in node.names)
            elif node.level == 0 and node.module and node.module.startswith("lib."):
                found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("lib."):
                    found.add(alias.name.split(".")[1])
    return {name for name in found if (LIB / f"{name}.py").is_file()}


def lib_closure(script: Path) -> list[Path]:
    """Every `lib` module a script can execute, in name order.

    The script's own imports — `from lib import x`, `from lib.x import y` —
    followed through `lib`'s relative imports to a fixed point. Read from the
    source rather than from `sys.modules`, so the answer is the same whichever
    branch of the script ran and whether or not it has run at all.
    """
    pending = list(_lib_imports(script, inside_lib=False))
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(_lib_imports(LIB / f"{name}.py", inside_lib=True) - seen)
    return sorted(LIB / f"{name}.py" for name in seen)


def code_files(script: str) -> list[Path]:
    """The script a step runs from, `lib/__init__.py`, and its `lib` closure.

    A numbered step lives in `scripts/` and a maintenance helper in `tools/`. A
    name found in neither is refused rather than recorded as having no code: a
    manifest that names a script nobody can find describes nothing.
    """
    for directory in (SCRIPTS, CODE_ROOT / "tools"):
        path = directory / script
        if path.is_file():
            return [path, LIB / "__init__.py", *lib_closure(path)]
    raise FileNotFoundError(f"provenance names a script that does not exist: {script}")


def describe_code(script: str) -> list[dict[str, object]]:
    """Every file of code a script can execute, described as inputs are.

    A list rather than a mapping keyed by path, like `inputs` and `configs`:
    the payload contract records an object's keys, and a step that gained an
    import would otherwise read there as a changed shape.
    """
    return [describe_file(path, CODE_ROOT) for path in code_files(script)]


def provenance(
    root: Path,
    script: str,
    *,
    inputs: list[Path] | None = None,
    configs: list[Path] | None = None,
    optional: list[Path] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """What produced an artefact: script, time, commit, environment and inputs.

    Every path in `inputs` and `configs` must exist. A manifest that silently
    leaves out an input it was told about describes a run that did not happen,
    which is worse than no manifest; a caller with a genuinely optional input
    names it in `optional`, where its absence is recorded rather than hidden.

    `code` holds the digest of the script and of every `lib` module it can
    execute, found from its imports rather than listed by its caller: the hand
    lists this replaced were each shorter than the real imports. The commit
    names the code only when the tree was clean, and a run from a dirty tree is
    exactly the one whose code needs naming. It stays out of `analysis_hash`;
    see `_VOLATILE_META`.
    """
    declared = [*(inputs or []), *(configs or [])]
    if missing := [path for path in declared if not path.exists()]:
        raise FileNotFoundError(
            "provenance names inputs that do not exist: "
            + ", ".join(path.as_posix() for path in missing)
        )
    present = [path for path in optional or [] if path.exists()]
    absent = [path for path in optional or [] if not path.exists()]
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
        "inputs": [describe_file(path, root) for path in [*(inputs or []), *present]],
        "configs": [describe_file(path, root) for path in configs or []],
        "code": describe_code(script),
    }
    if absent:
        payload["absent_optional"] = [
            path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
            for path in absent
        ]
    if extra:
        payload.update(extra)
    return payload
