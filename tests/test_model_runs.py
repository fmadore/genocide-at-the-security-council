"""The same input refusals apply to every model consumer."""

import json

import pytest
from lib import model_runs


def test_duplicate_rows_never_become_a_sampling_stratum():
    row = {"occurrence_id": "x", "model": "m"}
    with pytest.raises(ValueError, match="duplicate"):
        model_runs.validate({"model": "m"}, [row, row])


def test_row_cannot_claim_another_instrument():
    with pytest.raises(ValueError, match="model"):
        model_runs.validate({"model": "m"}, [{"occurrence_id": "x", "model": "different"}])


def test_partial_population_is_not_refused_as_incomplete():
    model_runs.validate({"model": "m"}, [{"occurrence_id": "x", "model": "m"}])


def test_readers_refuse_a_pending_transaction(tmp_path):
    (tmp_path / "pending.json").write_text("{}")
    with pytest.raises(ValueError, match="unfinished transaction"):
        model_runs.read(tmp_path)


def test_referent_revision_must_match_the_manifest():
    with pytest.raises(ValueError, match="referents_version"):
        model_runs.validate({"referents_version": "1"}, [{"occurrence_id": "x", "referents_version": "2"}])


def test_named_directory_must_hold_the_named_run(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "another-run"}))
    with pytest.raises(ValueError, match="directory and manifest"):
        model_runs.read(tmp_path)


# --- The one run allowed to publish with a coverage gap ----------------------
#
# Only the Makefile used to read `allow_partial_run.txt`, so running step 15
# directly refused the run `make` published.


def test_the_allowance_names_one_committed_run(tmp_path, monkeypatch):
    allowance = tmp_path / "allow_partial_run.txt"
    allowance.write_text("2026-09-08-qwen-131k\n", encoding="utf-8")
    monkeypatch.setattr(model_runs, "ALLOW_PARTIAL_RUN", allowance)
    assert model_runs.partial_allowed("2026-09-08-qwen-131k")
    assert not model_runs.partial_allowed("2026-08-31-gemini-v1")
    # A run read by path has no committed id, and an empty file allows nothing.
    assert not model_runs.partial_allowed("")
    allowance.write_text("", encoding="utf-8")
    assert not model_runs.partial_allowed("")


def test_an_absent_allowance_allows_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(model_runs, "ALLOW_PARTIAL_RUN", tmp_path / "absent.txt")
    assert not model_runs.partial_allowed("2026-09-08-qwen-131k")


def test_an_allowed_gap_is_published_and_said_and_an_unallowed_one_refused(capsys):
    from lib import usage_refusals

    usage_refusals.refuse_partial(9, 10, "allow_partial_run.txt names this run")
    assert "allow_partial_run.txt names this run: 9 of 10" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        usage_refusals.refuse_partial(9, 10, "")
    usage_refusals.refuse_partial(10, 10, "")
