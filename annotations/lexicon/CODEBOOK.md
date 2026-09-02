# Lexicon audit codebook

Codebook version 3 — 2 September 2026. **Annotation schema version 3**: `stance` becomes
`concrete_case` and `speaker_position`, and six fields are added. The controlled referent
list is at version 2 and carries its own version columns. Both versions are readable side by
side — a file or a run coded against schema 2 is translated onto this vocabulary rather than
refused, and the aggregation says what the translation could not answer. See the changelog
at the end.

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
- `schema_version`: `3`.
- `lexicon_version`: the candidate's value.
- `coder`: stable coder name or pseudonym.
- `coded_at`: ISO date, `YYYY-MM-DD`.
- `source_checked`: `yes` or `no`.
- `confidence`: `high`, `medium`, or `low`.
- `rationale`: **required**, one sentence, free text. Why the position and the case
  decision are what they are — what in the passage decided them, not a restatement of the
  labels. Where you hesitated between two values, name the other one. It is what an
  adjudicator reads when two coders differ, and it costs a sentence.
- `comment`: optional explanation, especially for `uncertain`, `unclear`, OCR damage, a
  proposed new referent, or the pair a compound referent leaves behind.

## Verdict

Choose exactly one:

- `true_positive`: the highlighted span is a real instance of the configured expression.
  Example: “acts of genocide” matched by the genocide pattern.
- `false_positive`: the string does not instantiate the expression. Example: damaged OCR
  joins unrelated fragments into something matching a tolerant pattern.
- `uncertain`: the available transcription/source does not permit a defensible decision.
  Example: severe OCR damage remains illegible in the scanned record.

For `false_positive`, set quotation, `concrete_case`, `speaker_position`, function,
referent, `referent_source`, `own_state_accused` and `salience` to `not_applicable`, and
leave `accused_actor` and `victim_group` empty. Still record an evidence span covering the
candidate string, and still write a rationale: the claim "this match is not the word being
used" is a claim about a passage and is unreadable without the passage.

For `true_positive` or `uncertain`, `not_applicable` is forbidden in quotation,
`concrete_case`, `speaker_position`, function and referent. It is *permitted* in
`referent_source`, `own_state_accused` and `salience`, where it means "there is nothing here
to record" — no referent to place, no one accused, no occurrence to weigh — which is a fact
about the passage and not about the verdict.

## Quotation

Choose exactly one:

- `not_quoted`: the current speaker uses the expression in their own formulation.
- `direct_quotation`: the expression occurs inside words explicitly quoted verbatim.
- `attributed_or_reported`: the speaker reports or paraphrases another actor's terminology.
- `unclear`: attribution cannot be resolved from the available passage.
- `not_applicable`: false positives only.

Examples: “We consider these acts genocide” is `not_quoted`; “the witness called it
‘genocide’” is `direct_quotation`; “the Commission described the acts as genocide” is
`attributed_or_reported`. Quotation does not determine position: naming the source of a
characterization says where it came from and nothing about whether this speaker adopts it. A
speaker may quote a claim in order to endorse it, to reject it, or to leave it standing
unjudged, and those are three values of `speaker_position` with one value here.

## Concrete case

Answer this before `speaker_position`. Choose exactly one:

- `yes`: the word is applied, in this passage, to a determinate situation, event, people or
  place — a case that could be named. It need not be named in the passage; see
  `referent_source`.
- `no`: the word is not applied to any case here. It names the crime as a legal category,
  sits inside the title or mandate of an office, a treaty or a tribunal, or stands in a
  general formula about prevention or atrocity.
- `unclear`: the passage does not let you tell which.
- `not_applicable`: false positives only.

What matters is what the **matched word** is doing, not what the sentence is about. “This
crime is forbidden by the 1948 Convention on the Prevention and Punishment of the Crime of
Genocide” is a sentence about a concrete crime in which the matched word occurs only inside
a treaty's title: `no`.

This field is version 3's central change, and it exists because version 2 asked the same
question three times and let a coder answer it differently each time. Stance
`neutral_legal_reference`, function `institutional_title_or_mandate` and the three non-case
referents were all asking "is this an abstract or legal mention?", and the largest label
confusions in the two model runs were exactly those pairs. Measured after the fact: 800 rows
of one committed run and 535 of the other record a position on a passage whose own referent
says no case is in view. Make the decision here, once.

## Speaker position

Choose exactly one:

- `asserts`: advances or endorses the characterization, or treats it as established. Also a
  legal status the speaker treats as settled — “those convicted of genocide by the ICTR”,
  “known génocidaires” — because a speaker who reasons from a finding has adopted it.
- `rejects`: disputes, denies or refuses the characterization, including marking the label as
  false while reporting it.
- `conditional`: presents it as a possibility, risk, threshold or warning rather than as an
  established characterization.
- `reports_without_position`: use **only** when the passage names the actor doing the
  characterizing **and** the speaker neither adopts nor rejects it. Both halves are required.
  If the characterizing actor is not named, the speaker is speaking in their own voice. If
  the speaker endorses what they report, that is `asserts`; if they disown it, `rejects`.
- `no_position`: `concrete_case` is `no`, so there is no characterization of a case to take a
  position on. Use this exactly when `concrete_case` is `no`, and never otherwise.
- `unclear`: evidence supports no reliable choice.
- `not_applicable`: false positives only.

`concrete_case: no` and `speaker_position: no_position` are one decision under two names, and
a row carrying one without the other is refused.

Examples: “This is genocide” is `asserts`; “unless prevented, this could become genocide” is
`conditional`; “there was no genocide” is `rejects`; “the Commission described the acts as
genocide”, with the speaker taking no side, is `reports_without_position`; naming the Genocide
Convention while discussing ratification is `no_position` with `concrete_case: no`.

**Distancing.** Ask what the hedge scopes over. Over the *label* — scare quotes, “so-called”,
“supposed”, “what X calls genocide”, “allegations of genocide” — the speaker is holding the
characterization at arm's length as somebody else's and declining it: `rejects`. Marking a
label as false is a position, not the absence of one. Over a *person or an act*, with the
category untouched — “alleged genocide financier”, “accused of genocide” — that is an unproven
charge inside a category the speaker treats as real: `asserts`. The two model runs split
almost exactly along this line on the 78 occurrences the frames codebook marks as distancing.

**Commemoration is assertion.** A commemorative formula — an anniversary, a remembrance, “we
honour the victims of the genocide” — treats the characterization as established, so its
position is `asserts` even where the passage accuses no one.

## Who, whom, and how much

- `referent_source`: `passage`, `speech`, `header`, or `not_applicable`. Where you found the
  referent: in the passage around the occurrence, elsewhere in the speech, or only in the
  speaker and agenda lines above it. `not_applicable` for a false positive and for referent
  `unclear`. This measures the coding and not the passage — record what you actually used.
- `accused_actor`: free text, a few words, as the passage names them. Empty when the passage
  accuses no one.
- `victim_group`: free text, a few words, as the passage names them. Empty when it names
  none. Both are copied from the passage and never inferred from the case: “genocide in
  Rwanda” with neither perpetrator nor victims named leaves both empty, and that is data.
- `own_state_accused`: `yes`, `no`, or `not_applicable`. Whether the speaker's own State or
  organisation is the one accused, or the one that would be accused if the characterization
  stood. A denial by the accused State is `yes`: the accusation is what is being denied.
- `salience`: `passing`, `substantive`, or `not_applicable`. `passing` where the word appears
  in a list, a formula or an aside the passage does not argue about — the four-crime
  responsibility-to-protect formula and the triad “genocide, war crimes and crimes against
  humanity” are passing. `substantive` where the characterization is what the passage is
  doing.

## Rhetorical function

Choose one or more labels separated by `|`, without spaces or repeated labels:

- `accusation_or_qualification`: names or legally characterizes conduct.
- `warning_or_prevention`: warns of risk or urges prevention/protection.
- `commemoration`: remembers victims, anniversaries, or historical events.
- `accountability`: concerns investigation, prosecution, punishment, or impunity — a
  proceeding, an arrest, a sentence, a fugitive, an amnesty. Not merely because a court is
  named: “genocide denial by ICTR defence lawyers” accuses the deniers and concerns no
  proceeding.
- `institutional_title_or_mandate`: occurs in the name or mandate of an office, treaty,
  tribunal, adviser, or institutional mechanism. This restates `concrete_case: no` rather
  than finding something new: a word inside a title is applied to no case.
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
  Where `concrete_case` is `no`, choose among the three non-case referents in this order,
  first match winning: the institutional title or mandate, then the Convention and the legal
  definition, then genocide in general.
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
with the end exclusive. Select the shortest passage that supports quotation,
`concrete_case`, `speaker_position`, function and referent, while containing the matched
term span. The minimum is the clause carrying the modal or the attribution — whatever it is
that makes the position label what it is. The validator rejects spans
outside the source or spans that omit the match.

**A false positive needs a span too.** "This match is not the word being used" is a claim
about a passage and is unreadable without it, so the cascade that sets the discourse
fields to `not_applicable` stops at the evidence and at the rationale: record the span that shows the match is not
a use. Three rows of the first model run answered this field with the literal string
`not_applicable`; `14` and `16` now refuse such a row rather than write it.

Positive example: include “could amount to genocide” rather than only “genocide,” because
the modal phrase is what makes the position `conditional`. Negative example: do not select the whole
speech merely because it contains background context. Ambiguous example: when attribution
begins in the preceding sentence, include both sentences and record why in `comment`.

## Coding procedure

1. Confirm identifiers and versions against the candidate row.
2. Read the context and expand to the speech/source as needed.
3. Code verdict before discourse fields.
4. Mark the evidence span, then code `concrete_case` from it, then everything else.
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

The sample is drawn in three frames and the `sampling_frame` column of the candidate file says
which one a row came from. **Code them alike and read them apart.** The `probability` frame is
an equal-probability draw and is the only one that estimates anything about the corpus; the
`coverage` frame guarantees that every period and usage cue is seen at all; the `disagreement`
frame is a purposive over-sample of the occurrences the two committed model runs read
differently, and exists so that a rare class has enough rows to be measured. Their inclusion
probabilities differ by a factor of seven, so a figure computed over the union of them
estimates nothing, and `15_usage.py` reports the frames separately for that reason.

**The frame is not a hint.** A row's stratum records why it was drawn — that a model called it
a rejection, that its referent predates the case it names — and never what to write in it. It
is the same rule the usage cue has carried since the sample was first drawn, applied to a
second kind of sampling device.

Disagreements are adjudicated by the procedure in step 6: neither coder edits the other's row,
both originals stay in the file, and the resolution is a separate row whose `coder` is
`adjudicated`.

## Model annotations are evaluated, never merged

Model output does not enter `annotations/`. It is committed under `model_annotations/`, where a
run keeps its own model identifier and prompt, and it is compared against these human rows —
never joined into them, and never used to fill a field a coder left uncertain. Where the two
disagree, the human label is the label; the disagreement is reported as a disagreement.

Drawing a *sample* from what two runs disagree about is the one use of model output that does
not breach this, and it is worth saying why. A sampling frame decides which passages a human
reads; it cannot decide what the human writes, and the inclusion probability it records is what
lets a later step weight the sample back or decline to. The rule the frame must not break is
the one above: no row of `annotations/` is written, cleared or suggested by any run.

## Changelog

- **3 — 2 September 2026.** Annotation schema version 3, and the first field change since
  24 August. `stance` becomes two fields: `speaker_position` records what the speaker does
  with the characterization, and `concrete_case` records whether the word is applied to a
  case at all. The two are locked at one value — `concrete_case: no` if and only if
  `speaker_position: no_position` — so the abstract-or-concrete decision is taken once
  instead of competing with itself across stance, function and the referent, which is what
  the review of 1 September 2026 (§4.2) found version 2 doing and what 800 rows of one
  committed run and 535 of the other measure. `attributes_or_reports` becomes
  `reports_without_position` and is defined positively — the characterizing actor is named
  *and* the speaker neither adopts nor rejects it — with a settled legal status counted as
  an assertion. Six fields are added: `referent_source`, `accused_actor`, `victim_group`,
  `own_state_accused`, `salience` and a required one-sentence `rationale`. The distancing,
  commemoration and accountability rules are written down; two of the three state what both
  committed runs already do, which makes them testable rather than new.

  A file or a run coded against schema 2 is read at its own version and translated onto this
  vocabulary, never refused. Four of the five position values are renames.
  `neutral_legal_reference` becomes `no_position` and is the only one that also fixes
  `concrete_case`. The six added fields have **no image in schema 2 at all**: they are
  reported as absent for the whole run rather than guessed at, and closing that gap is what
  a run against prompt v2 buys.

- **2.2 — 2 September 2026.** Two changes on one day, neither of which moves a field or a
  controlled value, so the annotation schema stays `2`.

  Referent list version 2. Twelve categories the two full model
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
  `referent` coding rule is unchanged.

  The genocide gold sample gains a third sampling frame,
  `disagreement`, drawn from the strata the two committed model runs read differently, and the
  two-coder section states how the three frames are read apart. A false positive requires a
  located evidence span exactly as a true positive does — the rule was always here, under
  *Evidence span*, and `14`/`16` now enforce it at the point a row is written.
- **2.1 — 28 August 2026.** `referents.csv` is seeded with a reviewed controlled list and gains
  the descriptive columns `kind`, `iso3` and `years`; the `referent` coding rule is unchanged.
  Adds the two-coder protocol for the genocide gold sample and states that model output is
  evaluated against human rows rather than merged into them. Schema version stays `2`.
- **2 — 24 August 2026.** Replaced the overloaded `phenomenon` column with separate verdict,
  quotation, stance, function, referent and evidence fields.
