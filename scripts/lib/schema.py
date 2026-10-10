"""The annotation schema: its version, its closed vocabularies and their rules.

The human file under `annotations/` and every model run are coded against the
names here. `lib.audit` holds a human row to them and `lib.llm` holds a model's
answer to them, so the two layers share one vocabulary rather than two copies
that could drift: a category exists for both or for neither. The schema-2
names stay because two committed runs were coded against them, and
:data:`POSITION_FROM_STANCE` and :func:`concrete_case_from_v1` say how such a
run is read today.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

#: The annotation schema the human file and every new model run are coded
#: against. Version 3 (2 September 2026) splits `stance` into `speaker_position`
#: and `concrete_case` and adds the six fields the study's own question needs;
#: the codebook's changelog says why each moved.
SCHEMA_VERSION = "3"

#: The schema the two paid runs of 30 and 31 August 2026 were coded against, on
#: 12,184 rows. They cannot be re-coded without buying them again, so they are
#: read at their own version and resolved onto the current vocabulary rather
#: than refused, which is the discipline `referents.csv` already applies to its
#: own list.
LEGACY_SCHEMA_VERSION = "2"

VERDICTS: Final = frozenset({"true_positive", "false_positive", "uncertain"})
SOURCE_CHECKED: Final = frozenset({"yes", "no"})
QUOTATIONS: Final = frozenset(
    {"not_quoted", "direct_quotation", "attributed_or_reported", "unclear", "not_applicable"}
)
#: What the speaker does with the characterization, at schema 3.
#:
#: Four real positions, a fifth value for the passages that characterize nothing,
#: and the two reserved answers. `no_position` and `concrete_case` are locked to
#: each other — see :data:`CONCRETE_CASE` — so the abstract-versus-concrete
#: decision is taken once instead of competing with itself across three fields,
#: which is what the review of 1 September 2026 (§4.2, item 1) found v1 doing.
POSITIONS: Final = frozenset(
    {
        "asserts",
        "rejects",
        "conditional",
        "reports_without_position",
        "no_position",
        "unclear",
        "not_applicable",
    }
)

#: The schema-2 `stance` vocabulary, kept because two committed runs use it.
#: Nothing new may be coded against it; :data:`POSITION_FROM_STANCE` says what
#: each value becomes when an older run is read.
STANCES: Final = frozenset(
    {
        "asserts",
        "attributes_or_reports",
        "rejects_or_denies",
        "hypothetical_or_conditional",
        "neutral_legal_reference",
        "unclear",
        "not_applicable",
    }
)

#: Whether the word is applied to a determinate case in this passage.
#:
#: A four-value string enum rather than the JSON boolean the review asked for,
#: and the cascade is the reason: a false positive answers every discourse field
#: with `not_applicable`, and an honest abstention has to be able to say
#: `unclear`. A boolean carries neither, so one of the two would have to travel
#: in a second field or be spelled `false` — which would make "not a concrete
#: case" and "not a real occurrence of the word" the same value. Every other
#: field in this schema is a closed string vocabulary checked by one code path,
#: and this one is too.
CONCRETE_CASE: Final = frozenset({"yes", "no", "unclear", "not_applicable"})

#: Where in the request the referent was found, which measures the instrument
#: rather than the passage: 25-47% of the two runs' named-case rows carry no cue
#: for that case in their evidence quote (review §4.2, item 4), and nothing
#: recorded whether the header had been read instead.
REFERENT_SOURCES: Final = frozenset({"passage", "speech", "header", "not_applicable"})

#: Whether the speaker's own State or organisation is the one accused — the
#: denial question Phase L exists for, and unanswerable from any v1 field.
#: `not_applicable` here means "this passage accuses no one", of which a false
#: positive is one case; it is not the cascade's reserved value.
OWN_STATE_ACCUSED: Final = frozenset({"yes", "no", "not_applicable"})

#: Whether the characterization is what the passage is doing, or an item in a
#: list. The atrocity triad is 1,446 of the 6,092 occurrences and was coded
#: identically to a sustained accusation.
SALIENCE: Final = frozenset({"passing", "substantive", "not_applicable"})
FUNCTIONS: Final = frozenset(
    {
        "accusation_or_qualification",
        "warning_or_prevention",
        "commemoration",
        "accountability",
        "institutional_title_or_mandate",
        "other",
        "unclear",
        "not_applicable",
    }
)
CONFIDENCE: Final = frozenset({"low", "medium", "high"})
DEFAULT_REFERENTS: Final = frozenset({"other", "unclear", "not_applicable"})

#: What a schema-2 `stance` becomes when a run coded against it is read at
#: schema 3. Six of the seven values are renames and carry over exactly; the
#: seventh is the one that changed meaning.
#:
#: `neutral_legal_reference` was the value answering two questions at once, and
#: it is the only one that also determines `concrete_case`: a passage a coder
#: called a neutral legal reference is a passage that characterizes no case, so
#: it resolves to `no_position` with `concrete_case: "no"`. The other values say
#: nothing about `concrete_case` on their own — :func:`concrete_case_from_v1`
#: reads it off the recorded referent instead, and abstains where it cannot.
POSITION_FROM_STANCE: Final[Mapping[str, str]] = {
    "asserts": "asserts",
    "rejects_or_denies": "rejects",
    "hypothetical_or_conditional": "conditional",
    "attributes_or_reports": "reports_without_position",
    "neutral_legal_reference": "no_position",
    "unclear": "unclear",
    "not_applicable": "not_applicable",
}

#: The three referents that mean "this passage names no case". They are what
#: makes `concrete_case` recoverable from a v1 row at all.
NON_CASE_REFERENTS: Final = frozenset(
    {"genocide_in_general", "genocide_convention_law", "institutional_mandate"}
)


def concrete_case_from_v1(stance: str, referent: str) -> str:
    """`concrete_case` for a row coded before the field existed.

    A derivation from two recorded fields rather than a re-coding, of the same
    character as resolving a superseded referent onto its successor: the rule
    applied is schema 3's own — the value is "no" exactly when the word is
    applied to no determinate case — and the evidence for it is what the v1
    coder actually wrote.

    Two recorded values answer it. `stance: neutral_legal_reference` says the
    passage characterizes no case, and so does any of the three non-case
    referents. Where the two disagree — a neutral legal reference filed under a
    named case, or an assertion filed under `genocide_in_general` — the referent
    is believed, because it is the field whose vocabulary says what the passage
    is *about*, while the stance value was carrying two questions at once and is
    the one schema 3 split apart.

    An `unclear` or `not_applicable` referent leaves it `unclear`: a row that
    could not name what the word was applied to is no evidence that it was
    applied to anything. That residue is not resolved, and 15 publishes how
    large it is.
    """
    if stance == "not_applicable" or referent == "not_applicable":
        return "not_applicable"
    if referent in NON_CASE_REFERENTS:
        return "no"
    if referent == "unclear" or not referent or stance == "unclear":
        return "unclear"
    return "yes"


#: The columns of `annotations/**/annotations.csv` at schema 3, in file order.
#:
#: They mirror the model run's own fields one for one, which is the property
#: that makes the two layers commensurable and the reason a change to either is
#: a change to both. `rationale` is required and is one sentence on why the
#: position and the case decision are what they are; `comment` stays free-form
#: for everything else, including the pair a compound referent leaves behind.
ANNOTATION_FIELDS = (
    "occurrence_id",
    "schema_version",
    "lexicon_version",
    "coder",
    "coded_at",
    "verdict",
    "source_checked",
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
    "referent_source",
    "accused_actor",
    "victim_group",
    "own_state_accused",
    "salience",
    "evidence_start",
    "evidence_end",
    "rationale",
    "confidence",
    "comment",
)


#: Fields a false positive must answer with `not_applicable`.
CASCADE_FIELDS: Final = (
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
    "referent_source",
    "own_state_accused",
    "salience",
)

#: Fields a false positive must leave empty.
FREE_TEXT_CASCADE_FIELDS: Final = ("accused_actor", "victim_group")

#: Fields in which `not_applicable` means "false positive" and nothing else.
#:
#: A strict subset of :data:`CASCADE_FIELDS`, and the three left out are left
#: out deliberately. `referent_source`, `own_state_accused` and `salience` each
#: have a real "there is nothing here to record" answer — no referent to place,
#: no one accused, no occurrence to weigh — which is a fact about the passage
#: and not about the verdict. Sharing one spelling with the cascade is a smaller
#: cost than a fourth value in three vocabularies.
RESERVED_FIELDS: Final = (
    "quotation",
    "concrete_case",
    "speaker_position",
    "function",
    "referent",
)
