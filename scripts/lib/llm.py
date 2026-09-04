"""The model annotation layer: the prompt, the contract, and what comes back.

`scripts/14_llm_annotate.py` is the only caller that talks to an API. Everything
that decides *what a model is asked* and *what is done with what it returns*
lives here, in plain Python, so it can be tested on any machine with no key, no
network and no `openai` package installed. That is the same division 06, 07 and
10 make against torch and spaCy; here the stakes are higher, because a run costs
money and cannot be repeated by CI or by the deploy to find out whether the
parsing was right.

Four things this module is responsible for:

- **The prompt is a file, not a string literal.** `model_annotations/genocide/
  PROMPT.md` holds the system message and the per-speech user template as fenced
  blocks. Its raw bytes are hashed into every manifest and every row, so a label
  can always be traced to the exact wording that produced it, and editing the
  file is a visible version change rather than a silent drift. The superseded
  wordings are kept beside it under `prompts/`, and a run is resolved against
  the one whose bytes it recorded — so revising the prompt costs a new run id
  and not the runs already paid for.
- **The model's labels are checked against the human codebook's own vocabulary.**
  The enums come from :mod:`lib.audit` — the frozensets the human annotation file
  is validated against — so the model cannot invent a category the codebook does
  not have. The false-positive cascade and the multi-label function rules are
  enforced here exactly as `audit._validate_labels` enforces them there. They are
  reimplemented rather than shared because audit's version operates on a merged
  candidate frame; the semantics, not the code path, are what must agree.
- **Evidence is located, not trusted.** The model returns a quotation; this
  module finds it in the speech and records the offsets, or records that it could
  not. A quote that cannot be located is not an error — it is a measurement, and
  `evidence_valid` is one of the numbers the pilot is evaluated on.
- **Nothing here writes anywhere near `annotations/`.** The output is a JSONL row
  set with a fixed key order, appended to a committed run directory under
  `model_annotations/`. docs/PLAN.md §5: no model output may overwrite corpus
  text, lexicon counts or human annotations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from . import audit
from .kwic import sentence_at, sentence_spans
from .occurrences import Occurrence

#: The annotation schema version these rows are coded against — the human
#: codebook's own, because the fields and their vocabularies are the same ones.
SCHEMA_VERSION: Final = audit.SCHEMA_VERSION

#: The exact key set of a row in `annotations.jsonl`, in the order it is written.
#: Order is load-bearing for readability rather than for parsing: a JSONL diff is
#: read by a human, and a run whose keys wander is one nobody can review.
ROW_FIELDS: Final = (
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
    "confidence",
)

#: Single-valued fields and the vocabulary each is closed over.
ENUMS: Final[dict[str, frozenset[str]]] = {
    "verdict": audit.VERDICTS,
    "quotation": audit.QUOTATIONS,
    "concrete_case": audit.CONCRETE_CASE,
    "speaker_position": audit.POSITIONS,
    "referent_source": audit.REFERENT_SOURCES,
    "own_state_accused": audit.OWN_STATE_ACCUSED,
    "salience": audit.SALIENCE,
    "confidence": audit.CONFIDENCE,
}

#: The same, for a row written against annotation schema 2.
LEGACY_ENUMS: Final[dict[str, frozenset[str]]] = {
    "verdict": audit.VERDICTS,
    "quotation": audit.QUOTATIONS,
    "stance": audit.STANCES,
    "confidence": audit.CONFIDENCE,
}

#: The fields a false positive must set to `not_applicable`, and the subset in
#: which that value may not appear otherwise. Both come from `lib.audit`, which
#: is where the human codebook's own rules live: the model is held to the
#: coder's cascade and not to one of its own.
CASCADE: Final = audit.CASCADE_FIELDS
RESERVED: Final = audit.RESERVED_FIELDS
FREE_TEXT_CASCADE: Final = audit.FREE_TEXT_CASCADE_FIELDS

#: The schema-2 cascade, for reading a committed run back.
LEGACY_CASCADE: Final = ("quotation", "stance", "function", "referent")

#: The name the structured-output schema is registered under in a request.
SCHEMA_NAME: Final = "unsc_occurrence_annotations"

#: Placeholders each template declares. Substitution is by literal replacement
#: rather than `str.format`, because both templates contain JSON braces and a
#: format call would read them as fields.
SYSTEM_PLACEHOLDERS: Final = ("referents_table",)
USER_PLACEHOLDERS: Final = (
    "filename",
    "date",
    "country_org",
    "participant_type",
    "meeting_symbol",
    "agenda_item",
    "speech",
    "occurrence_count",
    "occurrences",
)

#: Kinds in `referents.csv`, in the order the rendered table presents them. A
#: kind the file introduces later is appended after these rather than dropped.
KIND_ORDER: Final = ("case", "historical", "meta", "reserved")
KIND_HEADINGS: Final = {
    "case": "Cases and situations:",
    "historical": "Historical referents:",
    "meta": "Non-case referents:",
    "reserved": "Reserved identifiers, whose rules follow this table:",
}

_HEADING_RE = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^```[^\n]*\n(?P<body>.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
_VERSION_RE = re.compile(r"^version:[ \t]*(?P<version>\d+)[ \t]*$", re.MULTILINE)
_WHITESPACE_RE = re.compile(r"\s+")


# --- The prompt ------------------------------------------------------------


#: The directory beside `PROMPT.md` that keeps the *superseded* prompt texts,
#: one file per version, named `v<n>.md`.
#:
#: Every run records the SHA-256 of the prompt file's raw bytes, on the manifest
#: and on all 7,747 of its rows, and 15 publishes that prompt verbatim beside
#: the labels it produced. So the digest is the run's only handle on the wording
#: it was made with, and until this directory existed there was exactly one file
#: that digest could be compared against: editing `PROMPT.md` made both
#: committed runs unpublishable, and `/usage` went dark. That is not a
#: hypothetical — it is the reason two changes were declined in one afternoon,
#: `genocidaires` and the referent identifiers, each of which would have been a
#: better instrument bought at the price of the two runs already paid for.
#:
#: The escape is the one `referents.csv` takes for its own list: keep every past
#: state, and resolve a run against the state it names rather than against
#: today's. A run resolves *by digest*, not by the `prompt_version` number,
#: because the digest is what was actually recorded and a version line is a
#: human's claim about it — the number is checked against the resolved file and
#: a disagreement is a provenance failure, which is the only thing it is good
#: for.
#:
#: The archive holds superseded versions **only**, and `PROMPT.md` alone holds
#: the current one. The rejected alternative was an archive holding every
#: version, `prompts/v2.md` being a byte-for-byte copy of `PROMPT.md`: it reads
#: more evenly, and it costs a state in which the two copies differ, which is
#: the one failure a digest cannot repair and would have to refuse. One writable
#: prompt and an append-only history behind it cannot reach that state at all.
ARCHIVE: Final = "prompts"

_ARCHIVE_NAME_RE = re.compile(r"^v(?P<version>[1-9]\d*)\.md$")


@dataclass(frozen=True)
class PromptPack:
    """One version of the prompt, with the digest that identifies it."""

    version: int
    sha256: str
    #: The file's raw text, as read. Carried rather than re-read from disk
    #: because a superseded version is published from the archive while
    #: `PROMPT.md` holds something else, and a caller that went back to a path
    #: would have to know which of the two it was holding.
    text: str
    system_template: str
    user_template: str
    #: What to call this file when a message has to name it.
    name: str = "PROMPT.md"


@dataclass(frozen=True)
class PromptLibrary:
    """The current prompt and every superseded one, keyed by digest."""

    current: PromptPack
    superseded: tuple[PromptPack, ...]

    @property
    def packs(self) -> tuple[PromptPack, ...]:
        """Newest first, which is the order a failure message lists them in."""
        return (self.current, *sorted(self.superseded, key=lambda p: -p.version))

    def by_digest(self, digest: str) -> PromptPack | None:
        """The prompt whose bytes hash to `digest`, or nothing if none does."""
        for pack in self.packs:
            if pack.sha256 == digest:
                return pack
        return None

    def describe(self) -> list[str]:
        """One line per known prompt, for the message that refuses an unknown."""
        return [f"v{pack.version} {pack.sha256[:12]}... in {pack.name}" for pack in self.packs]


def prompt_sha256(path: Path) -> str:
    """The digest recorded in the manifest and in every row.

    Over the file's raw bytes, not over the parsed sections: the documentation
    around the fenced blocks explains what a label means, and a reader who
    changes it has changed the prompt's provenance even when the two templates
    come out identical.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section(source: str, title: str, path: Path) -> str:
    """The first fenced block under the `## <title>` heading."""
    headings = list(_HEADING_RE.finditer(source))
    for position, heading in enumerate(headings):
        if heading.group("title").strip().lower() != title.lower():
            continue
        end = headings[position + 1].start() if position + 1 < len(headings) else len(source)
        fence = _FENCE_RE.search(source, heading.end(), end)
        if not fence:
            raise ValueError(f"{path.name}: section '## {title}' has no fenced block.")
        return fence.group("body")
    raise ValueError(f"{path.name}: no '## {title}' section.")


def load_prompt(path: Path) -> PromptPack:
    """Read PROMPT.md into the two templates and the digest of the whole file."""
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file is missing: {path}")
    source = path.read_text(encoding="utf-8")
    version = _VERSION_RE.search(source)
    if not version:
        raise ValueError(f"{path.name}: no 'version: <n>' line in the header.")
    pack = PromptPack(
        version=int(version.group("version")),
        sha256=prompt_sha256(path),
        text=source,
        system_template=_section(source, "System", path),
        user_template=_section(source, "User template", path),
        name=path.name,
    )
    for template, declared, name in (
        (pack.system_template, SYSTEM_PLACEHOLDERS, "System"),
        (pack.user_template, USER_PLACEHOLDERS, "User template"),
    ):
        missing = [key for key in declared if "{" + key + "}" not in template]
        if missing:
            raise ValueError(
                f"{path.name}: '## {name}' is missing placeholders: {', '.join(missing)}"
            )
    return pack


def load_prompt_library(path: Path) -> PromptLibrary:
    """`PROMPT.md` and every superseded version beside it, checked as one set.

    The current file is the one 14 and 16 render; the files under
    :data:`ARCHIVE` are the ones earlier runs were made with, and each is loaded
    through :func:`load_prompt` rather than merely hashed, so a text that no
    longer parses into two templates is found here and not on the day someone
    tries to reproduce a run from it.

    Four rules, each of which exists because breaking it would make a run's
    digest ambiguous or its version a lie:

    - an archived file is named for the version it declares, `v<n>.md`, so the
      directory can be read without opening anything;
    - no two prompts in the library share a version number;
    - every archived version is below the current one. The archive is history,
      and a version above `PROMPT.md`'s means an edit went backwards. This is
      also what forbids parking a copy of the current text in the archive, which
      is the layout rejected above;
    - no two share a digest. The three rules above already make that
      unreachable — two files with different `version:` lines cannot have the
      same bytes — so this one is held for the invariant rather than for a case
      anyone has produced: :meth:`PromptLibrary.by_digest` returns one pack, and
      a library that could answer with two would make it a coin toss.

    An empty or absent archive is the ordinary state of a repository whose
    prompt has never been revised, and is not an error.
    """
    current = load_prompt(path)
    directory = path.parent / ARCHIVE
    superseded: list[PromptPack] = []
    for file in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        name = _ARCHIVE_NAME_RE.match(file.name)
        if not name:
            raise ValueError(
                f"{ARCHIVE}/{file.name}: an archived prompt is named for its version, "
                "as v<n>.md."
            )
        pack = load_prompt(file)
        if pack.version != int(name.group("version")):
            raise ValueError(
                f"{ARCHIVE}/{file.name} declares version {pack.version}; "
                "the file name and the header have to agree."
            )
        if pack.version >= current.version:
            raise ValueError(
                f"{ARCHIVE}/{file.name} is version {pack.version} and {path.name} is "
                f"version {current.version}; the archive holds superseded versions only."
            )
        superseded.append(
            PromptPack(
                version=pack.version,
                sha256=pack.sha256,
                text=pack.text,
                system_template=pack.system_template,
                user_template=pack.user_template,
                name=f"{ARCHIVE}/{file.name}",
            )
        )

    packs = [current, *superseded]
    for field, label in (("version", "version"), ("sha256", "digest")):
        seen: dict[object, str] = {}
        for pack in packs:
            value = getattr(pack, field)
            if value in seen:
                raise ValueError(
                    f"{pack.name} and {seen[value]} have the same prompt {label} "
                    f"({str(value)[:12]}); a prompt version is one file and one digest."
                )
            seen[value] = pack.name
    return PromptLibrary(current=current, superseded=tuple(superseded))


def _fill(template: str, values: Mapping[str, object]) -> str:
    filled = template
    for key, value in values.items():
        filled = filled.replace("{" + key + "}", str(value))
    return filled


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

    :func:`lib.audit.read_referents` already validates the identifiers and is the
    authority on which ones an annotation may use; this reads the same file for
    the richer fields, tolerating a header that has not yet grown them. A row
    with no declared kind is reserved if it is one of the three reserved IDs and
    a case otherwise, which is what the file meant before `kind` existed.

    Retired identifiers are left out, because the model is offered only what is
    current. They stay in the file so a committed run that used one can still be
    read, but rendering them would invite a new run to reuse a category the
    list has withdrawn, and the run would then be neither v1 nor v2.
    """
    table = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing = sorted({"id", "label", "description"} - set(table.columns))
    if missing:
        raise ValueError(f"Referent file is missing columns: {', '.join(missing)}")
    referents = []
    for values in table.to_dict(orient="records"):
        identifier = str(values["id"])
        if str(values.get("retired_in") or "").strip():
            continue
        default = "reserved" if identifier in audit.DEFAULT_REFERENTS else "case"
        referents.append(
            Referent(
                id=identifier,
                label=str(values["label"]),
                description=str(values["description"]),
                kind=str(values.get("kind") or "") or default,
                years=str(values.get("years") or ""),
            )
        )
    return referents


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


def response_schema() -> dict[str, object]:
    """The strict JSON schema the structured output is constrained to.

    `referent` is a plain string rather than an enum: the controlled list is a
    reviewed CSV that grows during the pilot, and baking thirty identifiers into
    the schema would make every addition a prompt change. It is validated against
    the run's referent set on the way back in, where a violation can be reported
    per occurrence instead of failing a whole speech at the decoder.
    """
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
                        "verdict": {"type": "string", "enum": sorted(audit.VERDICTS)},
                        "quotation": {"type": "string", "enum": sorted(audit.QUOTATIONS)},
                        "concrete_case": {
                            "type": "string",
                            "enum": sorted(audit.CONCRETE_CASE),
                        },
                        "speaker_position": {
                            "type": "string",
                            "enum": sorted(audit.POSITIONS),
                        },
                        "function": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(audit.FUNCTIONS)},
                        },
                        "referent": {"type": "string"},
                        "proposed_referent": {"type": "string"},
                        "referent_source": {
                            "type": "string",
                            "enum": sorted(audit.REFERENT_SOURCES),
                        },
                        "accused_actor": {"type": "string"},
                        "victim_group": {"type": "string"},
                        "own_state_accused": {
                            "type": "string",
                            "enum": sorted(audit.OWN_STATE_ACCUSED),
                        },
                        "salience": {"type": "string", "enum": sorted(audit.SALIENCE)},
                        "evidence_quote": {"type": "string"},
                        "rationale": {"type": "string"},
                        "confidence": {"type": "string", "enum": sorted(audit.CONFIDENCE)},
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


def build_request(
    speech: Mapping[str, object],
    body: str,
    occurrences: Sequence[Occurrence],
    pack: PromptPack,
    referents_table: str,
) -> SpeechRequest:
    """One speech, its occurrences, and the two messages that ask about them."""
    if not occurrences:
        raise ValueError("A request needs at least one occurrence.")
    filename = str(speech["filename"])
    ordinals = tuple(occurrence.ordinal for occurrence in occurrences)
    if len(set(ordinals)) != len(ordinals):
        raise ValueError(f"{filename}: occurrence ordinals must be unique.")
    user = _fill(
        pack.user_template,
        {
            "filename": filename,
            "date": _as_date(speech.get("date", "")),
            "country_org": speech.get("country_org", ""),
            "participant_type": speech.get("participanttype", ""),
            "meeting_symbol": speech.get("meeting_symbol", ""),
            "agenda_item": speech.get("agenda_item_manual", ""),
            "speech": body,
            "occurrence_count": len(occurrences),
            "occurrences": render_occurrences(body, occurrences),
        },
    )
    return SpeechRequest(
        filename=filename,
        custom_id=filename.removesuffix(".txt"),
        system=_fill(pack.system_template, {"referents_table": referents_table}),
        user=user,
        ordinals=ordinals,
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
) -> dict[str, object]:
    """The `/v1/responses` body, identical in a batch line and in a live call.

    Built here rather than in 14 so that the two paths cannot drift: a pilot run
    made with `--live` and a corpus run made through the Batch API have to be
    asking the same question, or the pilot measures nothing.

    `prompt_cache_key` is omitted entirely when empty rather than sent as a blank
    string, so a run made without it is byte-identical to a run made before the
    field existed and the two remain comparable.
    """
    body: dict[str, object] = {
        "model": model,
        "reasoning": {"effort": reasoning_effort},
        "input": [
            {"role": "developer", "content": request.system},
            {"role": "user", "content": request.user},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "strict": True,
                "schema": response_schema(),
            }
        },
        "max_output_tokens": max_output_tokens,
    }
    if prompt_cache_key:
        body["prompt_cache_key"] = prompt_cache_key
    return body


# --- Reading one speech's response -----------------------------------------


def _functions(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        parts: list[str] = value.split("|")
    elif isinstance(value, list | tuple):
        parts = [str(item) for item in value]
    else:
        raise ValueError(f"Function must be a list or a pipe-joined string: {value!r}")
    if not parts:
        raise ValueError("Function needs at least one label.")
    unknown = [part for part in parts if part not in audit.FUNCTIONS]
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
    legacy = str(schema) == audit.LEGACY_SCHEMA_VERSION
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
) -> dict[int, dict[str, object]]:
    """One speech's response, checked against the schema and the codebook.

    Raises on anything that would produce a row nobody can defend: a missing or
    invented occurrence, a label outside the codebook, a broken cascade. The
    caller records the speech as a parse failure and its occurrences simply stay
    absent from the run, where 15 will report them as a coverage gap. Repairing a
    bad response here would be inventing an annotation.
    """
    if isinstance(payload, str | bytes):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Response is not JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"Response must be a JSON object, not {type(payload).__name__}.")
    entries = payload.get("occurrences")
    if not isinstance(entries, list):
        raise ValueError("Response must carry an 'occurrences' array.")

    labels: dict[int, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("Every occurrence must be a JSON object.")
        if set(entry) != set(RESPONSE_FIELDS):
            unexpected = sorted(set(entry) - set(RESPONSE_FIELDS))
            absent = sorted(set(RESPONSE_FIELDS) - set(entry))
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
            "evidence_quote": str(entry["evidence_quote"]),
            "rationale": str(entry["rationale"]).strip(),
            "confidence": str(entry["confidence"]),
        }

    expected = set(ordinals)
    if set(labels) != expected:
        extra = sorted(set(labels) - expected)
        absent = sorted(expected - set(labels))
        raise ValueError(f"Ordinals do not match the request: unexpected={extra}, missing={absent}")
    return labels


# --- Locating the evidence --------------------------------------------------


def _flatten(source: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed text, and where each character came from.

    `offsets[i]` is the index in `source` of `flat[i]`, so a span found in the
    flattened text maps straight back without a second search over the original.
    """
    flat: list[str] = []
    offsets: list[int] = []
    space = False
    for index, character in enumerate(source):
        if character.isspace():
            space = True
            continue
        if space and flat:
            flat.append(" ")
            offsets.append(index)
        space = False
        flat.append(character)
        offsets.append(index)
    return "".join(flat), offsets


#: Characters the record's typography and a model's transcription of it disagree
#: about, mapped to the plain form the two can be compared through.
#:
#: The Council's records are typeset with curly quotation marks and en dashes,
#: and a model asked for a verbatim span returns the passage as prose with the
#: typography normalised on the way out — so the quote is the right words and
#: not the right bytes, and an exact substring search finds nothing. NFKC folds
#: the ligatures, the non-breaking spaces and the compatibility forms; this
#: table folds what NFKC leaves alone, because Unicode holds that a curly
#: apostrophe and a straight one are different characters and is right to.
#:
#: Every replacement is one character wide, and the fold is applied character by
#: character rather than to the whole string, so a folded body indexes into the
#: same positions as the body it was folded from.
FOLDED: Final[dict[str, str]] = {
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark — the record's apostrophe
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",  # prime, which OCR reads an apostrophe as
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u201e": '"',
    "\u2033": '"',
    "\u00ab": '"',  # guillemets, from the French-language records
    "\u00bb": '"',
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash — the record's range and parenthetical dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\u00ad": "-",  # soft hyphen
}

#: Quotation marks a model wraps around the span it is reporting. Stripped from
#: the *ends of the quote* alone, in the relocating pass alone, and never from
#: the record: six of the eighteen quotes the two runs could not place are a
#: verbatim span with one quotation mark in front of it that the record does not
#: have there — the model has marked the passage as a quotation, which is a
#: statement about the passage and not part of it.
WRAPPERS: Final = "\"'\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a\u201e\u201a "


def _fold(character: str) -> str:
    """One character in the form two typographies can be compared through.

    NFKC, the table above, and lower case, in that order, and always exactly one
    character wide: a fold that changed the length would break the offset
    mapping :func:`_normalised` builds, and the offsets are what make a span
    found in the folded text a span in the real body. Anything NFKC or `lower`
    expands — the Turkish dotted capital, a handful of ligatures the corpus does
    not contain — keeps its original character rather than being expanded, which
    costs a match nobody has yet needed and cannot cost an offset.

    Lower case is here because two of the unplaced quotes differ from the record
    in exactly one letter's case, at the front, where the model has presented a
    mid-sentence clause as a sentence of its own.
    """
    folded = unicodedata.normalize("NFKC", FOLDED.get(character, character)).lower()
    return folded if len(folded) == 1 else character


def _normalised(source: str) -> tuple[str, list[int]]:
    """The folded, whitespace-collapsed text, and where each character came from.

    :func:`_flatten` with two more relaxations, each one a case the two
    committed runs actually produced:

    - every character folded by :func:`_fold`;
    - the space after a hyphen dropped, which closes the record's line-break
      hyphenation. The Council's records break words across lines and the OCR
      keeps the break, so the body holds `gender- based` and
      `Secretary- General's` where the model returns the word whole. The rule is
      applied to both sides, so a genuine dash before a word — the record's
      parenthetical em dash — is closed on both and still matches.

    `offsets[i]` is the index in `source` of the ith character of the result, as
    in :func:`_flatten`, so a span found here maps back without a second search.
    """
    text: list[str] = []
    offsets: list[int] = []
    space = False
    for index, character in enumerate(source):
        if character.isspace():
            space = True
            continue
        if space and text and text[-1] != "-":
            text.append(" ")
            offsets.append(index)
        space = False
        text.append(_fold(character))
        offsets.append(index)
    return "".join(text), offsets


def _matches(haystack: str, needle: str) -> list[int]:
    found = []
    position = haystack.find(needle)
    while position != -1:
        found.append(position)
        position = haystack.find(needle, position + 1)
    return found


def _spans(text: str, needle: str, offsets: list[int]) -> list[tuple[int, int]]:
    """Every match of `needle` in a normalised `text`, as spans in the original.

    One place rather than two, because the two normalising passes below differ
    only in how they normalise and a second copy of this arithmetic is a second
    chance to be off by one at the end of a span.
    """
    return [
        (offsets[position], offsets[position + len(needle) - 1] + 1)
        for position in _matches(text, needle)
    ]


def _choose(spans: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    """The span that best answers for the occurrence at `[start, end)`.

    Containing beats overlapping beats first-in-the-speech. A speaker who says
    "genocide" six times in one paragraph produces six occurrences whose evidence
    quotes may be identical strings; picking the first match every time would
    attach five of them to a passage they are not in.
    """
    for span in spans:
        if span[0] <= start and end <= span[1]:
            return span
    for span in spans:
        if span[0] < end and start < span[1]:
            return span
    return spans[0]


def locate_evidence(
    body: str, quote: str, occurrence_start: int, occurrence_end: int
) -> tuple[int | None, int | None, bool, bool]:
    """Where the model's quotation actually is, and whether it can be believed.

    Three passes, each admitting one more kind of difference between what the
    record says and what a model returned when asked to copy it:

    1. exact substring;
    2. runs of whitespace collapsed on both sides, which is what a model returns
       when it copies across a line break in the record;
    3. the relocating pass — :func:`_normalised` on both sides, and the model's
       own wrapping quotation marks stripped off the quote.

    The third is the review's (§4.5, item 4). Of the eighteen quotes the two
    committed runs could not place, ten are of this kind and none of them is a
    fabrication: six carry a leading quotation mark the record does not have
    there, two straddle a word the record hyphenates across a line break, and
    two differ from the record in the case of one letter. The remaining eight
    are three false positives answered with the literal string
    `not_applicable`, one quote found in a different sentence of the same
    speech, and four passages the model has genuinely paraphrased or spliced —
    and those must stay unplaced, which is what the relaxations are kept narrow
    for.

    A quote placed by the third pass is *relocated*, and the row carries the
    flag. Its offsets are as good as any other pass's; what the flag records is
    that the record's punctuation, hyphenation or capitalisation had to be
    ignored to find it, and a reader counting how far a run's evidence can be
    trusted is entitled to know how many.

    Each pass maps its match back through its own normalisation, so the offsets
    recorded are into the real body and never into a normalised copy.

    Returns `(start, end, valid, relocated)`. `valid` is true only when the
    located passage contains the occurrence's own span, which is the codebook's
    rule for a human evidence span too. A quote that is found in the wrong place
    still reports where it was found, marked invalid, because that is the more
    useful thing to look at; a quote that is nowhere in the speech returns
    `(None, None, False, False)`. Never raises: an unlocatable quote is a
    measurement of the run, not a fault in it.
    """
    if not quote.strip():
        return None, None, False, False

    relocated = False
    spans = [(position, position + len(quote)) for position in _matches(body, quote)]
    if not spans:
        flat, offsets = _flatten(body)
        needle = _WHITESPACE_RE.sub(" ", quote).strip()
        if not needle:
            return None, None, False, False
        spans = _spans(flat, needle, offsets)
    if not spans:
        folded, offsets = _normalised(body)
        needle, _ = _normalised(quote.strip(WRAPPERS))
        if not needle:
            return None, None, False, False
        spans = _spans(folded, needle, offsets)
        relocated = bool(spans)
    if not spans:
        return None, None, False, False

    start, end = _choose(spans, occurrence_start, occurrence_end)
    return start, end, start <= occurrence_start and occurrence_end <= end, relocated


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
    labels: Mapping[int, Mapping[str, object]],
    meta: RunMeta,
) -> list[dict[str, object]]:
    """One row per occurrence, in the run's fixed key order."""
    rows = []
    for occurrence in occurrences:
        entry = labels[occurrence.ordinal]
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
                "confidence": entry["confidence"],
                "annotated_at": meta.annotated_at,
            }
        )
    return rows


def validate_row(
    row: Mapping[str, object], referents: set[str], *, appending: bool = True
) -> None:
    """The gate a row passes to be written into a committed run, or read back out.

    Used by 14 and 16 on the way out, by 15 on the way in, and by the tests on
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
    shapes = (ROW_FIELDS,) if appending else (ROW_FIELDS, LEGACY_ROW_FIELDS)
    if tuple(row) not in shapes:
        unexpected = sorted(set(row) - set(ROW_FIELDS))
        absent = sorted(set(shapes[-1]) - set(row))
        if unexpected or absent:
            raise ValueError(f"Row keys are wrong: unexpected={unexpected}, missing={absent}")
        raise ValueError("Row keys are in the wrong order; see llm.ROW_FIELDS.")

    expected_schema = audit.LEGACY_SCHEMA_VERSION if legacy else SCHEMA_VERSION
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

    The counterpart of `15_usage.py::resolve_referents`, and the same argument:
    a superseded value is *translated* rather than refused, because the four
    committed runs are 12,184 rows that cannot be re-coded without being bought
    again, and refusing them would mean the schema could never move.

    A schema-3 row is returned unchanged. A schema-2 row is read as follows:

    - `stance` becomes `speaker_position` through
      :data:`lib.audit.POSITION_FROM_STANCE`, which is six renames and one value
      that changed meaning;
    - `concrete_case` is derived by :func:`lib.audit.concrete_case_from_v1` from
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
            "concrete_case": audit.concrete_case_from_v1(stance, referent),
            "speaker_position": audit.POSITION_FROM_STANCE.get(stance, "unclear"),
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


# --- The run file ------------------------------------------------------------


def read_rows(path: Path) -> list[dict[str, object]]:
    """Every row of a run's `annotations.jsonl`, or nothing if it has none yet."""
    if not path.is_file():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} line {number} is not JSON: {exc}") from exc
    return rows


def append_rows(path: Path, rows: Iterable[Mapping[str, object]]) -> int:
    """Append rows and get them onto the disk before returning.

    Deliberately not atomic-replace, which is how every other artefact in this
    repository is written. A run is hours of paid API calls arriving in pieces,
    and rewriting the whole file per batch would risk the one failure mode that
    actually matters here: losing work already paid for. The file only ever
    grows, each line is complete when written, and a crash costs the batch in
    flight rather than the run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
        stream.flush()
        os.fsync(stream.fileno())
    return written


def completed(
    path: Path,
    occurrences: Sequence[Occurrence],
    *,
    prompt_sha256: str,
    model: str,
) -> set[str]:
    """Speeches this run has already annotated in full, for a resumed run.

    Refuses rather than resumes when the file was written with a different
    prompt or a different model: a run is one prompt and one model, and a mixed
    `annotations.jsonl` is a file whose rows cannot be compared with each other.
    A changed prompt is a new run id, not a continuation.

    Refuses too when a row names an occurrence the corpus no longer has. The
    occurrence ID is built over the span and the digest of the speech body, so
    that only happens when the corpus or the lexicon moved underneath the run,
    and appending to it would silently mix two enumerations.
    """
    rows = read_rows(path)
    if not rows:
        return set()

    stale_prompts = {str(row.get("prompt_sha256", "")) for row in rows} - {prompt_sha256}
    if stale_prompts:
        raise ValueError(
            f"{path.name} was written with a different prompt "
            f"({sorted(stale_prompts)[0][:12]}...); a changed prompt is a new run id."
        )
    stale_models = {str(row.get("model", "")) for row in rows} - {model}
    if stale_models:
        raise ValueError(
            f"{path.name} was written with a different model ({sorted(stale_models)[0]}); "
            "a run is one prompt and one model."
        )

    expected: dict[str, set[str]] = {}
    for occurrence in occurrences:
        expected.setdefault(occurrence.filename, set()).add(occurrence.occurrence_id)
    known = {identifier for identifiers in expected.values() for identifier in identifiers}

    seen: dict[str, set[str]] = {}
    for row in rows:
        identifier = str(row.get("occurrence_id", ""))
        if identifier not in known:
            raise ValueError(
                f"{path.name} names an occurrence the corpus does not have ({identifier[:12]}"
                "...); the corpus or the lexicon changed under this run."
            )
        seen.setdefault(str(row.get("filename", "")), set()).add(identifier)
    return {filename for filename, ids in expected.items() if ids <= seen.get(filename, set())}
