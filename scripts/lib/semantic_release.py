"""Restore a pinned semantic artifact without rerunning GPU inference.

Also the export's rules for that artifact: which corpus fingerprints a pin may
vouch for (:func:`check_against_pin`), the waiting state published when no map
exists (:func:`write_pending`), and re-deriving its display attributes from the
current corpus (:func:`rebind`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import yaml

from . import artifacts
from .paths import SEMANTIC_PIN, SOURCE_REPAIRS

FILES = {"map.json", *[f"neighbours/{i}.json" for i in range(256)]}
MAX_BYTES = 512 * 1024 * 1024

#: Where a pin may send a download: this repository's own release assets.
RELEASES = "https://github.com/fmadore/genocide-at-the-security-council/releases/download/"


def load_pin(path: Path = SEMANTIC_PIN) -> dict:
    """The committed release pin, refused unless it is one this code reads."""
    pin = json.loads(path.read_text(encoding="utf-8"))
    if pin.get("schema") != 1 or not str(pin.get("url", "")).startswith(RELEASES):
        raise ValueError("unsupported semantic release pin")
    return pin


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


def repair_exclusions(path: Path = SOURCE_REPAIRS) -> frozenset[str]:
    """Speech ids and record ids the source repairs took off the map.

    Dropped records and speeches have no row in the corpus, and a trimmed
    speech and both halves of a split one have bodies no vector was computed
    for. Until the next
    embedding run they are kept out of the map and the neighbour index rather
    than shown with a vector of some other text. A speech is excluded when its
    id, or its record's id, is in the set.
    """
    if not path.is_file():
        return frozenset()
    repairs = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    excluded = {str(item["record_id"]) for item in repairs.get("drop_records") or []}
    for item in repairs.get("drop_speeches") or []:
        excluded |= {str(speech) for speech in item["pairs"]}
    excluded |= {str(item["speech_id"]) for item in repairs.get("trim_speeches") or []}
    for item in repairs.get("split_speeches") or []:
        excluded |= {str(item["speech_id"]), str(item["new"]["speech_id"])}
    return frozenset(excluded)


def is_excluded(row_id: str, excluded: frozenset[str]) -> bool:
    return row_id in excluded or row_id.rsplit("-", 1)[0] in excluded


def geometry_fingerprint(path: Path, excluded: frozenset[str] = frozenset()) -> str:
    """What the map's geometry depends on: which speeches, and their exact bodies.

    The projection and the neighbours are functions of the embedded texts and
    of nothing else. Years, affiliations, agendas and the lexical flag are
    display attributes the export re-derives from the current corpus, so a
    lexicon release or a relabelled affiliation no longer invalidates a map
    whose every vector is still the vector of the text it shows. Rows in
    `excluded` (:func:`repair_exclusions`) are left out of the digest.
    """
    import pandas as pd

    frame = pd.read_parquet(path, columns=["row_id", "text", "body_start"])
    if frame.row_id.isna().any() or frame.row_id.duplicated().any():
        raise ValueError("semantic corpus IDs must be unique and present")
    if excluded:
        frame = frame[[not is_excluded(str(row_id), excluded) for row_id in frame.row_id]]
    digest = hashlib.sha256(b"semantic-geometry-v1\n")
    for row_id, text, start in frame.sort_values("row_id").itertuples(index=False, name=None):
        body = hashlib.sha256(text[int(start):].encode("utf-8")).hexdigest()
        digest.update(f"{row_id}\t{body}\n".encode())
    return digest.hexdigest()


def validate(
    directory: Path,
    corpus_sha256: str | Path,
    *,
    content_sha256: str | None = None,
    geometry_sha256: str | None = None,
    excluded: frozenset[str] = frozenset(),
) -> dict:
    """Check a semantic artifact's files, then that it describes this corpus.

    Three ways to agree with the corpus, strictest first: the exact Parquet
    bytes the map was built from; a pinned fingerprint of the same content,
    which survives Arrow re-serialisation; or a pinned fingerprint of the
    geometry's inputs alone, which survives any change to the display
    attributes the export re-derives anyway. The two fingerprints are only
    accepted from a pin bound to this exact manifest. The geometry is compared
    without the `excluded` rows, which the export then takes off the map.
    """
    meta = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = meta.get("files", {})
    if set(files) != FILES or any(artifacts.sha256(directory / p) != h for p, h in files.items()):
        raise ValueError("semantic payload is incomplete or has failed checksum validation")
    corpus_path = corpus_sha256 if isinstance(corpus_sha256, Path) else None
    if corpus_path:
        corpus_sha256 = artifacts.sha256(corpus_path)
    if any(item.get("sha256") == corpus_sha256 for item in meta.get("inputs", [])):
        return meta
    if corpus_path and content_sha256 and corpus_fingerprint(corpus_path) == content_sha256:
        return meta
    if (corpus_path and geometry_sha256
            and geometry_fingerprint(corpus_path, excluded) == geometry_sha256):
        return meta
    raise ValueError("semantic map was built from a different corpus")


def pinned_exclusions(pin_path: Path = SEMANTIC_PIN, repairs: Path = SOURCE_REPAIRS) -> frozenset[str]:
    """The rows the pin's geometry digest leaves out, or none.

    The pin records the checksum of the source repairs its digest was computed
    without. A repair added or changed since then voids the exclusions, and the
    geometry check fails until the digest is recomputed and reviewed: the map is
    never quietly trimmed by a repair nobody measured it against.
    """
    if not pin_path.is_file():
        return frozenset()
    recorded = load_pin(pin_path).get("source_repairs_sha256")
    if not recorded or not repairs.is_file() or artifacts.sha256(repairs) != recorded:
        return frozenset()
    return repair_exclusions(repairs)


def check_against_pin(directory: Path, corpus: Path, pin_path: Path = SEMANTIC_PIN) -> dict:
    """:func:`validate`, with the fingerprints the pin vouches for if it may.

    The artifact records the Parquet bytes it was built from, and Arrow
    versions can serialise identical content differently. Only a pin bound to
    this exact manifest may authorise comparison by canonical content or by
    geometry; any other artifact must match the corpus byte for byte.
    """
    content_sha256 = geometry_sha256 = None
    excluded: frozenset[str] = frozenset()
    if pin_path.is_file():
        pin = load_pin(pin_path)
        if artifacts.sha256(directory / "manifest.json") == pin.get("manifest_sha256"):
            content_sha256 = pin.get("corpus_content_sha256")
            geometry_sha256 = pin.get("corpus_geometry_sha256")
            excluded = pinned_exclusions(pin_path)
    return validate(
        directory,
        corpus,
        content_sha256=content_sha256,
        geometry_sha256=geometry_sha256,
        excluded=excluded,
    )


def write_pending(directory: Path) -> None:
    """The explicit waiting state the export publishes when no map exists yet."""
    artifacts.atomic_write_json(directory / "map.json", {"status": "pending", "schema": 1})


def reshard(staged: Path, order: list[str], excluded: frozenset[str]) -> int:
    """Rewrite the neighbour shards for a map whose points are now `order`.

    The dashboard finds a speech's neighbours in shard `position % 256`, by its
    position in `map.json`, so taking points off the map moves every later
    speech to another shard. Excluded speeches lose their entry, and every other
    speech loses the links that pointed to one; the rest keep their ranks.
    Returns how many links were removed.
    """
    records: dict[str, list] = {}
    for number in range(256):
        records.update(json.loads((staged / "neighbours" / f"{number}.json").read_text(encoding="utf-8")))
    removed = 0
    shards: list[dict[str, list]] = [{} for _ in range(256)]
    for position, row_id in enumerate(order):
        links = records[row_id]
        kept = [link for link in links if not is_excluded(str(link[0]), excluded)]
        removed += len(links) - len(kept)
        shards[position % 256][row_id] = kept
    for number, shard in enumerate(shards):
        artifacts.atomic_write_json(staged / "neighbours" / f"{number}.json", shard)
    return removed


def rebind(staged: Path, corpus: Path, excluded: frozenset[str] = frozenset()) -> dict[str, object]:
    """Re-derive the display attributes of a copied map from `corpus`.

    Keeps every point's projected coordinates and replaces its year,
    affiliation, agenda and lexical flag with what the corpus now says, then
    rewrites the copied manifest's checksum for `map.json` and records what was
    done, so the payload never carries a manifest its own files contradict.
    Speeches in `excluded` (:func:`pinned_exclusions`) are taken off the map and
    out of the neighbour index. Returns what changed, for the export's log.
    """
    import pandas as pd

    from . import semantic

    path = staged / "map.json"
    published = json.loads(path.read_text(encoding="utf-8"))
    released_sha256 = artifacts.sha256(path)
    coordinates = {
        str(point[0]): (point[1], point[2])
        for point in published["points"]
        if not is_excluded(str(point[0]), excluded)
    }
    speeches = pd.read_parquet(
        corpus, columns=["row_id", "year", "country_org", "agenda_item_manual", "has_genocide"]
    )
    if excluded:
        speeches = speeches[[not is_excluded(str(row_id), excluded) for row_id in speeches.row_id]]
    countries, agendas, points = semantic.display_points(speeches, coordinates)
    before = {str(point[0]): point for point in published["points"]}
    changed = sum(
        1
        for point in points
        if (
            point[3] != before[point[0]][3]
            or countries[point[4]] != published["countries"][before[point[0]][4]]
            or agendas[point[5]] != published["agendas"][before[point[0]][5]]
            or point[6] != before[point[0]][6]
        )
    )
    display = {
        "rebound_at_export": True,
        "corpus_sha256": artifacts.sha256(corpus),
        "release_map_sha256": released_sha256,
        "points_changed": changed,
        "columns": semantic.POINT_COLUMNS[3:],
    }
    meta = {**published["meta"], "display": display}
    manifest_path = staged / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if excluded:
        dropped = sorted(row for row in before if row not in coordinates)
        links = reshard(staged, [str(point[0]) for point in points], excluded)
        display["excluded"] = {
            "why": "changed by config/source_repairs.yml; no vector until the next embedding run",
            "speeches": dropped,
            "links_removed": links,
        }
        meta["speeches"] = len(points)
        for number in range(256):
            name = f"neighbours/{number}.json"
            manifest["files"][name] = artifacts.sha256(staged / name)
    artifacts.atomic_write_json(
        path, {"meta": meta, "countries": countries, "agendas": agendas, "points": points}
    )
    manifest["files"]["map.json"] = artifacts.sha256(path)
    manifest["display"] = display
    artifacts.atomic_write_json(manifest_path, manifest, indent=2)
    return display


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
    pin = load_pin(pin_path)
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
