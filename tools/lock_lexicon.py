"""Write config/lexicon.lock.json — the digests that hold `pattern_since` honest.

    python tools/lock_lexicon.py          # rewrite the lock
    python tools/lock_lexicon.py --check  # verify only; exits non-zero on a mismatch

`pattern_since` is a hand-written claim about a hand-written matching rule: it
says the version in which that term's `pattern` or `anchor` last changed, and it
is what lets a gold sample or a committed model run survive a version bump that
did not touch the term it is keyed to. Nothing inside `config/lexicon.yml` can
tell whether the claim survived the last edit, so an edited rule with a
forgotten bump would let `15_usage.py` aggregate a run enumerated from a regex
the file no longer holds.

The lock closes that: it records each pattern's SHA-256 and each term's anchor
beside the `pattern_since` they are declared to date from, and `lexicon.load()`
refuses a lexicon the lock no longer describes. A forgotten bump therefore fails
at 03 and in CI rather than validating stale artefacts. The anchor is recorded
literally rather than hashed with the pattern so that a lock diff says in words
which terms started or stopped requiring `genocid*` in the sentence.

The lock is **committed**, unlike
anything under `data/`: it is derived from a hand-edited config rather than from
the corpus, so it belongs to the same diff as the config it locks. This tool
touches neither the network nor the corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import console, lexicon, lexicon_lock
from lib.paths import LEXICON, LEXICON_LOCK, atomic_write_text, rel


def lock_for(lex: lexicon.Lexicon) -> dict[str, object]:
    """The lock this lexicon should have.

    Every term, the disabled ones included: a held-back pattern is still what
    the OCR delta is measured with, and a lock that skipped it would let it
    change unrecorded. Keys sorted so the file diffs by term.
    """
    anchor = lex.anchor
    assert anchor is not None
    return {
        "version": lex.version,
        "anchor": {
            "pattern_sha256": lexicon_lock.pattern_sha256(anchor.pattern),
            "widened_since": anchor.widened_since,
        },
        "terms": {
            name: {
                "pattern_since": term.pattern_since,
                "widened_since": term.widened_since,
                "pattern_sha256": lexicon_lock.pattern_sha256(term.pattern),
                "anchor": term.anchor,
            }
            for name, term in sorted(lex.terms.items())
        },
    }


def read_lock() -> dict[str, object]:
    """The committed lock, or an empty mapping when there is none yet."""
    if not LEXICON_LOCK.exists():
        return {}
    return json.loads(LEXICON_LOCK.read_text(encoding="utf-8"))


def unbumped(lex: lexicon.Lexicon, old: dict[str, object]) -> list[str]:
    """Terms whose matching rule moved since `old` without their `pattern_since`.

    The rule is the pattern and the anchor together: an anchored term counts
    strictly fewer occurrences than its pattern matches, so anchoring one
    invalidates an artefact keyed to it exactly as a regex edit would, and the
    lock has to catch both. A term the old lock does not hold is a new term, and
    a new rule is a changed rule. Writing the lock for either without the bump
    would record the forgetting rather than catch it, which is the one thing
    this file is for.
    """
    entries = old.get("terms")
    entries = entries if isinstance(entries, dict) else {}
    stale = []
    for name, term in lex.terms.items():
        entry = entries.get(name)
        digest = lexicon_lock.pattern_sha256(term.pattern)
        anchored_changed = not isinstance(entry, dict) or entry.get("anchor") != term.anchor
        pattern_changed = not isinstance(entry, dict) or entry.get("pattern_sha256") != digest
        # A pattern edit may be dated either way — as a new rule, or as a
        # declared widening that 03 then verifies on the corpus. Anchoring or
        # unanchoring a term is always a new rule.
        new_rule = anchored_changed and term.pattern_since != lex.version
        undated = pattern_changed and lex.version not in (term.pattern_since, term.widened_since)
        if new_rule or undated:
            stale.append(name)
    anchor = lex.anchor
    locked = old.get("anchor")
    if anchor is not None and isinstance(locked, dict):
        anchored = [term for term in lex.terms.values() if term.anchor is not None]
        moved = locked.get("pattern_sha256") != lexicon_lock.pattern_sha256(anchor.pattern)
        if moved and anchor.widened_since != lex.version and any(
            term.pattern_since != lex.version for term in anchored
        ):
            stale.append("anchor")
    return sorted(stale)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed lock against config/lexicon.yml and write nothing",
    )
    args = parser.parse_args()

    # Without the check, since this is the tool that repairs what it checks.
    lex = lexicon.load(check_lock=False)
    console.step("Read the lexicon")
    console.info(f"version {lex.version} ({lex.updated}), {len(lex.terms)} terms")

    if args.check:
        if not LEXICON_LOCK.exists():
            console.fail(
                f"{rel(LEXICON_LOCK)} is missing",
                ["run `python tools/lock_lexicon.py` to write it"],
            )
        try:
            lexicon_lock.check_lock(lex.terms, lex.version, read_lock(), lex.anchor)
        except ValueError as exc:
            console.fail(f"{rel(LEXICON_LOCK)} does not describe {rel(LEXICON)}", [str(exc)])
        console.step("The lock matches the lexicon")
        return

    old = read_lock()
    if old:
        if stale := unbumped(lex, old):
            console.fail(
                "these matching rules changed without their pattern_since or widened_since",
                [
                    f"'{name}': set pattern_since to {lex.version} in {rel(LEXICON)}, or "
                    f"widened_since to {lex.version} with widened_from if it only adds matches"
                    for name in stale
                ],
            )
    else:
        console.warn(
            f"{rel(LEXICON_LOCK)} does not exist yet — recording the patterns as declared"
        )

    payload = json.dumps(lock_for(lex), ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(LEXICON_LOCK, payload)
    console.step("Wrote the lock")
    console.table(
        [
            ("file", rel(LEXICON_LOCK)),
            ("version", lex.version),
            ("terms", len(lex.terms)),
        ]
    )


if __name__ == "__main__":
    main()
