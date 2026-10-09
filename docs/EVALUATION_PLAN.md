# Evaluation plan for the gold sample

> **Proposal — to be decided by FM and JG before coding starts.**
> Drafted 9 October 2026. Everything below is a proposal with options, except the
> two points marked **Decided**, which FM settled on 9 October 2026.

The gold sample is the only measure of whether the model's labels are right. This
plan fixes, before anyone codes a passage, what will be measured, what counts as
good enough, and what happens to a published figure that falls short. Writing
the rules first matters: a threshold chosen after seeing the results can always
be made to fit them.

Once FM and JG have decided, replace the banner above with the date of the
decision and commit the plan before the first scored row is written.

## Contents

1. What is evaluated
2. First decision: instrument v3 or v4
3. Freeze the sample before coding
4. The 59 passages already reviewed (decided)
5. Keeping the coders independent
6. Agreement between the two coders
7. Suggested thresholds for agreement
8. Model accuracy, category by category
9. What happens to a figure that fails
10. Adjudication
11. What is reported
12. Decisions needed

## 1. What is evaluated

**The sample.** Step 13 drew it on 24 September 2026: 469 rows over 453 distinct
occurrences of *genocide*, in three sampling frames ([VALIDATION.md](VALIDATION.md),
open check 6).

| Frame | Rows | What it is for |
|---|---:|---|
| `probability` | 120 | Every occurrence had the same chance. The only frame that estimates anything about the corpus on its own. |
| `coverage` | 80 | One occurrence per decade and usage cue, then a random fill, so every period is seen. |
| `model_strata` | 269 | Over-samples the labels the published run assigns rarely: 100 `rejects`, all 9 occurrences dated before the first year of the referent the model gave them, 40 `other`, 60 `reports_without_position`, 60 `conditional`. |

The ten occurrences behind the prompt's worked examples are outside every frame,
because their labels were dictated to the model.

**The coders.** FM and JG each code every occurrence independently, under
[the codebook](../annotations/lexicon/CODEBOOK.md) (codebook 3, annotation
schema 3, referent list 2). Rows go only into
`annotations/genocide/annotations.csv`, which holds its header row and nothing
else on 8 October 2026: 0 of 469 rows are coded.

**Two questions, kept apart.**

- *Reliability:* how far two careful readers agree when they apply the codebook.
  This measures the codebook, not the model.
- *Accuracy:* how far the model's label matches the human reference label. This
  measures the model, and only makes sense on fields where the humans agree well
  enough.

**What is already computed.** Step 15 (`scripts/lib/usage.py`) already produces,
once rows exist:

- between the coders, per field: observed agreement, Cohen's κ (withheld when one
  coder used a single label for more than 99% of rows), PABAK (agreement corrected
  against an even spread over the codebook's categories), and, for the
  multi-label `function` field, Krippendorff's α with the MASI distance and κ per
  label;
- model against the human reference: accuracy, per-class precision, recall and F1
  (rates withheld below 20 reference occurrences, counts always shown), macro and
  weighted F1, the abstention rate, and the share of occurrences left without a
  reference because the coders disagreed;
- weighted to the corpus: the model's accuracy per field, weighting each coded
  occurrence by its chance of being drawn under the three frames together, and
  corrected corpus shares for `concrete_case` and `speaker_position`. Both wait
  until at least 30 occurrences have a reference label.

**Not yet computed:** Krippendorff's α for the single-label fields, and intervals
(bootstrap or other) for κ and α. Section 6 proposes adding both.

## 2. First decision: instrument v3 or v4

The published Qwen run and the Gemma comparison run both use prompt v3 and
codebook 3. The proposed instrument v4
([INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md)) splits `rejects` into
`denies` (the speaker says there was no genocide) and `distances` (the speaker
holds the word at arm's length: "so-called genocide", "allegations of
genocide").

This has to be settled before coding, for two reasons:

- The codebook says that a revision after the pilot needs a new codebook version
  and must not be applied halfway through a sample (CODEBOOK, "Coding
  procedure"). Coding 469 rows and then changing the position categories would
  mean recoding the field.
- A human `rejects` under codebook 3 cannot be turned into `denies` or
  `distances` afterwards; only a reader can tell which it was. The reverse is
  mechanical: `denies` and `distances` together make `rejects`.

**Options.**

- **A. Code under codebook 3 now.** The published v3 runs are scored as they are.
  A v4 instrument becomes a later revision with its own pilot, and the
  `speaker_position` field of the gold sample would have to be recoded for it.
- **B. Settle codebook 4 first, then code under it.** Run the v4 pilot
  (INSTRUMENT_V4_PROPOSAL, section 4), then code the gold sample under codebook 4.
  The v3 runs are still scored, by merging `denies` and `distances` back into
  `rejects`. A future v4 run is scored on the same rows without recoding. Costs a
  pilot round before coding starts.
- **C. Code under codebook 3, with one added column** recording, for every row
  coded `rejects`, whether it denies or distances. Keeps codebook 3's categories
  for scoring v3, and keeps the v4 distinction for later. Adding a column is a
  schema change, so the schema version moves before coding starts.

Whichever is chosen, the shared pilot outside the scored sample comes first, as
the codebook requires.

## 3. Freeze the sample before coding

The sample is not stored in the repository. Step 13 redraws it on every build,
deterministically, from three inputs: the occurrence population (the lexicon),
the run named in `model_annotations/genocide/current_run.txt`, and the run named
in `comparison_run.txt`. Two foreseeable changes would redraw a different sample
under the coders:

- Naming the Gemma run in `comparison_run.txt` makes step 13 replace the
  `model_strata` frame with a `disagreement` frame cut from where the two runs
  differ.
- A change to the `genocide` pattern changes the population.

**Proposal.** Before the first scored row:

1. Record the identity of the drawn sample: the SHA-256 checksums of
   `genocide_gold_packet.csv`, `genocide_gold_candidates.csv` and
   `genocide_gold_design.csv`, which step 13's manifest already lists. Write them
   into this plan.
2. Keep a copy that cannot be overwritten. Options: archive the three files in
   the first release ([RELEASING.md](RELEASING.md)), or commit a copy to the
   repository by hand under a new folder outside `data/`.
3. Until coding and adjudication are complete, do not change
   `comparison_run.txt` or the `genocide` pattern; or, if one must change, check
   that step 13 still reproduces the recorded checksums before coding continues.

## 4. The 59 passages already reviewed

**Decided (FM, 9 October 2026): the 59 passages are flagged, not dropped.** The
sample stays as drawn. Any of the 59 that fall in it are marked, and every result
is reported both with and without them.

**What they are.** On 10 September 2026, 59 occurrences from the 9 September
checkpoint of the Qwen run were read against the model's labels: the first 12 in
corpus order, examples across the position, quotation, case and function values,
and every invalid or relocated evidence quote ([PLAN.md](PLAN.md), "Decisions
from the preliminary Qwen review"). That review was an assistant's spot check,
not human gold coding. Its findings, with passage identifiers, are summarised in
PLAN.md and in the v4 proposal.

**Why they need a flag.** Anyone who has read that review has seen the model's
label and a discussion of these passages. Unlike the ten prompt examples, they
are not excluded from the sampling frames. A coder's reading of them may no
longer be independent of the model.

**Where they are identified.** `data/interim/qwen-review-sample.json` holds 59
records. Each carries an `id`, the occurrence identifier in the form
`SC00211-01-007#1` (speech identifier, `#`, the occurrence's ordinal in the
speech), with Qwen's labels, evidence quote and rationale. The `data/interim/`
folder is not under version control, so this file exists only on the machine
where the review was run.

**Proposal for carrying the flag.**

- Commit the 59 occurrence identifiers, without the labels, as a versioned list,
  so the flag can be reproduced from the repository. The pipeline change that
  reads it is planned separately.
- Report every agreement and accuracy figure twice: over all coded occurrences,
  and without the flagged ones. If the two differ by more than the interval
  width, say so beside the figure.
- Keep the flag out of the coders' packet, like the sampling frame.

How many of the 59 fall in the current sample is not known yet. The gold files
on disk date from 12 September, before the 24 September redraw, so the overlap
can only be counted against the frozen sample (section 3).

## 5. Keeping the coders independent

Proposed rules for both coders, from the pilot to the end of adjudication:

- **Do not use the public site while coding**, nor the downloaded tables. The
  site shows a model label for every passage: on the Usage page, in the contested
  passages, and through the concordance's referent filter.
- For the same reason, do not open `model_annotations/`, the files under
  `data/derived/usage/`, or the step 15 note in `notes/`.
- Code from the blinded packet, or from the offline coding page built from it
  (`python tools/coding_page.py`). The packet shows the passage and nothing about
  why it was drawn.
- Do not discuss particular passages with each other until both have finished
  coding them. Discussion belongs to adjudication.
- Write the one-sentence rationale the codebook requires for every row. It is
  what adjudication works from.

**Coding order, an open choice.** The roadmap asks for the probability frame
first, because the corpus-weighted estimates need it. But the packet hides the
frame on purpose, and pulling out the probability rows tells the coders that the
remaining rows are richer in rare labels.

- **Option 1:** code the packet in its shuffled order. Fully blind; weighted
  estimates arrive only when most of the sample is coded.
- **Option 2:** a script splits the packet into two packets, the probability
  rows first. Earlier estimates, at the cost of a small loss of blindness in the
  second packet.

## 6. Agreement between the two coders

Agreement is computed over the occurrences both coders coded, before
adjudication. It describes the sample as drawn, so it is also reported frame by
frame.

| Field | Kind | Proposed statistics |
|---|---|---|
| `verdict` | one label from 3 | observed agreement, Cohen's κ, Krippendorff's α, PABAK |
| `quotation` | one label from 5 | as above |
| `concrete_case` | one label from 4 | as above |
| `speaker_position` | one label from 7 | as above |
| `referent` | one label from 40 | as above |
| `function` | one or more labels | Krippendorff's α with MASI distance, κ per label |
| `referent_source`, `own_state_accused`, `salience` | one label each | as for single-label fields (not computed yet; proposed) |
| `accused_actor`, `victim_group` | free text | no statistic; read in adjudication |

- **κ and α together.** Cohen's κ is the familiar figure. Krippendorff's α is
  the one the thresholds below are written for, and it handles the multi-label
  field. With two coders and no missing rows the two are usually close; a large
  gap is worth a sentence.
- **Intervals.** Each κ and α gets a 95% interval from a bootstrap: draw the
  coded occurrences again, with replacement, 2,000 times, and take the middle
  95% of the results. Proposed: resample occurrences; as a check, also resample
  whole meetings, since occurrences in one debate are not independent.
- **Rare fields.** Where one coder used one label for nearly every row, κ is
  withheld (the existing rule) and PABAK is shown in its place.

## 7. Suggested thresholds for agreement

These are **suggestions**. They follow Krippendorff's widely used conventions
for α.

| α for a field | Reading | Consequence |
|---|---|---|
| 0.80 or above | firm | The human reference for this field may be used to score the model. |
| 0.67 to 0.80 | tentative | Usable, but any conclusion resting on the field is labelled tentative. |
| below 0.67 | not reliable | The field's codebook entry is revised (new codebook version, new pilot). No accuracy claim is made for the model on this field. |

To decide: judge on the point estimate, or, more cautiously, on the lower end of
the 95% interval.

## 8. Model accuracy, category by category

The model is scored against the human reference: the adjudicated label where
there is one, otherwise the label both coders agreed on. Accuracy is reported
per frame and weighted to the corpus. For each category the key quantities are:

- **precision**: of the occurrences the model put in the category, the share the
  humans also put there. This says whether a count of that category can be
  trusted;
- **recall**: of the occurrences the humans put in the category, the share the
  model found. This says whether the count misses much.

**Suggested standard for a category**, applied only on fields that reached at
least "tentative" agreement in section 7:

| Result | Condition (suggested) |
|---|---|
| passes | precision and recall both 0.80 or above, and the lower end of each 95% interval at least 0.67 |
| flagged | neither below 0.67, but not passing |
| fails | precision or recall below 0.67 |
| not measured | fewer than 20 reference occurrences in the category (the existing floor); treated as not passing |

**Which published figures rest on which categories:**

| Figure (Usage page unless noted) | Field and categories it depends on |
|---|---|
| Who rejects the word | `speaker_position`: `rejects` |
| Which genocide each delegation means | `referent`, each referent shown; `concrete_case` and `verdict` through eligibility |
| When each delegation first said it | `referent`, plus `asserts` and `rejects` for two of the three milestones |
| The contested passages | no accuracy claim: it shows where two models disagree |
| Concordance, referent filter | `referent` |
| Language page, frame triangulation | none for the frames, which are computed; the model enters only the cross-tabulation |

## 9. What happens to a figure that fails

Proposed rule, applied to each figure through the categories it depends on:

- **Passes:** the figure stays. Its caption and downloads say it was checked
  against the gold sample, with the date and the number of coded passages.
  Statistical markers (such as "unusual") are allowed.
- **Flagged:** the figure stays, with the measured precision and recall and
  their intervals beside it. No ranking or statistical marker rests on the
  category. Downloads carry the status.
- **Fails or not measured:** the figure is withdrawn from the site, or reduced to
  plain counts labelled as failing evaluation. Where corrected shares exist they
  may replace the model's own shares. The underlying data stay in the archive
  and the downloads, with their status written on them.

**Decided (FM, 9 October 2026): "Who rejects the word" shows counts only.**
Until the gold sample measures how often `rejects` is right, the figure shows
plain counts per delegation, without the "unusual" markers and without ordering
delegations by their share of rejections. The markers and the ordering return
only when `rejects` passes the threshold in section 8. The site change is made
separately.

A new model run or prompt is scored again on the same frozen sample. The human
reference does not need recoding unless the codebook changes.

## 10. Adjudication

Proposed procedure:

1. When both coders have finished (or at agreed batches), list every
   occurrence and field where they differ, with both rationales.
2. Both coders meet and discuss each one. Neither edits the other's row; both
   original rows stay in the file (CODEBOOK, "Coding procedure", step 6).
3. The agreed decision is written as a new row whose `coder` is `adjudicated`.
   **It must carry every field**, including those the coders already agreed on:
   step 15 takes an adjudicated row as the whole reference for that occurrence.
4. Where the coders still cannot agree, options: record `unclear` in the
   adjudicated row, or ask a third reader. To decide.
5. Adjudicate without looking at the model's labels. They are revealed only
   once the reference is final.
6. A codebook problem found during adjudication is written down as a proposal
   for the next codebook version. It is not applied to the current sample.

Agreement between the coders (section 6) is always computed on the original
rows, before adjudication.

## 11. What is reported

For each field: the number of occurrences, observed agreement, κ, α and PABAK
with intervals, by frame and overall, with and without the 59 flagged passages.
For the model: per-category counts and rates (rates only above the floor), the
share of occurrences without a reference label, the corpus-weighted accuracy and
the corrected shares. Every figure names the codebook, prompt and run it refers
to, and the date.

The results go into a dated entry in [VALIDATION.md](VALIDATION.md) and into the
gold block the Usage page already reads. [CLAIMS.md](CLAIMS.md) is updated so
that each affected figure shows its new status.

## 12. Decisions needed

Already decided by FM on 9 October 2026: the 59 reviewed passages are flagged
(section 4); "Who rejects the word" shows counts only until `rejects` passes
(section 9).

For FM and JG:

1. Instrument: option A, B or C (section 2).
2. How to freeze the sample (section 3).
3. Coding order: shuffled packet or probability frame first (section 5).
4. Statistics: confirm the list; add α for single-label fields and bootstrap
   intervals; occurrences or meetings as the resampling unit (section 6).
5. Agreement thresholds: confirm 0.67 and 0.80; point estimate or interval
   (section 7).
6. Model standard per category (section 8).
7. The rule for a failing figure (section 9).
8. Adjudication: how to break a deadlock (section 10).
9. Whether to compute agreement on `referent_source`, `own_state_accused` and
   `salience` (section 6).

Out of scope here: the lexicon precision audit (VALIDATION.md, open check 2),
which has its own sample and its own annotation file, and the check of the
first events on the diffusion curves (open check 6a).
