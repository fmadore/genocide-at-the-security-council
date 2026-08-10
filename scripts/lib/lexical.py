"""Lexicometry: collocates, keyness, and the co-occurrence network.

Three measurements, each with the same discipline: report an effect size next to
every significance figure, and say what the comparison was made against.

**Log-likelihood (G²)** ranks a word by how confidently we can say its rate
differs between two corpora. It is a significance measure, and on 59 million
tokens almost everything is significant — so every row also carries **log ratio**
(Hardie 2014), which says by how much. A word can top the G² table on a rate
difference of 1.2x; the log ratio is what stops that being read as a finding.

**Keyness needs a control, and the control needs matching.** Comparing
genocide-bearing speeches against the rest of the corpus recovers "these are
speeches about Rwanda in 1994" — the vocabulary of the occasion, not of the
concept. Each target is therefore paired with a speech from the same year, the
same agenda item and the same speaker group, and the shortfall where no such
speech exists is reported rather than absorbed.

**PMI on the lexicon network** is computed at the level of the speech: two terms
are linked when they are used in the same intervention. Normalised PMI travels
alongside because raw PMI is unbounded and rewards rarity — `genocidal_ideology`
would otherwise dominate a graph it appears in 30 speeches of.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .lexicon import HAS, Lexicon, Term
from .paths import STOPWORDS, rel

#: Words: letters, with internal apostrophes and hyphens kept. Digits are
#: dropped — resolution numbers and dates are not vocabulary, and they would
#: swamp any table they were let into. The curly apostrophe is named by code
#: point: the OCR carries both, and they are identical on screen.
TOKEN_RE = re.compile("[a-z][a-z'" + chr(0x2019) + "-]*")

#: Below this many occurrences in the target, a word is noise however extreme
#: its statistic. G² is unreliable on small expected counts.
MIN_COUNT = 5


def load_stopwords() -> frozenset[str]:
    """Read `config/stopwords.txt` — function words only, by design."""
    if not STOPWORDS.exists():
        raise FileNotFoundError(f"{rel(STOPWORDS)} is missing")
    words = []
    for line in STOPWORDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line.lower())
    return frozenset(words)


# --- Tokens ----------------------------------------------------------------


@dataclass(frozen=True)
class Tokens:
    """Words and where each one starts, so a character span can find them."""

    words: list[str]
    starts: list[int]

    def __len__(self) -> int:
        return len(self.words)

    def around(self, span: tuple[int, int], width: int) -> list[str]:
        """Up to `width` tokens either side of a character span.

        The tokens the span itself covers are excluded: a node word is not its
        own collocate.
        """
        first = bisect.bisect_left(self.starts, span[0])
        past = bisect.bisect_left(self.starts, span[1])
        return self.words[max(0, first - width) : first] + self.words[past : past + width]

    def context(self, spans: list[tuple[int, int]], width: int) -> list[str]:
        """Unique context tokens around several nodes in one speech.

        Overlapping windows are merged at token level and every node token is
        excluded. This prevents a phrase repeated in one sentence from counting
        the shared context once per occurrence.
        """
        context_indices: set[int] = set()
        node_indices: set[int] = set()
        for start, stop in spans:
            first = bisect.bisect_left(self.starts, start)
            past = bisect.bisect_left(self.starts, stop)
            node_indices.update(range(first, past))
            context_indices.update(range(max(0, first - width), min(len(self), past + width)))
        return [self.words[index] for index in sorted(context_indices - node_indices)]


def tokenise(source: str) -> Tokens:
    """Lower-case word tokens with their offsets into `source`."""
    words, starts = [], []
    for match in TOKEN_RE.finditer(source.lower()):
        words.append(match.group())
        starts.append(match.start())
    return Tokens(words, starts)


def vocabulary(texts) -> Counter[str]:
    """Corpus-wide token frequencies. The reference every rate is read against."""
    counts: Counter[str] = Counter()
    for source in texts:
        counts.update(TOKEN_RE.findall(source.lower()))
    return counts


# --- Statistics ------------------------------------------------------------


def log_likelihood(a: int, b: int, target_total: int, reference_total: int) -> float:
    """Signed G² for one word's rate in a target against a reference corpus.

    Positive when the word is over-represented in the target, negative when it
    is under-represented, so a single sorted table shows attraction at one end
    and repulsion at the other.
    """
    if target_total <= 0 or reference_total <= 0 or a + b == 0:
        return 0.0
    total = target_total + reference_total
    expected_target = target_total * (a + b) / total
    expected_reference = reference_total * (a + b) / total

    statistic = 0.0
    if a > 0:
        statistic += a * math.log(a / expected_target)
    if b > 0:
        statistic += b * math.log(b / expected_reference)
    statistic *= 2

    over = (a / target_total) >= (b / reference_total)
    return statistic if over else -statistic


def log_ratio(a: int, b: int, target_total: int, reference_total: int) -> float:
    """Effect size: log2 of the rate ratio, with a half-occurrence floor.

    A word absent from the reference has an infinite ratio, which no chart can
    plot. Substituting half an occurrence is the standard fix and is reported as
    what it is rather than as a measured value.
    """
    if target_total <= 0 or reference_total <= 0:
        return 0.0
    target_rate = max(a, 0.5) / target_total
    reference_rate = max(b, 0.5) / reference_total
    return math.log2(target_rate / reference_rate)


def compare(
    target: Counter[str],
    reference: Counter[str],
    target_total: int,
    reference_total: int,
    stopwords: frozenset[str],
    min_count: int = MIN_COUNT,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Rank words by how strongly the target's rate differs from the reference.

    `reference` is expected to *contain* the target's counts — the whole corpus,
    not its complement — and they are subtracted here so the two sides of the
    contingency table do not overlap.
    """
    rows = []
    for word, count in target.items():
        if count < min_count or word in stopwords:
            continue
        elsewhere = max(reference.get(word, 0) - count, 0)
        rows.append(
            {
                "word": word,
                "target": count,
                "reference": elsewhere,
                "g2": round(log_likelihood(count, elsewhere, target_total, reference_total), 3),
                "log_ratio": round(
                    log_ratio(count, elsewhere, target_total, reference_total), 3
                ),
            }
        )
    rows.sort(key=lambda r: -float(r["g2"]))  # type: ignore[arg-type]
    return rows[:limit] if limit else rows


# --- Collocates ------------------------------------------------------------


def collocates(
    bodies,
    term: Term,
    width: int,
    reference: Counter[str],
    reference_total: int,
    stopwords: frozenset[str],
    min_count: int = MIN_COUNT,
    limit: int | None = 100,
    tokeniser=None,
) -> tuple[list[dict[str, object]], int, int]:
    """Words attracted to `term` within `width` tokens.

    Returns the ranked rows, the number of node occurrences behind them, and the
    total tokens in the windows — both needed to say how much evidence a table
    rests on.

    `tokeniser(index, source) -> Tokens` overrides how a speech is turned into
    countable units; `lib.lemmas` supplies one that yields lemmas while keeping
    the surface offsets. It is a callback rather than a second parameter holding
    the lemma rows because `lemmas` imports this module, and the node spans below
    must go on being found in the original text whatever is being counted.
    """
    window: Counter[str] = Counter()
    occurrences = 0
    for index, source in enumerate(bodies):
        matches = list(term.regex.finditer(source))
        if not matches:
            continue
        tokens = tokenise(source) if tokeniser is None else tokeniser(index, source)
        occurrences += len(matches)
        window.update(tokens.context([(match.start(), match.end()) for match in matches], width))

    window_total = sum(window.values())
    rows = compare(
        window,
        reference,
        window_total,
        max(reference_total - window_total, 1),
        stopwords,
        min_count,
        limit,
    )
    return rows, occurrences, window_total


# --- Matched control -------------------------------------------------------


@dataclass(frozen=True)
class MatchedPairs:
    """Aligned target and control indices drawn from the same strata."""

    target_index: pd.Index
    control_index: pd.Index
    matched: int  #: target speeches that found a partner
    wanted: int  #: target speeches in total
    short_strata: list[tuple[tuple, int, int]]  #: (key, wanted, found)

    @property
    def coverage(self) -> float:
        return self.matched / self.wanted if self.wanted else 0.0


def matched_control(
    frame: pd.DataFrame, flag: str, keys: list[str], seed: int = 20_260_807
) -> MatchedPairs:
    """One non-target speech per target, from the same stratum.

    Sampling is without replacement inside a stratum, so no control speech is
    counted twice. Where a stratum holds fewer non-targets than targets — a
    debate in which almost everyone said the word — the shortfall is recorded
    and returned, because a control set that quietly under-covers the crisis
    years would bias the keyness table towards exactly those years.
    """
    rng = np.random.default_rng(seed)
    targets = frame[frame[flag]]
    pool = frame[~frame[flag]]
    available = {key: list(idx) for key, idx in pool.groupby(keys, sort=True).groups.items()}

    picked_targets: list = []
    picked_controls: list = []
    short: list[tuple[tuple, int, int]] = []
    for key, group in targets.groupby(keys, sort=True):
        wanted = len(group)
        candidates = available.get(key, [])
        take = min(wanted, len(candidates))
        if take < wanted:
            short.append((key if isinstance(key, tuple) else (key,), wanted, take))
        if take:
            target_indices = np.asarray(group.index)
            if take < wanted:
                target_indices = rng.choice(target_indices, take, replace=False)
            picked_targets.extend(target_indices.tolist())
            picked_controls.extend(
                rng.choice(np.asarray(candidates), take, replace=False).tolist()
            )

    return MatchedPairs(
        target_index=pd.Index(picked_targets),
        control_index=pd.Index(picked_controls),
        matched=len(picked_controls),
        wanted=len(targets),
        short_strata=short,
    )


# --- Co-occurrence network -------------------------------------------------


def pmi_network(
    frame: pd.DataFrame, lex: Lexicon, min_speeches: int = 20
) -> list[dict[str, object]]:
    """Pointwise mutual information between lexicon terms, at speech level.

    Two terms are linked when the same intervention uses both. Normalised PMI
    is carried alongside the raw value: PMI is unbounded and rewards rarity, so
    a term appearing in thirty speeches would otherwise own the graph.
    """
    total = len(frame)
    if total == 0:
        return []

    names = [t.name for t in lex.active]
    present = {name: frame[f"{HAS}{name}"].to_numpy() for name in names}
    counts = {name: int(present[name].sum()) for name in names}

    edges = []
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            left_term = lex.terms[left]
            right_term = lex.terms[right]
            if left_term.nested_under == right or right_term.nested_under == left:
                continue
            together = int((present[left] & present[right]).sum())
            if together < min_speeches:
                continue
            joint = together / total
            expected = (counts[left] / total) * (counts[right] / total)
            pmi = math.log2(joint / expected)
            edges.append(
                {
                    "source": left,
                    "target": right,
                    "speeches": together,
                    "pmi": round(pmi, 4),
                    # -log2(joint) is 0 when two terms always co-occur, which
                    # would divide by zero; that case is npmi = 1 by definition.
                    "npmi": round(pmi / -math.log2(joint), 4) if joint < 1 else 1.0,
                }
            )
    edges.sort(key=lambda e: -float(e["npmi"]))  # type: ignore[arg-type]
    return edges
