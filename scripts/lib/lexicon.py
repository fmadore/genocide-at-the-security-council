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
    enabled: bool = True
    note: str = ""
    regex: re.Pattern[str] = field(compare=False, repr=False, default=None)  # type: ignore[assignment]

    def count(self, texts: pd.Series) -> pd.Series:
        """Occurrences of this term in each text."""
        return pd.Series(
            [len(self.regex.findall(t)) for t in texts], index=texts.index, dtype="int32"
        )


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

    terms: dict[str, Term] = {}
    for name, spec in raw["terms"].items():
        try:
            regex = re.compile(spec["pattern"], re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"{rel(LEXICON)}: term '{name}' has an invalid pattern: {exc}") from exc
        terms[name] = Term(
            name=name,
            pattern=spec["pattern"],
            tier=spec.get("tier", "adjacent"),
            register=spec.get("register", "other"),
            enabled=spec.get("enabled", True),
            note=(spec.get("note") or "").strip(),
            regex=regex,
        )

    sets = raw.get("sets", {})
    unknown = {
        name: [t for t in members if t not in terms] for name, members in sets.items()
    }
    if bad := {k: v for k, v in unknown.items() if v}:
        raise ValueError(f"{rel(LEXICON)}: sets reference undefined terms: {bad}")

    return Lexicon(
        version=raw.get("version", 0),
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
