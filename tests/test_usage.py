"""The usage aggregation, checked on constructed rows.

`15_usage.py` reads a run that costs money to produce and a corpus that CI does
not have, so everything it decides lives in `lib.usage` and is asserted here
against rows written by hand. Two kinds of assertion:

- **Recounts.** The aggregation is compared against a brute-force count of the
  same fabricated rows, written in plain loops. A groupby that agrees with a
  loop is a groupby that means what its column names say.
- **Golden numbers.** Every agreement statistic is checked against a value
  computed by hand in the comment above it. The formulas are in the module's
  docstrings; these are the arithmetic, so that a rewrite of either has something
  to fail against.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from lib import audit, lexicon, usage

ROOT = Path(__file__).resolve().parents[1]


def _step(name: str, module_name: str):
    """Load a numbered script as a module. A script cannot be named `15_…`.

    Registered in `sys.modules` before it is executed, and removed again if it
    raises, for uniformity with the other step loaders in this suite: a step
    that grows a frozen dataclass needs it — `dataclasses` resolves a field's
    annotations through `sys.modules[cls.__module__]` — and one that does not
    loses nothing by it.
    """
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


step = _step("15_usage.py", "usage_step")

# --- Fixtures ---------------------------------------------------------------

ROW = {
    "occurrence_id": "",
    "country_org": "Rwanda",
    "iso3": "RWA",
    "entity_type": "state",
    "speaker_group": "Non-member state",
    "verdict": "true_positive",
    "quotation": "not_quoted",
    "stance": "asserts",
    "function": "accusation_or_qualification",
    "referent": "rwanda_1994",
    "proposed_referent": "",
    "confidence": "high",
    "evidence_valid": True,
}

REFERENTS = [
    {"id": "rwanda_1994", "label": "Rwanda 1994", "kind": "case", "iso3": "RWA", "years": "1994"},
    {"id": "holocaust", "label": "The Holocaust", "kind": "historical", "iso3": "", "years": ""},
    {"id": "gaza", "label": "Gaza since 2023", "kind": "case", "iso3": "PSE", "years": "2023-"},
    {"id": "other", "label": "Other", "kind": "reserved", "iso3": "", "years": ""},
    {"id": "unclear", "label": "Unclear", "kind": "reserved", "iso3": "", "years": ""},
    {
        "id": "not_applicable",
        "label": "Not applicable",
        "kind": "reserved",
        "iso3": "",
        "years": "",
    },
]


def rows(*changes: dict[str, object]) -> pd.DataFrame:
    """A joined model frame, one row per argument, with an id per position."""
    return pd.DataFrame(
        [
            {**ROW, **change, "occurrence_id": change.get("occurrence_id", f"occ-{number:03d}")}
            for number, change in enumerate(changes)
        ]
    )


def repeat(count: int, **change: object) -> list[dict[str, object]]:
    return [dict(change) for _ in range(count)]


def false_positive(**change: object) -> dict[str, object]:
    """A false positive with the codebook's cascade, as `lib.llm` enforces it."""
    return {
        "verdict": "false_positive",
        "quotation": "not_applicable",
        "stance": "not_applicable",
        "function": "not_applicable",
        "referent": "not_applicable",
        **change,
    }


# --- Eligible and assigned --------------------------------------------------


def test_eligible_needs_both_a_true_positive_and_located_evidence() -> None:
    frame = rows(
        {},
        {"verdict": "uncertain", "referent": "unclear", "stance": "unclear"},
        false_positive(),
        {"evidence_valid": False},
    )
    assert usage.eligible_mask(frame).tolist() == [True, False, False, False]


def test_other_counts_as_assigned_and_the_two_reserved_ids_do_not() -> None:
    frame = rows(
        {"referent": "rwanda_1994"},
        {"referent": "other", "proposed_referent": "a case not yet controlled"},
        {"referent": "unclear"},
        false_positive(),
    )
    assert usage.assigned_mask(frame).tolist() == [True, True, False, False]


def test_an_eligible_row_with_no_referent_still_carries_its_stance() -> None:
    # The denial figure is cut from eligible rows, not from assigned ones: a
    # speaker can reject the characterisation in a passage that names no case.
    frame = rows({"referent": "unclear", "stance": "rejects_or_denies"})
    assert usage.eligible_mask(frame).tolist() == [True]
    assert usage.assigned_mask(frame).tolist() == [False]
    assert usage.stance_rows(frame, ["Rwanda"], minimum=1)[0]["stances"][
        "rejects_or_denies"
    ] == 1


def test_the_funnel_counts_what_each_gate_removes() -> None:
    frame = rows(
        *repeat(5, stance="asserts"),
        *repeat(2, verdict="uncertain", quotation="unclear", stance="unclear",
                function="unclear", referent="unclear"),
        false_positive(),
        {"evidence_valid": False},
        {"referent": "unclear"},
        {"referent": "other", "proposed_referent": "somewhere"},
    )
    counts = usage.funnel(frame)
    assert counts["annotated"] == 11
    assert (counts["false_positive"], counts["uncertain"]) == (1, 2)
    assert counts["evidence_invalid"] == 1
    # 11 rows, minus one false positive, two uncertain and one unlocated: 7.
    assert counts["eligible"] == 7
    # Counted over every annotated row rather than over the eligible ones: the
    # two `uncertain` verdicts abstain on the referent too, and the abstention
    # figure is about the run and not about what survived the gates.
    assert counts["referent_unclear"] == 3
    # Seven eligible, one of which abstains on the referent. `other` is assigned.
    assert counts["assigned"] == 6
    assert counts["referent_other"] == 1


# --- Stance blocks ----------------------------------------------------------


def test_every_stance_key_is_written_even_when_nothing_used_it() -> None:
    counts = usage.stance_counts(rows({"stance": "asserts"}))
    assert list(counts) == list(usage.STANCES)
    assert set(counts) == set(audit.STANCES)
    assert counts["asserts"] == 1
    assert all(counts[key] == 0 for key in usage.STANCES if key != "asserts")


def test_an_actor_with_no_eligible_rows_still_gets_seven_zeroes() -> None:
    frame = rows(false_positive(country_org="Chad"), {"country_org": "Rwanda"})
    written = {row["actor"]: row for row in usage.stance_rows(frame, ["Rwanda", "Chad"])}
    assert written["Chad"]["eligible"] == 0
    assert written["Chad"]["stances"] == dict.fromkeys(usage.STANCES, 0)
    assert written["Chad"]["share_rejects"] is None


# --- Withholding ------------------------------------------------------------


@pytest.mark.parametrize(
    ("eligible", "sufficient"),
    [(19, False), (20, True), (21, True)],
)
def test_a_share_is_withheld_below_the_minimum_and_written_at_it(
    eligible: int, sufficient: bool
) -> None:
    frame = rows(*repeat(eligible, stance="rejects_or_denies"))
    written = usage.stance_rows(frame, ["Rwanda"])[0]
    assert usage.MINIMUM_OCCURRENCES == 20
    assert written["eligible"] == eligible
    assert written["sufficient"] is sufficient
    # The count is a fact and is always written; the share is an estimate.
    assert written["stances"]["rejects_or_denies"] == eligible
    if sufficient:
        assert written["share_rejects"] == 1.0
    else:
        assert written["share_rejects"] is None


def test_the_two_sufficiency_flags_guard_different_denominators() -> None:
    # Twenty-one eligible occurrences, of which only two name a case: the stance
    # composition may be shown, the matrix row may not.
    frame = rows(*repeat(19, referent="unclear"), *repeat(2, referent="gaza"))
    actor = usage.actor_rows(frame)[0]
    stance = usage.stance_rows(frame, ["Rwanda"])[0]
    assert (actor["eligible"], actor["assigned"], actor["sufficient"]) == (21, 2, False)
    assert (stance["eligible"], stance["sufficient"]) == (21, True)


# --- The aggregation against a brute-force recount --------------------------


def recount(frame: pd.DataFrame) -> dict[tuple[str, str], int]:
    """The matrix, counted in a loop rather than by a groupby."""
    cells: dict[tuple[str, str], int] = {}
    for row in frame.to_dict(orient="records"):
        if row["verdict"] != "true_positive" or not row["evidence_valid"]:
            continue
        if row["referent"] in ("unclear", "not_applicable"):
            continue
        key = (row["country_org"], row["referent"])
        cells[key] = cells.get(key, 0) + 1
    return cells


def mixed() -> pd.DataFrame:
    return rows(
        *repeat(4, country_org="Rwanda", referent="rwanda_1994"),
        *repeat(2, country_org="Rwanda", referent="rwanda_1994",
                stance="rejects_or_denies"),
        *repeat(3, country_org="Rwanda", referent="holocaust"),
        {"country_org": "Rwanda", "referent": "unclear"},
        false_positive(country_org="Rwanda"),
        *repeat(5, country_org="Israel", iso3="ISR", referent="gaza"),
        *repeat(2, country_org="European Union", iso3=None, entity_type="igo",
                speaker_group="Non-state", referent="gaza"),
        {"country_org": "European Union", "iso3": None, "entity_type": "igo",
         "speaker_group": "Non-state", "referent": "other",
         "proposed_referent": "a case not yet controlled"},
    )


def test_the_matrix_reconciles_against_a_recount_of_the_same_rows() -> None:
    frame = mixed()
    built = {(cell["actor"], cell["referent"]): cell["count"] for cell in
             usage.aggregate(frame, REFERENTS)["matrix"]}
    assert built == recount(frame)
    assert sum(built.values()) == int(usage.assigned_mask(frame).sum())


def test_every_cell_carries_a_stance_breakdown_that_sums_to_its_count() -> None:
    for cell in usage.aggregate(mixed(), REFERENTS)["matrix"]:
        assert sum(cell["stances"].values()) == cell["count"]
        assert list(cell["stances"]) == list(usage.STANCES)


def test_each_referent_total_equals_its_column_of_the_matrix() -> None:
    blocks = usage.aggregate(mixed(), REFERENTS)
    for referent in blocks["referents"]:
        column = sum(
            cell["count"] for cell in blocks["matrix"] if cell["referent"] == referent["id"]
        )
        assert referent["occurrences"] == column


def test_an_actor_row_counts_every_annotated_occurrence_not_only_the_countable() -> None:
    actors = {row["country_org"]: row for row in usage.aggregate(mixed(), REFERENTS)["actors"]}
    # Rwanda: 10 usable rows plus one false positive is 11 annotated; the false
    # positive leaves 10 eligible; the one `unclear` referent leaves 9 assigned.
    assert actors["Rwanda"]["occurrences"] == 11
    assert actors["Rwanda"]["eligible"] == 10
    assert actors["Rwanda"]["assigned"] == 9


def test_a_speaker_with_no_code_keeps_a_null_rather_than_an_empty_string() -> None:
    actors = {row["country_org"]: row for row in usage.aggregate(mixed(), REFERENTS)["actors"]}
    assert actors["European Union"]["iso3"] is None
    assert actors["Israel"]["iso3"] == "ISR"


def test_the_group_is_the_modal_one_with_ties_broken_lexically() -> None:
    frame = rows(
        *repeat(3, speaker_group="E10"),
        *repeat(2, speaker_group="P5"),
    )
    assert usage.actor_rows(frame)[0]["group"] == "E10"
    tied = rows(*repeat(2, speaker_group="P5"), *repeat(2, speaker_group="E10"))
    assert usage.actor_rows(tied)[0]["group"] == "E10"


# --- Sort orders ------------------------------------------------------------


def test_actors_are_ranked_by_assigned_then_by_name() -> None:
    frame = rows(
        *repeat(3, country_org="Zimbabwe"),
        *repeat(2, country_org="Belgium"),
        *repeat(2, country_org="Angola"),
    )
    assert [row["country_org"] for row in usage.actor_rows(frame)] == [
        "Zimbabwe",
        "Angola",
        "Belgium",
    ]


def test_referents_are_ranked_by_occurrences_then_by_identifier() -> None:
    frame = rows(
        *repeat(3, referent="gaza"),
        *repeat(1, referent="holocaust"),
        *repeat(1, referent="rwanda_1994"),
    )
    ranked = usage.referent_rows(frame, REFERENTS)
    assert [row["id"] for row in ranked] == [
        "gaza",
        "holocaust",
        "rwanda_1994",
        "not_applicable",
        "other",
        "unclear",
    ]
    # The reserved identifiers are written and are always zero.
    assert [row["occurrences"] for row in ranked] == [3, 1, 1, 0, 0, 0]


def test_the_matrix_follows_the_actor_order_then_the_referent_order() -> None:
    blocks = usage.aggregate(mixed(), REFERENTS)
    actor_rank = {row["country_org"]: n for n, row in enumerate(blocks["actors"])}
    referent_rank = {row["id"]: n for n, row in enumerate(blocks["referents"])}
    keys = [
        (actor_rank[cell["actor"]], referent_rank[cell["referent"]])
        for cell in blocks["matrix"]
    ]
    assert keys == sorted(keys)


def test_the_stance_block_is_written_in_the_actor_order() -> None:
    blocks = usage.aggregate(mixed(), REFERENTS)
    assert [row["actor"] for row in blocks["stance_by_actor"]] == [
        row["country_org"] for row in blocks["actors"]
    ]


# --- Diffusion --------------------------------------------------------------

ORDER = ["rwanda_1994", "gaza", "holocaust", "other"]


def dated(date: object, line_id: str, **change: object) -> dict[str, object]:
    """One row of a diffusion frame: a date and a KWIC line id beside the labels."""
    return {"date": date, "line_id": line_id, **change}


def curves(frame: pd.DataFrame, order: list[str] | None = None) -> dict[str, list[dict]]:
    """The diffusion block keyed by referent, for assertions that read."""
    return {
        entry["id"]: entry["events"]
        for entry in usage.diffusion_rows(frame, ORDER if order is None else order)
    }


def test_each_milestone_is_the_first_row_that_reaches_it() -> None:
    frame = rows(
        dated("1994-04-21", "a#1", stance="attributes_or_reports"),
        dated("1994-05-16", "b#1", stance="asserts"),
        dated("1994-06-08", "c#1", stance="asserts"),
        dated("1995-01-10", "d#1", stance="rejects_or_denies"),
        dated("1996-02-02", "e#1", stance="rejects_or_denies"),
    )
    events = curves(frame)["rwanda_1994"]
    assert [(event["milestone"], event["id"]) for event in events] == [
        ("mention", "a#1"),
        ("asserts", "b#1"),
        ("rejects_or_denies", "d#1"),
    ]
    # The mention keeps the stance of the row it was drawn from, which is not the
    # milestone: this delegation reported the characterisation before making it.
    assert events[0]["stance"] == "attributes_or_reports"
    assert events[0]["date"] == "1994-04-21"
    assert events[0]["actor"] == "Rwanda"
    assert set(events[0]) == {"date", "actor", "milestone", "stance", "id"}


def test_one_occurrence_can_be_both_the_first_mention_and_the_first_assertion() -> None:
    frame = rows(dated("1994-04-21", "a#1", stance="asserts"))
    events = curves(frame)["rwanda_1994"]
    assert [event["milestone"] for event in events] == ["mention", "asserts"]
    # Two events, one occurrence: both carry the same date and the same line id,
    # because the curves they feed are counted separately.
    assert {event["id"] for event in events} == {"a#1"}
    assert {event["stance"] for event in events} == {"asserts"}


def test_a_first_rejection_is_recorded_even_when_the_delegation_asserted_first() -> None:
    frame = rows(
        dated("1994-04-21", "a#1", stance="asserts"),
        dated("1994-05-16", "b#1", stance="rejects_or_denies"),
    )
    events = {event["milestone"]: event for event in curves(frame)["rwanda_1994"]}
    assert events["mention"]["id"] == "a#1"
    assert events["asserts"]["id"] == "a#1"
    assert events["rejects_or_denies"]["id"] == "b#1"
    assert events["rejects_or_denies"]["date"] == "1994-05-16"


def test_a_same_day_tie_is_broken_by_the_line_id() -> None:
    # Written in the reverse of the answer, so a first-row-wins implementation
    # that never sorted would fail here.
    frame = rows(
        dated("1994-04-21", "b#2", stance="asserts"),
        dated("1994-04-21", "a#1", stance="asserts"),
    )
    assert curves(frame)["rwanda_1994"][0]["id"] == "a#1"


def test_a_pair_is_per_referent_and_per_actor() -> None:
    frame = rows(
        dated("1994-04-21", "a#1", country_org="Rwanda", referent="rwanda_1994"),
        dated("1994-05-16", "b#1", country_org="Chad", referent="rwanda_1994"),
        dated("1993-01-01", "c#1", country_org="Rwanda", referent="holocaust"),
    )
    built = curves(frame)
    assert {event["actor"] for event in built["rwanda_1994"]} == {"Rwanda", "Chad"}
    # Rwanda's first mention of the Holocaust is earlier than its first mention
    # of 1994, and neither displaces the other: the pair is the unit.
    assert [event["date"] for event in built["holocaust"]] == ["1993-01-01"] * 2


def test_referents_follow_the_order_they_are_given() -> None:
    frame = rows(
        dated("1994-04-21", "a#1", referent="holocaust"),
        dated("1994-05-16", "b#1", referent="rwanda_1994"),
        dated("1994-06-08", "c#1", referent="gaza"),
    )
    given = ["rwanda_1994", "gaza", "holocaust"]
    assert [entry["id"] for entry in usage.diffusion_rows(frame, given)] == given
    reversed_order = list(reversed(given))
    assert [
        entry["id"] for entry in usage.diffusion_rows(frame, reversed_order)
    ] == reversed_order
    # A referent the order does not name is sorted last rather than dropped.
    assert [entry["id"] for entry in usage.diffusion_rows(frame, ["gaza"])] == [
        "gaza",
        "holocaust",
        "rwanda_1994",
    ]


def test_events_are_sorted_by_date_then_line_id_then_milestone() -> None:
    frame = rows(
        dated("1994-06-08", "c#1", country_org="Chad", stance="rejects_or_denies"),
        dated("1994-04-21", "a#1", country_org="Rwanda", stance="asserts"),
        dated("1994-04-21", "a#2", country_org="Angola", stance="asserts"),
    )
    events = curves(frame)["rwanda_1994"]
    assert [(event["date"], event["id"], event["milestone"]) for event in events] == [
        ("1994-04-21", "a#1", "mention"),
        ("1994-04-21", "a#1", "asserts"),
        ("1994-04-21", "a#2", "mention"),
        ("1994-04-21", "a#2", "asserts"),
        ("1994-06-08", "c#1", "mention"),
        ("1994-06-08", "c#1", "rejects_or_denies"),
    ]


def test_only_assigned_rows_can_carry_a_first_event() -> None:
    frame = rows(
        dated("1993-01-01", "a#1", **false_positive()),
        dated("1993-02-02", "b#1", referent="unclear", stance="rejects_or_denies"),
        dated("1993-03-03", "c#1", evidence_valid=False),
        dated("1994-04-21", "d#1", stance="asserts"),
        dated("1994-05-16", "e#1", referent="other",
              proposed_referent="a case not yet controlled"),
    )
    built = curves(frame)
    # The three ineligible or unassigned rows are earlier than every kept one, so
    # a leak would show up as a first mention rather than as an extra event.
    assert [event["id"] for event in built["rwanda_1994"]] == ["d#1", "d#1"]
    # `other` is assigned everywhere else in this module, and here too.
    assert [event["id"] for event in built["other"]] == ["e#1", "e#1"]
    assert set(built) == {"rwanda_1994", "other"}


def test_a_frame_with_nothing_assigned_yields_no_referents() -> None:
    # No rows at all, and rows none of which are assigned: an empty list either
    # way, never a referent carrying an empty `events` array.
    assert usage.diffusion_rows(rows(dated("1994-04-21", "a#1")).iloc[:0], ORDER) == []
    frame = rows(dated("1994-04-21", "a#1", referent="unclear"))
    assert usage.diffusion_rows(frame, ORDER) == []


def test_the_diffusion_block_refuses_a_frame_that_is_missing_a_column() -> None:
    frame = rows(dated("1994-04-21", "a#1"))
    with pytest.raises(KeyError, match="date"):
        usage.diffusion_rows(frame.drop(columns=["date"]), ORDER)
    with pytest.raises(KeyError, match="line_id"):
        usage.diffusion_rows(frame.drop(columns=["line_id"]), ORDER)


def test_an_assigned_row_with_no_date_is_refused_rather_than_repaired() -> None:
    frame = rows(
        dated("1994-04-21", "a#1"),
        dated("", "b#1"),
        dated("   ", "c#1"),
    )
    with pytest.raises(ValueError, match="b#1, c#1"):
        usage.diffusion_rows(frame, ORDER)
    # An undated row that would not have been counted anyway is not a refusal.
    tolerated = rows(dated("1994-04-21", "a#1"), dated("", "b#1", referent="unclear"))
    assert curves(tolerated)["rwanda_1994"][0]["id"] == "a#1"


def test_a_timestamp_is_published_as_the_calendar_date_it_names() -> None:
    # The normalised corpus holds `date` as a datetime64, so a joined row carries
    # a Timestamp; the artefact publishes the ISO date and never a midnight.
    frame = rows(dated(pd.Timestamp("1994-04-21"), "a#1"))
    assert curves(frame)["rwanda_1994"][0]["date"] == "1994-04-21"
    undated = rows(dated(pd.NaT, "a#1"))
    with pytest.raises(ValueError, match="a#1"):
        usage.diffusion_rows(undated, ORDER)


# --- Agreement --------------------------------------------------------------

# Ten paired judgements, six `yes` on the left and five on the right:
#
#   left   yes yes yes yes yes yes  no  no  no  no
#   right  yes yes yes yes  no  no yes  no  no  no
#
#   p_o    = 7/10                                  = 0.70
#   p_e    = (6/10)(5/10) + (4/10)(5/10) = 0.30 + 0.20 = 0.50
#   kappa  = (0.70 - 0.50) / (1 - 0.50)            = 0.40
LEFT = ["yes"] * 6 + ["no"] * 4
RIGHT = ["yes", "yes", "yes", "yes", "no", "no", "yes", "no", "no", "no"]


def test_observed_agreement_and_kappa_match_the_hand_computation() -> None:
    assert usage.observed_agreement(LEFT, RIGHT) == 0.7
    assert usage.cohens_kappa(LEFT, RIGHT) == 0.4


def test_kappa_is_none_where_it_is_not_defined() -> None:
    # One category throughout: the two agreed completely, chance predicts
    # complete agreement, and 1 - p_e is zero. 0.0 would say the opposite.
    assert usage.observed_agreement(["yes"] * 5, ["yes"] * 5) == 1.0
    assert usage.cohens_kappa(["yes"] * 5, ["yes"] * 5) is None
    assert usage.cohens_kappa([], []) is None
    assert usage.observed_agreement([], []) is None


def test_paired_labels_of_different_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="paired labels"):
        usage.observed_agreement(["a", "b"], ["a"])


# Five judgements over three classes:
#
#   reference  a a b b c
#   predicted  a b b b c
#
#   a: tp 1, predicted 1, support 2 -> P 1.000, R 0.500, F1 0.6667
#   b: tp 2, predicted 3, support 2 -> P 0.6667, R 1.000, F1 0.800
#   c: tp 1, predicted 1, support 1 -> P 1.000, R 1.000, F1 1.000
#   accuracy = 4/5 = 0.800
#   macro-F1 = (0.6667 + 0.800 + 1.000) / 3 = 0.822222
REFERENCE = ["a", "a", "b", "b", "c"]
PREDICTED = ["a", "b", "b", "b", "c"]


def test_the_per_class_table_matches_the_hand_computation() -> None:
    # `floor=1`: the hand computation is over five judgements, and the support
    # floor the artefact publishes at would withhold all three rates. What the
    # floor does is asserted separately, below.
    table = {row["label"]: row for row in usage.per_class(REFERENCE, PREDICTED, floor=1)}
    assert [
        row["label"] for row in usage.per_class(REFERENCE, PREDICTED, floor=1)
    ] == ["a", "b", "c"]
    assert (table["a"]["precision"], table["a"]["recall"], table["a"]["f1"]) == (
        1.0,
        0.5,
        0.666667,
    )
    assert (table["b"]["precision"], table["b"]["recall"], table["b"]["f1"]) == (
        0.666667,
        1.0,
        0.8,
    )
    assert table["c"]["f1"] == 1.0
    assert [table[label]["support"] for label in "abc"] == [2, 2, 1]


def test_accuracy_and_macro_f1_match_the_hand_computation() -> None:
    # weighted-F1 = (2 * 0.666667 + 2 * 0.800 + 1 * 1.000) / 5 = 0.786667
    scored = usage.classification(REFERENCE, PREDICTED, floor=1)
    assert scored is not None
    assert scored["n"] == 5
    assert scored["accuracy"] == 0.8
    assert scored["macro_f1"] == 0.822222
    assert scored["weighted_f1"] == 0.786667


def test_macro_f1_is_none_on_a_degenerate_comparison() -> None:
    # One category on both sides: the F1 of the only class says nothing about
    # telling classes apart.
    scored = usage.classification(["a", "a"], ["a", "a"])
    assert scored is not None
    assert scored["accuracy"] == 1.0
    assert scored["macro_f1"] is None
    assert usage.classification([], []) is None


def test_the_abstention_rate_counts_the_field_s_own_declining_label() -> None:
    scored = usage.classification(
        ["true_positive"] * 4, ["true_positive", "uncertain", "uncertain", "false_positive"],
        abstention="uncertain",
    )
    assert scored is not None
    assert scored["abstention_rate"] == 0.5


def test_the_multi_label_field_is_scored_by_overlap() -> None:
    # {a} vs {a}          -> 1
    # {a,b} vs {a}        -> 1/2
    # {a} vs {c}          -> 0
    # mean = (1 + 0.5 + 0) / 3 = 0.5
    assert usage.jaccard(["a", "a|b", "a"], ["a", "a", "c"]) == 0.5
    assert usage.jaccard([], []) is None


# --- The gold sample --------------------------------------------------------


def annotation(occurrence: str, coder: str, **changes: str) -> dict[str, str]:
    base = {
        "occurrence_id": occurrence,
        "schema_version": audit.SCHEMA_VERSION,
        "lexicon_version": "2",
        "coder": coder,
        "coded_at": "2026-09-01",
        "verdict": "true_positive",
        "source_checked": "no",
        "quotation": "not_quoted",
        "stance": "asserts",
        "function": "accusation_or_qualification",
        "referent": "rwanda_1994",
        "evidence_start": "0",
        "evidence_end": "40",
        "confidence": "high",
        "comment": "",
    }
    return {**base, **changes}


def annotations(*records: dict[str, str]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(audit.ANNOTATION_FIELDS))
    return pd.DataFrame(records).loc[:, list(audit.ANNOTATION_FIELDS)]


def test_the_gold_state_moves_from_not_started_to_complete() -> None:
    empty = usage.gold_block(
        annotations(), rows(), sample_size=200, unique_occurrences=2
    )
    assert empty["state"] == "not_started"
    assert (empty["coders"], empty["double_coded"], empty["adjudicated"]) == ([], 0, 0)
    assert (empty["human_agreement"], empty["model_vs_human"]) == ([], [])

    started = usage.gold_block(
        annotations(annotation("occ-000", "FM")), rows(), sample_size=200,
        unique_occurrences=2,
    )
    assert started["state"] == "in_progress"
    assert started["coders"] == [{"coder": "FM", "rows": 1}]
    assert started["double_coded"] == 0

    done = usage.gold_block(
        annotations(
            annotation("occ-000", "FM"),
            annotation("occ-000", "JG"),
            annotation("occ-001", "FM"),
            annotation("occ-001", "JG"),
        ),
        rows(),
        sample_size=200,
        unique_occurrences=2,
    )
    assert done["state"] == "complete"
    assert done["double_coded"] == 2
    assert done["coders"] == [{"coder": "FM", "rows": 2}, {"coder": "JG", "rows": 2}]


def test_a_file_of_blank_rows_is_still_not_started() -> None:
    blank = annotations(dict.fromkeys(audit.ANNOTATION_FIELDS, ""))
    assert usage.gold_block(
        blank, rows(), sample_size=200, unique_occurrences=2
    )["state"] == "not_started"


def test_human_agreement_is_computed_over_the_double_coded_occurrences_only() -> None:
    coded = annotations(
        annotation("occ-000", "FM"),
        annotation("occ-000", "JG"),
        annotation("occ-001", "FM", stance="rejects_or_denies"),
        annotation("occ-001", "JG", stance="asserts"),
        annotation("occ-002", "FM"),  # coded once; contributes to no pair
    )
    table = {row["field"]: row for row in usage.human_agreement(coded)}
    assert set(table) == set(usage.SINGLE_LABEL_FIELDS)
    assert table["stance"]["n"] == 2
    assert table["stance"]["observed"] == 0.5
    # One category on the verdict field, so kappa is not defined there.
    assert table["verdict"]["observed"] == 1.0
    assert table["verdict"]["kappa"] is None


ADJUDICATED = annotations(
    # Both coders agree, the adjudicator overrides them: the adjudicated label
    # is the reference.
    annotation("occ-000", "FM", verdict="true_positive"),
    annotation("occ-000", "JG", verdict="true_positive"),
    annotation("occ-000", "adjudicated", verdict="uncertain", stance="unclear",
               quotation="unclear", referent="unclear"),
    # Both coders agree and nobody adjudicated: their label is the reference.
    annotation("occ-001", "FM", verdict="true_positive"),
    annotation("occ-001", "JG", verdict="true_positive"),
    # The coders disagree on every field and nobody adjudicated: skipped.
    annotation("occ-002", "FM", verdict="true_positive", stance="asserts",
               quotation="not_quoted", referent="rwanda_1994"),
    annotation("occ-002", "JG", verdict="uncertain", stance="unclear",
               quotation="unclear", referent="unclear"),
)


def test_an_adjudicated_label_beats_the_two_coders_agreeing() -> None:
    reference = usage.reference_labels(ADJUDICATED)
    assert reference["occ-000"]["verdict"] == "uncertain"
    assert reference["occ-001"]["verdict"] == "true_positive"


def test_a_disagreement_nobody_adjudicated_is_left_out_rather_than_resolved() -> None:
    reference = usage.reference_labels(ADJUDICATED)
    assert "occ-002" not in reference
    scored = {row["field"]: row for row in usage.model_vs_human(ADJUDICATED, rows({}, {}, {}))}
    # occ-000 and occ-001 have a reference; occ-002 does not.
    assert scored["verdict"]["n"] == 2
    # The model said true_positive for both; the reference says uncertain, then
    # true_positive. One of two right.
    assert scored["verdict"]["accuracy"] == 0.5


def test_the_model_is_scored_only_where_it_annotated_the_occurrence() -> None:
    # The run covers occ-001 alone, so the join leaves one comparable pair.
    scored = {
        row["field"]: row
        for row in usage.model_vs_human(ADJUDICATED, rows({"occurrence_id": "occ-001"}))
    }
    assert scored["verdict"]["n"] == 1
    assert scored["verdict"]["accuracy"] == 1.0
    assert usage.model_vs_human(ADJUDICATED, rows()) == []


def test_the_function_overlap_uses_the_same_reference_rule() -> None:
    # occ-000's adjudicated function is the reference; occ-001's agreed one is;
    # occ-002 is skipped. The model matches both, so the overlap is 1.
    coded = annotations(
        annotation("occ-000", "FM", function="commemoration"),
        annotation("occ-000", "JG", function="commemoration"),
        annotation("occ-000", "adjudicated", function="accountability"),
        annotation("occ-001", "FM", function="accountability"),
        annotation("occ-001", "JG", function="accountability"),
    )
    model = rows({"function": "accountability"}, {"function": "accountability"})
    assert usage.function_jaccard(coded, model) == 1.0
    assert usage.function_jaccard(annotations(), model) is None



# --- Chance correction where the marginals are the problem -------------------


def test_the_minority_share_is_the_flatter_of_the_two_margins() -> None:
    # Left: 99 of 100 "a", so 1% fell outside its commonest label.
    # Right: every one "a", so nothing did. The smaller of the two governs,
    # because one flat margin is enough to make kappa's correction meaningless.
    assert usage.minority_share(["a"] * 99 + ["b"], ["a"] * 100) == 0.0
    assert usage.minority_share(["a"] * 99 + ["b"], ["a"] * 98 + ["b"] * 2) == 0.01
    assert usage.minority_share([], []) is None


# PABAK over k categories:  ( k * p_o - 1 ) / ( k - 1 )
#
#   p_o = 0.99 over the ten pairs below repeated, k = 3
#   PABAK = (3 * 0.99 - 1) / 2 = 1.97 / 2 = 0.985
#   k = 2 gives the classic form: 2 * 0.99 - 1 = 0.98
def test_pabak_matches_the_hand_computation() -> None:
    left = ["a"] * 99 + ["b"]
    right = ["a"] * 100
    assert usage.observed_agreement(left, right) == 0.99
    assert usage.pabak(left, right, categories=3) == 0.985
    assert usage.pabak(left, right) == 0.98
    assert usage.pabak(left, right, categories=1) is None
    assert usage.pabak([], [], categories=3) is None


def test_kappa_is_withheld_where_one_margin_is_flat_and_pabak_is_not() -> None:
    # The verdict field of both committed runs, in miniature: 99.9% agreement
    # over a field one label carries. Kappa divides by what chance leaves, which
    # is almost nothing, and returns a number that reads as failure.
    withheld = usage.chance_corrected(["a"] * 999 + ["b"], ["a"] * 1000, categories=3)
    assert withheld["kappa"] is None
    assert withheld["kappa_withheld"] is True
    assert withheld["minority_share"] == 0.0
    assert withheld["pabak"] == 0.9985

    # A field with information in both margins keeps its kappa, and the flag
    # says nothing was suppressed.
    kept = usage.chance_corrected(LEFT, RIGHT, categories=2)
    assert kept["kappa"] == 0.4
    assert kept["kappa_withheld"] is False
    assert kept["pabak"] == 0.4  # k = 2: 2 * 0.7 - 1


def test_a_kappa_that_was_never_defined_is_not_reported_as_withheld() -> None:
    # One category across both raters: kappa is undefined, not suppressed, and
    # the two readings are different findings.
    undefined = usage.chance_corrected(["a"] * 5, ["a"] * 5, categories=3)
    assert undefined["kappa"] is None
    assert undefined["kappa_withheld"] is True
    empty = usage.chance_corrected([], [], categories=3)
    assert (empty["kappa"], empty["kappa_withheld"], empty["pabak"]) == (None, False, None)


def test_the_declared_category_counts_are_the_codebook_s_own() -> None:
    # Written out in the module so a chance correction cannot move when the
    # vocabulary does; held to the codebook here so it cannot drift in silence.
    referents = audit.read_referents(ROOT / "annotations" / "lexicon" / "referents.csv")
    codebook = {
        "verdict": len(audit.VERDICTS),
        "quotation": len(audit.QUOTATIONS),
        "stance": len(audit.STANCES),
        "referent": len(referents),
    }
    assert codebook == usage.FIELD_CATEGORIES
    assert set(usage.FIELD_CATEGORIES) == set(usage.SINGLE_LABEL_FIELDS)


# --- The multi-label field ---------------------------------------------------


def test_the_masi_distance_is_jaccard_weighted_by_containment() -> None:
    a, b, c = frozenset({"a"}), frozenset({"b"}), frozenset({"c"})
    # Identical: J = 1, M = 1, distance 0.
    assert usage.masi_distance(a, a) == 0.0
    # Proper subset: J = 1/2, M = 2/3, similarity 1/3, distance 2/3.
    assert usage.masi_distance(a, a | b) == pytest.approx(2 / 3)
    # Intersecting, neither contained: J = 1/3, M = 1/3, similarity 1/9.
    assert usage.masi_distance(a | b, a | c) == pytest.approx(1 - 1 / 9)
    # Disjoint: distance 1.
    assert usage.masi_distance(a, b) == 1.0
    # Two empty sets are one judgement, not a division by zero.
    assert usage.masi_distance(frozenset(), frozenset()) == 0.0


# Krippendorff's alpha under MASI over three units, two coders:
#
#   u1  {a}    {a}     delta 0
#   u2  {a,b}  {a}     delta 1 - (1/2)(2/3) = 2/3
#   u3  {a}    {c}     delta 1
#
#   D_o = (0 + 2/3 + 1) / 3 = 5/9
#
#   pooled values: {a} x 4, {a,b} x 1, {c} x 1, so 2n = 6
#   ordered pairs: 8 x delta({a},{a,b}) = 8 * 2/3 = 16/3
#                  8 x delta({a},{c})   = 8
#                  2 x delta({a,b},{c}) = 2
#   D_e = (16/3 + 10) / (6 * 5) = (46/3) / 30 = 23/45
#
#   alpha = 1 - (5/9) / (23/45) = 1 - 25/23 = -2/23 = -0.086957
def test_krippendorff_alpha_under_masi_matches_the_hand_computation() -> None:
    assert usage.krippendorff_alpha_masi(["a", "a|b", "a"], ["a", "a", "c"]) == -0.086957
    assert usage.krippendorff_alpha_masi([], []) is None
    # Nothing but one set throughout: expected disagreement is zero, and the
    # ratio is undefined rather than a perfect score.
    assert usage.krippendorff_alpha_masi(["a", "a"], ["a", "a"]) is None


def test_alpha_ignores_the_order_the_labels_were_written_in() -> None:
    # The same two judgements written in two orders. Observed disagreement is
    # zero and the two units differ from each other, so the statistic has
    # something to divide by and returns perfect agreement rather than nothing.
    assert usage.krippendorff_alpha_masi(["a|b", "b|c"], ["b|a", "c|b"]) == 1.0


def test_per_label_kappa_names_the_label_the_two_readings_differ_on() -> None:
    # Four units. `commemoration` is agreed throughout; `accountability` is on
    # every left-hand set and no right-hand one.
    left = ["commemoration|accountability"] * 2 + ["commemoration"] * 2
    right = ["commemoration"] * 4
    table = {row["label"]: row for row in usage.per_label_kappa(left, right)}
    assert table["commemoration"]["left"] == 4
    assert table["commemoration"]["right"] == 4
    # Both sides put it on every unit: one category, no chance to correct.
    assert table["commemoration"]["kappa"] is None
    assert (table["accountability"]["left"], table["accountability"]["right"]) == (2, 0)
    assert table["accountability"]["observed"] == 0.5
    assert usage.per_label_kappa([], []) == []


# --- The support floor under the per-class table -----------------------------


def test_a_class_below_the_support_floor_keeps_its_counts_and_loses_its_rates() -> None:
    reference = ["a"] * 25 + ["b"] * 3
    predicted = ["a"] * 24 + ["b"] + ["b"] * 2 + ["a"]
    table = {row["label"]: row for row in usage.per_class(reference, predicted)}
    assert table["a"]["measurable"] is True
    assert table["a"]["support"] == 25
    assert table["a"]["f1"] is not None
    # Three occurrences: recall moves in thirds and F1 is not a measurement.
    assert table["b"]["measurable"] is False
    assert (table["b"]["support"], table["b"]["predicted"], table["b"]["correct"]) == (3, 3, 2)
    assert (table["b"]["precision"], table["b"]["recall"], table["b"]["f1"]) == (
        None,
        None,
        None,
    )


def test_the_macro_average_is_over_measurable_classes_and_the_weighted_one_is_not() -> None:
    # a: support 25, predicted 25, correct 24 -> F1 = 2*24/50 = 0.96
    # b: support  3, predicted  3, correct  2 -> F1 = 2*2/6   = 0.666667
    # macro over the measurable classes = 0.96 (b is below the floor)
    # weighted = (25 * 0.96 + 3 * 0.666667) / 28 = 26/28 = 0.928571
    reference = ["a"] * 25 + ["b"] * 3
    predicted = ["a"] * 24 + ["b"] + ["b"] * 2 + ["a"]
    scored = usage.classification(reference, predicted)
    assert scored is not None
    assert scored["macro_f1"] == 0.96
    assert scored["weighted_f1"] == 0.928571
    assert (scored["classes_measured"], scored["classes_withheld"]) == (1, 1)
    assert scored["support_floor"] == 20


def test_a_field_whose_every_class_is_rare_reports_no_macro_average() -> None:
    # Nine referent classes of two occurrences each: nothing clears the floor,
    # and a macro-F1 over them would be an average of numbers computed in halves.
    labels = [f"case_{index}" for index in range(9)]
    reference = [label for label in labels for _ in range(2)]
    scored = usage.classification(reference, list(reference))
    assert scored is not None
    assert scored["macro_f1"] is None
    assert scored["weighted_f1"] == 1.0
    assert scored["classes_measured"] == 0
    assert scored["classes_withheld"] == 9


# --- What the reference leaves out -------------------------------------------


def test_the_excluded_share_travels_with_the_score() -> None:
    coverage = usage.reference_coverage(ADJUDICATED)
    # Three double-coded occurrences; occ-002's coders differ on every field.
    assert coverage["stance"]["available"] == 3
    assert coverage["stance"]["resolved"] == 2
    assert coverage["stance"]["excluded"] == 1
    assert coverage["stance"]["excluded_share"] == 0.333333
    scored = {row["field"]: row for row in usage.model_vs_human(ADJUDICATED, rows({}, {}, {}))}
    assert scored["stance"]["double_coded"] == 3
    assert scored["stance"]["excluded"] == 1
    assert scored["stance"]["excluded_share"] == 0.333333
    assert usage.reference_coverage(annotations()) == {}


def test_the_two_coders_function_sets_are_compared_as_sets_not_as_strings() -> None:
    # The same judgement written in two orders. Compared as strings it left the
    # reference silently, while the model comparison had always used sets.
    coded = annotations(
        annotation("occ-000", "FM", function="accountability|commemoration"),
        annotation("occ-000", "JG", function="commemoration|accountability"),
    )
    model = rows({"function": "accountability|commemoration"})
    assert usage.function_jaccard(coded, model) == 1.0


def test_the_coders_multi_label_agreement_reports_alpha_and_the_label_table() -> None:
    coded = annotations(
        annotation("occ-000", "FM", function="commemoration"),
        annotation("occ-000", "JG", function="commemoration"),
        annotation("occ-001", "FM", function="accountability|commemoration"),
        annotation("occ-001", "JG", function="commemoration"),
    )
    block = usage.human_function_agreement(coded)
    assert block["n"] == 2
    assert block["jaccard"] == 0.75  # (1 + 1/2) / 2
    assert block["alpha_masi"] is not None
    assert {row["label"] for row in block["labels"]} == {
        "accountability",
        "commemoration",
    }
    empty = usage.human_function_agreement(annotations())
    assert (empty["n"], empty["alpha_masi"], empty["labels"]) == (0, None, [])

# --- The second opinion -----------------------------------------------------


def second_run(*changes: dict[str, object]) -> list[dict[str, object]]:
    """A comparison run's rows, in the shape `lib.llm.read_rows` returns them.

    A list of dicts and not a frame, because that is what `15_usage.py` has in
    hand when it reads a second run: the comparison never joins the corpus, so
    nothing builds a frame around it. Ids are assigned by position, as in
    :func:`rows`, so the two runs line up unless a test says otherwise.
    """
    return rows(*changes).to_dict(orient="records")


#: The ten paired judgements of LEFT and RIGHT, spelled in the codebook's stance
#: vocabulary so that two runs can be written from them.
STANCE_OF = {"yes": "asserts", "no": "rejects_or_denies"}


def test_a_field_is_contested_only_where_the_two_runs_label_it_differently() -> None:
    published = rows(*repeat(3, stance="asserts"))
    second = second_run(
        {"stance": "asserts"},
        {"stance": "rejects_or_denies"},
        {"stance": "unclear"},
    )
    table = {row["field"]: row for row in usage.comparison_fields(published, second)}
    assert table["stance"]["n"] == 3
    assert table["stance"]["contested"] == 2
    # The other three fields are identical in both runs and contest nothing.
    assert [table[field]["contested"] for field in ("verdict", "quotation", "referent")] == [
        0,
        0,
        0,
    ]


def test_the_multi_label_field_is_compared_as_a_set() -> None:
    # Order carries no meaning in `function`, so two spellings of one judgement
    # are not a disagreement; a strictly larger set is.
    published = rows({"function": "a|b"}, {"function": "a"})
    second = second_run({"function": "b|a"}, {"function": "a|b"})
    contested = usage.contested_rows(published, second)
    assert contested["occ-000"] == ([], None)
    assert contested["occ-001"][0] == ["function"]
    # `function` carries no kappa, so it is absent from the per-field table and
    # reported as an overlap instead.
    assert [row["field"] for row in usage.comparison_fields(published, second)] == list(
        usage.SINGLE_LABEL_FIELDS
    )


def test_the_alternative_reading_is_carried_in_full_or_not_at_all() -> None:
    published = rows({}, {})
    second = second_run({"stance": "rejects_or_denies"}, {})
    contested = usage.contested_rows(published, second)
    fields, alternative = contested["occ-000"]
    assert fields == ["stance"]
    # All five labels, not only the contested one: a reader told an occurrence is
    # contested is being invited to read the other run's whole reading of it.
    assert alternative == {
        "verdict": "true_positive",
        "quotation": "not_quoted",
        "stance": "rejects_or_denies",
        "function": "accusation_or_qualification",
        "referent": "rwanda_1994",
    }
    assert list(alternative) == list(usage.COMPARED_FIELDS)
    # Agreement carries no alternative: a reading identical to the published one
    # is not an alternative to it.
    assert contested["occ-001"] == ([], None)


def test_the_overlap_is_what_both_runs_reached_and_nothing_else() -> None:
    published = rows({"occurrence_id": "a"}, {"occurrence_id": "b"})
    second = second_run({"occurrence_id": "b"}, {"occurrence_id": "c"})
    assert usage.comparison_overlap(published, second) == ["b"]
    assert list(usage.contested_rows(published, second)) == ["b"]
    assert usage.comparison_fields(published, second)[0]["n"] == 1
    # An occurrence only one run reached is absent from the mapping rather than
    # present and agreeing, and the block says how far the two overlap.
    block = usage.comparison_block(published, second)
    assert (block["occurrences_annotated"], block["overlap"]) == (2, 1)


def test_a_refused_match_is_compared_rather_than_filtered_out() -> None:
    # The published run called the match a false positive and the second called
    # it a true positive. The eligibility gate every other block is cut on would
    # drop this row, and it is the disagreement most worth reading.
    contested = usage.contested_rows(rows(false_positive()), second_run({}))
    fields, alternative = contested["occ-000"]
    assert fields == list(usage.COMPARED_FIELDS)
    assert alternative["verdict"] == "true_positive"
    # Nor is an evidence quotation nobody could locate a reason to drop a row.
    assert usage.contested_rows(rows({"evidence_valid": False}), second_run({})) == {
        "occ-000": ([], None)
    }


def test_observed_and_kappa_are_the_statistics_the_two_coders_are_scored_by() -> None:
    published = rows(*[{"stance": STANCE_OF[value]} for value in LEFT])
    second = second_run(*[{"stance": STANCE_OF[value]} for value in RIGHT])
    table = {row["field"]: row for row in usage.comparison_fields(published, second)}
    # p_o = 0.70 and kappa = 0.40, hand-computed above LEFT and RIGHT.
    assert (table["stance"]["observed"], table["stance"]["kappa"]) == (0.7, 0.4)
    assert table["stance"]["contested"] == 3
    # One category on the verdict field: kappa is not defined there, and the
    # answer is the same one `human_agreement` gives from the same function.
    assert table["verdict"]["observed"] == 1.0
    assert table["verdict"]["kappa"] is None


def test_the_multi_label_overlap_is_reported_where_kappa_cannot_be() -> None:
    # {a} vs {a} -> 1, {a,b} vs {a} -> 1/2, {a} vs {c} -> 0; mean 0.5.
    published = rows({"function": "a"}, {"function": "a|b"}, {"function": "a"})
    second = second_run({"function": "a"}, {"function": "a"}, {"function": "c"})
    block = usage.comparison_block(published, second)
    assert block["function_jaccard"] == 0.5
    assert block["function_contested"] == 2
    assert block["contested_any"] == 2


def test_what_the_second_run_did_is_counted_over_all_of_its_rows() -> None:
    published = rows({"occurrence_id": "a"})
    second = second_run(
        {"occurrence_id": "a"},
        {"occurrence_id": "b", "referent": "unclear", "evidence_valid": False},
    )
    block = usage.comparison_block(published, second)
    # The abstention and the unlocatable evidence belong to the second run and
    # are reported whether or not the published run reached that occurrence; the
    # agreement figures below them are over the overlap alone.
    assert (block["evidence_invalid"], block["abstention"]["referent_unclear"]) == (1, 1)
    assert (block["overlap"], block["contested_any"]) == (1, 0)


def test_an_empty_comparison_is_written_as_a_state_rather_than_as_an_absence() -> None:
    published = rows({}, {})
    empty = usage.comparison_block(published, [])
    computed = usage.comparison_block(
        published, second_run({"stance": "unclear"}, {}), run_id="0000-00-00-second"
    )
    # One builder, so the two states cannot drift apart: a consumer reads the
    # same keys whether or not a second opinion was bought.
    assert list(empty) == list(computed)
    assert (empty["state"], computed["state"]) == ("none", "computed")
    assert empty["fields"] == []
    assert empty["function_jaccard"] is None
    assert [
        empty[key]
        for key in ("run_id", "model", "run_date", "reasoning_effort", "prompt_sha256")
    ] == [""] * 5
    assert [
        empty[key]
        for key in (
            "occurrences_annotated",
            "overlap",
            "evidence_invalid",
            "function_contested",
            "contested_any",
        )
    ] == [0] * 5
    assert empty["abstention"] == {
        "verdict_uncertain": 0,
        "referent_unclear": 0,
        "stance_unclear": 0,
    }
    assert usage.contested_rows(published, []) == {}


def test_the_comparison_run_is_scored_against_the_same_human_reference() -> None:
    # occ-000's reference is `uncertain` and occ-001's is `true_positive`; the
    # comparison run says `uncertain` to both, so one of two is right.
    published = rows({}, {})
    second = rows(
        *repeat(2, verdict="uncertain", quotation="unclear", stance="unclear",
                function="unclear", referent="unclear")
    )
    block = usage.gold_block(
        ADJUDICATED, published, sample_size=200, unique_occurrences=2, comparison=second
    )
    scored = {row["field"]: row for row in block["model_vs_human_comparison"]}
    assert (scored["verdict"]["n"], scored["verdict"]["accuracy"]) == (2, 0.5)
    keys = list(block)
    assert keys.index("model_vs_human_comparison") == keys.index("model_vs_human") + 1
    # Empty rather than absent where no comparison run was read, as every other
    # table in this block is until it can be computed.
    assert usage.gold_block(
        ADJUDICATED, published, sample_size=200, unique_occurrences=2
    )["model_vs_human_comparison"] == []


# --- Refusals ---------------------------------------------------------------

ENUMERATED = {"occ-000": "digest-a", "occ-001": "digest-b"}


def test_a_row_naming_an_occurrence_the_corpus_does_not_have_is_refused() -> None:
    problems = usage.row_problems(
        [{"occurrence_id": "occ-999", "source_sha256": "digest-a"}], ENUMERATED
    )
    assert len(problems) == 1
    assert "does not have" in problems[0]


def test_a_row_whose_body_digest_has_moved_is_refused() -> None:
    problems = usage.row_problems(
        [{"occurrence_id": "occ-000", "source_sha256": "digest-moved"}], ENUMERATED
    )
    assert len(problems) == 1
    assert "was annotated against body" in problems[0]


def test_the_same_occurrence_annotated_twice_is_refused() -> None:
    row = {"occurrence_id": "occ-000", "source_sha256": "digest-a"}
    problems = usage.row_problems([row, dict(row)], ENUMERATED)
    assert len(problems) == 1
    assert "more than once" in problems[0]


def test_rows_that_agree_with_the_enumeration_raise_nothing() -> None:
    assert usage.row_problems(
        [
            {"occurrence_id": "occ-000", "source_sha256": "digest-a"},
            {"occurrence_id": "occ-001", "source_sha256": "digest-b"},
        ],
        ENUMERATED,
    ) == []


def test_the_aggregation_refuses_a_frame_that_is_missing_a_column() -> None:
    frame = rows({}).drop(columns=["evidence_valid"])
    with pytest.raises(KeyError, match="evidence_valid"):
        usage.actor_rows(frame)


# --- The lexicon a run was made against -------------------------------------


def lexicon_at(version: int, pattern_since: int) -> lexicon.Lexicon:
    """A lexicon holding the one term `15_usage.py` aggregates."""
    pattern = r"\bgenocid\w*"
    return lexicon.Lexicon(
        version=version,
        updated="2026-09-01",
        terms={
            step.TERM: lexicon.Term(
                name=step.TERM,
                pattern=pattern,
                tier="core",
                register="core",
                pattern_since=pattern_since,
                examples=("genocide",),
                prefilters=("genocid",),
                regex=re.compile(pattern, re.IGNORECASE),
            )
        },
        sets={},
    )


def run_at(version: str) -> tuple[dict[str, object], list[dict]]:
    return {"lexicon_version": version}, [{"lexicon_version": version}]


def test_a_run_survives_a_bump_that_did_not_touch_its_term() -> None:
    """The whole point of `pattern_since`: v3 moved other terms, `genocide`
    enumerates what it did at v2, and the committed run is still about this
    corpus. Refusing it would force a paid re-run for nothing."""
    manifest, rows_ = run_at("2")
    step.refuse_stale_lexicon(manifest, rows_, lexicon_at(3, pattern_since=2))


def test_a_run_older_than_the_terms_pattern_is_refused() -> None:
    manifest, rows_ = run_at("1")
    with pytest.raises(SystemExit):
        step.refuse_stale_lexicon(manifest, rows_, lexicon_at(3, pattern_since=2))


def test_a_run_newer_than_the_lexicon_is_refused() -> None:
    """A run cannot have been coded against a lexicon this repository does not
    have; the checkout is behind the run, not the other way round."""
    manifest, rows_ = run_at("4")
    with pytest.raises(SystemExit):
        step.refuse_stale_lexicon(manifest, rows_, lexicon_at(3, pattern_since=2))


def test_a_run_with_no_recorded_lexicon_version_is_refused() -> None:
    with pytest.raises(SystemExit):
        step.refuse_stale_lexicon({}, [], lexicon_at(3, pattern_since=2))


def test_rows_are_checked_even_when_the_manifest_is_compatible() -> None:
    """The manifest is written once at the end of a run; the rows arrive as the
    run goes."""
    with pytest.raises(SystemExit):
        step.refuse_stale_lexicon(
            {"lexicon_version": "2"},
            [{"lexicon_version": "2"}, {"lexicon_version": "1"}],
            lexicon_at(3, pattern_since=2),
        )
