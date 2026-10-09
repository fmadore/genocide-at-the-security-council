"""The lexicon's two committed records: the pattern lock and the counts.

`config/lexicon.lock.json` pins each term's pattern, and the anchor's, to the
version it is declared to date from, so a pattern edited without its
`pattern_since` is refused when the lexicon is loaded. `config/lexicon.counts.json`
holds what each enabled term counts on the pinned corpus: 03 refuses a count
that differs, and 13, 14 and 15 read their population from it. The lock is
written by `tools/lock_lexicon.py` and the counts by `03_lexicon.py
--update-counts`; this module reads both and says where the lexicon or the
corpus no longer agrees with them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from .paths import LEXICON, LEXICON_COUNTS, LEXICON_LOCK, rel

if TYPE_CHECKING:
    import pandas as pd

    from .lexicon import Anchor, Lexicon, Term


def pattern_sha256(pattern: str) -> str:
    """The digest the lock pins a term's pattern by.

    One helper for the check and for the tool that writes the lock, so the two
    can never disagree about what was hashed.
    """
    return hashlib.sha256(pattern.encode("utf-8")).hexdigest()


def check_lock(
    terms: Mapping[str, Term],
    version: int,
    lock: Mapping[str, object],
    anchor: Anchor | None = None,
) -> None:
    """Refuse a lexicon the committed lock no longer describes.

    `pattern_since` is a hand-written claim about a hand-written matching rule,
    and nothing inside the file can tell whether the claim survived the last
    edit. The lock records each pattern's digest — and, since v4, the anchor
    beside it — against the version the rule is declared to date from, so
    editing either without bumping `pattern_since` fails here, at 03 and in CI,
    instead of letting `15_usage.py` aggregate a run enumerated from a rule the
    file no longer holds. The anchor is recorded literally rather than folded
    into the digest so that a lock diff says which terms changed register-
    critical behaviour and which changed a regex. Rewrite the lock with
    `python tools/lock_lexicon.py`.
    """
    locked_version = lock.get("version")
    if isinstance(locked_version, bool) or not isinstance(locked_version, int):
        raise ValueError(
            f"{rel(LEXICON_LOCK)} has no integer 'version': {locked_version!r}; "
            "run `python tools/lock_lexicon.py`"
        )
    if locked_version != version:
        raise ValueError(
            f"{rel(LEXICON_LOCK)} locks lexicon version {locked_version}, but "
            f"{rel(LEXICON)} is version {version}; run `python tools/lock_lexicon.py`"
        )

    entries = lock.get("terms")
    if not isinstance(entries, Mapping):
        raise ValueError(
            f"{rel(LEXICON_LOCK)} has no 'terms' table; run `python tools/lock_lexicon.py`"
        )
    # Every term, the disabled ones included: a held-back pattern is still what
    # the OCR delta is measured with.
    missing = sorted(set(terms) - set(entries))
    if missing:
        raise ValueError(
            f"{rel(LEXICON_LOCK)} does not lock {missing}; run `python tools/lock_lexicon.py`"
        )
    unknown = sorted(set(entries) - set(terms))
    if unknown:
        raise ValueError(
            f"{rel(LEXICON_LOCK)} locks {unknown}, which {rel(LEXICON)} no longer "
            "defines; run `python tools/lock_lexicon.py`"
        )

    if anchor is not None:
        locked_anchor = lock.get("anchor")
        if not isinstance(locked_anchor, Mapping):
            raise ValueError(
                f"{rel(LEXICON_LOCK)} does not lock the anchor; run "
                "`python tools/lock_lexicon.py`"
            )
        if locked_anchor.get("pattern_sha256") != pattern_sha256(anchor.pattern):
            raise ValueError(
                f"{rel(LEXICON)}: the anchor pattern changed, which changes what every "
                f"anchored term counts: declare it widened_since {version} with the old "
                f"pattern as widened_from, or set every anchored term's pattern_since to "
                f"{version}, and run `python tools/lock_lexicon.py`"
            )
        if locked_anchor.get("widened_since") != anchor.widened_since:
            raise ValueError(
                f"{rel(LEXICON)}: the anchor declares widened_since {anchor.widened_since}, "
                f"{rel(LEXICON_LOCK)} records {locked_anchor.get('widened_since')!r}; run "
                "`python tools/lock_lexicon.py`"
            )

    for name, term in terms.items():
        entry = entries[name]
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"{rel(LEXICON_LOCK)}: the entry for '{name}' is not a table: {entry!r}; "
                "run `python tools/lock_lexicon.py`"
            )
        if entry.get("pattern_sha256") != pattern_sha256(term.pattern):
            raise ValueError(
                f"{rel(LEXICON)}: the pattern of '{name}' changed: set its pattern_since "
                f"to {version} — or, for a change that only adds matches, its "
                f"widened_since to {version} with the old pattern as widened_from — "
                "and run `python tools/lock_lexicon.py`"
            )
        if entry.get("widened_since") != term.widened_since:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' declares widened_since "
                f"{term.widened_since}, {rel(LEXICON_LOCK)} records "
                f"{entry.get('widened_since')!r}; run `python tools/lock_lexicon.py`"
            )
        if entry.get("anchor") != term.anchor:
            raise ValueError(
                f"{rel(LEXICON)}: the anchor of '{name}' changed from "
                f"{entry.get('anchor')!r} to {term.anchor!r}, which changes what it "
                f"counts as surely as a pattern edit: set its pattern_since to "
                f"{version} and run `python tools/lock_lexicon.py`"
            )
        if entry.get("pattern_since") != term.pattern_since:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' declares pattern_since "
                f"{term.pattern_since}, {rel(LEXICON_LOCK)} records "
                f"{entry.get('pattern_since')!r}; the pattern itself has not changed, so "
                "run `python tools/lock_lexicon.py` once the declaration is the one you want"
            )


def _check_committed_lock(terms: Mapping[str, Term], version: int, anchor: Anchor) -> None:
    """Read the committed lock and hold `terms` to it.

    Separate from `check_lock` only because `load`'s keyword of that name
    shadows it inside `load`; the check itself stays a pure function of values.
    """
    if not LEXICON_LOCK.exists():
        raise FileNotFoundError(
            f"{rel(LEXICON_LOCK)} is missing — it is committed beside "
            f"{rel(LEXICON)}; run `python tools/lock_lexicon.py` to write it"
        )
    check_lock(terms, version, json.loads(LEXICON_LOCK.read_text(encoding="utf-8")), anchor)


# --- Committed counts -------------------------------------------------------


def counts_record(counts: pd.DataFrame, lex: Lexicon, speeches: int) -> dict[str, object]:
    """What `config/lexicon.counts.json` should say for these counts.

    One entry per enabled term and derived measure, in name order so the file
    diffs by term. The corpus size is recorded beside them because a count is
    only a count of something.
    """
    # Imported here: `lib.lexicon` imports this module to check the lock as it
    # loads, so a module-level import of it would be circular.
    from .lexicon import COUNT, HAS

    names = sorted([term.name for term in lex.active] + list(lex.derived))
    return {
        "lexicon_version": lex.version,
        "speeches": int(speeches),
        "terms": {
            name: {
                "speeches": int(counts[f"{HAS}{name}"].sum()),
                "occurrences": int(counts[f"{COUNT}{name}"].sum()),
            }
            for name in names
        },
    }


def load_counts(path: Path = LEXICON_COUNTS) -> dict[str, object]:
    """The committed counts, refusing a file that is missing or malformed."""
    if not path.exists():
        raise FileNotFoundError(
            f"{rel(path)} is missing — run `python scripts/03_lexicon.py --update-counts` "
            "on the pinned corpus and commit it"
        )
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or not isinstance(record.get("terms"), dict):
        raise ValueError(f"{rel(path)} has no 'terms' table")
    return record


def count_problems(record: Mapping[str, object], committed: Mapping[str, object]) -> list[str]:
    """Every way the measured counts differ from the committed ones.

    The version is not compared: a release that edited no pattern moves no
    count, and holding it to a rewrite would make every note edit a corpus run.
    What is compared is what a published number depends on — the corpus size
    and each term's two counts — and a term present on one side only.
    """
    problems = []
    if record.get("speeches") != committed.get("speeches"):
        problems.append(
            f"corpus of {record.get('speeches')!r} speeches; the committed counts describe "
            f"{committed.get('speeches')!r}"
        )
    measured = record.get("terms", {})
    locked = committed.get("terms", {})
    assert isinstance(measured, Mapping) and isinstance(locked, Mapping)
    for name in sorted(set(measured) | set(locked)):
        if name not in locked:
            problems.append(f"'{name}' is counted but not committed")
        elif name not in measured:
            problems.append(f"'{name}' is committed but no longer counted")
        elif measured[name] != locked[name]:
            now, then = measured[name], locked[name]
            problems.append(
                f"'{name}': {now['speeches']:,} speeches / {now['occurrences']:,} "
                f"occurrences, committed {then['speeches']:,} / {then['occurrences']:,}"
            )
    return problems


def population(term: str, path: Path = LEXICON_COUNTS) -> tuple[int, int]:
    """`(speeches, occurrences)` the committed counts give `term`.

    What 13, 14 and 15 hold their enumeration to. They used to carry the two
    numbers as constants of their own, four copies that a lexicon change had to
    find by hand.
    """
    terms = load_counts(path)["terms"]
    entry = terms.get(term) if isinstance(terms, Mapping) else None
    if not isinstance(entry, Mapping):
        raise ValueError(f"{rel(path)} holds no counts for '{term}'")
    return int(entry["speeches"]), int(entry["occurrences"])
