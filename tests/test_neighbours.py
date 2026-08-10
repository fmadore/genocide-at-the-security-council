"""The nearest-neighbour inspection written by 06.

docs/PLAN.md §4 asks for this before any topic model is trusted, and it is the
part of 06 most able to produce a confident-looking table that means nothing: a
join off by one row still yields ten neighbours, a plausible cosine and a
summary that reads fine.

The step is loaded the way `test_fetch.py` loads 00 — by path, since the
numbered scripts are orchestrators rather than importable modules. Nothing here
touches torch: `lib.embeddings` imports it inside the functions that need it, so
everything below runs on any machine.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from lib import embeddings


@pytest.fixture(scope="module")
def step():
    path = Path(__file__).resolve().parents[1] / "scripts" / "06_embed.py"
    spec = importlib.util.spec_from_file_location("embed_step", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus():
    """Three speeches about one thing, three about another, one bystander.

    Built so the right answer is known: rows 0-2 should find each other.
    """
    vectors = embeddings.l2_normalise(
        np.array(
            [
                [1.0, 0.0, 0.0],
                [0.99, 0.1, 0.0],
                [0.98, 0.15, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 0.1, 0.99],
                [0.0, 0.15, 0.98],
                [0.0, 1.0, 0.0],
            ]
        )
    )
    speeches = pd.DataFrame(
        {
            "row_id": [f"r{i}" for i in range(7)],
            "year": [1994, 1994, 2004, 1995, 2005, 2005, 2015],
            "country_org": ["Rwanda", "France", "Rwanda", "Bosnia", "France", "France", "Chile"],
            "has_genocide": [True, False, True, False, False, False, False],
        }
    )
    return vectors, speeches


def test_a_speech_is_never_its_own_neighbour(step, corpus) -> None:
    """The one error that would make every summary below meaningless."""
    _, rows = step.build_neighbours(*corpus, k=3)
    assert len(rows)
    assert (rows["row_id"] != rows["neighbour_row_id"]).all()


def test_one_row_per_target_per_rank(step, corpus) -> None:
    summary, rows = step.build_neighbours(*corpus, k=3)
    assert summary["targets"] == 2
    assert len(rows) == 2 * 3
    assert sorted(rows["rank"].unique()) == [1, 2, 3]


def test_neighbours_are_the_semantically_close_ones(step, corpus) -> None:
    """r0's nearest is r1, then r2 — not the row that happens to sit next to it
    in the parquet."""
    _, rows = step.build_neighbours(*corpus, k=2)
    first = rows[(rows["row_id"] == "r0") & (rows["rank"] == 1)]
    assert first["neighbour_row_id"].iloc[0] == "r1"


def test_cosines_do_not_increase_with_rank(step, corpus) -> None:
    _, rows = step.build_neighbours(*corpus, k=3)
    for _, block in rows.groupby("row_id"):
        ordered = block.sort_values("rank")["cosine"].to_numpy()
        assert np.all(np.diff(ordered) <= 1e-6)


def test_the_summary_reports_the_base_rate_beside_the_hit_rate(step, corpus) -> None:
    """A hit rate without its base rate is unreadable: 40% of neighbours using
    the term is either remarkable or expected, and only the second number says
    which."""
    summary, _ = step.build_neighbours(*corpus, k=3)
    assert summary["corpus_genocide_bearing_share"] == pytest.approx(2 / 7, abs=1e-4)
    assert 0.0 <= summary["top1_also_genocide_bearing"] <= 1.0


def test_same_year_and_same_speaker_are_measured(step, corpus) -> None:
    """If neighbours are mostly the same debate, the space found the occasion,
    not the vocabulary — so both shares are reported rather than inferred."""
    summary, rows = step.build_neighbours(*corpus, k=3)
    assert "top1_same_year" in summary
    assert "top1_same_speaker" in summary
    assert set(rows["same_speaker"].unique()) <= {True, False}


def test_a_corpus_with_no_genocide_bearing_speech_is_not_an_error(step, corpus) -> None:
    """The `--limit` smoke path: the first few hundred speeches may contain
    none, and the run must still finish rather than crash after the encode."""
    vectors, speeches = corpus
    summary, rows = step.build_neighbours(vectors, speeches.assign(has_genocide=False), k=3)
    assert summary["targets"] == 0
    assert rows.empty


def test_the_note_survives_an_empty_inspection(step, corpus) -> None:
    vectors, speeches = corpus
    summary, _ = step.build_neighbours(vectors, speeches.assign(has_genocide=False), k=3)
    plan = embeddings.Plan(
        pieces=["x"] * 7, owner=np.arange(7), weight=np.ones(7), chunked_rows=0
    )
    registry = embeddings.load_registry()
    note = step.build_note(
        registry.models[registry.default], speeches, plan, summary,
        {"device": "cpu", "gpu_packages": {}}, 1.0,
    )
    assert "Nearest-neighbour inspection" in note


def test_the_note_states_what_a_cosine_does_not_license(step, corpus) -> None:
    """docs/PLAN.md §4 governs; the caveat travels with the artefact rather than
    living only in the plan."""
    summary, _ = step.build_neighbours(*corpus, k=3)
    plan = embeddings.Plan(
        pieces=["x"] * 7, owner=np.arange(7), weight=np.ones(7), chunked_rows=0
    )
    registry = embeddings.load_registry()
    note = step.build_note(
        registry.models[registry.default], corpus[1], plan, summary,
        {"device": "cuda", "gpu_name": "H100", "gpu_packages": {"torch": "2.13.0"}}, 60.0,
    )
    assert "not about politics" in note
    assert "claim about position or influence" in note
    assert "not bit-exact" in note
