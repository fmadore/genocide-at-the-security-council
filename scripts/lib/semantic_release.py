"""Restore a pinned semantic artifact without rerunning GPU inference."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from . import artifacts

FILES = {"map.json", *[f"neighbours/{i}.json" for i in range(256)]}
MAX_BYTES = 512 * 1024 * 1024


def corpus_fingerprint(path: Path) -> str:
    """Semantic inputs, independent of Parquet writer version and row order.

    Bind exact embedded bodies and every displayed/filterable attribute. The
    release pin binds this digest to the original artifact's manifest checksum.
    """
    import pandas as pd

    columns = ["row_id", "text", "body_start", "year", "country_org", "agenda_item_manual", "has_genocide"]
    frame = pd.read_parquet(path, columns=columns)
    if frame.row_id.isna().any() or frame.row_id.duplicated().any():
        raise ValueError("semantic corpus IDs must be unique and present")
    digest = hashlib.sha256(b"semantic-speeches-v1\n")
    for row_id, text, start, year, country, agenda, flag in frame.sort_values("row_id").itertuples(index=False, name=None):
        record = [str(row_id), hashlib.sha256(text[int(start):].encode("utf-8")).hexdigest(),
                  int(year), str(country) if pd.notna(country) else "Unknown affiliation",
                  str(agenda) if pd.notna(agenda) else "Unknown agenda", bool(flag)]
        digest.update((json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    return digest.hexdigest()


def validate(directory: Path, corpus_sha256: str | Path, *, content_sha256: str | None = None) -> dict:
    meta = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = meta.get("files", {})
    if set(files) != FILES or any(artifacts.sha256(directory / p) != h for p, h in files.items()):
        raise ValueError("semantic payload is incomplete or has failed checksum validation")
    corpus_path = corpus_sha256 if isinstance(corpus_sha256, Path) else None
    if corpus_path:
        corpus_sha256 = artifacts.sha256(corpus_sha256)
    if (not any(item.get("sha256") == corpus_sha256 for item in meta.get("inputs", []))
            and not (corpus_path and content_sha256 and corpus_fingerprint(corpus_path) == content_sha256)):
        raise ValueError("semantic map was built from a different corpus")
    return meta


def install(archive: Path, target: Path, pin: dict) -> None:
    if artifacts.sha256(archive) != pin["sha256"]:
        raise ValueError("semantic archive checksum mismatch")
    with zipfile.ZipFile(archive) as source, artifacts.atomic_directory(target) as staged:
        members = source.infolist()
        names = [entry.filename for entry in members]
        if (set(names) != FILES | {"manifest.json"} or len(names) != len(set(names))
                or sum(entry.file_size for entry in members) > MAX_BYTES
                or any(stat.S_ISLNK(entry.external_attr >> 16) for entry in members)):
            raise ValueError("semantic archive has an invalid file inventory")
        # Exact allowlist above rejects traversal, absolute paths and extra files.
        for entry in members:
            path = staged / entry.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as incoming, path.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
        if artifacts.sha256(staged / "manifest.json") != pin["manifest_sha256"]:
            raise ValueError("semantic manifest checksum mismatch")
        validate(staged, pin["corpus_sha256"])


def restore(pin_path: Path, target: Path) -> None:
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    if pin.get("schema") != 1 or not pin["url"].startswith(
        "https://github.com/fmadore/genocide-at-the-security-council/releases/download/"
    ):
        raise ValueError("unsupported semantic release pin")
    if (target / "manifest.json").is_file():
        try:
            if artifacts.sha256(target / "manifest.json") == pin["manifest_sha256"]:
                validate(target, pin["corpus_sha256"])
                print("Semantic release verified locally")
                return
        except (OSError, ValueError):
            pass
    with tempfile.TemporaryDirectory(prefix="unsc-semantic-") as temporary:
        archive = Path(temporary) / "semantic.zip"
        with urllib.request.urlopen(pin["url"], timeout=120) as response, archive.open("wb") as output:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > MAX_BYTES:
                    raise ValueError("semantic archive exceeds download limit")
                output.write(block)
        install(archive, target, pin)
    print("Semantic release restored and verified")
