"""Aggregate one committed model run into the artefacts the usage view reads.

`14_llm_annotate.py` is the only step that reserves a model-serving GPU and the only one CI and
the deploy can never re-run. What it leaves behind — `model_annotations/genocide/
runs/<run_id>/` — is therefore a *committed input*, read here exactly as the
human annotations under `annotations/` are read by 03. This step is the opposite
of that one in every respect: deterministic, offline, free, and re-runnable by
anyone with the corpus and the repository.

It writes two artefacts into `data/derived/usage/`:

- `usage.json` — the aggregate. Who invoked the word about what, with what
  position, when each delegation first reached each case, how much of the run was
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
annotated twice — each stops the run. So does a run whose recorded prompt digest
matches neither `PROMPT.md` nor any superseded wording under `prompts/`, because
`usage.json` publishes that prompt verbatim and a reader is entitled to believe
it is the one the model was given. Revising the prompt is therefore not a
break: the old text moves into `prompts/v<n>.md`, the runs made with it go on
resolving to it, and only a wording this repository no longer holds is refused.
The single tolerated gap is coverage: a run that did not reach every occurrence
is aggregated when `allow_partial_run.txt` names it, or under `--allow-partial`,
and reports honestly how much of the corpus it covers. A comparison run has no such gate — it is read over the
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
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    artifacts,
    audit,
    console,
    frames,
    gold_estimates,
    lexicon,
    llm,
    model_runs,
    prompts,
    usage,
    usage_comparison,
    usage_refusals,
)
from lib import occurrences as occurrences_lib
from lib import referents as referents_lib
from lib.paths import (
    INTERIM,
    LEXICON,
    MANIFESTS,
    ROOT,
    SPEECHES_NORM,
    USAGE,
    ensure_dirs,
    rel,
    write_note,
)

# The refusals a run must pass, and the resolutions that read an older run in
# today's vocabulary, live in `lib.usage_refusals`; the counting, and the model
# block that describes a run, in `lib.usage`; the gold block in
# `lib.gold_estimates` and the second opinion in `lib.usage_comparison`. All are
# tested there on constructed manifests and rows, which this step cannot be.

TERM = model_runs.TERM

STORE = model_runs.STORE
PROMPT = model_runs.PROMPT
RUNS = model_runs.RUNS
CURRENT_RUN = model_runs.CURRENT_RUN

#: The counter-instrument, named the same way and read the same way. Empty is
#: an ordinary state: a comparison run costs a second cluster run and buys no
#: authority, so nothing here selects one for you.
COMPARISON_RUN = model_runs.COMPARISON_RUN

REFERENTS = model_runs.REFERENTS
GOLD_ANNOTATIONS = model_runs.GOLD_ANNOTATIONS
GOLD_CANDIDATES = model_runs.GOLD_CANDIDATES
GOLD_DESIGN = model_runs.GOLD_DESIGN
#: The passages read against a model's labels before coding, and the column 13
#: marks them with in the candidate file this step reads.
PRIOR_REVIEW = model_runs.PRIOR_REVIEW
PRIOR_REVIEW_FLAG = model_runs.PRIOR_REVIEW_FLAG


def reviewed_before_coding(candidates: pd.DataFrame) -> set[str]:
    """The sampled occurrences 13 marked as read against a model's labels.

    Read off the candidate file rather than off the committed list, so the
    occurrences set aside are exactly the ones the sample this step reports on
    carries the mark for. The file is read as text, where pandas wrote the
    boolean as `True`.
    """
    if PRIOR_REVIEW_FLAG not in candidates:
        console.fail(
            f"{rel(GOLD_CANDIDATES)} has no `{PRIOR_REVIEW_FLAG}` column",
            ["re-run 13_gold_sample.py; it marks the passages read before coding"],
        )
    marked = candidates[PRIOR_REVIEW_FLAG].astype(str) == "True"
    return set(candidates.loc[marked, "occurrence_id"].astype(str))

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
#:
#: The six after `referent_source` are annotation schema 3's, and a row from a
#: run coded against schema 2 carries them as empty strings — `lib.llm.resolve_row`
#: does not guess them, and the view renders a field it finds empty as absent
#: rather than as an answer. That is what "a v1 run keeps working" looks like at
#: the row level: everything schema 2 measured is here, and everything it did
#: not is visibly not here.
ROW_FIELDS = (
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
    "rationale",
    "evidence_quote",
    "evidence_valid",
)


# --- Reading the inputs ------------------------------------------------------


def read_referents(path: Path) -> tuple[audit.ReferentList, list[dict[str, object]]]:
    """The controlled referent list, as the run is checked against it and as published.

    Parsed once by `lib.referents`, which holds every reader of the file to the
    same rules. The first view is the versions a run must be compatible with;
    the second is every row with the columns the artefact publishes, `iso3`
    included because the usage view puts a case on a map. Retired referents are
    published too, and marked, so a run made before a retirement still has a
    row for each identifier it counted under.

    A cell that breaks a rule stops the step with the rule, the row and the
    file named, rather than with a traceback.
    """
    try:
        parsed = referents_lib.read(path)
        return parsed.listing(), parsed.published()
    except referents_lib.ReferentFileError as error:
        console.fail(str(error))


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
    return model_runs.read(directory)


def check_population(
    found: list[occurrences_lib.Occurrence], expected: tuple[int, int] | None = None
) -> list[str]:
    """Reasons the enumeration cannot be the committed one, if any.

    Asserted here as 13 and 14 assert it: a run whose rows were drawn from a
    different enumeration cannot be joined to the published counts.
    """
    return model_runs.population_problems(
        (occurrence.filename for occurrence in found), len(found), expected
    )


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


# --- The artefacts -----------------------------------------------------------


def retest_block(
    pairs: Sequence[tuple[str, dict[str, object], list[dict[str, object]]]],
) -> list[dict[str, object]]:
    """The same model, the same prompt, asked twice: the noise floor of each run.

    Two models disagreeing on a fifth of the position labels means nothing until a
    reader knows how far *one* model disagrees with itself. The review of
    1 September 2026 (§4.6) asks for the retest figures beside the cross-model
    ones for exactly that reason, and both runs have a sibling that supplies
    them: the 50-speech pilots of 30 and 31 August, sent the byte-identical
    prompt to the byte-identical model, and never merged into anything.

    A retest is discovered rather than named: any other committed run of the
    same model and the same prompt hash is one, and the largest overlap wins.
    That is the whole definition — a run of the same instrument answering the
    same questionnaire — and hard-coding two run ids would leave the block
    stale the first time a third run is bought.

    The statistics are the ones :func:`usage_comparison.comparison_fields` computes between
    two *different* models, deliberately, so a reader can lay one table over the
    other and read the difference. Nothing here is an accuracy either: a model
    that agrees with itself perfectly may be perfectly wrong.
    """
    out: list[dict[str, object]] = []
    for label, manifest, rows in pairs:
        model = str(manifest.get("model", ""))
        digest = str(manifest.get("prompt_sha256", ""))
        run_id = str(manifest.get("run_id", ""))
        if not rows or not model:
            continue
        best: tuple[int, str, list[dict[str, object]]] | None = None
        for candidate in sorted(RUNS.glob("*/manifest.json")):
            sibling = json.loads(candidate.read_text(encoding="utf-8"))
            if str(sibling.get("model")) != model or str(sibling.get("run_id")) == run_id:
                continue
            if str(sibling.get("prompt_sha256")) != digest:
                continue
            # Resolved onto the current vocabulary like everything else: a
            # retest is the same instrument answering the same questionnaire,
            # and reading its rows at a different schema from the run they are
            # compared against would report every label as a disagreement.
            sibling_rows = [
                llm.resolve_row(row)
                for row in model_runs.read_rows(candidate.parent / "annotations.jsonl")
            ]
            overlap = len(usage_comparison.comparison_overlap(rows, sibling_rows))
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, str(sibling.get("run_id", "")), sibling_rows)
        if best is None:
            continue
        overlap, sibling_id, sibling_rows = best
        contested = usage_comparison.contested_rows(rows, sibling_rows)
        out.append(
            {
                "which": label,
                "model": model,
                "run_id": run_id,
                "retest_run_id": sibling_id,
                "overlap": overlap,
                "fields": usage_comparison.comparison_fields(rows, sibling_rows),
                "function_jaccard": usage_comparison.comparison_function_jaccard(rows, sibling_rows),
                "identical": int(sum(not fields for fields, _ in contested.values())),
            }
        )
    return out


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
    comparison run labelled differently, and that run's own six labels where it
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
            value = row.get(field, "")
            entry[field] = bool(value) if field == "evidence_valid" else str(value or "")
        fields, alternative = contested.get(str(row["occurrence_id"]), ([], None))
        entry["contested"] = fields
        entry["alt"] = alternative
        out.append(entry)
    return out


def diffusion_block(
    rows: pd.DataFrame, referent_order: list[str], speeches: pd.DataFrame | None = None
) -> dict[str, object]:
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
        referents = usage.diffusion_rows(rows, referent_order)
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
    # The risk set beside each curve: who sat in a debate that named the case.
    exposure = {} if speeches is None else usage.exposure_rows(rows, speeches)
    for entry in referents:
        entry["exposed"] = exposure.get(str(entry["id"]), [])
    return {"milestones": list(usage.MILESTONES), "referents": referents}


#: Every dated first the diffusion figure draws, for a coder to check against
#: the record. A first is a minimum over dates, so a single mislabelled early
#: occurrence moves it, and there are few enough of them to read them all.
FIRST_EVENTS = INTERIM / "genocide_first_events.csv"


def write_first_events(diffusion: dict[str, object], rows: pd.DataFrame) -> None:
    """The review list of first events, with each one's evidence quotation."""
    quotes = {
        str(line): (str(identifier), str(quote))
        for line, identifier, quote in zip(
            rows["line_id"], rows["occurrence_id"], rows["evidence_quote"], strict=True
        )
    }
    records = [
        {
            "referent": entry["id"],
            "actor": event["actor"],
            "milestone": event["milestone"],
            "date": event["date"],
            "line_id": event["id"],
            "occurrence_id": quotes.get(str(event["id"]), ("", ""))[0],
            "evidence_quote": quotes.get(str(event["id"]), ("", ""))[1],
            "verified": "",
            "note": "",
        }
        for entry in diffusion["referents"]  # type: ignore[union-attr]
        for event in entry["events"]
    ]
    artifacts.atomic_write_csv(FIRST_EVENTS, pd.DataFrame(records))
    console.info(f"wrote {rel(FIRST_EVENTS)}: {len(records):,} first events to verify")


def build_note(
    payload: dict[str, object],
    counts: dict[str, int],
    jaccard: float | None,
    minimum: int,
    run_directory: Path,
    *,
    synthetic: bool = False,
    prior_review: dict[str, object] | None = None,
) -> str:
    """The findings note: the funnel, the leaders, and what is withheld.

    `prior_review` is :func:`lib.gold_estimates.without_prior_review`'s block:
    once anything is coded, the note repeats its gold tables without the
    passages read against a model's labels before coding.
    """
    model = payload["model"]
    gold = payload["gold"]
    actors = payload["actors"]
    referents = [row for row in payload["referents"] if int(row["occurrences"]) > 0]
    positions = payload["position_by_actor"]
    annotated = int(model["occurrences_annotated"])
    total = int(model["occurrences_total"])
    withheld = [row for row in actors if not row["sufficient"]]
    withheld_shares = [row for row in positions if not row["sufficient"]]

    def share(value: int, of: int) -> str:
        return f"{value / of:.1%}" if of else "—"

    def number(value: object, digits: int = 3) -> str:
        """A statistic, or an em dash where it is not defined."""
        return "—" if value is None else f"{float(value):.{digits}f}"

    def percent(value: object) -> str:
        return "withheld" if value is None else f"{float(value):.1%}"

    ranked = sorted(positions, key=lambda row: -int(row["eligible"]))
    denial = sorted(
        (row for row in positions if row["share_rejects"] is not None),
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
            if event["milestone"] == "rejects"
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
    prior = prior_review or {}
    agreement_without = [
        f"| `{row['field']}` | {row['n']} | {number(row['observed'])} | "
        f"{number(row['kappa'])} |"
        for row in prior.get("human_agreement", [])
    ]
    scored_without = [
        f"| `{row['field']}` | {row['n']} | {number(row['accuracy'])} | "
        f"{number(row['macro_f1'])} | {number(row['abstention_rate'])} |"
        for row in prior.get("model_vs_human", [])
    ]
    jaccard_without = prior.get("function_jaccard")

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
            f"| `speaker_position` = `unclear` | {model['abstention']['position_unclear']:,} | "
            f"{share(model['abstention']['position_unclear'], annotated)} |",
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
            "eligible occurrences, which is the denominator the position composition is cut "
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
            "that referent whatever position it carried; the last two columns count the "
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
            f"- {len(withheld_shares):,} of {len(positions):,} speakers carry no "
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
                    "### Without the passages read before coding",
                    "",
                    f"{prior.get('flagged_coded', 0):,} of the {prior.get('coded', 0):,} coded "
                    "occurrences are among the passages read against the Qwen run's labels "
                    "on 10 September 2026, before coding began "
                    f"(`{rel(PRIOR_REVIEW)}`), so a coder may have seen the model's answer "
                    "for them. They stay in the sample, and every figure above is repeated "
                    "here without them (docs/EVALUATION_PLAN.md, section 4). PABAK, the MASI "
                    "alpha, the comparison run's scores, the weighted accuracy and the "
                    "corrected shares are repeated in the step's manifest, under "
                    "`gold_without_prior_review`.",
                    "",
                    *(
                        [
                            "| Field | n | Observed | Kappa |",
                            "|---|---:|---:|---:|",
                            *agreement_without,
                            "",
                        ]
                        if agreement_without
                        else []
                    ),
                    *(
                        [
                            "| Field | n | Accuracy | Macro-F1 | Model abstention |",
                            "|---|---:|---:|---:|---:|",
                            *scored_without,
                            "",
                        ]
                        if scored_without
                        else []
                    ),
                    (
                        "Mean Jaccard overlap on `function` against the same reference: "
                        f"**{float(jaccard_without):.3f}**."
                        if jaccard_without is not None
                        else "The `function` overlap could not be computed without them."
                    ),
                    "",
                ]
                if prior and (agreement or scored)
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
                    "are contested on at least one of the six fields. Each of them "
                    "carries the other run's six labels in `occurrences.json`, under "
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
            "unmeasured; after it is, corpus accuracy is estimated from the probability "
            "frame rather than asserted over the full occurrence population.",
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


def run_without_model() -> None:
    """Write an explicit empty usage layer while the migrated corpus has no run."""
    console.step("No current model run; writing the migration state")
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)
    lex = lexicon.load()
    found = occurrences_lib.enumerate_term(speeches, bodies, lex.terms[TERM])
    if problems := check_population(found):
        console.fail("the enumeration disagrees with docs/CORPUS.md", problems)

    if not GOLD_CANDIDATES.is_file():
        console.fail(
            f"{rel(GOLD_CANDIDATES)} is missing",
            ["run 13_gold_sample.py first"],
        )
    candidates = pd.read_csv(GOLD_CANDIDATES, dtype="string", keep_default_na=False)
    annotations = audit.read_annotations(GOLD_ANNOTATIONS)
    empty = pd.DataFrame()
    prompt_text = PROMPT.read_text(encoding="utf-8") if PROMPT.is_file() else ""
    referent_list, published = read_referents(REFERENTS)
    referent_rows = [{**row, "occurrences": 0} for row in published]
    zeros = {
        "verdict_uncertain": 0,
        "referent_unclear": 0,
        "position_unclear": 0,
    }
    meta = artifacts.provenance(
        ROOT,
        "15_usage.py",
        inputs=[SPEECHES_NORM, GOLD_CANDIDATES],
        configs=[LEXICON, REFERENTS, PROMPT, GOLD_ANNOTATIONS],
        extra={
            "state": "awaiting_new_model_run",
            "occurrences_total": len(found),
            "occurrences_annotated": 0,
            "outputs": [],
        },
    )
    payload = {
        "meta": meta,
        "model": {
            "id": "not-run",
            "run_id": "",
            "run_date": "",
            "prompt_version": "",
            "referents_version": str(referent_list.version),
            "prompt_sha256": prompts.prompt_sha256(PROMPT) if PROMPT.is_file() else "",
            "reasoning_effort": "",
            "requests": 0,
            "requests_recounted": False,
            "occurrences_total": len(found),
            "occurrences_annotated": 0,
            "parse_failures": 0,
            "evidence_invalid": 0,
            "abstention": zeros,
            "tokens": {"input": 0, "output": 0},
        },
        "prompt": prompt_text,
        "referents": referent_rows,
        "actors": [],
        "minimum_occurrences": 20,
        "matrix": [],
        "position_by_actor": [],
        "diffusion": {"milestones": list(usage.MILESTONES), "referents": []},
        "comparison": usage_comparison.comparison_block([], []),
        "retest": [],
        "gold": gold_estimates.gold_block(
            annotations,
            empty,
            sample_size=len(candidates),
            unique_occurrences=int(candidates["occurrence_id"].nunique()),
            candidates=candidates,
        ),
    }
    with artifacts.atomic_directory(USAGE) as staged:
        artifacts.atomic_write_json(staged / "usage.json", payload)
        artifacts.atomic_write_json(
            staged / "occurrences.json", {"meta": meta, "occurrences": []}
        )
    write_note(
        "15_usage.md",
        "# 15 — Usage\n\nNo model run is selected after the corpus migration. "
        f"The empty artefact records {len(found):,} occurrences awaiting annotation; "
        "no historical label was joined to the new corpus.\n",
    )
    artifacts.atomic_write_json(
        MANIFESTS / "15_usage.json",
        artifacts.provenance(
            ROOT,
            "15_usage.py",
            inputs=[SPEECHES_NORM, GOLD_CANDIDATES],
            configs=[LEXICON, REFERENTS, PROMPT, GOLD_ANNOTATIONS],
            extra={
                "state": "awaiting_new_model_run",
                "occurrences_total": len(found),
                "occurrences_annotated": 0,
                "outputs": [
                    artifacts.describe_file(USAGE / "usage.json", ROOT),
                    artifacts.describe_file(USAGE / "occurrences.json", ROOT),
                ],
                # Kept out of the payload, whose shape the contract fixes; the
                # coders' agreement is all there is to repeat without a model.
                "gold_without_prior_review": gold_estimates.without_prior_review(
                    annotations, empty, reviewed=reviewed_before_coding(candidates)
                ),
            },
        ),
        indent=1,
    )
    console.info(f"wrote an empty, explicit usage layer in {rel(USAGE)}")


def run(args: argparse.Namespace) -> None:
    ensure_dirs()

    selected = args.run or (
        CURRENT_RUN.read_text(encoding="utf-8").strip() if CURRENT_RUN.is_file() else ""
    )
    if args.run_dir is None and not selected:
        run_without_model()
        return

    console.step("Choosing the run")
    directory, run_id = select_run(args.run, args.run_dir)
    # Decided on the committed id, before a run read by path borrows the id its
    # manifest records: the allowance names a committed run.
    allowed_by = (
        "--allow-partial"
        if args.allow_partial
        else f"{rel(model_runs.ALLOW_PARTIAL_RUN)} names this run"
        if model_runs.partial_allowed(run_id)
        else ""
    )
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
    comparison_schema: dict[str, int] = {"unanswered": 0, "split_decision": 0}
    comparison_schema_version = ""
    if comparison_dir is None:
        console.info(
            f"no comparison run selected in {rel(COMPARISON_RUN)}; the second opinion "
            "block is written empty"
        )
    else:
        usage_refusals.refuse_self_comparison(directory, comparison_dir)
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
        console.fail("the enumeration disagrees with config/lexicon.counts.json", problems)
    console.info(
        f"{len(found):,} occurrences in "
        f"{len({occurrence.filename for occurrence in found}):,} speeches"
    )
    enumerated = enumerated_frame(speeches, found)

    console.step("Checking the run against this corpus")
    prompt = usage_refusals.resolve_prompt(manifest)
    console.info(
        f"prompt v{prompt.version}, sha256 {prompt.sha256[:12]}, published from "
        f"{prompt.name}"
    )
    referent_list, referent_table = read_referents(REFERENTS)
    raw_rows, schema_counts, superseded = usage_refusals.validated(
        manifest, raw_rows, lex=lex, enumerated=enumerated, referent_list=referent_list
    )
    usage_refusals.refuse_partial(len(raw_rows), len(found), allowed_by, run_id=run_id)
    console.info(
        f"referent list v{referent_list.version}: {len(referent_list.current)} current, "
        f"{len(referent_list.retired_in)} retired, every row validated against them"
    )
    if superseded:
        console.info(
            f"{superseded:,} rows carry a superseded referent and are read under its "
            "successor; the run's own version is in the artefact's provenance"
        )
    if schema_counts["unanswered"]:
        console.info(
            f"{schema_counts['unanswered']:,} rows were coded against annotation schema "
            f"{audit.LEGACY_SCHEMA_VERSION} and carry none of the six fields schema "
            f"{llm.SCHEMA_VERSION} adds; they are read, never guessed at"
        )
    if schema_counts["split_decision"]:
        console.info(
            f"{schema_counts['split_decision']:,} rows record a position on a passage "
            "their own referent says names no case — the split decision schema "
            f"{llm.SCHEMA_VERSION} locks"
        )

    if comparison_raw:
        # Every identity check the published run passed, plus the one only a
        # comparison can fail. Coverage is the one thing not checked: a
        # comparison run is read over the occurrences both runs reached, so a
        # short one narrows the comparison rather than invalidating the counts.
        usage_refusals.refuse_other_prompt(comparison_manifest, prompt.sha256)
        # The comparison may be a run made against a different version of the
        # referent list — that is the point of reading two runs side by side —
        # so it is checked against its own recorded version and resolved onto
        # the same current identifiers before either is counted.
        comparison_raw, comparison_schema, _ = usage_refusals.validated(
            comparison_manifest,
            comparison_raw,
            lex=lex,
            enumerated=enumerated,
            referent_list=referent_list,
            what="the comparison run",
        )
        comparison_schema_version = str(
            comparison_manifest.get("schema_version", "") or audit.LEGACY_SCHEMA_VERSION
        )
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
    contested = usage_comparison.contested_rows(rows, comparison_raw)
    comparison = usage_comparison.comparison_block(
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

    console.step("The noise floor: each model against itself")
    retest = retest_block(
        [
            ("published", manifest, raw_rows),
            *(
                []
                if not comparison_raw
                else [("comparison", comparison_manifest, comparison_raw)]
            ),
        ]
    )
    for entry in retest:
        console.info(
            f"{entry['model']} vs {entry['retest_run_id']}: {entry['overlap']:,} shared, "
            f"{entry['identical']:,} identical on every compared field"
        )
    if not retest:
        console.info("no run of either model with the same prompt to retest against")

    console.step("Aggregating")
    blocks = usage.aggregate(
        rows,
        referent_table,
        args.minimum,
        contested=frozenset(
            key for key, (fields, _) in contested.items() if fields
        ),
    )
    counts = usage.funnel(rows)
    diffusion = diffusion_block(
        rows,
        [str(row["id"]) for row in blocks["referents"]],
        speeches[["filename", "meeting_symbol", "country_org", "date"]],
    )
    write_first_events(diffusion, rows)
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
                f"{sum(1 for row in blocks['position_by_actor'] if not row['sufficient']):,} "
                f"of {len(blocks['position_by_actor']):,}",
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
    if not GOLD_DESIGN.is_file():
        console.fail(
            f"{rel(GOLD_DESIGN)} is missing",
            ["run 13_gold_sample.py first; it writes the design beside the candidates"],
        )
    design = pd.read_csv(GOLD_DESIGN, dtype={"occurrence_id": "string"}, keep_default_na=False)
    annotations = audit.read_annotations(GOLD_ANNOTATIONS)
    gold = gold_estimates.gold_block(
        annotations,
        rows,
        sample_size=len(candidates),
        unique_occurrences=int(candidates["occurrence_id"].nunique()),
        # The frames are reported separately or not at all: the probability
        # frame is weighted back to the corpus and estimates accuracy over it,
        # the disagreement frame is a purposive over-sample whose inclusion
        # probabilities differ by a factor of seven, and a figure pooled over
        # both would estimate nothing. 13 records the probability per row.
        candidates=candidates,
        # The comparison run scored against the same human reference, by the same
        # computation. This is the one place either model can be said to be
        # accurate about anything; the `comparison` block scores them against each
        # other, which measures neither.
        comparison=pd.DataFrame(comparison_raw),
        # Every population unit's probability under the union of the frames,
        # which is what the weighted accuracy and the corrected shares divide by.
        design=design,
    )
    jaccard = gold_estimates.function_jaccard(annotations, rows)
    console.info(
        f"gold state '{gold['state']}': {gold['double_coded']:,} of "
        f"{gold['unique_occurrences']:,} occurrences double-coded, "
        f"{gold['adjudicated']:,} adjudicated"
    )
    # Every gold figure again without the passages read against a model's labels
    # before coding (docs/EVALUATION_PLAN.md §4). Written to the note and the
    # manifest rather than the payload: the payload's shape is the contract the
    # dashboard is built against, and nothing on it reads these figures yet.
    reviewed = reviewed_before_coding(candidates)
    without_review = gold_estimates.without_prior_review(
        annotations,
        rows,
        reviewed=reviewed,
        comparison=pd.DataFrame(comparison_raw),
        design=design,
    )
    console.info(
        f"{len(reviewed):,} sampled occurrences were read against a model's labels before "
        f"coding, {without_review['flagged_coded']:,} of them coded; every gold figure is "
        "repeated without them"
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
            # Both: the list the counts were cut on, and the list the run was
            # made against, because a run whose superseded identifiers were
            # resolved is reported under names its own prompt never showed it.
            "referents_version": referent_list.version,
            "run_referents_version": int(str(manifest.get("referents_version", "") or 1)),
            # The prompt has no such pair: nothing is resolved onto a later
            # wording, so what is published is the run's own version and the
            # file it was found in.
            "prompt_version": prompt.version,
            "prompt_file": prompt.name,
            # The schema the counts are reported in, and the schema the run was
            # coded against, for the same reason the referent pair is carried:
            # a resolved row is reported under names its own codebook did not
            # have.
            "schema_version": llm.SCHEMA_VERSION,
            "run_schema_version": str(
                manifest.get("schema_version", "") or audit.LEGACY_SCHEMA_VERSION
            ),
            "rows_without_schema_3_fields": schema_counts["unanswered"],
            "rows_with_split_case_decision": schema_counts["split_decision"],
            "term": TERM,
            "run_id": run_id,
            "run_dir": rel(directory),
            "model": str(manifest.get("model", "")),
            "minimum_occurrences": args.minimum,
            "occurrences_total": len(found),
            "occurrences_annotated": len(rows),
            "allow_partial": bool(allowed_by),
            "state": "partial_model_run" if len(rows) < len(found) else "annotated_model_run",
            # Output file hashes live in the stage manifest; payloads cannot hash themselves.
            "outputs": [],
        },
    )
    # Written in reading order rather than in the order the blocks were computed:
    # the two axes the matrix is indexed by come before the cells, and
    # `minimum_occurrences` sits between the actors and the shares it governs.
    # JSON objects are unordered and every consumer here reads by key, so this is
    # for whoever opens the file.
    payload = {
        "meta": meta,
        # The run's own digest and the run's own text, from wherever the
        # library resolved them, so a v1 run keeps saying v1 after the file
        # beside it has become v2.
        "model": usage.model_block(manifest, run_id, prompt.sha256, rows, len(found)),
        "prompt": prompt.text,
        "referents": blocks["referents"],
        "actors": blocks["actors"],
        "minimum_occurrences": args.minimum,
        "matrix": blocks["matrix"],
        "position_by_actor": blocks["position_by_actor"],
        "diffusion": diffusion,
        "comparison": comparison,
        "retest": retest,
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
            prior_review=without_review,
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
                # A comparison may be a run of a different schema — that is one
                # of the things two runs may differ by — so its own resolution
                # is reported beside the published run's rather than folded in.
                "comparison_schema_version": comparison_schema_version,
                "comparison_rows_without_schema_3_fields": comparison_schema["unanswered"],
                "comparison_overlap": comparison["overlap"],
                "comparison_contested": comparison["contested_any"],
                "retest_runs": [entry["retest_run_id"] for entry in retest],
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
                "gold_without_prior_review": without_review,
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
        help="aggregate a run that has not reached every occurrence, and record the gap; "
        "implied for the run allow_partial_run.txt names",
    )
    parser.add_argument(
        "--minimum",
        type=int,
        default=usage.MINIMUM_OCCURRENCES,
        help="occurrences a speaker needs before a share of them is published",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    console.main(main)
