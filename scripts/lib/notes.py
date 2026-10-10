"""Markdown for the findings notes the steps write under notes/.

A note is read as a file and diffed between runs, so a table is written one
way in every step: a header, a rule that sets each column's alignment, and one
line per row, each cell already formatted by the caller.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

#: The rule under a column, by its alignment: `l` for text, `r` for numbers.
RULES = {"l": "---", "r": "---:"}


def row(cells: Sequence[object]) -> str:
    """One table line: the cells between pipes, with a pipe at each end."""
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def table(headers: Sequence[str], rows: Iterable[Sequence[object]], align: str) -> list[str]:
    """A Markdown table as note lines: the header, its rule, then one line per row.

    `align` gives each column one letter, `l` or `r`. A row whose cells do not
    match the headers in number is refused rather than written, because
    Markdown renders it without complaint and every cell after the gap lands
    in the wrong column.
    """
    if len(align) != len(headers) or set(align) - set(RULES):
        raise ValueError(f"align {align!r} must give l or r for each of {len(headers)} columns")
    lines = [row(headers), "|" + "|".join(RULES[column] for column in align) + "|"]
    for cells in rows:
        if len(cells) != len(headers):
            raise ValueError(f"a row of {len(cells)} cells under {len(headers)} headers: {cells!r}")
        lines.append(row(cells))
    return lines
