import importlib.util
from pathlib import Path

import pandas as pd


def test_annual_denominators_missing_years_and_boundary():
    spec = importlib.util.spec_from_file_location("actor_year", Path(__file__).parents[1] / "scripts/20_actor_year.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frame = pd.DataFrame({
        "row_id": ["a", "b", "c"], "year": [2000, 2000, 2002],
        "country_org": ["A", "A", "B"], "meeting_symbol": ["m", "m", "n"],
        "words": [10, 30, 20], "tokens": [12, 32, 22],
        "has_genocide": [True, False, True], "n_genocide": [2, 0, 1],
    })
    rows = module.annual_table(frame, "genocide", minimum=2).set_index(["country_org", "year"])
    assert len(rows) == 6
    assert rows.loc[("A", 2000), "held"] == 2
    assert rows.loc[("A", 2000), "words"] == 40
    assert rows.loc[("A", 2000), "meetings"] == 1
    assert rows.loc[("A", 2000), "sufficient"]
    assert rows.loc[("A", 2001), "withheld_reason"] == "no speeches"
    assert pd.isna(rows.loc[("B", 2002), "speech_rate"])
    assert rows.loc[("B", 2002), "occurrences"] == 1
