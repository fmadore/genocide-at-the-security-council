"""The three R9 reading sets, defined once for every pipeline consumer.

A scope selects speeches to read; it never supplies a denominator.  Keeping
the predicates here prevents the series and meeting exports from quietly
building different versions of "the vocabulary" or "the debate".
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
