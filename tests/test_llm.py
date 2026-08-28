"""The model annotation contract, checked without a key, a network or an SDK.

Everything a paid run depends on is decided in `lib.llm`: what the model is
asked, what counts as an acceptable answer, and where a quotation actually sits
in the record. None of that can be re-measured by re-running the step, so it is
measured here instead, offline, on constructed cases.

The referent list is a synthetic CSV rather than the real
`annotations/lexicon/referents.csv`: that file is a growing research input, and a
test that asserts against its contents would fail every time a reviewed case is
added. What is asserted against the real repository is the prompt — because its
bytes are the run's provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from lib import audit, lexicon, llm, occurrences

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "model_annotations" / "genocide" / "PROMPT.md"

REFERENT_CSV = """id,label,description,kind,iso3,years
other,Other known referent,A referent not yet controlled.,reserved,,
unclear,Unclear referent,The context does not support an assignment.,reserved,,
not_applicable,Not applicable,Reserved for false positives.,reserved,,
rwanda_1994,Rwanda 1994,The 1994 genocide against the Tutsi in Rwanda.,case,RWA,1994
holocaust,The Holocaust,The Nazi genocide of European Jews.,historical,,1941-1945
genocide_in_general,Genocide in general,Abstract discussion with no case in view.,meta,,
"""

REFERENTS = {
    "other",
    "unclear",
    "not_applicable",
    "rwanda_1994",
    "holocaust",
    "genocide_in_general",
}

TERM = lexicon.Term(
    name="genocide",
    pattern=r"\bgenocide\b",
    tier="core",
    register="core",
    examples=("genocide",),
    prefilters=("genocide",),
    regex=re.compile(r"\bgenocide\b", re.IGNORECASE),
)


@pytest.fixture
def referent_file(tmp_path: Path) -> Path:
    path = tmp_path / "referents.csv"
    path.write_text(REFERENT_CSV, encoding="utf-8")
    return path


def enumerate_bodies(bodies: dict[str, str]) -> list[occurrences.Occurrence]:
    """Real occurrence identities over constructed speeches."""
    speeches = pd.DataFrame(
        {"filename": list(bodies), "body_start": [0] * len(bodies)},
        index=range(len(bodies)),
    )
    series = pd.Series(list(bodies.values()), index=speeches.index)
    return occurrences.enumerate_term(speeches, series, TERM)


def labels(**changes: object) -> dict[str, object]:
    entry = {
        "verdict": "true_positive",
        "quotation": "not_quoted",
        "stance": "asserts",
        "function": ["accusation_or_qualification"],
        "referent": "rwanda_1994",
        "proposed_referent": "",
        "evidence_quote": "this is genocide",
        "confidence": "high",
    }
    entry.update(changes)
    return entry


def payload(*entries: dict[str, object]) -> dict[str, object]:
    return {"occurrences": list(entries)}


def entry(ordinal: int, **changes: object) -> dict[str, object]:
    return {"ordinal": ordinal, **labels(**changes)}


# --- The prompt is the run's provenance -------------------------------------


def test_prompt_parses_into_the_two_templates_the_step_sends() -> None:
    pack = llm.load_prompt(PROMPT)
    assert pack.version == 1
    assert "{referents_table}" in pack.system_template
    for placeholder in llm.USER_PLACEHOLDERS:
        assert "{" + placeholder + "}" in pack.user_template
    assert "```" not in pack.system_template
    assert "```" not in pack.user_template


def test_prompt_states_the_task_boundary_and_the_cascade() -> None:
    system = llm.load_prompt(PROMPT).system_template
    # Wrapped for a human reader, so the sentences are matched unwrapped.
    flat = re.sub(r"\s+", " ", system)
    assert "You never decide whether an underlying event legally constitutes genocide" in flat
    assert 'If verdict is "false_positive"' in flat
    assert "reserved for false positives" in flat
    for label in sorted(audit.STANCES | audit.QUOTATIONS | audit.FUNCTIONS | audit.CONFIDENCE):
        assert label in system, f"the prompt never names {label}"


def test_prompt_digest_is_over_the_raw_bytes_and_does_not_move() -> None:
    expected = hashlib.sha256(PROMPT.read_bytes()).hexdigest()
    assert llm.prompt_sha256(PROMPT) == expected
    assert llm.load_prompt(PROMPT).sha256 == expected
    assert llm.load_prompt(PROMPT).sha256 == llm.load_prompt(PROMPT).sha256


def test_a_prompt_without_its_sections_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "PROMPT.md"
    path.write_text("version: 1\n\n## System\n\n```text\nnothing\n```\n", encoding="utf-8")
    with pytest.raises(ValueError, match="User template"):
        llm.load_prompt(path)

    path.write_text("## System\n\n```text\n{referents_table}\n```\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        llm.load_prompt(path)


# --- The controlled referents -----------------------------------------------


def test_referent_table_is_grouped_and_leaves_nothing_out(referent_file: Path) -> None:
    referents = llm.read_referent_table(referent_file)
    assert {referent.id for referent in referents} == REFERENTS
    assert {referent.kind for referent in referents} == {"reserved", "case", "historical", "meta"}

    rendered = llm.render_referents(referents)
    assert "rwanda_1994 — Rwanda 1994 (1994) — The 1994 genocide" in rendered
    assert "genocide_in_general — Genocide in general — Abstract" in rendered
    assert rendered.index("rwanda_1994") < rendered.index("holocaust") < rendered.index("other")
    for identifier in REFERENTS:
        assert identifier in rendered


def test_a_referent_file_without_a_kind_column_still_renders(tmp_path: Path) -> None:
    path = tmp_path / "referents.csv"
    path.write_text(
        "id,label,description\nother,Other,Known\nunclear,Unclear,Unknown\n"
        "not_applicable,N/A,False positive\nrwanda_1994,Rwanda 1994,The 1994 genocide.\n",
        encoding="utf-8",
    )
    kinds = {referent.id: referent.kind for referent in llm.read_referent_table(path)}
    assert kinds == {
        "other": "reserved",
        "unclear": "reserved",
        "not_applicable": "reserved",
        "rwanda_1994": "case",
    }


# --- What one speech is asked ------------------------------------------------


SPEECH = (
    "The Council has heard the reports. What happened there was genocide, and the word "
    "matters. Others have said that genocide is too strong a word for it."
)

META = {
    "filename": "UNSC_1994_SPV.3377_spch0004.txt",
    "date": pd.Timestamp("1994-05-16"),
    "country_org": "New Zealand",
    "participanttype": "Council member",
    "meeting_symbol": "S/PV.3377",
    "agenda_item_manual": "The situation concerning Rwanda",
}


def build() -> llm.SpeechRequest:
    found = enumerate_bodies({str(META["filename"]): SPEECH})
    pack = llm.load_prompt(PROMPT)
    return llm.build_request(META, SPEECH, found, pack, "  rwanda_1994 — Rwanda 1994 — a case")


def test_request_carries_the_metadata_and_the_referent_table() -> None:
    request = build()
    assert request.filename == META["filename"]
    assert request.custom_id == "UNSC_1994_SPV.3377_spch0004"
    assert request.ordinals == (1, 2)
    assert "Date: 1994-05-16" in request.user
    assert "Speaker (country or organisation): New Zealand" in request.user
    assert "Meeting: S/PV.3377" in request.user
    assert "Agenda item: The situation concerning Rwanda" in request.user
    assert "rwanda_1994 — Rwanda 1994 — a case" in request.system
    assert "{referents_table}" not in request.system


def test_the_speech_travels_unmarked_and_the_occurrences_travel_beside_it() -> None:
    request = build()
    quoted = request.user.split("===== SPEECH TEXT BEGINS =====\n")[1]
    quoted = quoted.split("\n===== SPEECH TEXT ENDS =====")[0]
    assert quoted == SPEECH, "the body must reach the model character for character"
    assert "[1]" not in quoted and "[2]" not in quoted

    first = SPEECH.index("genocide")
    second = SPEECH.index("genocide", first + 1)
    assert f"[1] characters {first}-{first + 8}" in request.user
    assert f"[2] characters {second}-{second + 8}" in request.user
    assert "sentence: What happened there was genocide, and the word matters." in request.user
    assert "Occurrences to annotate (2)" in request.user


def test_the_schema_is_strict_and_asks_for_a_list_of_functions() -> None:
    schema = llm.response_schema()
    item = schema["properties"]["occurrences"]["items"]
    assert schema["additionalProperties"] is False
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(llm.RESPONSE_FIELDS)
    assert set(item["properties"]) == set(llm.RESPONSE_FIELDS)
    assert item["properties"]["function"]["type"] == "array"
    assert set(item["properties"]["verdict"]["enum"]) == set(audit.VERDICTS)
    assert item["properties"]["referent"]["type"] == "string"


def test_the_request_body_pins_the_model_the_effort_and_the_schema() -> None:
    body = llm.request_body(build(), model="a-model", reasoning_effort="high", max_output_tokens=99)
    assert body["model"] == "a-model"
    assert body["reasoning"] == {"effort": "high"}
    assert body["max_output_tokens"] == 99
    assert [message["role"] for message in body["input"]] == ["developer", "user"]
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    # The batch input file is JSONL: anything unserialisable here would surface
    # only once a run was already being paid for.
    assert json.loads(json.dumps(body, ensure_ascii=False)) == body


# --- What comes back ---------------------------------------------------------


def test_a_well_formed_response_is_accepted() -> None:
    accepted = llm.validate_response(
        payload(entry(1), entry(2, verdict="uncertain", stance="unclear", confidence="low")),
        ordinals=[1, 2],
        referents=REFERENTS,
    )
    assert set(accepted) == {1, 2}
    assert accepted[1]["function"] == ("accusation_or_qualification",)
    assert accepted[2]["verdict"] == "uncertain"


def test_a_response_may_arrive_as_json_text() -> None:
    accepted = llm.validate_response(
        json.dumps(payload(entry(1))), ordinals=[1], referents=REFERENTS
    )
    assert accepted[1]["referent"] == "rwanda_1994"
    with pytest.raises(ValueError, match="not JSON"):
        llm.validate_response("{oops", ordinals=[1], referents=REFERENTS)


def test_the_ordinal_set_must_equal_the_one_that_was_asked() -> None:
    with pytest.raises(ValueError, match="missing=\\[2\\]"):
        llm.validate_response(payload(entry(1)), ordinals=[1, 2], referents=REFERENTS)
    with pytest.raises(ValueError, match="unexpected=\\[7\\]"):
        llm.validate_response(payload(entry(1), entry(7)), ordinals=[1], referents=REFERENTS)
    with pytest.raises(ValueError, match="returned twice"):
        llm.validate_response(payload(entry(1), entry(1)), ordinals=[1], referents=REFERENTS)


def test_a_label_outside_the_codebook_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown stance label: agrees"):
        llm.validate_response(payload(entry(1, stance="agrees")), ordinals=[1], referents=REFERENTS)
    with pytest.raises(ValueError, match="Unknown function label: rhetoric"):
        llm.validate_response(
            payload(entry(1, function=["rhetoric"])), ordinals=[1], referents=REFERENTS
        )
    with pytest.raises(ValueError, match="Unknown verdict label"):
        llm.validate_response(payload(entry(1, verdict="")), ordinals=[1], referents=REFERENTS)


def test_function_may_be_multiple_but_never_alongside_an_abstention() -> None:
    accepted = llm.validate_response(
        payload(entry(1, function=["accountability", "warning_or_prevention"])),
        ordinals=[1],
        referents=REFERENTS,
    )
    assert accepted[1]["function"] == ("accountability", "warning_or_prevention")

    with pytest.raises(ValueError, match="cannot be combined"):
        llm.validate_response(
            payload(entry(1, function=["accountability", "unclear"])),
            ordinals=[1],
            referents=REFERENTS,
        )
    with pytest.raises(ValueError, match="cannot be combined"):
        llm.validate_response(
            payload(entry(1, function=["accountability", "not_applicable"])),
            ordinals=[1],
            referents=REFERENTS,
        )
    with pytest.raises(ValueError, match="must not be repeated"):
        llm.validate_response(
            payload(entry(1, function=["accountability", "accountability"])),
            ordinals=[1],
            referents=REFERENTS,
        )


def test_a_false_positive_takes_the_whole_cascade_or_none_of_it() -> None:
    with pytest.raises(ValueError, match="must use not_applicable"):
        llm.validate_response(
            payload(entry(1, verdict="false_positive")), ordinals=[1], referents=REFERENTS
        )
    with pytest.raises(ValueError, match="must use not_applicable"):
        llm.validate_response(
            payload(
                entry(
                    1,
                    verdict="false_positive",
                    quotation="not_applicable",
                    stance="not_applicable",
                    function=["not_applicable"],
                    referent="rwanda_1994",
                )
            ),
            ordinals=[1],
            referents=REFERENTS,
        )
    accepted = llm.validate_response(
        payload(
            entry(
                1,
                verdict="false_positive",
                quotation="not_applicable",
                stance="not_applicable",
                function=["not_applicable"],
                referent="not_applicable",
            )
        ),
        ordinals=[1],
        referents=REFERENTS,
    )
    assert accepted[1]["referent"] == "not_applicable"

    with pytest.raises(ValueError, match="reserved for false positives"):
        llm.validate_response(
            payload(entry(1, stance="not_applicable")), ordinals=[1], referents=REFERENTS
        )


def test_the_referent_must_come_from_the_run_s_own_list() -> None:
    with pytest.raises(ValueError, match="Unknown referent: rwanda"):
        llm.validate_response(
            payload(entry(1, referent="rwanda")), ordinals=[1], referents=REFERENTS
        )


def test_a_proposed_referent_belongs_to_other_and_only_to_other() -> None:
    accepted = llm.validate_response(
        payload(entry(1, referent="other", proposed_referent="Western Sahara")),
        ordinals=[1],
        referents=REFERENTS,
    )
    assert accepted[1]["proposed_referent"] == "Western Sahara"

    with pytest.raises(ValueError, match="requires a proposed_referent"):
        llm.validate_response(payload(entry(1, referent="other")), ordinals=[1], referents=REFERENTS)
    with pytest.raises(ValueError, match="only for referent 'other'"):
        llm.validate_response(
            payload(entry(1, proposed_referent="Western Sahara")),
            ordinals=[1],
            referents=REFERENTS,
        )


def test_a_response_that_is_not_the_agreed_shape_is_refused() -> None:
    with pytest.raises(ValueError, match="'occurrences' array"):
        llm.validate_response({"answers": []}, ordinals=[], referents=REFERENTS)
    with pytest.raises(ValueError, match="do not match the schema"):
        llm.validate_response(
            {"occurrences": [{"ordinal": 1, "verdict": "true_positive"}]},
            ordinals=[1],
            referents=REFERENTS,
        )
    with pytest.raises(ValueError, match="Ordinal must be an integer"):
        llm.validate_response(payload(entry("1")), ordinals=[1], referents=REFERENTS)


# --- Locating the evidence ---------------------------------------------------


def test_an_exact_quotation_is_located_and_valid() -> None:
    body = "The Council was told that this is genocide and must be named."
    start, end, valid = llm.locate_evidence(body, "this is genocide", 34, 42)
    assert body[start:end] == "this is genocide"
    assert valid is True


def test_a_quotation_copied_across_a_line_break_maps_back_to_the_real_offsets() -> None:
    body = "The Council was told\nthat this is\n   genocide and must be named."
    match = body.index("genocide")
    start, end, valid = llm.locate_evidence(body, "this is genocide", match, match + 8)
    assert body[start:end] == "this is\n   genocide"
    assert valid is True


def test_the_match_chosen_is_the_one_the_occurrence_falls_inside() -> None:
    body = "acts of genocide in one place. Later, acts of genocide in another place."
    first = body.index("genocide")
    second = body.index("genocide", first + 1)
    start, end, valid = llm.locate_evidence(body, "acts of genocide", second, second + 8)
    assert (start, end) == (second - 8, second + 8)
    assert valid is True

    start, end, valid = llm.locate_evidence(body, "acts of genocide", first, first + 8)
    assert (start, end) == (first - 8, first + 8)
    assert valid is True


def test_a_quotation_that_is_not_in_the_speech_records_no_offsets() -> None:
    body = "The Council was told that this is genocide."
    assert llm.locate_evidence(body, "the Secretary-General said", 34, 42) == (None, None, False)
    assert llm.locate_evidence(body, "   ", 34, 42) == (None, None, False)


def test_a_quotation_found_in_the_wrong_place_is_located_but_not_valid() -> None:
    body = "First, this is genocide. Second, these are acts of war and nothing else."
    match = body.index("genocide")
    start, end, valid = llm.locate_evidence(body, "these are acts of war", match, match + 8)
    assert body[start:end] == "these are acts of war"
    assert valid is False


# --- Rows --------------------------------------------------------------------


def meta() -> llm.RunMeta:
    return llm.RunMeta(
        run_id="2026-09-05-luna-v1",
        model="a-model",
        prompt_version=1,
        prompt_sha256="f" * 64,
        reasoning_effort="high",
        lexicon_version="2",
        term="genocide",
        annotated_at="2026-09-05",
    )


def rows_for(body: str, **changes: object) -> list[dict[str, object]]:
    found = enumerate_bodies({"speech.txt": body})
    accepted = llm.validate_response(
        payload(*(entry(item.ordinal, **changes) for item in found)),
        ordinals=[item.ordinal for item in found],
        referents=REFERENTS,
    )
    return llm.annotation_rows(found, body, accepted, meta())


def test_a_row_carries_the_agreed_keys_in_the_agreed_order() -> None:
    body = "The Council was told that this is genocide."
    [row] = rows_for(body)
    assert tuple(row) == llm.ROW_FIELDS
    assert row["line_id"] == "speech#1"
    assert row["term"] == "genocide"
    assert row["function"] == "accusation_or_qualification"
    assert row["schema_version"] == audit.SCHEMA_VERSION
    assert row["evidence_valid"] is True
    assert body[row["evidence_start"] : row["evidence_end"]] == "this is genocide"
    assert row["start"] == body.index("genocide")
    llm.validate_row(row, REFERENTS)


def test_an_unlocatable_quotation_produces_a_row_with_null_offsets() -> None:
    [row] = rows_for("The Council was told that this is genocide.", evidence_quote="not in here")
    assert (row["evidence_start"], row["evidence_end"], row["evidence_valid"]) == (None, None, False)
    llm.validate_row(row, REFERENTS)


def test_validate_row_refuses_a_reordered_or_incomplete_row() -> None:
    [row] = rows_for("The Council was told that this is genocide.")
    reordered = {key: row[key] for key in reversed(llm.ROW_FIELDS)}
    with pytest.raises(ValueError, match="wrong order"):
        llm.validate_row(reordered, REFERENTS)

    dropped = {key: value for key, value in row.items() if key != "confidence"}
    with pytest.raises(ValueError, match="Row keys are wrong"):
        llm.validate_row(dropped, REFERENTS)


def test_validate_row_applies_the_same_cascade_the_response_had_to_pass() -> None:
    [row] = rows_for("The Council was told that this is genocide.")
    with pytest.raises(ValueError, match="must use not_applicable"):
        llm.validate_row({**row, "verdict": "false_positive"}, REFERENTS)
    with pytest.raises(ValueError, match="Unknown referent"):
        llm.validate_row({**row, "referent": "somewhere"}, REFERENTS)
    with pytest.raises(ValueError, match="cannot be combined"):
        llm.validate_row({**row, "function": "accountability|unclear"}, REFERENTS)
    with pytest.raises(ValueError, match="ISO date"):
        llm.validate_row({**row, "annotated_at": "2026-9-5"}, REFERENTS)
    with pytest.raises(ValueError, match="must contain the matched term"):
        llm.validate_row({**row, "evidence_start": row["start"] + 1}, REFERENTS)
    with pytest.raises(ValueError, match="together or not at all"):
        llm.validate_row({**row, "evidence_end": None}, REFERENTS)


# --- Resuming a run ----------------------------------------------------------


BODIES = {
    "one.txt": "This is genocide, and it is genocide again.",
    "two.txt": "The word genocide appears once here.",
}


def written(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "annotations.jsonl"
    llm.append_rows(path, rows)
    return path


def test_a_speech_counts_as_done_only_when_all_its_occurrences_are_written(
    tmp_path: Path,
) -> None:
    found = enumerate_bodies(BODIES)
    everything = llm.annotation_rows(
        [item for item in found if item.filename == "one.txt"],
        BODIES["one.txt"],
        {item.ordinal: labels() for item in found},
        meta(),
    )
    path = written(tmp_path, everything)
    assert llm.completed(path, found, prompt_sha256="f" * 64, model="a-model") == {"one.txt"}

    partial = written(tmp_path / "half", everything[:1])
    assert llm.completed(partial, found, prompt_sha256="f" * 64, model="a-model") == set()


def test_an_absent_run_file_means_nothing_has_been_asked_yet(tmp_path: Path) -> None:
    found = enumerate_bodies(BODIES)
    missing = tmp_path / "annotations.jsonl"
    assert llm.completed(missing, found, prompt_sha256="f" * 64, model="a-model") == set()


def test_a_run_written_with_another_prompt_or_model_is_never_resumed(tmp_path: Path) -> None:
    found = enumerate_bodies(BODIES)
    rows = llm.annotation_rows(
        [item for item in found if item.filename == "two.txt"],
        BODIES["two.txt"],
        {item.ordinal: labels() for item in found},
        meta(),
    )
    path = written(tmp_path, rows)

    with pytest.raises(ValueError, match="different prompt"):
        llm.completed(path, found, prompt_sha256="a" * 64, model="a-model")
    with pytest.raises(ValueError, match="different model"):
        llm.completed(path, found, prompt_sha256="f" * 64, model="another-model")


def test_a_row_from_a_corpus_that_has_moved_is_refused(tmp_path: Path) -> None:
    found = enumerate_bodies(BODIES)
    rows = llm.annotation_rows(
        [item for item in found if item.filename == "two.txt"],
        BODIES["two.txt"],
        {item.ordinal: labels() for item in found},
        meta(),
    )
    path = written(tmp_path, rows)
    moved = enumerate_bodies({**BODIES, "two.txt": "The word genocide appears once, here."})
    with pytest.raises(ValueError, match="corpus does not have"):
        llm.completed(path, moved, prompt_sha256="f" * 64, model="a-model")
