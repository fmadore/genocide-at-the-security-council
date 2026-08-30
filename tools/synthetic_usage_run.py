"""Fabricate a complete model run so the payload contract exists before the bill.

**Nothing here is data.** Every label this writes is invented by a hash of an
occurrence identifier. The run it produces is stamped `0000-00-00-synthetic` and
attributed to a model called `synthetic-fixture`, both of which are impossible
values for a real run: run ids are dates and the model field records an exact API
model id. `15_usage.py` will aggregate it happily, and the artefacts it produces
are a shape and not a finding. Never put this run id in
`model_annotations/genocide/current_run.txt`, and never read a number out of the
`usage.json` built from it.

Two things it is for:

- **The contract.** `tests/contract/payload.json` is the committed skeleton of
  everything the dashboard fetches, and `export_web.py` refuses to publish a
  payload that no longer matches it. The usage view has to be written against a
  declared shape, and the shape cannot be declared from an artefact that does not
  exist. A paid run is weeks away and a frontend is not blocked on it.
- **Looking at it.** A view built against an empty fixture is a view nobody has
  seen full. This produces 6,092 rows with a plausible spread — most occurrences
  asserting a case, a minority denying one, a few percent abstaining, a few
  refusing the match outright — so the matrix has the density and the ragged
  edges the real one will have.

The distribution is engineered to exercise both variants of every leaf the
contract records as nullable, because a fixture that only ever produced one of
them would declare a narrower shape than the real run needs: a speaker above the
minimum and a speaker below it, so `share_rejects` is a float somewhere and null
somewhere; a state and an IGO, so `actors[].iso3` is a string somewhere and null
somewhere. Both are asserted before anything is written, and the tool fails
rather than shipping a single-variant contract.

Output goes to `data/interim/synthetic_run/`, which `.gitignore` excludes — the
fixture takes a minute to rebuild from the corpus, and committing 6,092
fabricated annotations beside a directory of real ones is exactly the confusion
the naming above is trying to prevent.

    python tools/synthetic_usage_run.py
    python scripts/15_usage.py --run-dir data/interim/synthetic_run

Requires an x64 Python 3.12 — pyarrow publishes no 32-bit wheel.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import artifacts, audit, console, frames, lexicon, llm
from lib import occurrences as occurrences_lib
from lib.kwic import sentence_at, sentence_spans
from lib.paths import INTERIM, LEXICON, ROOT, SPEECHES_NORM, ensure_dirs, rel

TERM = "genocide"

#: Impossible values for a real run, on purpose. A run id is a date and a model
#: field records an exact API model id, so neither of these can be mistaken for
#: something that was asked of an API.
RUN_ID = "0000-00-00-synthetic"
MODEL = "synthetic-fixture"

#: Fixed, so that rebuilding the fixture twice produces byte-identical files and
#: a contract diff means a real shape change. A real run stamps the day it ran.
ANNOTATED_AT = "2000-01-01"
TIMESTAMP = "2000-01-01T00:00:00Z"

OUTPUT = INTERIM / "synthetic_run"
PROMPT = ROOT / "model_annotations" / TERM / "PROMPT.md"
REFERENTS = ROOT / "annotations" / "lexicon" / "referents.csv"

COLUMNS = ["filename", "body_start", "text", "country_org", "iso3"]

DOCUMENTED_SPEECHES = 3_273
DOCUMENTED_OCCURRENCES = 6_092

#: The minimum `15_usage.py` withholds a share below. Duplicated here as a
#: post-condition rather than imported as a rule: this tool's job is to produce a
#: fixture that straddles it, and it has to be able to say that it did.
MINIMUM_OCCURRENCES = 20

#: What the model is pretending to have decided, as (label, weight) pairs. The
#: weights are a guess at a plausible shape and nothing more — no claim is made
#: that the Council asserts genocide four times as often as it denies it.
VERDICTS: tuple[tuple[str, float], ...] = (
    ("true_positive", 0.950),
    ("false_positive", 0.030),
    ("uncertain", 0.020),
)
STANCES: tuple[tuple[str, float], ...] = (
    ("asserts", 0.60),
    ("attributes_or_reports", 0.12),
    ("rejects_or_denies", 0.10),
    ("neutral_legal_reference", 0.08),
    ("hypothetical_or_conditional", 0.07),
    ("unclear", 0.03),
)
QUOTATIONS: tuple[tuple[str, float], ...] = (
    ("not_quoted", 0.78),
    ("attributed_or_reported", 0.13),
    ("direct_quotation", 0.06),
    ("unclear", 0.03),
)
FUNCTIONS: tuple[tuple[str, float], ...] = (
    ("accusation_or_qualification", 0.34),
    ("warning_or_prevention", 0.17),
    ("commemoration", 0.13),
    ("accountability", 0.12),
    ("institutional_title_or_mandate", 0.09),
    ("accusation_or_qualification|accountability", 0.06),
    ("warning_or_prevention|accusation_or_qualification", 0.04),
    ("commemoration|accountability", 0.02),
    ("other", 0.02),
    ("unclear", 0.01),
)
CONFIDENCE: tuple[tuple[str, float], ...] = (
    ("high", 0.55),
    ("medium", 0.35),
    ("low", 0.10),
)

#: Share of true positives sent down each of the two referent side-paths.
UNCLEAR_REFERENT = 0.045
OTHER_REFERENT = 0.020

#: Share of rows whose evidence quotation is deliberately unlocatable, so that
#: `evidence_valid` is false somewhere and the eligibility gate has something to
#: bite on. The string is signposted rather than plausible: a fixture that faked
#: a near-miss quotation would be testing the locator instead of the aggregation.
BAD_EVIDENCE = 0.025
BAD_QUOTE = "[synthetic fixture] this quotation is not in the speech"

#: What a `referent: other` row proposes. One value, so it is obvious in a diff.
PROPOSED = "a case the controlled list does not hold"


def stream(occurrence_id: str, salt: str) -> float:
    """A uniform draw in [0, 1) that depends on nothing but its two arguments.

    Seeded by the occurrence identity rather than by a counter, so the labels are
    the same whatever order the corpus is read in and stay the same when the
    enumeration grows a speech somewhere in the middle.
    """
    digest = hashlib.sha256(f"{salt}\x1f{occurrence_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def pick(value: float, weighted: Sequence[tuple[str, float]]) -> str:
    """The label whose weight interval contains `value`."""
    cursor = value * sum(weight for _, weight in weighted)
    for label, weight in weighted:
        cursor -= weight
        if cursor < 0:
            return label
    return weighted[-1][0]


def referent_weights(referents: Sequence[str]) -> tuple[tuple[str, float], ...]:
    """A skewed but complete spread over the controlled cases.

    Zipf-shaped in the file's own order, which puts Rwanda and Bosnia at the top
    where the corpus would too, and gives the thinnest referent about one percent
    of the assigned rows — enough that every one of them appears, which is the
    property the payload contract needs. A uniform spread would be a less
    plausible fixture; a steeper one would leave the tail empty.
    """
    return tuple((name, 1 / (position + 1.5)) for position, name in enumerate(referents))


def labels_for(occurrence_id: str, sentence: str, cases: Sequence[tuple[str, float]]) -> dict:
    """One occurrence's fabricated labels, obeying the codebook's own cascade.

    The rules `lib.llm.check_labels` enforces are followed here rather than
    worked around: a false positive carries `not_applicable` in all four
    discourse fields and nothing else does, `other` carries a proposed referent
    and nothing else does, and `uncertain` abstains across the board rather than
    guessing labels for a passage it has just said is illegible.
    """
    verdict = pick(stream(occurrence_id, "verdict"), VERDICTS)
    quote = (
        BAD_QUOTE if stream(occurrence_id, "evidence") < BAD_EVIDENCE else sentence
    )

    if verdict == "false_positive":
        return {
            "verdict": verdict,
            "quotation": "not_applicable",
            "stance": "not_applicable",
            "function": ("not_applicable",),
            "referent": "not_applicable",
            "proposed_referent": "",
            "evidence_quote": quote,
            "confidence": pick(stream(occurrence_id, "confidence"), CONFIDENCE),
        }
    if verdict == "uncertain":
        return {
            "verdict": verdict,
            "quotation": "unclear",
            "stance": "unclear",
            "function": ("unclear",),
            "referent": "unclear",
            "proposed_referent": "",
            "evidence_quote": quote,
            "confidence": "low",
        }

    draw = stream(occurrence_id, "referent")
    if draw < UNCLEAR_REFERENT:
        referent, proposed = "unclear", ""
    elif draw < UNCLEAR_REFERENT + OTHER_REFERENT:
        referent, proposed = "other", PROPOSED
    else:
        referent, proposed = pick(stream(occurrence_id, "case"), cases), ""
    return {
        "verdict": verdict,
        "quotation": pick(stream(occurrence_id, "quotation"), QUOTATIONS),
        "stance": pick(stream(occurrence_id, "stance"), STANCES),
        "function": tuple(
            pick(stream(occurrence_id, "function"), FUNCTIONS).split("|")
        ),
        "referent": referent,
        "proposed_referent": proposed,
        "evidence_quote": quote,
        "confidence": pick(stream(occurrence_id, "confidence"), CONFIDENCE),
    }


def check_variants(rows: pd.DataFrame, referents: Sequence[str]) -> list[str]:
    """The post-conditions that make this fixture a usable contract.

    Each of these is a leaf the committed skeleton records as carrying two types.
    A fixture that produced only one of them would declare a narrower shape than
    the real run needs, `export_web.py` would then refuse the real run's payload
    for a difference nobody introduced, and the failure would arrive months later
    attached to the wrong change.
    """
    problems: list[str] = []

    used = set(rows["referent"])
    if missing := sorted(set(referents) - used):
        problems.append(
            f"{len(missing)} referents are never assigned: {', '.join(missing[:6])}"
        )

    eligible = rows.loc[rows["verdict"].eq("true_positive") & rows["evidence_valid"]]
    per_actor = eligible.groupby("country_org").size()
    above = int((per_actor >= MINIMUM_OCCURRENCES).sum())
    below = int((per_actor < MINIMUM_OCCURRENCES).sum())
    if not above or not below:
        problems.append(
            f"share_rejects would be single-typed: {above} speakers at or above "
            f"{MINIMUM_OCCURRENCES} eligible occurrences, {below} below"
        )

    # Blank is missing, not a value, and the parquet spells it three ways
    # depending on how it was read — None, NaN, pd.NA. `lib.actors._text` makes
    # the same argument about the same column.
    codes = rows["iso3"].map(lambda value: "" if pd.isna(value) else str(value).strip())
    coded = codes.ne("").groupby(rows["country_org"]).any()
    if not coded.any() or coded.all():
        problems.append(
            f"actors[].iso3 would be single-typed: {int(coded.sum())} speakers carry a "
            f"code and {int((~coded).sum())} carry none"
        )
    return problems


def build(limit: int | None) -> None:
    ensure_dirs()

    console.step("Reading the corpus and the lexicon")
    speeches = frames.read(SPEECHES_NORM, columns=COLUMNS)
    bodies = frames.body(speeches)
    lex = lexicon.load()
    if TERM not in lex.terms or not lex.terms[TERM].enabled:
        console.fail(f"'{TERM}' is not an active term in {rel(LEXICON)}")
    console.info(f"lexicon version {lex.version} ({lex.updated})")

    console.step("Enumerating the term")
    found = occurrences_lib.enumerate_term(speeches, bodies, lex.terms[TERM])
    grouped: dict[object, list[occurrences_lib.Occurrence]] = {}
    for occurrence in found:
        grouped.setdefault(occurrence.index, []).append(occurrence)
    console.info(f"{len(found):,} occurrences in {len(grouped):,} speeches")
    if limit is None and (
        len(found) != DOCUMENTED_OCCURRENCES or len(grouped) != DOCUMENTED_SPEECHES
    ):
        console.fail(
            "the enumeration does not reproduce the documented figures",
            [
                f"speeches {len(grouped):,} vs {DOCUMENTED_SPEECHES:,}",
                f"occurrences {len(found):,} vs {DOCUMENTED_OCCURRENCES:,}",
                "a fixture cut from a different population would declare the wrong shape",
            ],
        )

    console.step("Reading the prompt and the controlled referents")
    pack = llm.load_prompt(PROMPT)
    referents = audit.read_referents(REFERENTS)
    cases = referent_weights(
        [
            referent.id
            for referent in llm.read_referent_table(REFERENTS)
            if referent.id not in audit.DEFAULT_REFERENTS
        ]
    )
    console.info(f"prompt v{pack.version} {pack.sha256[:12]}, {len(cases)} controlled cases")

    console.step("Fabricating labels")
    meta = llm.RunMeta(
        run_id=RUN_ID,
        model=MODEL,
        prompt_version=pack.version,
        prompt_sha256=pack.sha256,
        reasoning_effort="high",
        lexicon_version=str(lex.version),
        term=TERM,
        annotated_at=ANNOTATED_AT,
    )
    rows: list[dict[str, object]] = []
    order = list(grouped)[:limit] if limit is not None else list(grouped)
    for index in order:
        items = grouped[index]
        body = str(bodies.loc[index])
        spans = sentence_spans(body)
        labels = {
            occurrence.ordinal: labels_for(
                occurrence.occurrence_id, sentence_at(body, occurrence.start, spans), cases
            )
            for occurrence in items
        }
        annotated = llm.annotation_rows(items, body, labels, meta)
        for row in annotated:
            llm.validate_row(row, referents)
        rows.extend(annotated)
    console.info(f"{len(rows):,} rows, every one validated by lib.llm.validate_row")

    console.step("Checking the fixture straddles what the contract needs")
    frame = pd.DataFrame(rows)
    speakers = speeches.loc[[occurrence.index for occurrence in found], ["country_org", "iso3"]]
    if limit is not None:
        speakers = speakers.iloc[: len(frame)]
    frame = pd.concat(
        [frame.reset_index(drop=True), speakers.reset_index(drop=True)], axis=1
    )
    # All twenty-nine, not only the twenty-six cases: the three reserved ids are
    # reached through the false-positive cascade and the two abstention paths, and
    # a fixture that never took one of those would leave that path untested.
    if problems := check_variants(
        frame, [name for name, _ in cases] + sorted(audit.DEFAULT_REFERENTS)
    ):
        console.fail(
            "the fabricated distribution would ship a single-variant contract",
            [*problems, "adjust the weights above rather than the contract"],
        )
    eligible = frame.loc[frame["verdict"].eq("true_positive") & frame["evidence_valid"]]
    console.table(
        [
            ("occurrences", f"{len(frame):,}"),
            ("true positives", f"{int(frame['verdict'].eq('true_positive').sum()):,}"),
            ("evidence not located", f"{int((~frame['evidence_valid']).sum()):,}"),
            ("eligible", f"{len(eligible):,}"),
            ("referents used", f"{frame['referent'].nunique()}"),
            ("speakers", f"{frame['country_org'].nunique()}"),
            (
                "rejects_or_denies",
                f"{int(frame['stance'].eq('rejects_or_denies').sum()):,}",
            ),
        ]
    )

    console.step("Writing")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    annotations = OUTPUT / "annotations.jsonl"
    # `lib.llm.append_rows` appends, because a real run arrives in pieces over
    # hours and must never lose work already paid for. A fixture is rebuilt whole,
    # so the previous one is removed rather than doubled.
    annotations.unlink(missing_ok=True)
    llm.append_rows(annotations, rows)
    manifest = {
        "run_id": RUN_ID,
        "term": TERM,
        "model": MODEL,
        "reasoning_effort": "high",
        "prompt_version": pack.version,
        "prompt_sha256": pack.sha256,
        "referents_sha256": artifacts.sha256(REFERENTS),
        "lexicon_version": str(lex.version),
        "schema_version": llm.SCHEMA_VERSION,
        "mode": "synthetic",
        "limit": limit,
        "created": TIMESTAMP,
        "completed": TIMESTAMP,
        "git_commit": artifacts.git_commit(ROOT),
        "batch_ids": [],
        "requests": {
            "planned": len(order),
            "submitted": len(order),
            "returned": len(order),
            "complete": len(order),
        },
        "occurrences": {"planned": len(rows), "written": len(rows)},
        "parse_failures": 0,
        "evidence_invalid": int((~frame["evidence_valid"]).sum()),
        # Zero rather than a plausible figure. No tokens were spent, and a
        # fixture that invented a bill would put an invented cost into a research
        # manifest.
        "usage": {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
        "cost_usd": None,
        "status": "complete",
        "synthetic": True,
    }
    artifacts.atomic_write_json(OUTPUT / "manifest.json", manifest, indent=1)
    console.info(f"wrote {rel(annotations)} and manifest.json")
    console.warn(
        f"this run is fabricated: run id {RUN_ID}, model {MODEL}. Never put it in "
        "model_annotations/genocide/current_run.txt."
    )
    console.info(f"aggregate it with: python scripts/15_usage.py --run-dir {rel(OUTPUT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        help="only the first N genocide-bearing speeches, for a quick look; the "
        "contract must be declared from a full fixture",
    )
    build(parser.parse_args().limit)


if __name__ == "__main__":
    main()
