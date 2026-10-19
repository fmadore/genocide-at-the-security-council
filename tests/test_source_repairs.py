"""The source repairs: what 01 does to the frame, and what follows from it.

`config/source_repairs.yml` drops duplicated records and copied speeches, trims
a speech that runs on past its record, and splits one that ran on into the next
turn. These tests hold the frame-level repair to the
checks it promises (a copy is a copy, a text is the one the rule was written
for), the run-row table to changing identities and never labels, and the
semantic map to leaving the repaired speeches out without moving anyone's
neighbours to the wrong shard.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest
import yaml
from lib import model_runs, sakamoto, semantic_release
from lib.paths import SOURCE_REPAIRS

LABEL = "The President (translated from French/: "
EBAN = "We restate the principles of our policy."
MALI = "As the list of speakers is now exhausted, I speak for Mali. We support the draft."
SPLIT_TEXT = f"{EBAN}\n{LABEL}{MALI}"


def row(speech_id: str, order: int, speech: str, **extra: str) -> dict[str, str]:
    base = {
        "speech_id": speech_id,
        "record_id": speech_id.rsplit("-", 1)[0],
        "order": str(order),
        "speaker": "Mr. Somebody",
        "affiliation": "Israel",
        "position": pd.NA,
        "president": "False",
        "secretary_general": "False",
        "procedural": "False",
        "count": str(len(speech.split())),
        "speech": speech,
        "affiliation_cow": "Israel",
        "cow_ccode": "666",
        "permanent_member": "False",
        "elected_member": "False",
        "state": "True",
        "igo": "False",
        "un_org": "False",
        "ngo": "False",
    }
    return {**base, **extra}


def source() -> pd.DataFrame:
    mali = {"speaker": "Mr. KANTE", "affiliation": "Mali", "affiliation_cow": "Mali",
            "cow_ccode": "432", "elected_member": "True", "president": "True", "procedural": "True"}
    return pd.DataFrame(
        [
            row("SC00002-01-001", 1, "The Congo first."),
            row("SC00002-01-002", 2, "The Congo second."),
            row("SC00003-01-001", 1, "I call on the representative of Israel.", **mali),
            row("SC00003-01-002", 2, SPLIT_TEXT, speaker="Mr. EBAN"),
            row("SC00003-01-003", 3, "A point of order."),
            row("SC00009-01-001", 1, "The Congo first."),
            row("SC00009-01-002", 2, "The Congo second."),
        ]
    )


def repairs(**changes: object) -> dict:
    split = {
        "speech_id": "SC00003-01-002",
        "source_sha256": hashlib.sha256(SPLIT_TEXT.encode("utf-8")).hexdigest(),
        "at": len(EBAN) + 1,
        "label": LABEL,
        "new": {"speech_id": "SC00003-01-004", "attributes_from": "SC00003-01-001",
                "president": True, "procedural": False},
        "reorder": {"SC00003-01-004": 3, "SC00003-01-003": 4},
    }
    split.update(changes)
    return {
        "schema": 1,
        "drop_records": [{"record_id": "SC00002-01", "duplicate_of": "SC00009-01", "speeches": 2}],
        "split_speeches": [split],
    }


def test_the_committed_repairs_name_what_they_expect():
    committed = yaml.safe_load(SOURCE_REPAIRS.read_text(encoding="utf-8"))
    assert committed["schema"] == 1
    assert [item["record_id"] for item in committed["drop_records"]] == ["SC00869-01", "SC02622-01"]
    copied = committed["drop_speeches"][0]
    assert copied["record_id"] == "SC00906-01"
    assert len(copied["pairs"]) == copied["speeches"] == 18
    assert set(copied["variants"]) <= set(copied["pairs"])
    assert committed["trim_speeches"][0]["speech_id"] == "SC00906-01-042"
    split = committed["split_speeches"][0]
    assert split["speech_id"] == "SC01379-01-007"
    assert split["new"]["speech_id"] == "SC01379-01-010"
    assert len(split["source_sha256"]) == 64


def test_a_duplicate_record_is_dropped_whole():
    out, log = sakamoto.apply_repairs(source(), repairs())

    assert not out["record_id"].eq("SC00002-01").any()
    assert out["record_id"].eq("SC00009-01").sum() == 2
    assert log[0]["speech_ids"] == ["SC00002-01-001", "SC00002-01-002"]


def test_a_record_that_is_not_a_copy_is_refused():
    frame = source()
    frame.loc[frame["speech_id"] == "SC00002-01-002", "speech"] = "Something else."
    with pytest.raises(sakamoto.RepairError, match="not a copy"):
        sakamoto.apply_repairs(frame, repairs())


def test_a_split_gives_the_tail_to_the_named_speaker():
    out, _ = sakamoto.apply_repairs(source(), repairs())
    by_id = out.set_index("speech_id")

    assert by_id.at["SC00003-01-002", "speech"] == EBAN
    assert by_id.at["SC00003-01-002", "speaker"] == "Mr. EBAN"
    assert by_id.at["SC00003-01-004", "speech"] == MALI
    assert by_id.at["SC00003-01-004", "speaker"] == "Mr. KANTE"
    assert by_id.at["SC00003-01-004", "affiliation"] == "Mali"
    assert by_id.at["SC00003-01-004", "elected_member"] == "True"
    assert by_id.at["SC00003-01-004", "president"] == "True"
    assert by_id.at["SC00003-01-004", "procedural"] == "False"
    # The source's word count is shared, never invented.
    original = len(SPLIT_TEXT.split())
    assert int(by_id.at["SC00003-01-002", "count"]) + int(by_id.at["SC00003-01-004", "count"]) == original


def test_a_split_keeps_identifiers_and_reorders_the_meeting():
    out, _ = sakamoto.apply_repairs(source(), repairs())
    meeting = out[out["record_id"] == "SC00003-01"]

    assert meeting["speech_id"].tolist() == ["SC00003-01-001", "SC00003-01-002", "SC00003-01-003", "SC00003-01-004"]
    order = dict(zip(meeting["speech_id"], meeting["order"].astype(int), strict=True))
    assert order == {"SC00003-01-001": 1, "SC00003-01-002": 2, "SC00003-01-004": 3, "SC00003-01-003": 4}
    # Rows of later meetings stay where they were.
    assert out["speech_id"].iloc[-1] == "SC00009-01-002"


COLOPHON = "\nLitho in U.N.\nPrice: 0.50"
JULY = "The amendment was rejected."


def partial_copy() -> pd.DataFrame:
    """A September record whose end repeats a July record's last speeches."""
    return pd.DataFrame(
        [
            row("SC00004-01-001", 1, "July opening."),
            row("SC00004-01-002", 2, JULY),
            row("SC00004-01-003", 3, "The resolution is adopted."),
            row("SC00005-01-001", 1, "September opening."),
            row("SC00005-01-002", 2, f"We thank you all.{COLOPHON}\n{JULY}"),
            row("SC00005-01-003", 3, "The resolution is adopted."),
            row("SC00005-01-004", 4, "The resolutoin is adopted."),
        ]
    )


def copy_repairs(**changes: object) -> dict:
    copied = {
        "record_id": "SC00005-01",
        "speeches": 2,
        "pairs": {"SC00005-01-003": "SC00004-01-003", "SC00005-01-004": "SC00004-01-003"},
        "variants": {"SC00005-01-004": hashlib.sha256(b"The resolutoin is adopted.").hexdigest()},
    }
    copied.update(changes)
    text = f"We thank you all.{COLOPHON}\n{JULY}"
    trim = {
        "speech_id": "SC00005-01-002",
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "at": len("We thank you all."),
        "expect_after": "\nLitho in U.N.",
    }
    return {"schema": 1, "drop_speeches": [copied], "trim_speeches": [trim]}


def test_copied_speeches_go_and_the_record_keeps_its_own():
    out, log = sakamoto.apply_repairs(partial_copy(), copy_repairs())
    september = out[out["record_id"] == "SC00005-01"].set_index("speech_id")

    assert september.index.tolist() == ["SC00005-01-001", "SC00005-01-002"]
    assert september.at["SC00005-01-002", "speech"] == "We thank you all."
    assert out["record_id"].eq("SC00004-01").sum() == 3
    assert [entry["repair"] for entry in log] == ["drop_speeches", "trim_speech"]
    assert log[0]["duplicate_of"] == "SC00004-01"
    kept, cut = log[1]["source_words"]
    assert kept + cut == len(f"We thank you all.{COLOPHON}\n{JULY}".split())


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"variants": {}}, "not a copy"),
        ({"variants": {"SC00005-01-004": "0" * 64}}, "not the variant"),
        ({"speeches": 3}, "3 expected"),
        ({"pairs": {"SC00004-01-001": "SC00004-01-001"}, "speeches": 1, "variants": {}}, "is not in SC00005-01"),
    ],
)
def test_a_partial_copy_is_refused_unless_it_is_one(change, match):
    with pytest.raises(sakamoto.RepairError, match=match):
        sakamoto.apply_repairs(partial_copy(), copy_repairs(**change))


def test_a_trim_needs_the_colophon_where_it_says():
    repairs_ = copy_repairs()
    repairs_["trim_speeches"][0]["at"] = 3
    with pytest.raises(sakamoto.RepairError, match=r"no '\\nLitho in U\.N\.' at character 3"):
        sakamoto.apply_repairs(partial_copy(), repairs_)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"source_sha256": "0" * 64}, "not the one"),
        ({"at": 3}, "no 'The President"),
        ({"new": {"speech_id": "SC00003-01-003", "attributes_from": "SC00003-01-001",
                  "president": True, "procedural": False}}, "already exists"),
    ],
)
def test_a_split_refuses_a_source_it_was_not_written_for(change, match):
    with pytest.raises(sakamoto.RepairError, match=match):
        sakamoto.apply_repairs(source(), repairs(**change))


def test_repaired_run_rows_change_identity_and_never_labels(tmp_path):
    table = tmp_path / "source_repairs.json"
    table.write_text(json.dumps({
        "schema": 1,
        "drop": {"gone": {"line_id": "SC00002-01-001#1", "because": "copy"}},
        "remap": {"moved": {
            "line_id_was": "SC00003-01-002#1",
            "to": {"occurrence_id": "new", "line_id": "SC00003-01-004#1",
                   "filename": "SC00003-01-004.txt", "start": 10, "end": 18, "source_sha256": "abc"},
            "evidence_shift": -40,
        }},
    }), encoding="utf-8")
    rows = [
        {"occurrence_id": "gone", "referent": "drc"},
        {"occurrence_id": "moved", "line_id": "SC00003-01-002#1", "start": 50, "end": 58,
         "evidence_start": 45, "evidence_end": 70, "referent": "holocaust"},
        {"occurrence_id": "kept", "referent": "other"},
    ]

    out = model_runs.repaired(rows, table)

    assert [row["occurrence_id"] for row in out] == ["new", "kept"]
    assert out[0]["line_id"] == "SC00003-01-004#1"
    assert (out[0]["start"], out[0]["evidence_start"], out[0]["evidence_end"]) == (10, 5, 30)
    assert out[0]["referent"] == "holocaust"


def test_excluded_rows_leave_the_geometry_digest(tmp_path):
    path = tmp_path / "corpus.parquet"
    frame = pd.DataFrame({
        "row_id": ["SC00001-01-001", "SC00002-01-001", "SC00003-01-002"],
        "text": ["one", "two", "three"],
        "body_start": [0, 0, 0],
    })
    frame.to_parquet(path)
    trimmed = tmp_path / "trimmed.parquet"
    frame.iloc[[0]].to_parquet(trimmed)
    excluded = frozenset({"SC00002-01", "SC00003-01-002"})

    assert semantic_release.geometry_fingerprint(path, excluded) == semantic_release.geometry_fingerprint(trimmed)
    assert semantic_release.geometry_fingerprint(path) != semantic_release.geometry_fingerprint(trimmed)


def test_exclusions_need_the_repairs_the_pin_was_measured_against(tmp_path):
    repairs_path = tmp_path / "source_repairs.yml"
    repairs_path.write_text(yaml.safe_dump(repairs()), encoding="utf-8")
    pin = tmp_path / "pin.json"
    url = semantic_release.RELEASES + "x/y.zip"
    pin.write_text(json.dumps({"schema": 1, "url": url, "source_repairs_sha256": "stale"}), encoding="utf-8")
    assert semantic_release.pinned_exclusions(pin, repairs_path) == frozenset()

    from lib import artifacts

    pin.write_text(json.dumps({"schema": 1, "url": url,
                               "source_repairs_sha256": artifacts.sha256(repairs_path)}), encoding="utf-8")
    assert semantic_release.pinned_exclusions(pin, repairs_path) == {
        "SC00002-01", "SC00003-01-002", "SC00003-01-004"
    }


def test_resharding_follows_the_new_positions(tmp_path):
    (tmp_path / "neighbours").mkdir()
    ids = [f"SC00001-01-{n:03d}" for n in range(1, 301)]
    gone = "SC00001-01-005"
    shards: list[dict] = [{} for _ in range(256)]
    for position, row_id in enumerate(ids):
        shards[position % 256][row_id] = [[gone, 0.9], [ids[0] if row_id != ids[0] else ids[1], 0.8]]
    for number, shard in enumerate(shards):
        (tmp_path / "neighbours" / f"{number}.json").write_text(json.dumps(shard), encoding="utf-8")

    order = [row_id for row_id in ids if row_id != gone]
    removed = semantic_release.reshard(tmp_path, order, frozenset({gone}))

    # Every remaining speech lost its one link to the excluded speech.
    assert removed == len(order)
    for position, row_id in enumerate(order):
        shard = json.loads((tmp_path / "neighbours" / f"{position % 256}.json").read_text(encoding="utf-8"))
        assert [link[0] for link in shard[row_id]] == [ids[0] if row_id != ids[0] else ids[1]]
    assert all(gone not in json.loads((tmp_path / "neighbours" / f"{n}.json").read_text(encoding="utf-8"))
               for n in range(256))
