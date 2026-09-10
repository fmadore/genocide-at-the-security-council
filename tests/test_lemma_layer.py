"""Content identity must survive reordered joins and reject stale but same-length text."""

import json

import pandas as pd
import pytest
from lib import artifacts, lemmas, lexical


@pytest.fixture
def layer(tmp_path):
    speeches = pd.DataFrame({
        "row_id": [10, 20], "text": ["The killings", "Two countries"], "body_start": [4, 4],
    }, index=[7, 9])
    table = pd.DataFrame({
        "row_id": [20, 10], "lemmas": ["country", "killing"],
        "body_sha256": [lemmas.body_hash("countries"), lemmas.body_hash("killings")],
    })

    def save(table=table, **updates):
        table.to_parquet(tmp_path / "lemmas.parquet", index=False)
        manifest = {
            "layer_schema": lemmas.LAYER_SCHEMA, "tokenizer": lexical.TOKEN_RE.pattern,
            "table_sha256": artifacts.sha256(tmp_path / "lemmas.parquet"), **updates,
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    save()
    return tmp_path, speeches, table, save


def test_alignment_uses_ids_and_preserves_requested_index(layer):
    directory, speeches, _, _ = layer
    result = lemmas.load_layer(directory, speeches)
    assert result.to_dict() == {7: "killing", 9: "country"}
    assert lemmas.load_layer(directory, speeches.iloc[[1]]).to_dict() == {9: "country"}


def test_same_token_count_different_text_is_stale(layer):
    directory, speeches, _, _ = layer
    speeches.loc[7, "text"] = "The murders"
    with pytest.raises(ValueError, match="body differs"):
        lemmas.load_layer(directory, speeches)


@pytest.mark.parametrize("updates", [{"layer_schema": 1}, {"tokenizer": "[a-z]+"}])
def test_old_schema_or_tokenizer_refused(layer, updates):
    directory, speeches, _, save = layer
    save(**updates)
    with pytest.raises(ValueError, match="schema/tokenizer"):
        lemmas.load_layer(directory, speeches)


def test_changed_parquet_refused(layer):
    directory, speeches, table, _ = layer
    table.loc[0, "lemmas"] = "nation"
    table.to_parquet(directory / "lemmas.parquet", index=False)
    with pytest.raises(ValueError, match="checksum"):
        lemmas.load_layer(directory, speeches)


@pytest.mark.parametrize("row", ["two countries", "country!", None])
def test_invalid_sequence_with_valid_checksum_refused(layer, row):
    directory, speeches, table, save = layer
    table.loc[0, "lemmas"] = row
    save(table)
    with pytest.raises(ValueError, match=r"alignment|must be text"):
        lemmas.load_layer(directory, speeches)


def test_missing_or_duplicate_ids_refused(layer):
    directory, speeches, table, save = layer
    save(table.iloc[:1])
    with pytest.raises(ValueError, match="missing"):
        lemmas.load_layer(directory, speeches)
    save(pd.concat([table, table.iloc[:1]]))
    with pytest.raises(ValueError, match="unique"):
        lemmas.load_layer(directory, speeches)


def test_pair_selection_keeps_corpus_order(layer):
    _, speeches, _, _ = layer
    pairs = pd.DataFrame({"target_row_id": [20], "control_row_id": [10]})
    assert lemmas.select_pairs(speeches, pairs).equals(speeches)


@pytest.mark.parametrize("target,control", [(10, 10), (10, 30), (None, 20)])
def test_bad_pair_selection_refused(layer, target, control):
    _, speeches, _, _ = layer
    with pytest.raises(ValueError, match="IDs"):
        lemmas.select_pairs(speeches, pd.DataFrame({
            "target_row_id": [target], "control_row_id": [control],
        }))
