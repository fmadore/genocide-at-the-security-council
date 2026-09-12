"""Exercise actor summaries using exactly the columns the pipeline loads."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pandas as pd
from lib import actors, lexicon, series

STEP = Path(__file__).resolve().parents[1] / "scripts" / "11_countries.py"


def _step():
    spec = importlib.util.spec_from_file_location("countries_step", STEP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def loaded_corpus(step) -> pd.DataFrame:
    """The frame `load_corpus` would return: 11's columns and the tracked ones, no more."""
    rows = [
        _speech(i, "Loud", 2000 + i % 4, 500, term=i < 10, count=2 if i < 2 else (1 if i < 10 else 0))
        for i in range(200)
    ]
    rows += [
        _speech(1000 + i, "Quiet", 1995, 200, term=i < 2, count=2 if i == 0 else (1 if i == 1 else 0))
        for i in range(5)
    ]
    frame = pd.DataFrame(rows)
    frame = frame.assign(
        source_state=True,
        source_un_org=False,
        source_igo=False,
        source_ngo=False,
        source_permanent_member=False,
        source_elected_member=True,
    )
    wanted = step.COLUMNS + [
        column
        for kind, name in step.TRACKED
        for column in series.columns_for(kind, name)
        if column is not None
    ]
    assert set(wanted) <= set(frame.columns), sorted(set(wanted) - set(frame.columns))
    return frame.loc[:, wanted]


def test_the_builders_run_on_the_columns_the_step_loads() -> None:
    step = _step()
    speeches = loaded_corpus(step)
    # Nothing beyond the declared columns: the frame is cut to `wanted` above,
    # so a builder reaching for a column the step never asked for fails here.
    assert "has_ethnic_cleansing" not in speeches.columns

    lex = lexicon.load()
    prevalence = float(speeches[f"has_{step.HEADLINE}"].mean())
    assert 0 < prevalence < 1
    assert actors.informative_zero_minimum(prevalence) > 0

    slices = actors.periods(int(speeches["year"].min()), int(speeches["year"].max()))
    measures, computed = step.build_measures(speeches, lex, slices, minimum=100)

    assert step.HEADLINE in computed
    assert set(measures) == {name for _, name in step.TRACKED}
    assert "derived_from" not in measures[step.HEADLINE]
    periods = step.build_periods(speeches, slices, computed, minimum=100)
    assert [p["key"] for p in periods] == [window.key for window in slices]
    whole = computed[step.HEADLINE][actors.WHOLE]
    assert int(whole["speeches"].sum()) == int(speeches[f"has_{step.HEADLINE}"].sum())


def test_only_the_full_word_family_is_published() -> None:
    step = _step()
    assert step.TRACKED == [("terms", "genocide")]


def test_every_measure_withholds_from_the_same_speakers() -> None:
    """One denominator, one withholding, whatever is counted inside it.

    A rate shown for one measure and withheld for the other, on the same
    speaker in the same period, would read as a finding about the two
    vocabularies. The step refuses such a payload; this is the check it makes.
    """
    step = _step()
    speeches = loaded_corpus(step)
    _, computed = step.build_measures(speeches, lexicon.load(), actors.periods(1995, 2003), 100)

    computed["comparison_fixture"] = dict(computed[step.HEADLINE])
    assert actors.reconcile_withholding(computed) == []

    # A measure that withheld from a different set of speakers is caught.
    broken = {name: dict(frames) for name, frames in computed.items()}
    damaged = broken["genocide"][actors.WHOLE].copy()
    damaged.loc[damaged.index[0], "sufficient"] = not damaged.loc[damaged.index[0], "sufficient"]
    broken["genocide"][actors.WHOLE] = damaged
    assert any("sufficient" in problem for problem in actors.reconcile_withholding(broken))


def test_the_headline_is_named_once_in_the_source() -> None:
    """No read of the headline measure by its literal name.

    A rename of `TRACKED` must be the only edit a change of headline needs;
    every other place reaches the measure through `HEADLINE`, so a literal
    left behind is a regression waiting for the next rename.
    """
    source = STEP.read_text(encoding="utf-8")
    literal = re.compile(r"""computed\[\s*["']genocide["']\s*\]|["']n?_?has_genocide["']|["']n_genocide["']""")
    assert not literal.findall(source), literal.findall(source)
    assert "HEADLINE = TRACKED[0][1]" in source
