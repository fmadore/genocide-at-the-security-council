"""The Markdown table every step's findings note is written with."""

from __future__ import annotations

import pytest
from lib import notes


def test_a_table_is_a_header_a_rule_and_a_line_per_row() -> None:
    assert notes.table(["Year", "Speeches"], [[1994, "1,234"], ["2001", ""]], "lr") == [
        "| Year | Speeches |",
        "|---|---:|",
        "| 1994 | 1,234 |",
        "| 2001 |  |",
    ]


def test_a_row_that_does_not_fit_the_header_is_refused() -> None:
    with pytest.raises(ValueError, match="a row of 1 cells under 2 headers"):
        notes.table(["Year", "Speeches"], [[1994]], "lr")


def test_every_column_needs_a_known_alignment() -> None:
    with pytest.raises(ValueError, match="must give l or r"):
        notes.table(["Year", "Speeches"], [], "l")
    with pytest.raises(ValueError, match="must give l or r"):
        notes.table(["Year", "Speeches"], [], "lc")
