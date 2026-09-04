"""The vLLM transport, checked without a server, socket or optional SDK."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest
from lib import annotate, llm

ROOT = Path(__file__).resolve().parents[1]


def _step():
    path = ROOT / "scripts" / "14_llm_annotate.py"
    spec = importlib.util.spec_from_file_location("vllm_annotate_step", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


step = _step()


def response(text: str, *, status: str = "completed", reason: str = "") -> dict[str, object]:
    body: dict[str, object] = {
        "status": status,
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {
            "input_tokens": 8,
            "output_tokens": 13,
            "output_tokens_details": {"reasoning_tokens": 5},
        },
    }
    if reason:
        body["incomplete_details"] = {"reason": reason}
    return body


def test_client_reads_only_the_environment_route(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class OpenAI:
        def __init__(self, **kwargs: object) -> None:
            seen.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=OpenAI))
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:8123/v1")
    step.client(timeout=17)
    assert seen == {
        "base_url": "http://127.0.0.1:8123/v1",
        "api_key": "not-used",
        "timeout": 17,
    }


def test_response_reader_separates_content_reasoning_usage_and_truncation() -> None:
    assert step.output_text(response('{"occurrences": []}')) == '{"occurrences": []}'
    assert step.usage_of(response("{}")) == {
        "input_tokens": 8,
        "output_tokens": 13,
        "reasoning_tokens": 5,
        "cached_tokens": 0,
    }
    with pytest.raises(ValueError, match="max_output_tokens"):
        step.output_text(response("{", status="incomplete", reason="max_output_tokens"))


def test_runtime_record_requires_and_preserves_reproducible_server_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "VLLM_MODEL_REVISION": "1" * 40,
        "VLLM_VERSION": "0.28.0",
        "VLLM_GPU_MODEL": "NVIDIA H100 80GB HBM3",
        "VLLM_GPU_COUNT": "1",
        "VLLM_MAX_MODEL_LEN": "65536",
        "VLLM_REASONING_PARSER": "qwen3",
        "VLLM_QUANTIZATION": "none",
        "VLLM_TENSOR_PARALLEL_SIZE": "1",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    args = types.SimpleNamespace(
        model="Qwen/Qwen3.8-27B",
        reasoning_effort="xhigh",
        reasoning_location="chat_template_kwargs",
        temperature=0.0,
        top_p=1.0,
    )
    record = step.runtime_record(args)
    assert record["model_revision"] == "1" * 40
    assert record["vllm_version"] == "0.28.0"
    assert record["reasoning"] == {
        "parameter": "reasoning_effort",
        "value": "xhigh",
        "location": "chat_template_kwargs",
    }
    assert record["sampling"] == {"temperature": 0.0, "top_p": 1.0}
    assert record["serving"]["max_model_len"] == 65536

    monkeypatch.delenv("VLLM_MODEL_REVISION")
    with pytest.raises(SystemExit):
        step.runtime_record(args)


def test_both_instruments_use_one_responses_api_code_path(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    class Result:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return response('{"occurrences": []}')

    class Responses:
        def create(self, **body: object) -> Result:
            calls.append(body)
            return Result()

    api = types.SimpleNamespace(responses=Responses())
    speech = annotate.Speech(
        filename="speech.txt",
        custom_id="speech",
        body="genocide",
        meta={},
        occurrences=[],
    )

    def build(_: annotate.Speech) -> llm.SpeechRequest:
        return llm.SpeechRequest(
            filename="speech.txt",
            custom_id="speech",
            system="system",
            user="user",
            ordinals=(),
        )

    qwen = step.live(
        api,
        [speech],
        build,
        model="Qwen/Qwen3.8-27B",
        effort="xhigh",
        reasoning_location="chat_template_kwargs",
        temperature=0.0,
        top_p=1.0,
        workers=1,
        raw=tmp_path / "qwen",
    )
    deepseek = step.live(
        api,
        [speech],
        build,
        model="deepseek-ai/DeepSeek-V4-Flash-0731",
        effort="max",
        reasoning_location="request",
        temperature=0.0,
        top_p=1.0,
        workers=1,
        raw=tmp_path / "deepseek",
    )

    assert set(qwen.responses) == set(deepseek.responses) == {"speech"}
    assert calls[0]["model"] == "Qwen/Qwen3.8-27B"
    assert calls[0]["chat_template_kwargs"] == {"reasoning_effort": "xhigh"}
    assert calls[1]["model"] == "deepseek-ai/DeepSeek-V4-Flash-0731"
    assert calls[1]["reasoning"] == {"effort": "max"}
    assert set(calls[0]) - {"model", "reasoning", "chat_template_kwargs"} == set(calls[1]) - {
        "model",
        "reasoning",
        "chat_template_kwargs",
    }
    assert json.loads(next((tmp_path / "qwen").glob("live-*.jsonl")).read_text())["custom_id"] == (
        "speech"
    )


def test_live_flushes_each_raw_response_before_its_checkpoint(tmp_path: Path) -> None:
    class Result:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return response('{"occurrences": []}')

    api = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **_: Result())
    )
    speeches = [
        annotate.Speech(filename=f"{name}.txt", custom_id=name, body="genocide", meta={}, occurrences=[])
        for name in ("one", "two")
    ]

    def build(speech: annotate.Speech) -> llm.SpeechRequest:
        return llm.SpeechRequest(
            filename=speech.filename,
            custom_id=speech.custom_id,
            system="system",
            user="user",
            ordinals=(),
        )

    checkpoints: list[tuple[int, int]] = []

    def observe(result: annotate.Outcome) -> None:
        raw_file = next(tmp_path.glob("live-*.jsonl"))
        checkpoints.append((result.requests, len(llm.read_rows(raw_file))))

    outcome = step.live(
        api,
        speeches,
        build,
        model="Qwen/Qwen3.8-27B",
        effort="xhigh",
        reasoning_location="chat_template_kwargs",
        temperature=0.0,
        top_p=1.0,
        workers=2,
        raw=tmp_path,
        on_result=observe,
    )

    assert checkpoints == [(1, 1), (1, 2)]
    assert outcome.requests == 2
    assert set(outcome.responses) == {"one", "two"}


def test_transport_truncation_and_validation_failures_have_distinct_kinds(tmp_path: Path) -> None:
    speech = annotate.Speech(
        filename="speech.txt",
        custom_id="speech",
        body="genocide",
        meta={},
        occurrences=[],
    )
    paths = {
        "annotations": tmp_path / "annotations.jsonl",
        "failures": tmp_path / "failures.jsonl",
    }
    run_meta = llm.RunMeta(
        run_id="pilot",
        model="Qwen/Qwen3.8-27B",
        prompt_version="1",
        prompt_sha256="a" * 64,
        reasoning_effort="xhigh",
        lexicon_version="1",
        referents_version="1",
        term="genocide",
        annotated_at="2026-09-04",
    )
    outcome = annotate.Outcome(
        responses={"speech": response("{", status="incomplete", reason="max_output_tokens")},
        failures=[
            {
                "custom_id": "unreachable",
                "kind": "transport_refusal",
                "reason": "ConnectionError",
            }
        ],
    )
    step.harvest(outcome, {"speech": speech}, run_meta, set(), paths)

    failures = llm.read_rows(paths["failures"])
    assert {row["kind"] for row in failures} == {"transport_refusal", "truncation"}


def test_manifest_checkpoints_fold_into_one_scheduler_pass(tmp_path: Path) -> None:
    run_meta = llm.RunMeta(
        run_id="pilot",
        model="Qwen/Qwen3.8-27B",
        prompt_version="1",
        prompt_sha256="a" * 64,
        reasoning_effort="xhigh",
        lexicon_version="1",
        referents_version="1",
        term="genocide",
        annotated_at="2026-09-04",
    )
    common = {
        "meta": run_meta,
        "referents_sha256": "b" * 64,
        "mode": "vllm",
        "limit": 2,
        "batch_ids": [],
        "planned_requests": 2,
        "planned_occurrences": 2,
        "complete": 1,
        "written": 1,
        "parse_failures": 0,
        "evidence_invalid": 0,
        "evidence_relocated": 0,
        "usage": {"input_tokens": 8, "output_tokens": 13, "reasoning_tokens": 5, "cached_tokens": 0},
        "pass_id": "123-one",
        "source_commit": "c" * 40,
    }
    first = annotate.write_manifest(
        tmp_path / "manifest.json", {}, requests=1, returned=1, **common
    )
    second = annotate.write_manifest(
        tmp_path / "manifest.json", first, requests=1, returned=1, **common
    )

    assert second["requests"]["sent"] == 2
    assert second["usage"]["output_tokens"] == 26
    assert second["passes"] == [
        {"at": second["passes"][0]["at"], "mode": "vllm", "requests": 2, "returned": 2, "pass_id": "123-one"}
    ]


def test_retired_gemini_run_and_prompt_remain_readable() -> None:
    directory = ROOT / "model_annotations" / "genocide"
    manifest = json.loads(
        (directory / "runs" / "2026-08-31-gemini-v1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    library = llm.load_prompt_library(directory / "PROMPT.md")
    matching = [
        pack
        for pack in (library.current, *library.superseded)
        if pack.sha256 == manifest["prompt_sha256"]
    ]
    assert manifest["model"] == "gemini-3.7-flash"
    assert len(matching) == 1
    [row] = llm.read_rows(directory / "runs" / "2026-08-31-gemini-pilot" / "annotations.jsonl")[:1]
    assert tuple(row) == llm.LEGACY_ROW_FIELDS
