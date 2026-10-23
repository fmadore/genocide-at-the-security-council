"""The victim-group table, `annotations/lexicon/victim_groups.csv`, read and applied.

`victim_group` is free text: the model names the people a passage concerns in
its own words, so 2,070 filled labels in the first published run came in 889
spellings, and "the Jewish people" and "Jews" could not be counted together.
This module gives each label the group a person-checked table assigns it. It
never rewrites the label itself, which is published as the model wrote it.

Matching is deliberately thin. :func:`key` only lower-cases, drops a leading
"the" and collapses spaces; every merge beyond that — plurals, places, the
Tutsi and the Rwandans — is a row in the table that a reader can see and
dispute. A row may name a referent, and then applies only to occurrences placed
on that referent, before the row without one: "Muslims" is a different people
in 1948, 1993 and 2018, and the passage's referent already says which.

A label the table does not list gets an empty group. It is not guessed, and
:func:`review_rows` lists it for a coder with its count.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .paths import rel

COLUMNS = ("label", "referent", "group", "checked")


class VictimGroupError(ValueError):
    """`victim_groups.csv` breaks a rule of the table."""


def key(label: str) -> str:
    """The form a label is looked up under: case, a leading "the" and spacing set aside."""
    flat = label.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'").strip().casefold()
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", flat))


@dataclass(frozen=True)
class VictimGroups:
    """The table, indexed: `(key, referent)` first, then `(key, "")`."""

    path: Path
    rows: Mapping[tuple[str, str], str]

    def group(self, label: str, referent: str = "") -> str:
        """The group for one occurrence's label, or `""` when the table has none."""
        if not label:
            return ""
        found = key(label)
        return self.rows.get((found, referent)) or self.rows.get((found, ""), "")


def read(path: Path) -> VictimGroups:
    """Parse the table, refusing a row that would make a label mean two things."""
    where = rel(path)
    frame = pd.read_csv(path, encoding="utf-8", comment="#", dtype=str, keep_default_na=False)
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise VictimGroupError(f"{where} lacks the column(s) {', '.join(sorted(missing))}")
    rows: dict[tuple[str, str], str] = {}
    for number, entry in enumerate(frame.to_dict(orient="records"), start=2):
        label, referent, group = (str(entry[c]).strip() for c in ("label", "referent", "group"))
        checked = str(entry["checked"]).strip()
        if not label or not group:
            raise VictimGroupError(f"{where}, row {number}: a row needs both a label and a group")
        if label != key(label):
            raise VictimGroupError(
                f"{where}, row {number}: {label!r} is not in lookup form; write {key(label)!r}"
            )
        if checked not in {"yes", "no"}:
            raise VictimGroupError(f"{where}, row {number}: checked is {checked!r}, not yes or no")
        if (label, referent) in rows:
            raise VictimGroupError(
                f"{where}, row {number}: {label!r}"
                + (f" under {referent!r}" if referent else "")
                + " is listed twice"
            )
        rows[(label, referent)] = group
    return VictimGroups(path=path, rows=rows)


def review_rows(
    table: VictimGroups, occurrences: Iterable[tuple[str, str]]
) -> list[dict[str, object]]:
    """Every distinct label with its count and group, most frequent first, for a coder.

    `occurrences` is `(victim_group, referent)` per occurrence. A label is
    counted under its lookup key, so the list is as long as the table would
    need to be to cover everything.
    """
    counts: Counter[str] = Counter()
    grouped: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    for label, referent in occurrences:
        if not label:
            continue
        found = key(label)
        counts[found] += 1
        spellings.setdefault(found, Counter())[label] += 1
        if table.group(label, referent):
            grouped[found] += 1
    return [
        {
            "label": found,
            "occurrences": total,
            "grouped": grouped[found],
            "group": table.rows.get((found, ""), ""),
            "spellings": " | ".join(s for s, _ in spellings[found].most_common()),
        }
        for found, total in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
