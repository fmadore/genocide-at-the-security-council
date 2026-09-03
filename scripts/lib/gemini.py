"""The Gemini half of the model annotation layer: one provider's wire format.

`lib.llm` decides *what a model is asked* and *what is done with what it
returns*, and neither of those is allowed to differ between the two runs Phase
L8 compares. This module holds only the part that cannot be shared: how Google's
API wants that same question phrased, and where in its reply the answer sits.
Nothing here re-implements a prompt, a schema, a validation rule or a row — it
imports `lib.llm` for all of them, so a drift between the OpenAI run and the
Gemini run is a drift in one file that both read rather than two files that
happen to agree today.

Like `lib.llm`, this module imports no SDK. `google-genai` is imported inside
`scripts/16_llm_annotate_gemini.py`'s transport functions, so every rule below is
unit-tested on a machine that has never installed it and CI — which installs
`requirements.lock` only — never needs it.

What was verified against Google's own documentation, and when
--------------------------------------------------------------

All checked 31 August 2026.

- **The model.** `gemini-3.7-flash`, GA since 13 August 2026: thinking levels
  `low`, `medium`, `high` (`minimal` "is not supported and returns an error"),
  input 1,048,576 tokens, output 65,536, Batch API *Supported*, structured
  output *Supported* — ai.google.dev/gemini-api/docs/models/gemini-3.7-flash.
  Pass the id exactly; the id recorded in every row is the id that was asked.
- **Thinking.** For the `generateContent` surface the knob is
  `generationConfig.thinkingConfig.thinkingLevel`, a string enum, default
  `medium` for 3.7 Flash — ai.google.dev/gemini-api/docs/generate-content/
  thinking. Gemini 3 replaced `thinkingBudget` with it, and sending both is an
  error. It is Google's own vocabulary for what OpenAI calls reasoning effort,
  and it is what the manifest and every row record under `reasoning_effort`.
  The documentation writes the values in lower case; the enum's members are
  `MINIMAL`/`LOW`/`MEDIUM`/`HIGH` and the SDK upper-cases what it is handed
  before sending, which a raw batch input file has nobody to do for it. See
  `request_body`.
- **Structured output.** `responseJsonSchema` takes a raw JSON Schema and
  honours `required`, `enum` and `additionalProperties`; `responseSchema` (the
  older OpenAPI-flavoured field, now being deprecated) must be omitted when it
  is used — ai.google.dev/gemini-api/docs/structured-output. It is the strictest
  server-side mechanism the API offers, so `llm.response_schema()` goes through
  it unchanged, which is what makes the two runs' constraints comparable.
- **The key.** "Set the environment variable `GEMINI_API_KEY` or
  `GOOGLE_API_KEY`… If both are set, `GOOGLE_API_KEY` takes precedence" —
  ai.google.dev/gemini-api/docs/api-key. Both are read here because the SDK
  documents both; `GEMINI_API_KEY` is preferred and the chosen value is passed to
  the client explicitly, so a stray `GOOGLE_API_KEY` left in a shell by some
  other Google tool cannot silently pay for this run under a different account
  than the one reported.
- **The reply.** A batch result line is `{"key": …, "response": {…}}` with the
  response in camelCase: `candidates[].content.parts[].text`, `finishReason`,
  and `usageMetadata` carrying `promptTokenCount`, `candidatesTokenCount` and
  `thoughtsTokenCount` — github.com/google-gemini/cookbook, `quickstarts/
  Batch_mode.ipynb`, whose recorded output was produced by `gemini-3.7-flash`.
  The live path gets the same object from the SDK in snake_case, so every reader
  below accepts either spelling rather than trusting one path's habits.
- **The SDK.** `google-genai` 2.20.0 on PyPI, Python >= 3.10; pinned
  `>=2.20,<3` in `requirements-llm.txt`. Every field name used here was also
  read off an installed copy rather than only off a documentation page:
  `GenerateContentConfig` carries `system_instruction`, `response_mime_type`,
  `response_json_schema`, `thinking_config` and `max_output_tokens`;
  `HttpOptions.timeout` is milliseconds; `errors.ClientError` and
  `errors.ServerError` both descend from `errors.APIError` and carry `code`;
  `JobState` has `QUEUED`, `PENDING`, `RUNNING`, `CANCELLING` and `PAUSED`
  besides the five terminal names, which is why `TERMINAL_STATES` lists what to
  stop on instead of what to keep waiting through.

One thing Google recommends that this step does not do
------------------------------------------------------

The Interactions API (`client.interactions.create`, with `response_format` and a
top-level `generation_config.thinking_level`) is now Google's recommended surface
and `generateContent` is labelled legacy. The Batch API has no Interactions
equivalent: it is defined over `GenerateContentRequest`, and batch is what makes
6,092 occurrences affordable at half price. So the default path is Batch over
`generateContent`, which the 3.7 Flash model page lists as supported, and
`--live` uses the same `generateContent` body so that a pilot and a corpus run
ask an identical question. The day batch grows an Interactions form, this module
is where that changes — and it will be a new run id, not an edit to an old run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Final

from . import llm

#: The model this study's counter-instrument targets. Not an alias: aliases move.
MODEL_ID: Final = "gemini-3.7-flash"

#: `thinkingLevel`'s documented values for this model, in the documentation's own
#: spelling — which is what the CLI takes, what the manifest records and what
#: every row carries as `reasoning_effort`. Closed on purpose, as 14's effort list
#: is: a level arriving in the API becomes a reviewable diff here rather than a
#: silent pass-through. `minimal` is absent because 3.7 Flash rejects it.
THINKING_LEVELS: Final = ("low", "medium", "high")

#: Read in this order. See the docstring: the SDK documents both, prefers the
#: second when both are set, and this step prefers the first and says so.
KEY_VARIABLES: Final = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

#: The model's documented output ceiling. Whether thoughts are charged against
#: it is not stated anywhere Google documents, so the ceiling a request asks for
#: is generous and a `MAX_TOKENS` finish is recorded as a refusal, never repaired.
MODEL_OUTPUT_LIMIT: Final = 65_536

#: The Batch API's terminal states — ai.google.dev/gemini-api/docs/batch-api.
#: `JOB_STATE_EXPIRED` is reached after 48 hours pending or running, which is the
#: operational reason a run is chunked rather than submitted as one job.
TERMINAL_STATES: Final = frozenset(
    {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }
)

#: A batch job resource name, for recognising one in a manifest.
JOB_NAME_PREFIX: Final = "batches/"

#: The three counts every manifest carries, whatever produced them.
EMPTY_USAGE: Final[dict[str, int]] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "cached_tokens": 0,
}

#: `usageMetadata` names, mapped onto the manifest's provider-neutral ones. The
#: reasoning slot takes `thoughtsTokenCount`, which is what Gemini charges for
#: thinking and what makes a Gemini run's token line readable beside an OpenAI
#: one — the same three numbers, from each provider's own report, never estimated.
USAGE_FIELDS: Final = {
    "input_tokens": ("promptTokenCount", "prompt_token_count"),
    "output_tokens": ("candidatesTokenCount", "candidates_token_count"),
    "reasoning_tokens": ("thoughtsTokenCount", "thoughts_token_count"),
    # How much of the prompt was served from cache and billed at the cached
    # rate. Gemini caches a repeated prefix without being asked, so there is
    # nothing to switch on — but nothing was measuring it either, and a run that
    # does not report its cached share cannot say what caching saved. A response
    # that omits the field reports zero, which is what a cache miss is.
    "cached_tokens": ("cachedContentTokenCount", "cached_content_token_count"),
}


# --- The key ----------------------------------------------------------------


def resolve_api_key(environ: Mapping[str, str]) -> tuple[str, str]:
    """The variable this run reads its key from, and the key.

    Returns the name as well as the value so a caller can report *which*
    variable paid for the run without ever printing the key itself. Raises
    `KeyError` when neither is set, which the step turns into a refusal before it
    reads a parquet or spends a call.
    """
    for name in KEY_VARIABLES:
        value = environ.get(name, "").strip()
        if value:
            return name, value
    raise KeyError(" or ".join(KEY_VARIABLES))


# --- One speech's request ----------------------------------------------------


def request_body(
    request: llm.SpeechRequest,
    *,
    thinking_level: str,
    max_output_tokens: int,
) -> dict[str, object]:
    """One `GenerateContentRequest`, identical in a batch line and a live call.

    Deliberately carries no `model` key. The Batch API takes the model once at
    job creation and the live path passes it as an argument, so a body that named
    one would either be ignored or contradict the job — and the id that goes into
    every row would no longer be provably the id that was asked.

    `llm.response_schema()` travels through `response_json_schema` unaltered:
    same field set, same enums, same `additionalProperties: false` the OpenAI run
    is constrained by. Nothing is loosened to suit a provider. Verified against
    the installed SDK: `GenerateContentConfig` carries the schema through with
    every keyword intact, which the older `response_schema` field does not.

    `thinking_level` is written in the wire spelling and not in the
    documentation's. Google's examples pass `"high"`, but `ThinkingLevel`'s
    members are `MINIMAL`/`LOW`/`MEDIUM`/`HIGH` and the SDK silently upper-cases
    what it is given before sending — a courtesy nothing extends to a batch input
    file, which is raw JSON that no SDK ever sees. Emitting `"HIGH"` here is what
    the live path puts on the wire anyway, so the two paths stay identical where
    it counts and a batch job cannot be rejected for a spelling the docs taught.
    """
    if thinking_level not in THINKING_LEVELS:
        raise ValueError(
            f"Unknown thinking level: {thinking_level or '(blank)'}; "
            f"{MODEL_ID} accepts {', '.join(THINKING_LEVELS)}."
        )
    if not 0 < max_output_tokens <= MODEL_OUTPUT_LIMIT:
        raise ValueError(
            f"max_output_tokens must be between 1 and {MODEL_OUTPUT_LIMIT:,}, "
            f"not {max_output_tokens}."
        )
    return {
        # A sibling of `contents` in GenerateContentRequest, not part of the
        # conversation: the same text 14 sends as the `developer` message.
        "system_instruction": {"parts": [{"text": request.system}]},
        "contents": [{"role": "user", "parts": [{"text": request.user}]}],
        "generation_config": {
            "thinking_config": {"thinking_level": thinking_level.upper()},
            "response_mime_type": "application/json",
            "response_json_schema": llm.response_schema(),
            "max_output_tokens": max_output_tokens,
        },
    }


def batch_line(
    request: llm.SpeechRequest,
    *,
    thinking_level: str,
    max_output_tokens: int,
) -> dict[str, object]:
    """One line of a batch input file: `{"key": …, "request": …}`.

    `key` is the speech's custom id, which is what correlates a reply to a
    speech; the file-based path is used precisely so that correlation is by name
    rather than by the position in a list that the inline path relies on.
    """
    return {
        "key": request.custom_id,
        "request": request_body(
            request,
            thinking_level=thinking_level,
            max_output_tokens=max_output_tokens,
        ),
    }


def generate_kwargs(body: Mapping[str, object]) -> dict[str, object]:
    """The same body, arranged the way `client.models.generate_content` takes it.

    The SDK flattens `systemInstruction` into the config object that everything
    else lives in. This is a rearrangement and never an addition: whatever the
    batch path sends, the live path sends, which is the only way a `--live` pilot
    measures the run it is a pilot for.
    """
    config = dict(body["generation_config"])  # type: ignore[arg-type]
    config["system_instruction"] = body["system_instruction"]
    return {"contents": body["contents"], "config": config}


# --- One speech's reply ------------------------------------------------------


def _field(mapping: Mapping[str, object], *names: str) -> object:
    """The first of `names` the mapping has.

    A batch result file is REST JSON (camelCase); the live path arrives through
    the SDK's own model dump (snake_case). Both are read here rather than
    normalised at the seam, because a normaliser is one more thing that can be
    wrong about a run nobody can re-run.
    """
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def output_text(response: Mapping[str, object]) -> str:
    """The single JSON text of one `GenerateContentResponse`.

    A blocked prompt, a missing candidate, a truncated answer and a safety stop
    are all raised as parse failures rather than smoothed over. Each one means
    this speech has no annotation, and naming which one it was is the difference
    between a run somebody can fix and a run somebody has to guess about.

    Thought parts are skipped. They are absent unless thought summaries are asked
    for, which this step never does; skipping them anyway costs a comparison and
    saves a whole speech from failing to parse if that default ever changes.
    """
    feedback = _field(response, "promptFeedback", "prompt_feedback")
    if isinstance(feedback, Mapping):
        blocked = _field(feedback, "blockReason", "block_reason")
        if blocked:
            raise ValueError(f"prompt blocked ({blocked})")

    candidates = _field(response, "candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("no candidates in the response")
    candidate = candidates[0]
    if not isinstance(candidate, Mapping):
        raise ValueError("the first candidate is not an object")

    finish = str(_field(candidate, "finishReason", "finish_reason") or "")
    if finish and finish not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
        raise ValueError(f"response did not finish ({finish})")

    content = _field(candidate, "content")
    parts = _field(content, "parts") if isinstance(content, Mapping) else None
    chunks = []
    for part in parts or []:
        if not isinstance(part, Mapping) or part.get("thought"):
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            chunks.append(text)
    if not chunks:
        raise ValueError(f"no text output (finish reason {finish or 'unreported'})")
    return "".join(chunks)


def usage_of(response: Mapping[str, object]) -> dict[str, int]:
    """Reported tokens, or zeros. Never estimated."""
    metadata = _field(response, "usageMetadata", "usage_metadata")
    if not isinstance(metadata, Mapping):
        return dict(EMPTY_USAGE)
    counts = {}
    for key, names in USAGE_FIELDS.items():
        value = _field(metadata, *names)
        counts[key] = int(value) if isinstance(value, int | float) else 0
    return counts


def read_result_line(line: str) -> tuple[str, dict[str, object] | None, str]:
    """One line of a batch output file, as `(key, response, reason)`.

    Exactly one of `response` and `reason` is meaningful. A line the API marked
    with a `status` or an `error` is a refusal carrying that text; a line that is
    neither is a refusal too, because a result nobody can read is not a result.
    """
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as error:
        return "", None, f"result line is not JSON: {error}"
    if not isinstance(parsed, Mapping):
        return "", None, "result line is not a JSON object"

    key = str(parsed.get("key", ""))
    failure = _field(parsed, "error", "status")
    if failure:
        return key, None, json.dumps(failure, ensure_ascii=False)[:300]
    response = parsed.get("response")
    if not isinstance(response, Mapping):
        return key, None, "result line carries neither a response nor an error"
    return key, dict(response), ""


def job_state(job: object) -> str:
    """A batch job's state as a `JOB_STATE_*` string, whatever shape it arrives in.

    `client.batches.get` returns an enum whose `.name` is the state; a job read
    back from a dump is a plain string. Both are named the same way here so the
    polling loop has one thing to compare against `TERMINAL_STATES`.
    """
    state = getattr(job, "state", job)
    return str(getattr(state, "name", state) or "")


def job_names(values: Sequence[object]) -> list[str]:
    """Batch job resource names from a manifest, refusing anything else.

    A manifest is edited by hand often enough — a run resumed from a laptop that
    was closed — that a mistyped name should stop a `--poll` rather than send it
    looking for a job that never existed.
    """
    names = []
    for value in values:
        name = str(value).strip()
        if not name.startswith(JOB_NAME_PREFIX):
            raise ValueError(f"Not a batch job name: {name or '(blank)'}")
        names.append(name)
    return names
