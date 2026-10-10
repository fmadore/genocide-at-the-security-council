"""Exercise actor summaries using exactly the columns the pipeline loads."""

from __future__ import annotations

import importlib
import json

import pandas as pd
from conftest import make_speeches
from lib import actors, lexicon, series


def _speech(row: int, country: str, year: int, words: int, *, term: bool, count: int) -> dict:
    return {
        "row_id": f"r{row}",
        "year": year,
        "country_org": country,
        "meeting_symbol": f"S/PV.{year}",
        "words": words,
        "tokens": words * 6 // 5,
        "entity_type": "state",
        "iso3": country[:3].upper(),
        "un_regional_group": "African Group",
        "speaker_group": "E10",
        "lat": 1.0,
        "lon": 2.0,
        "has_genocide": term,
        "n_genocide": count,
    }


def loaded_corpus() -> pd.DataFrame:
    """The frame `load_corpus` would return: 11's columns and the tracked ones, no more."""
    rows = [
        _speech(i, "Loud", 2000 + i % 4, 500, term=i < 10, count=2 if i < 2 else (1 if i < 10 else 0))
        for i in range(200)
    ]
    rows += [
        _speech(1000 + i, "Quiet", 1995, 200, term=i < 2, count=2 if i == 0 else (1 if i == 1 else 0))
        for i in range(5)
    ]
    # The source flags follow from `entity_type` and `speaker_group`, as 02 reads them.
    frame = make_speeches(rows)
    wanted = actors.COLUMNS + [
        column
        for kind, name in actors.TRACKED
        for column in series.columns_for(kind, name)
        if column is not None
    ]
    assert set(wanted) <= set(frame.columns), sorted(set(wanted) - set(frame.columns))
    return frame.loc[:, wanted]


def test_the_builders_run_on_the_columns_the_step_loads() -> None:
    speeches = loaded_corpus()
    # Nothing beyond the declared columns: the frame is cut to `wanted` above,
    # so a builder reaching for a column the step never asked for fails here.
    assert "has_ethnic_cleansing" not in speeches.columns

    lex = lexicon.load()
    prevalence = float(speeches[f"has_{actors.HEADLINE}"].mean())
    assert 0 < prevalence < 1
    assert actors.informative_zero_minimum(prevalence) > 0

    slices = actors.periods(int(speeches["year"].min()), int(speeches["year"].max()))
    measures, computed = actors.build_measures(speeches, lex, slices, minimum=100)

    assert actors.HEADLINE in computed
    assert set(measures) == {name for _, name in actors.TRACKED}
    assert "derived_from" not in measures[actors.HEADLINE]
    periods = actors.build_periods(speeches, slices, computed, minimum=100)
    assert [p["key"] for p in periods] == [window.key for window in slices]
    whole = computed[actors.HEADLINE][actors.WHOLE]
    assert int(whole["speeches"].sum()) == int(speeches[f"has_{actors.HEADLINE}"].sum())


def test_only_the_full_word_family_is_published() -> None:
    assert actors.TRACKED == [("terms", "genocide")]


def test_every_measure_withholds_from_the_same_speakers() -> None:
    """One denominator, one withholding, whatever is counted inside it.

    A rate shown for one measure and withheld for the other, on the same
    speaker in the same period, would read as a finding about the two
    vocabularies. The step refuses such a payload; this is the check it makes.
    """
    speeches = loaded_corpus()
    _, computed = actors.build_measures(speeches, lexicon.load(), actors.periods(1995, 2003), 100)

    computed["comparison_fixture"] = dict(computed[actors.HEADLINE])
    assert actors.reconcile_withholding(computed) == []

    # A measure that withheld from a different set of speakers is caught.
    broken = {name: dict(frames) for name, frames in computed.items()}
    damaged = broken["genocide"][actors.WHOLE].copy()
    damaged.loc[damaged.index[0], "sufficient"] = not damaged.loc[damaged.index[0], "sufficient"]
    broken["genocide"][actors.WHOLE] = damaged
    assert any("sufficient" in problem for problem in actors.reconcile_withholding(broken))


def test_the_headline_is_named_once(tmp_path, monkeypatch) -> None:
    """No read of the headline measure by its literal name.

    A rename of `TRACKED` must be the only edit a change of headline needs;
    every other place reaches the measure through `HEADLINE`. So 11 is run
    whole, in process, with `war_crimes` as the headline over a corpus that
    has no genocide columns at all: a literal left behind anywhere in the step
    or in `lib.actors` fails here with a missing column or measure.
    """
    assert actors.TRACKED[0][1] == actors.HEADLINE
    step = importlib.import_module("11_countries")
    tracked = [("terms", "war_crimes")]
    for module in (actors, step):
        monkeypatch.setattr(module, "TRACKED", tracked)
        monkeypatch.setattr(module, "HEADLINE", "war_crimes")

    # Every period 11 reports holds speeches, and two speakers clear the minimum.
    rows = [
        {
            "year": year,
            "country_org": country,
            "meeting_symbol": f"S/PV.{year}",
            "has_war_crimes": (year + i) % 9 == 0,
            "n_war_crimes": int((year + i) % 9 == 0),
        }
        for year in range(1946, 2024)
        for i, country in enumerate(["Loud", "Quiet", "Loud"])
    ]
    corpus = make_speeches(rows)
    parquet = tmp_path / "speeches_flagged.parquet"
    corpus.to_parquet(parquet, index=False)
    monkeypatch.setattr(step, "SPEECHES_FLAGGED", parquet)
    monkeypatch.setattr(step, "COUNTRIES", tmp_path / "countries")
    monkeypatch.setattr(step, "ensure_dirs", lambda: None)
    monkeypatch.setattr(step, "write_note", lambda name, body: tmp_path / name)
    monkeypatch.setattr(step, "EXPECTED_SPEECHES", len(corpus))
    monkeypatch.setattr(step, "EXPECTED_TOKENS", int(corpus["tokens"].sum()))
    monkeypatch.setattr(step, "EXPECTED_WORDS", int(corpus["words"].sum()))

    step.run(30)

    written = json.loads((tmp_path / "countries" / "countries.json").read_text(encoding="utf-8"))
    assert set(written["measures"]) == {"war_crimes"}
    assert "genocide" not in json.dumps(written["measures"])


def test_a_period_without_speeches_has_no_share_rather_than_a_crash(tmp_path, monkeypatch) -> None:
    """The note's table divides by each period's speeches. A corpus that starts
    after a period it reports, as a test corpus or a subset may, has none there,
    and the row shows a dash where the division used to raise."""
    step = importlib.import_module("11_countries")
    rows = [
        {
            "year": year,
            "country_org": country,
            "meeting_symbol": f"S/PV.{year}",
            "has_genocide": (year + i) % 3 == 0,
            "n_genocide": int((year + i) % 3 == 0),
        }
        for year in range(2000, 2024)
        for i, country in enumerate(["Loud", "Quiet", "Loud"])
    ]
    corpus = make_speeches(rows)
    parquet = tmp_path / "speeches_flagged.parquet"
    corpus.to_parquet(parquet, index=False)
    notes: dict[str, str] = {}
    monkeypatch.setattr(step, "SPEECHES_FLAGGED", parquet)
    monkeypatch.setattr(step, "COUNTRIES", tmp_path / "countries")
    monkeypatch.setattr(step, "ensure_dirs", lambda: None)

    def write_note(name: str, body: str):
        notes[name] = body
        return tmp_path / name

    monkeypatch.setattr(step, "write_note", write_note)
    monkeypatch.setattr(step, "EXPECTED_SPEECHES", len(corpus))
    monkeypatch.setattr(step, "EXPECTED_TOKENS", int(corpus["tokens"].sum()))
    monkeypatch.setattr(step, "EXPECTED_WORDS", int(corpus["words"].sum()))

    step.run(10)

    (body,) = notes.values()
    empty = [line for line in body.splitlines() if line.startswith("| 1950-1959 | 0 |")]
    assert empty and empty[0].endswith("| — |")
