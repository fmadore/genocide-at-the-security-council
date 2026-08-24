"""The artefact contract: what a shape is, and what counts as breaking it.

`scripts/lib/contract.py` exists because the payload's shape was written three
times — by the Python that emits it, by `web/src/lib/types.ts` that declares it,
and by `web/src/lib/data.ts` that validates it — with nothing joining them. A
renamed field passed every check this repository had and was found by looking at
an empty figure.

What is tested here is the join itself: that it notices a field that moved, and
that it does *not* notice the things a working project does every week. A check
that fails on an ordinary lexicon edit gets switched off, and a check that has
been switched off is worse than none, because the file it guards still looks
guarded.
"""

from __future__ import annotations

import json

from lib import contract
from lib.paths import CONTRACT


class TestSkeleton:
    def test_values_are_replaced_by_their_types(self):
        shape = contract.skeleton({"speeches": 3, "rate": 0.5, "label": "genocide"})
        assert shape == {"label": "str", "rate": "float", "speeches": "int"}

    def test_an_array_is_reduced_to_one_merged_element(self):
        """Merged rather than sampled from the first.

        A payload whose rows disagree about their fields is exactly what a
        figure mis-draws, and taking element zero as representative would hide
        the disagreement behind whichever row happened to be written first.
        """
        shape = contract.skeleton([{"a": 1}, {"a": 1, "b": "x"}])
        assert shape == [{"a": "int", "b?": "str"}]

    def test_a_nullable_column_keeps_its_null(self):
        """The withheld rate is the load-bearing null in this project.

        `11_countries.py` writes null where a speaker is under the minimum, and
        the interface detects it rather than reading it through `?? 0`. A
        contract that collapsed it to `float` would let the null disappear
        without complaint, and 468 withheld speakers would become measured zeros.
        """
        assert contract.skeleton([0.1, None, 0.3]) == ["float|null"]

    def test_a_block_keyed_on_the_lexicon_is_folded_into_one_member(self):
        shape = contract.skeleton({"terms": {"genocide": {"speeches": [1]}, "atrocity": {}}})
        assert shape == {"terms": {contract.MEMBER: {"speeches?": ["int"]}}}

    def test_a_discriminator_shared_by_every_variant_stays_required(self):
        shape = contract.skeleton(
            [{"kind": "term", "pattern": "genocid"}, {"kind": "set", "members": ["genocide"]}]
        )
        assert shape == [{"kind": "str", "members?": ["str"], "pattern?": "str"}]

    def test_an_empty_container_constrains_only_its_kind(self):
        """An artefact whose array happens to be empty this run is not a shape.

        `series/change_points.json` carries an empty `token_rate` for a measure
        with no accepted break. Recording `[]` says "an array lives here" and
        nothing about what is in it, which is the only honest reading.
        """
        assert contract.skeleton({"breaks": [], "block": {}}) == {"block": {}, "breaks": []}


class TestDifferences:
    def test_a_renamed_field_is_reported_with_its_path(self):
        promised = contract.skeleton({"terms": {"genocide": {"speech_rate": [0.1]}}})
        found = contract.skeleton({"terms": {"genocide": {"rate": [0.1]}}})
        assert list(contract.differences(promised, found)) == [".terms.*.speech_rate: missing"]

    def test_a_number_emitted_as_a_string_is_reported(self):
        promised = contract.skeleton({"periods": [1992]})
        found = contract.skeleton({"periods": ["1992"]})
        assert list(contract.differences(promised, found)) == [
            ".periods[]: expected int, found str"
        ]

    def test_a_new_field_is_not_a_difference(self):
        """Every feature here has started as a field nothing read yet.

        A contract that failed on growth would be updated reflexively, which is
        the same as not reading it.
        """
        promised = contract.skeleton({"meta": {"script": "04_series.py"}})
        found = contract.skeleton({"meta": {"script": "04_series.py"}, "coverage": 0.86})
        assert list(contract.differences(promised, found)) == []

    def test_one_member_losing_a_required_field_is_a_difference(self):
        promised = contract.skeleton({"terms": {"a": {"x": 1}, "b": {"x": 1}}})
        found = contract.skeleton({"terms": {"a": {"x": 1}, "b": {}}})
        assert list(contract.differences(promised, found)) == [
            ".terms.*.x: required field is absent from some members"
        ]

    def test_an_optional_field_may_move_between_members(self):
        """An ordinary lexicon edit remains compatible.

        A set has no occurrence count and a term does; adding or removing either
        changes which members carry the optional field without changing what any
        consumer can require.
        """
        promised = contract.skeleton({"terms": {"a": {"x": 1, "y": 2}, "b": {"x": 1}}})
        found = contract.skeleton({"terms": {"a": {"x": 1}, "b": {"x": 1, "y": 2}}})
        assert list(contract.differences(promised, found)) == []

    def test_a_declared_optional_field_may_be_absent_from_every_member(self):
        promised = contract.skeleton({"terms": {"a": {"x": 1, "y": 2}, "b": {"x": 1}}})
        found = contract.skeleton({"terms": {"a": {"x": 1}, "b": {"x": 1}}})
        assert list(contract.differences(promised, found)) == []

    def test_a_discriminator_becoming_optional_is_a_difference(self):
        promised = contract.skeleton([{"kind": "term"}, {"kind": "set"}])
        found = contract.skeleton([{"kind": "term"}, {"members": ["genocide"]}])
        assert list(contract.differences(promised, found)) == [
            "[].kind: required field is absent from some members"
        ]

    def test_a_null_appearing_where_none_was_promised_is_a_difference(self):
        """The reverse of the withheld-rate case, and it breaks the same way.

        A column contracted as a number that starts arriving with nulls in it
        reaches arithmetic that was written without a guard.
        """
        promised = contract.skeleton({"rate": [0.1, 0.2]})
        found = contract.skeleton({"rate": [0.1, None]})
        assert list(contract.differences(promised, found)) == [
            ".rate[]: expected float, found float|null"
        ]

    def test_a_null_disappearing_is_not_a_difference(self):
        """A run in which nothing happened to be withheld is not a shape change."""
        promised = contract.skeleton({"rate": [0.1, None]})
        found = contract.skeleton({"rate": [0.1, 0.2]})
        assert list(contract.differences(promised, found)) == []

    def test_an_object_replaced_by_an_array_is_reported(self):
        promised = contract.skeleton({"corpus": {"speeches": [1]}})
        found = contract.skeleton({"corpus": [1]})
        assert list(contract.differences(promised, found)) == [
            ".corpus: expected an object, found an array"
        ]


class TestCommittedContract:
    """The file itself, checked without any data present.

    This is what makes the mechanism run in CI. `export_web.py` enforces the
    contract against a built payload, which only exists on a machine that has
    run the pipeline; these assertions hold on a fresh checkout.
    """

    def test_it_parses_and_declares_a_shape_for_every_tracked_artefact(self):
        promised = json.loads(CONTRACT.read_text(encoding="utf-8"))
        expected = {*contract.TRACKED, contract.SPEECH_SAMPLE}
        assert set(promised) == expected

    def test_every_artefact_carries_its_provenance_block(self):
        """`meta` is not decoration: `export.ts` builds every download's header
        from it, and a file with no provenance is an orphan the moment a figure
        is regenerated. It is the one field required of all of them."""
        promised = json.loads(CONTRACT.read_text(encoding="utf-8"))
        without = [name for name, shape in promised.items() if "meta" not in shape]
        assert without == []

    def test_a_payload_matching_the_contract_reports_nothing(self, tmp_path):
        """The round trip, on a payload built for the purpose.

        `check` reads files, so this is the only place the two halves meet
        without needing `data/derived/` to exist.
        """
        payload = {"meta": {"script": "04_series.py"}, "periods": [1992, 1993]}
        (tmp_path / "series").mkdir()
        (tmp_path / "series" / "annual.json").write_text(json.dumps(payload), encoding="utf-8")
        promised = {"series/annual.json": contract.skeleton(payload)}
        assert contract.check(tmp_path, promised) == ([], [])

    def test_an_absent_artefact_is_reported_apart_from_a_shape_failure(self, tmp_path):
        """`export_web.py` already refuses a payload with a missing part, and
        saying it twice in different words helps nobody. What this returns is a
        list to warn about, not a problem to fail on."""
        promised = {"series/annual.json": {"meta": {}}}
        assert contract.check(tmp_path, promised) == ([], ["series/annual.json"])
