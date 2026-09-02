"""The Gemini counter-instrument, checked without a key, a network or an SDK.

Phase L8 compares two independent readings of the same 6,092 occurrences. That
comparison is only worth making if the two runs asked the same question of the
same population and wrote rows of the same shape, and none of that can be
re-measured by re-running either step: both cost money and neither is run by CI
or by the deploy. So it is measured here instead, offline, on constructed cases —
including, directly against `scripts/14_llm_annotate.py`, the two things that
would silently invalidate the comparison if they ever drifted apart: the corpus
figures each run asserts, and the text each one sends.

`tests/test_llm.py` covers everything provider-agnostic; nothing of it is
repeated. What is asserted here is the wire format, the reply reader, and the
run's refusals.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from lib import annotate, gemini, lexicon, llm, occurrences

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "model_annotations" / "genocide" / "PROMPT.md"


def _step(name: str, module_name: str):
    """Load a numbered script as a module. A script cannot be named `16_…`.

    Registered in `sys.modules` before it is executed because both scripts define
    frozen dataclasses, and `dataclasses` resolves a field's annotations through
    `sys.modules[cls.__module__]`.
    """
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


step = _step("16_llm_annotate_gemini.py", "gemini_annotate_step")
openai_step = _step("14_llm_annotate.py", "openai_annotate_step")


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

TABLE = "  rwanda_1994 — Rwanda 1994 — a case"


def enumerate_bodies(bodies: dict[str, str]) -> list[occurrences.Occurrence]:
    """Real occurrence identities over constructed speeches."""
    speeches = pd.DataFrame(
        {"filename": list(bodies), "body_start": [0] * len(bodies)},
        index=range(len(bodies)),
    )
    series = pd.Series(list(bodies.values()), index=speeches.index)
    return occurrences.enumerate_term(speeches, series, TERM)


def build() -> llm.SpeechRequest:
    found = enumerate_bodies({str(META["filename"]): SPEECH})
    return llm.build_request(META, SPEECH, found, llm.load_prompt(PROMPT), TABLE)


def labels(**changes: object) -> dict[str, object]:
    entry = {
        "verdict": "true_positive",
        "quotation": "not_quoted",
        "concrete_case": "yes",
        "speaker_position": "asserts",
        "function": ["accusation_or_qualification"],
        "referent": "rwanda_1994",
        "proposed_referent": "",
        "referent_source": "passage",
        "accused_actor": "",
        "victim_group": "",
        "own_state_accused": "no",
        "salience": "substantive",
        "evidence_quote": "this is genocide",
        "rationale": "The speaker applies the word in their own voice.",
        "confidence": "high",
    }
    entry.update(changes)
    return entry


def answer(*ordinals: int, **changes: object) -> str:
    """The JSON text a well-behaved model returns for one speech."""
    return json.dumps(
        {"occurrences": [{"ordinal": ordinal, **labels(**changes)} for ordinal in ordinals]}
    )


def response(text: str, *, finish: str = "STOP", thought: bool = False) -> dict[str, object]:
    """A `GenerateContentResponse` shaped as a batch result file carries it.

    Field spellings and the `usageMetadata` counts are taken from the recorded
    output of `quickstarts/Batch_mode.ipynb` in github.com/google-gemini/cookbook,
    which ran against `gemini-3.7-flash`.
    """
    parts: list[dict[str, object]] = []
    if thought:
        parts.append({"text": "First I will read the sentence.", "thought": True})
    parts.append({"text": text})
    return {
        "responseId": "6VFkaIDwEPXVjMcP4-XW6Qo",
        "modelVersion": "gemini-3.7-flash",
        "candidates": [
            {"index": 0, "finishReason": finish, "content": {"role": "model", "parts": parts}}
        ],
        "usageMetadata": {
            "promptTokenCount": 8,
            "candidatesTokenCount": 63,
            "thoughtsTokenCount": 1180,
            "totalTokenCount": 1251,
        },
    }


# --- The key ----------------------------------------------------------------


def test_the_key_is_read_from_either_documented_variable_in_one_order() -> None:
    assert gemini.KEY_VARIABLES == ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    assert gemini.resolve_api_key({"GEMINI_API_KEY": "a", "GOOGLE_API_KEY": "b"}) == (
        "GEMINI_API_KEY",
        "a",
    )
    assert gemini.resolve_api_key({"GOOGLE_API_KEY": "b"}) == ("GOOGLE_API_KEY", "b")
    # Exported empty is not set: an unset shell variable often arrives as "".
    assert gemini.resolve_api_key({"GEMINI_API_KEY": "  ", "GOOGLE_API_KEY": "b"})[0] == (
        "GOOGLE_API_KEY"
    )
    with pytest.raises(KeyError):
        gemini.resolve_api_key({})


def test_the_step_refuses_in_words_before_it_reads_anything(monkeypatch) -> None:
    for name in gemini.KEY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as refusal:
        step.read_key()
    assert refusal.value.code == 1


def test_the_command_line_refuses_without_a_key() -> None:
    """The whole CLI, not just the guard: no key, no parquet read, no call."""
    environment = {
        key: value for key, value in os.environ.items() if key not in gemini.KEY_VARIABLES
    }
    environment["PYTHONIOENCODING"] = "utf-8"
    finished = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "16_llm_annotate_gemini.py"),
            "--run-id",
            "x",
            "--model",
            gemini.MODEL_ID,
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert finished.returncode == 1
    assert "GEMINI_API_KEY" in finished.stderr and "GOOGLE_API_KEY" in finished.stderr
    assert "Traceback" not in finished.stderr


# --- What one speech is asked ------------------------------------------------


def test_the_request_is_a_generate_content_body_that_never_names_the_model() -> None:
    body = gemini.request_body(build(), thinking_level="high", max_output_tokens=99)
    assert set(body) == {"system_instruction", "contents", "generation_config"}
    assert "model" not in body, "the Batch API takes the model once, at job creation"

    request = build()
    assert body["system_instruction"] == {"parts": [{"text": request.system}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": request.user}]}]

    config = body["generation_config"]
    assert set(config) == {
        "thinking_config",
        "response_mime_type",
        "response_json_schema",
        "max_output_tokens",
    }
    # The wire spelling, not the documentation's: `ThinkingLevel`'s members are
    # upper case and the SDK upper-cases for the live path, but a batch input
    # file is raw JSON that no SDK ever touches.
    assert config["thinking_config"] == {"thinking_level": "HIGH"}
    assert config["response_mime_type"] == "application/json"
    assert config["max_output_tokens"] == 99
    # responseSchema must be omitted when responseJsonSchema is used.
    assert "response_schema" not in config

    schema = config["response_json_schema"]
    assert schema == llm.response_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["occurrences"]["items"]["additionalProperties"] is False

    # The batch input file is JSONL: anything unserialisable here would surface
    # only once a run was already being paid for.
    assert json.loads(json.dumps(body, ensure_ascii=False)) == body


def test_the_thinking_level_and_the_ceiling_are_closed_over_what_the_model_takes() -> None:
    assert gemini.THINKING_LEVELS == ("low", "medium", "high")
    for level in gemini.THINKING_LEVELS:
        body = gemini.request_body(build(), thinking_level=level, max_output_tokens=99)
        assert body["generation_config"]["thinking_config"] == {"thinking_level": level.upper()}
    # 3.7 Flash answers `minimal` with an error rather than with a cheap reading.
    with pytest.raises(ValueError, match="Unknown thinking level: minimal"):
        gemini.request_body(build(), thinking_level="minimal", max_output_tokens=99)
    with pytest.raises(ValueError, match="Unknown thinking level"):
        gemini.request_body(build(), thinking_level="", max_output_tokens=99)

    assert gemini.MODEL_OUTPUT_LIMIT == 65_536
    with pytest.raises(ValueError, match="max_output_tokens"):
        gemini.request_body(build(), thinking_level="high", max_output_tokens=65_537)
    with pytest.raises(ValueError, match="max_output_tokens"):
        gemini.request_body(build(), thinking_level="high", max_output_tokens=0)


def test_a_batch_line_is_keyed_by_the_speech_and_carries_the_whole_request() -> None:
    request = build()
    line = gemini.batch_line(request, thinking_level="high", max_output_tokens=99)
    assert set(line) == {"key", "request"}
    assert line["key"] == request.custom_id == "UNSC_1994_SPV.3377_spch0004"
    assert line["request"] == gemini.request_body(
        request, thinking_level="high", max_output_tokens=99
    )


def test_the_live_call_rearranges_the_batch_body_and_adds_nothing_to_it() -> None:
    body = gemini.request_body(build(), thinking_level="high", max_output_tokens=99)
    kwargs = gemini.generate_kwargs(body)
    assert set(kwargs) == {"contents", "config"}
    assert kwargs["contents"] is body["contents"]
    assert set(kwargs["config"]) == set(body["generation_config"]) | {"system_instruction"}
    assert kwargs["config"]["system_instruction"] == body["system_instruction"]
    for key, value in body["generation_config"].items():
        assert kwargs["config"][key] == value


# --- The two runs must be asking the same question ---------------------------


def test_both_providers_are_sent_the_same_two_messages() -> None:
    """Byte for byte: a comparison of two readings needs one question."""
    request = build()
    gemini_body = gemini.request_body(request, thinking_level="high", max_output_tokens=99)
    openai_body = llm.request_body(
        request, model="gpt-5.6-luna", reasoning_effort="high", max_output_tokens=99
    )
    assert (
        gemini_body["system_instruction"]["parts"][0]["text"] == openai_body["input"][0]["content"]
    )
    assert gemini_body["contents"][0]["parts"][0]["text"] == openai_body["input"][1]["content"]
    assert (
        gemini_body["generation_config"]["response_json_schema"]
        == openai_body["text"]["format"]["schema"]
    )


def test_both_steps_annotate_the_same_documented_population() -> None:
    assert step.DOCUMENTED_SPEECHES == openai_step.DOCUMENTED_SPEECHES == 3_273
    assert step.DOCUMENTED_OCCURRENCES == openai_step.DOCUMENTED_OCCURRENCES == 6_092
    assert step.COLUMNS == openai_step.COLUMNS
    assert step.TERM == openai_step.TERM
    assert step.PROMPT == openai_step.PROMPT
    assert step.RUNS == openai_step.RUNS


def test_the_two_steps_share_the_enumeration_rather_than_agreeing_about_it() -> None:
    """Identity, not equality.

    The review of 1 September 2026 (§4.5, item 10) is right that the assertions
    above pin constants: two `gather` functions can agree on
    `DOCUMENTED_SPEECHES` to the digit and still enumerate different speeches.
    What makes the two runs comparable is that there is one enumeration, and
    that is what this asserts — the same function object, reached from both
    steps, and the same manifest writer and the same refusal.
    """
    for name in ("gather", "output_ceiling", "read_manifest", "write_manifest", "refuse_mismatch"):
        assert getattr(annotate, name) is not None
        assert not hasattr(step, name), f"16 defines its own {name} again"
        assert not hasattr(openai_step, name), f"14 defines its own {name} again"
    assert step.Speech is openai_step.Speech is annotate.Speech
    assert step.Outcome is openai_step.Outcome is annotate.Outcome
    assert step.COLUMNS is openai_step.COLUMNS is annotate.COLUMNS


def test_the_ceiling_provisions_a_speech_for_its_thinking_and_not_only_its_json() -> None:
    """The recorded MAX_TOKENS failure, and what the run says the bound must be.

    One Gemini speech with three occurrences was truncated at the old ceiling of
    `12,000 + 1,200 * n` = 15,600 tokens and lost; another with two came within
    271 tokens of its own. Over the 3,273 answers the run returned, thinking
    plus output reached 18,781 tokens on a single speech, and the length of the
    thinking is not a function of the occurrence count. So the base carries it.
    """
    speech = next(iter(one_speech().values()))
    assert len(speech.occurrences) == 2
    truncated = 15_600  # what the speech that was lost had to work inside
    assert annotate.output_ceiling(speech, step.MAX_OUTPUT_TOKENS) > truncated
    assert annotate.output_ceiling(speech, step.MAX_OUTPUT_TOKENS) > 18_781
    # Clamped to whatever the provider will actually accept, per provider.
    assert annotate.output_ceiling(speech, 1_000) == 1_000
    assert step.MAX_OUTPUT_TOKENS == gemini.MODEL_OUTPUT_LIMIT
    assert openai_step.MAX_OUTPUT_TOKENS == 100_000


# --- What comes back ---------------------------------------------------------


def test_the_json_is_read_out_of_the_candidate_the_batch_file_carries() -> None:
    assert gemini.output_text(response('{"occurrences": []}')) == '{"occurrences": []}'


def test_a_thought_part_is_never_mistaken_for_the_answer() -> None:
    assert gemini.output_text(response('{"occurrences": []}', thought=True)) == (
        '{"occurrences": []}'
    )


def test_the_live_response_is_read_by_the_same_reader_in_its_own_spelling() -> None:
    """The SDK dumps snake_case; a result file is camelCase. Both, or neither."""
    live = {
        "candidates": [
            {
                "finish_reason": "STOP",
                "content": {"role": "model", "parts": [{"text": '{"occurrences": []}'}]},
            }
        ],
        "usage_metadata": {
            "prompt_token_count": 8,
            "candidates_token_count": 63,
            "thoughts_token_count": 1180,
        },
    }
    assert gemini.output_text(live) == '{"occurrences": []}'
    assert gemini.usage_of(live) == {
        "input_tokens": 8,
        "output_tokens": 63,
        "reasoning_tokens": 1180,
    }


def test_thinking_tokens_are_reported_as_the_reasoning_count_never_estimated() -> None:
    assert gemini.usage_of(response("{}")) == {
        "input_tokens": 8,
        "output_tokens": 63,
        "reasoning_tokens": 1180,
    }
    assert gemini.usage_of({"candidates": []}) == gemini.EMPTY_USAGE
    assert gemini.usage_of({"usageMetadata": {"promptTokenCount": 8}}) == {
        "input_tokens": 8,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }


def test_a_truncated_blocked_or_empty_answer_says_which_it_was() -> None:
    with pytest.raises(ValueError, match="did not finish \\(MAX_TOKENS\\)"):
        gemini.output_text(response("{", finish="MAX_TOKENS"))
    with pytest.raises(ValueError, match="did not finish \\(PROHIBITED_CONTENT\\)"):
        gemini.output_text(response("", finish="PROHIBITED_CONTENT"))
    with pytest.raises(ValueError, match="prompt blocked \\(SAFETY\\)"):
        gemini.output_text({"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []})
    with pytest.raises(ValueError, match="no candidates"):
        gemini.output_text({"candidates": []})
    with pytest.raises(ValueError, match="no text output"):
        gemini.output_text({"candidates": [{"content": {"parts": [{"thought": True}]}}]})


def test_a_result_line_is_a_response_or_a_recorded_refusal_and_never_both() -> None:
    line = json.dumps({"key": "speech", "response": response("{}")})
    key, body, reason = gemini.read_result_line(line)
    assert (key, reason) == ("speech", "")
    assert body is not None and body["modelVersion"] == "gemini-3.7-flash"

    key, body, reason = gemini.read_result_line(
        json.dumps({"key": "speech", "status": {"code": 3, "message": "invalid argument"}})
    )
    assert (key, body) == ("speech", None)
    assert "invalid argument" in reason

    key, body, reason = gemini.read_result_line('{"key": "speech"}')
    assert body is None and "neither a response nor an error" in reason

    key, body, reason = gemini.read_result_line("{oops")
    assert (key, body) == ("", None)
    assert "not JSON" in reason


def test_a_job_name_that_is_not_a_job_name_stops_a_poll() -> None:
    assert gemini.job_names(["batches/123", "batches/456"]) == ["batches/123", "batches/456"]
    with pytest.raises(ValueError, match="Not a batch job name: batch_abc"):
        gemini.job_names(["batch_abc"])
    with pytest.raises(ValueError, match="Not a batch job name"):
        gemini.job_names([""])


def test_a_job_state_is_read_from_an_enum_or_from_a_plain_string() -> None:
    class _Enum:
        name = "JOB_STATE_SUCCEEDED"

    class _Job:
        state = _Enum()

    assert gemini.job_state(_Job()) == "JOB_STATE_SUCCEEDED"
    assert gemini.job_state("JOB_STATE_EXPIRED") == "JOB_STATE_EXPIRED"
    assert "JOB_STATE_EXPIRED" in gemini.TERMINAL_STATES
    assert "JOB_STATE_RUNNING" not in gemini.TERMINAL_STATES


# --- From a canned reply to committed rows -----------------------------------


def run_meta() -> llm.RunMeta:
    return llm.RunMeta(
        run_id="2026-09-08-gemini-v1",
        model=gemini.MODEL_ID,
        prompt_version=1,
        prompt_sha256="f" * 64,
        reasoning_effort="high",
        lexicon_version="2",
        referents_version="2",
        term="genocide",
        annotated_at="2026-09-08",
    )


def one_speech(body: str = SPEECH) -> dict[str, object]:
    found = enumerate_bodies({str(META["filename"]): body})
    speech = step.Speech(
        filename=str(META["filename"]),
        custom_id=str(META["filename"]).removesuffix(".txt"),
        body=body,
        meta=dict(META),
        occurrences=found,
    )
    return {speech.custom_id: speech}


def paths_in(directory: Path) -> dict[str, Path]:
    return {
        "manifest": directory / "manifest.json",
        "annotations": directory / "annotations.jsonl",
        "failures": directory / "failures.jsonl",
    }


def test_a_canned_reply_becomes_validated_rows_in_the_run_file(tmp_path: Path) -> None:
    scope = one_speech()
    outcome = step.Outcome(responses={next(iter(scope)): response(answer(1, 2))}, requests=1)
    paths = paths_in(tmp_path)
    tally = step.harvest(outcome, scope, run_meta(), REFERENTS, paths)

    assert tally["written"] == 2
    assert tally["failures"] == 0
    assert tally["reasoning_tokens"] == 1180
    assert tally["input_tokens"] == 8

    rows = llm.read_rows(paths["annotations"])
    assert len(rows) == 2
    for row in rows:
        assert tuple(row) == llm.ROW_FIELDS
        assert row["model"] == gemini.MODEL_ID
        assert row["prompt_sha256"] == "f" * 64
        assert row["reasoning_effort"] == "high"
        assert row["run_id"] == "2026-09-08-gemini-v1"
        llm.validate_row(row, REFERENTS)
    assert not paths["failures"].exists()


def test_a_reply_that_is_not_json_loses_its_speech_and_writes_no_rows(tmp_path: Path) -> None:
    scope = one_speech()
    outcome = step.Outcome(responses={next(iter(scope)): response("{oops")}, requests=1)
    paths = paths_in(tmp_path)
    tally = step.harvest(outcome, scope, run_meta(), REFERENTS, paths)

    assert tally["written"] == 0
    assert tally["failures"] == 1
    assert llm.read_rows(paths["annotations"]) == []

    [failure] = llm.read_rows(paths["failures"])
    assert failure["custom_id"] == "UNSC_1994_SPV.3377_spch0004"
    assert "not JSON" in str(failure["reason"])
    assert failure["run_id"] == "2026-09-08-gemini-v1"


def test_a_reply_outside_the_codebook_is_refused_and_not_repaired(tmp_path: Path) -> None:
    scope = one_speech()
    outcome = step.Outcome(
        responses={next(iter(scope)): response(answer(1, 2, speaker_position="agrees"))}, requests=1
    )
    paths = paths_in(tmp_path)
    tally = step.harvest(outcome, scope, run_meta(), REFERENTS, paths)
    assert (tally["written"], tally["failures"]) == (0, 1)
    assert "Unknown speaker_position label" in str(llm.read_rows(paths["failures"])[0]["reason"])


def test_a_truncated_reply_is_recorded_with_its_finish_reason(tmp_path: Path) -> None:
    scope = one_speech()
    outcome = step.Outcome(
        responses={next(iter(scope)): response(answer(1), finish="MAX_TOKENS")}, requests=1
    )
    paths = paths_in(tmp_path)
    tally = step.harvest(outcome, scope, run_meta(), REFERENTS, paths)
    assert (tally["written"], tally["failures"]) == (0, 1)
    assert "MAX_TOKENS" in str(llm.read_rows(paths["failures"])[0]["reason"])


def test_a_batch_result_file_is_split_into_responses_and_refusals() -> None:
    payload = "\n".join(
        [
            json.dumps({"key": "one", "response": response(answer(1))}),
            "",
            json.dumps({"key": "two", "status": {"message": "quota exhausted"}}),
        ]
    )
    outcome = step.Outcome()
    step.read_results(payload, outcome, job_name="batches/123")
    assert set(outcome.responses) == {"one"}
    assert [failure["custom_id"] for failure in outcome.failures] == ["two"]
    assert outcome.failures[0]["batch"] == "batches/123"


# --- Resuming, and refusing to reopen a finished run -------------------------


def test_a_speech_this_run_already_wrote_is_not_asked_again(tmp_path: Path) -> None:
    scope = one_speech()
    paths = paths_in(tmp_path)
    step.harvest(
        step.Outcome(responses={next(iter(scope)): response(answer(1, 2))}),
        scope,
        run_meta(),
        REFERENTS,
        paths,
    )
    speech = next(iter(scope.values()))
    already = llm.completed(
        paths["annotations"],
        speech.occurrences,
        prompt_sha256="f" * 64,
        model=gemini.MODEL_ID,
    )
    assert already == {speech.filename}
    assert [item for item in [speech] if item.filename not in already] == []

    with pytest.raises(ValueError, match="different model"):
        llm.completed(
            paths["annotations"],
            speech.occurrences,
            prompt_sha256="f" * 64,
            model="gemini-3.6-flash",
        )
    with pytest.raises(ValueError, match="different prompt"):
        llm.completed(
            paths["annotations"], speech.occurrences, prompt_sha256="a" * 64, model=gemini.MODEL_ID
        )


def test_a_completed_run_is_never_written_into_twice() -> None:
    with pytest.raises(SystemExit):
        annotate.refuse_mismatch({"status": "complete"}, "a-run", gemini.MODEL_ID, "f" * 64)
    with pytest.raises(SystemExit):
        annotate.refuse_mismatch(
            {"model": "gemini-3.6-flash", "prompt_sha256": "f" * 64},
            "a-run",
            gemini.MODEL_ID,
            "f" * 64,
        )
    with pytest.raises(SystemExit):
        annotate.refuse_mismatch(
            {"model": gemini.MODEL_ID, "prompt_sha256": "a" * 64},
            "a-run",
            gemini.MODEL_ID,
            "f" * 64,
        )
    annotate.refuse_mismatch({}, "a-run", gemini.MODEL_ID, "f" * 64)


def test_the_manifest_carries_14_s_keys_and_the_job_names(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = annotate.write_manifest(
        path,
        {},
        meta=run_meta(),
        referents_sha256="c" * 64,
        mode="batch",
        limit=None,
        batch_ids=["batches/456", "batches/123"],
        planned_requests=2,
        planned_occurrences=3,
        requests=2,
        returned=0,
        complete=0,
        written=0,
        parse_failures=0,
        evidence_invalid=0,
        evidence_relocated=0,
        usage=dict(gemini.EMPTY_USAGE),
    )
    assert manifest["model"] == gemini.MODEL_ID
    assert manifest["reasoning_effort"] == "high"
    assert manifest["batch_ids"] == ["batches/123", "batches/456"]
    assert manifest["cost_usd"] is None
    assert manifest["status"] == "in_progress"
    assert json.loads(path.read_text(encoding="utf-8")) == manifest

    # Effort accumulates across passes; the artefact's own counts are measured.
    resumed = annotate.write_manifest(
        path,
        manifest,
        meta=run_meta(),
        referents_sha256="c" * 64,
        mode="poll",
        limit=None,
        batch_ids=["batches/123"],
        planned_requests=2,
        planned_occurrences=3,
        requests=0,
        returned=2,
        complete=2,
        written=3,
        parse_failures=0,
        evidence_invalid=0,
        evidence_relocated=0,
        usage={"input_tokens": 8, "output_tokens": 63, "reasoning_tokens": 1180},
    )
    assert resumed["requests"] == {"planned": 2, "sent": 2, "returned": 2, "complete": 2}
    assert resumed["usage"]["reasoning_tokens"] == 1180
    assert resumed["batch_ids"] == ["batches/123", "batches/456"]
    assert resumed["status"] == "complete"
    assert resumed["created"] == manifest["created"]
    # One row per pass, in order, so a manifest says how a run was assembled.
    assert [entry["mode"] for entry in resumed["passes"]] == ["batch", "poll"]
    assert [entry["requests"] for entry in resumed["passes"]] == [2, 0]
    assert [entry["returned"] for entry in resumed["passes"]] == [0, 2]


def test_a_pass_that_sent_nothing_adds_nothing_to_the_request_count(tmp_path: Path) -> None:
    # The fault of §4.5, item 1, in miniature: the Gemini run recorded 7,966
    # requests over a corpus of 3,273 because every pass added the size of what
    # it meant to ask, including one whose first chunk the quota refused. What
    # is added now is what a caller counted after a job existed.
    manifest = {"requests": {"planned": 3273, "sent": 800, "returned": 800, "complete": 800}}
    refused = annotate.write_manifest(
        tmp_path / "manifest.json",
        manifest,
        meta=run_meta(),
        referents_sha256="c" * 64,
        mode="batch",
        limit=None,
        batch_ids=[],
        planned_requests=3273,
        planned_occurrences=6092,
        requests=0,
        returned=0,
        complete=800,
        written=1500,
        parse_failures=0,
        evidence_invalid=0,
        evidence_relocated=0,
        usage=dict(gemini.EMPTY_USAGE),
    )
    assert refused["requests"]["sent"] == 800
    assert refused["passes"][-1]["requests"] == 0


def test_an_answer_downloaded_twice_is_returned_once() -> None:
    # A --poll reads every job the manifest records, so a resumed run downloads
    # answers written on an earlier pass. `returned: 4474` over 3,273 requests
    # is what counting them again looks like.
    answered = frozenset({"speech-a", "speech-b"})
    assert annotate.fresh_returns(["speech-a", "speech-b"], answered) == 0
    assert annotate.fresh_returns(["speech-a", "speech-c"], answered) == 1
    assert annotate.fresh_returns([], answered) == 0


# --- Nothing here needs the SDK ----------------------------------------------


class _NoGoogleGenAI:
    """A finder that makes `google.genai` unimportable, as CI's environment is."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "google.genai" or fullname.startswith("google.genai."):
            raise ImportError("google-genai is not installed")
        return None


def test_both_modules_import_with_no_google_genai_installed() -> None:
    blocker = _NoGoogleGenAI()
    sys.meta_path.insert(0, blocker)
    try:
        sys.modules.pop("lib.gemini", None)
        importlib.invalidate_caches()
        module = importlib.import_module("lib.gemini")
        assert module.MODEL_ID == "gemini-3.7-flash"
        reloaded = _step("16_llm_annotate_gemini.py", "gemini_annotate_step_offline")
        assert reloaded.MAX_OUTPUT_TOKENS == 65_536
    finally:
        sys.meta_path.remove(blocker)
    assert "google.genai" not in sys.modules
