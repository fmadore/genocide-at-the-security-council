"""The prompt: one versioned file, its archive, and the templates inside it.

**The prompt is a file, not a string literal.** `model_annotations/genocide/
PROMPT.md` holds the system message and the per-speech user template as fenced
blocks. Its raw bytes are hashed into every manifest and every row, so a label
can always be traced to the exact wording that produced it, and editing the
file is a visible version change rather than a silent drift. The superseded
wordings are kept beside it under `prompts/`, and a run is resolved against
the one whose bytes it recorded — so revising the prompt costs a new run id
and not the runs already paid for.

Reading and checking those files is all this module does. What is asked of a
model with them, and what is done with the answer, is `lib.llm`'s.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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

#: Constraints a prompt may declare on a `constraints:` line in its header,
#: each of which changes what the model is asked for and so is part of the
#: prompt's own versioned text. A prompt that declares none — v1 to v3 — builds
#: byte-identical requests to the ones its runs were made with.
#:
#: `referent-enum` puts the controlled identifiers, the request's own ordinals
#: and the exact number of occurrences into the structured-output schema, so a
#: guided decoder cannot return "Rwanda" for `rwanda` (73 of the Qwen run's 77
#: refusals) or answer an occurrence twice. `sentence-evidence` numbers the
#: speech's sentences and asks for evidence as a first and last sentence number
#: instead of a copied quotation, so evidence is contiguous and always located
#: (docs/ROADMAP.md, RV7 and RV8).
REFERENT_ENUM: Final = "referent-enum"
SENTENCE_EVIDENCE: Final = "sentence-evidence"
CONSTRAINTS: Final = frozenset({REFERENT_ENUM, SENTENCE_EVIDENCE})
_CONSTRAINTS_RE = re.compile(r"^constraints:[ \t]*(?P<names>[^\n]*)$", re.MULTILINE)

#: The placeholder a `sentence-evidence` prompt must carry: the numbered list.
SENTENCES_PLACEHOLDER: Final = "sentences"

_HEADING_RE = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^```[^\n]*\n(?P<body>.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
_VERSION_RE = re.compile(r"^version:[ \t]*(?P<version>\d+)[ \t]*$", re.MULTILINE)


#: The directory beside `PROMPT.md` that keeps the *superseded* prompt texts,
#: one file per version, named `v<n>.md`.
#:
#: Every run records the SHA-256 of the prompt file's raw bytes, on the manifest
#: and on every one of its rows, and 15 publishes that prompt verbatim beside
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
    #: The instrument constraints the header declares; see :data:`CONSTRAINTS`.
    constraints: frozenset[str] = frozenset()


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
    declared_line = _CONSTRAINTS_RE.search(source.split("## System", 1)[0])
    constraints = frozenset(
        name.strip()
        for name in (declared_line.group("names").split(",") if declared_line else [])
        if name.strip()
    )
    if unknown := sorted(constraints - CONSTRAINTS):
        raise ValueError(f"{path.name}: unknown constraints {unknown}; known: {sorted(CONSTRAINTS)}")
    pack = PromptPack(
        version=int(version.group("version")),
        sha256=prompt_sha256(path),
        text=source,
        system_template=_section(source, "System", path),
        user_template=_section(source, "User template", path),
        name=path.name,
        constraints=constraints,
    )
    user_placeholders = (
        (*USER_PLACEHOLDERS, SENTENCES_PLACEHOLDER)
        if SENTENCE_EVIDENCE in constraints
        else USER_PLACEHOLDERS
    )
    for template, declared, name in (
        (pack.system_template, SYSTEM_PLACEHOLDERS, "System"),
        (pack.user_template, user_placeholders, "User template"),
    ):
        missing = [key for key in declared if "{" + key + "}" not in template]
        if missing:
            raise ValueError(
                f"{path.name}: '## {name}' is missing placeholders: {', '.join(missing)}"
            )
    return pack


def load_prompt_library(path: Path) -> PromptLibrary:
    """`PROMPT.md` and every superseded version beside it, checked as one set.

    The current file is the one 14 renders; the files under
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
