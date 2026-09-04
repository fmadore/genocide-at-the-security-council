"""The genocide lexicon: load, compile, count.

`config/lexicon.yml` is a hypothesis about what "discussing genocide" looks
like in a verbatim record, not a ground truth. This module keeps it honest:

- every term carries its own `tier` and `register`, so a count can always be
  traced back to the discursive family it belongs to;
- terms marked ``enabled: false`` — the OCR-tolerant net — are compiled and
  measured but kept out of the headline columns, so their contribution is
  reported as a delta rather than folded silently into the total;
- the lexicon's version is recorded in the output, because changing this file
  changes every downstream number;
- a term may be *anchored* to the sentence, and then it is counted only where
  the sentence holding it also says `genocid*`. The review of 1 September 2026
  (§3.4) found the commemorative register tracking UN anniversaries — of
  resolution 1325, of independence days — rather than genocide memory, and
  `survivors` tracking the women-and-peace-and-security agenda. The anchor is
  what separates a word this study is about from the same word doing another
  job elsewhere on the Council's agenda. It is declared per term in
  config/lexicon.yml, and the terms left unanchored there are the ones whose
  surface form is already specific to atrocity talk.

Counting runs against the speech *body* (form of address removed). Counting
against the raw text would inflate every country name and the word "President".
"""

from __future__ import annotations

import bisect
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import pandas as pd
import yaml

from . import text as text_lib
from .paths import LEXICON, LEXICON_LOCK, rel

#: Column prefixes. ``has_x`` is a boolean, ``n_x`` the occurrence count.
HAS = "has_"
COUNT = "n_"

#: What an anchored term must find beside itself. Deliberately the broad
#: `genocid*` of lexicon v2 rather than v4's narrowed `genocide` pattern: the
#: anchor asks whether the sentence is about genocide at all, and a sentence
#: naming the *génocidaires* is, so excluding the actor label here would be
#: reading the anchor as a term rather than as a test of what is being talked
#: about.
ANCHOR_RE = re.compile(r"\bgenocid\w*", re.IGNORECASE)

#: The literal that lets :meth:`Term.count` skip a speech before segmenting it.
#: Every string :data:`ANCHOR_RE` matches contains it, on exactly the rule the
#: per-term prefilters are held to, so the fast path cannot lose an anchored
#: match — and segmentation runs on the three thousand speeches that say the
#: word rather than on all 167,642 speeches.
ANCHOR_PREFILTER = "genocid"

#: The anchors a term may declare. One for now, and its name is the unit:
#: `sentence` means the sentence holding a match must also match
#: :data:`ANCHOR_RE`. A closed set rather than a free string, because a
#: mistyped anchor would silently mean "none" and inflate a term's count
#: without changing anything a reader would look at twice.
ANCHORS = frozenset({"sentence"})


@dataclass(frozen=True)
class Term:
    """One lexicon entry."""

    name: str
    pattern: str
    tier: str
    register: str
    #: Lexicon version at which this term's *matching rule* last changed — its
    #: `pattern` or its `anchor`, because a reader of an occurrence cannot tell
    #: which of the two put it there. `load` requires it in the config; the
    #: default is for the hand-built terms in the tests.
    pattern_since: int = 1
    enabled: bool = True
    note: str = ""
    examples: tuple[str, ...] = ()
    prefilters: tuple[str, ...] = ()
    nested_under: str | None = None
    #: ``"sentence"`` to count only where the sentence holding a match also
    #: matches :data:`ANCHOR_RE`; ``None`` to count every match.
    anchor: str | None = None
    regex: re.Pattern[str] = field(compare=False, repr=False, default=None)  # type: ignore[assignment]

    def spans(self, source: str) -> list[tuple[int, int]]:
        """Every span of `source` this term counts, in reading order.

        The one place the term's whole matching rule is applied, so a count, a
        concordance line, a highlighted offset and an audit sample can never
        disagree about what was matched. Callers reach for this rather than for
        `regex.finditer`: an anchored term matches strictly fewer spans than its
        pattern does, and the difference is exactly the occurrences that belong
        to another agenda.

        A match is attributed to the sentence it *starts* in. No pattern here
        can straddle a full stop, so there is nothing to arbitrate.
        """
        matches = list(self.regex.finditer(source))
        if not matches or self.anchor is None:
            return [match.span() for match in matches]

        sentences = text_lib.sentence_spans(source)
        opens = [start for start, _ in sentences]
        # One search per sentence, however many matches it holds: the
        # commemorative terms cluster, and re-scanning the same sentence for
        # `genocid*` once per occurrence is the difference between one pass over
        # the corpus and several.
        anchored: dict[int, bool] = {}
        kept: list[tuple[int, int]] = []
        for match in matches:
            index = max(bisect.bisect_right(opens, match.start()) - 1, 0)
            start, end = sentences[index]
            found = anchored.get(index)
            if found is None:
                found = ANCHOR_RE.search(source, start, end) is not None
                anchored[index] = found
            if found:
                kept.append(match.span())
        return kept

    def count(self, texts: pd.Series) -> pd.Series:
        """Occurrences of this term in each text.

        The prefilters are a fast path and never a second filter: `load` refuses
        a literal that is not a whitespace-free ASCII token, and
        config/lexicon.yml requires every literal to appear in every string the
        pattern can match, so skipping a text that holds none of them cannot
        lose an occurrence — for the ASCII literals the loader requires. The
        fast path is `str.contains(case=False)`, which is upper-case
        containment, while the pattern runs under `re.IGNORECASE`; the two agree
        on ASCII and diverge outside it (`re.IGNORECASE` folds U+0130 "İ" to
        "i", upper-casing does not), which is why the loader insists.

        An anchored term takes :data:`ANCHOR_PREFILTER` as a further condition
        of the same kind: an anchored match needs `genocid*` in its sentence and
        therefore in its text, so requiring the literal cannot lose one, and it
        keeps sentence segmentation off the hundred thousand speeches that never
        say the word.
        """
        candidates = pd.Series(False, index=texts.index)
        for literal in self.prefilters:
            candidates |= texts.str.contains(literal, case=False, regex=False, na=False)
        if self.anchor is not None:
            candidates &= texts.str.contains(
                ANCHOR_PREFILTER, case=False, regex=False, na=False
            )
        counts = pd.Series(0, index=texts.index, dtype="int64")
        if candidates.any():
            sources = texts.loc[candidates]
            matched = pd.Series(
                [len(self.spans(source)) for source in sources],
                index=sources.index,
                dtype="int64",
            )
            counts.loc[candidates] = matched
        return counts


@dataclass(frozen=True)
class Derived:
    """A measure obtained by subtracting terms from a term, not by matching.

    It has no pattern, enumerates no occurrence and appears in no concordance.
    It exists because *what a figure should report* and *what an occurrence is*
    are different questions, and v4 needed to answer the first without touching
    the second: `genocide` folds the actor label `genocidaires` into the count
    of the word as event qualification, and narrowing its pattern to say so
    would have moved every occurrence identity in the corpus — invalidating the
    gold sample and four committed model runs — to move a published figure by
    half a per cent. Subtracting reports the same number and costs nothing.

    The subtraction is only sound where each subtrahend is `nested_under` the
    minuend *and* the two patterns partition it. `load` checks the nesting;
    nothing in a regex can check the partition, so `tests/test_config.py`
    asserts it on the forms the corpus holds and :func:`apply` refuses a
    negative result, which is what a broken partition looks like in the data.
    """

    name: str
    minuend: str
    subtrahends: tuple[str, ...]
    tier: str
    register: str
    note: str = ""


@dataclass(frozen=True)
class Lexicon:
    """The whole versioned lexicon."""

    version: int
    updated: str
    terms: dict[str, Term]
    sets: dict[str, list[str]]
    derived: dict[str, Derived] = field(default_factory=dict)

    @property
    def active(self) -> list[Term]:
        """Terms that contribute to the headline counts."""
        return [t for t in self.terms.values() if t.enabled]

    @property
    def disabled(self) -> list[Term]:
        """Terms measured and reported separately, never folded in."""
        return [t for t in self.terms.values() if not t.enabled]

    def compatible(self, term_name: str, version: int | str) -> bool:
        """Whether an artefact keyed to `term_name` at lexicon `version` still holds.

        True when `term_name` enumerates the same occurrences here as it did at
        `version`: neither its pattern nor its anchor has been edited since
        (`pattern_since <= version`) and `version` is not ahead of this
        lexicon. That is what lets
        a gold sample or a committed model run survive a version bump that
        edited other terms.

        It guarantees nothing else. Other terms' counts may have moved, any
        aggregate over the whole lexicon may have moved, and the artefact's own
        rows are still checked against this corpus row by row.
        """
        if term_name not in self.terms:
            raise ValueError(f"unknown lexicon term '{term_name}'")
        # A version is an integer or the digits an artefact recorded it as.
        # `int()` would take True for 1 and truncate 2.9, and `load` refuses a
        # bool in this field for the same reason: an unreadable version is not a
        # matching one, and guessing at one would let an artefact through on a
        # number nobody wrote.
        if isinstance(version, bool):
            return False
        if isinstance(version, int):
            recorded = version
        elif isinstance(version, str) and version.isascii() and version.isdigit():
            recorded = int(version)
        else:
            return False
        return self.terms[term_name].pattern_since <= recorded <= self.version

    def by_register(self) -> dict[str, list[Term]]:
        out: dict[str, list[Term]] = {}
        for term in self.active:
            out.setdefault(term.register, []).append(term)
        return out

    def by_tier(self) -> dict[str, list[Term]]:
        out: dict[str, list[Term]] = {}
        for term in self.active:
            out.setdefault(term.tier, []).append(term)
        return out


def summable(terms: Sequence[Term], table: Mapping[str, Term]) -> list[Term]:
    """The subset of ``terms`` that can be added into a single occurrence count.

    A nested term's matches lie inside its parent's — every "mass atrocity" is
    also an "atrocity", every "Genocide Convention" also a `genocid*` — so
    adding a child and its parent to one sum counts the same span twice. This
    drops each term with *any* ancestor summed alongside it, in the order given.
    A term whose ancestors are all absent from the list stays: nothing else in
    that sum covers it, which is why a child counts in full in its own register
    when its parent belongs to another.

    ``table`` is the whole lexicon's terms, and the chain is walked through it
    rather than through ``terms``: with A ← B ← C and B out of the sum — another
    register, or disabled — C still sits inside A, so looking only one level up
    would keep both and count C's spans twice.

    Nesting is declared in `config/lexicon.yml`, not proven span by span, and a
    few alternatives inside a nested pattern do not sit inside a parent match:
    `convention on the prevention and punishment` matches `genocide_convention`
    on its own, with the parent's `genocid*` following as a separate span
    ("...of the Crime of Genocide"), and `special adviser on the prevention`
    likewise for `prevention_of_genocide`. Treating every nested occurrence as
    already counted by the parent therefore undercounts those few mentions. That
    is the safer direction: the roll-up understates rather than inflates.
    """
    summed = {term.name for term in terms}

    def covered(term: Term) -> bool:
        """Whether an ancestor of `term` is summed alongside it."""
        seen = {term.name}
        parent = term.nested_under
        # `check_nesting` refuses a cycle, so this walk terminates on a loaded
        # lexicon; `seen` keeps a hand-built one from spinning forever here
        # rather than at the point that built it.
        while parent is not None and parent not in seen:
            if parent in summed:
                return True
            seen.add(parent)
            parent = table[parent].nested_under if parent in table else None
        return False

    return [term for term in terms if not covered(term)]


def pattern_sha256(pattern: str) -> str:
    """The digest the lock pins a term's pattern by.

    One helper for the check and for the tool that writes the lock, so the two
    can never disagree about what was hashed.
    """
    return hashlib.sha256(pattern.encode("utf-8")).hexdigest()


def check_nesting(terms: Mapping[str, Term]) -> None:
    """Refuse a `nested_under` graph that cannot describe containment.

    A parent no term defines, a term nested under itself, a chain that loops:
    none of them can mean "these matches lie inside those". `summable` would
    read the first two as a term nobody covers and the third as a set covering
    itself, dropping every member of the loop from the sum — a silent
    undercount, which is exactly what refusing the file here prevents.
    """
    bad_parents = {
        term.name: term.nested_under
        for term in terms.values()
        if term.nested_under is not None and term.nested_under not in terms
    }
    if bad_parents:
        raise ValueError(f"{rel(LEXICON)}: nested terms reference undefined parents: {bad_parents}")

    itself = sorted(term.name for term in terms.values() if term.nested_under == term.name)
    if itself:
        raise ValueError(
            f"{rel(LEXICON)}: terms nested under themselves: {itself}; a term cannot "
            "contain its own matches, and declaring it so would drop it from every sum"
        )

    for term in terms.values():
        chain = [term.name]
        parent = term.nested_under
        while parent is not None:
            if parent in chain:
                raise ValueError(
                    f"{rel(LEXICON)}: nesting runs in a cycle: "
                    f"{' -> '.join([*chain, parent])}; containment has a direction and "
                    "every chain must end at a term nested under nothing"
                )
            chain.append(parent)
            parent = terms[parent].nested_under


def check_lock(terms: Mapping[str, Term], version: int, lock: Mapping[str, object]) -> None:
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
                f"to {version} and run `python tools/lock_lexicon.py`"
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


def _check_committed_lock(terms: Mapping[str, Term], version: int) -> None:
    """Read the committed lock and hold `terms` to it.

    Separate from `check_lock` only because `load`'s keyword of that name
    shadows it inside `load`; the check itself stays a pure function of values.
    """
    if not LEXICON_LOCK.exists():
        raise FileNotFoundError(
            f"{rel(LEXICON_LOCK)} is missing — it is committed beside "
            f"{rel(LEXICON)}; run `python tools/lock_lexicon.py` to write it"
        )
    check_lock(terms, version, json.loads(LEXICON_LOCK.read_text(encoding="utf-8")))


def load(*, check_lock: bool = True) -> Lexicon:
    """Read and compile config/lexicon.yml.

    `check_lock` holds the file to `config/lexicon.lock.json`, which is what
    catches a pattern edited without its `pattern_since`. Only the tool that
    writes that lock passes False: every other caller wants the check.
    """
    if not LEXICON.exists():
        raise FileNotFoundError(f"{rel(LEXICON)} is missing")
    raw = yaml.safe_load(LEXICON.read_text(encoding="utf-8"))

    version = raw.get("version", 0)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"{rel(LEXICON)}: 'version' must be an integer, got {version!r}")
    # Said here rather than left to the `pattern_since` bounds below, which
    # would report a missing `version:` as a range of "1..0".
    if version < 1:
        raise ValueError(
            f"{rel(LEXICON)}: 'version' must be at least 1, got {version}; every release "
            "of the lexicon is numbered and the first one is 1"
        )

    terms: dict[str, Term] = {}
    for name, spec in raw["terms"].items():
        try:
            regex = re.compile(spec["pattern"], re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"{rel(LEXICON)}: term '{name}' has an invalid pattern: {exc}") from exc
        since = spec.get("pattern_since")
        if not isinstance(since, int) or isinstance(since, bool):
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' needs an integer 'pattern_since' — the "
                "lexicon version at which its pattern last changed"
            )
        if not 1 <= since <= version:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' has pattern_since {since}, outside "
                f"1..{version}; a pattern cannot have changed in a version that does "
                "not exist yet"
            )

        anchor = spec.get("anchor")
        if anchor is not None and anchor not in ANCHORS:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' declares anchor {anchor!r}; the "
                f"anchors are {sorted(ANCHORS)}, or none at all. An unrecognised "
                "anchor would count every match and look like a decision to anchor"
            )

        terms[name] = Term(
            name=name,
            pattern=spec["pattern"],
            pattern_since=since,
            tier=spec.get("tier", "adjacent"),
            register=spec.get("register", "other"),
            enabled=spec.get("enabled", True),
            note=(spec.get("note") or "").strip(),
            examples=tuple(str(example) for example in spec.get("examples", [])),
            prefilters=tuple(str(literal) for literal in spec.get("prefilters", [])),
            nested_under=spec.get("nested_under"),
            anchor=anchor,
            regex=regex,
        )

        if not terms[name].examples:
            raise ValueError(f"{rel(LEXICON)}: term '{name}' needs at least one example")
        if not terms[name].prefilters:
            raise ValueError(f"{rel(LEXICON)}: term '{name}' needs at least one prefilter")
        missed = [example for example in terms[name].examples if not regex.search(example)]
        if missed:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' does not match its examples: {missed}"
            )
        unfiltered = [
            example
            for example in terms[name].examples
            if not any(literal.lower() in example.lower() for literal in terms[name].prefilters)
        ]
        if unfiltered:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' prefilters miss its examples: {unfiltered}"
            )
        # The records keep their hard line breaks, so `\s+` in a pattern spans a
        # newline that a multi-word literal never will: such a literal would skip
        # the speech and lose the match rather than merely slow the scan down.
        # ASCII for the same reason rather than for tidiness: the fast path is
        # `str.contains(case=False)`, upper-case containment, while the pattern
        # runs under `re.IGNORECASE`. The two agree on ASCII and diverge outside
        # it — `re.IGNORECASE` folds U+0130 "İ" to "i", upper-casing does not —
        # so a non-ASCII literal could skip a speech the regex would match.
        unusable = [
            literal
            for literal in terms[name].prefilters
            if any(c.isspace() for c in literal) or not literal.isascii()
        ]
        if unusable:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' has prefilters that are not whitespace-free "
                f"ASCII: {unusable}; a prefilter is a plain case-insensitive substring test "
                "and must be one ASCII token"
            )

    sets = raw.get("sets", {})
    unknown = {
        name: [t for t in members if t not in terms] for name, members in sets.items()
    }
    if bad := {k: v for k, v in unknown.items() if v}:
        raise ValueError(f"{rel(LEXICON)}: sets reference undefined terms: {bad}")

    check_nesting(terms)

    derived: dict[str, Derived] = {}
    for name, spec in (raw.get("derived") or {}).items():
        if name in terms:
            raise ValueError(
                f"{rel(LEXICON)}: derived measure '{name}' has the name of a term; "
                "the two share a column namespace and one would silently overwrite "
                "the other"
            )
        minuend = spec.get("from")
        subtrahends = tuple(spec.get("minus") or ())
        missing = [t for t in (minuend, *subtrahends) if t not in terms]
        if missing:
            raise ValueError(
                f"{rel(LEXICON)}: derived measure '{name}' references undefined "
                f"terms: {missing}"
            )
        if not subtrahends:
            raise ValueError(
                f"{rel(LEXICON)}: derived measure '{name}' subtracts nothing; a "
                "measure equal to a term is that term under a second name"
            )
        # Nesting is the declared claim that one term's matches lie inside
        # another's. Without it the subtraction is not a narrowing of the
        # minuend but an arithmetic accident of two unrelated counts.
        outside = [t for t in subtrahends if terms[t].nested_under != minuend]
        if outside:
            raise ValueError(
                f"{rel(LEXICON)}: derived measure '{name}' subtracts {outside} from "
                f"'{minuend}', but they are not declared nested under it; only a term "
                "whose matches lie inside another's may be subtracted from it"
            )
        derived[name] = Derived(
            name=name,
            minuend=str(minuend),
            subtrahends=subtrahends,
            tier=spec.get("tier", terms[str(minuend)].tier),
            register=spec.get("register", terms[str(minuend)].register),
            note=(spec.get("note") or "").strip(),
        )

    if check_lock:
        _check_committed_lock(terms, version)

    return Lexicon(
        version=version,
        updated=str(raw.get("updated", "")),
        terms=terms,
        sets=sets,
        derived=derived,
    )


def apply(bodies: pd.Series, lex: Lexicon) -> pd.DataFrame:
    """Count every active term in every speech body.

    Returns a frame of ``n_<term>`` and ``has_<term>`` columns, one such pair
    per :class:`Derived` measure, plus one ``has_<set>`` column per convenience
    grouping and per register, all indexed like ``bodies``.

    The occurrence roll-ups — each ``n_register_<register>`` and
    ``n_lexicon_total`` — are sums over :func:`summable`, so a term declared
    nested under another is not added on top of the parent that already counts
    its span. The ``has_`` flags and ``n_lexicon_terms`` stay over every member:
    neither can double-count a span. A derived measure enters no roll-up at
    all: it is a restatement of its minuend, which every roll-up already holds,
    and adding it would count those spans a second time.
    """
    counts = pd.DataFrame(index=bodies.index)
    for term in lex.active:
        counts[f"{COUNT}{term.name}"] = term.count(bodies)
        counts[f"{HAS}{term.name}"] = counts[f"{COUNT}{term.name}"] > 0

    for measure in lex.derived.values():
        net = counts[f"{COUNT}{measure.minuend}"].copy()
        for subtrahend in measure.subtrahends:
            net -= counts[f"{COUNT}{subtrahend}"]
        # A negative count is the one way a broken partition shows itself in the
        # data: a subtrahend matched somewhere its declared parent did not, so
        # the two do not divide the parent's spans between them and the
        # difference is not the narrowing it claims to be.
        if bool((net < 0).any()):
            offenders = bodies.index[net < 0].tolist()[:5]
            raise ValueError(
                f"derived measure '{measure.name}' is negative in "
                f"{int((net < 0).sum())} speeches (first: {offenders}); "
                f"{list(measure.subtrahends)} do not partition "
                f"'{measure.minuend}' and the subtraction is not a narrowing"
            )
        counts[f"{COUNT}{measure.name}"] = net.astype("int64")
        counts[f"{HAS}{measure.name}"] = net > 0

    for register, terms in lex.by_register().items():
        summed = [f"{COUNT}{t.name}" for t in summable(terms, lex.terms)]
        counts[f"{COUNT}register_{register}"] = counts[summed].sum(axis=1).astype("int32")
        # The flag asks whether the register was used at all, which no amount of
        # nesting can double-count, so it stays over every member — the booleans
        # written a few lines above, rather than a second sum of the same counts.
        members = [f"{HAS}{t.name}" for t in terms]
        counts[f"{HAS}register_{register}"] = counts[members].any(axis=1)

    for set_name, members in lex.sets.items():
        columns = [f"{COUNT}{m}" for m in members if f"{COUNT}{m}" in counts]
        if columns:
            counts[f"{HAS}set_{set_name}"] = counts[columns].sum(axis=1) > 0

    active = [f"{COUNT}{t.name}" for t in lex.active]
    summed = [f"{COUNT}{t.name}" for t in summable(lex.active, lex.terms)]
    counts["n_lexicon_total"] = counts[summed].sum(axis=1).astype("int32")
    # Distinct terms present, not spans: a nested term and its parent are two
    # terms, and a speech using both is described by both.
    counts["n_lexicon_terms"] = (counts[active] > 0).sum(axis=1).astype("int32")
    return counts


def ocr_delta(bodies: pd.Series, lex: Lexicon) -> list[dict[str, object]]:
    """Extra speeches each disabled term would add, over the enabled terms.

    Reported rather than absorbed: silently folding OCR noise into the headline
    count would overstate how much of it there is.
    """
    report: list[dict[str, object]] = []
    for term in lex.disabled:
        found = term.count(bodies) > 0
        # Compare against the terms of the same tier that are switched on.
        peers = [t for t in lex.active if t.tier == term.tier]
        already = pd.Series(False, index=bodies.index)
        for peer in peers:
            already |= peer.count(bodies) > 0
        report.append(
            {
                "term": term.name,
                "pattern": term.pattern,
                "speeches": int(found.sum()),
                "extra": int((found & ~already).sum()),
                "extra_index": bodies.index[found & ~already].tolist(),
            }
        )
    return report
