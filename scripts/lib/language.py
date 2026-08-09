"""Delivery-language classification with source-format uncertainty preserved."""

from __future__ import annotations

import pandas as pd

ENGLISH_INFERRED = "English (inferred, in-person)"
UNKNOWN_VTC = "Unknown (VTC)"
UNKNOWN = "Unknown"


def delivery_language(frame: pd.DataFrame) -> pd.Series:
    """Classify delivery language without treating missing VTC markers as English.

    In the standard in-person verbatim records the Secretariat marks a language
    when it is not English. The separate VTC format carries no such markers, so
    absence there is missing evidence rather than evidence of English.
    """
    required = {"spoken_language", "speech_format"}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"delivery language needs columns: {', '.join(sorted(missing))}")

    spoken = frame["spoken_language"].astype("string")
    result = spoken.copy()
    missing_marker = spoken.isna()
    in_person = frame["speech_format"].astype("string").eq("In-Person")
    vtc = frame["speech_format"].astype("string").eq("VTC")
    result.loc[missing_marker & in_person] = ENGLISH_INFERRED
    result.loc[missing_marker & vtc] = UNKNOWN_VTC
    return result.fillna(UNKNOWN).astype("string")
