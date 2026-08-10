"""A lemma layer laid over the corpus, aligned to the tokens 05 already counts.

Inflection splits every table in 05. `killing`, `killed` and `kills` compete for
rows in a collocate list that has room for a hundred; `atrocity` and `atrocities`
each score half the evidence they jointly support. Collapsing them is worth real
resolution — but only if it is done in a way that can be checked and undone.

Three commitments make that possible.

**The surface corpus is never overwritten.** This produces a parallel
representation keyed by ``row_id``. Nothing downstream is obliged to use it, and
the tables built from surface forms remain exactly as they were.

**Alignment is positional, not textual.** For each speech, the lemma sequence has
exactly one entry per token that :func:`lexical.tokenise` finds, in the same
order. That is what lets a lemma sequence be dropped into
:class:`lexical.Tokens` while keeping the *surface* character offsets, so a
collocate window still excludes the node's own span exactly. A speech whose
counts do not line up is recorded as a failure and falls back to its surface
forms rather than being silently misaligned by one token — which would shift
every window in it.

**The collapse is auditable.** `mapping.csv` lists every surface form that
changed, with what it became and how often, most frequent first. A reader who
distrusts a lemma table can see precisely which words were merged into which,
without rerunning anything.

What this deliberately does not do: touch the lexicon. `config/lexicon.yml`
matches surface forms, and docs/PLAN.md §1.1 gates a human audit on those
patterns. Lemmatising before step 03 would fold `genocides` into `genocide`,
move every count, and restart that audit. The lemma layer is built from the
flagged corpus and feeds only the vocabulary side — collocates, keyness, and
07's tokenisation.

spaCy is imported inside :func:`lemmatise`. Everything else here — alignment,
validation, the mapping table, and turning a stored row back into tokens — is
plain Python and is tested without it.
"""

from __future__ import annotations

import bisect
from collections import Counter
from dataclasses import dataclass

from . import lexical

#: Separator for the stored lemma sequence. A TOKEN_RE token can never contain a
#: space and an empty lemma is rejected below, so join/split round-trips exactly.
SEPARATOR = " "

#: Above this share of speeches failing to align, the run is not trustworthy.
#: Failures fall back to surface forms, so a small number is a quality note; a
#: large number means the tokenisations have diverged and the table would be a
#: mixture of two things being presented as one.
MAX_FAILURE_RATE = 0.01


@dataclass(frozen=True)
class Result:
    """One speech's lemmas, and whether they could be trusted.

    ``refused`` counts tokens where the tagger offered a different lemma and the
    rules below turned it down. It is the price of the two conservative rules,
    and it is reported rather than hidden: a reader deciding whether to trust a
    lemma table is entitled to know how often the layer declined to act.
    """

    lemmas: list[str]
    aligned: bool
    refused: int = 0
    changed: int = 0


def align(source: str, spans: list[tuple[int, int, str]]) -> Result:
    """Map lemmas onto the positions `lexical.tokenise` produces.

    ``spans`` is what a tagger returns: ``(start, end, lemma)`` per its own
    token, in character offsets into `source`. For every token 05 would count,
    the lemma of the tagger token covering it is taken. The two tokenisers do
    not have to agree on boundaries — only to cover the same characters — which
    is why the lookup is by offset rather than by position.

    A token no tagger span covers keeps its surface form. That is a silent,
    local fallback by design: it costs one row its collapse, where a positional
    guess would shift every window after it.

    Two rules decide whether a lemma is usable, and the tokenisers disagree in
    both directions.

    **The tagger token must cover the whole surface token.** spaCy splits on
    hyphens where TOKEN_RE keeps them, so `Secretary-General` is three tagger
    tokens against one TOKEN_RE token. Taking the lemma found at the token's
    first character would turn 71,703 occurrences of the corpus's most frequent
    title into `secretary` — a different word, merged with every unrelated
    secretary. When the extents disagree, the surface form stands.

    **The lemma must itself be a word**, by `lexical.TOKEN_RE` end to end. The
    tagger's tokens are also frequently *wider*: it keeps `S/24232`, `US$` and
    OCR-glued `concern.to` whole, where TOKEN_RE sees `s`, `us`, and
    `concern` + `to`. Without this rule those sub-tokens inherit the entire
    tagger token and the vocabulary fills with document symbols.

    Both rules cost the same thing — a missed collapse — and prevent the same
    thing: a word silently becoming a different word. The trade is deliberate.
    Hyphenated compounds therefore keep their surface form and do not collapse;
    `mapping.csv` shows what did.
    """
    # `tokenise` lowercases first. Where lowercasing changes length — a handful
    # of characters in Unicode do — every offset after it would be wrong, so the
    # speech is refused rather than aligned approximately.
    if len(source.lower()) != len(source):
        surface = lexical.tokenise(source)
        return Result(list(surface.words), aligned=False)

    surface = lexical.tokenise(source)
    starts = [span[0] for span in spans]
    lemmas: list[str] = []
    refused = 0
    changed = 0
    for word, position in zip(surface.words, surface.starts, strict=True):
        index = bisect.bisect_right(starts, position) - 1
        lemma = ""
        covered = False
        if 0 <= index < len(spans):
            start, end, candidate = spans[index]
            covered = start <= position < end
            # `end >= position + len(word)`, not `position < end`: the tagger
            # token has to span the whole surface token, or its lemma describes
            # only a fragment of it.
            if start <= position and end >= position + len(word):
                lemma = candidate.strip().lower()
        # Only a well-formed word is accepted; anything else — a document symbol,
        # a currency sign, two words glued by OCR punctuation, or an empty string
        # — leaves the surface form in place. This also guarantees the stored
        # representation round-trips, since a token can contain no space.
        if lemma and lexical.TOKEN_RE.fullmatch(lemma):
            lemmas.append(lemma)
            changed += lemma != word
        else:
            if covered:
                refused += 1
            lemmas.append(word)
    return Result(lemmas, aligned=True, refused=refused, changed=changed)


def encode(lemmas: list[str]) -> str:
    """The stored form: one row per speech, lemmas in token order."""
    return SEPARATOR.join(lemmas)


def decode(row: str) -> list[str]:
    return row.split(SEPARATOR) if row else []


def tokens(source: str, row: str) -> lexical.Tokens:
    """A `Tokens` carrying lemmas as words and the *surface* offsets.

    The offsets must stay surface, because `collocates` finds a node's span by
    running the lexicon regex over the original text. Substituting lemma-derived
    offsets would put the window in the wrong place.
    """
    words = decode(row)
    surface = lexical.tokenise(source)
    if len(words) != len(surface.words):
        raise ValueError(
            f"lemma row has {len(words)} entries for {len(surface.words)} tokens — "
            f"the lemma layer is stale; re-run 10_lemmatise.py"
        )
    return lexical.Tokens(words, surface.starts)


def vocabulary(rows) -> Counter[str]:
    """Corpus-wide lemma frequencies, the reference every lemma rate is read against."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(decode(row))
    return counts


def mapping(sources, rows, limit: int | None = None) -> list[dict[str, object]]:
    """Every surface form that changed, and what it became.

    The audit artefact. Sorted by how much text each merge moves, because that
    is the order in which a reader should spend their scepticism: a wrong lemma
    on a word appearing 40,000 times matters, and one on a hapax does not.
    """
    pairs: Counter[tuple[str, str]] = Counter()
    for source, row in zip(sources, rows, strict=True):
        surface = lexical.tokenise(source).words
        lemmas = decode(row)
        if len(surface) != len(lemmas):
            continue
        for word, lemma in zip(surface, lemmas, strict=True):
            if word != lemma:
                pairs[(word, lemma)] += 1

    collapsed: dict[str, set[str]] = {}
    for (word, lemma), _ in pairs.items():
        collapsed.setdefault(lemma, set()).add(word)

    rows_out = [
        {
            "surface": word,
            "lemma": lemma,
            "occurrences": count,
            "forms_merged_into_lemma": len(collapsed[lemma]) + 1,
        }
        for (word, lemma), count in pairs.most_common(limit)
    ]
    return rows_out


def stopword_check(stopwords: frozenset[str], pairs: list[dict[str, object]]) -> list[str]:
    """Stopwords whose lemma is not itself a stopword.

    `is`, `are`, `was` and `were` all lemmatise to `be`, so a stoplist that omits
    `be` would stop filtering them the moment lemmatisation is switched on and
    the top of every table would fill with auxiliaries. This reports the leak
    rather than silently repairing the stoplist, which is a hand-curated file
    that argues for its own boundary.
    """
    leaks = []
    for row in pairs:
        surface, lemma = str(row["surface"]), str(row["lemma"])
        if surface in stopwords and lemma not in stopwords:
            leaks.append(f"{surface} -> {lemma}")
    return sorted(set(leaks))


def lemmatise(texts: list[str], model: str, batch_size: int = 64, processes: int = 1):
    """Tag and lemmatise, yielding one :class:`Result` per input text.

    Only the tagger path is kept: the parser and entity recogniser cost most of
    the wall-clock and contribute nothing to a lemma. spaCy's lemmatiser needs
    coarse part of speech, which is why `tagger` and `attribute_ruler` stay —
    without them every `meeting` is a noun and every `left` is a direction.

    Imported here rather than at module scope so the tests, CI and steps 00-05
    run without spaCy installed.
    """
    import spacy

    nlp = spacy.load(model, disable=["parser", "ner", "senter"])
    for text, doc in zip(
        texts, nlp.pipe(texts, batch_size=batch_size, n_process=processes), strict=True
    ):
        spans = [(token.idx, token.idx + len(token.text), token.lemma_) for token in doc]
        yield align(text, spans)
