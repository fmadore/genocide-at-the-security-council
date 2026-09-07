"""Run identity and interrupted speech transactions, without inference."""

import json

import pytest
from lib import artifacts, run_store


def test_only_one_process_may_write_a_run(tmp_path):
    with run_store.writer(tmp_path), pytest.raises(ValueError, match="Another process"), run_store.writer(tmp_path):
        pytest.fail("second writer acquired the run")
    with run_store.writer(tmp_path):
        pass


def test_identity_refuses_a_changed_referent_before_writing(tmp_path):
    identity = {"prompt": "p", "referents": "old", "corpus": "c", "runtime": {}}
    run_store.bind_identity(tmp_path, identity)
    before = (tmp_path / "identity.json").read_bytes()
    with pytest.raises(ValueError, match="identity"):
        run_store.bind_identity(tmp_path, {**identity, "referents": "new"})
    assert (tmp_path / "identity.json").read_bytes() == before


@pytest.mark.parametrize("cut", [0, 5, 12])
def test_recovery_finishes_a_torn_speech_exactly_once(tmp_path, cut):
    target = tmp_path / "annotations.jsonl"
    target.write_bytes(b'{"old":1}\n')
    addition = '{"id":"one"}\n{"id":"two"}\n'
    pending = {"appends": {"annotations.jsonl": {"offset": target.stat().st_size,
                "text": addition}}, "manifest": {"requests": {"sent": 1}}}
    artifacts.atomic_write_json(tmp_path / "pending.json", pending)
    with target.open("ab") as stream:
        stream.write(addition.encode()[:cut])
    run_store.recover(tmp_path)
    run_store.recover(tmp_path)
    assert target.read_bytes() == b'{"old":1}\n' + addition.encode()
    assert json.loads((tmp_path / "manifest.json").read_text()) == pending["manifest"]


def test_recovery_after_manifest_write_does_not_double_count(tmp_path):
    manifest = {"requests": {"sent": 1}, "usage": {"output_tokens": 17}}
    run_store.commit(tmp_path, {"annotations.jsonl": [{"id": "one"}]}, manifest)
    run_store.recover(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest
    assert len((tmp_path / "annotations.jsonl").read_text().splitlines()) == 1


def test_recovery_refuses_a_conflicting_tail(tmp_path):
    (tmp_path / "annotations.jsonl").write_text("different")
    artifacts.atomic_write_json(tmp_path / "pending.json", {
        "appends": {"annotations.jsonl": {"offset": 0, "text": "expected"}},
        "manifest": {},
    })
    with pytest.raises(ValueError, match="conflict"):
        run_store.recover(tmp_path)
    assert (tmp_path / "annotations.jsonl").read_text() == "different"


@pytest.mark.parametrize("field", ["corpus", "runtime", "requests", "probe"])
def test_every_instrument_input_is_fixed(tmp_path, field):
    identity = dict.fromkeys(["corpus", "runtime", "requests", "probe"], "old")
    run_store.bind_identity(tmp_path, identity)
    with pytest.raises(ValueError, match="identity"):
        run_store.bind_identity(tmp_path, {**identity, field: "new"})


def test_actual_failure_between_append_and_manifest_recovers(tmp_path, monkeypatch):
    original = artifacts.atomic_write_json
    def interrupt(path, *args, **kwargs):
        if path.name == "manifest.json":
            raise OSError("simulated interruption")
        original(path, *args, **kwargs)
    monkeypatch.setattr(artifacts, "atomic_write_json", interrupt)
    manifest = {"requests": {"sent": 1}, "usage": {"output_tokens": 17}}
    with pytest.raises(OSError, match="interruption"):
        run_store.commit(tmp_path, {"annotations.jsonl": [{"id": "one"}, {"id": "two"}]}, manifest)
    monkeypatch.setattr(artifacts, "atomic_write_json", original)
    run_store.recover(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest
    assert len((tmp_path / "annotations.jsonl").read_text().splitlines()) == 2
    assert not (tmp_path / "pending.json").exists()
