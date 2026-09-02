"""Lexicometry: collocates, keyness, and the co-occurrence network.

Three measurements, each with the same discipline: report an effect size next to
every significance figure, and say what the comparison was made against.

**Log-likelihood (G²)** ranks a word by how confidently we can say its rate
differs between two corpora. It is a significance measure, and on 58.9 million
words almost everything is significant — so every row also carries **log ratio**
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

**Significance is a floor, not a ranking** (review of 1 September 2026, §3.2).
G² on pooled token counts treats every token as independent, so a collocate
repeated fifty times in one speech ranks as if it appeared in fifty speeches.
Tables are therefore ranked by effect — log ratio for keywords, logDice for
collocates — among the rows that clear :data:`G2_FLOOR`, and every row carries
its **dispersion**: the documents and distinct meetings it appears in, and
Gries's DP, so a reader can tell a property of the register from a property of
one debate.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .lexicon import ANCHOR_RE, HAS, Lexicon, Term
from .paths import STOPWORDS, rel

#: Words: a letter, then letters, digits, internal apostrophes and hyphens,
#: ending on a letter or digit. A token cannot *start* with a digit —
#: resolution numbers and dates are not vocabulary, and they would swamp any
#: table they were let into — but may carry one, so `R2P` is one word rather
#: than `r` and `p`. It cannot *end* on an apostrophe or hyphen either: the
#: earlier pattern kept them, so a scare-quoted `'genocide'` tokenised as
#: `genocide'`, a separate type, and the one usage this study most wants to
#: see — the distanced, contested one — dropped out of every keyness table.
#: The curly apostrophe is named by code point: the OCR carries both, and they
#: are identical on screen.
TOKEN_RE = re.compile("[a-z](?:[a-z0-9'" + chr(0x2019) + "-]*[a-z0-9])?")

#: Below this many occurrences in the target, a word is noise however extreme
#: its statistic. G² is unreliable on small expected counts.
MIN_COUNT = 5

#: The significance floor a row must clear before it is ranked at all: G² for
#: one degree of freedom at p < 0.001. Below it the effect size is a number
#: about noise. It is a floor and never an ordering — see the module docstring.
G2_FLOOR = 10.83


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


def word_count(texts) -> list[int]:
    """Words in each text, by :data:`TOKEN_RE` and by nothing else.

    The denominator of every "per 100,000 words" figure on the site, written
    into `speeches_norm.parquet` by 02 so that it is counted once and divided
    by everywhere. Before 2 September 2026 those figures divided by the
    codebook's `tokens` column — quanteda's count over the full text,
    punctuation and numbers included — which is 12.7% larger than this, so the
    rates ran 11.3% below the label they carried (review of 1 September 2026,
    §3.3).

    Counting here rather than in 02 keeps the tokeniser in one module: this is
    the same `TOKEN_RE` the keyness tables, the collocate windows and the
    language page's 59-million-word universe are built on, and a denominator
    counted by a second rule would eventually disagree with the numerator it
    divides.
    """
    return [len(TOKEN_RE.findall(source.lower())) for source in texts]


def vocabulary(texts) -> Counter[str]:
    """Corpus-wide token frequencies. The reference every rate is read against."""
    counts: Counter[str] = Counter()
    for source in texts:
        counts.update(TOKEN_RE.findall(source.lower()))
    return counts


def document_vocabulary(texts) -> list[Counter[str]]:
    """The same counts, one `Counter` per document, for :func:`dispersion`."""
    return [Counter(TOKEN_RE.findall(source.lower())) for source in texts]


# --- Dispersion ------------------------------------------------------------


def dispersion(
    documents: Sequence[Counter[str]],
    sizes: Sequence[int],
    meetings: Sequence[object] | None = None,
) -> dict[str, dict[str, object]]:
    """Per word: the documents and meetings it appears in, and Gries's DP.

    A frequency says how often; dispersion says how *evenly*. DP (Gries 2008)
    compares the share of a word's occurrences that fall in each document with
    the share of the text that document is: 0 when the word is spread exactly
    as the text is, 1 when the whole of it sits in a document of vanishing
    size. A collocate at DP 0.95 is one debate's word; at 0.3 it is the
    register's.

    `documents` are per-document counts, `sizes` their token totals (the
    windows' sizes for a collocate table, the speeches' for a keyword table),
    `meetings` the meeting each document came from, so that a word repeated
    across thirty speeches of one sitting is not mistaken for one spread across
    thirty sittings. The DP sum is taken only over documents holding the word —
    every absent document contributes exactly its expected share — which is
    what keeps this linear in the number of (document, word) pairs.
    """
    if len(documents) != len(sizes):
        raise ValueError(f"{len(documents)} documents against {len(sizes)} sizes")
    if meetings is not None and len(meetings) != len(documents):
        raise ValueError(f"{len(documents)} documents against {len(meetings)} meetings")
    total = float(sum(sizes))
    if total <= 0:
        return {}
    expected = [size / total for size in sizes]

    frequency: Counter[str] = Counter()
    for counts in documents:
        frequency.update(counts)

    difference: dict[str, float] = {}
    covered: dict[str, float] = {}
    seen_in: Counter[str] = Counter()
    seen_at: dict[str, set[object]] = {}
    for index, counts in enumerate(documents):
        share = expected[index]
        meeting = None if meetings is None else meetings[index]
        for word, count in counts.items():
            if count <= 0:
                continue
            observed = count / frequency[word]
            difference[word] = difference.get(word, 0.0) + abs(share - observed)
            covered[word] = covered.get(word, 0.0) + share
            seen_in[word] += 1
            if meetings is not None:
                seen_at.setdefault(word, set()).add(meeting)

    return {
        word: {
            "documents": seen_in[word],
            "meetings": len(seen_at[word]) if meetings is not None else None,
            "dp": round(0.5 * (difference[word] + 1.0 - covered[word]), 4),
        }
        for word in frequency
        if frequency[word] > 0
    }


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


def log_dice(joint: int, node: int, collocate: int) -> float:
    """logDice (Rychlý 2008): the collocation measure that does not reward rarity.

    ``14 + log2(2·f(node, collocate) / (f(node) + f(collocate)))``, with 14 the
    score of a pair that never appears apart. It is independent of corpus size,
    so a value means the same thing in a 1994 slice and in the whole corpus,
    which G² and log ratio do not offer.
    """
    if joint <= 0 or node + collocate <= 0:
        return float("-inf")
    return 14.0 + math.log2(2.0 * joint / (node + collocate))


def compare(
    target: Counter[str],
    reference: Counter[str],
    target_total: int,
    reference_total: int,
    stopwords: frozenset[str],
    min_count: int = MIN_COUNT,
    limit: int | None = None,
    *,
    floor: float = G2_FLOOR,
    rank: str = "log_ratio",
    dispersion: Mapping[str, Mapping[str, object]] | None = None,
    extra: Callable[[str, int], dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Rank words by how much the target's rate differs from the reference.

    `reference` is expected to *contain* the target's counts — the whole corpus,
    not its complement — and they are subtracted here so the two sides of the
    contingency table do not overlap.

    A row must clear `floor` on |G²| to be kept at all, and the kept rows are
    ordered by `rank` (descending), then by G², then by word, so a tie settles
    the same way on every run. `rank` names a column the row carries: `log_ratio`
    for a keyword table, or a column `extra` adds — `collocates` adds `log_dice`
    and ranks on it. `dispersion`, from :func:`dispersion`, contributes
    `documents`, `meetings` and `dp` to every row; a caller that has
    per-document counts should always pass it, because a table without
    dispersion cannot tell one debate's word from the register's.
    """
    rows = []
    for word, count in target.items():
        if count < min_count or word in stopwords:
            continue
        elsewhere = max(reference.get(word, 0) - count, 0)
        g2 = log_likelihood(count, elsewhere, target_total, reference_total)
        if abs(g2) < floor:
            continue
        row: dict[str, object] = {
            "word": word,
            "target": count,
            "reference": elsewhere,
            "g2": round(g2, 3),
            "log_ratio": round(log_ratio(count, elsewhere, target_total, reference_total), 3),
        }
        if extra is not None:
            row |= extra(word, count)
        if dispersion is not None:
            spread = dispersion.get(word)
            if spread is None:
                raise KeyError(f"no dispersion for {word!r}, which the target counts")
            row |= {
                "documents": spread["documents"],
                "meetings": spread["meetings"],
                "dp": spread["dp"],
            }
        rows.append(row)
    if rows and rank not in rows[0]:
        raise KeyError(f"cannot rank on {rank!r}: rows carry {sorted(rows[0])}")
    rows.sort(key=lambda r: (-float(r[rank]), -float(r["g2"]), str(r["word"])))  # type: ignore[arg-type]
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
    meetings: Sequence[object] | None = None,
    floor: float = G2_FLOOR,
) -> tuple[list[dict[str, object]], int, int]:
    """Words attracted to `term` within `width` tokens.

    Returns the ranked rows, the number of node occurrences behind them, and the
    total tokens in the windows — both needed to say how much evidence a table
    rests on. Rows are ranked by logDice among those clearing the G² floor, and
    each carries its dispersion over the node-bearing speeches: the speeches
    and meetings whose windows hold the word, and DP over the windows.

    `tokeniser(index, source) -> Tokens` overrides how a speech is turned into
    countable units; `lib.lemmas` supplies one that yields lemmas while keeping
    the surface offsets. It is a callback rather than a second parameter holding
    the lemma rows because `lemmas` imports this module, and the node spans below
    must go on being found in the original text whatever is being counted.

    `meetings` is aligned to `bodies` and names the meeting each speech came
    from; without it the `meetings` column is null rather than guessed.
    """
    window: Counter[str] = Counter()
    per_speech: list[Counter[str]] = []
    sizes: list[int] = []
    from_meetings: list[object] = []
    occurrences = 0
    for index, source in enumerate(bodies):
        matches = term.spans(source)
        if not matches:
            continue
        tokens = tokenise(source) if tokeniser is None else tokeniser(index, source)
        occurrences += len(matches)
        context = Counter(tokens.context(matches, width))
        window.update(context)
        per_speech.append(context)
        sizes.append(sum(context.values()))
        if meetings is not None:
            from_meetings.append(meetings[index])

    window_total = sum(window.values())
    spread = dispersion(per_speech, sizes, from_meetings if meetings is not None else None)
    rows = compare(
        window,
        reference,
        window_total,
        max(reference_total - window_total, 1),
        stopwords,
        min_count,
        limit,
        floor=floor,
        rank="log_dice",
        dispersion=spread,
        extra=lambda word, count: {
            "log_dice": round(
                log_dice(count, occurrences, max(reference.get(word, 0), count)), 3
            )
        },
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


def _stratum(key: object) -> tuple:
    """One group key as a tuple, however many columns it was grouped on."""
    return key if isinstance(key, tuple) else (key,)


def matched_control(
    frame: pd.DataFrame,
    flag: str | pd.Series,
    keys: list[str],
    seed: int = 20_260_807,
) -> MatchedPairs:
    """One non-target speech per target, from the same stratum.

    Sampling is without replacement inside a stratum, so no control speech is
    counted twice. Where a stratum holds fewer non-targets than targets — a
    debate in which almost everyone said the word — the shortfall is recorded
    and returned, because a control set that quietly under-covers the crisis
    years would bias the keyness table towards exactly those years.

    `flag` names a boolean column or is a boolean Series aligned to `frame`.
    The second form is what `lib.keyness` uses to make one speaker the target:
    "this delegation" is not a column of the corpus and adding one per speaker
    would mean a hundred and thirty-three passes writing a hundred and
    thirty-three columns, but it is the same pairing either way — which is the
    point of it being this function rather than a second one.
    """
    rng = np.random.default_rng(seed)
    mask = frame[flag] if isinstance(flag, str) else flag
    targets = frame[mask]
    pool = frame[~mask]
    # A list of one column is unwrapped, and both sides are keyed through
    # `_stratum` regardless. Grouping by `["stratum"]` gives a scalar from
    # `.groups` and a one-tuple from iteration — pandas deprecates the first and
    # will change it — so the two lookups silently miss each other and every
    # stratum comes back empty, which reads as "no comparable speech exists"
    # rather than as a bug.
    by = keys[0] if len(keys) == 1 else keys
    available = {
        _stratum(key): list(idx) for key, idx in pool.groupby(by, sort=True).groups.items()
    }

    picked_targets: list = []
    picked_controls: list = []
    short: list[tuple[tuple, int, int]] = []
    for key, group in targets.groupby(by, sort=True):
        wanted = len(group)
        candidates = available.get(_stratum(key), [])
        take = min(wanted, len(candidates))
        if take < wanted:
            short.append((_stratum(key), wanted, take))
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


def definitional_pairs(lex: Lexicon) -> list[dict[str, str]]:
    """Pairs of terms whose co-occurrence is written into the lexicon itself.

    Three ways a pair can be definitional rather than observed. A term declared
    `nested_under` another matches inside its parent's span, so the two always
    co-occur. A term declared `anchor: sentence` is counted only where the
    sentence also says `genocid*`, so it cannot appear in a speech that no
    `genocid*` term appears in: its edge to `genocide` and to `genocidaires` is
    an artefact of the anchor, and it is the strongest of the three, because the
    anchor guarantees the co-occurrence in the same *sentence*. And a term whose
    pattern *contains* another term — before v4, `denial`'s pattern held
    `genocid`, so "denying the genocide" was a `genocide` hit by construction —
    co-occurs with it for the same reason, though nothing in the config says so.
    The third case is found by running each term's regex over the other's
    declared `examples`: an example is the config's own statement of what the
    pattern is for, so a second term matching it is a second term matching by
    definition. Every suppressed pair is returned with its reason, so the
    artefact can list what the graph does not draw and say why.
    """
    pairs: list[dict[str, str]] = []
    active = list(lex.active)
    # The terms the anchor is made of: those every one of whose examples is
    # itself a whole `ANCHOR_RE` match, which is `genocide` and `genocidaires`
    # and not `genocide_convention`, whose examples merely contain the word.
    # Derived from the config rather than named here, so splitting the node
    # word again does not leave a hard-coded pair behind.
    anchoring = {
        term.name
        for term in active
        if term.examples and all(ANCHOR_RE.fullmatch(ex) for ex in term.examples)
    }
    for i, left in enumerate(active):
        for right in active[i + 1 :]:
            if left.nested_under == right.name or right.nested_under == left.name:
                pairs.append(
                    {"source": left.name, "target": right.name, "reason": "nested"}
                )
                continue
            anchored = next(
                (
                    (a, b)
                    for a, b in ((left, right), (right, left))
                    if a.anchor is not None and b.name in anchoring
                ),
                None,
            )
            if anchored is not None:
                a, b = anchored
                pairs.append(
                    {
                        "source": a.name,
                        "target": b.name,
                        "reason": (
                            f"`{a.name}` is anchored: it is counted only in a sentence "
                            f"that also matches `{b.name}`"
                        ),
                    }
                )
                continue
            for a, b in ((left, right), (right, left)):
                hit = next((ex for ex in b.examples if a.regex.search(ex)), None)
                if hit is not None:
                    pairs.append(
                        {
                            "source": a.name,
                            "target": b.name,
                            "reason": f"`{a.name}` matches `{b.name}`'s example “{hit}”",
                        }
                    )
                    break
    return pairs


def pmi_network(
    frame: pd.DataFrame, lex: Lexicon, min_speeches: int = 20
) -> list[dict[str, object]]:
    """Pointwise mutual information between lexicon terms, at speech level.

    Two terms are linked when the same intervention uses both. Normalised PMI
    is carried alongside the raw value: PMI is unbounded and rewards rarity, so
    a term appearing in thirty speeches would otherwise own the graph. Pairs
    :func:`definitional_pairs` names are never drawn: their co-occurrence is a
    fact about the lexicon, not about the speeches.
    """
    total = len(frame)
    if total == 0:
        return []

    names = [t.name for t in lex.active]
    present = {name: frame[f"{HAS}{name}"].to_numpy() for name in names}
    counts = {name: int(present[name].sum()) for name in names}
    definitional = {
        frozenset((pair["source"], pair["target"])) for pair in definitional_pairs(lex)
    }

    edges = []
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            if frozenset((left, right)) in definitional:
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
