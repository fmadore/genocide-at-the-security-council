"""The shape the dashboard is promised, and whether the payload still has it.

`web/src/lib/types.ts` says of itself that it is "hand-kept in step with
`scripts/`", and that if a field there is wrong "the failure is a blank chart,
not an error". That is an honest description of a real gap: the artefact
contract is written three times — once by the Python that emits the JSON, once
by the TypeScript that declares its type, once by the validators at the fetch
boundary — and nothing joined them. A renamed field passed `pytest`, passed
`svelte-check`, and was discovered by a reader looking at an empty figure.

This module is the join. It reduces a payload to its *skeleton* — the keys, the
nesting, and the type at each leaf, with the data thrown away — and compares one
skeleton against another. `tests/contract/payload.json` holds the committed
skeleton of everything the dashboard fetches; `export_web.py` checks the payload
it is about to hand over against it and refuses to publish a shape the
application was not written for.

A skeleton is not a schema and does not pretend to be one. It says a field
exists, is nested where it was, and still holds the kind of value it held. It
says nothing about ranges, alignment between arrays, or any of the substantive
refusals `web/src/lib/data.ts` makes — those stay where they are, at the
boundary, where a reader can be told about them. What this catches is the
failure that was silent: a field that moved, was renamed, or stopped being
written at all.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

#: Artefacts the dashboard fetches, as paths under `web/static/data/`.
#:
#: `speeches/` is represented by one document rather than by all 6,595: they are
#: written by one loop in `09_export_speeches.py`, so a shape change reaches
#: every one of them, and parsing 425 MB to learn that twice over would make the
#: export slower for no extra finding. The same argument does not apply to
#: `kwic/`, where each term is a separate file, but the shape is likewise one
#: writer's, so one representative term is checked.
TRACKED: list[str] = [
    "series/annual.json",
    "series/quarterly.json",
    "series/monthly.json",
    "series/breakdowns.json",
    "series/change_points.json",
    "series/events.json",
    "lexical/collocates.json",
    "lexical/collocates_sliced.json",
    "lexical/keyness.json",
    "lexical/network.json",
    "countries/countries.json",
    "countries/speaker_keyness.json",
    "kwic/index.json",
    "kwic/genocide.json",
    "meetings.json",
]

#: A representative document from `speeches/`, chosen by name rather than by
#: position so the contract does not silently follow a change in sort order.
SPEECH_SAMPLE = "speeches/UNSC_1992_SPV.3137.json"

#: Keys whose *contents* vary with the data rather than with the code, so only
#: their presence and type are contracted. `iso3_collisions` is keyed on whichever
#: codes happen to be shared; `terms`, `registers`, `sets`, `measures` and
#: `series` are keyed on the lexicon; `packages` on whatever the environment had
#: installed. Recording today's key set would make an ordinary lexicon edit look
#: like a breaking change, and the point of this file is to be believed when it
#: fails.
#:
#: Their members are folded into one shape by :func:`merge`, so what is
#: contracted is the union of the fields any member carries. A measure that drops
#: a field while another keeps it therefore passes — the alternative fails on
#: every lexicon edit — and a field that stops being written *anywhere* is caught,
#: which is the change that silently blanks a figure.
OPAQUE: frozenset[str] = frozenset(
    {
        "by_period",
        "iso3_collisions",
        "measures",
        "packages",
        "registers",
        "series",
        "sets",
        "terms",
    }
)

#: The single key an opaque block is reduced to. No artefact writes a field of
#: this name, and `differences` treats it as an ordinary key: both sides of a
#: comparison have already been folded, so it is compared merge against merge.
MEMBER = "*"


def skeleton(value: Any, *, key: str | None = None) -> Any:
    """A payload reduced to its shape.

    Objects become their keys, sorted, mapped to the skeleton of each value.
    Arrays become a single-element list holding the *merged* skeleton of every
    element, so a ragged array is visible rather than hidden behind whichever
    element happened to be first. Everything else becomes the name of its type.

    A key listed in :data:`OPAQUE` keeps one representative value's shape rather
    than its own key set, because its keys are data.
    """
    if isinstance(value, dict):
        if key in OPAQUE:
            # The keys are the lexicon's, not the code's. Contract one member's
            # shape — every member is written by the same loop — and nothing
            # about which members exist.
            members = [skeleton(item) for item in value.values()]
            return {MEMBER: merge(members)} if members else {}
        return {name: skeleton(item, key=name) for name, item in sorted(value.items())}
    if isinstance(value, list):
        return [merge([skeleton(item) for item in value])] if value else []
    if value is None:
        # Null is a value the artefacts use deliberately — a withheld rate — so
        # it is not a type of its own here. `merge` folds it into whatever the
        # other elements carry, and a column that is null throughout stays null.
        return "null"
    return type(value).__name__


def merge(shapes: list[Any]) -> Any:
    """One shape covering every element of an array.

    A field present in some elements and absent from others is kept: the union
    is what the consumer has to be able to read. Two different leaf types at one
    path are reported as both, which is how a nullable number stays legible as
    `float|null` rather than collapsing to whichever element came first.
    """
    if not shapes:
        return {}
    if all(isinstance(shape, dict) for shape in shapes):
        keys = {key for shape in shapes for key in shape}
        return {key: merge([shape[key] for shape in shapes if key in shape]) for key in sorted(keys)}
    if all(isinstance(shape, list) for shape in shapes):
        inner = [item for shape in shapes for item in shape]
        return [merge(inner)] if inner else []
    leaves = {shape for shape in shapes if isinstance(shape, str)}
    if len(shapes) != len(leaves):
        # A mix of leaves and containers. Say so rather than picking one: it is
        # a shape no consumer can be written against.
        return "|".join(sorted({s if isinstance(s, str) else "object" for s in shapes}))
    return "|".join(sorted(leaves))


def _leaf_covers(promised: str, found: str) -> bool:
    """Whether a leaf still carries what was promised.

    Read as a set of the types a path may hold. `found` may be narrower — an
    artefact whose nullable column happens to have no nulls this run is not a
    breaking change — but it may not introduce a type nothing was written for.
    """
    return set(found.split("|")) <= set(promised.split("|"))


def differences(promised: Any, found: Any, path: str = "") -> Iterator[str]:
    """Every way `found` fails to carry what `promised` describes.

    Additions are not differences. The payload may grow a field the dashboard
    does not read yet — that is how every feature here has started — and a check
    that failed on it would be turned off within a week. What is reported is
    what was taken away, moved, or changed underfoot.
    """
    where = path or "(root)"
    if isinstance(promised, dict):
        if not isinstance(found, dict):
            yield f"{where}: expected an object, found {_name(found)}"
            return
        for key, expected in promised.items():
            if key not in found:
                yield f"{where}.{key}: missing"
                continue
            yield from differences(expected, found[key], f"{path}.{key}")
        return
    if isinstance(promised, list):
        if not isinstance(found, list):
            yield f"{where}: expected an array, found {_name(found)}"
            return
        if promised and found:
            yield from differences(promised[0], found[0], f"{path}[]")
        return
    if isinstance(found, (dict, list)):
        yield f"{where}: expected {promised}, found {_name(found)}"
        return
    if not _leaf_covers(promised, found):
        yield f"{where}: expected {promised}, found {found}"


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, list):
        return "an array"
    return str(value)


def payload_skeleton(root: Path) -> dict[str, Any]:
    """The skeleton of every tracked artefact under a built payload directory."""
    shapes: dict[str, Any] = {}
    for relative in [*TRACKED, SPEECH_SAMPLE]:
        path = root / relative
        if not path.exists():
            continue
        shapes[relative] = skeleton(json.loads(path.read_text(encoding="utf-8")))
    return shapes


def check(root: Path, promised: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Compare a built payload against a committed contract.

    Returns the problems and the artefacts that could not be read. An absent
    artefact is not a shape failure — `export_web.py` already refuses a payload
    with a missing part, and saying it twice in different words helps nobody.
    """
    problems: list[str] = []
    absent: list[str] = []
    for relative, expected in promised.items():
        path = root / relative
        if not path.exists():
            absent.append(relative)
            continue
        found = skeleton(json.loads(path.read_text(encoding="utf-8")))
        problems.extend(f"{relative} {line}" for line in differences(expected, found))
    return problems, absent
