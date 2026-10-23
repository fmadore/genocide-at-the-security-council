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
:func:`review_rows` lists it for a coder with its count. :func:`victims_block`
counts the groups for the usage view's three victim figures.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

from .paths import rel
from .usage import eligible_mask

COLUMNS = ("label", "referent", "group", "checked")

#: The suffix of the groups that name no particular people: civilians, victims,
#: "our people". Counted apart from the peoples, never ranked among them.
UNSPECIFIED = " (unspecified)"

#: The four classes every eligible occurrence falls in, in the order the view stacks them.
KINDS = ("people", "unspecified", "ungrouped", "none")


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
    #: How many rows a person has marked `checked=yes`.
    checked: int = 0

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
    checked_rows = 0
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
        checked_rows += checked == "yes"
    return VictimGroups(path=path, rows=rows, checked=checked_rows)


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


def victims_block(rows: pd.DataFrame, table: VictimGroups) -> dict[str, object]:
    """Who the eligible occurrences name as the victim, by group, decade and speaker.

    Counted over eligible rows only, as every discourse figure is: a false
    positive names no victim, and a label whose evidence could not be found has
    nothing behind it. Each eligible row falls in exactly one of four classes, so
    a decade's four counts sum to its eligible occurrences:

    - `people`: a group that names a particular people;
    - `unspecified`: one of the groups that name none (civilians, victims);
    - `ungrouped`: a label the table does not list yet;
    - `none`: the passage names no victim at all.

    `cells` and `by_actor` are sparse and cover `people` and `unspecified` rows.
    `table` says how many rows the grouping rests on and how many a person has
    checked, so the view can say so beside every figure.
    """
    needed = {"victim_group", "referent", "country_org", "date", "verdict", "evidence_valid"}
    if missing := sorted(needed - set(rows.columns)):
        raise KeyError(f"victims_block() needs columns: {', '.join(missing)}")
    summary = {"rows": len(table.rows), "checked": table.checked}
    kept = rows.loc[eligible_mask(rows)] if not rows.empty else rows
    if kept.empty:
        return {"table": summary, "groups": [], "decades": [], "cells": [], "by_actor": []}
    years = pd.to_datetime(kept["date"], errors="coerce").dt.year
    if years.isna().any():
        raise ValueError("a victim count needs a date, and some eligible rows carry none")
    labels = kept["victim_group"].fillna("").astype(str)
    referents = kept["referent"].fillna("").astype(str)
    groups = pd.Series(
        [table.group(label, referent) for label, referent in zip(labels, referents, strict=True)],
        index=kept.index,
    )
    kind = pd.Series("people", index=kept.index)
    kind[groups.str.endswith(UNSPECIFIED)] = "unspecified"
    kind[(groups == "") & (labels.str.strip() != "")] = "ungrouped"
    kind[labels.str.strip() == ""] = "none"
    frame = pd.DataFrame(
        {
            "group": groups,
            "kind": kind,
            "decade": (years // 10 * 10).astype(int),
            "actor": kept["country_org"].astype(str),
        }
    )
    named = frame.loc[frame["kind"].isin(["people", "unspecified"])]

    group_rows = [
        {
            "group": str(group),
            "unspecified": str(group).endswith(UNSPECIFIED),
            "count": len(here),
            "actors": int(here["actor"].nunique()),
        }
        for group, here in named.groupby("group")
    ]
    group_rows.sort(key=lambda row: (-cast(int, row["count"]), str(row["group"])))

    decade_rows = []
    for decade in range(int(frame["decade"].min()), int(frame["decade"].max()) + 1, 10):
        here = frame.loc[frame["decade"] == decade, "kind"]
        decade_rows.append(
            {
                "decade": decade,
                "eligible": len(here),
                **{name: int((here == name).sum()) for name in KINDS},
            }
        )

    def sparse(by: str) -> list[dict[str, object]]:
        counts = named.groupby(["group", by]).size()
        return [
            {"group": str(group), by: (int(at) if by == "decade" else str(at)), "count": int(n)}
            for (group, at), n in counts.items()
        ]

    cells = sorted(sparse("decade"), key=lambda c: (cast(int, c["decade"]), str(c["group"])))
    by_actor = sorted(sparse("actor"), key=lambda c: (str(c["actor"]), str(c["group"])))
    return {
        "table": summary,
        "groups": group_rows,
        "decades": decade_rows,
        "cells": cells,
        "by_actor": by_actor,
    }
