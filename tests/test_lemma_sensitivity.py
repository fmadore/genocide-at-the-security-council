"""Exercise the optional lemma analysis with a known inflection merge."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
from lib import artifacts, lemmas, lexical


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/18_lexical_robustness.py"
    spec = importlib.util.spec_from_file_location("lemma_sensitivity_step", script)
    step = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step)
    bodies = ["killings " * 20, "killed " * 20, "peace " * 20, "peace " * 20]
    frame = pd.DataFrame({
        "row_id": [1, 2, 3, 4], "text": bodies, "body_start": [0] * 4,
        "meeting_symbol": ["A", "B", "A", "C"], "has_genocide": [True, True, False, False],
        "year": [1994] * 4, "agenda_item_manual": ["item"] * 4, "speaker_group": ["state"] * 4,
    })
    corpus = tmp_path / "corpus.parquet"
    frame.to_parquet(corpus, index=False)
    layer = tmp_path / "lemmas"
    layer.mkdir()
    pd.DataFrame({
        "row_id": [1, 2, 3, 4],
        "lemmas": [lemmas.encode([word] * 20) for word in ["kill", "kill", "peace", "peace"]],
        "body_sha256": [lemmas.body_hash(body) for body in bodies],
    }).to_parquet(layer / "lemmas.parquet", index=False)
    (layer / "manifest.json").write_text(json.dumps({
        "layer_schema": lemmas.LAYER_SCHEMA, "tokenizer": lexical.TOKEN_RE.pattern,
        "table_sha256": artifacts.sha256(layer / "lemmas.parquet"),
    }), encoding="utf-8")
    monkeypatch.setattr(step, "SPEECHES_FLAGGED", corpus)
    monkeypatch.setattr(step, "DERIVED", tmp_path)
    return step, layer, tmp_path


def test_complete_comparison_and_merge_audit(analysis):
    step, layer, root = analysis
    step.run(20260807, 100, layer)
    target = root / "lexical_robustness_lemma"
    comparison = pd.read_csv(target / "lemma_comparison.csv").set_index("word")
    assert comparison.loc["kill", "lemma_rank"] == 1
    assert pd.isna(comparison.loc["kill", "surface_rank"])
    assert pd.isna(comparison.loc["killings", "lemma_rank"])
    forms = pd.read_csv(target / "lemma_forms.csv")
    assert set(forms.surface) == {"killings", "killed"}
    assert forms.occurrences.sum() == 40
    influence = pd.read_csv(target / "lemma_meeting_influence.csv").set_index("word")
    assert influence.loc["kill", "valid_deletions"] == 3
    assert influence.loc["kill", "sign_reversals"] == 0
    manifest = json.loads((target / "manifest.json").read_text())
    assert manifest["lemma_sensitivity"]["tokens"] == manifest["current_tokens"] == [40, 40]
    assert not (root / "lexical_robustness").exists()


def test_invalid_layer_does_not_replace_previous_output(analysis):
    step, layer, root = analysis
    target = root / "lexical_robustness_lemma"
    target.mkdir()
    previous = target / "previous.txt"
    previous.write_text("retain", encoding="utf-8")
    (layer / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        step.run(20260807, 100, layer)
    assert previous.read_text() == "retain"


def test_empty_lemma_ranking_is_a_reported_result(analysis):
    step, layer, root = analysis
    table = pd.read_parquet(layer / "lemmas.parquet")
    table["lemmas"] = lemmas.encode(["peace"] * 20)
    table.to_parquet(layer / "lemmas.parquet", index=False)
    manifest = json.loads((layer / "manifest.json").read_text())
    manifest["table_sha256"] = artifacts.sha256(layer / "lemmas.parquet")
    (layer / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    step.run(20260807, 100, layer)
    target = root / "lexical_robustness_lemma"
    assert pd.read_csv(target / "lemma_meeting_influence.csv").empty
    assert list(pd.read_parquet(target / "lemma_deletion_effects.parquet")) == step.EFFECT_COLUMNS
    meta = json.loads((target / "manifest.json").read_text())
    assert meta["lemma_sensitivity"]["ranked_words"] == 0


def test_partial_collapse_exposes_residual_counts(analysis):
    step, layer, root = analysis
    table = pd.read_parquet(layer / "lemmas.parquet")
    table.loc[0, "lemmas"] = lemmas.encode(["kill"] * 10 + ["killings"] * 10)
    table.to_parquet(layer / "lemmas.parquet", index=False)
    manifest = json.loads((layer / "manifest.json").read_text())
    manifest["table_sha256"] = artifacts.sha256(layer / "lemmas.parquet")
    (layer / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    step.run(20260807, 100, layer)
    rows = pd.read_csv(root / "lexical_robustness_lemma/lemma_comparison.csv").set_index("word")
    row = rows.loc["killings"]
    assert row["partly_lemmatized"]
    assert row["surface_target"] == 20
    assert row["lemma_target"] == row["unchanged_surface_tokens"] == 10
    assert not rows.loc["kill", "partly_lemmatized"]
