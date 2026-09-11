import hashlib
import json
import zipfile

import pandas as pd
import pytest
from lib import artifacts, semantic_release


def release(tmp_path, *, extra=None, corpus="corpus", corrupt=False):
    files = dict.fromkeys(semantic_release.FILES, b"{}")
    meta = {"inputs": [{"sha256": corpus}], "files": {
        name: hashlib.sha256(value).hexdigest() for name, value in files.items()
    }}
    files["manifest.json"] = json.dumps(meta).encode()
    pin = {"manifest_sha256": hashlib.sha256(files["manifest.json"]).hexdigest(),
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
    pin.update(schema=1, url="https://github.com/fmadore/genocide-at-the-security-council/releases/download/test/semantic.zip")
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
    monkeypatch.setattr(export_web, "ROOT", tmp_path)
    monkeypatch.setattr(export_web, "SPEECHES_FLAGGED", corpus)
    export_web.copy_part([source], "semantic", root=tmp_path / "web")
    pin["manifest_sha256"] = "different artifact"
    (config / "semantic-release.json").write_text(json.dumps(pin))
    with pytest.raises(ValueError, match="different corpus"):
        export_web.copy_part([source], "semantic", root=tmp_path / "web")
