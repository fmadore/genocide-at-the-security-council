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
