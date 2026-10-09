"""The refusals a committed run must pass before step 15 aggregates it.

`15_usage.py` refuses rather than repairs. A run made against a lexicon that
enumerated the term differently, a row naming an occurrence this corpus does not
have or a body that has moved since, a label the codebook no longer accepts, a
referent the run's own list could not have offered, a prompt this checkout does
not hold, a comparison made with another prompt or against the run itself, a
coverage gap nobody allowed: each stops the step, and each is decided here. So
are the three resolutions that let an older run be *read* rather than refused —
a superseded referent onto its successor, a schema-2 row onto schema 3, a
revised prompt onto the archived wording the run was made with.

They live in `lib` so that each rule can be tested on a constructed manifest;
the step reads a run that needed a serving GPU and a corpus CI does not have,
and cannot be. Every refusal raises :class:`lib.console.Refusal` carrying the
message the step has always printed, which the step's `console.main` prints
before it exits, and takes `what`, so that a comparison run is named as one. The
check over a run's rows that returns its problems instead of refusing,
:func:`row_problems`, is here too, beside the refusal that reports them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd

from . import audit, console, lexicon, llm, model_runs, prompts
from .agreement import _text
from .paths import LEXICON, rel

#: The one term the model-assisted layer covers, and the store files the
#: refusals name; all of them are `lib.model_runs`'s.
TERM = model_runs.TERM
PROMPT = model_runs.PROMPT
REFERENTS = model_runs.REFERENTS
COMPARISON_RUN = model_runs.COMPARISON_RUN


def refuse_stale_lexicon(
    manifest: dict[str, object],
    rows: list[dict],
    lex: lexicon.Lexicon,
    *,
    what: str = "the run",
) -> None:
    """A run is coded against one lexicon version; the counts are cut on another.

    The lexicon defines what an occurrence *is*, so a run made against a lexicon
    that enumerated `TERM` differently is annotating a population this corpus no
    longer has. What decides that is the term's own pattern, not the lexicon's
    version number: `pattern_since` records the release in which that pattern
    last moved, so a bump that edited other terms leaves this run's occurrences
    exactly where they were and the run stands. Editing `TERM`'s pattern bumps
    its `pattern_since` and the run is refused, as it must be. The row-level
    check is not redundant: the manifest is written once at the end of a run and
    the rows are appended as they arrive.

    `what` names the run in the message. A comparison run is held to every
    identity check the published one is, and a reader told "the run" when two
    were read would have to guess which of them moved.
    """
    since = lex.terms[TERM].pattern_since
    provenance = (
        f"{rel(LEXICON)} is now version {lex.version} and '{TERM}' has carried its "
        f"current pattern since version {since}"
    )
    recorded = str(manifest.get("lexicon_version", ""))
    if not lex.compatible(TERM, recorded):
        raise console.Refusal(
            f"{what} was made against an incompatible lexicon",
            [
                f"it records version {recorded or '(none)'}; {provenance}",
                "re-run 03_lexicon.py and 14_llm_annotate.py, or aggregate the run "
                "that matches this lexicon",
            ],
        )
    # A run holds hundreds of thousands of rows and a handful of distinct
    # versions; the question is about the version, so ask it once per version.
    recorded_rows = {str(row.get("lexicon_version", "")) for row in rows}
    stale = sorted(version for version in recorded_rows if not lex.compatible(TERM, version))
    if stale:
        raise console.Refusal(
            f"some rows of {what} were written against an incompatible lexicon",
            [f"row lexicon versions: {', '.join(stale)}; {provenance}"],
        )


def refuse_stale_referents(
    manifest: dict[str, object],
    rows: list[dict[str, object]],
    referents: audit.ReferentList,
    *,
    what: str = "the run",
) -> int:
    """A run is coded against one referent list; the list has moved since.

    The lexicon's rule, transposed. What decides compatibility is not the list's
    version number but the identifier's own `since` and `retired_in`, so a
    version bump that added twelve categories leaves a run that used none of them
    exactly where it was. Two ways a run can fail: it used an identifier that did
    not yet mean what it means now, or one that had already been retired and was
    therefore never rendered into its prompt. Either says the manifest and the
    rows disagree about which list was in front of the model, which is a
    provenance failure rather than a counting one.

    Renaming a case would otherwise orphan the rows that used the old name —
    3,934 of the two committed runs' 12,184 — so a retired identifier keeps its
    row in the file and names its successor, and this returns how many rows of
    the run carry one. Resolving them is a translation and not a repair, which
    is the distinction that lets it stand in a script that refuses everything
    else: the mapping is a column of a human-owned file, so the reader looks it
    up rather than inferring it, and every superseded identifier has exactly one
    answer. An identifier retired without a successor resolves to itself and is
    published under its own name.

    Returns the number of rows carrying a superseded identifier, so the caller
    can say so rather than translating silently.
    """
    recorded = str(manifest.get("referents_version", ""))
    provenance = (
        f"{rel(REFERENTS)} is now version {referents.version}; a run that records no "
        "version was made against version 1"
    )
    if recorded.strip() and int(recorded) > referents.version:
        raise console.Refusal(
            f"{what} was made against a newer referent list than this checkout holds",
            [
                f"it records version {recorded}; {provenance}",
                "check out the commit whose referent list matches the run, or aggregate "
                "a run this list can read",
            ],
        )
    # Hundreds of thousands of rows carry a handful of distinct (version,
    # identifier) pairs; the question is about the pair, so ask it once each.
    pairs = {
        (str(row.get("referents_version", "") or recorded), str(row.get("referent", "")))
        for row in rows
    }
    stale = sorted(
        f"{name} (run version {version or '1'}, "
        f"introduced at {referents.since.get(name, '?')}"
        + (
            f", retired at {referents.retired_in[name]}"
            if name in referents.retired_in
            else ""
        )
        + ")"
        for version, name in pairs
        if not referents.compatible(name, version)
    )
    if stale:
        raise console.Refusal(
            f"{what} used referents the list it records could not have offered",
            [
                *stale[:8],
                *([f"... and {len(stale) - 8} more"] if len(stale) > 8 else []),
                provenance,
                "a referent is offered to a run only between its `since` and its "
                "`retired_in`; re-annotate, or aggregate the run that matches this list",
            ],
        )
    return sum(
        1
        for row in rows
        if referents.resolve(str(row.get("referent", ""))) != row.get("referent")
    )


def resolve_schema(
    manifest: dict[str, object],
    rows: list[dict[str, object]],
    *,
    what: str = "the run",
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Read a run at its own annotation schema, in the current vocabulary.

    The referent list's rule, applied to the fields themselves. Schema 3 split
    `stance` into `speaker_position` and `concrete_case` and added six fields;
    the four committed runs are 12,366 rows coded against schema 2, and refusing
    them would mean the schema could never move without buying every run again.
    So a schema-2 row is *translated* — `lib.llm.resolve_row` — and the artefact
    says what the translation could not answer.

    Two numbers come back with the rows, and both are published rather than
    smoothed over:

    - `unanswered`, the count of rows carrying none of the six fields schema 3
      adds. For a v1 run it is every row, which is the honest statement of what
      such a run cannot say and the reason the pilot exists.
    - `split_decision`, the count of rows whose recorded `stance` and recorded
      `referent` disagree about whether a case is in view — an assertion filed
      under `genocide_in_general`, or a neutral legal reference filed under a
      named case. That is the review's §4.2 item 1 measured rather than argued:
      800 rows of the Luna run and 535 of the Gemini one took the
      abstract-or-concrete decision twice and differently, and schema 3's lock
      between `concrete_case` and `no_position` is what stops a third.
    """
    recorded = str(manifest.get("schema_version", "") or llm.SCHEMA_VERSION)
    if recorded not in (llm.SCHEMA_VERSION, "3", audit.LEGACY_SCHEMA_VERSION):
        raise console.Refusal(
            f"{what} records an annotation schema this checkout cannot read",
            [
                f"it says version {recorded}; this checkout reads "
                f"{audit.LEGACY_SCHEMA_VERSION} and {llm.SCHEMA_VERSION}",
                "check out the commit whose codebook matches the run",
            ],
        )
    resolved = [llm.resolve_row(row) for row in rows]
    counts = {
        "unanswered": sum(
            1
            for row in resolved
            if not any(str(row.get(field, "")).strip() for field in llm.UNANSWERED_BY_V1)
        ),
        "split_decision": sum(
            1
            for row in resolved
            if (str(row.get("concrete_case")) == "no")
            != (str(row.get("speaker_position")) == "no_position")
        ),
    }
    return resolved, counts


def resolve_referents(
    rows: list[dict[str, object]], referents: audit.ReferentList
) -> list[dict[str, object]]:
    """Rewrite each row's referent to whatever that identifier is called now.

    So that a v1 run and a v2 run can be read side by side: the second-opinion
    comparison counts agreement on the `referent` string, and `rwanda_1994`
    against `rwanda` is a rename rather than a disagreement. The run's own
    version stays in the artefact's provenance block, and the file's
    `superseded_by` column says what was translated into what, so nothing is
    lost that a reader would need to undo it.
    """
    return [{**row, "referent": referents.resolve(str(row.get("referent", "")))} for row in rows]


def resolve_prompt(
    manifest: dict[str, object], *, what: str = "the run"
) -> prompts.PromptPack:
    """The prompt this run was actually made with, found by its digest.

    `usage.json` publishes the prompt verbatim beside the labels it produced, so
    it has to be the run's own; the digest recorded on the manifest and on every
    row is the only handle the run has on it. Until the archive existed there
    was one file that digest could be compared against, and the comparison was
    an equality: any edit to `PROMPT.md` made both committed runs
    un-aggregatable and took `/usage` down with them. That price was refused
    twice in one afternoon, for `genocidaires` and for the referent identifiers,
    and refusing it a third time would have meant never improving the
    instrument.

    So the question changes from "is this today's prompt?" to "is this a prompt
    this repository still holds?" — the same move `referents.csv` makes for its
    own list, and for the same reason. :func:`lib.prompts.load_prompt_library`
    reads `PROMPT.md` and every superseded version under `prompts/`, and a run
    resolves to whichever of them its bytes hash to. Only a digest that appears
    nowhere is refused, and then loudly: a run whose wording this checkout does
    not hold cannot be published, because the alternative is publishing some
    other wording under its labels.

    The recorded `prompt_version` is checked against the resolved file's own
    header rather than used to find it. The digest is what was measured; the
    version line is a human's claim about it, and the only useful thing to do
    with a claim is to test it.
    """
    if not PROMPT.is_file():
        raise console.Refusal(f"{rel(PROMPT)} is missing — the run's prompt cannot be published")
    try:
        library = prompts.load_prompt_library(PROMPT)
    except (ValueError, FileNotFoundError) as exc:
        raise console.Refusal(
            f"the prompt archive beside {rel(PROMPT)} cannot be read", [str(exc)]
        ) from exc
    recorded = str(manifest.get("prompt_sha256", ""))
    pack = library.by_digest(recorded)
    if pack is None:
        raise console.Refusal(
            f"{what} was made with a prompt this checkout does not hold",
            [
                f"it records {recorded[:12] or '(none)'}...",
                *(f"this checkout holds {line}" for line in library.describe()),
                f"a revised prompt keeps its old text as {prompts.ARCHIVE}/v<n>.md, so an "
                "earlier run stays readable; restore that file, or aggregate a run whose "
                "prompt is here",
            ],
        )
    declared = str(manifest.get("prompt_version", "")).strip()
    if declared and declared != str(pack.version):
        raise console.Refusal(
            f"{what} records a prompt version its own bytes contradict",
            [
                f"the manifest says v{declared}; {pack.name} hashes to "
                f"{pack.sha256[:12]}... and declares v{pack.version}",
                "the digest is what was measured and the version line is a claim about "
                "it; one of the two was edited after the run",
            ],
        )
    return pack


def refuse_other_prompt(manifest: dict[str, object], digest: str) -> None:
    """A second opinion is a second model, not a second questionnaire.

    The comparison run must have been made from the same prompt bytes as the
    published one. If it was not, every disagreement between the two confounds
    the instrument with the questionnaire — the models were asked different
    questions — and no arithmetic downstream can say which difference produced
    which disagreement. There is nothing to repair here: the comparison is either
    of the same question or it is not a comparison.

    The archive does not loosen this. It lets a v1 run and a v2 run each be
    published, one aggregation at a time, under the wording each was made with;
    it does not let one be laid over the other and the difference called an
    instrument effect. So this compares against the digest
    :func:`resolve_prompt` returned for the published run, which is that run's
    own and not the file's.
    """
    recorded = str(manifest.get("prompt_sha256", ""))
    if recorded != digest:
        raise console.Refusal(
            "the comparison run was made with a different prompt",
            [
                f"the comparison run records {recorded[:12] or '(none)'}..., "
                f"the published run was made with {digest[:12]}...",
                "agreement across two prompts measures the questionnaire and the model "
                "at once and cannot separate them",
                "annotate the comparison run against this prompt, or select a comparison "
                "run that was",
            ],
        )


def refuse_self_comparison(published: Path, comparison: Path) -> None:
    """A run compared against itself agrees everywhere and measures nothing."""
    if published.resolve() == comparison.resolve():
        raise console.Refusal(
            "the comparison run is the published run",
            [
                f"both point at {rel(published)}",
                "a run agrees with itself on every field of every occurrence, which is "
                "arithmetic rather than a finding",
                f"name a different run in {rel(COMPARISON_RUN)}, or empty it",
            ],
        )


def row_problems(
    rows: Sequence[Mapping[str, object]], enumerated: Mapping[str, str]
) -> list[str]:
    """Every reason a run's rows cannot be joined to this enumeration.

    `enumerated` maps occurrence_id to the digest of the speech body it was found
    in. Three failures:

    - a row naming an occurrence the enumeration does not have;
    - a row whose `source_sha256` differs from the enumerated one, so the same
      span in the same file is now in a different text;
    - the same occurrence annotated twice, which would double-count it.

    The first two mean the corpus or the lexicon moved underneath a run that has
    already been paid for. The third means the run file was appended to twice,
    which `lib.model_runs.completed` is meant to prevent and which cannot be
    repaired here: the two rows may carry different labels, and there is no rule
    for choosing between them that is not a coin toss.

    Returned rather than raised, so the caller can report all of them at once
    instead of one per run.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        identifier = _text(row.get("occurrence_id"))
        if identifier not in enumerated:
            problems.append(
                f"{identifier[:12] or '(blank)'}... names an occurrence this enumeration "
                "does not have"
            )
            continue
        digest = _text(row.get("source_sha256"))
        if digest != enumerated[identifier]:
            problems.append(
                f"{identifier[:12]}... was annotated against body {digest[:12]}..., "
                f"the corpus now holds {enumerated[identifier][:12]}..."
            )
        if identifier in seen:
            problems.append(f"{identifier[:12]}... is annotated more than once")
        seen.add(identifier)
    return problems


def refuse_bad_rows(
    rows: list[dict[str, object]],
    frame: pd.DataFrame,
    referents: set[str],
    *,
    what: str = "the run",
) -> None:
    """Identity, then labels. Both are refusals, never repairs."""
    digests = dict(
        zip(frame["occurrence_id"].astype(str), frame["source_sha256"].astype(str), strict=True)
    )
    if problems := row_problems(rows, digests):
        raise console.Refusal(
            f"{what}'s rows cannot be joined to this corpus",
            [
                *problems[:8],
                *([f"... and {len(problems) - 8} more"] if len(problems) > 8 else []),
                "a run must name each of this enumeration's occurrences at most once, "
                "against the body digest it was annotated from",
                "if the corpus or the lexicon moved, re-run 02 and 03 and re-annotate; "
                "if the run file was appended to twice, the run is not resumable",
            ],
        )

    invalid: list[str] = []
    for row in rows:
        try:
            llm.validate_row(row, referents, appending=False)
        except (ValueError, KeyError) as error:
            invalid.append(f"{str(row.get('occurrence_id', ''))[:12]}...: {error}")
    if invalid:
        raise console.Refusal(
            f"{what} holds rows the current codebook does not accept",
            [
                *invalid[:8],
                *([f"... and {len(invalid) - 8} more"] if len(invalid) > 8 else []),
                f"a referent removed from {rel(REFERENTS)} invalidates every row that "
                "used it; restore it, or re-annotate",
            ],
        )


def validated(
    manifest: dict[str, object],
    rows: list[dict[str, object]],
    *,
    lex: lexicon.Lexicon,
    enumerated: pd.DataFrame,
    referent_list: audit.ReferentList,
    what: str = "the run",
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    """Every identity check a run must pass, then its rows in today's vocabulary.

    One function for the published run and the comparison run, which used to
    repeat the same five calls. The lexicon it was enumerated against, the
    occurrence identities and body digests, the codebook, and the referent list
    version, in that order; then superseded referents resolved onto their
    successors and schema-2 rows onto schema 3. Returns the rows, the schema
    counts and how many rows carried a superseded referent.

    Existence is checked against every identifier the referent file holds,
    retired ones included: a run that used a referent the list has since
    withdrawn is not a broken run, it is an older one, and the version check is
    what says whether it was entitled to use it.
    """
    refuse_stale_lexicon(manifest, rows, lex, what=what)
    refuse_bad_rows(rows, enumerated, referent_list.all, what=what)
    superseded = refuse_stale_referents(manifest, rows, referent_list, what=what)
    rows = resolve_referents(rows, referent_list)
    rows, schema_counts = resolve_schema(manifest, rows, what=what)
    return rows, schema_counts, superseded


def refuse_partial(annotated: int, total: int, allowed_by: str, *, run_id: str = "") -> None:
    """A gap is reported honestly or refused, never averaged over.

    `allowed_by` says what allows a gap — `--allow-partial`, or
    `model_runs.ALLOW_PARTIAL_RUN` naming the run — and is empty when nothing
    does.
    """
    if annotated >= total:
        return
    missing = total - annotated
    if not allowed_by:
        raise console.Refusal(
            f"the run annotates {annotated:,} of {total:,} occurrences",
            [
                f"{missing:,} occurrences are missing, so every count here would be a "
                "floor of unknown depth",
                f"resume it with 14_llm_annotate.py --run-id {run_id or '<run id>'} and the "
                "model and sampling settings it was started with (on the cluster, resubmit "
                "the identical submit_annotate.sh command); completed speeches are skipped",
                f"or name it in {rel(model_runs.ALLOW_PARTIAL_RUN)}, or pass --allow-partial, "
                "to publish the coverage as it stands",
            ],
        )
    console.warn(
        f"{allowed_by}: {annotated:,} of {total:,} occurrences annotated "
        f"({annotated / total:.1%}); the artefact records the gap"
    )
