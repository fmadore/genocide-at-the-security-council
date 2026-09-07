"""The three R9 reading sets, defined once for every pipeline consumer.

A scope selects speeches to read; it never supplies a denominator.  Keeping
the predicates here prevents the series and meeting exports from quietly
building different versions of "the vocabulary" or "the debate".

The aggregations below cut the same three sets by year and by speaker, which
is what the chronology, the actors view and the concordance draw when a reader
changes scope.  Each cut carries the population it came out of, so every rate
the site publishes under a scope divides by the whole corpus and not by the
reading set.
"""

from __future__ import annotations

import pandas as pd

ATROCITY_TERMS = (
    "ethnic_cleansing",
    "crimes_against_humanity",
    "war_crimes",
)

SCOPE_DEFINITIONS = (
    ("word", "The word", "Speeches containing a genocid* match."),
    (
        "vocabulary",
        "The vocabulary",
        "Speeches containing genocid*, ethnic cleansing, crimes against humanity or war crimes.",
    ),
    (
        "debate",
        "The debate",
        "Every speech in a meeting where at least one speech contains a genocid* match.",
    ),
)


def speech_masks(speeches: pd.DataFrame) -> dict[str, pd.Series]:
    """Return aligned membership masks for R9's three nested reading sets."""
    required = [
        "meeting_symbol",
        "has_genocide",
        *(f"has_{term}" for term in ATROCITY_TERMS),
    ]
    missing = [column for column in required if column not in speeches]
    if missing:
        raise ValueError(f"scope predicate is missing column(s): {', '.join(missing)}")

    word = speeches["has_genocide"].fillna(False).astype(bool)
    atrocity = (
        speeches[[f"has_{term}" for term in ATROCITY_TERMS]]
        .fillna(False)
        .astype(bool)
        .any(axis=1)
    )
    word_meetings = set(speeches.loc[word, "meeting_symbol"])
    return {
        "word": word,
        "vocabulary": word | atrocity,
        "debate": speeches["meeting_symbol"].isin(word_meetings),
    }


def _require(speeches: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in speeches]
    if missing:
        raise ValueError(f"scope aggregation is missing column(s): {', '.join(missing)}")


def by_year(speeches: pd.DataFrame) -> list[dict[str, object]]:
    """Each year's own corpus denominator, with the three reading sets beside it.

    The denominator is written next to the sets rather than left to be derived
    from them, so a consumer cannot divide one reading set by another and call
    the result a rate.  That is the trap R9 names, and the artefact refuses to
    hold the shape that invites it.
    """
    _require(speeches, ["year"])
    masks = speech_masks(speeches)
    held = speeches.groupby("year").size().sort_index()
    counted = {key: speeches.loc[mask].groupby("year").size() for key, mask in masks.items()}
    return [
        {
            "year": int(year),
            "held": int(total),
            "scopes": {key: int(counted[key].get(year, 0)) for key in masks},
        }
        for year, total in held.items()
    ]


def by_delegation(speeches: pd.DataFrame) -> list[dict[str, object]]:
    """Reading-set membership per speaker, against that speaker's own total.

    A speaker with nothing in any of the three sets is left out rather than
    written as three zeroes: 708 speakers sat in this corpus, this artefact is
    fetched on every page, and an absent speaker contributes nothing anywhere.
    """
    _require(speeches, ["country_org"])
    masks = speech_masks(speeches)
    held = speeches.groupby("country_org").size()
    counted = {
        key: speeches.loc[mask].groupby("country_org").size() for key, mask in masks.items()
    }
    rows = []
    for country in sorted(held.index, key=lambda name: str(name).casefold()):
        sets = {key: int(counted[key].get(country, 0)) for key in masks}
        if not any(sets.values()):
            continue
        rows.append(
            {"country_org": str(country), "held": int(held[country]), "scopes": sets}
        )
    return rows


def summary(speeches: pd.DataFrame) -> list[dict[str, object]]:
    """Counts for the scope control, always against the complete input corpus."""
    masks = speech_masks(speeches)
    definitions = {key: (label, definition) for key, label, definition in SCOPE_DEFINITIONS}
    rows = []
    for key in ("word", "vocabulary", "debate"):
        mask = masks[key]
        label, definition = definitions[key]
        rows.append(
            {
                "id": key,
                "label": label,
                "definition": definition,
                "speeches": int(mask.sum()),
                "meetings": int(speeches.loc[mask, "meeting_symbol"].nunique()),
            }
        )
    return rows
