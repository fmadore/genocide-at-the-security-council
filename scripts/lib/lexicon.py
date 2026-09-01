"""The genocide lexicon: load, compile, count.

`config/lexicon.yml` is a hypothesis about what "discussing genocide" looks
like in a verbatim record, not a ground truth. This module keeps it honest:

- every term carries its own `tier` and `register`, so a count can always be
  traced back to the discursive family it belongs to;
- terms marked ``enabled: false`` — the OCR-tolerant net — are compiled and
  measured but kept out of the headline columns, so their contribution is
  reported as a delta rather than folded silently into the total;
- the lexicon's version is recorded in the output, because changing this file
  changes every downstream number.

Counting runs against the speech *body* (form of address removed). Counting
against the raw text would inflate every country name and the word "President".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd
import yaml

from .paths import LEXICON, rel

#: Column prefixes. ``has_x`` is a boolean, ``n_x`` the occurrence count.
HAS = "has_"
COUNT = "n_"


@dataclass(frozen=True)
class Term:
    """One lexicon entry."""

    name: str
    pattern: str
    tier: str
    register: str
    #: Lexicon version at which `pattern` last changed. `load` requires it in
    #: the config; the default is for the hand-built terms in the tests.
    pattern_since: int = 1
    enabled: bool = True
    note: str = ""
    examples: tuple[str, ...] = ()
    prefilters: tuple[str, ...] = ()
    nested_under: str | None = None
    regex: re.Pattern[str] = field(compare=False, repr=False, default=None)  # type: ignore[assignment]

    def count(self, texts: pd.Series) -> pd.Series:
        """Occurrences of this term in each text.

        The prefilters are a fast path and never a second filter: `load` refuses
        a literal that is not whitespace-free, and config/lexicon.yml requires
        every literal to appear in every string the pattern can match, so
        skipping a text that holds none of them cannot lose an occurrence.
        """
        candidates = pd.Series(False, index=texts.index)
        for literal in self.prefilters:
            candidates |= texts.str.contains(literal, case=False, regex=False, na=False)
        counts = pd.Series(0, index=texts.index, dtype="int64")
        if candidates.any():
            sources = texts.loc[candidates]
            matched = pd.Series(
                [len(self.regex.findall(source)) for source in sources],
                index=sources.index,
                dtype="int64",
            )
            counts.loc[candidates] = matched
        return counts


@dataclass(frozen=True)
class Lexicon:
    """The whole versioned lexicon."""

    version: int
    updated: str
    terms: dict[str, Term]
    sets: dict[str, list[str]]

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
        `version`: its pattern has not been edited since (`pattern_since <=
        version`) and `version` is not ahead of this lexicon. That is what lets
        a gold sample or a committed model run survive a version bump that
        edited other terms.

        It guarantees nothing else. Other terms' counts may have moved, any
        aggregate over the whole lexicon may have moved, and the artefact's own
        rows are still checked against this corpus row by row.
        """
        if term_name not in self.terms:
            raise ValueError(f"unknown lexicon term '{term_name}'")
        try:
            recorded = int(version)
        except (TypeError, ValueError):
            # An unreadable version is not a matching one.
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


def load() -> Lexicon:
    """Read and compile config/lexicon.yml."""
    if not LEXICON.exists():
        raise FileNotFoundError(f"{rel(LEXICON)} is missing")
    raw = yaml.safe_load(LEXICON.read_text(encoding="utf-8"))

    version = raw.get("version", 0)
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"{rel(LEXICON)}: 'version' must be an integer, got {version!r}")

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
        spaced = [
            literal for literal in terms[name].prefilters if any(c.isspace() for c in literal)
        ]
        if spaced:
            raise ValueError(
                f"{rel(LEXICON)}: term '{name}' has prefilters containing whitespace: "
                f"{spaced}; a prefilter is a plain substring test and must be one token"
            )

    sets = raw.get("sets", {})
    unknown = {
        name: [t for t in members if t not in terms] for name, members in sets.items()
    }
    if bad := {k: v for k, v in unknown.items() if v}:
        raise ValueError(f"{rel(LEXICON)}: sets reference undefined terms: {bad}")

    bad_parents = {
        term.name: term.nested_under
        for term in terms.values()
        if term.nested_under is not None and term.nested_under not in terms
    }
    if bad_parents:
        raise ValueError(f"{rel(LEXICON)}: nested terms reference undefined parents: {bad_parents}")

    return Lexicon(
        version=version,
        updated=str(raw.get("updated", "")),
        terms=terms,
        sets=sets,
    )


def apply(bodies: pd.Series, lex: Lexicon) -> pd.DataFrame:
    """Count every active term in every speech body.

    Returns a frame of ``n_<term>`` and ``has_<term>`` columns, plus one
    ``has_<set>`` column per convenience grouping and per register, all indexed
    like ``bodies``.
    """
    counts = pd.DataFrame(index=bodies.index)
    for term in lex.active:
        counts[f"{COUNT}{term.name}"] = term.count(bodies)
        counts[f"{HAS}{term.name}"] = counts[f"{COUNT}{term.name}"] > 0

    for register, terms in lex.by_register().items():
        columns = [f"{COUNT}{t.name}" for t in terms]
        counts[f"{COUNT}register_{register}"] = counts[columns].sum(axis=1).astype("int32")
        counts[f"{HAS}register_{register}"] = counts[f"{COUNT}register_{register}"] > 0

    for set_name, members in lex.sets.items():
        columns = [f"{COUNT}{m}" for m in members if f"{COUNT}{m}" in counts]
        if columns:
            counts[f"{HAS}set_{set_name}"] = counts[columns].sum(axis=1) > 0

    active = [f"{COUNT}{t.name}" for t in lex.active]
    counts["n_lexicon_total"] = counts[active].sum(axis=1).astype("int32")
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
