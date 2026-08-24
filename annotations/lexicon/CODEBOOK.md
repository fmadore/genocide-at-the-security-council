# Lexicon audit codebook

Version 2 — 24 August 2026

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
