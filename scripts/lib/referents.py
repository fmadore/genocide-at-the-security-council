"""The controlled referent list, `annotations/lexicon/referents.csv`, read once.

Four readers used to parse this file, each with rules of its own: one checked
identifiers and versions, one filled in a missing `kind`, one accepted fewer
headers and gave a traceback on a version cell that was not a number. A file
two readers accepted differently said two things at once. Now :func:`read`
parses it into one :class:`ReferentFile`, every rule is applied to every
caller, and the callers take the view they need:

- :meth:`ReferentFile.current`, what the prompt renders and a new annotation
  may use (`lib.llm.read_referent_table`);
- :meth:`ReferentFile.listing`, the versions, retirements and successors that
  keep an older run readable (`lib.audit.read_referent_list`);
- :meth:`ReferentFile.published`, every row with the columns the usage view
  publishes, retired ones marked (`15_usage.py`).

A cell that breaks a rule raises :class:`ReferentFileError`, naming the file,
the row and the column. It is a `ValueError`, so a caller that already refused
on one keeps doing so.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .audit import DEFAULT_REFERENTS, ReferentList
from .paths import rel

#: Columns without which the file is not a referent list at all. The others
#: arrived later, and a file that has not grown them is read as what it meant
#: before they existed: version 1, nothing retired, `kind` from the reserved IDs.
REQUIRED = frozenset({"id", "label", "description"})

#: Columns the usage view publishes, all of which it requires.
PUBLISHED = frozenset(
    {"id", "label", "description", "kind", "iso3", "years", "since", "retired_in", "superseded_by"}
)


class ReferentFileError(ValueError):
    """`referents.csv` breaks a rule of the controlled list."""


@dataclass(frozen=True)
class Referent:
    """One row of the file, with every rule applied."""

    id: str
    label: str
    description: str
    #: As declared, or for a blank cell `reserved` for the three reserved IDs
    #: and `case` otherwise, which is what the file meant before `kind` existed.
    kind: str
    iso3: str
    years: str
    #: The list version at which this identifier's meaning was last set.
    since: int
    #: The version at which it stopped being offered, or None while current.
    retired_in: int | None
    superseded_by: str

    @property
    def retired(self) -> bool:
        return self.retired_in is not None


@dataclass(frozen=True)
class ReferentFile:
    """Every row of the file, in file order, and the columns it carried."""

    path: Path
    rows: tuple[Referent, ...]
    columns: frozenset[str]

    @property
    def version(self) -> int:
        """The highest version any row mentions; see `lib.audit.ReferentList`."""
        return max(
            [*(row.since for row in self.rows), *(row.retired_in or 0 for row in self.rows), 1]
        )

    @property
    def since(self) -> Mapping[str, int]:
        return {row.id: row.since for row in self.rows}

    @property
    def retired_in(self) -> Mapping[str, int]:
        return {row.id: row.retired_in for row in self.rows if row.retired_in is not None}

    @property
    def superseded_by(self) -> Mapping[str, str]:
        return {row.id: row.superseded_by for row in self.rows if row.superseded_by}

    def current(self) -> list[Referent]:
        """The rows a new annotation may use and the prompt renders."""
        return [row for row in self.rows if not row.retired]

    def listing(self) -> ReferentList:
        """The versions, retirements and successors that keep an older run readable."""
        return ReferentList(
            version=self.version,
            since=self.since,
            retired_in=self.retired_in,
            superseded_by=self.superseded_by,
        )

    def published(self) -> list[dict[str, object]]:
        """Every row, retired ones marked, as the usage view publishes it.

        Retired rows are kept: a run made before a retirement counted rows under
        the old identifier, and the view has to know that an empty column is a
        withdrawn category rather than a case no delegation raised.
        """
        if missing := sorted(PUBLISHED - self.columns):
            raise ReferentFileError(f"{rel(self.path)} is missing columns: {', '.join(missing)}")
        return [
            {
                "id": row.id,
                "label": row.label,
                "description": row.description,
                "kind": row.kind,
                "iso3": row.iso3,
                "years": row.years,
                "since": row.since,
                "retired_in": row.retired_in,
                "retired": row.retired,
                "superseded_by": row.superseded_by,
            }
            for row in self.rows
        ]


def read(path: Path) -> ReferentFile:
    """Parse the file and hold it to every rule of the controlled list.

    The identifier checks are here because every reader depends on them: an
    identifier with surrounding whitespace, a blank one or a duplicate would
    each fragment one referent into two silently, which is the failure the
    controlled list exists to prevent.
    """
    table = pd.read_csv(path, dtype="string", keep_default_na=False)
    where = rel(path)
    if missing := sorted(REQUIRED - set(table.columns)):
        raise ReferentFileError(f"Referent file is missing columns: {', '.join(missing)} ({where})")
    identifiers = table["id"].astype(str)
    if identifiers.str.strip().ne(identifiers).any():
        raise ReferentFileError(f"Referent IDs must not contain surrounding whitespace. ({where})")
    if identifiers.eq("").any() or identifiers.duplicated().any():
        raise ReferentFileError(f"Referent IDs must be nonempty and unique. ({where})")
    if missing_defaults := sorted(DEFAULT_REFERENTS - set(identifiers)):
        raise ReferentFileError(
            f"Referent file is missing reserved IDs: {', '.join(missing_defaults)} ({where})"
        )

    rows = []
    for values in table.to_dict(orient="records"):
        name = str(values["id"])
        since = _version_cell(values.get("since"), name, "since", where, default=1)
        retired = _version_cell(values.get("retired_in"), name, "retired_in", where, default=0)
        rows.append(
            Referent(
                id=name,
                label=str(values["label"]),
                description=str(values["description"]),
                kind=str(values.get("kind") or "")
                or ("reserved" if name in DEFAULT_REFERENTS else "case"),
                iso3=str(values.get("iso3") or ""),
                years=str(values.get("years") or ""),
                since=since,
                retired_in=retired or None,
                superseded_by=str(values.get("superseded_by") or "").strip(),
            )
        )
    parsed = ReferentFile(path=path, rows=tuple(rows), columns=frozenset(table.columns))

    successors = parsed.superseded_by
    if unknown := sorted(set(successors.values()) - set(parsed.since)):
        raise ReferentFileError(
            "Referent file supersedes IDs onto ones it does not hold: "
            f"{', '.join(unknown)} ({where})"
        )
    if stranded := sorted(name for name in successors if name not in parsed.retired_in):
        raise ReferentFileError(
            "Referent file names a successor for IDs it has not retired: "
            f"{', '.join(stranded)} ({where})"
        )
    return parsed


def _version_cell(value: object, name: str, column: str, where: str, *, default: int) -> int:
    """One version number from the file, or the default an empty cell means."""
    text = str(value or "").strip()
    if not text:
        return default
    if not text.isdigit() or int(text) < 1:
        raise ReferentFileError(f"Referent '{name}' has a non-numeric {column}: {text} ({where})")
    return int(text)
