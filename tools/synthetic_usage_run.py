"""Fabricate two complete model runs so the payload contract exists before the bill.

**Nothing here is data.** Every label this writes is invented by a hash of an
occurrence identifier. The runs it produces are stamped `0000-00-00-synthetic`
and `0000-00-00-synthetic-comparison`, attributed to models called
`synthetic-fixture` and `synthetic-comparison`, all of which are impossible
values for a real run: run ids are dates and the model field records an exact API
model id. `15_usage.py` will aggregate them happily, and the artefacts it
produces are a shape and not a finding. Never put either run id in
`model_annotations/genocide/current_run.txt` or `comparison_run.txt`, and never
read a number out of the `usage.json` built from them.

The second run is the **counter-instrument** the comparison block is declared
from: the same occurrences and the same prompt hash, a different model id, and
labels that are the first run's with some decisions deterministically redrawn, so
that every compared field carries both agreements and disagreements. It also
omits a small share of the occurrences outright, because a comparison run may
legitimately cover less of the corpus than the published one and the artefact has
to have a shape for that.

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

Output goes to `data/interim/synthetic_run/` and
`data/interim/synthetic_run_comparison/`, which `.gitignore` excludes — the
fixture takes a minute to rebuild from the corpus, and committing 6,092
fabricated annotations beside a directory of real ones is exactly the confusion
the naming above is trying to prevent.

    python tools/synthetic_usage_run.py
    python scripts/15_usage.py --run-dir data/interim/synthetic_run \
        --comparison-run-dir data/interim/synthetic_run_comparison

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

#: The counter-instrument's own impossible pair. A second opinion has to be a
#: different model, and a reader of either artefact has to be able to see at a
#: glance that neither of these was ever asked anything.
COMPARISON_RUN_ID = "0000-00-00-synthetic-comparison"
COMPARISON_MODEL = "synthetic-comparison"

#: Fixed, so that rebuilding the fixture twice produces byte-identical files and
#: a contract diff means a real shape change. A real run stamps the day it ran.
ANNOTATED_AT = "2000-01-01"
TIMESTAMP = "2000-01-01T00:00:00Z"

OUTPUT = INTERIM / "synthetic_run"
COMPARISON_OUTPUT = INTERIM / "synthetic_run_comparison"
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
POSITIONS: tuple[tuple[str, float], ...] = (
    ("asserts", 0.60),
    ("reports_without_position", 0.12),
    ("rejects", 0.10),
    ("no_position", 0.08),
    ("conditional", 0.07),
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

#: Annotation schema 3's own fields, as (label, weight) pairs. `concrete_case`
#: is not among them: it is not drawn at all but derived from the position,
#: because the schema locks the two together — `concrete_case: no` if and only
#: if `speaker_position: no_position` — and a fixture that drew them
#: independently would spend most of its rows being refused.
REFERENT_SOURCES: tuple[tuple[str, float], ...] = (
    ("passage", 0.70),
    ("speech", 0.22),
    ("header", 0.08),
)
OWN_STATE: tuple[tuple[str, float], ...] = (
    ("no", 0.72),
    ("not_applicable", 0.24),
    ("yes", 0.04),
)
SALIENCE: tuple[tuple[str, float], ...] = (("substantive", 0.62), ("passing", 0.38))

#: One fabricated free-text value per field, signposted rather than plausible.
#: A fixture that invented an actor's name would read as a finding in a diff.
ACCUSED = "[synthetic fixture] an actor the passage names"
VICTIM = "[synthetic fixture] a group the passage names"
RATIONALE = "[synthetic fixture] not a rationale; the fields have a shape."

#: How often the second model is made to differ, per decision. Redrawn rather
#: than randomised: a counter-instrument that agreed nowhere would exercise the
#: disagreement paths and nothing else, and one that agreed everywhere would
#: leave `contested` empty in the contract. The numbers are a guess at a
#: plausible spread between two competent models and nothing more; a redraw can
#: land on the label it replaced, so the observed disagreement is a little lower
#: than each rate.
FLIP: dict[str, float] = {
    "verdict": 0.03,
    "quotation": 0.12,
    "speaker_position": 0.15,
    "function": 0.14,
    "referent": 0.10,
}

#: Share of occurrences the second run never reached at all, so that the
#: partial-coverage path — `overlap` below `occurrences_annotated`, and rows whose
#: `contested` is empty because nobody looked rather than because two models
#: agreed — has something in it.
OMITTED = 0.02


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


def quote_for(verdict: str, sentence: str, draw: float) -> str:
    """The evidence quotation, and the one verdict that may not miss with it.

    A share of rows quote something the speech does not contain, so that
    `evidence_valid` is false somewhere and the eligibility gate has something to
    bite on. A false positive is exempt: `lib.llm.validate_row` requires it to
    carry a located span, because "this match is not the word being used" is a
    claim about a passage and is unreadable without the passage. The fixture
    obeys the codebook rather than working around it — and this is where it
    stopped obeying it, on the first run after that rule landed.
    """
    if verdict == "false_positive":
        return sentence
    return BAD_QUOTE if draw < BAD_EVIDENCE else sentence


def cascade(verdict: str, quote: str, confidence: str) -> dict:
    """The labels a verdict other than `true_positive` fixes on its own.

    `lib.llm.check_labels` allows a false positive no discourse labels but
    `not_applicable`, and reserves that value for false positives; a model that
    has called the passage illegible abstains across the board rather than
    guessing four labels for it. Factored out because both fabricated runs obey
    the same cascade and neither may drift from it.
    """
    if verdict == "false_positive":
        return {
            "quotation": "not_applicable",
            "concrete_case": "not_applicable",
            "speaker_position": "not_applicable",
            "function": ("not_applicable",),
            "referent": "not_applicable",
            "proposed_referent": "",
            "referent_source": "not_applicable",
            "accused_actor": "",
            "victim_group": "",
            "own_state_accused": "not_applicable",
            "salience": "not_applicable",
            "evidence_quote": quote,
            "rationale": RATIONALE,
            "confidence": confidence,
        }
    return {
        "quotation": "unclear",
        "concrete_case": "unclear",
        "speaker_position": "unclear",
        "function": ("unclear",),
        "referent": "unclear",
        "proposed_referent": "",
        "referent_source": "not_applicable",
        "accused_actor": "",
        "victim_group": "",
        "own_state_accused": "not_applicable",
        "salience": "not_applicable",
        "evidence_quote": quote,
        "rationale": RATIONALE,
        "confidence": "low",
    }


def discourse_labels(
    occurrence_id: str, cases: Sequence[tuple[str, float]], prefix: str = ""
) -> dict:
    """The five fields a true positive carries, drawn from one salted stream.

    `prefix` is what makes a second model a second model: the same occurrence
    identity through a different salt is an independent draw, so the comparison
    run's alternative reading of a passage is reproducible without being the
    first run's reading. An empty prefix is the published run's own draw and must
    stay that way — changing it would rewrite every label in the fixture and turn
    an unrelated commit into a whole-contract diff.
    """
    draw = stream(occurrence_id, f"{prefix}referent")
    if draw < UNCLEAR_REFERENT:
        referent, proposed = "unclear", ""
    elif draw < UNCLEAR_REFERENT + OTHER_REFERENT:
        referent, proposed = "other", PROPOSED
    else:
        referent, proposed = pick(stream(occurrence_id, f"{prefix}case"), cases), ""
    position = pick(stream(occurrence_id, f"{prefix}speaker_position"), POSITIONS)
    abstract = position == "no_position"
    accused = stream(occurrence_id, f"{prefix}accused") < 0.55 and not abstract
    return {
        "quotation": pick(stream(occurrence_id, f"{prefix}quotation"), QUOTATIONS),
        # Derived, never drawn: the schema locks the two together.
        "concrete_case": "no" if abstract else "yes",
        "speaker_position": position,
        "function": tuple(
            pick(stream(occurrence_id, f"{prefix}function"), FUNCTIONS).split("|")
        ),
        "referent": referent,
        "proposed_referent": proposed,
        "referent_source": (
            "not_applicable"
            if referent == "unclear"
            else pick(stream(occurrence_id, f"{prefix}source"), REFERENT_SOURCES)
        ),
        "accused_actor": ACCUSED if accused else "",
        "victim_group": (
            VICTIM if stream(occurrence_id, f"{prefix}victim") < 0.45 and not abstract else ""
        ),
        "own_state_accused": (
            "not_applicable"
            if not accused
            else pick(stream(occurrence_id, f"{prefix}own"), OWN_STATE)
        ),
        "salience": (
            "passing" if abstract else pick(stream(occurrence_id, f"{prefix}salience"), SALIENCE)
        ),
    }


def labels_for(occurrence_id: str, sentence: str, cases: Sequence[tuple[str, float]]) -> dict:
    """One occurrence's fabricated labels, obeying the codebook's own cascade.

    The rules `lib.llm.check_labels` enforces are followed here rather than
    worked around: a false positive carries `not_applicable` in all four
    discourse fields and nothing else does, `other` carries a proposed referent
    and nothing else does, and `uncertain` abstains across the board rather than
    guessing labels for a passage it has just said is illegible.
    """
    verdict = pick(stream(occurrence_id, "verdict"), VERDICTS)
    quote = quote_for(verdict, sentence, stream(occurrence_id, "evidence"))
    confidence = pick(stream(occurrence_id, "confidence"), CONFIDENCE)
    if verdict != "true_positive":
        return {"verdict": verdict, **cascade(verdict, quote, confidence)}
    return {
        "verdict": verdict,
        **discourse_labels(occurrence_id, cases),
        "evidence_quote": quote,
        "rationale": RATIONALE,
        "confidence": confidence,
    }


def comparison_labels_for(
    occurrence_id: str, sentence: str, cases: Sequence[tuple[str, float]]
) -> dict:
    """A second model's labels: the first's, with some decisions redrawn.

    Not an independent draw. Two models given one prompt and one passage agree
    about most of it, and a fixture whose two runs agreed at chance would put a
    kappa near zero into the contract and make the view built against it look
    like a bug. Each decision is kept or replaced by :data:`FLIP`, deterministically
    per occurrence, so every compared field carries both agreements and
    disagreements — which is the post-condition :func:`check_comparison` asserts
    before anything is written.

    The cascade is obeyed on both sides. Where the two runs disagree about the
    *verdict*, the second one's discourse labels are whatever its own verdict
    fixes them to, and where the first run refused the match outright it has no
    discourse labels to keep, so the second draws its own.
    """
    first = labels_for(occurrence_id, sentence, cases)
    verdict = (
        pick(stream(occurrence_id, "alt-verdict"), VERDICTS)
        if stream(occurrence_id, "flip-verdict") < FLIP["verdict"]
        else first["verdict"]
    )
    # Its own draw, so that `evidence_valid` differs between the runs somewhere:
    # two models quote different sentences, and one of them can miss.
    quote = quote_for(verdict, sentence, stream(occurrence_id, "alt-evidence"))
    confidence = pick(stream(occurrence_id, "alt-confidence"), CONFIDENCE)
    if verdict != "true_positive":
        return {"verdict": verdict, **cascade(verdict, quote, confidence)}

    kept = first if first["verdict"] == "true_positive" else None
    other = discourse_labels(occurrence_id, cases, prefix="alt-")

    def decide(field: str) -> object:
        if kept is None or stream(occurrence_id, f"flip-{field}") < FLIP[field]:
            return other[field]
        return kept[field]

    referent = decide("referent")
    position = decide("speaker_position")
    # The lock travels with the decision it belongs to: whichever run's position
    # this row kept, `concrete_case` is that run's, so a redrawn position cannot
    # leave the pair contradicting itself.
    source = kept if kept is not None and position == kept["speaker_position"] else other
    return {
        "verdict": verdict,
        "quotation": decide("quotation"),
        "concrete_case": "no" if position == "no_position" else "yes",
        "speaker_position": position,
        "function": decide("function"),
        "referent": referent,
        # Tied to the referent it justifies rather than decided separately:
        # `other` requires a proposal and nothing else may carry one.
        "proposed_referent": PROPOSED if referent == "other" else "",
        "referent_source": (
            "not_applicable" if referent == "unclear" else source["referent_source"]
        ),
        "accused_actor": "" if position == "no_position" else source["accused_actor"],
        "victim_group": "" if position == "no_position" else source["victim_group"],
        "own_state_accused": (
            "not_applicable"
            if position == "no_position" or not source["accused_actor"]
            else source["own_state_accused"]
        ),
        "salience": "passing" if position == "no_position" else source["salience"],
        "evidence_quote": quote,
        "rationale": RATIONALE,
        "confidence": confidence,
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


def check_comparison(first: pd.DataFrame, second: pd.DataFrame) -> list[str]:
    """The post-conditions that make the second run a usable counter-instrument.

    Every compared field must carry both an agreement and a disagreement over the
    overlap, and the coverage must be partial without being empty. A fixture that
    agreed everywhere would declare `contested` as an always-empty array and an
    `alt` that is always null; one that agreed nowhere would never write a row on
    the agreeing side of the same shapes. Either way the contract would be
    narrower than the real pair of runs needs, and the failure would arrive
    months later attached to the wrong change.
    """
    problems: list[str] = []
    left = first.set_index("occurrence_id")
    right = second.set_index("occurrence_id")
    shared = left.index.intersection(right.index)
    if not len(shared):
        return ["the two runs annotate no occurrence in common"]
    for field in ("verdict", "quotation", "speaker_position", "function", "referent"):
        before, after = left.loc[shared, field], right.loc[shared, field]
        if field == "function":
            # Set equality, as `lib.usage` compares it: the pipe order carries no
            # meaning and must not be counted as a disagreement.
            same = [
                set(x.split("|")) == set(y.split("|"))
                for x, y in zip(before, after, strict=True)
            ]
        else:
            same = [x == y for x, y in zip(before, after, strict=True)]
        if all(same) or not any(same):
            problems.append(
                f"{field} would be single-typed: {sum(same)} of {len(same)} "
                "overlapping occurrences agree"
            )
    if len(right) >= len(left):
        problems.append(
            f"the second run omits nothing ({len(right):,} rows against {len(left):,}), "
            "so the partial-coverage path would go undeclared"
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
    referent_list = audit.read_referent_list(REFERENTS)
    referents = referent_list.current
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
        referents_version=str(referent_list.version),
        term=TERM,
        annotated_at=ANNOTATED_AT,
    )
    # The same prompt hash and the same lexicon: 15 refuses a comparison made
    # against either a different questionnaire or a different population, and a
    # fixture that could not be compared would declare nothing. A different
    # reasoning effort, because it is the one thing about the second instrument
    # that may honestly differ and the block publishes it.
    comparison_meta = llm.RunMeta(
        run_id=COMPARISON_RUN_ID,
        model=COMPARISON_MODEL,
        prompt_version=pack.version,
        prompt_sha256=pack.sha256,
        reasoning_effort="medium",
        lexicon_version=str(lex.version),
        referents_version=str(referent_list.version),
        term=TERM,
        annotated_at=ANNOTATED_AT,
    )
    rows: list[dict[str, object]] = []
    second: list[dict[str, object]] = []
    order = list(grouped)[:limit] if limit is not None else list(grouped)
    for index in order:
        items = grouped[index]
        body = str(bodies.loc[index])
        spans = sentence_spans(body)
        sentences = {
            occurrence.ordinal: sentence_at(body, occurrence.start, spans)
            for occurrence in items
        }
        labels = {
            occurrence.ordinal: labels_for(
                occurrence.occurrence_id, sentences[occurrence.ordinal], cases
            )
            for occurrence in items
        }
        annotated = llm.annotation_rows(items, body, labels, meta)
        for row in annotated:
            llm.validate_row(row, referents)
        rows.extend(annotated)

        reached = [
            occurrence
            for occurrence in items
            if stream(occurrence.occurrence_id, "omit") >= OMITTED
        ]
        if reached:
            alternatives = {
                occurrence.ordinal: comparison_labels_for(
                    occurrence.occurrence_id, sentences[occurrence.ordinal], cases
                )
                for occurrence in reached
            }
            compared = llm.annotation_rows(reached, body, alternatives, comparison_meta)
            for row in compared:
                llm.validate_row(row, referents)
            second.extend(compared)
    console.info(f"{len(rows):,} rows, every one validated by lib.llm.validate_row")
    console.info(
        f"{len(second):,} comparison rows, {len(rows) - len(second):,} occurrences the "
        "second run never reached"
    )

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
    comparison_frame = pd.DataFrame(second)
    if problems := check_comparison(pd.DataFrame(rows), comparison_frame):
        console.fail(
            "the second run would not exercise the comparison shapes",
            [*problems, "adjust FLIP and OMITTED above rather than the contract"],
        )
    eligible = frame.loc[frame["verdict"].eq("true_positive") & frame["evidence_valid"]]
    # Reported rather than asserted: `check_comparison` has already refused a
    # fixture on which this would be zero or complete, and the number is here so
    # that whoever rebuilds the fixture sees how contested the pair came out.
    published = {str(row["occurrence_id"]): row for row in rows}
    contested = sum(
        1
        for row in second
        if any(
            set(str(published[str(row["occurrence_id"])][field]).split("|"))
            != set(str(row[field]).split("|"))
            if field == "function"
            else published[str(row["occurrence_id"])][field] != row[field]
            for field in ("verdict", "quotation", "speaker_position", "function", "referent")
        )
    )
    console.table(
        [
            ("occurrences", f"{len(frame):,}"),
            ("true positives", f"{int(frame['verdict'].eq('true_positive').sum()):,}"),
            ("evidence not located", f"{int((~frame['evidence_valid']).sum()):,}"),
            ("eligible", f"{len(eligible):,}"),
            ("referents used", f"{frame['referent'].nunique()}"),
            ("speakers", f"{frame['country_org'].nunique()}"),
            (
                "rejects",
                f"{int(frame['speaker_position'].eq('rejects').sum()):,}",
            ),
            ("compared", f"{len(comparison_frame):,}"),
            ("contested", f"{contested:,} of {len(comparison_frame):,}"),
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

    COMPARISON_OUTPUT.mkdir(parents=True, exist_ok=True)
    comparison_annotations = COMPARISON_OUTPUT / "annotations.jsonl"
    comparison_annotations.unlink(missing_ok=True)
    llm.append_rows(comparison_annotations, second)
    # The published run's manifest with the second instrument's identity in it,
    # and one honest difference: a comparison run may reach fewer speeches, so
    # `requests` counts the ones it actually contributed rows from.
    reached_speeches = len({str(row["filename"]) for row in second})
    artifacts.atomic_write_json(
        COMPARISON_OUTPUT / "manifest.json",
        {
            **manifest,
            "run_id": COMPARISON_RUN_ID,
            "model": COMPARISON_MODEL,
            "reasoning_effort": "medium",
            "requests": {
                "planned": reached_speeches,
                "submitted": reached_speeches,
                "returned": reached_speeches,
                "complete": reached_speeches,
            },
            "occurrences": {"planned": len(second), "written": len(second)},
            "evidence_invalid": int((~comparison_frame["evidence_valid"]).sum()),
        },
        indent=1,
    )
    console.info(f"wrote {rel(comparison_annotations)} and manifest.json")

    console.warn(
        f"both runs are fabricated: {RUN_ID} / {MODEL} and {COMPARISON_RUN_ID} / "
        f"{COMPARISON_MODEL}. Never put either in model_annotations/genocide/"
        "current_run.txt or comparison_run.txt."
    )
    console.info(
        f"aggregate them with: python scripts/15_usage.py --run-dir {rel(OUTPUT)} "
        f"--comparison-run-dir {rel(COMPARISON_OUTPUT)}"
    )


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
