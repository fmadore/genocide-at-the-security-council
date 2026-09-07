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
exists, whether every collection member carries it, where it is nested, and
what kind of value it held. It says nothing about ranges, alignment between
arrays, or any of the substantive refusals `web/src/lib/data.ts` makes — those
stay where they are, at the boundary, where a reader can be told about them.
What this catches is the failure that was silent: a field that moved, was
renamed, stopped being written, or became absent from some rows.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

#: Artefacts the dashboard fetches, as paths under `web/static/data/`.
#:
#: `speeches/` is represented by one document rather than by all 9,464: they are
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
    # Both of 15's artefacts, not one representative. They are written by the
    # same step but not by the same loop: `usage.json` is nine hand-built blocks
    # and `occurrences.json` is a flat row set, so neither one's shape says
    # anything about the other's.
    "usage/usage.json",
    "usage/occurrences.json",
    # 17's summary, but not its `occurrences.json`. That file ships — the export
    # copies a directory wholesale, and a reader who downloads the payload should
    # be able to check the table row by row — and no figure fetches it. The
    # dashboard's half of this contract (`web/src/lib/contract.test.ts`) refuses
    # an artefact tracked here that nothing reads, and it is right to: a shape
    # promised to no consumer is a promise nobody can break.
    "frames/frames.json",
    "kwic/index.json",
    "kwic/genocide.json",
    "meetings.json",
    "scopes.json",
]

#: A representative document from `speeches/`, chosen by name rather than by
#: position so the contract does not silently follow a change in sort order.
SPEECH_SAMPLE = "speeches/SC00001-01.json"

#: Keys whose *contents* vary with the data rather than with the code, so only
#: their presence and type are contracted. `iso3_collisions` is keyed on whichever
#: codes happen to be shared; `terms`, `measures`, `series` and speech `hits` are
#: keyed on the lexicon; `packages` on whatever the environment had installed.
#: Recording today's key set would make an ordinary lexicon edit look like a
#: breaking change, and the point of this file is to be believed when it fails.
#:
#: Their members are folded into one shape by :func:`merge`. Fields shared by
#: every member remain required; fields carried by only some are marked optional.
#: This lets a measure legitimately omit an occurrence count while still catching
#: a required row field that disappeared from one member.
OPAQUE: frozenset[str] = frozenset(
    {
        "by_period",
        "hits",
        "iso3_collisions",
        "measures",
        "packages",
        "series",
        "terms",
    }
)

#: Keys that would carry a measure summed or unioned over more than one lexicon
#: term. R7 removed every one of them: a count of *the legal register* is a count
#: of a category `config/lexicon.yml` invented, published as though it were a
#: property of the corpus, and a reader watching the line move cannot tell which
#: of six words moved it. The site publishes one measure per term and the reader
#: composes the group.
#:
#: Checked by name rather than by arithmetic, because the arithmetic is gone: no
#: step computes these any more, so what this catches is one being reintroduced
#: — by a revived `sets:` block, a resurrected roll-up, or a hand-written block
#: in a later step that reaches for the same convenience.
ROLL_UP_PREFIXES: tuple[str, ...] = ("has_register_", "n_register_", "has_set_")
ROLL_UP_KEYS: frozenset[str] = frozenset(
    {"n_lexicon_total", "n_lexicon_terms", "registers", "sets"}
)

#: Values of a measure's `kind` that would name a group of terms rather than one
#: term, and the attribute a grouped measure carried its membership in.
ROLL_UP_KINDS: frozenset[str] = frozenset({"registers", "sets", "register", "set"})
MEMBERS = "members"

#: The one block where naming several terms is the point rather than the fault.
#: R8's `corpora` holds *populations*: a speech belongs to one or it does not,
#: it enters once however many of the named phrases it uses, and the names are
#: published precisely so a reader can see what the predicate was. R9's reading
#: sets are the same object under a different name. Everything else that lists
#: the terms it stands for is a measure standing for several of them.
POPULATIONS = "corpora"

#: The single key an opaque block is reduced to. No artefact writes a field of
#: this name, and `differences` treats it as an ordinary key: both sides of a
#: comparison have already been folded, so it is compared merge against merge.
MEMBER = "*"

#: A suffix on a skeleton key means that the JSON field is absent from at least
#: one member of the collection that was merged. JSON keys in this project's
#: payload do not end in `?`; using a suffix keeps the committed contract compact
#: and human-readable instead of wrapping every field in schema machinery.
OPTIONAL = "?"


def _field(key: str) -> tuple[str, bool]:
    """The JSON key and whether its skeleton key is optional."""
    if key.endswith(OPTIONAL):
        return key[: -len(OPTIONAL)], True
    return key, False


def _fields(shape: dict[str, Any]) -> dict[str, tuple[bool, Any]]:
    """A skeleton object keyed by the JSON field rather than its marker."""
    fields = {}
    for key, value in shape.items():
        name, optional = _field(key)
        fields[name] = (optional, value)
    return fields


def skeleton(value: Any, *, key: str | None = None) -> Any:
    """A payload reduced to its shape.

    Objects become their keys, sorted, mapped to the skeleton of each value.
    Arrays become a single-element list holding the *merged* skeleton of every
    element. A field absent from at least one merged member gains a `?` suffix,
    so a ragged array is visible rather than hidden behind whichever member
    happened to carry the field. Everything else becomes the name of its type.

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

    A field present in some elements and absent from others is kept but marked
    optional. Optionality already found by an inner merge is preserved by outer
    merges. Two different leaf types at one path are reported as both, which is
    how a nullable number stays legible as `float|null` rather than collapsing
    to whichever element came first.
    """
    if not shapes:
        return {}
    if all(isinstance(shape, dict) for shape in shapes):
        members = [_fields(shape) for shape in shapes]
        keys = {key for member in members for key in member}
        merged = {}
        for key in sorted(keys):
            present = [member[key] for member in members if key in member]
            required = len(present) == len(members) and not any(optional for optional, _ in present)
            output_key = key if required else f"{key}{OPTIONAL}"
            merged[output_key] = merge([value for _, value in present])
        return merged
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
        promised_fields = _fields(promised)
        found_fields = _fields(found)
        for key, (optional, expected) in promised_fields.items():
            if key not in found_fields:
                if not optional:
                    yield f"{where}.{key}: missing"
                continue
            found_optional, value = found_fields[key]
            if not optional and found_optional:
                yield f"{where}.{key}: required field is absent from some members"
            yield from differences(expected, value, f"{path}.{key}")
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


def roll_ups(document: Any, path: str = "", *, population: bool = False) -> Iterator[str]:
    """Every place in one parsed artefact that sums or unions several terms.

    A pure walk over the parsed JSON, so the rule can be tested on a document
    written by hand and enforced on the real payload by the same code.

    Three shapes are refused, because a roll-up can come back in three ways: a
    column carried through from `03` (`n_register_legal`, `has_set_rome_triad`,
    the lexicon totals), a block of them keyed by group (`registers`, `sets`),
    and a measure that describes itself as a group — `kind: "sets"`, or a
    `members` list naming the terms it stands for.

    What it deliberately does *not* refuse is a **population**: R8's
    genocide-free atrocity corpus and R9's three reading sets each hold speeches
    selected by a predicate over several terms, and a speech enters once however
    many of those terms it uses. That is a statement about which speeches a view
    may read, not a number added up across categories nobody can see, and the
    difference is the whole of R7.
    """
    if isinstance(document, dict):
        for key, value in document.items():
            where = f"{path}.{key}" if path else key
            inside = population or key == POPULATIONS
            if key in ROLL_UP_KEYS or key.startswith(ROLL_UP_PREFIXES):
                yield f"{where} is a measure over more than one term"
            elif key == "kind" and isinstance(value, str) and value in ROLL_UP_KINDS:
                yield f"{where} declares the measure a group of terms: {value!r}"
            elif key == MEMBERS and isinstance(value, list) and len(value) > 1 and not inside:
                yield f"{where} names {len(value)} terms one measure stands for"
            else:
                yield from roll_ups(value, where, population=inside)
    elif isinstance(document, list):
        for index, item in enumerate(document):
            yield from roll_ups(item, f"{path}[{index}]", population=population)


def aggregates(root: Path) -> list[str]:
    """Every roll-up in a built payload, artefact by artefact.

    Run at the export seam beside :func:`check`, and for the same reason: the
    shape check would pass a `registers` block happily, because a reintroduced
    aggregate is a well-formed object and not a malformed one. This is the check
    that says the payload publishes no measure whose movement a reader cannot
    attribute to a word.
    """
    found: list[str] = []
    for relative in [*TRACKED, SPEECH_SAMPLE]:
        path = root / relative
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        found.extend(f"{relative} {line}" for line in roll_ups(document))
    return found


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
