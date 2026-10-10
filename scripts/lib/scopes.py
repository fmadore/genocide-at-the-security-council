"""The three R9 reading sets, defined once for every pipeline consumer.

A scope selects speeches to read; it never supplies a denominator.  Keeping
the predicates here prevents the series and meeting exports from quietly
building different versions of "the vocabulary" or "the debate".

The aggregations below cut the same three sets by year and by speaker, which
is what the chronology, the actors view and the concordance draw when a reader
changes scope.  Each cut carries the population it came out of, so every rate
the site publishes under a scope divides by the whole corpus and not by the
reading set.

The same predicates are applied here inside one meeting record, for 09's
meeting export, and to R8's genocide-free comparison corpus, which 04 publishes
beside the term series.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import series

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

#: R8's comparison corpus. These are phrases with determinate legal meanings,
#: not the broader convenience set in the lexicon. A speech enters once when it
#: carries any member and leaves whenever it carries `genocid*` too.
GENOCIDE_FREE_ATROCITY_TERMS = ATROCITY_TERMS


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
    rows: list[dict[str, object]] = []
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


def meeting_scope_counts(speeches: list[dict[str, Any]]) -> dict[str, int]:
    """R9 membership inside one meeting; the debate is all-or-nothing."""
    word = sum("genocide" in speech["hits"] for speech in speeches)
    vocabulary = sum(
        bool({"genocide", *ATROCITY_TERMS} & set(speech["hits"]))
        for speech in speeches
    )
    return {
        "word": word,
        "vocabulary": vocabulary,
        "debate": len(speeches) if word else 0,
    }


def delegations(speeches: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Who sat in a meeting and which vocabulary each delegation used."""
    grouped: dict[str, dict[str, Any]] = {}
    for speech in speeches:
        country = str(speech["country"])
        row = grouped.setdefault(
            country,
            {
                "country": country,
                "iso3": speech["iso3"],
                "group": speech["group"],
                "type": speech["type"],
                "speeches": 0,
                "terms": set(),
            },
        )
        row["speeches"] = int(row["speeches"]) + 1
        row["terms"].update(speech["hits"])
    return [
        {**row, "terms": sorted(row["terms"])}
        for _, row in sorted(grouped.items(), key=lambda item: item[0].casefold())
    ]


def scope_payload(speeches: pd.DataFrame, meta: dict[str, object]) -> dict[str, object]:
    """The small shared-layout artefact, kept out of the 3 MB meeting index.

    It carries the two cuts the consuming views need — by year and by speaker —
    because a scope that changes only a number beside a control is a control
    nothing obeys, and fetching the meeting index to obey it would cost 3 MB on
    every page.
    """
    return {
        "meta": meta,
        "corpus": {
            "speeches": len(speeches),
            "meetings": int(speeches["meeting_symbol"].nunique()),
        },
        "scopes": summary(speeches),
        "years": by_year(speeches),
        "delegations": by_delegation(speeches),
    }


def comparison_corpora(
    speeches: pd.DataFrame,
    periods: pd.Series,
    totals: pd.DataFrame,
    *,
    minimum: int | None = None,
) -> dict[str, dict[str, object]]:
    """Named corpus slices whose membership is a reproducible row predicate.

    This is deliberately not a set measure. It defines which speeches a later
    analysis may read, and counts each qualifying speech once even when it uses
    two or three member phrases. The member term series remain separate.
    """
    columns = [f"has_{term}" for term in GENOCIDE_FREE_ATROCITY_TERMS]
    missing = sorted({"has_genocide", *columns} - set(speeches.columns))
    if missing:
        raise ValueError("Comparison corpus is missing columns: " + ", ".join(missing))
    included = speeches[columns].fillna(False).astype(bool).any(axis=1)
    has_genocide = speeches["has_genocide"].fillna(False).astype(bool)
    working = speeches.assign(has_genocide_free_atrocity=included & ~has_genocide)
    measured = series.measure(
        working,
        periods,
        totals,
        "has_genocide_free_atrocity",
        None,
    )
    if minimum is not None:
        measured = series.withhold_below(measured, totals["speeches"], minimum)
    return {
        "genocide_free_atrocity": {
            "label": "Atrocity vocabulary without genocid*",
            "definition": (
                "Speeches using ethnic cleansing, crimes against humanity or war crimes "
                "and containing no genocid* match."
            ),
            "members": list(GENOCIDE_FREE_ATROCITY_TERMS),
            "excludes": ["genocide"],
            "speeches": measured["speeches"].tolist(),
            "speech_rate": series.rates(measured["speech_rate"], 6),
            "speech_rate_low": series.rates(measured["speech_rate_low"], 6),
            "speech_rate_high": series.rates(measured["speech_rate_high"], 6),
        }
    }
