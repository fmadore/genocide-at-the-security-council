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

import pandas as pd
import pytest
from lib import audit, usage

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
    table = {row["label"]: row for row in usage.per_class(REFERENCE, PREDICTED)}
    assert [row["label"] for row in usage.per_class(REFERENCE, PREDICTED)] == ["a", "b", "c"]
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
    scored = usage.classification(REFERENCE, PREDICTED)
    assert scored is not None
    assert scored["n"] == 5
    assert scored["accuracy"] == 0.8
    assert scored["macro_f1"] == 0.822222


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
