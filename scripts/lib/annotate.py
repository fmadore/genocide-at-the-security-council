"""What 14 and 16 do identically, in one place, so that they cannot drift.

`14_llm_annotate.py` and `16_llm_annotate_gemini.py` ask two models the same
question about the same population with the same prompt bytes, and the whole
value of the second run rests on that being true. Until now it was true because
the second script was written by copying the first: `gather`, `output_ceiling`,
`read_manifest`, `write_manifest` and `refuse_mismatch` existed twice, with a
comment in 16 saying so and a test pinning the constants either side. The review
of 1 September 2026 (§4.5, item 10) is right that pinning constants is not
testing behaviour — two `gather` functions can agree on `DOCUMENTED_SPEECHES`
and still enumerate differently — so they live here instead, and the parity test
runs them.

A module and not a base class. There is one enumeration and one manifest shape,
not a family of them, and the two steps differ where the provider differs: how a
request is built, how a response is read, how tokens are named. Those stay in
the steps, beside the SDK each needs, and nothing here imports either SDK.

**Counting requests.** The manifest's `requests` block describes *effort*, and
the review found it describing intention instead (§4.5, item 1). The Gemini run
recorded 7,966 requests submitted over a corpus of 3,273 speeches: each pass
added the number of speeches it *meant* to ask about, whether or not the batch
quota let it create a single job, and one refused outright still added 73. Its
`returned: 4,474` counted every answer downloaded, so a `--poll` that re-read
three jobs counted 1,200 answers a second time. Both are counted here at the
moment the work happens — a request when a job is created or a live call is
sent, a return when a `custom_id` is answered for the first time in this run —
and every pass is recorded in `passes` with its mode, so a manifest says what
was done rather than what was attempted.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from . import artifacts, console, frames, lexicon, llm
from . import occurrences as occurrences_lib
from .paths import ROOT, SPEECHES_NORM

#: The one term the model-assisted layer covers; see Phase L in
#: `docs/IMPROVEMENT_ROADMAP.md` for why the scope is a single word.
TERM: Final = "genocide"

#: docs/CORPUS.md §8, reproduced exactly by 03 and by `lib.occurrences`. A run
#: that enumerates anything else is annotating a different corpus, and its rows
#: could not be joined to the published counts. Only `--limit` may leave this
#: unmet, and the manifest records the limit that did.
DOCUMENTED_SPEECHES: Final = 3_273
DOCUMENTED_OCCURRENCES: Final = 6_092

#: Columns a run needs. The normalised frame is 99 columns and 389 MB of text;
#: reading all of it to use eight of them is a minute of nothing.
COLUMNS: Final = [
    "filename",
    "body_start",
    "text",
    "date",
    "meeting_symbol",
    "country_org",
    "agenda_item_manual",
    "participanttype",
]

#: A generous ceiling on one speech's answer, as `base + per_occurrence * n`.
#:
#: Reasoning tokens count against this on both providers, so the bound has to
#: cover the thinking as well as the JSON, and the review (§4.5, item 9) found
#: the old `12,000 + 1,200 * n` under-provisioning long speeches: one Gemini
#: speech with three occurrences was truncated at 15,600 tokens and lost, and
#: another with two came within 271 tokens of its own ceiling.
#:
#: The run's own arithmetic says why the per-occurrence term was the wrong place
#: to fix that. Over the 3,273 answers Gemini returned, thinking plus output
#: fits `1,288 + 651 * n` with a residual reaching 12,939 tokens on a single
#: speech: how long the thinking runs is a property of how hard the passage is,
#: not of how many occurrences it holds. So the *base* absorbs the spread — the
#: largest total observed was 18,781 tokens, and 32,000 clears it by the whole
#: width of that residual — while the per-occurrence term stays at 1,200, which
#: is already seven times the 154 output tokens an occurrence's JSON costs.
#:
#: A ceiling is a cap and not a reservation: neither provider bills for tokens a
#: model did not generate, so the headroom is free, and a truncated answer costs
#: a whole speech.
BASE_OUTPUT_TOKENS: Final = 32_000
PER_OCCURRENCE_TOKENS: Final = 1_200

#: Requests per batch file. The API ceilings are far higher; this is about how
#: much is in flight behind one id when something goes wrong, and about getting
#: the first rows onto disk within hours rather than at the end.
BATCH_CHUNK: Final = 400


@dataclass(frozen=True)
class Speech:
    """One speech in scope, with everything a request and its rows need."""

    filename: str
    custom_id: str
    body: str
    meta: dict[str, object]
    occurrences: list[occurrences_lib.Occurrence]


@dataclass
class Outcome:
    """What one pass returned, before anything is written.

    `requests` counts what was actually sent — one per line of a batch file that
    became a job, one per live call — and not what the pass set out to send. A
    chunk the quota refused creates no job and sends nothing, and the manifest
    must not say otherwise.
    """

    responses: dict[str, dict[str, object]] = field(default_factory=dict)
    failures: list[dict[str, object]] = field(default_factory=list)
    requests: int = 0


Builder = Callable[[Speech], llm.SpeechRequest]


def gather(limit: int | None) -> tuple[list[Speech], list[Speech], int]:
    """Every genocide-bearing speech, in corpus order, with its occurrences.

    Returns the whole enumeration and the slice this run is asking about. The
    two differ only under `--limit`, and both are needed: the scope says what to
    ask, while the resume check has to see every occurrence the corpus has, or a
    pilot re-run would read rows from a fuller run as evidence that the corpus
    had moved.
    """
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)
    lex = lexicon.load()
    console.info(f"lexicon version {lex.version} ({lex.updated})")

    found = occurrences_lib.enumerate_term(speeches, bodies, lex.terms[TERM])
    grouped: dict[object, list[occurrences_lib.Occurrence]] = {}
    for occurrence in found:
        grouped.setdefault(occurrence.index, []).append(occurrence)
    console.info(f"{len(found):,} occurrences in {len(grouped):,} speeches")

    if limit is None and (
        len(found) != DOCUMENTED_OCCURRENCES or len(grouped) != DOCUMENTED_SPEECHES
    ):
        console.fail(
            "The enumeration does not reproduce the documented figures",
            [
                f"speeches {len(grouped):,} vs {DOCUMENTED_SPEECHES:,}",
                f"occurrences {len(found):,} vs {DOCUMENTED_OCCURRENCES:,}",
                "run 03 and read docs/VALIDATION.md before spending an API call",
            ],
        )

    everything = []
    for index, items in grouped.items():
        row = speeches.loc[index]
        filename = str(row["filename"])
        everything.append(
            Speech(
                filename=filename,
                custom_id=filename.removesuffix(".txt"),
                body=str(bodies.loc[index]),
                meta={column: row[column] for column in COLUMNS if column != "text"},
                occurrences=items,
            )
        )
    scope = everything
    if limit is not None:
        scope = everything[:limit]
        console.warn(f"--limit {limit}: {len(scope):,} speeches, a pilot and not the corpus")
    return everything, scope, lex.version


def output_ceiling(speech: Speech, maximum: int) -> int:
    """The output ceiling for one speech, under the provider's own hard limit."""
    return min(maximum, BASE_OUTPUT_TOKENS + PER_OCCURRENCE_TOKENS * len(speech.occurrences))


def fresh_returns(responses: Iterable[str], answered: frozenset[str]) -> int:
    """How many of this pass's answers are for speeches this run had not answered.

    `answered` is every `custom_id` the run has already dealt with: the speeches
    whose rows are on disk, and the speeches recorded in `failures.jsonl`. Both
    halves are needed, and neither is optional. A `--poll` reads every job the
    manifest records, not only the ones still outstanding, so a resumed run
    downloads answers already counted; without the failures a speech that came
    back unparseable would be counted again on every later pass, which is the
    smaller half of how the Gemini manifest reached 4,474 returns over 3,273
    requests.
    """
    return sum(1 for identifier in responses if identifier not in answered)


# --- The manifest ------------------------------------------------------------


def read_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(
    path: Path,
    previous: dict[str, object],
    *,
    meta: llm.RunMeta,
    referents_sha256: str,
    mode: str,
    limit: int | None,
    batch_ids: Sequence[str],
    planned_requests: int,
    planned_occurrences: int,
    requests: int,
    returned: int,
    complete: int,
    written: int,
    parse_failures: int,
    evidence_invalid: int,
    evidence_relocated: int,
    usage: dict[str, int],
) -> dict[str, object]:
    """One manifest per run, rewritten atomically after every pass.

    Counts that describe effort — requests sent, answers returned, tokens — add
    to what a previous pass recorded, because a resumed run did that work too.
    Counts that describe the artefact — occurrences written, speeches complete,
    parse failures still outstanding — are measured from the files on disk, so
    they cannot drift from what the run actually contains.

    `requests` is what this pass *sent*, counted by the caller at job creation
    or at the live call, and `returned` what it answered for the first time,
    from :func:`fresh_returns`. The old counters took both from the size of the
    pass's intention, before any of it happened; these two are the only numbers
    in the block a reader can hold the bill against.

    `passes` records one row per pass — when, in which mode, how much was sent,
    how much came back new and how much was a re-download — so the manifest says
    how a run was assembled and not only what it ended at. The Gemini run took
    six passes under a full batch quota, and nothing in its manifest said so.
    """
    before = previous.get("requests") if isinstance(previous.get("requests"), dict) else {}
    tokens = previous.get("usage") if isinstance(previous.get("usage"), dict) else {}
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    done = planned_requests > 0 and complete >= planned_requests
    history = [dict(entry) for entry in previous.get("passes") or [] if isinstance(entry, dict)]
    history.append(
        {"at": now, "mode": mode, "requests": int(requests), "returned": int(returned)}
    )
    manifest = {
        "run_id": meta.run_id,
        "term": meta.term,
        "model": meta.model,
        "reasoning_effort": meta.reasoning_effort,
        "prompt_version": meta.prompt_version,
        "prompt_sha256": meta.prompt_sha256,
        "referents_sha256": referents_sha256,
        "lexicon_version": meta.lexicon_version,
        "schema_version": llm.SCHEMA_VERSION,
        "mode": mode,
        "limit": limit,
        "created": previous.get("created", now),
        "completed": now if done else None,
        "git_commit": artifacts.git_commit(ROOT),
        "batch_ids": sorted({*(previous.get("batch_ids") or []), *batch_ids}),
        "requests": {
            "planned": planned_requests,
            "sent": int(before.get("sent", 0)) + int(requests),
            "returned": int(before.get("returned", 0)) + int(returned),
            "complete": complete,
        },
        "passes": history,
        "occurrences": {"planned": planned_occurrences, "written": written},
        "parse_failures": parse_failures,
        "evidence_invalid": evidence_invalid,
        "evidence_relocated": evidence_relocated,
        "usage": {key: int(tokens.get(key, 0)) + value for key, value in usage.items()},
        # Null, always, unless a price table is recorded beside the run. Tokens
        # are reported by both APIs; prices are not, and a number written here
        # from a pricing page would be a figure in a research manifest that
        # nothing in this repository produced. docs/VALIDATION.md §7 carries the
        # open check that owes it.
        "cost_usd": None,
        "status": "complete" if done else "in_progress",
    }
    artifacts.atomic_write_json(path, manifest, indent=1)
    return manifest


def refuse_mismatch(previous: dict[str, object], run_id: str, model: str, digest: str) -> None:
    """A run is one prompt and one model. A change to either is a new run id."""
    if previous.get("status") == "complete":
        console.fail(
            f"Run {run_id} is already complete",
            ["its manifest says so; publishing a second reading needs a new --run-id"],
        )
    if previous and str(previous.get("model")) != model:
        console.fail(
            f"Run {run_id} was started with model {previous.get('model')}",
            [f"--model {model} would mix two models in one file; use a new --run-id"],
        )
    if previous and str(previous.get("prompt_sha256")) != digest:
        console.fail(
            f"Run {run_id} was started with a different prompt",
            [
                f"manifest {str(previous.get('prompt_sha256'))[:12]}..., file {digest[:12]}...",
                "a changed prompt is a new prompt version and a new --run-id",
            ],
        )
