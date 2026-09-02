# Lexicon audit codebook

Codebook version 2.2 — 2 September 2026. Annotation schema version 2, unchanged: no field
definition has moved since 24 August 2026. The controlled referent list is at version 2 and
carries its own version columns, so a run coded against version 1 stays readable. See the
changelog at the end.

## Purpose and unit

Code one sampled term occurrence, not an entire speech and not whether the underlying event
legally constitutes genocide. The task is to determine whether the configured pattern found
the expression it claims to find and, where it did, describe what that expression is doing
in this passage.

Read the supplied context first. Consult the complete speech when the context is insufficient.
Set `source_checked=yes` only after consulting the original UN record, not merely the corpus
transcription. Use `uncertain`, `unclear`, and low confidence rather than guessing.

Do not edit generated files under `data/interim/`. Copy the occurrence ID and sampling
metadata into the versioned `annotations.csv`; never change an ID.

## Administrative fields

- `occurrence_id`: exact generated identifier.
- `schema_version`: `2`.
- `lexicon_version`: the candidate's value.
- `coder`: stable coder name or pseudonym.
- `coded_at`: ISO date, `YYYY-MM-DD`.
- `source_checked`: `yes` or `no`.
- `confidence`: `high`, `medium`, or `low`.
- `comment`: optional explanation, especially for `uncertain`, `unclear`, OCR damage, or a
  proposed new referent.

## Verdict

Choose exactly one:

- `true_positive`: the highlighted span is a real instance of the configured expression.
  Example: “acts of genocide” matched by the genocide pattern.
- `false_positive`: the string does not instantiate the expression. Example: damaged OCR
  joins unrelated fragments into something matching a tolerant pattern.
- `uncertain`: the available transcription/source does not permit a defensible decision.
  Example: severe OCR damage remains illegible in the scanned record.

For `false_positive`, set quotation, stance, function, and referent to `not_applicable`.
Still record an evidence span covering the candidate string. For `true_positive` or
`uncertain`, `not_applicable` is forbidden.

## Quotation

Choose exactly one:

- `not_quoted`: the current speaker uses the expression in their own formulation.
- `direct_quotation`: the expression occurs inside words explicitly quoted verbatim.
- `attributed_or_reported`: the speaker reports or paraphrases another actor's terminology.
- `unclear`: attribution cannot be resolved from the available passage.
- `not_applicable`: false positives only.

Examples: “We consider these acts genocide” is `not_quoted`; “the witness called it
‘genocide’” is `direct_quotation`; “the Commission described the acts as genocide” is
`attributed_or_reported`. Quotation does not determine stance: a speaker may quote a claim
in order to reject it.

## Stance

Choose exactly one:

- `asserts`: endorses or advances the characterization.
- `attributes_or_reports`: reports a characterization without clear endorsement.
- `rejects_or_denies`: disputes, rejects, or denies the characterization.
- `hypothetical_or_conditional`: presents it as a possibility, threshold, warning, or
  condition rather than an established characterization.
- `neutral_legal_reference`: refers to law, a treaty, a definition, jurisdiction, or a
  formal category without characterizing a concrete case.
- `unclear`: evidence supports no reliable choice.
- `not_applicable`: false positives only.

Examples: “This is genocide” is `asserts`; “the delegation alleged genocide” is
`attributes_or_reports`; “there was no genocide” is `rejects_or_denies`; “unless prevented,
this could become genocide” is `hypothetical_or_conditional`; naming the Genocide Convention
while discussing ratification is `neutral_legal_reference`.

## Rhetorical function

Choose one or more labels separated by `|`, without spaces or repeated labels:

- `accusation_or_qualification`: names or legally characterizes conduct.
- `warning_or_prevention`: warns of risk or urges prevention/protection.
- `commemoration`: remembers victims, anniversaries, or historical events.
- `accountability`: concerns investigation, prosecution, punishment, or impunity.
- `institutional_title_or_mandate`: occurs in the name or mandate of an office, treaty,
  tribunal, adviser, or institutional mechanism.
- `other`: a clear function not represented above; explain in `comment`.
- `unclear`: function cannot be determined.
- `not_applicable`: false positives only.

Example: “Prosecute those responsible for genocide so that it never happens again” may be
`accountability|warning_or_prevention`. `unclear` and `not_applicable` cannot be combined
with another label. Prefer the smallest defensible set; do not infer purposes absent from
the text.

## Referent

Choose one identifier from `referents.csv`:

- `other`: the referent is identifiable but not yet controlled; propose an ID in `comment`.
- `unclear`: the passage does not identify it reliably.
- `not_applicable`: false positives only.

The controlled list will grow through reviewed additions during the pilot. Do not type a
new place, conflict, people, or institution directly into `annotations.csv`; add it to
`referents.csv` first so spelling variants cannot silently fragment one referent.

`referents.csv` is now seeded rather than empty: the situations argued before the Council, the
memory cases that predate the corpus, and the meta referents a passage carries when it names no
case at all. It also carries three descriptive columns — `kind`, `iso3` and `years` — which
place a referent and help you find it. They are documentation, not coding: choose the
identifier from the passage, exactly as before, and never from a country code or a date range.
A description says what speeches invoke, not whether the event was a genocide; that judgement is
outside this codebook.

**A passage naming two cases is coded as the first one named**, and the pair goes into
`comment` — `proposed_referent`, for a model run — as the speaker gave it. "Rwanda and
Srebrenica" is `rwanda`, "the former Yugoslavia and Rwanda" is `croatia_yugoslav_wars`.
This is a convention and not a finding: 44 of the two model runs' 641 `other` rows are such
a pair, 5% of the bucket, and they have to go somewhere consistent. The rejected alternative
was a pair referent for each combination that occurs, which would add a category per pair —
seven distinct ones appear in the runs — each carrying a handful of rows and none
comparable to the single-case referent it overlaps. Coding the first named keeps the pair
recoverable from the free text while leaving the single-case counts on one scale. Where a
passage names a case and something more specific inside it — Khojaly inside
Nagorno-Karabakh, the Yazidis inside ISIL's crimes — that is not a compound: code the more
specific identifier.

**Where a passage names a period a referent's `years` does not cover, code the referent
anyway.** The range is documentation. A 2009 speech about Gaza is `israel_palestine` because
that is what the speech is about, not because 2009 falls in a range.

### The list is versioned

`referents.csv` carries three more columns, and they are the file's own bookkeeping rather
than anything a coder chooses. `since` is the list version at which an identifier's meaning
was last set. `retired_in` is the version at which it stopped being offered; a retired
identifier is not on the list you code from, and the model annotation prompt does not render
it. `superseded_by` names what it became.

Retired rows stay in the file, and that is the point of the columns. Two paid model runs
recorded 12,184 rows against version 1, and renaming a case would otherwise orphan every row
that used the old name — 3,934 of them, and 126 more under an identifier retired without a
successor. `scripts/15_usage.py` reads a run against the
version the run recorded, refuses one that used an identifier its own list could not have
offered, and reports a superseded identifier under its successor so a version 1 run and a
version 2 run can be read side by side.

`iso3` and `years` never move `since`, because this codebook already calls both
documentation: correcting a date range cannot invalidate a run that was coded from passages.
Widening or narrowing what a description covers does move it, and adds a version.

The list version is the highest version any row mentions, so there is no separate number to
keep in step.

## Evidence span

`evidence_start` and `evidence_end` are zero-based offsets in the normalized speech body,
with the end exclusive. Select the shortest passage that supports quotation, stance,
function, and referent, while containing the matched term span. The validator rejects spans
outside the source or spans that omit the match.

Positive example: include “could amount to genocide” rather than only “genocide,” because
the modal phrase supports a conditional stance. Negative example: do not select the whole
speech merely because it contains background context. Ambiguous example: when attribution
begins in the preceding sentence, include both sentences and record why in `comment`.

## Coding procedure

1. Confirm identifiers and versions against the candidate row.
2. Read the context and expand to the speech/source as needed.
3. Code verdict before discourse fields.
4. Mark the evidence span and then code quotation, stance, function, and referent from it.
5. Record confidence and explain uncertainty.
6. Never resolve disagreement by editing another coder's row. Adjudication will preserve
   both original rows and create a separate resolved record in a later scoring phase.

Before scored coding begins, all coders must complete a shared pilot outside the scored
sample. Revisions after the pilot require a schema/codebook version change; they must not be
silently applied halfway through a sample.

## Two coders on the genocide gold sample

The genocide gold sample is coded under this codebook and this schema, but its rows live in
`annotations/genocide/annotations.csv` rather than beside the lexicon audit, because the two
answer different questions from different sampling frames.

The coder identifiers are `FM` and `JG`. Both code every sampled occurrence independently:
double coding is 100% here, not a fraction, because these rows are the whole evaluation set and
a single-coded row cannot show whether a difference is one coder's reading or a real error. The
shared pilot required above applies unchanged, and comes first.

Disagreements are adjudicated by the procedure in step 6: neither coder edits the other's row,
both originals stay in the file, and the resolution is a separate row whose `coder` is
`adjudicated`.

## Model annotations are evaluated, never merged

Model output does not enter `annotations/`. It is committed under `model_annotations/`, where a
run keeps its own model identifier and prompt, and it is compared against these human rows —
never joined into them, and never used to fill a field a coder left uncertain. Where the two
disagree, the human label is the label; the disagreement is reported as a disagreement.

## Changelog

- **2.2 — 2 September 2026.** Referent list version 2. Twelve categories the two full model
  runs asked for by name in `proposed_referent` — `israel_palestine`, `isil_iraq_syria`,
  `syria`, `croatia_yugoslav_wars`, `bangladesh`, `abkhazia_south_ossetia`,
  `afghanistan_hazara`, `khojaly`, `india_muslims`, `holodomor`,
  `apartheid_south_africa`, `crimean_tatars` — each proposed independently by both
  instruments and each naming a determinate case. Years leave the identifiers, the labels
  and the descriptions and stay in `years`: `rwanda_1994` → `rwanda`, `ukraine_2022` →
  `ukraine`, `drc_great_lakes` → `drc`. `armenian_genocide` keeps its identifier and loses
  the verdict from its label and its description, as do `bosnia_srebrenica`, `holocaust`
  and the description that becomes `rwanda`'s: the table is rendered into the annotation
  prompt, and a label that asserts the qualification can push the stance field that is
  supposed to measure it. `hypothetical_future` is retired without a successor — it is a
  modal property rather than a referent — and its rows in the committed runs are left as
  they are rather than remapped. Adds the compound rule, the three version columns, and the
  statement that a passage outside a referent's `years` still takes that referent. The
  annotation schema stays version 2 and the `referent` coding rule is unchanged.
- **2.1 — 28 August 2026.** `referents.csv` is seeded with a reviewed controlled list and gains
  the descriptive columns `kind`, `iso3` and `years`; the `referent` coding rule is unchanged.
  Adds the two-coder protocol for the genocide gold sample and states that model output is
  evaluated against human rows rather than merged into them. Schema version stays `2`.
- **2 — 24 August 2026.** Replaced the overloaded `phenomenon` column with separate verdict,
  quotation, stance, function, referent and evidence fields.
