"""The per-speaker step, on the columns it actually loads.

`11_countries.py` reads a narrow column set from the flagged parquet — its own
`COLUMNS` plus what `series.columns_for` names for each tracked measure — and
nothing else. On 2 September 2026 the tracked list moved to the derived
`genocide_qualification` while five reads of `computed["genocide"]` and a
prevalence over `has_genocide` stayed behind, on columns the step no longer
loaded; the deploy died on the first of them, after 03 had been repaired. The
end-to-end test could not have caught it: 11 asserts the real corpus totals
and cannot run on a synthetic one.

So the step is exercised here on exactly the frame `load_corpus` would hand it,
and its source is held to naming the headline once.
"""

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
        "has_genocide_qualification": term,
        "n_genocide_qualification": count,
        "has_set_atrocity_core": term,
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
    assert "has_genocide" not in speeches.columns  # the raw term is not loaded

    lex = lexicon.load()
    prevalence = float(speeches[f"has_{step.HEADLINE}"].mean())
    assert 0 < prevalence < 1
    assert actors.informative_zero_minimum(prevalence) > 0

    slices = actors.periods(int(speeches["year"].min()), int(speeches["year"].max()))
    measures, computed = step.build_measures(speeches, lex, slices, minimum=100)

    assert step.HEADLINE in computed
    assert set(measures) == {name for _, name in step.TRACKED}
    assert measures[step.HEADLINE]["derived_from"] == "genocide"
    periods = step.build_periods(speeches, slices, computed, minimum=100)
    assert [p["key"] for p in periods] == [window.key for window in slices]
    whole = computed[step.HEADLINE][actors.WHOLE]
    assert int(whole["speeches"].sum()) == int(speeches[f"has_{step.HEADLINE}"].sum())


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
