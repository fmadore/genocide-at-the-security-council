import hashlib
import json
import zipfile

import pandas as pd
import pytest
from lib import artifacts, semantic_release

#: A published map over the two speeches of `speeches()`, as step 21 writes one.
MAP = {
    "meta": {"script": "21_semantic_map.py"},
    "countries": ["A", "Unknown affiliation"],
    "agendas": ["B", "Unknown agenda"],
    "points": [["b", 0.5, -1.25, 2000, 0, 0, False], ["a", 2.0, 3.0, 2001, 1, 1, True]],
}


def release(tmp_path, *, extra=None, corpus="corpus", corrupt=False):
    files = dict.fromkeys(semantic_release.FILES, b"{}")
    files["map.json"] = json.dumps(MAP).encode()
    meta = {"inputs": [{"sha256": corpus}], "files": {
        name: hashlib.sha256(value).hexdigest() for name, value in files.items()
    }}
    files["manifest.json"] = json.dumps(meta).encode()
    pin = {"schema": 1, "url": semantic_release.RELEASES + "test/semantic.zip",
           "manifest_sha256": hashlib.sha256(files["manifest.json"]).hexdigest(),
           "corpus_sha256": "corpus"}
    if corrupt:
        files["map.json"] = b"corrupted"
    if extra:
        files[extra] = b"unexpected"
    archive = tmp_path / "semantic.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, content in files.items():
            output.writestr(name, content)
    pin["sha256"] = artifacts.sha256(archive)
    return archive, pin


def test_installs_complete_verified_release(tmp_path):
    archive, pin = release(tmp_path)
    target = tmp_path / "installed"
    semantic_release.install(archive, target, pin)
    assert len(list(target.rglob("*.json"))) == 258
    semantic_release.validate(target, "corpus")


@pytest.mark.parametrize("options,match", [
    ({"extra": "../escape.json"}, "inventory"),
    ({"extra": "neighbours/256.json"}, "inventory"),
    ({"corpus": "stale"}, "different corpus"),
    ({"corrupt": True}, "checksum"),
])
def test_failed_install_preserves_previous_release(tmp_path, options, match):
    archive, pin = release(tmp_path, **options)
    target = tmp_path / "installed"
    target.mkdir()
    (target / "previous").write_text("retain")
    with pytest.raises(ValueError, match=match):
        semantic_release.install(archive, target, pin)
    assert (target / "previous").read_text() == "retain"
    assert not (tmp_path / "escape.json").exists()


@pytest.mark.parametrize("field", ["sha256", "manifest_sha256"])
def test_rejects_changed_release_identity(tmp_path, field):
    archive, pin = release(tmp_path)
    pin[field] = "wrong"
    with pytest.raises(ValueError, match="checksum"):
        semantic_release.install(archive, tmp_path / "installed", pin)


def test_verified_local_release_needs_no_network(tmp_path, monkeypatch):
    archive, pin = release(tmp_path)
    target = tmp_path / "installed"
    semantic_release.install(archive, target, pin)
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(json.dumps(pin))
    monkeypatch.setattr(semantic_release.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used"))
    semantic_release.restore(pin_path, target)


def speeches():
    return pd.DataFrame({"row_id": ["b", "a"], "text": ["Hello. One", "Two"],
                         "body_start": [7, 0], "year": [2000, 2001],
                         "country_org": ["A", None], "agenda_item_manual": ["B", None],
                         "has_genocide": [False, True]})


def test_content_identity_ignores_serialization_and_row_order(tmp_path):
    first, second = tmp_path / "first.parquet", tmp_path / "second.parquet"
    speeches().to_parquet(first, compression="zstd", index=False)
    speeches().iloc[::-1].to_parquet(second, compression="snappy", index=False)
    assert artifacts.sha256(first) != artifacts.sha256(second)
    assert semantic_release.corpus_fingerprint(first) == semantic_release.corpus_fingerprint(second)
    archive, pin = release(tmp_path)
    target = tmp_path / "installed"
    semantic_release.install(archive, target, pin)
    with pytest.raises(ValueError, match="different corpus"):
        semantic_release.validate(target, second)
    semantic_release.validate(target, second, content_sha256=semantic_release.corpus_fingerprint(first))


@pytest.mark.parametrize("field,value", [("text", "changed"), ("body_start", 0),
    ("year", 1999), ("country_org", "changed"), ("agenda_item_manual", "changed"),
    ("has_genocide", True), ("row_id", "changed")])
def test_content_identity_rejects_changed_semantic_inputs(tmp_path, field, value):
    path = tmp_path / "corpus.parquet"
    frame = speeches()
    frame.to_parquet(path)
    before = semantic_release.corpus_fingerprint(path)
    frame.loc[0, field] = value
    frame.to_parquet(path)
    assert semantic_release.corpus_fingerprint(path) != before


def test_export_content_fallback_requires_the_pinned_manifest(tmp_path, monkeypatch):
    import export_web

    archive, pin = release(tmp_path)
    source = tmp_path / "source"
    semantic_release.install(archive, source, pin)
    corpus = tmp_path / "corpus.parquet"
    speeches().to_parquet(corpus)
    pin["corpus_content_sha256"] = semantic_release.corpus_fingerprint(corpus)
    config = tmp_path / "config"
    config.mkdir()
    (config / "semantic-release.json").write_text(json.dumps(pin))
    monkeypatch.setattr(export_web, "SEMANTIC_PIN", config / "semantic-release.json")
    monkeypatch.setattr(export_web, "SPEECHES_FLAGGED", corpus)
    export_web.copy_part([source], "semantic", root=tmp_path / "web")
    pin["manifest_sha256"] = "different artifact"
    (config / "semantic-release.json").write_text(json.dumps(pin))
    with pytest.raises(ValueError, match="different corpus"):
        export_web.copy_part([source], "semantic", root=tmp_path / "web")


@pytest.mark.parametrize("field,value,moves", [
    ("text", "changed", True), ("body_start", 0, True), ("row_id", "changed", True),
    ("year", 1999, False), ("country_org", "changed", False),
    ("agenda_item_manual", "changed", False), ("has_genocide", True, False)])
def test_the_geometry_fingerprint_binds_bodies_and_ids_only(tmp_path, field, value, moves):
    """What the projection depends on moves it; what the export re-derives does not."""
    path = tmp_path / "corpus.parquet"
    frame = speeches()
    frame.to_parquet(path)
    before = semantic_release.geometry_fingerprint(path)
    frame.loc[0, field] = value
    frame.to_parquet(path)
    assert (semantic_release.geometry_fingerprint(path) != before) is moves


def export_with_geometry_pin(tmp_path, monkeypatch, corpus_frame):
    import export_web

    archive, pin = release(tmp_path)
    source = tmp_path / "source"
    semantic_release.install(archive, source, pin)
    pinned = tmp_path / "pinned.parquet"
    speeches().to_parquet(pinned)
    pin["corpus_geometry_sha256"] = semantic_release.geometry_fingerprint(pinned)
    corpus = tmp_path / "corpus.parquet"
    corpus_frame.to_parquet(corpus)
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    (config / "semantic-release.json").write_text(json.dumps(pin))
    monkeypatch.setattr(export_web, "SEMANTIC_PIN", config / "semantic-release.json")
    monkeypatch.setattr(export_web, "SPEECHES_FLAGGED", corpus)
    export_web.copy_part([source], "semantic", root=tmp_path / "web")
    return tmp_path / "web" / "semantic"


def test_a_relabelled_corpus_keeps_the_geometry_and_takes_the_new_colours(tmp_path, monkeypatch):
    frame = speeches()
    frame.loc[frame.row_id == "b", "has_genocide"] = True
    frame.loc[frame.row_id == "b", "country_org"] = "Renamed"
    target = export_with_geometry_pin(tmp_path, monkeypatch, frame)
    published = json.loads((target / "map.json").read_text(encoding="utf-8"))
    points = {point[0]: point for point in published["points"]}
    assert points["b"][1:3] == [0.5, -1.25], "the coordinates are the release's"
    assert points["b"][6] is True
    assert published["countries"][points["b"][4]] == "Renamed"
    assert published["meta"]["display"]["points_changed"] == 1
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["map.json"] == artifacts.sha256(target / "map.json")


def test_a_changed_body_is_still_a_different_corpus(tmp_path, monkeypatch):
    frame = speeches()
    frame.loc[frame.row_id == "a", "text"] = "Rewritten"
    with pytest.raises(ValueError, match="different corpus"):
        export_with_geometry_pin(tmp_path, monkeypatch, frame)


def test_rebinding_refuses_a_map_of_other_speeches(tmp_path):
    from lib import semantic

    with pytest.raises(ValueError, match="row ids differ"):
        semantic.display_points(speeches(), {"a": (0, 0), "z": (1, 1)})


def test_the_committed_pin_is_one_this_code_reads():
    pin = semantic_release.load_pin()
    assert pin["url"].startswith(semantic_release.RELEASES)


@pytest.mark.parametrize("change", [{"schema": 2}, {"url": "https://example.org/semantic.zip"}])
def test_a_pin_this_code_cannot_read_is_refused_by_every_reader(tmp_path, change):
    """The export used to parse the pin raw, and only the restore checked it."""
    path = tmp_path / "pin.json"
    path.write_text(json.dumps({"schema": 1, "url": semantic_release.RELEASES + "x.zip"} | change))
    with pytest.raises(ValueError, match="unsupported"):
        semantic_release.load_pin(path)
    with pytest.raises(ValueError, match="unsupported"):
        semantic_release.check_against_pin(tmp_path, tmp_path / "corpus.parquet", path)
