"""Adapt the Sakamoto-Matsuoka v5 tables to the pipeline's canonical columns.

Frame to frame, so the adapter's contract is tested without the raw
distribution: textual booleans and integers are parsed and refused when
unknown, the source identifiers become the pipeline's row and meeting keys,
and every source column the adapter renames keeps a `source_` prefix.
`01_build_parquet.py` reads the TSVs, calls these and validates the result
before anything is written.
"""

from __future__ import annotations

import pandas as pd

INTEGER_COLUMNS = ("year", "month", "day", "meeting_num")
BOOLEAN_COLUMNS = (
    "president",
    "secretary_general",
    "procedural",
    "permanent_member",
    "elected_member",
    "state",
    "igo",
    "un_org",
    "ngo",
)


def as_boolean(values: pd.Series, name: str) -> pd.Series:
    """Parse Dataverse's textual booleans and refuse unknown values."""
    lowered = values.astype("string").str.lower()
    known = {"true": True, "false": False, "1": True, "0": False}
    unknown = sorted(set(lowered.dropna()) - set(known))
    if unknown:
        raise ValueError(f"{name}: unknown boolean values: {', '.join(unknown[:5])}")
    return lowered.map(known).fillna(False).astype(bool)


def as_integer(values: pd.Series, name: str) -> pd.Series:
    parsed = pd.to_numeric(values, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{name}: {int(parsed.isna().sum())} values are not integers")
    return parsed.astype("int32")


def make_date(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame[["year", "month", "day"]], errors="coerce")


def broad_agenda(values: pd.Series) -> pd.Series:
    """Take the first Repertoire category as the one-valued dashboard facet."""
    first = values.astype("string").str.split(";").str[0].str.strip()
    return first.replace({"Thematic Issues": "Thematic"})


def participant_type(frame: pd.DataFrame) -> pd.Series:
    """Derive explicit, mutually exclusive speaking capacities."""
    result = pd.Series("Guest", index=frame.index, dtype="string")
    member = frame["permanent_member"] | frame["elected_member"]
    result.loc[member] = "Council member"
    result.loc[frame["secretary_general"] | frame["un_org"]] = "UN official"
    result.loc[frame["president"] & ~frame["procedural"]] = "Council President"
    result.loc[frame["procedural"]] = "Procedural"
    return result


def adapt_meetings(raw: pd.DataFrame) -> pd.DataFrame:
    meetings = raw.copy()
    for column in INTEGER_COLUMNS:
        meetings[column] = as_integer(meetings[column], column)
    meetings["closed"] = as_boolean(meetings["closed"], "closed")
    meetings["source_speeches_available"] = as_boolean(meetings["speeches"], "speeches")
    meetings["date"] = make_date(meetings)
    meetings["basename"] = meetings["record_id"]
    meetings["spv"] = meetings["record"]
    meetings["meeting_symbol"] = meetings["record"]
    meetings["agenda_item1"] = broad_agenda(meetings["agenda_categories"])
    meetings["agenda_item_manual"] = meetings["topic"].fillna(meetings["agenda"])
    meetings["source_word_count"] = pd.to_numeric(
        meetings["word_count"], errors="coerce"
    ).astype("Int64")
    meetings = meetings.drop(columns=["speeches", "word_count"])
    return meetings


def adapt_speeches(raw: pd.DataFrame, meetings: pd.DataFrame) -> pd.DataFrame:
    speeches = raw.copy()
    for column in (*INTEGER_COLUMNS, "order", "count"):
        speeches[column] = as_integer(speeches[column], column)
    for column in BOOLEAN_COLUMNS:
        speeches[column] = as_boolean(speeches[column], column)

    meeting_meta = meetings[
        [
            "record_id",
            "record",
            "record_url",
            "agenda_categories",
            "agenda_item1",
            "closed",
        ]
    ]
    speeches = speeches.merge(meeting_meta, on="record_id", how="left", validate="many_to_one")

    speeches["row_id"] = speeches["speech_id"]
    speeches["filename"] = speeches["speech_id"] + ".txt"
    speeches["basename"] = speeches["record_id"]
    speeches["date"] = make_date(speeches)
    speeches["speaker"] = speeches["speaker"].fillna("Unknown speaker")
    speeches["country_org"] = speeches["affiliation"].fillna("Unknown affiliation")
    state_with_cow_name = speeches["state"] & speeches["affiliation_cow"].notna()
    speeches.loc[state_with_cow_name, "country_org"] = speeches.loc[
        state_with_cow_name, "affiliation_cow"
    ]
    speeches["role"] = speeches["position"]
    speeches["participanttype"] = participant_type(speeches)
    speeches["speech_number"] = speeches["order"].astype("int32")
    speeches["tokens"] = speeches["count"].astype("int32")
    speeches["source_word_count"] = speeches["count"].astype("int32")
    speeches["text"] = speeches["speech"].fillna("")
    speeches["n_chars"] = speeches["text"].str.len().astype("int32")
    speeches["document_symbol"] = speeches["record"]
    speeches["meeting_symbol"] = speeches["record"]
    speeches["agenda_item_manual"] = speeches["topic"].fillna(speeches["agenda"])
    for column in ("agenda_item2", "agenda_item3", "agenda_item4"):
        speeches[column] = pd.Series(pd.NA, index=speeches.index, dtype="string")

    # The source contains the English transcript but has already removed the
    # printed form-of-address marker that identifies the language of delivery.
    # "Transcript" deliberately maps to Unknown in lib.language instead of
    # turning every translated intervention into inferred English.
    speeches["speech_format"] = "Transcript"
    speeches["record_speech"] = speeches["speech_id"]

    source_renames = {
        "affiliation": "source_affiliation",
        "president": "source_president",
        "secretary_general": "source_secretary_general",
        "procedural": "source_procedural",
        "affiliation_cow": "source_affiliation_cow",
        "cow_ccode": "source_cow_ccode",
        "permanent_member": "source_permanent_member",
        "elected_member": "source_elected_member",
        "state": "source_state",
        "igo": "source_igo",
        "un_org": "source_un_org",
        "ngo": "source_ngo",
        "closed": "source_closed_meeting",
    }
    speeches = speeches.rename(columns=source_renames)
    speeches = speeches.drop(columns=["speech", "count", "order", "position"])
    return speeches
