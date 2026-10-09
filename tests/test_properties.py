"""Properties that must hold for every input, checked on generated ones.

The fixtures elsewhere test the cases someone thought of. These let
`hypothesis` search for the ones nobody did: bodies built from every term's
own examples, broken by sentence ends and case changes, and counts and
p-values over their whole ranges.

The search is derandomised and keeps no example database, so a run is the
same run on every machine, and what Hypothesis caches goes to a temporary
directory rather than into the working tree.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from conftest import OPENING, make_speeches
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.configuration import set_hypothesis_home_dir
from lib import frames, kwic, lexical, lexicon, occurrences, series, usage

# Hypothesis caches the constants it reads out of the code under test in
# `.hypothesis/` under the working directory, database or not. Set at import,
# because it reads them before any fixture of this module would run.
set_hypothesis_home_dir(Path(tempfile.gettempdir()) / "unsc-debates-hypothesis")

pytestmark = pytest.mark.slow

PROPERTY = settings(derandomize=True, database=None, deadline=None, max_examples=60)

LEX = lexicon.load()
TERMS = sorted(LEX.active, key=lambda term: term.name)

#: What a generated body is made of: every active term's examples, the word an
#: anchored term needs beside it in several cases, and filler.
PIECES = sorted(
    {example for term in TERMS for example in term.examples}
    | {"genocide", "Genocide", "GÉNOCIDE", "génocidaires", "genocidal"}
    | {"the", "Council", "of", "against", "war", "crimes", "humanity", "ethnic", "cleansing"}
    | {"Mr.", "U.N.", "1994", "Rwanda's", "self-defence"}
)
SEPARATORS = [" ", " ", " ", ", ", ". ", "; ", "! ", "? ", "\n", " - ", ": ", "'s "]

bodies = st.lists(
    st.tuples(
        st.one_of(
            st.sampled_from(PIECES),
            st.text(alphabet="abcdeginoéÉ '-.", max_size=8),
        ),
        st.sampled_from(SEPARATORS),
    ),
    max_size=30,
).map(lambda parts: "".join(word + separator for word, separator in parts))


@PROPERTY
@given(body=bodies, term=st.sampled_from(TERMS))
def test_every_count_of_a_term_agrees(body: str, term: lexicon.Term) -> None:
    """03's count, the spans, 08's lines and the enumeration 13-15 share.

    Four routes to "how many times does this speech use the term", and the
    site publishes all four side by side; they may never disagree, on any
    text, for any term, anchored or not.
    """
    speeches = make_speeches([{"text": OPENING + body, "body_start": len(OPENING)}])
    texts = frames.body(speeches)
    spans = term.spans(body)
    counted = int(term.count(pd.Series([body])).iloc[0])
    applied = int(lexicon.apply(texts, LEX)[f"n_{term.name}"].iloc[0])
    lines = list(kwic.extract(speeches, term))
    found = occurrences.enumerate_term(speeches, texts, term)
    assert counted == applied == len(spans) == len(lines) == len(found)
    assert [(line.start, line.end) for line in lines] == [
        (len(OPENING) + start, len(OPENING) + end) for start, end in spans
    ]


counts = st.integers(min_value=0, max_value=100_000)
totals = st.integers(min_value=1, max_value=100_000_000)


@PROPERTY
@given(a=counts, b=counts, target=totals, reference=totals)
def test_g2_changes_sign_when_the_corpora_swap(a, b, target, reference) -> None:
    """Over-represented in one corpus is under-represented in the other, by as much."""
    forward = lexical.log_likelihood(a, b, target, reference)
    backward = lexical.log_likelihood(b, a, reference, target)
    assert forward == pytest.approx(-backward, rel=1e-9, abs=1e-9)


@PROPERTY
@given(a=counts, b=counts, target=totals, reference=totals)
def test_log_ratio_changes_sign_when_the_corpora_swap(a, b, target, reference) -> None:
    forward = lexical.log_ratio(a, b, target, reference)
    backward = lexical.log_ratio(b, a, reference, target)
    assert forward == pytest.approx(-backward, rel=1e-12, abs=1e-12)


@PROPERTY
@given(a=counts, b=counts, target=totals, reference=totals)
def test_g2_points_the_way_the_rates_do(a, b, target, reference) -> None:
    statistic = lexical.log_likelihood(a, b, target, reference)
    if a * reference > b * target:
        assert statistic > 0
    elif a * reference < b * target:
        assert statistic < 0


@PROPERTY
@given(p_values=st.lists(st.floats(min_value=0.0, max_value=1.0), max_size=60))
def test_benjamini_hochberg_is_monotone_and_bounded(p_values: list[float]) -> None:
    adjusted = usage.benjamini_hochberg(p_values)
    assert len(adjusted) == len(p_values)
    assert all(0.0 <= q <= 1.0 for q in adjusted)
    # An adjustment never makes a test look stronger than it was; the slack is
    # for `p * m / m`, which can land one rounding step below `p`.
    assert all(q >= p - 1e-15 for p, q in zip(p_values, adjusted, strict=True))
    # And it keeps the tests in the order their p-values put them.
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    ranked = [adjusted[index] for index in order]
    assert ranked == sorted(ranked)


speeches_strategy = st.lists(
    st.tuples(st.integers(min_value=1990, max_value=1995), bodies, st.integers(0, 3)),
    min_size=1,
    max_size=10,
)


@settings(PROPERTY, max_examples=30)
@given(rows=speeches_strategy)
def test_derived_counts_are_never_negative(rows) -> None:
    """Counts, flags, rates and bounds stay where a count can be, on any corpus."""
    frame = make_speeches(
        {
            "year": year,
            "meeting_symbol": f"S/PV.{year}{meeting}",
            "text": OPENING + body,
            "body_start": len(OPENING),
        }
        for year, body, meeting in rows
    )
    flags = lexicon.apply(frames.body(frame), LEX)
    for term in TERMS:
        count = flags[f"n_{term.name}"]
        assert (count >= 0).all()
        assert (flags[f"{lexicon.HAS}{term.name}"] == (count > 0)).all()
    assert (frame["words"] >= 0).all()

    corpus = pd.concat([frame, flags], axis=1)
    periods = series.period(corpus, "year")
    denominators = series.denominators(corpus, periods)
    measured = series.measure(corpus, periods, denominators, "has_genocide", "n_genocide")
    assert (measured["speeches"] >= 0).all()
    assert (measured["occurrences"] >= measured["speeches"]).all()
    assert (measured["speeches"] <= denominators["speeches"]).all()
    # A period of empty speeches has no words to divide by: no rate, not a negative one.
    assert not (measured["token_rate"] < 0).any()
    low, rate, high = (measured[c] for c in ("speech_rate_low", "speech_rate", "speech_rate_high"))
    assert ((low >= 0) & (low <= rate + 1e-12) & (rate <= high + 1e-12) & (high <= 1)).all()
    for name, (low, high) in series.meeting_bootstrap(
        corpus, periods, denominators.index, {"genocide": "has_genocide"}, resamples=19
    ).items():
        assert name == "genocide"
        assert ((low >= 0) & (low <= high) & (high <= 1)).all()
