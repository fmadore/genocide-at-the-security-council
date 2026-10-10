# Claims and their status

A guide for reviewers and collaborators. It lists each kind of figure the website
publishes, what the figure rests on, and how far it can be trusted today. State on
8 October 2026.

## Three kinds of status

| Status | Meaning | On the site |
|---|---|---|
| **Computed** | Produced by fixed, published rules from the speech text and the source's metadata, and rebuilt identically from the pinned corpus. Not a guarantee of correctness: the limits below still apply. | "Computed from the record" |
| **Model-derived, unvalidated** | Rests on labels a language model assigned, or on embeddings a model produced. No person has yet checked the labels against the text. | "Model-derived · experimental", or "Computed and model-derived" where both enter |
| **Validated** | Model labels whose accuracy has been measured on the coded gold sample and passed the thresholds of [EVALUATION_PLAN.md](EVALUATION_PLAN.md). | — |

**No figure is validated yet.** The gold sample is uncoded (0 of 469 rows), and the
model run behind every model-derived figure is partial: 4,097 of 4,133 speeches
([model_annotations/README.md](../model_annotations/README.md)).

## Limits that apply to every figure

- **Counts are minimums** of words in the English record: scanning can damage a
  word, and no measure of scanning quality by decade exists.
- **The record is English.** For speakers of other languages, *genocide* is the UN
  translator's word.
- **Formal meetings only.** Informal consultations leave no record.
- **No lexicon term has a measured precision**, and recall is not estimated. The
  pattern for *genocide* is narrow, but this has not been checked by sampling.
- **A state label is not a government**, a leader or a policy.

Details: [CORPUS.md](CORPUS.md#limitations-that-must-remain-visible).

## Figure by figure

### Overview and Chronology

| Figure | Rests on | Status |
|---|---|---|
| Occurrences and share of speeches, 1946–2024 | Lexicon matches of `g[eé]nocid*` (step 03), counted per year against all speeches held (step 04); Wilson intervals; the change-point test | Computed |
| The vocabulary, word by word | The same, for every lexicon term | Computed |
| The word list over time | Annual or quarterly counts and rates per term, with Wilson intervals and intervals from resampling whole meetings; an optional overlay of dated events | Computed. The events (`config/events.csv`) are hand-chosen context from primary sources, not explanations; eight legal milestones still need their dates checked ([VALIDATION.md](VALIDATION.md), "Primary-source chronology overlay"). |
| Composition and use (drawn under the chronology) | The change in the speech rate split into agenda composition and use within agenda items | Computed |
| Testing for a change in the rate | A search for the year the rate changes most, tested against shuffled meetings and corrected for the number of tests | Computed. "No accepted split" means not enough evidence under the test, not a constant rate. |
| The vocabulary's calendar; The same twelve months, pooled | Monthly counts and rates; months with too few speeches have no rate | Computed |
| Who says it, and in what debate | Rates by speaker group and agenda category | Computed |
| The reading set, year by year | Speeches and meetings that use the word, the vocabulary, or belong to a debate where it is used (step 09) | Computed |

### Words in context (Language page)

| Figure | Rests on | Status |
|---|---|---|
| What the word is doing | Seventeen grammatical constructions found by fixed patterns around each occurrence (step 17) | Computed. No person has yet read a sample of the classifications, and occurrences that match no construction form a residue whose share drifts over time. |
| The words that sit near a term; The profile of a term; The same word in two mouths | Collocates within a window, filtered by G² ≥ 10.83 and ranked by logDice (step 05) | Computed. The G² cut-off is a filter, not a significance test of each word. |
| Compared with a like-for-like speech | Keyness of genocide-bearing speeches against matched speeches from the same stratum (step 05) | Computed. The matched controls are a seeded draw; the stability block shows how much the list varies between draws. |
| Which terms travel together | Co-occurrence of lexicon terms in speeches; pairs linked by the lexicon's own definitions are left out | Computed |

### Actors

| Figure | Rests on | Status |
|---|---|---|
| The reading set, by delegation | Step 09's reading sets per source affiliation | Computed |
| Speakers by rate | Each affiliation's rate against its own speeches; rates withheld below 125 speeches (step 11). The map is navigation only. | Computed |
| What a delegation says that the room does not | Keyness of a delegation's speeches against matched speeches by others (step 12) | Computed. Translation affects delegations that did not speak English. |
| Who held a seat when they spoke | The source's permanent and elected member flags, per speech | Computed |

### Concordance and Reader

| Figure | Rests on | Status |
|---|---|---|
| Keyword in context | Every lexicon match, with its sentence and context (step 08) | Computed |
| Keyword in context, filtered by referent | The model's referent label for each occurrence (step 15) | Model-derived, unvalidated |
| The meeting reader | The source's speech text, with matches highlighted at their recorded positions | Computed (the text is the source's) |

### Usage (model labels)

Every figure on this page rests on the published Qwen run: prompt v3, partial, no
human check.

| Figure | Rests on | Status |
|---|---|---|
| Which genocide each delegation means | The model's `referent` for each occurrence, counted per delegation; only occurrences the model called a use of the word, with a located evidence quote | Model-derived, unvalidated |
| When each delegation first said it | The earliest dated occurrence per delegation and referent for three milestones: first use, first assertion, first rejection. Once a comparison run is published, referents whose labels are unstable between the two models are withheld. | Model-derived, unvalidated. A first is a minimum over dates, so one wrong label moves it; the list of firsts has not been checked ([VALIDATION.md](VALIDATION.md), check 6a). |
| Who rejects the word | The model's `speaker_position: rejects`, counted per delegation | Model-derived, unvalidated. **Decided by FM, 9 October 2026:** until the gold sample measures how often `rejects` is right, the figure shows plain counts per delegation, without the "unusual" markers and without ordering by rejection share. The markers return only when `rejects` passes the threshold in [EVALUATION_PLAN.md](EVALUATION_PLAN.md). The prompt's rule that sends "allegations of genocide" to `rejects` is itself under review ([INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md)). |
| The contested passages | Where a second model labels an occurrence differently | Not shown: no comparison run is published. When shown, it measures stability between two models, never accuracy. |
| Agreement and accuracy tables | The coded gold sample | Waiting: nothing coded |

### Similar speeches (semantic map)

| Figure | Rests on | Status |
|---|---|---|
| Semantic map | Embeddings of every speech from Qwen3-Embedding-0.6B, projected to two dimensions (steps 06 and 21) | Model-derived, experimental. Diagnostics: neighbour recall@10 0.9742 against exact search; trustworthiness 0.8000 on a 1,000-speech subsample. Distance on the map is not diplomatic alignment or shared meaning ([PLAN.md](PLAN.md#4-optional-topics-and-embeddings)). |

## Downloads

Every CSV download and image carries its provenance: the step that produced it,
the analysis hash, the commit and the input checksums. Downloads of model-derived
figures name the model and run, but do not yet state that the labels are
unvalidated and the run partial (review of 8 October 2026, A1). Anyone quoting
such a download should quote its status with it.

## When this guide changes

Update a row when its status changes: when the gold sample is coded and a category
passes or fails the evaluation plan, when a comparison run is published, or when a
figure is withdrawn. The decision rules are in
[EVALUATION_PLAN.md](EVALUATION_PLAN.md), section 9.
