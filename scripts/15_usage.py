"""Aggregate one committed model run into the artefacts the usage view reads.

`14_llm_annotate.py` is the only step that spends money and the only one CI and
the deploy can never re-run. What it leaves behind — `model_annotations/genocide/
runs/<run_id>/` — is therefore a *committed input*, read here exactly as the
human annotations under `annotations/` are read by 03. This step is the opposite
of that one in every respect: deterministic, offline, free, and re-runnable by
anyone with the corpus and the repository.

It writes two artefacts into `data/derived/usage/`:

- `usage.json` — the aggregate. Who invoked the word about what, with what
  stance, when each delegation first reached each case, how much of the run was
  eligible to be counted at all, and how the model scored against the human gold
  sample.
- `occurrences.json` — one row per annotated occurrence, so a reader can get
  from a cell of the matrix to the passages behind it. The evidence *offsets*
  stay in the run's JSONL: the view highlights from the KWIC index it already
  loads, and republishing two coordinate systems for the same string is two
  chances to disagree.

**A second opinion, if one has been bought.** `comparison_run.txt` may name a
second run — a different model, the same prompt, the same occurrences — and this
step then publishes how far the two agree, per field and per occurrence. It is a
counter-instrument and never an authority: the comparison run is never merged
into anything, its labels never replace the published run's, and agreement
between two models is stability across instruments rather than accuracy. The
human gold sample remains the only calibration. Nothing is selected by default,
and the comparison block is written in its empty state when nothing is.

**Everything is refused rather than repaired.** A run made against a lexicon
that enumerated the term differently, a row naming an occurrence this corpus
does not have, a row whose `source_sha256` says the speech has changed
underneath it, a label the current referent list no longer holds, an occurrence
annotated twice — each stops the run. So does a prompt file whose bytes no
longer hash to what the run recorded, because `usage.json` publishes that prompt
verbatim and a reader is entitled to believe it is the one the model was given.
The single tolerated gap is coverage: a run that did not reach every occurrence
is aggregated under `--allow-partial` and reports honestly how much of the
corpus it covers. A comparison run has no such gate — it is read over the
occurrences both runs reached, and the artefact says how many those were — but it
is refused on everything else the published run is refused on, and on one more: a
comparison made with a different prompt, which would confound the instrument with
the questionnaire.

Usage:
    python scripts/15_usage.py                      # the run named in current_run.txt
    python scripts/15_usage.py --run 2026-09-05-luna-v1
    python scripts/15_usage.py --run-dir data/interim/synthetic_run [--allow-partial]
    python scripts/15_usage.py --comparison-run 2026-09-06-gemini-v1
    python scripts/15_usage.py --run-dir data/interim/synthetic_run \
        --comparison-run-dir data/interim/synthetic_run_comparison

Requires an x64 Python 3.12 — pyarrow publishes no 32-bit wheel.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import artifacts, audit, console, frames, lexicon, llm, usage
from lib import occurrences as occurrences_lib
from lib.paths import (
    INTERIM,
    LEXICON,
    MANIFESTS,
    MODEL_ANNOTATIONS,
    ROOT,
    SPEECHES_NORM,
    USAGE,
    ensure_dirs,
    rel,
    write_note,
)

TERM = "genocide"

#: docs/CORPUS.md §8, asserted by 13 and by 14 before a single API call. A run
#: whose rows were drawn from a different enumeration cannot be joined to the
#: published counts, so this is checked here too rather than assumed from the
#: fact that 14 checked it once.
DOCUMENTED_SPEECHES = 3_273
DOCUMENTED_OCCURRENCES = 6_092

STORE = MODEL_ANNOTATIONS / TERM
PROMPT = STORE / "PROMPT.md"
RUNS = STORE / "runs"
CURRENT_RUN = STORE / "current_run.txt"

#: The counter-instrument, named the same way and read the same way. Committed
#: empty, and empty is the ordinary state: a comparison run costs a second bill
#: and buys no authority, so nothing here selects one for you.
COMPARISON_RUN = STORE / "comparison_run.txt"

REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"
GOLD_ANNOTATIONS = ROOT / "annotations" / TERM / "annotations.csv"
GOLD_CANDIDATES = INTERIM / "genocide_gold_candidates.csv"

#: Columns this step needs. The normalised frame is 99 columns and 389 MB of
#: text; the eleven below are the enumeration's inputs plus the speaker
#: attributes every actor row is cut on.
COLUMNS = [
    "filename",
    "body_start",
    "text",
    "year",
    "date",
    "meeting_symbol",
    "country_org",
    "iso3",
    "speaker_group",
    "entity_type",
    "participanttype",
    "agenda_item_manual",
]

#: Speaker attributes carried onto every occurrence. `country_org` is the actor
#: identity; the rest describe it and are read modally or first-observed by
#: `lib.usage`, never re-derived per row.
SPEAKER_COLUMNS = ["country_org", "iso3", "entity_type", "speaker_group"]

#: Those, plus the one attribute of the *meeting* any block here counts on: the
#: date, which is the axis the diffusion block's first-events are ordered and
#: published on. Named separately because it describes the sitting rather than
#: the speaker, and a reader of `SPEAKER_COLUMNS` should not find a date in it.
OCCURRENCE_COLUMNS = [*SPEAKER_COLUMNS, "date"]

#: The model's fields, in the order `occurrences.json` writes them.
ROW_FIELDS = (
    "verdict",
    "quotation",
    "stance",
    "function",
    "referent",
    "proposed_referent",
    "confidence",
    "evidence_quote",
    "evidence_valid",
)


# --- Reading the inputs ------------------------------------------------------


def read_referents(path: Path) -> list[dict[str, str]]:
    """The controlled referent list with the columns the artefact publishes.

    A third reader of `referents.csv`, deliberately. `lib.audit.read_referents`
    returns the identifiers and is the authority on which ones an annotation may
    use; `lib.llm.read_referent_table` returns what the *prompt* renders, which
    does not include `iso3` because a model has no use for an ISO code. The usage
    view does: it puts a case on a map. Widening the prompt's dataclass to carry
    a field the prompt never shows would be the worse of the two duplications.
    """
    table = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing = sorted({"id", "label", "kind", "iso3", "years"} - set(table.columns))
    if missing:
        console.fail(f"{rel(path)} is missing columns: {', '.join(missing)}")
    return [
        {key: str(row[key]) for key in ("id", "label", "kind", "iso3", "years")}
        for row in table.to_dict(orient="records")
    ]


def uncommitted_run(run_dir: Path, flag: str) -> Path:
    """A run directory named by a path rather than by a committed run id.

    The escape hatch behind `--run-dir` and `--comparison-run-dir`, for a run
    that is not committed under `model_annotations/` — the synthetic fixtures
    `tools/synthetic_usage_run.py` builds are the only ones in the repository.
    """
    # Resolved, because the provenance block describes the run's files by their
    # path relative to the repository root and a bare `data/interim/...` typed at
    # a shell is relative to nothing the artefact can name.
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        console.fail(
            f"{flag} {rel(run_dir)} is not a directory",
            ["it must hold a manifest.json and an annotations.jsonl"],
        )
    if not run_dir.is_relative_to(ROOT):
        console.fail(
            f"{flag} {run_dir} is outside the repository",
            [
                "every artefact records the sha256 and the repository-relative path "
                "of each input it read, and a path outside the tree has no such name",
                "copy the run under data/interim/ and point at it there",
            ],
        )
    return run_dir


def select_run(run: str | None, run_dir: Path | None) -> tuple[Path, str]:
    """The run directory to aggregate, and the id it is published under.

    `--run-dir` names a directory rather than a run id, and the id is read back
    out of the manifest so the artefact still says which run it came from.
    """
    if run_dir is not None:
        return uncommitted_run(run_dir, "--run-dir"), ""

    selected = run or (
        CURRENT_RUN.read_text(encoding="utf-8").strip() if CURRENT_RUN.is_file() else ""
    )
    if not selected:
        console.fail(
            "no model run is selected, so there is nothing to aggregate",
            [
                f"{rel(CURRENT_RUN)} is empty and --run was not given",
                f"write a run id from {rel(RUNS)} into that file to publish it, "
                "or pass --run <run_id> to read one without publishing it",
                "runs are made by hand with 14_llm_annotate.py; CI and the deploy "
                "never make one",
            ],
        )
    directory = RUNS / selected
    if not directory.is_dir():
        console.fail(
            f"run '{selected}' has no directory under {rel(RUNS)}",
            [
                f"{rel(directory)} does not exist",
                "a run is a committed input; commit it before publishing it",
            ],
        )
    return directory, selected


def select_comparison(run: str | None, run_dir: Path | None) -> tuple[Path | None, str]:
    """The counter-instrument to read the published run against, if any.

    Selected the same three ways the published run is — a committed id in
    `comparison_run.txt`, `--comparison-run` to read one without committing the
    choice, `--comparison-run-dir` for a fixture that is not committed at all.
    The one difference is what an empty selection means: there, nothing to
    aggregate and a refusal; here, no second opinion, which is the ordinary state
    of this repository and not an error. The block is written empty and the step
    continues.
    """
    if run_dir is not None:
        return uncommitted_run(run_dir, "--comparison-run-dir"), ""
    selected = run or (
        COMPARISON_RUN.read_text(encoding="utf-8").strip()
        if COMPARISON_RUN.is_file()
        else ""
    )
    if not selected:
        return None, ""
    directory = RUNS / selected
    if not directory.is_dir():
        console.fail(
            f"comparison run '{selected}' has no directory under {rel(RUNS)}",
            [
                f"{rel(directory)} does not exist",
                f"a comparison run is a committed input like any other; empty "
                f"{rel(COMPARISON_RUN)} to publish without a second opinion",
            ],
        )
    return directory, selected


def read_run(directory: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    """The run's manifest and its rows, refusing an incomplete directory."""
    manifest_path = directory / "manifest.json"
    rows_path = directory / "annotations.jsonl"
    if not manifest_path.is_file():
        console.fail(
            f"{rel(manifest_path)} is missing",
            ["a run without its manifest cannot say which model or prompt produced it"],
        )
    if not rows_path.is_file():
        console.fail(
            f"{rel(rows_path)} is missing",
            ["the run directory holds no annotations to aggregate"],
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = llm.read_rows(rows_path)
    if not rows:
        console.fail(
            f"{rel(rows_path)} has no rows",
            ["an empty run is not a partial run; there is nothing to publish"],
        )
    return manifest, rows


def check_population(found: list[occurrences_lib.Occurrence]) -> list[str]:
    """Reasons the enumeration cannot be the documented one, if any."""
    problems = []
    if len(found) != DOCUMENTED_OCCURRENCES:
        problems.append(
            f"{len(found):,} occurrences against the {DOCUMENTED_OCCURRENCES:,} "
            "documented in docs/CORPUS.md §8"
        )
    speeches = len({occurrence.filename for occurrence in found})
    if speeches != DOCUMENTED_SPEECHES:
        problems.append(
            f"{speeches:,} speeches against the {DOCUMENTED_SPEECHES:,} "
            "documented in docs/CORPUS.md §8"
        )
    return problems


def enumerated_frame(
    speeches: pd.DataFrame, found: list[occurrences_lib.Occurrence]
) -> pd.DataFrame:
    """Every occurrence with the attributes its row will be counted under.

    In corpus order — speech order, then match order within a speech — which is
    the order `occurrences.json` is written in and the order the matrix's cells
    are ultimately cut from.
    """
    frame = occurrences_lib.frame(found)
    attributes = (
        speeches.loc[frame["index"].tolist(), OCCURRENCE_COLUMNS]
        .reset_index(drop=True)
        .astype("object")
    )
    return pd.concat([frame.reset_index(drop=True), attributes], axis=1)


# --- The refusals ------------------------------------------------------------


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
        console.fail(
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
        console.fail(
            f"some rows of {what} were written against an incompatible lexicon",
            [f"row lexicon versions: {', '.join(stale)}; {provenance}"],
        )


def refuse_stale_prompt(manifest: dict[str, object]) -> str:
    """`usage.json` publishes the prompt verbatim, so it must be the run's own.

    The digest is over the file's raw bytes, as `lib.llm.prompt_sha256` computes
    it, and the prompt's own header says an edit is a new version and a new run
    id. Publishing today's file beside yesterday's labels would misattribute
    every one of them.
    """
    if not PROMPT.is_file():
        console.fail(f"{rel(PROMPT)} is missing — the run's prompt cannot be published")
    digest = llm.prompt_sha256(PROMPT)
    recorded = str(manifest.get("prompt_sha256", ""))
    if digest != recorded:
        console.fail(
            f"{rel(PROMPT)} is not the prompt this run was made with",
            [
                f"the run records {recorded[:12] or '(none)'}..., "
                f"the file now hashes to {digest[:12]}...",
                "an edited prompt is a new prompt version and a new run id; restore the "
                "file or aggregate the run that matches it",
            ],
        )
    return PROMPT.read_text(encoding="utf-8")


def refuse_other_prompt(manifest: dict[str, object], digest: str) -> None:
    """A second opinion is a second model, not a second questionnaire.

    The comparison run must have been made from the same PROMPT.md bytes as the
    published one. If it was not, every disagreement between the two confounds
    the instrument with the questionnaire — the models were asked different
    questions — and no arithmetic downstream can say which difference produced
    which disagreement. There is nothing to repair here: the comparison is either
    of the same question or it is not a comparison.
    """
    recorded = str(manifest.get("prompt_sha256", ""))
    if recorded != digest:
        console.fail(
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
        console.fail(
            "the comparison run is the published run",
            [
                f"both point at {rel(published)}",
                "a run agrees with itself on every field of every occurrence, which is "
                "arithmetic rather than a finding",
                f"name a different run in {rel(COMPARISON_RUN)}, or empty it",
            ],
        )


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
    if problems := usage.row_problems(rows, digests):
        console.fail(
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
        console.fail(
            f"{what} holds rows the current codebook does not accept",
            [
                *invalid[:8],
                *([f"... and {len(invalid) - 8} more"] if len(invalid) > 8 else []),
                f"a referent removed from {rel(REFERENTS)} invalidates every row that "
                "used it; restore it, or re-annotate",
            ],
        )


def refuse_partial(annotated: int, total: int, allow: bool) -> None:
    """A gap is reported honestly or refused, never averaged over."""
    if annotated >= total:
        return
    missing = total - annotated
    if not allow:
        console.fail(
            f"the run annotates {annotated:,} of {total:,} occurrences",
            [
                f"{missing:,} occurrences are missing, so every count here would be a "
                "floor of unknown depth",
                "resume the run with 14_llm_annotate.py --poll, or pass --allow-partial "
                "to publish the coverage as it stands",
            ],
        )
    console.warn(
        f"--allow-partial: {annotated:,} of {total:,} occurrences annotated "
        f"({annotated / total:.1%}); the artefact records the gap"
    )


# --- The artefacts -----------------------------------------------------------


def model_block(
    manifest: dict[str, object],
    run_id: str,
    prompt_digest: str,
    rows: pd.DataFrame,
    total: int,
) -> dict[str, object]:
    """What produced these labels, and how much of the run is countable.

    Counts that describe the artefact — how many occurrences carry a row, how
    many abstained, how much evidence could not be located — are measured from
    the rows rather than copied from the manifest, so they cannot drift from
    what is actually published here. Counts that describe the *effort* — requests
    made, tokens spent, speeches that failed to parse — only the run knows, and
    they are read from its manifest.
    """
    stamp = str(manifest.get("completed") or manifest.get("created") or "")
    tokens = manifest.get("usage") if isinstance(manifest.get("usage"), dict) else {}
    requests = manifest.get("requests") if isinstance(manifest.get("requests"), dict) else {}
    verdict = rows["verdict"].astype(str)
    return {
        "id": str(manifest.get("model", "")),
        "run_id": run_id or str(manifest.get("run_id", "")),
        "run_date": stamp[:10],
        # A string, because it is an identifier rather than a quantity: nothing
        # here adds prompt versions up or compares them as numbers.
        "prompt_version": str(manifest.get("prompt_version", "")),
        "prompt_sha256": prompt_digest,
        "reasoning_effort": str(manifest.get("reasoning_effort", "")),
        # `sent`, and `submitted` only where a manifest predates the recount.
        # The old key counted intentions — the Gemini run recorded 7,966 over a
        # corpus of 3,273 — and the view prints this figure as "Requests", so
        # reading the old key first would publish the number the review found.
        # `tools/recount_run.py` writes `sent`; a run whose raw record is gone
        # keeps `submitted`, and `docs/VALIDATION.md` §7 says which are which.
        "requests": int(requests.get("sent", requests.get("submitted", 0)) or 0),
        "requests_recounted": "sent" in requests,
        "occurrences_total": int(total),
        "occurrences_annotated": len(rows),
        "parse_failures": int(manifest.get("parse_failures", 0) or 0),
        "evidence_invalid": int((~rows["evidence_valid"].map(bool)).sum()),
        "abstention": {
            "verdict_uncertain": int((verdict == "uncertain").sum()),
            "referent_unclear": int((rows["referent"].astype(str) == "unclear").sum()),
            "stance_unclear": int((rows["stance"].astype(str) == "unclear").sum()),
        },
        "tokens": {
            "input": int(tokens.get("input_tokens", 0) or 0),
            "output": int(tokens.get("output_tokens", 0) or 0),
        },
    }


def occurrence_rows(
    rows: pd.DataFrame,
    contested: dict[str, tuple[list[str], dict[str, str] | None]],
) -> list[dict[str, object]]:
    """One row per annotated occurrence, in corpus order.

    `id` is the KWIC line id, which is what joins these to
    `kwic/genocide.json` and to the reader view; `occurrence_id` is the SHA-256
    identity, which is what joins them to the gold sample and to any future run.
    Both are written because the two answer different questions and neither can
    be derived from the other.

    No evidence offsets. They exist, in the run's JSONL, and they are relative to
    the speech *body* while everything the reader view highlights is in whole-text
    coordinates; shipping a second coordinate system for the same string is a
    second chance to be wrong about it.

    `contested` and `alt` are the second opinion, per occurrence: the fields a
    comparison run labelled differently, and that run's own five labels where it
    did. Three different situations write the same empty `contested`, and that is
    deliberate — no comparison run, a comparison run that did not reach this
    occurrence, and a comparison run that agreed. Distinguishing them at the row
    level would put the state of the whole run into 6,092 rows; the `comparison`
    block in `usage.json` carries it once.
    """
    out: list[dict[str, object]] = []
    for row in rows.to_dict(orient="records"):
        entry: dict[str, object] = {
            "id": str(row["line_id"]),
            "occurrence_id": str(row["occurrence_id"]),
        }
        for field in ROW_FIELDS:
            value = row[field]
            entry[field] = bool(value) if field == "evidence_valid" else str(value)
        fields, alternative = contested.get(str(row["occurrence_id"]), ([], None))
        entry["contested"] = fields
        entry["alt"] = alternative
        out.append(entry)
    return out


def diffusion_block(rows: pd.DataFrame, referent_order: list[str]) -> dict[str, object]:
    """The dated first-events, under the referent block's own order.

    That order is read back off the block `usage.aggregate` has already built
    rather than recomputed from the referent table, so there is one answer to
    "which referent comes first" and the curves are ordered like everything else
    in the artefact.

    An undated assigned row is a refusal, as everything else in this step is:
    `lib.usage` raises, and the traceback is turned into the same kind of message
    every other refusal here produces.
    """
    try:
        return {
            "milestones": list(usage.MILESTONES),
            "referents": usage.diffusion_rows(rows, referent_order),
        }
    except ValueError as error:
        console.fail(
            "the run cannot be laid on a timeline",
            [
                str(error),
                "01_build_parquet.py refuses a speech with no date, so an undated row "
                "here means the join above lost one",
                "a first mention on an invented date is worse than no curve at all",
            ],
        )
        raise  # unreachable; console.fail exits, and a reader cannot know that


def build_note(
    payload: dict[str, object],
    counts: dict[str, int],
    jaccard: float | None,
    minimum: int,
    run_directory: Path,
    *,
    synthetic: bool = False,
) -> str:
    """The findings note: the funnel, the leaders, and what is withheld."""
    model = payload["model"]
    gold = payload["gold"]
    actors = payload["actors"]
    referents = [row for row in payload["referents"] if int(row["occurrences"]) > 0]
    stances = payload["stance_by_actor"]
    annotated = int(model["occurrences_annotated"])
    total = int(model["occurrences_total"])
    withheld = [row for row in actors if not row["sufficient"]]
    withheld_shares = [row for row in stances if not row["sufficient"]]

    def share(value: int, of: int) -> str:
        return f"{value / of:.1%}" if of else "—"

    def number(value: object, digits: int = 3) -> str:
        """A statistic, or an em dash where it is not defined."""
        return "—" if value is None else f"{float(value):.{digits}f}"

    def percent(value: object) -> str:
        return "withheld" if value is None else f"{float(value):.1%}"

    ranked = sorted(stances, key=lambda row: -int(row["eligible"]))
    denial = sorted(
        (row for row in stances if row["share_rejects"] is not None),
        key=lambda row: -float(row["share_rejects"]),
    )

    # The three referents carrying the most first-events, `other` excluded: it is
    # assigned and therefore carries events, but it is a bucket of unlike cases
    # and "the first delegation to mention other" is not a sentence about
    # anything. The reserved kind is the only one that can be excluded here —
    # `unclear` and `not_applicable` are never assigned and never appear.
    kinds = {str(row["id"]): str(row["kind"]) for row in payload["referents"]}
    curves = sorted(
        (
            entry
            for entry in payload["diffusion"]["referents"]
            if kinds.get(str(entry["id"])) != "reserved"
        ),
        key=lambda entry: (-len(entry["events"]), str(entry["id"])),
    )[:3]
    spread = []
    for entry in curves:
        mentions = [event for event in entry["events"] if event["milestone"] == "mention"]
        asserting = {
            event["actor"] for event in entry["events"] if event["milestone"] == "asserts"
        }
        rejecting = {
            event["actor"]
            for event in entry["events"]
            if event["milestone"] == "rejects_or_denies"
        }
        first = min(mentions, key=lambda event: (str(event["date"]), str(event["id"])))
        spread.append(
            f"| `{entry['id']}` | {first['actor']}, {first['date']} | "
            f"{len(mentions):,} | {len(asserting):,} | {len(rejecting):,} |"
        )

    by_name = {str(actor["country_org"]): actor for actor in actors}
    leaders = []
    for row in ranked[:15]:
        actor = by_name[str(row["actor"])]
        leaders.append(
            f"| {row['actor']} | {actor['group'] or '—'} | {actor['occurrences']:,} | "
            f"{row['eligible']:,} | {actor['assigned']:,} | "
            f"{percent(row['share_rejects'])} |"
        )

    comparison = payload["comparison"]
    compared = [
        f"| `{row['field']}` | {row['n']:,} | {number(row['observed'])} | "
        f"{number(row['kappa'])} | {row['contested']:,} |"
        for row in comparison["fields"]
    ]

    agreement = [
        f"| `{row['field']}` | {row['n']} | {number(row['observed'])} | "
        f"{number(row['kappa'])} |"
        for row in gold["human_agreement"]
    ]
    scored = [
        f"| `{row['field']}` | {row['n']} | {number(row['accuracy'])} | "
        f"{number(row['macro_f1'])} | {number(row['abstention_rate'])} |"
        for row in gold["model_vs_human"]
    ]

    return "\n".join(
        [
            "# 15 — Usage",
            "",
            *(
                [
                    "> **This note describes a fabricated run.** Its manifest declares "
                    "itself synthetic, and `tools/synthetic_usage_run.py` invented every "
                    "label in it from a hash of an occurrence identifier. The shapes are "
                    "real and the numbers are not. Do not cite anything below.",
                    "",
                ]
                if synthetic
                else []
            ),
            f"One model run over every occurrence of `{TERM}` in the corpus, aggregated "
            "into the two artefacts the usage view reads. Nothing here is a finding about "
            "genocide: every number is a count of what a model said one speaker was doing "
            "with one word in one passage, and the section on the gold sample below is the "
            "only thing that says how far those labels can be trusted.",
            "",
            "## The run",
            "",
            "| | |",
            "|---|---|",
            f"| Run | `{model['run_id']}` |",
            f"| Directory | `{rel(run_directory)}` |",
            f"| Model | `{model['id']}` |",
            f"| Reasoning effort | {model['reasoning_effort']} |",
            f"| Prompt | v{model['prompt_version']}, "
            f"`{str(model['prompt_sha256'])[:12]}` |",
            f"| Run date | {model['run_date'] or '—'} |",
            f"| Requests | {model['requests']:,} |",
            f"| Tokens | {model['tokens']['input']:,} in, "
            f"{model['tokens']['output']:,} out |",
            "",
            "## Coverage",
            "",
            f"**{annotated:,} of {total:,} occurrences** carry a label "
            f"({share(annotated, total)}). "
            + (
                "The run is complete."
                if annotated >= total
                else f"{total - annotated:,} are missing, so every count below is a floor. "
                f"{model['parse_failures']} speeches failed to parse and contribute nothing; "
                "they are recorded per run in the run's own `failures.jsonl`."
            ),
            "",
            "## From annotated to assigned",
            "",
            "Two gates, in this order. **Eligible** is the model's verdict `true_positive` "
            "*and* an evidence quotation that could be located around the match: a label "
            "attached to a quotation nobody can find in the speech is not evidence about the "
            "speech. **Assigned** is eligible *and* a referent that names something — "
            "everything except `unclear` and `not_applicable`. `other` counts as assigned, "
            "because the model has said the passage is about something the controlled list "
            "does not hold yet, and dropping it would understate how much of the corpus is "
            "about a case at all.",
            "",
            "| Step | Occurrences | Share of annotated |",
            "|---|---:|---:|",
            f"| Annotated | {counts['annotated']:,} | 100.0% |",
            f"| — verdict `false_positive` | {counts['false_positive']:,} | "
            f"{share(counts['false_positive'], annotated)} |",
            f"| — verdict `uncertain` | {counts['uncertain']:,} | "
            f"{share(counts['uncertain'], annotated)} |",
            f"| — evidence not located | {counts['evidence_invalid']:,} | "
            f"{share(counts['evidence_invalid'], annotated)} |",
            f"| **Eligible** | {counts['eligible']:,} | "
            f"{share(counts['eligible'], annotated)} |",
            f"| — referent `unclear` | {counts['referent_unclear']:,} | "
            f"{share(counts['referent_unclear'], annotated)} |",
            f"| **Assigned** | {counts['assigned']:,} | "
            f"{share(counts['assigned'], annotated)} |",
            "",
            "## Abstention",
            "",
            "The prompt tells the model that an honest abstention beats a guess, so these "
            "are a measurement of the run rather than a defect in it.",
            "",
            "| Field | Abstained | Share of annotated |",
            "|---|---:|---:|",
            f"| `verdict` = `uncertain` | {model['abstention']['verdict_uncertain']:,} | "
            f"{share(model['abstention']['verdict_uncertain'], annotated)} |",
            f"| `stance` = `unclear` | {model['abstention']['stance_unclear']:,} | "
            f"{share(model['abstention']['stance_unclear'], annotated)} |",
            f"| `referent` = `unclear` | {model['abstention']['referent_unclear']:,} | "
            f"{share(model['abstention']['referent_unclear'], annotated)} |",
            f"| evidence not located | {model['evidence_invalid']:,} | "
            f"{share(model['evidence_invalid'], annotated)} |",
            "",
            "## What the word is used about",
            "",
            f"{len(referents):,} of the {len(payload['referents']):,} controlled referents "
            "carry at least one assigned occurrence. `unclear` and `not_applicable` never "
            "can and always read zero; `other` can, and its count is how much of the corpus "
            "is about a case the controlled list does not hold yet.",
            "",
            "| Referent | Kind | Assigned |",
            "|---|---|---:|",
            *[
                f"| `{row['id']}` | {row['kind']} | {row['occurrences']:,} |"
                for row in referents[:15]
            ],
            "",
            "## Who uses it",
            "",
            f"{len(actors):,} speakers have at least one annotated occurrence. Ranked by "
            "eligible occurrences, which is the denominator the stance composition is cut "
            "from.",
            "",
            "| Speaker | Group | Occurrences | Eligible | Assigned | Rejects or denies |",
            "|---|---|---:|---:|---:|---:|",
            *leaders,
            "",
            "## Diffusion",
            "",
            "When each delegation first used the word about a case, and in which "
            "direction. A **mention** is a delegation's first assigned occurrence of "
            "that referent whatever stance it carried; the last two columns count the "
            "delegations whose first assertion, or first rejection, of the "
            "characterisation is on record. The same occurrence can be both a first "
            "mention and a first assertion, so the columns overlap and do not add up.",
            "",
            *(
                [
                    "| Referent | First mention | Delegations | Asserting | Rejecting |",
                    "|---|---|---:|---:|---:|",
                    *spread,
                    "",
                    "Firsts in this corpus and nowhere else. The date is the first "
                    "sitting at which that delegation is recorded using the word about "
                    "that case, which is not the day it took the position, and a "
                    "delegation absent from a curve is very often one that had no floor "
                    "to take.",
                ]
                if spread
                else [
                    "No referent outside the reserved identifiers carries a first event, "
                    "so there is no curve to describe.",
                ]
            ),
            "",
            "## What is withheld",
            "",
            f"**{minimum} occurrences.** A share of a speaker's occurrences is written only "
            f"when the speaker has at least {minimum} of them; below that `share_rejects` is "
            "`null` and `sufficient` is `false`, while every count is written at every "
            "denominator. A count is a fact and a share is an estimate — the same "
            "distinction `11_countries.py` draws, at a different threshold because the "
            "denominator is different: there it is a speaker's whole output and the question "
            "is whether a rare word appears in it at all; here the occurrences are already "
            "in hand and the question is only how they divide.",
            "",
            f"- {len(withheld_shares):,} of {len(stances):,} speakers carry no "
            "`share_rejects` (fewer than "
            f"{minimum} eligible occurrences).",
            f"- {len(withheld):,} of {len(actors):,} speakers are marked insufficient in the "
            f"matrix (fewer than {minimum} assigned occurrences).",
            f"- {len(denial):,} speakers carry a denial share at all"
            + (
                f"; the highest is {denial[0]['actor']} at "
                f"{float(denial[0]['share_rejects']):.1%} of "
                f"{denial[0]['eligible']:,} eligible occurrences."
                if denial
                else "."
            ),
            "",
            "## The gold sample",
            "",
            f"State: **{gold['state']}**. {gold['sample_size']:,} candidate rows over "
            f"{gold['unique_occurrences']:,} distinct occurrences drawn by "
            "`13_gold_sample.py`; "
            f"{gold['double_coded']:,} of them have been coded by both coders and "
            f"{gold['adjudicated']:,} adjudicated rows exist.",
            "",
            *(
                [
                    "### Between the two coders",
                    "",
                    "Observed agreement and Cohen's kappa over the occurrences both have "
                    "coded independently, adjudication ignored: this measures how far apart "
                    "the codebook leaves two readers. A kappa of `—` is a field on which "
                    "one category was used throughout, where the statistic is not defined.",
                    "",
                    "| Field | n | Observed | Kappa |",
                    "|---|---:|---:|---:|",
                    *agreement,
                    "",
                ]
                if agreement
                else [
                    "No occurrence has been coded by both coders yet, so there is no "
                    "inter-coder agreement to report and the model has nothing to be scored "
                    "against. Until then every figure above is the model's word alone.",
                    "",
                ]
            ),
            *(
                [
                    "### The model against the human reference",
                    "",
                    "The reference is the adjudicated label where one exists and the two "
                    "coders' agreed label otherwise; a field they disagree on with no "
                    "adjudication is left out rather than resolved by a rule.",
                    "",
                    "| Field | n | Accuracy | Macro-F1 | Model abstention |",
                    "|---|---:|---:|---:|---:|",
                    *scored,
                    "",
                    (
                        f"`function` is multi-label, so it carries no kappa and no macro-F1. "
                        f"Mean Jaccard overlap against the same reference: **{jaccard:.3f}**."
                        if jaccard is not None
                        else "`function` is multi-label and carries no kappa; its Jaccard "
                        "overlap could not be computed on this sample."
                    ),
                    "",
                ]
                if scored
                else []
            ),
            *(
                [
                    "## The second opinion",
                    "",
                    "A second model was given the same prompt and the same "
                    "occurrences. This is a counter-instrument and not a check: where "
                    "the two runs agree, what has been measured is that the label is "
                    "stable across instruments; where they differ, the artefact says so "
                    "occurrence by occurrence so that a reader can go and look. Nothing "
                    "above is affected — the comparison run is never merged into the "
                    "counts, and none of its labels replace the published run's.",
                    "",
                    "| | |",
                    "|---|---|",
                    f"| Run | `{comparison['run_id'] or '—'}` |",
                    f"| Model | `{comparison['model']}` |",
                    f"| Reasoning effort | {comparison['reasoning_effort'] or '—'} |",
                    f"| Run date | {comparison['run_date'] or '—'} |",
                    f"| Annotated | {comparison['occurrences_annotated']:,} of "
                    f"{total:,} "
                    f"({share(int(comparison['occurrences_annotated']), total)}) |",
                    f"| Compared | {comparison['overlap']:,} occurrences carry a label "
                    "from both runs |",
                    f"| Evidence not located | {comparison['evidence_invalid']:,} |",
                    "",
                    "Agreement is computed over that overlap, on raw labels and with no "
                    "eligibility gate: the verdict the gate is cut from is itself one of "
                    "the fields being compared, and an occurrence one model called a "
                    "true positive while the other refused the match is exactly the "
                    "disagreement worth reading.",
                    "",
                    "| Field | n | Observed | Kappa | Contested |",
                    "|---|---:|---:|---:|---:|",
                    *compared,
                    "",
                    (
                        "`function` is multi-label and carries no kappa. Mean Jaccard "
                        "overlap between the two runs: "
                        f"**{float(comparison['function_jaccard']):.3f}**, with "
                        f"{comparison['function_contested']:,} occurrences carrying a "
                        "different set of functions."
                        if comparison["function_jaccard"] is not None
                        else "`function` is multi-label and carries no kappa; its "
                        "overlap could not be computed on this pair of runs."
                    ),
                    "",
                    f"**{comparison['contested_any']:,} of "
                    f"{comparison['overlap']:,} compared occurrences** "
                    f"({share(int(comparison['contested_any']), int(comparison['overlap']))}) "
                    "are contested on at least one of the five fields. Each of them "
                    "carries the other run's five labels in `occurrences.json`, under "
                    "`alt`.",
                    "",
                ]
                if comparison["state"] == "computed"
                else []
            ),
            "## What this artefact may and may not be read as",
            "",
            "- **These are labels, not findings.** Every row records what a model said a "
            "speaker was doing with a word. The Council's own disagreements about whether "
            "an event was genocide are the object of study, and nothing here adjudicates "
            "them.",
            "- **Read the denominator.** `share_rejects` is a share of that speaker's own "
            "eligible occurrences, never of the Council's.",
            "- **A blank cell is not a zero.** The matrix is sparse; an absent "
            "(speaker, referent) pair had no assigned occurrence, and a withheld share is "
            "`null` rather than absent.",
            "- **A diffusion curve counts speakers, not states.** It rises when a "
            "delegation is recorded using the word about a case in this corpus, so only "
            "delegations that spoke can appear on it: absence is not refusal, and how "
            "many delegations are in a position to speak at all varies with Council "
            "membership and with which debates were opened to non-members.",
            "- **The gold sample is the only calibration.** Until it is coded, accuracy is "
            "unmeasured; after it is, it is measured on 200 occurrences and not on 6,092.",
            *(
                [
                    "- **A second opinion is not a second measurement.** The comparison "
                    "block says how far two models agree with each other. That is "
                    "stability across instruments — one questionnaire, answered twice — "
                    "and never accuracy: two models can be wrong about a passage in the "
                    "same way, and nothing in that block would notice. The gold sample "
                    "remains the only calibration.",
                ]
                if comparison["state"] == "computed"
                else []
            ),
            "",
        ]
    ) + "\n"


# --- Orchestration -----------------------------------------------------------


def run(args: argparse.Namespace) -> None:
    ensure_dirs()

    console.step("Choosing the run")
    directory, run_id = select_run(args.run, args.run_dir)
    manifest, raw_rows = read_run(directory)
    run_id = run_id or str(manifest.get("run_id", ""))
    console.info(f"{rel(directory)}: {len(raw_rows):,} rows, run '{run_id}'")
    console.info(f"model {manifest.get('model')}, status {manifest.get('status')}")
    if manifest.get("synthetic"):
        console.warn(
            "this run declares itself synthetic: every label in it was fabricated by "
            "tools/synthetic_usage_run.py. The artefacts are a shape, not a finding."
        )

    comparison_dir, comparison_id = select_comparison(
        args.comparison_run, args.comparison_run_dir
    )
    comparison_manifest: dict[str, object] = {}
    comparison_raw: list[dict[str, object]] = []
    if comparison_dir is None:
        console.info(
            f"no comparison run selected in {rel(COMPARISON_RUN)}; the second opinion "
            "block is written empty"
        )
    else:
        refuse_self_comparison(directory, comparison_dir)
        comparison_manifest, comparison_raw = read_run(comparison_dir)
        comparison_id = comparison_id or str(comparison_manifest.get("run_id", ""))
        console.info(
            f"comparison {rel(comparison_dir)}: {len(comparison_raw):,} rows, run "
            f"'{comparison_id}', model {comparison_manifest.get('model')}"
        )
        if comparison_manifest.get("synthetic"):
            console.warn(
                "the comparison run declares itself synthetic: every label in it was "
                "fabricated too, and so is every agreement figure below."
            )

    console.step("Reading the corpus and the lexicon")
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)
    lex = lexicon.load()
    if TERM not in lex.terms or not lex.terms[TERM].enabled:
        console.fail(f"'{TERM}' is not an active term in {rel(LEXICON)}")
    console.info(f"lexicon version {lex.version} ({lex.updated})")

    console.step("Enumerating the term")
    found = occurrences_lib.enumerate_term(speeches, bodies, lex.terms[TERM])
    if problems := check_population(found):
        console.fail("the enumeration disagrees with docs/CORPUS.md §8", problems)
    console.info(
        f"{len(found):,} occurrences in "
        f"{len({occurrence.filename for occurrence in found}):,} speeches"
    )
    enumerated = enumerated_frame(speeches, found)

    console.step("Checking the run against this corpus")
    refuse_stale_lexicon(manifest, raw_rows, lex)
    prompt_text = refuse_stale_prompt(manifest)
    referents = audit.read_referents(REFERENTS)
    refuse_bad_rows(raw_rows, enumerated, referents)
    refuse_partial(len(raw_rows), len(found), args.allow_partial)
    console.info(f"{len(referents)} controlled referents, every row validated against them")

    if comparison_raw:
        # Every identity check the published run passed, plus the one only a
        # comparison can fail. Coverage is the one thing not checked: a
        # comparison run is read over the occurrences both runs reached, so a
        # short one narrows the comparison rather than invalidating the counts.
        refuse_other_prompt(comparison_manifest, str(manifest.get("prompt_sha256", "")))
        refuse_stale_lexicon(
            comparison_manifest, comparison_raw, lex, what="the comparison run"
        )
        refuse_bad_rows(comparison_raw, enumerated, referents, what="the comparison run")
        if len(comparison_raw) < len(found):
            console.warn(
                f"the comparison run annotates {len(comparison_raw):,} of {len(found):,} "
                "occurrences; agreement is computed over the overlap and the artefact "
                "records how large it is"
            )

    console.step("Joining the run to the corpus")
    # The five dropped columns are the enumeration's own, written into every row
    # by 14 and already checked against it above. Keeping both copies would
    # suffix them and leave two answers to "where is this occurrence".
    labelled = pd.DataFrame(raw_rows)
    merged = enumerated.merge(
        labelled.drop(columns=["filename", "line_id", "start", "end", "source_sha256"]),
        on="occurrence_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    rows = merged.loc[merged["_merge"] == "both"].drop(columns="_merge").reset_index(drop=True)
    console.info(f"{len(rows):,} occurrences carry a label")

    console.step("Weighing the second opinion")
    contested = usage.contested_rows(rows, comparison_raw)
    comparison = usage.comparison_block(
        rows,
        comparison_raw,
        run_id=comparison_id,
        model=str(comparison_manifest.get("model", "")),
        run_date=str(
            comparison_manifest.get("completed") or comparison_manifest.get("created") or ""
        )[:10],
        reasoning_effort=str(comparison_manifest.get("reasoning_effort", "")),
        prompt_sha256=str(comparison_manifest.get("prompt_sha256", "")),
    )
    if comparison["state"] == "computed":
        console.info(
            f"{comparison['overlap']:,} occurrences carry a label from both runs, "
            f"{comparison['contested_any']:,} of them contested on at least one field"
        )
        for field in comparison["fields"]:
            observed = field["observed"]
            kappa = field["kappa"]
            console.info(
                f"  {field['field']:<10s} "
                f"observed {'—' if observed is None else format(observed, '.3f')}, "
                f"kappa {'—' if kappa is None else format(kappa, '.3f')}, "
                f"{field['contested']:,} contested"
            )
    else:
        console.info("no comparison run; the block is written in its 'none' state")

    console.step("Aggregating")
    referent_table = read_referents(REFERENTS)
    blocks = usage.aggregate(rows, referent_table, args.minimum)
    counts = usage.funnel(rows)
    diffusion = diffusion_block(rows, [str(row["id"]) for row in blocks["referents"]])
    events = sum(len(entry["events"]) for entry in diffusion["referents"])
    console.table(
        [
            ("annotated", f"{counts['annotated']:,}"),
            ("eligible", f"{counts['eligible']:,}"),
            ("assigned", f"{counts['assigned']:,}"),
            ("speakers", f"{len(blocks['actors']):,}"),
            ("matrix cells", f"{len(blocks['matrix']):,}"),
            (
                "first events",
                f"{events:,} over {len(diffusion['referents']):,} referents",
            ),
            (
                "shares withheld",
                f"{sum(1 for row in blocks['stance_by_actor'] if not row['sufficient']):,} "
                f"of {len(blocks['stance_by_actor']):,}",
            ),
            (
                "contested",
                f"{comparison['contested_any']:,} of {comparison['overlap']:,} compared"
                if comparison["state"] == "computed"
                else "no comparison run",
            ),
        ]
    )

    console.step("Reading the gold sample")
    if not GOLD_CANDIDATES.is_file():
        console.fail(
            f"{rel(GOLD_CANDIDATES)} is missing",
            ["run 13_gold_sample.py first; the gold block reports on a sample that exists"],
        )
    candidates = pd.read_csv(GOLD_CANDIDATES, dtype="string", keep_default_na=False)
    annotations = audit.read_annotations(GOLD_ANNOTATIONS)
    gold = usage.gold_block(
        annotations,
        rows,
        sample_size=len(candidates),
        unique_occurrences=int(candidates["occurrence_id"].nunique()),
        # The comparison run scored against the same human reference, by the same
        # computation. This is the one place either model can be said to be
        # accurate about anything; the `comparison` block scores them against each
        # other, which measures neither.
        comparison=pd.DataFrame(comparison_raw),
    )
    jaccard = usage.function_jaccard(annotations, rows)
    console.info(
        f"gold state '{gold['state']}': {gold['double_coded']:,} of "
        f"{gold['unique_occurrences']:,} occurrences double-coded, "
        f"{gold['adjudicated']:,} adjudicated"
    )

    console.step("Writing")
    meta = artifacts.provenance(
        ROOT,
        "15_usage.py",
        inputs=[
            SPEECHES_NORM,
            directory / "manifest.json",
            directory / "annotations.jsonl",
            # The comparison run is an input like any other: `provenance` skips a
            # path that does not exist, so the list is simply shorter when no
            # second opinion was read, and the block's own `state` says so.
            *([] if comparison_dir is None else [comparison_dir / "manifest.json"]),
            *([] if comparison_dir is None else [comparison_dir / "annotations.jsonl"]),
        ],
        configs=[LEXICON, REFERENTS, PROMPT, GOLD_ANNOTATIONS],
        extra={
            "lexicon_version": lex.version,
            "term": TERM,
            "run_id": run_id,
            "run_dir": rel(directory),
            "model": str(manifest.get("model", "")),
            "minimum_occurrences": args.minimum,
            "occurrences_total": len(found),
            "occurrences_annotated": len(rows),
            "allow_partial": bool(args.allow_partial),
        },
    )
    # Written in reading order rather than in the order the blocks were computed:
    # the two axes the matrix is indexed by come before the cells, and
    # `minimum_occurrences` sits between the actors and the shares it governs.
    # JSON objects are unordered and every consumer here reads by key, so this is
    # for whoever opens the file.
    payload = {
        "meta": meta,
        "model": model_block(manifest, run_id, llm.prompt_sha256(PROMPT), rows, len(found)),
        "prompt": prompt_text,
        "referents": blocks["referents"],
        "actors": blocks["actors"],
        "minimum_occurrences": args.minimum,
        "matrix": blocks["matrix"],
        "stance_by_actor": blocks["stance_by_actor"],
        "diffusion": diffusion,
        "comparison": comparison,
        "gold": gold,
    }

    with artifacts.atomic_directory(USAGE) as staged:
        artifacts.atomic_write_json(staged / "usage.json", payload)
        artifacts.atomic_write_json(
            staged / "occurrences.json",
            {"meta": meta, "occurrences": occurrence_rows(rows, contested)},
        )
        for name in ("usage.json", "occurrences.json"):
            size = (staged / name).stat().st_size / 1e3
            console.info(f"wrote {name}  ({size:,.0f} kB)")

    note = write_note(
        "15_usage.md",
        build_note(
            payload,
            counts,
            jaccard,
            args.minimum,
            directory,
            synthetic=bool(manifest.get("synthetic")),
        ),
    )
    console.info(f"wrote {note.name}")
    artifacts.atomic_write_json(
        MANIFESTS / "15_usage.json",
        artifacts.provenance(
            ROOT,
            "15_usage.py",
            inputs=[
                SPEECHES_NORM,
                directory / "annotations.jsonl",
                *([] if comparison_dir is None else [comparison_dir / "annotations.jsonl"]),
            ],
            configs=[LEXICON, REFERENTS, PROMPT, GOLD_ANNOTATIONS],
            extra={
                "run_id": run_id,
                "run_dir": rel(directory),
                "model": str(manifest.get("model", "")),
                "comparison_run_id": comparison_id,
                "comparison_run_dir": "" if comparison_dir is None else rel(comparison_dir),
                "comparison_state": comparison["state"],
                "comparison_overlap": comparison["overlap"],
                "comparison_contested": comparison["contested_any"],
                "lexicon_version": lex.version,
                "minimum_occurrences": args.minimum,
                "outputs": [
                    artifacts.describe_file(USAGE / "usage.json", ROOT),
                    artifacts.describe_file(USAGE / "occurrences.json", ROOT),
                ],
                "funnel": counts,
                "actors": len(blocks["actors"]),
                "matrix_cells": len(blocks["matrix"]),
                "diffusion_events": events,
                "gold_state": gold["state"],
            },
        ),
        indent=1,
    )
    console.info(f"payload in {rel(USAGE)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--run",
        help=f"run id under {rel(RUNS)}; defaults to the one named in current_run.txt",
    )
    selection.add_argument(
        "--run-dir",
        type=Path,
        help="read a run directory anywhere, for a fixture that is not committed",
    )
    # A second group, because the two selections are independent: a comparison
    # may be named against any published run, including one given by --run-dir.
    second = parser.add_mutually_exclusive_group()
    second.add_argument(
        "--comparison-run",
        help=f"run id under {rel(RUNS)} to read the published run against; defaults "
        "to the one named in comparison_run.txt, which is empty",
    )
    second.add_argument(
        "--comparison-run-dir",
        type=Path,
        help="read a comparison run directory anywhere, for a fixture that is not "
        "committed",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="aggregate a run that has not reached every occurrence, and record the gap",
    )
    parser.add_argument(
        "--minimum",
        type=int,
        default=usage.MINIMUM_OCCURRENCES,
        help="occurrences a speaker needs before a share of them is published",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
