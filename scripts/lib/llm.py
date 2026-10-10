"""The model annotation layer: the request, the contract, and what comes back.

`scripts/14_llm_annotate.py` is the only caller that talks to an API. Everything
that decides *what a model is asked* and *what is done with what it returns*
lives in `lib`, in plain Python, so it can be tested on any machine with no key,
no network and no `openai` package installed. That is the same division 06, 07
and 10 make against torch and spaCy; here the stakes are higher, because a run
costs money and cannot be repeated by CI or by the deploy to find out whether
the parsing was right.

The prompt files are read by `lib.prompts`, the model's evidence is found in the
speech by `lib.evidence`, and a run's `annotations.jsonl` is read and appended
to by `lib.model_runs`; each states the rule it keeps. Two things this module is
responsible for:

- **The model's labels are checked against the human codebook's own vocabulary.**
  The enums come from :mod:`lib.schema` — the frozensets the human annotation file
  is validated against — so the model cannot invent a category the codebook does
  not have. The false-positive cascade and the multi-label function rules are
  enforced here exactly as `audit._validate_labels` enforces them there. They are
  reimplemented rather than shared because audit's version operates on a merged
  candidate frame; the semantics, not the code path, are what must agree.
- **Nothing here writes anywhere near `annotations/`.** The output is a JSONL row
  set with a fixed key order, appended to a committed run directory under
  `model_annotations/`. docs/PLAN.md §5: no model output may overwrite corpus
  text, lexicon counts or human annotations.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

from . import referents as referents_lib

# Every name imported with a redundant `as` is a re-export, kept importable from
# this module for the callers and tests that still reach it here; new code
# imports it from where it is defined. The `as` marks it as deliberate rather
# than as an unused import.
from . import schema as schema_lib
from .evidence import _WHITESPACE_RE, _sentence_range, locate_evidence
from .evidence import FOLDED as FOLDED
from .evidence import WRAPPERS as WRAPPERS
from .kwic import sentence_at, sentence_spans
from .model_runs import append_rows as append_rows
from .model_runs import completed as completed
from .model_runs import read_rows as read_rows
from .occurrences import Occurrence
from .prompts import ARCHIVE as ARCHIVE
from .prompts import CONSTRAINTS as CONSTRAINTS
from .prompts import REFERENT_ENUM, SENTENCE_EVIDENCE, SENTENCES_PLACEHOLDER, PromptPack, _fill
from .prompts import SYSTEM_PLACEHOLDERS as SYSTEM_PLACEHOLDERS
from .prompts import USER_PLACEHOLDERS as USER_PLACEHOLDERS
from .prompts import PromptLibrary as PromptLibrary
from .prompts import load_prompt as load_prompt
from .prompts import load_prompt_library as load_prompt_library
from .prompts import prompt_sha256 as prompt_sha256

#: Model schema; human schema 3 keeps its independent confidence field.
SCHEMA_VERSION: Final = "3.1"  # model-only revision: human schema 3 retains confidence

#: The exact key set of a row in `annotations.jsonl`, in the order it is written.
#: Order is load-bearing for readability rather than for parsing: a JSONL diff is
#: read by a human, and a run whose keys wander is one nobody can review.
SCHEMA3_ROW_FIELDS: Final = (
    "occurrence_id",
    "line_id",
    "filename",
    "term",
    "start",
    "end",
    "source_sha256",
    "schema_version",
    "lexicon_version",
    "referents_version",
    "run_id",
    "model",
    "prompt_version",
    "prompt_sha256",
    "reasoning_effort",
    "verdict",
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
    "proposed_referent",
    "referent_source",
    "accused_actor",
    "victim_group",
    "own_state_accused",
    "salience",
    "evidence_quote",
    "evidence_start",
    "evidence_end",
    "evidence_valid",
    "evidence_relocated",
    "rationale",
    "confidence",
    "annotated_at",
)

ROW_FIELDS: Final = tuple(field for field in SCHEMA3_ROW_FIELDS if field != "confidence")

#: The shape of the two runs of 30 and 31 August 2026 and their two pilots,
#: which are the only files that will ever have it: 12,184 rows written against
#: annotation schema 2, before the relocating locator existed and before the
#: referent list carried a version.
#:
#: Written out rather than derived from :data:`ROW_FIELDS` by exclusion, because
#: it is no longer a subset — it carries `stance`, which schema 3 replaced with
#: `concrete_case` and `speaker_position`. A validator that refused this shape
#: would defeat the point of versioning anything: the versions exist so that
#: improving the instrument does not orphan the runs that were paid for under
#: the old one. So the shape is named here and accepted where a committed run is
#: read back, never at the write seam, and `lib.llm.resolve_row` says what each
#: of its rows means in schema 3's vocabulary.
LEGACY_ROW_FIELDS: Final = (
    "occurrence_id",
    "line_id",
    "filename",
    "term",
    "start",
    "end",
    "source_sha256",
    "schema_version",
    "lexicon_version",
    "run_id",
    "model",
    "prompt_version",
    "prompt_sha256",
    "reasoning_effort",
    "verdict",
    "quotation",
    "stance",
    "function",
    "referent",
    "proposed_referent",
    "evidence_quote",
    "evidence_start",
    "evidence_end",
    "evidence_valid",
    "confidence",
    "annotated_at",
)

#: The per-occurrence object the model is asked to return. `function` arrives as
#: a JSON array — a model emitting a pipe-joined string would be guessing at a
#: storage convention — and is joined with "|" only when a row is written.
RESPONSE_FIELDS: Final = (
    "ordinal",
    "verdict",
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
    "proposed_referent",
    "referent_source",
    "accused_actor",
    "victim_group",
    "own_state_accused",
    "salience",
    "evidence_quote",
    "rationale",
)

#: Single-valued fields and the vocabulary each is closed over.
ENUMS: Final[dict[str, frozenset[str]]] = {
    "verdict": schema_lib.VERDICTS,
    "quotation": schema_lib.QUOTATIONS,
    "concrete_case": schema_lib.CONCRETE_CASE,
    "speaker_position": schema_lib.POSITIONS,
    "referent_source": schema_lib.REFERENT_SOURCES,
    "own_state_accused": schema_lib.OWN_STATE_ACCUSED,
    "salience": schema_lib.SALIENCE,
}

#: The same, for a row written against annotation schema 2.
LEGACY_ENUMS: Final[dict[str, frozenset[str]]] = {
    "verdict": schema_lib.VERDICTS,
    "quotation": schema_lib.QUOTATIONS,
    "stance": schema_lib.STANCES,
    "confidence": schema_lib.CONFIDENCE,
}

#: The fields a false positive must set to `not_applicable`, and the subset in
#: which that value may not appear otherwise. Both come from `lib.schema`, which
#: is where the human codebook's own rules live: the model is held to the
#: coder's cascade and not to one of its own.
CASCADE: Final = schema_lib.CASCADE_FIELDS
RESERVED: Final = schema_lib.RESERVED_FIELDS
FREE_TEXT_CASCADE: Final = schema_lib.FREE_TEXT_CASCADE_FIELDS

#: The schema-2 cascade, for reading a committed run back.
LEGACY_CASCADE: Final = ("quotation", "stance", "function", "referent")

#: The name the structured-output schema is registered under in a request.
SCHEMA_NAME: Final = "unsc_occurrence_annotations"

#: Kinds in `referents.csv`, in the order the rendered table presents them. A
#: kind the file introduces later is appended after these rather than dropped.
KIND_ORDER: Final = ("case", "historical", "meta", "reserved")
KIND_HEADINGS: Final = {
    "case": "Cases and situations:",
    "historical": "Historical referents:",
    "meta": "Non-case referents:",
    "reserved": "Reserved identifiers, whose rules follow this table:",
}


# --- The controlled referents ----------------------------------------------


@dataclass(frozen=True)
class Referent:
    """One row of `annotations/lexicon/referents.csv`, as the prompt shows it."""

    id: str
    label: str
    description: str
    kind: str
    years: str


def read_referent_table(path: Path) -> list[Referent]:
    """The referent list with the columns the prompt renders.

    Parsed, and held to every rule of the list, by `lib.referents`, which also
    decides a row's `kind` when the file does not declare one. This is the view
    a prompt needs: no `iso3`, because a model has no use for an ISO code.

    Retired identifiers are left out, because the model is offered only what is
    current. They stay in the file so a committed run that used one can still be
    read, but rendering them would invite a new run to reuse a category the
    list has withdrawn, and the run would then be neither v1 nor v2.
    """
    return [
        Referent(
            id=row.id,
            label=row.label,
            description=row.description,
            kind=row.kind,
            years=row.years,
        )
        for row in referents_lib.read(path).current()
    ]


def render_referents(referents: Sequence[Referent]) -> str:
    """The `{referents_table}` block: `id — label (years) — description`.

    Grouped by kind so a reader of the prompt can see that the controlled list
    distinguishes a live situation from a historical one, and nothing is left
    out: the three reserved IDs appear here too, immediately above the
    instructions in the system text that say what each of them means.
    """
    kinds = list(KIND_ORDER) + sorted({r.kind for r in referents} - set(KIND_ORDER))
    blocks = []
    for kind in kinds:
        members = [referent for referent in referents if referent.kind == kind]
        if not members:
            continue
        lines = [KIND_HEADINGS.get(kind, f"{kind.capitalize()}:")]
        for referent in members:
            years = f" ({referent.years})" if referent.years else ""
            lines.append(f"  {referent.id} — {referent.label}{years} — {referent.description}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --- Building one speech's request -----------------------------------------


@dataclass(frozen=True)
class SpeechRequest:
    """Everything one speech needs, with no reference to any SDK."""

    filename: str
    custom_id: str
    system: str
    user: str
    ordinals: tuple[int, ...]
    #: The structured-output schema for this request, when the prompt declares
    #: constraints that depend on it; ``None`` means :func:`response_schema`.
    schema: dict[str, object] | None = None
    #: How many sentences the request numbered; zero without sentence evidence.
    sentence_count: int = 0


def response_schema(
    *,
    referents: Sequence[str] | None = None,
    ordinals: Sequence[int] | None = None,
    sentences: int = 0,
) -> dict[str, object]:
    """The strict JSON schema the structured output is constrained to.

    Called bare it is the schema of prompts v1 to v3, byte for byte: `referent`
    a plain string, validated on the way back in. With `referents` and
    `ordinals` — a `referent-enum` prompt — the identifiers, the request's own
    ordinals and the number of occurrences are part of the schema, so a guided
    decoder cannot produce what the validator would refuse. The referent list
    is already hashed into every run's identity, which is why building it into
    the schema at run time is not a hidden prompt change. With `sentences` — a
    `sentence-evidence` prompt — `evidence_quote` is replaced by a first and
    last sentence number within the request's own numbering.
    """
    schema = _base_schema()
    item = schema["properties"]["occurrences"]["items"]  # type: ignore[index]
    if referents is not None:
        item["properties"]["referent"] = {"type": "string", "enum": sorted(referents)}
    if ordinals is not None:
        item["properties"]["ordinal"] = {"type": "integer", "enum": sorted(ordinals)}
        schema["properties"]["occurrences"]["minItems"] = len(ordinals)  # type: ignore[index]
        schema["properties"]["occurrences"]["maxItems"] = len(ordinals)  # type: ignore[index]
    if sentences:
        bound = {"type": "integer", "minimum": 1, "maximum": sentences}
        del item["properties"]["evidence_quote"]
        item["properties"]["evidence_sentences"] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["first", "last"],
            "properties": {"first": dict(bound), "last": dict(bound)},
        }
        item["required"] = [
            "evidence_sentences" if field == "evidence_quote" else field
            for field in item["required"]
        ]
    return schema


def _base_schema() -> dict[str, object]:
    """The v1-v3 schema, unconstrained; see :func:`response_schema`."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["occurrences"],
        "properties": {
            "occurrences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(RESPONSE_FIELDS),
                    "properties": {
                        "ordinal": {"type": "integer"},
                        "verdict": {"type": "string", "enum": sorted(schema_lib.VERDICTS)},
                        "quotation": {"type": "string", "enum": sorted(schema_lib.QUOTATIONS)},
                        "concrete_case": {
                            "type": "string",
                            "enum": sorted(schema_lib.CONCRETE_CASE),
                        },
                        "speaker_position": {
                            "type": "string",
                            "enum": sorted(schema_lib.POSITIONS),
                        },
                        "function": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(schema_lib.FUNCTIONS)},
                        },
                        "referent": {"type": "string"},
                        "proposed_referent": {"type": "string"},
                        "referent_source": {
                            "type": "string",
                            "enum": sorted(schema_lib.REFERENT_SOURCES),
                        },
                        "accused_actor": {"type": "string"},
                        "victim_group": {"type": "string"},
                        "own_state_accused": {
                            "type": "string",
                            "enum": sorted(schema_lib.OWN_STATE_ACCUSED),
                        },
                        "salience": {"type": "string", "enum": sorted(schema_lib.SALIENCE)},
                        "evidence_quote": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                },
            }
        },
    }


def _as_date(value: object) -> str:
    formatted = getattr(value, "strftime", None)
    return formatted("%Y-%m-%d") if callable(formatted) else str(value)


def render_occurrences(body: str, occurrences: Sequence[Occurrence]) -> str:
    """The numbered list the model answers, one entry per occurrence.

    The speech itself is never marked up. Highlighting the matches inline would
    put characters into the text that the record does not contain, and every
    evidence quote copied across them would fail to locate — so the coordinates
    travel beside the speech instead of inside it.
    """
    spans = sentence_spans(body)
    lines = []
    for occurrence in occurrences:
        lines.append(
            f"[{occurrence.ordinal}] characters {occurrence.start}-{occurrence.end}, "
            f'matched text: "{occurrence.keyword}"'
        )
        lines.append(f"    sentence: {sentence_at(body, occurrence.start, spans)}")
    return "\n".join(lines)


def render_sentences(body: str) -> tuple[str, int]:
    """The speech as numbered sentences, and how many there are.

    For a `sentence-evidence` prompt only. The numbering is the same
    segmentation the anchor and the concordance use, so sentence *n* of the
    request is `sentence_spans(body)[n - 1]` when the answer comes back.
    """
    spans = sentence_spans(body)
    lines = [
        f"[{number}] {_WHITESPACE_RE.sub(' ', body[start:end]).strip()}"
        for number, (start, end) in enumerate(spans, start=1)
    ]
    return "\n".join(lines), len(spans)


def build_request(
    speech: Mapping[str, object],
    body: str,
    occurrences: Sequence[Occurrence],
    pack: PromptPack,
    referents_table: str,
    *,
    referent_ids: Sequence[str] | None = None,
) -> SpeechRequest:
    """One speech, its occurrences, and the two messages that ask about them.

    `referent_ids` is read only by a `referent-enum` prompt, which needs the
    identifiers to build its schema; any other prompt ignores it, so a caller
    may always pass the run's current list.
    """
    if not occurrences:
        raise ValueError("A request needs at least one occurrence.")
    filename = str(speech["filename"])
    ordinals = tuple(occurrence.ordinal for occurrence in occurrences)
    if len(set(ordinals)) != len(ordinals):
        raise ValueError(f"{filename}: occurrence ordinals must be unique.")
    values: dict[str, object] = {
        "filename": filename,
        "date": _as_date(speech.get("date", "")),
        "country_org": speech.get("country_org", ""),
        "participant_type": speech.get("participanttype", ""),
        "meeting_symbol": speech.get("meeting_symbol", ""),
        "agenda_item": speech.get("agenda_item_manual", ""),
        "speech": body,
        "occurrence_count": len(occurrences),
        "occurrences": render_occurrences(body, occurrences),
    }
    sentence_count = 0
    if SENTENCE_EVIDENCE in pack.constraints:
        values[SENTENCES_PLACEHOLDER], sentence_count = render_sentences(body)
    schema = None
    if pack.constraints:
        if REFERENT_ENUM in pack.constraints and referent_ids is None:
            raise ValueError(f"{pack.name} declares {REFERENT_ENUM} but no referent ids were given.")
        schema = response_schema(
            referents=referent_ids if REFERENT_ENUM in pack.constraints else None,
            ordinals=ordinals if REFERENT_ENUM in pack.constraints else None,
            sentences=sentence_count,
        )
    return SpeechRequest(
        filename=filename,
        custom_id=filename.removesuffix(".txt"),
        system=_fill(pack.system_template, {"referents_table": referents_table}),
        user=_fill(pack.user_template, values),
        ordinals=ordinals,
        schema=schema,
        sentence_count=sentence_count,
    )


def cache_key(prompt_digest: str, referents_digest: str) -> str:
    """The routing key for the fixed prefix these two files make.

    Every request in a run opens with the same system message: the prompt's own
    text with the referents table rendered into it. That prefix is about 8,000
    tokens of the roughly 4,200 a request averages beyond it, and it was sent
    3,273 times — the review of 1 September (§4.2, item 8) measured some 9M of
    Luna's 13.8M input tokens as the fixed part, and found neither script asking
    for it to be cached.

    Caching is automatic on both providers once a prefix is long enough; what a
    key buys is that requests sharing a prefix are routed to the same cache
    rather than spread over several. So it is derived from exactly what the
    prefix is made of — the prompt bytes and the referent file's — and changes
    when either does, which is when the cached prefix is no longer the same
    text. Never the run id: two runs of one prompt should share the cache, which
    is most of the point of a pilot at all.
    """
    return f"unsc-genocide-{prompt_digest[:12]}-{referents_digest[:12]}"


def request_body(
    request: SpeechRequest,
    *,
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    prompt_cache_key: str = "",
    reasoning_location: str = "request",
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
) -> dict[str, object]:
    """The `/v1/responses` body, identical in a batch line and in a live call.

    Built here rather than in 14 so that the two paths cannot drift: a pilot run
    made with `--live` and a corpus run made through the Batch API have to be
    asking the same question, or the pilot measures nothing.

    `prompt_cache_key` is omitted entirely when empty rather than sent as a blank
    string, so a run made without it is byte-identical to a run made before the
    field existed and the two remain comparable.
    """
    if reasoning_location not in {"request", "chat_template_kwargs", "enable_thinking"}:
        raise ValueError(f"Unknown reasoning parameter location: {reasoning_location}")
    body: dict[str, object] = {
        "model": model,
        "input": [
            {"role": "developer", "content": request.system},
            {"role": "user", "content": request.user},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "strict": True,
                "schema": request.schema or response_schema(),
            }
        },
        "max_output_tokens": max_output_tokens,
    }
    if reasoning_location == "request":
        body["reasoning"] = {"effort": reasoning_effort}
    elif reasoning_location == "enable_thinking":
        if reasoning_effort not in {"low", "high"}:
            raise ValueError("Boolean thinking supports only low (off) and high (on)")
        body["chat_template_kwargs"] = {"enable_thinking": reasoning_effort == "high"}
    else:
        body["chat_template_kwargs"] = {"reasoning_effort": reasoning_effort}
    if prompt_cache_key:
        body["prompt_cache_key"] = prompt_cache_key
    if temperature is not None:
        body["temperature"] = temperature
    if top_p is not None:
        body["top_p"] = top_p
    # Omitted when unset, like the two above, so a run made without it keeps
    # its request bytes. vLLM reads it as an extension of the Responses body.
    if top_k is not None:
        body["top_k"] = top_k
    return body


# --- Reading one speech's response -----------------------------------------

def sdk_request_kwargs(body: dict[str, object]) -> dict[str, object]:
    """Adapt the recorded wire body to the SDK without changing its JSON."""
    kwargs = dict(body)
    extra = {key: kwargs.pop(key) for key in ("chat_template_kwargs", "top_k") if key in kwargs}
    if extra:
        kwargs["extra_body"] = extra
    return kwargs



def _functions(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: list[str] = value.split("|")
    elif isinstance(value, list | tuple):
        parts = [str(item) for item in value]
    else:
        raise ValueError(f"Function must be a list or a pipe-joined string: {value!r}")
    if not parts:
        raise ValueError("Function needs at least one label.")
    unknown = [part for part in parts if part not in schema_lib.FUNCTIONS]
    if unknown:
        raise ValueError(f"Unknown function label: {unknown[0] or '(blank)'}")
    if len(set(parts)) != len(parts):
        raise ValueError("Function labels must not be repeated.")
    if len(parts) > 1 and ({"unclear", "not_applicable"} & set(parts)):
        raise ValueError("unclear and not_applicable cannot be combined with other functions.")
    return tuple(parts)


def check_labels(
    entry: Mapping[str, object], referents: set[str], *, schema: str = SCHEMA_VERSION
) -> tuple[str, ...]:
    """The codebook's rules over one occurrence's labels, whatever wrote them.

    Mirrors `audit._validate_labels` for the fields the model supplies. Returns
    the function labels as a tuple so a caller does not parse them twice.

    `schema` is the annotation schema the entry is coded against. Schema 3 is
    what a model is asked for and what a new row is written at; schema 2 is the
    vocabulary of the four committed runs, read here so that 15 can aggregate
    them without their being re-coded — which would mean buying them again.

    `proposed_referent` is required when the referent is `other` and refused on a
    false positive, but is not refused on a controlled referent. The compound
    rule the codebook carries — a passage naming two cases is coded as the first
    one named — has to leave the pair recorded somewhere, and this field is where
    the model already writes free text about a referent. About one in twenty of
    the two runs' `other` rows is such a pair, so losing them would lose the
    evidence for whether the rule is the right one. The rejected alternative was
    a `compound_referents` field of its own, which would oblige the human
    codebook to grow a column no coder has been trained on, to carry something
    this field already carries.
    """
    legacy = str(schema) == schema_lib.LEGACY_SCHEMA_VERSION
    if str(schema) == "3" and str(entry.get("confidence", "")) not in schema_lib.CONFIDENCE:
        raise ValueError("Unknown historical confidence label")
    for field, allowed in (LEGACY_ENUMS if legacy else ENUMS).items():
        value = str(entry[field])
        if value not in allowed:
            raise ValueError(f"Unknown {field} label: {value or '(blank)'}")

    functions = _functions(entry["function"])
    referent = str(entry["referent"])
    if referent not in referents:
        raise ValueError(f"Unknown referent: {referent or '(blank)'}")

    cascade = LEGACY_CASCADE if legacy else CASCADE
    reserved = LEGACY_CASCADE if legacy else RESERVED
    if str(entry["verdict"]) == "false_positive":
        answered = {str(entry[field]) for field in cascade if field != "function"}
        if answered | set(functions) != {"not_applicable"}:
            raise ValueError("False positives must use not_applicable discourse labels.")
        if not legacy and any(
            str(entry[field]).strip() for field in FREE_TEXT_CASCADE
        ):
            raise ValueError("False positives leave the free-text label fields empty.")
    else:
        answered = {str(entry[field]) for field in reserved if field != "function"}
        if "not_applicable" in answered | set(functions):
            raise ValueError("not_applicable is reserved for false positives.")

    if not legacy:
        # One decision, checked once: `concrete_case: no` and
        # `speaker_position: no_position` are two names for the finding that the
        # word is applied to no case here. A row carrying one without the other
        # has taken the decision twice and differently, which is the fault
        # schema 3 exists to remove.
        blank = str(entry["concrete_case"]) == "no"
        if blank != (str(entry["speaker_position"]) == "no_position"):
            raise ValueError(
                "concrete_case 'no' and speaker_position 'no_position' are one decision: "
                f"got {entry['concrete_case']!r} and {entry['speaker_position']!r}."
            )
        if str(entry["verdict"]) != "false_positive" and not str(entry["rationale"]).strip():
            raise ValueError("Every annotation carries a one-sentence rationale.")

    proposed = str(entry["proposed_referent"]).strip()
    if referent == "other" and not proposed:
        raise ValueError("referent 'other' requires a proposed_referent.")
    if str(entry["verdict"]) == "false_positive" and proposed:
        raise ValueError("A false positive has no proposed_referent.")
    return functions


def validate_response(
    payload: object,
    *,
    ordinals: Sequence[int],
    referents: set[str],
    sentences: int = 0,
) -> dict[int, dict[str, object]]:
    """One speech's response, checked against the schema and the codebook.

    Raises on anything that would produce a row nobody can defend: a missing or
    invented occurrence, a label outside the codebook, a broken cascade. The
    caller records the speech as a parse failure and its occurrences simply stay
    absent from the run, where 15 will report them as a coverage gap. Repairing a
    bad response here would be inventing an annotation.
    """
    if isinstance(payload, str | bytes):
        payload = response_document(payload)
    if not isinstance(payload, Mapping):
        raise ValueError(f"Response must be a JSON object, not {type(payload).__name__}.")
    entries = payload.get("occurrences")
    if not isinstance(entries, list):
        raise ValueError("Response must carry an 'occurrences' array.")

    fields = (
        {*RESPONSE_FIELDS, "evidence_sentences"} - {"evidence_quote"}
        if sentences
        else set(RESPONSE_FIELDS)
    )
    labels: dict[int, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("Every occurrence must be a JSON object.")
        if set(entry) != fields:
            unexpected = sorted(set(entry) - fields)
            absent = sorted(fields - set(entry))
            raise ValueError(
                "Occurrence fields do not match the schema: "
                f"unexpected={unexpected}, missing={absent}"
            )
        ordinal = entry["ordinal"]
        if isinstance(ordinal, bool) or not isinstance(ordinal, int):
            raise ValueError(f"Ordinal must be an integer, not {ordinal!r}.")
        if ordinal in labels:
            raise ValueError(f"Ordinal {ordinal} was returned twice.")
        functions = check_labels(entry, referents)
        labels[ordinal] = {
            "verdict": str(entry["verdict"]),
            "quotation": str(entry["quotation"]),
            "concrete_case": str(entry["concrete_case"]),
            "speaker_position": str(entry["speaker_position"]),
            "function": functions,
            "referent": str(entry["referent"]),
            "proposed_referent": str(entry["proposed_referent"]).strip(),
            "referent_source": str(entry["referent_source"]),
            "accused_actor": str(entry["accused_actor"]).strip(),
            "victim_group": str(entry["victim_group"]).strip(),
            "own_state_accused": str(entry["own_state_accused"]),
            "salience": str(entry["salience"]),
            "evidence_quote": "" if sentences else str(entry["evidence_quote"]),
            "rationale": str(entry["rationale"]).strip(),
        }
        if sentences:
            labels[ordinal]["evidence_sentences"] = _sentence_range(
                entry["evidence_sentences"], sentences
            )

    expected = set(ordinals)
    if set(labels) != expected:
        extra_ordinals = sorted(set(labels) - expected)
        absent_ordinals = sorted(expected - set(labels))
        raise ValueError(
            f"Ordinals do not match the request: unexpected={extra_ordinals}, "
            f"missing={absent_ordinals}"
        )
    return labels


def response_document(payload: str | bytes) -> object:
    """Extract one JSON document without repairing what the model wrote.

    vLLM's structured-output constraint normally returns the document alone,
    but open-weight models can still wrap it in a Markdown fence or introduce
    it with prose.  Those wrappers carry no annotation value, so they may be
    removed.  Missing commas, unclosed braces and other malformed JSON are
    never repaired: the caller records the speech as a failure instead.

    The recovery order is deliberate and is the one promised in roadmap C1:
    exact JSON, one fenced block, then the first balanced object or array.
    Strings and escapes are tracked while balancing so braces inside an
    evidence quotation cannot terminate the document early.
    """
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        exact_error = str(error)

    fenced = re.fullmatch(r"\s*```(?:json)?\s*\n?(.*?)\n?```\s*", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    starts = ((text.find("{"), "{", "}"), (text.find("["), "[", "]"))
    candidates = sorted(item for item in starts if item[0] >= 0)
    for start, opening, closing in candidates:
        depth = 0
        quoted = escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
                continue
            if character == '"':
                quoted = True
            elif character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Response is not JSON: {exact_error}")


# --- Assembling and checking rows -------------------------------------------


@dataclass(frozen=True)
class RunMeta:
    """What every row of one run carries about the run that produced it."""

    run_id: str
    model: str
    prompt_version: int
    prompt_sha256: str
    reasoning_effort: str
    lexicon_version: str
    referents_version: str
    term: str
    annotated_at: str


def annotation_rows(
    occurrences: Sequence[Occurrence],
    body: str,
    labels: Mapping[int, Mapping[str, Any]],
    meta: RunMeta,
) -> list[dict[str, object]]:
    """One row per occurrence, in the run's fixed key order."""
    rows = []
    spans = sentence_spans(body) if any("evidence_sentences" in e for e in labels.values()) else []
    for occurrence in occurrences:
        entry = labels[occurrence.ordinal]
        start: int | None
        end: int | None
        if "evidence_sentences" in entry:
            # Sentence evidence cannot be misquoted: the span is the sentences'
            # own, and valid exactly when it holds the occurrence.
            first, last = entry["evidence_sentences"]
            start, end = spans[first - 1][0], spans[last - 1][1]
            quote = body[start:end]
            valid, relocated = start <= occurrence.start and occurrence.end <= end, False
        else:
            quote = str(entry["evidence_quote"])
            start, end, valid, relocated = locate_evidence(
                body, quote, occurrence.start, occurrence.end
            )
        rows.append(
            {
                "occurrence_id": occurrence.occurrence_id,
                "line_id": occurrence.line_id,
                "filename": occurrence.filename,
                "term": meta.term,
                "start": occurrence.start,
                "end": occurrence.end,
                "source_sha256": occurrence.source_sha256,
                "schema_version": SCHEMA_VERSION,
                "lexicon_version": meta.lexicon_version,
                "referents_version": meta.referents_version,
                "run_id": meta.run_id,
                "model": meta.model,
                "prompt_version": meta.prompt_version,
                "prompt_sha256": meta.prompt_sha256,
                "reasoning_effort": meta.reasoning_effort,
                "verdict": entry["verdict"],
                "quotation": entry["quotation"],
                "concrete_case": entry["concrete_case"],
                "speaker_position": entry["speaker_position"],
                "function": "|".join(entry["function"]),
                "referent": entry["referent"],
                "proposed_referent": entry["proposed_referent"],
                "referent_source": entry["referent_source"],
                "accused_actor": entry["accused_actor"],
                "victim_group": entry["victim_group"],
                "own_state_accused": entry["own_state_accused"],
                "salience": entry["salience"],
                "evidence_quote": quote,
                "evidence_start": start,
                "evidence_end": end,
                "evidence_valid": valid,
                "evidence_relocated": relocated,
                "rationale": entry["rationale"],
                "annotated_at": meta.annotated_at,
            }
        )
    return rows


def validate_row(
    row: Mapping[str, Any], referents: set[str], *, appending: bool = True
) -> None:
    """The gate a row passes to be written into a committed run, or read back out.

    Used by 14 on the way out, by 15 on the way in, and by the tests on
    constructed rows, so that the file's shape is asserted by the thing that
    writes it rather than by whatever reads it next.

    `appending` is true at the write seam and false where a committed run is
    read back, and two things hold only at the seam. A run that has been paid
    for cannot be made to satisfy a rule written after it, and refusing to
    aggregate it would delete the evidence rather than improve it:

    - the older row shape, :data:`LEGACY_ROW_FIELDS`. It is annotation schema 2:
      one `stance` field where there are now two, no `referents_version`, no
      `evidence_relocated`, and none of the six fields schema 3 adds. Every
      committed run has it, and it is accepted on the way in and never on the
      way out.
    - a false positive's own located quote. Three rows of the first run answered
      the evidence field with the literal string `not_applicable`, which the
      prompt's cascade invited and nothing refused; the codebook requires a span
      for a false positive exactly as for a true one, because the claim "this
      match is not the word being used" is a claim about a passage and is
      unreadable without it. New runs are held to it. The first run's three rows
      are recorded in `docs/VALIDATION.md` §7 instead.

    The row's own `schema_version` has to agree with its shape, which is what
    stops a schema-2 file being read as though its `stance` column meant what
    `speaker_position` means.
    """
    legacy = tuple(row) == LEGACY_ROW_FIELDS
    shapes = (ROW_FIELDS,) if appending else (ROW_FIELDS, SCHEMA3_ROW_FIELDS, LEGACY_ROW_FIELDS)
    if tuple(row) not in shapes:
        unexpected = sorted(set(row) - set(ROW_FIELDS))
        absent = sorted(set(shapes[-1]) - set(row))
        if unexpected or absent:
            raise ValueError(f"Row keys are wrong: unexpected={unexpected}, missing={absent}")
        raise ValueError("Row keys are in the wrong order; see llm.ROW_FIELDS.")

    expected_schema = schema_lib.LEGACY_SCHEMA_VERSION if legacy else ("3" if tuple(row) == SCHEMA3_ROW_FIELDS else SCHEMA_VERSION)
    check_labels(row, referents, schema=expected_schema)

    for field in ("start", "end"):
        if isinstance(row[field], bool) or not isinstance(row[field], int):
            raise ValueError(f"{field} must be an integer offset into the speech body.")
    if int(row["start"]) >= int(row["end"]):
        raise ValueError("The occurrence span must be nonempty.")
    for flag in ("evidence_valid", "evidence_relocated"):
        if flag in row and not isinstance(row[flag], bool):
            raise ValueError(f"{flag} must be a boolean.")
    if row.get("evidence_relocated") and not row["evidence_valid"]:
        raise ValueError("A relocated quote that does not contain the term is not located.")

    start, end = row["evidence_start"], row["evidence_end"]
    located = [value for value in (start, end) if value is not None]
    if len(located) == 1:
        raise ValueError("evidence_start and evidence_end are recorded together or not at all.")
    if located:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in located):
            raise ValueError("Evidence offsets must be integers or null.")
        if int(start) < 0 or int(end) <= int(start):
            raise ValueError("The evidence span must be nonempty and inside the body.")
    elif row["evidence_valid"]:
        raise ValueError("Evidence cannot be valid without offsets.")
    if row["evidence_valid"] and not (
        int(start) <= int(row["start"]) and int(row["end"]) <= int(end)
    ):
        raise ValueError("Valid evidence must contain the matched term span.")

    # A false positive is the one verdict the prompt's cascade lets a model
    # answer with `not_applicable` in every discourse field, and the review
    # found what that permits: three of the first run's six false positives
    # carry the literal string `not_applicable` as the *evidence quote*, which
    # the locator then cannot place and nothing refused. The codebook requires
    # an evidence span for a false positive exactly as for a true one — the
    # claim "this match is not the word being used" is a claim about a passage,
    # and it is unreadable without the passage. So the cascade stops at the
    # quote, here, where a row is written rather than in the prompt where it is
    # only asked for.
    if appending and str(row["verdict"]) == "false_positive" and not row["evidence_valid"]:
        quote = str(row["evidence_quote"]).strip()
        raise ValueError(
            "A false positive needs a located evidence quote containing the match: "
            f"{quote[:40] or '(blank)'!r} was not found around it."
        )

    if str(row["schema_version"]) != expected_schema:
        raise ValueError(
            f"Row schema version is not {expected_schema}: {row['schema_version']}; "
            "the row's shape and the version it records have to be the same schema."
        )
    coded = str(row["annotated_at"])
    try:
        if date.fromisoformat(coded).isoformat() != coded:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"annotated_at must be an ISO date: {coded or '(blank)'}") from exc


def resolve_row(row: Mapping[str, object]) -> dict[str, object]:
    """One run row in schema 3's vocabulary, whichever schema wrote it.

    The counterpart of :func:`lib.usage_refusals.resolve_referents`, and the
    same argument: a superseded value is *translated* rather than refused,
    because the four committed runs are 12,184 rows that cannot be re-coded
    without being bought again, and refusing them would mean the schema could
    never move.

    A schema-3 row is returned unchanged. A schema-2 row is read as follows:

    - `stance` becomes `speaker_position` through
      :data:`lib.schema.POSITION_FROM_STANCE`, which is six renames and one value
      that changed meaning;
    - `concrete_case` is derived by :func:`lib.schema.concrete_case_from_v1` from
      the stance and the referent, and is `unclear` wherever those two cannot
      answer it;
    - the six fields schema 3 adds have **no v1 image at all** and are returned
      empty — `referent_source`, `accused_actor`, `victim_group`,
      `own_state_accused`, `salience` and `rationale`. They are not guessed, and
      the aggregation reports them as absent for the whole run rather than
      counting an empty string as an answer. That is the honest statement of
      what a v1 run can and cannot say, and it is the reason the pilot exists.

    The row keeps its own `schema_version`, so nothing downstream can mistake a
    resolved row for one that was coded at 3.
    """
    if tuple(row) != LEGACY_ROW_FIELDS:
        return dict(row)
    stance = str(row.get("stance", ""))
    referent = str(row.get("referent", ""))
    resolved = {key: value for key, value in row.items() if key != "stance"}
    resolved.update(
        {
            "referents_version": "1",
            "concrete_case": schema_lib.concrete_case_from_v1(stance, referent),
            "speaker_position": schema_lib.POSITION_FROM_STANCE.get(stance, "unclear"),
            "referent_source": "",
            "accused_actor": "",
            "victim_group": "",
            "own_state_accused": "",
            "salience": "",
            "evidence_relocated": bool(row.get("evidence_relocated", False)),
            "rationale": "",
        }
    )
    return {field: resolved.get(field, "") for field in ROW_FIELDS}


#: The schema-3 fields a schema-2 row cannot answer, in the order the artefact
#: reports them. Named here so that the aggregation and the view agree on what
#: "this run does not carry it" means, and so a reader can see at a glance what
#: the pilot is for.
UNANSWERED_BY_V1: Final = (
    "referent_source",
    "accused_actor",
    "victim_group",
    "own_state_accused",
    "salience",
    "rationale",
)
