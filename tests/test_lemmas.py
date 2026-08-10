"""The lemma layer's alignment, storage and audit table.

spaCy lives in `requirements-cluster.txt` and is installed only on the cluster,
so the tagger is faked here. That is not a gap: the tagger's job is to return
`(start, end, lemma)` spans, and every way this can go wrong afterwards is in the
code below.

The failure being guarded against is specific and quiet. If a lemma sequence ends
up one entry short, nothing raises — the counts simply shift by one token, every
collocate window in that speech moves, and the table that comes out looks
entirely reasonable. So the invariant is checked from both ends: `align` must
emit exactly one lemma per token `lexical.tokenise` finds, and `tokens` must
refuse a stored row that does not match.
"""

from __future__ import annotations

import pytest
from lib import lemmas, lexical


def spans(text: str, mapping: dict[str, str]) -> list[tuple[int, int, str]]:
    """Fake tagger output: whitespace tokens, lemmatised by lookup.

    Deliberately a *different* tokenisation from TOKEN_RE — it keeps punctuation
    attached — because that is the real situation the offset lookup exists to
    survive.
    """
    out = []
    position = 0
    for chunk in text.split(" "):
        if chunk:
            stripped = chunk.strip(".,;:!?")
            out.append((position, position + len(chunk), mapping.get(stripped.lower(), stripped)))
        position += len(chunk) + 1
    return out


# --- Alignment -------------------------------------------------------------


def test_one_lemma_per_token() -> None:
    text = "The Council condemns the killings"
    result = lemmas.align(text, spans(text, {"killings": "killing", "condemns": "condemn"}))
    assert result.aligned
    assert len(result.lemmas) == len(lexical.tokenise(text).words)


def test_lemmas_replace_the_surface_forms() -> None:
    text = "The Council condemns the killings"
    result = lemmas.align(text, spans(text, {"killings": "killing", "condemns": "condemn"}))
    assert result.lemmas == ["the", "council", "condemn", "the", "killing"]


def test_a_differently_tokenised_tagger_still_aligns() -> None:
    """The tagger keeps punctuation attached; TOKEN_RE strips it. The lookup is
    by character offset precisely so the two need not agree on boundaries."""
    text = "Genocide, and crimes against humanity."
    result = lemmas.align(text, spans(text, {"genocide": "genocide", "crimes": "crime"}))
    assert result.aligned
    assert result.lemmas == ["genocide", "and", "crime", "against", "humanity"]


def test_an_uncovered_token_keeps_its_surface_form() -> None:
    """A local fallback, not a shift: guessing a position would move every
    window after it."""
    text = "council condemns killings"
    result = lemmas.align(text, [(0, 7, "council")])
    assert result.lemmas == ["council", "condemns", "killings"]
    assert result.aligned


def test_an_empty_lemma_falls_back_rather_than_breaking_the_row() -> None:
    text = "council condemns"
    result = lemmas.align(text, [(0, 7, "council"), (8, 16, "   ")])
    assert result.lemmas == ["council", "condemns"]


def test_a_lemma_containing_a_space_falls_back() -> None:
    """The stored form is space-joined; a lemma with a space in it would silently
    add a token on the way back."""
    text = "council condemns"
    result = lemmas.align(text, [(0, 7, "council"), (8, 16, "condemn it")])
    assert result.lemmas == ["council", "condemns"]
    assert len(lemmas.decode(lemmas.encode(result.lemmas))) == 2


def test_a_speech_whose_length_changes_under_lowercasing_is_refused() -> None:
    """Turkish dotted capital I lowercases to two code points, which would put
    every offset after it out by one."""
    text = "İstanbul council"
    assert len(text.lower()) != len(text)
    result = lemmas.align(text, spans(text, {}))
    assert not result.aligned
    assert result.lemmas == lexical.tokenise(text).words


def test_alignment_is_positional_not_textual() -> None:
    """Repeated words must not collapse onto one span."""
    text = "crimes and crimes and crimes"
    result = lemmas.align(text, spans(text, {"crimes": "crime"}))
    assert result.lemmas == ["crime", "and", "crime", "and", "crime"]


# --- Storage ---------------------------------------------------------------


def test_encode_and_decode_round_trip() -> None:
    row = ["council", "condemn", "killing"]
    assert lemmas.decode(lemmas.encode(row)) == row


def test_an_empty_row_decodes_to_nothing() -> None:
    """A speech with no countable tokens is not one empty token."""
    assert lemmas.decode("") == []


def test_tokens_carry_lemmas_but_surface_offsets() -> None:
    """The offsets must stay surface: `collocates` finds a node's span by running
    the lexicon regex over the original text."""
    text = "the council condemns the killings"
    row = lemmas.encode(["the", "council", "condemn", "the", "killing"])
    built = lemmas.tokens(text, row)
    assert built.words == ["the", "council", "condemn", "the", "killing"]
    assert built.starts == lexical.tokenise(text).starts


def test_a_stale_row_is_refused_loudly() -> None:
    """The quiet failure this whole module is arranged to prevent."""
    text = "the council condemns the killings"
    with pytest.raises(ValueError, match="re-run 10_lemmatise"):
        lemmas.tokens(text, lemmas.encode(["the", "council"]))


def test_a_lemma_window_still_excludes_the_node() -> None:
    """End to end: lemma counting must not start counting the node itself."""
    text = "the council condemns the genocide in rwanda"
    row = lemmas.encode(
        ["the", "council", "condemn", "the", "genocide", "in", "rwanda"]
    )
    built = lemmas.tokens(text, row)
    start = text.index("genocide")
    context = built.context([(start, start + len("genocide"))], width=2)
    assert "genocide" not in context
    assert "condemn" in context and "rwanda" in context


def test_vocabulary_counts_lemmas() -> None:
    rows = [lemmas.encode(["crime", "crime"]), lemmas.encode(["crime", "council"])]
    counts = lemmas.vocabulary(rows)
    assert counts["crime"] == 3
    assert counts["council"] == 1


# --- The audit table -------------------------------------------------------


def test_mapping_records_only_what_changed() -> None:
    sources = ["crimes and killings"]
    rows = [lemmas.encode(["crime", "and", "killing"])]
    table = lemmas.mapping(sources, rows)
    assert {row["surface"] for row in table} == {"crimes", "killings"}


def test_mapping_is_ordered_by_how_much_text_a_merge_moves() -> None:
    sources = ["crimes crimes crimes killings"]
    rows = [lemmas.encode(["crime", "crime", "crime", "killing"])]
    table = lemmas.mapping(sources, rows)
    assert table[0]["surface"] == "crimes"
    assert table[0]["occurrences"] == 3


def test_mapping_skips_a_misaligned_speech_rather_than_pairing_wrongly() -> None:
    sources = ["crimes and killings", "a b"]
    rows = [lemmas.encode(["crime", "and", "killing"]), lemmas.encode(["only-one"])]
    table = lemmas.mapping(sources, rows)
    assert {row["surface"] for row in table} == {"crimes", "killings"}


def test_mapping_counts_how_many_forms_share_a_lemma() -> None:
    sources = ["crimes crime's"]
    rows = [lemmas.encode(["crime", "crime"])]
    table = lemmas.mapping(sources, rows)
    assert all(row["forms_merged_into_lemma"] >= 2 for row in table)


# --- The stoplist ----------------------------------------------------------


def test_a_stopword_lemmatising_outside_the_stoplist_is_reported() -> None:
    """`is`/`are`/`was` all become `be`. A stoplist without `be` would stop
    filtering them the moment lemmatisation is switched on, and the top of every
    table would fill with auxiliaries."""
    pairs = [{"surface": "was", "lemma": "be", "occurrences": 10}]
    assert lemmas.stopword_check(frozenset({"was", "is"}), pairs) == ["was -> be"]


def test_no_leak_when_the_lemma_is_also_a_stopword() -> None:
    pairs = [{"surface": "was", "lemma": "be", "occurrences": 10}]
    assert lemmas.stopword_check(frozenset({"was", "be"}), pairs) == []


def test_the_shipped_stoplist_survives_the_usual_collapses() -> None:
    """The auxiliaries the English lemmatiser folds together, checked against the
    real config/stopwords.txt rather than a fixture."""
    stopwords = lexical.load_stopwords()
    for surface, lemma in (
        ("is", "be"), ("are", "be"), ("was", "be"), ("were", "be"),
        ("has", "have"), ("had", "have"), ("does", "do"), ("did", "do"),
    ):
        assert surface in stopwords, f"{surface} should be stoplisted"
        assert lemma in stopwords, f"{surface} lemmatises to {lemma}, which must also be"


# --- Tokens the tagger keeps whole but TOKEN_RE splits ---------------------


@pytest.mark.parametrize(
    ("text", "chunk", "tagger_lemma", "expected"),
    [
        # Security Council document symbols: the tagger keeps `S/24232` whole,
        # TOKEN_RE sees only the leading `s`.
        ("resolution S/24232 adopted", "S/24232", "s/24232", "s"),
        # Currency.
        ("spent US$ 40 million", "US$", "us$", "us"),
        # OCR glues a sentence boundary together.
        ("of concern.to us", "concern.to", "concern.to", "concern"),
        # A stray leading mark.
        ("in .the report", ".the", ".the", "the"),
    ],
)
def test_a_lemma_that_is_not_a_word_is_refused(text, chunk, tagger_lemma, expected) -> None:
    """Without this the vocabulary fills with document symbols: a TOKEN_RE token
    that is a strict sub-span of a tagger token inherits the whole thing."""
    start = text.index(chunk)
    result = lemmas.align(text, [(start, start + len(chunk), tagger_lemma)])
    assert expected in result.lemmas
    assert tagger_lemma not in result.lemmas


def test_every_lemma_is_a_word_by_the_projects_own_definition() -> None:
    text = "resolution S/24232 and US$ 40 million of concern.to us"
    result = lemmas.align(text, [(0, len(text), "S/24232")])
    assert all(lexical.TOKEN_RE.fullmatch(lemma) for lemma in result.lemmas)


def test_a_legitimate_lemma_still_replaces_the_surface_form() -> None:
    """The rule must not be so strict that nothing collapses."""
    text = "the killings"
    result = lemmas.align(text, spans(text, {"killings": "killing"}))
    assert result.lemmas == ["the", "killing"]


# --- Tokens TOKEN_RE keeps whole but the tagger splits ---------------------


def test_a_hyphenated_compound_is_not_lemmatised_to_its_first_fragment() -> None:
    """The corpus's most frequent title. spaCy tokenises `Secretary-General` as
    three tokens; TOKEN_RE keeps it as one. Taking the lemma at the token's first
    character would merge 71,703 occurrences into `secretary`."""
    text = "the Secretary-General reported"
    start = text.index("Secretary-General")
    tagger = [
        (start, start + len("Secretary"), "secretary"),
        (start + len("Secretary"), start + len("Secretary-"), "-"),
        (start + len("Secretary-"), start + len("Secretary-General"), "general"),
    ]
    result = lemmas.align(text, tagger)
    assert "secretary-general" in result.lemmas
    assert "secretary" not in result.lemmas


def test_a_partially_covering_tagger_token_is_refused() -> None:
    text = "the well-being of civilians"
    start = text.index("well-being")
    result = lemmas.align(text, [(start, start + len("well"), "well")])
    assert "well-being" in result.lemmas
    assert "well" not in result.lemmas


def test_an_exactly_matching_extent_still_collapses() -> None:
    """The rule must not be so strict that ordinary plurals stop merging."""
    text = "the efforts of countries"
    result = lemmas.align(text, spans(text, {"efforts": "effort", "countries": "country"}))
    assert result.lemmas == ["the", "effort", "of", "country"]
