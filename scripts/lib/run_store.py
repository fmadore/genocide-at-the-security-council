"""A fixed run identity and one recoverable speech transaction at a time.

The small pending file is a write-ahead record: rows and accounting either
arrive together or are replayed from the same record on the next invocation.
Historical annotation files remain read-only inputs, not migration targets.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

from . import artifacts


@contextmanager
def writer(directory: Path):
    """One local writer per run; the OS releases the lock even on process death."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".writer.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            def acquire():
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        try:
            acquire()
        except OSError as exc:
            raise ValueError("Another process is writing this run") from exc
        try:
            yield
        finally:
            release()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bind_identity(directory: Path, identity: dict) -> str:
    path = directory / "identity.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != identity:
            raise ValueError("Run identity changed; use a new run id, never append a different instrument")
    else:
        if any((directory / name).exists() for name in ("manifest.json", "annotations.jsonl", "failures.jsonl", "pending.json")):
            raise ValueError("Existing run has no complete identity; preserve it and use a new run id")
        artifacts.atomic_write_json(path, identity)
    return digest(identity)


def recover(directory: Path) -> None:
    pending = directory / "pending.json"
    if not pending.exists():
        return
    transaction = json.loads(pending.read_text(encoding="utf-8"))
    for name, append in transaction["appends"].items():
        if name not in {"annotations.jsonl", "failures.jsonl"}:
            raise ValueError("Unknown transaction output")
        path = directory / name
        offset = append["offset"]
        content = append["text"].encode("utf-8")
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("Invalid transaction offset")
        existing = path.stat().st_size if path.exists() else 0
        if existing < offset:
            raise ValueError("Transaction prefix is missing")
        with path.open("r+b" if path.exists() else "w+b") as stream:
            stream.seek(offset)
            tail = stream.read()
            if not content.startswith(tail):
                raise ValueError("Transaction tail conflicts with durable output")
            stream.seek(offset)
            stream.write(content)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
    artifacts.atomic_write_json(directory / "manifest.json", transaction["manifest"], indent=1)
    pending.unlink()


def commit(directory: Path, rows: dict[str, list[dict]], manifest: dict) -> None:
    recover(directory)
    appends = {}
    for name, records in rows.items():
        if not records:
            continue
        path = directory / name
        appends[name] = {
            "offset": path.stat().st_size if path.exists() else 0,
            "text": "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        }
    artifacts.atomic_write_json(directory / "pending.json", {"appends": appends, "manifest": manifest})
    recover(directory)
