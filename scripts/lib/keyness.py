"""One delegation's words against the Council's, with the occasion held constant.

`05_lexical.py` asks what distinguishes *genocide-bearing* speeches from
comparable speeches that do not use the word. This module asks the other
question `docs/PLAN.md` §3 wants for an actor profile: what distinguishes *this
speaker's* speeches from what everyone else said in the same debate.

The comparison is the same shape as 05's and deliberately reuses its parts —
:func:`lib.lexical.matched_control` for the pairing and :func:`lib.lexical.compare`
for the statistic — because a keyness computed a second way here would
eventually disagree with the one 05 publishes and nothing in either artefact
would say which was wrong. What changes is only what the target is.

Three decisions belong to this module rather than to the script.

**The control is drawn from the same debate, not from the rest of the corpus.**
A delegation that speaks mostly about the Middle East is not distinguished by
the vocabulary of the Middle East, and an unmatched comparison would say it was.
Each of a speaker's speeches is paired with one from the same year, the same
agenda item and the same speaker group, given by someone else. What survives
that is the speaker's own diction; what the matching removes was the occasion.
Both readings are published, per speaker, for the reason 05 gives: the unmatched
table is not a result, it is the thing the matching is meant to improve on, and
shipping the pair is the only way a reader can see whether it did.

**Matching on speaker group narrows the pool on purpose.** A P5 member's control
speeches can only come from the other four, because institutional position is
part of what makes a speech comparable rather than part of what makes a speaker
distinctive. It is also the reason coverage is published per speaker rather than
once for the table: it varies with how crowded a speaker's strata are, and a
speaker matched at 40% is being described by a biased half of its own speeches.

**The corpus is counted once, into a matrix.** A speaker's token counts are then
a sum over rows rather than a re-read of its text, which is what makes the
stability battery affordable: without it, twenty seeds across every eligible
speaker means tokenising fifty-eight million words forty times over. The counts
are built with :data:`lib.lexical.TOKEN_RE`, so they are identical to what
:func:`lib.lexical.vocabulary` would have returned — asserted in
`tests/test_keyness.py` rather than assumed here.
"""

from __future__ import annotations

from array import array
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import actors, lexical

#: What a control speech has to match on — 05's list, unchanged. Year holds the
#: occasion constant, agenda item the subject, speaker group the institutional
#: position from which a speech is given.
MATCH_ON: list[str] = ["year", "agenda_item_manual", "speaker_group"]

#: Matched pairs a speaker needs before its keywords are published.
#:
#: Inherited from :data:`lib.actors.MIN_SPEECHES` rather than derived, and the
#: difference is worth stating because every other minimum in this project is
#: derived. That one is the denominator at which a *zero* means "quieter than
#: the Council"; this table computes no rate and that argument does not transfer.
#: What justifies the number here is consistency: the actor view withholds a
#: speaker's rates below 100 speeches, and a keyness table for a speaker whose
#: rates are withheld would put a profile of a delegation beside a blank where
#: its rate should be. The statistical guard on this table is per row rather
#: than per speaker — :data:`lib.lexical.MIN_COUNT` requires five occurrences
#: before a word is reported at all, which is the classical expected-count floor
#: that G² needs.
#:
#: It is counted in *pairs*, not in speeches, because pairs are what the table is
#: computed from: a speaker with 300 speeches and 60 partners has a 60-speech
#: comparison whatever its denominator says.
MIN_PAIRS = actors.MIN_SPEECHES

#: Share of a speaker's own speeches the matching must have found partners for.
#:
#: The second gate, and it exists because the first one does not catch the case
#: that made it necessary. The UN Secretariat gave 4,709 speeches and the pairing
#: found partners for 123 of them — it is the only speaker in its speaker group,
#: so a control from the same group is very nearly unavailable by construction.
#: Those 123 pairs clear :data:`MIN_PAIRS` comfortably, and a table built on them
#: would read as the Secretariat's diction while resting on 2.6% of its record —
#: and not a random 2.6%, but exactly the strata where a second UN speaker
#: happened to appear.
#:
#: Half is a declared line rather than a derived one, and it is worth being plain
#: about that: bias from partial matching is continuous, and no threshold on it
#: is a discovery. What the number says is that a published comparison rests on
#: the majority of a speaker's own speeches. Coverage is written for every
#: speaker either way, so a reader can disagree with the line and see what sits
#: on both sides of it.
MIN_COVERAGE = 0.5

#: Rows kept per speaker table. Smaller than 05's 100 because a per-speaker table
#: is read as a profile rather than as a lexicon, and because the file carries
#: two tables for each of a hundred-odd speakers.
LIMIT = 40

#: Agenda items listed per speaker. The rest are summed into `other`, so the
#: shares always total one and a reader can see how much was folded away.
AGENDA_ITEMS = 8


# --- The corpus as counts --------------------------------------------------


def _gather(indptr: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Positions of every (document, term) entry belonging to `rows`.

    The loop-free form of ``concatenate([arange(indptr[r], indptr[r+1]) ...])``.
    Written out because the readable version allocates one array per document,
    and this is called once per speaker per seed.
    """
    starts = indptr[rows]
    lengths = indptr[rows + 1] - starts
    total = int(lengths.sum())
    if total == 0:
        return np.empty(0, dtype=np.int64)
    out_starts = np.zeros(len(rows), dtype=np.int64)
    np.cumsum(lengths[:-1], out=out_starts[1:])
    return np.arange(total) - np.repeat(out_starts, lengths) + np.repeat(starts, lengths)


@dataclass(frozen=True)
class DocumentTerms:
    """The corpus as (document, term, count) triples, in compressed row form.

    `indptr[i]:indptr[i + 1]` is document *i*'s slice of `terms` and `counts`.
    Row numbers are positions in the frame the matrix was built from, which is
    why :func:`build` refuses anything but a positional index: a matrix that
    silently disagreed with its frame about which row is which would produce a
    perfectly plausible table for the wrong speaker.
    """

    words: list[str]
    indptr: np.ndarray
    terms: np.ndarray
    counts: np.ndarray

    @property
    def documents(self) -> int:
        return len(self.indptr) - 1

    @property
    def entries(self) -> int:
        return len(self.terms)

    def totals(self, rows: np.ndarray) -> np.ndarray:
        """Summed counts per vocabulary id over the given row positions."""
        positions = _gather(self.indptr, np.asarray(rows, dtype=np.int64))
        if len(positions) == 0:
            return np.zeros(len(self.words), dtype=np.int64)
        return np.bincount(
            self.terms[positions],
            weights=self.counts[positions],
            minlength=len(self.words),
        ).astype(np.int64)

    def counter(self, rows: np.ndarray) -> Counter[str]:
        """The same sum as a `Counter`, which is what `lexical.compare` reads."""
        totals = self.totals(rows)
        present = np.flatnonzero(totals)
        return Counter({self.words[i]: int(totals[i]) for i in present})


def build(texts) -> DocumentTerms:
    """Count every document once, into the compressed form above.

    `array` rather than a list of Python ints: twenty-six million entries is
    a hundred megabytes as int32 and roughly a gigabyte as boxed integers.
    """
    vocabulary: dict[str, int] = {}
    indptr = array("q", [0])
    terms = array("i")
    counts = array("i")
    for source in texts:
        for word, count in Counter(lexical.TOKEN_RE.findall(source.lower())).items():
            identifier = vocabulary.get(word)
            if identifier is None:
                identifier = vocabulary[word] = len(vocabulary)
            terms.append(identifier)
            counts.append(count)
        indptr.append(len(terms))
    return DocumentTerms(
        words=list(vocabulary),
        indptr=np.frombuffer(indptr, dtype=np.int64).copy(),
        terms=np.frombuffer(terms, dtype=np.int32).copy(),
        counts=np.frombuffer(counts, dtype=np.int32).copy(),
    )


# --- Strata ----------------------------------------------------------------


def strata(frame: pd.DataFrame, keys: list[str] = MATCH_ON) -> pd.Series:
    """One integer per distinct combination of the matching keys.

    :func:`lib.lexical.matched_control` groups the corpus once per speaker per
    seed, and grouping a hundred thousand rows by three object columns that many
    times is most of the run. Factorising them once is the same partition — a
    test asserts the pairing is identical either way — computed on integers.

    Missing values are given their own code rather than dropping out, because a
    speech with no hand-coded agenda item is still comparable to another speech
    with no hand-coded agenda item, and dropping it would quietly shrink the
    denominator the coverage figure is read against.
    """
    missing = [key for key in keys if key not in frame.columns]
    if missing:
        raise KeyError(f"strata needs {', '.join(missing)}")
    joined = frame[keys].astype("string").fillna("\x00").agg("\x1f".join, axis=1)
    codes, _ = pd.factorize(joined, use_na_sentinel=False)
    return pd.Series(codes, index=frame.index, name="stratum")


# --- One speaker -----------------------------------------------------------


@dataclass(frozen=True)
class Pairing:
    """How much of a speaker's record the matching could actually compare."""

    pairs: int
    held: int
    short_strata: int
    shortfall: int

    @property
    def coverage(self) -> float:
        return self.pairs / self.held if self.held else 0.0


def self_reference(name: str) -> frozenset[str]:
    """Tokens of a speaker's own canonical name.

    Every delegation says its own name constantly — "France believes", "the
    United Kingdom welcomes" — so the top of every table would otherwise be
    occupied by the one word that distinguishes a speaker for no reason worth
    reading. The rows are **marked, never removed**: a suppressed word is a
    number a reader cannot check, and how often a delegation refers to itself is
    a fact about its register rather than noise.

    Deliberately mechanical, and therefore partial. It catches `russian` and
    `federation` for the Russian Federation and `kingdom` for the United Kingdom,
    because those words are in the name; it does not catch `french`, `chinese` or
    `beijing`, because a demonym list is a hand-built artefact and a
    half-complete one would make the flag look authoritative. The artefact says
    which rule was applied so a reader knows what the absence of a mark means.
    """
    return frozenset(lexical.TOKEN_RE.findall(name.lower()))


def pair_speaker(
    frame: pd.DataFrame, mask: pd.Series, stratum: str, seed: int
) -> tuple[pd.Index, pd.Index, Pairing]:
    """Target and control rows for one speaker, plus what the matching cost."""
    matched = lexical.matched_control(frame, mask, [stratum], seed)
    return (
        matched.target_index,
        matched.control_index,
        Pairing(
            pairs=matched.matched,
            held=matched.wanted,
            short_strata=len(matched.short_strata),
            shortfall=sum(wanted - found for _, wanted, found in matched.short_strata),
        ),
    )


def speaker_keyness(
    frame: pd.DataFrame,
    matrix: DocumentTerms,
    name: str,
    stratum: str,
    reference: Counter[str],
    reference_total: int,
    stopwords: frozenset[str],
    *,
    seed: int,
    limit: int = LIMIT,
    repetitions: int = 0,
    minimum: int = MIN_PAIRS,
    min_coverage: float = MIN_COVERAGE,
) -> dict[str, object]:
    """One speaker's keywords against a matched control, and against the corpus.

    `reference` is the whole corpus's counts; the unmatched table is computed
    against it exactly as 05 does, so the two artefacts' unmatched columns are
    the same measurement made on different targets.

    `repetitions` re-runs the whole pairing on consecutive seeds — not only the
    sampling of controls, because a short stratum also decides *which* targets
    are kept, and a stability figure that held the target set fixed would report
    less movement than the table actually has.

    Below either gate the tables are **written as null rather than left out**.
    The two are not the same downstream: §7 of `docs/PLAN.md` records a figure
    published as `0.00 per 100,000 words` because a consumer read an absent key
    through `?? 0`, and the fix was for the artefact to say what it withheld.
    Every key a sufficient speaker has, an insufficient one has too, holding
    null — and `withheld_because` names which gate closed, because "too few
    speeches to compare" and "compared on an unrepresentative part of the record"
    are different objections and a consumer that reports one for the other is
    telling a reader something untrue.
    """
    mask = frame["country_org"] == name
    targets, controls, pairing = pair_speaker(frame, mask, stratum, seed)
    withheld_because = [
        *(["pairs"] if pairing.pairs < minimum else []),
        *(["coverage"] if pairing.coverage < min_coverage else []),
    ]
    described: dict[str, object] = {
        "pairs": pairing.pairs,
        "held": pairing.held,
        "coverage": round(pairing.coverage, 4),
        "short_strata": pairing.short_strata,
        "shortfall": pairing.shortfall,
        "sufficient": not withheld_because,
        "withheld_because": withheld_because,
    }
    if withheld_because:
        return {
            **described,
            "target_tokens": None,
            "control_tokens": None,
            "keywords": None,
            "keywords_unmatched": None,
        }

    target_counts = matrix.counter(targets.to_numpy())
    control_counts = matrix.counter(controls.to_numpy())
    target_total = sum(target_counts.values())
    control_total = sum(control_counts.values())

    # `compare` subtracts the target from its reference, so the control counts go
    # in as-is: the two corpora are disjoint by construction.
    rows = lexical.compare(
        target_counts,
        target_counts + control_counts,
        target_total,
        control_total,
        stopwords,
        limit=limit,
    )
    unmatched = lexical.compare(
        target_counts,
        reference,
        target_total,
        max(reference_total - target_total, 1),
        stopwords,
        limit=limit,
    )
    own = self_reference(name)
    for row in (*rows, *unmatched):
        row["self_reference"] = str(row["word"]) in own

    payload: dict[str, object] = {
        **described,
        "target_tokens": target_total,
        "control_tokens": control_total,
        "keywords": rows,
        "keywords_unmatched": unmatched,
    }
    if repetitions:
        payload["stability"] = _stability(
            frame,
            matrix,
            mask,  # the same speaker, re-paired; see `_stability`
            stratum,
            [str(row["word"]) for row in rows],
            seed=seed,
            repetitions=repetitions,
        )
    return payload


def _stability(
    frame: pd.DataFrame,
    matrix: DocumentTerms,
    mask: pd.Series,
    stratum: str,
    words: list[str],
    *,
    seed: int,
    repetitions: int,
) -> dict[str, object]:
    """Where each keyword's effect size lands across consecutive seeds.

    The interval is the interesting number rather than the median: a word whose
    log ratio runs from +0.4 to +3.1 depending on which control speeches were
    drawn is a property of the draw, and a table that showed only its central
    value would present it as a property of the speaker.

    **The published draw is one of the draws.** The seeds run from `seed`, not
    from `seed + 1`, so the first repetition reproduces the pairing the
    `keywords` table was computed from. That costs one redundant pairing and
    buys the only property that makes the interval readable beside the row: an
    interval drawn from *other* seeds can exclude the very number it is printed
    next to, and a reader meeting `+1.33 [+1.38, +1.53]` has been shown what
    looks exactly like an error. Both figures now come from one sample.
    """
    effects: dict[str, list[float]] = {word: [] for word in words}
    coverages: list[float] = []
    for repetition in range(repetitions):
        targets, controls, pairing = pair_speaker(frame, mask, stratum, seed + repetition)
        coverages.append(pairing.coverage)
        target_counts = matrix.counter(targets.to_numpy())
        control_counts = matrix.counter(controls.to_numpy())
        target_total = sum(target_counts.values())
        control_total = sum(control_counts.values())
        for word in words:
            effects[word].append(
                lexical.log_ratio(
                    target_counts.get(word, 0),
                    control_counts.get(word, 0),
                    target_total,
                    control_total,
                )
            )
    return {
        "repetitions": repetitions,
        "coverage_min": round(min(coverages), 4) if coverages else 0.0,
        "coverage_max": round(max(coverages), 4) if coverages else 0.0,
        # `p05`/`p95` match what 05 reports for the whole-corpus keyness, so the
        # two artefacts can be read against each other. `low`/`high` are the
        # observed range, and they are here because the percentiles are not
        # enough for a figure that prints one draw beside its interval: at ten
        # draws the 5th percentile is interpolated *above* the smallest value,
        # so a published draw that happens to be the extreme of its own sample
        # would sit outside a bracket printed next to it. The range cannot do
        # that, and it is the honest summary at this many repetitions anyway.
        "keyword_log_ratio": [
            {
                "word": word,
                "median": round(float(np.median(values)), 3),
                "low": round(float(np.min(values)), 3),
                "high": round(float(np.max(values)), 3),
                "p05": round(float(np.quantile(values, 0.05)), 3),
                "p95": round(float(np.quantile(values, 0.95)), 3),
            }
            for word, values in effects.items()
        ],
    }


# --- Agenda composition ----------------------------------------------------


def agenda_composition(
    speeches: pd.DataFrame, name: str, items: int = AGENDA_ITEMS
) -> dict[str, object]:
    """What a speaker spoke about, as shares of its own speeches.

    The other half of §3's bullet, and the context its keyness table has to be
    read against: the matching holds the agenda item constant, so this says what
    was held constant. A delegation heard mostly on one file has a keyness table
    computed almost entirely within that file's debates.

    Items outside the top `items` are summed into one `other` row rather than
    dropped, so the shares total one and the tail is visible as a quantity.
    """
    own = speeches[speeches["country_org"] == name]
    held = len(own)
    counts = own["agenda_item_manual"].fillna("(unlabelled)").value_counts()
    top = counts.head(items)
    return {
        "held": held,
        "items": int(counts.size),
        "top": [
            {"item": str(item), "speeches": int(count), "share": round(count / held, 4)}
            for item, count in top.items()
        ],
        "other": {
            "speeches": int(counts.iloc[items:].sum()),
            "share": round(float(counts.iloc[items:].sum()) / held, 4) if held else 0.0,
        },
        "concentration": round(float(top.iloc[: min(3, len(top))].sum()) / held, 4)
        if held
        else 0.0,
    }
