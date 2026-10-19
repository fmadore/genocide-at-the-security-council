"""Adapt the Sakamoto-Matsuoka v5 tables to the pipeline's canonical columns.

Frame to frame, so the adapter's contract is tested without the raw
distribution: textual booleans and integers are parsed and refused when
unknown, the source identifiers become the pipeline's row and meeting keys,
and every source column the adapter renames keeps a `source_` prefix.
`01_build_parquet.py` reads the TSVs, calls these and validates the result
before anything is written.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

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


class RepairError(ValueError):
    """The source does not look the way a repair says it should."""


#: The speaker's own columns, copied from `attributes_from` onto a split-off row.
SPEAKER_COLUMNS = (
    "speaker",
    "affiliation",
    "position",
    "secretary_general",
    "affiliation_cow",
    "cow_ccode",
    "permanent_member",
    "elected_member",
    "state",
    "igo",
    "un_org",
    "ngo",
)


def _one(raw: pd.DataFrame, speech_id: str) -> int:
    matches = raw.index[raw["speech_id"] == speech_id]
    if len(matches) != 1:
        raise RepairError(f"{speech_id}: expected one source row, found {len(matches)}")
    return int(matches[0])


def _words(text: str) -> int:
    return len(text.split())


def drop_duplicate_record(raw: pd.DataFrame, repair: Mapping[str, Any]) -> tuple[pd.DataFrame, dict]:
    """Drop a record whose speeches are, word for word and in order, another's."""
    record, original = str(repair["record_id"]), str(repair["duplicate_of"])
    copy = raw[raw["record_id"] == record].sort_values("order", key=lambda v: v.astype(int))
    kept = raw[raw["record_id"] == original].sort_values("order", key=lambda v: v.astype(int))
    if len(copy) != int(repair["speeches"]):
        raise RepairError(f"{record}: expected {repair['speeches']} speeches, found {len(copy)}")
    if copy["speech"].tolist() != kept["speech"].tolist():
        raise RepairError(f"{record}: its speeches are not a copy of {original}'s")
    return raw.drop(index=copy.index), {
        "repair": "drop_record",
        "record_id": record,
        "duplicate_of": original,
        "speech_ids": copy["speech_id"].tolist(),
        "source_words": int(copy["count"].astype(int).sum()),
    }


def split_speech(raw: pd.DataFrame, repair: Mapping[str, Any]) -> tuple[pd.DataFrame, dict]:
    """Cut a speech where the source missed a turn marker, into two rows.

    The text before `at` stays with the source row. The text after the turn's
    `label` becomes a new row, with the speaker attributes of `attributes_from`.
    The source's word count is shared between the two in proportion to their
    whitespace words, so the corpus total stays the source's.
    """
    speech_id = str(repair["speech_id"])
    row = _one(raw, speech_id)
    text = str(raw.at[row, "speech"])
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != repair["source_sha256"]:
        raise RepairError(f"{speech_id}: the source text is not the one the repair was written for")
    at, label = int(repair["at"]), str(repair["label"])
    if not text.startswith(label, at):
        raise RepairError(f"{speech_id}: no {label!r} at character {at}")
    # The new body starts right after the label, so an offset in it is the old
    # offset minus `at + len(label)`: tools/remap_run_rows.py relies on that.
    head, tail = text[:at].rstrip(), text[at + len(label):].rstrip()
    if not tail or tail[0].isspace():
        raise RepairError(f"{speech_id}: the text after {label!r} must start straight away")

    new = repair["new"]
    if (raw["speech_id"] == new["speech_id"]).any():
        raise RepairError(f"{new['speech_id']} already exists in the source")
    donor = _one(raw, str(new["attributes_from"]))
    if raw.at[donor, "record_id"] != raw.at[row, "record_id"]:
        raise RepairError(f"{new['attributes_from']} is not in {speech_id}'s meeting")

    total = int(raw.at[row, "count"])
    tail_count = round(total * _words(tail) / (_words(head) + _words(tail)))
    added = raw.loc[[row]].copy()
    added.index = [raw.index.max() + 1]
    for column in SPEAKER_COLUMNS:
        added[column] = raw.at[donor, column]
    added["speech_id"] = str(new["speech_id"])
    added["president"] = str(bool(new["president"]))
    added["procedural"] = str(bool(new["procedural"]))
    added["speech"] = tail
    added["count"] = str(tail_count)

    out = raw.copy()
    out.at[row, "speech"] = head
    out.at[row, "count"] = str(total - tail_count)
    out = pd.concat([out, added])
    for moved, order in repair.get("reorder", {}).items():
        out.at[_one(out, str(moved)), "order"] = str(int(order))
    return out, {
        "repair": "split_speech",
        "speech_id": speech_id,
        "new_speech_id": str(new["speech_id"]),
        "at": at,
        "source_words": [total - tail_count, tail_count],
    }


def apply_repairs(raw: pd.DataFrame, repairs: Mapping[str, Any]) -> tuple[pd.DataFrame, list[dict]]:
    """Apply `config/source_repairs.yml` to the source speeches, before adapting.

    Every repair checks that the source is the one it was written for and
    raises :class:`RepairError` if not. Returns the repaired frame, in source
    row order with split-off rows after their meeting's last row, and a log of
    what was done for the step's manifest.
    """
    if repairs.get("schema") != 1:
        raise RepairError("unsupported source_repairs schema")
    log: list[dict] = []
    out = raw.reset_index(drop=True)
    for repair in repairs.get("drop_records") or []:
        out, entry = drop_duplicate_record(out, repair)
        log.append(entry)
    for repair in repairs.get("split_speeches") or []:
        out, entry = split_speech(out, repair)
        log.append(entry)
    position = {speech_id: index for index, speech_id in enumerate(raw["speech_id"])}
    record_end = {record: position[ids.iloc[-1]] for record, ids in raw.groupby("record_id", sort=False)["speech_id"]}
    key = [position.get(s, record_end.get(r, len(position)) + 0.5) for s, r in zip(out["speech_id"], out["record_id"], strict=True)]
    out = out.assign(_key=key).sort_values("_key", kind="stable").drop(columns="_key")
    return out.reset_index(drop=True), log


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
