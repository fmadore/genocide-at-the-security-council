# Project focus and release gates

Updated 9 October 2026. This document holds the current position only: where the
project stands, what comes next, the gates a release must pass, and the research
decisions still in force with their reasons. Superseded status notes, job logs and
dated verification snapshots were removed on 9 October 2026; they remain in git
history (`git log -p docs/PLAN.md`) and, for measurements, in
[VALIDATION.md](VALIDATION.md).

The section numbers (§1.1, §3, §4, §5, §6, §7, §7.3, §7.5) and the item codes
(R1, R2, R7 …) are cited from code comments, so they are kept stable.

## Where the project stands — 8 October 2026

| Part | State |
|---|---|
| Corpus | Sakamoto and Matsuoka v5.0, 1946–2024, pinned by checksum ([CORPUS.md](CORPUS.md)). Lexicon v8 finds `g[eé]nocid*` in 4,136 speeches, 7,787 occurrences. |
| Published model layer | A **partial, unvalidated preview**: Qwen3.8-27B run `2026-09-08-qwen-131k`, prompt v3, 4,097 of 4,133 speeches and 7,694 of 7,747 occurrences (7,694 of 7,787 since lexicon v8). See [model_annotations/README.md](../model_annotations/README.md). |
| Comparison run | Gemma 4 31B IT, prompt v3: 4,129 of 4,133 speeches. Four speeches (two truncations, two validation failures) block the merge of its batches. Its results are not yet fetched or published; `comparison_run.txt` is empty. |
| Gold sample | Drawn on 24 September 2026: 469 rows over 453 occurrences, in three frames. **0 of 469 rows coded.** The evaluation rules are a proposal ([EVALUATION_PLAN.md](EVALUATION_PLAN.md)). |
| Semantic map | Experimental. Restored at every build from the pinned release `semantic-2026-09-11` (§4). |
| Citable release | None yet. [RELEASING.md](RELEASING.md) explains how to cut one. |
| Reviews | All code from the reviews of 19 and 24 September 2026 is in ([ROADMAP.md](ROADMAP.md)); what remains waits on a person or the cluster. The review of 8 October 2026 is being worked through ([REVIEW_2026-10-08.md](REVIEW_2026-10-08.md)). |

The site remains experimental, and the human-validation gate (§1.1) is open. No
figure resting on model labels is validated.

## Priorities

| Priority | Work | Done when |
|---|---|---|
| 1 | Decide the evaluation plan, starting with instrument v3 or v4 (R1; ROADMAP open item 2) | FM and JG have settled the open points in [EVALUATION_PLAN.md](EVALUATION_PLAN.md), the plan is committed with its date, and the sample is frozen. |
| 2 | Code and adjudicate the gold sample (H1–H2, ROADMAP open item 1) | Every row double-coded, disagreements adjudicated, results reported as the plan requires. No automated replacement for human verdicts. |
| 3 | Finish the Gemma comparison run | The four outstanding speeches are retried, the batches merge under the checks in §5, the run is fetched and inspected, and a decision on publishing it is recorded. Naming it in `comparison_run.txt` redraws the gold sample's third frame, so it waits until the sample is frozen. |
| 4 | Cut a citable preview, "v0.1 — unvalidated preview", if FM chooses | Released and archived as [RELEASING.md](RELEASING.md) describes. It does not close the release gate (§1.3). |
| 5 | Human checks outside the gold sample | First events on the diffusion curves (ROADMAP open item 3), the source checks and lexicon audit in [VALIDATION.md](VALIDATION.md). |
| 6 | R2 / R8 / R10: interpretive extensions | Wait for reviewed, validated role and referent evidence. |
| 7 | R12 / R13 / R15: editorial decisions | The purpose of disputed figures decided; Joël's signed epistemological text and approved attribution obtained. The government overlay stays unadopted. |
| 8 | S1 / S5: read the robustness results | Fragile speaker keywords and stopword leaks inspected before any strong interpretation (§6). |
| 9 | M1–M3: measured maintenance | Initial concordance transfer and startup; physical-device measurements remain open (§7). |

## Research contract

The object is vocabulary in the English UN verbatim record, not private
deliberation, untranslated speech, legal adjudication or inferred intent.
Every quantitative claim needs versioned inputs, an explicit unit, numerator and
denominator, artifact provenance, an evidence path, a stated limitation and a
test of its data contract. Model agreement measures stability, not accuracy;
agreement between the lexicon and a model is triangulation, not human validation.
[CLAIMS.md](CLAIMS.md) lists each kind of published figure and its status.

Keep the numbered Python pipeline, plain artifact files, static SvelteKit hosting
and lazy evidence loading. No backend, accounts, orchestration framework or model
registry is currently justified. Open weights on university hardware are the
chosen inference path because weights and runtime can be recorded and pinned.

### Decisions from the preliminary Qwen review (10 September 2026)

A purposive sample of 59 occurrences from the 9 September checkpoint of the Qwen
run (2,104 completed speeches, 3,608 annotation rows) was read against the
model's labels: the first 12 in corpus order, examples across the position,
quotation, case and function values, and every invalid or relocated evidence
quote. This was an assistant's spot review, not an independent human gold set or
an estimate of accuracy. The sample is in `data/interim/qwen-review-sample.json`,
which is not under version control.

**The 59 are flagged in the gold sample.** Decided by FM on 9 October 2026: any of
them that fall in the gold sample stay in it, are marked, and are reported
separately ([EVALUATION_PLAN.md](EVALUATION_PLAN.md), section 4).

**Keep what works.** SC00228-01-002#1 codes the explicit East Punjab accusation as
an assertion; SC00232-01-005#1–3 recognises India's explicit rejection;
SC00211-01-007#1–2 distinguishes general or legal references from a case
assertion. These support keeping the occurrence-level approach and separate
quotation and position fields. They do not establish corpus-wide reliability.

**First priority for a future instrument: identifiers, not labels.** Every
non-truncation rejection in that snapshot was a referent written as a display
name ("Rwanda", "Bosnia and Srebrenica") instead of an identifier. The prompt
asks for identifiers but its prose uses display labels, and one invalid referent
rejects the whole speech's response. A future instrument should constrain the
field to the pinned referent list and show examples such as `rwanda`, never
`Rwanda`. Changing the schema changes the recorded request identity, so it must
not be slipped into a current run. Do not silently relabel existing responses or
relax the referent validator.

**Second priority: contiguous evidence.** Eleven of 3,608 rows (0.30%) had
unlocated evidence, from omitted middle sentences, reordered text or corrected
spelling (SC01253-01-003#2, SC03454-02-003#1, SC04127-01-006#1,
SC01745-01-023#1). The proposed rule: one contiguous span of the source, keeping
all intervening text, never assembled from separate passages. Do not repair these
quotes by fuzzy acceptance.

**Substantive rules need coder review before revision.** The distancing rule maps
"allegations of genocide" to rejection and "accused of genocide" to assertion;
neither mapping alone establishes the speaker's view. SC00235-01-001#3 is coded
rejection where Pakistan denies accusing India's government, just before
asserting that genocide occurred (#4). SC03247-01-039#1 is coded reported speech
for "what it termed 'genocide'", despite the rule. Also review SC03656-01-005#7 (a
future threat to Zaire assigned to Rwanda, apparently from the speech's
background) and SC06880-01-031#10 (`own_state_accused=no` with no accused actor
named). These are boundary questions, to be tested on paired examples with the
human coders; [INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md) turns them
into a proposal.

**Decision.** No live prompt, queued job or annotation was changed by this review.
Qwen and Gemma stay on the same prompt v3 for the current comparison unless both
are deliberately rerun under a reviewed v4; a new prompt or schema needs a new run
identity and a fresh probe. Partial aggregates remain unsuitable for unqualified
trends.

### Reference documents

Each has one job; none is another roadmap.

- [ROADMAP.md](ROADMAP.md): what is still open from the reviews of 19 and 24
  September 2026, and an index of the finished items the code cites.
- [REVIEW_2026-10-08.md](REVIEW_2026-10-08.md): the review of 8 October 2026.
- [EVALUATION_PLAN.md](EVALUATION_PLAN.md): the proposed rules for the gold sample.
- [CLAIMS.md](CLAIMS.md): each kind of published figure and what it rests on.
- [CORPUS.md](CORPUS.md): source, schema, counts and coverage limits.
- [DATASHEET.md](DATASHEET.md): the derived dataset and its fields.
- [VALIDATION.md](VALIDATION.md): dated checks and outstanding source checks.
- [RELEASING.md](RELEASING.md) and [RUNBOOK.md](RUNBOOK.md): making a citable
  release, and what to do when the rebuild fails.
- [CLUSTER.md](CLUSTER.md): optional environments and GPU operating instructions.
- [Pipeline guide](../scripts/README.md) and [web guide](../web/README.md):
  commands and implementation contracts.
- [Human annotation store](../annotations/README.md),
  [codebook](../annotations/lexicon/CODEBOOK.md) and
  [model store](../model_annotations/README.md): versioned instruments and storage
  rules.

## 1. Validation and citable release

### 1.1 Human audit

Generated candidates and human annotations remain separate. Stable occurrence IDs
and declared sampling frames support occurrence-level and speech-level estimates,
with term-by-period coverage. Freeze and review the current sample before coding;
record verdict, source check and phenomenon independently, then adjudicate.
Publish precision and agreement with denominators and uncertainty, under the
rules of [EVALUATION_PLAN.md](EVALUATION_PLAN.md) once they are decided. A pattern
change bumps the lexicon version and reopens this gate. Occurrence identities bind
the span and matched text; `pattern_since` prevents incompatible patterns from
inheriting verdicts while unchanged patterns keep their compatibility. Lemma
sensitivity never changes the surface-form lexicon against which the audit is
conducted.

### 1.2 Source checks

Complete the manual checks in VALIDATION.md, including OCR-tolerant matches,
repaired records and continuations. Chronology annotations require primary
institutional sources and remain context rather than explanatory variables.
Use current CORPUS.md totals; distinguish speeches, meetings and documents.

### 1.3 Release gate

Before a release that claims validated results: complete the human audit and
source checks; rebuild from a clean checkout; reconcile analytical hashes apart
from timestamps and commit metadata; verify the payload and production browser
journeys; align published prose with the rebuilt figures; archive the audit and
reproducible artifacts. Citation metadata is in CITATION.cff. Code is MIT,
project-authored derived work CC BY 4.0, and source speech text remains CC0
(LICENSE-DATA.md).

A preview release, named as unvalidated, may be archived before the gate is
passed ([RELEASING.md](RELEASING.md)); it gives citations a fixed target and does
not close the gate. A passing build is never by itself a release.

## 2. Reproducible publication

The Makefile owns the deterministic build graph. Deployment verifies fresh and
cached payloads, with input-complete cache keys and caches saved only after
success. A cache is an optimisation; a clean rebuild must work without it. Retain
pinned source checksums, complete export inventories and atomic replacement
boundaries. An optional corpus mirror must preserve the original pin and checksum
checks.

Keep the hashed release environment separate from optional cluster dependencies.
GPU arithmetic is not promised bit-identical across devices; manifests record the
actual hardware and runtime. Operational instructions belong in CLUSTER.md; what
to do when a deploy fails is in [RUNBOOK.md](RUNBOOK.md).

## 3. Actor evidence

Build and validate the analytical table before drawing it. Rates disclose their
speaker-period denominators and withholding; affiliations and membership come
from the source, not map enrichment. Centroids navigate to delegations, not the
physical location of Council speech. The table remains usable if the map fails.
Evidence links open a real lexicon term and exact occurrence, stating when a
derived measure opens a broader set. Matched keyness must preserve its declared
target/control design and expose agenda composition, dispersion and limitations.
State labels do not identify governments, individuals, policy continuity or intent.
Membership is a per-speech status, not one fixed label for a delegation: preserve
the composition of permanent, elected and non-member participation over time.

Step 20 publishes annual speaker tables (S2) reconciled to corpus speeches, words
and term occurrences. Rates are withheld below 125 speeches; missing years have
zero counts and withheld rates; historical affiliations stay distinct; Wilson
bounds are labelled as speech-level and not meeting-clustered.

## 4. Optional topics and embeddings

**Decision (10 September 2026):** the question for the experimental semantic map
is speech similarity and evidence retrieval. Step 21 projects complete,
content-validated Qwen3-Embedding-0.6B vectors with a fixed-seed cosine graph and
UMAP. It reports original-space neighbour recall against exact search (minimum
0.8), plus projection trustworthiness and neighbour loss on a deterministic
1,000-speech subsample. These diagnostics are not a human interpretability score.
Colour is by source affiliation, agenda category or decade; filters preserve the
projection; related speeches come from similarity in the original vector space,
not from the drawing.

**The published release.** It covers all 167,642 speeches (167,878 chunks, 1,024
dimensions). Neighbour recall@10 is 0.9742 over 128 exact queries; on the
1,000-speech subsample (k = 25) trustworthiness is 0.8000 and neighbour loss
0.6981. UMAP's spectral initialisation fell back to seeded random initialisation,
which the release pin records. These support exploratory use with the visible
projection caveat, not claims about diplomatic alignment. Five retrieval spot
checks returned related material; that was an inspection, not a blinded relevance
evaluation.

`config/semantic-release.json` pins the release archive, its manifest and the
corpus by SHA-256. A content fingerprint binds the embedded bodies, so an
equivalent Parquet file written by another Arrow version is accepted; only a pin
matching the artifact's manifest may authorise it. Clean deployments restore and
verify the release before exporting, so the map survives cache eviction without
another GPU run. Re-embedding waits on the 24 trimmed openings (ROADMAP open
item 6).

Topic labels remain deferred. UMAP distance is not diplomatic position or shared
meaning. Compare clustering in the source embedding space and the reduced space;
inspect nearest neighbours, stability across seeds and baselines; require blinded
human interpretability or intrusion judgements alongside numerical coherence. A
machine score cannot supply the missing human judgement. Evaluation scripts
produce inspection evidence, not a release result. Generic sentiment and headline
topic maps remain out of scope.

## 5. Model-assisted interpretation

No model output may overwrite corpus text, lexicon counts or human annotations.
Archived runs from the former corpus remain historical evidence and cannot be
silently joined to current identities. Require a compatible population, unique
occurrence IDs, immutable run identity and validated row and manifest provenance.
Keep raw receipts, located evidence and failures; empty or waiting states are
valid published states. Select a publication or comparison pointer only after
inspecting the actual run. An independent comparison instrument should examine
shared model blind spots; cross-model agreement does not license accuracy claims
without the gold sample.

R4 uses prompt v3 and model schema 3.1 without self-reported confidence. R1's
future schema 4 needs a separately reviewed prompt revision. Preserve historical
schemas and prompt archives; never silently relabel old runs.

**The two instruments.** The published instrument is Qwen3.8-27B at reasoning
effort `xhigh` on one H100, context 131,072 tokens, temperature 0; full speech
text and output allowances are never trimmed. Gemma 4 31B IT, at the pinned
revision `842da3794eaa0b77d5f08bae87a17459d91ff475`, is the second model,
replacing the planned DeepSeek run, which this cluster cannot serve (the reason
is recorded in `scripts/cluster/env.sh`). Gemma's reasoning is a boolean switch
(`enable_thinking`), not a graded effort: "low" and "high" in its probe mean off
and on. It runs on two H100s per task; two L40s were tested and rejected
([CLUSTER.md](CLUSTER.md)).

**Truncation is handled by resume passes, not by changing the instrument.** On
the first 100 genocide-bearing speeches Gemma cut off 5 responses at the output
limit, against Qwen's 4 in 4,097. In the smoke test, asking again under identical
settings returned a cut-off speech complete, but not every time: SC00257-01-004
was cut off in two of three runs. Raising the output allowance would stop the two models answering
under identical limits, and switching thinking off would compare a reasoning model
with a non-reasoning one; both change the instrument. A corpus run therefore
budgets up to three passes and checks what is still outstanding after them. That
100 was a chronological head, not a random sample, so the 5% is an order of
magnitude, not a published rate. The same measurement found 3 of 182 evidence
quotes unlocated (1.6%); carry that into the run's validation.

**Fixed batches.** Model runs can be split into fixed speech batches
(`scripts/annotation_batches.py`, Slurm arrays). A plan assigns each speech once;
separate run directories keep each batch resumable. The merge requires every batch
to be complete, disjoint and instrument-compatible, and keeps source hashes and
validation counters ([CLUSTER.md](CLUSTER.md#independent-batches-for-future-models)).

## 6. Lexical and statistical follow-up

Implemented: a meeting-block change-point null, Wilson rate intervals,
meeting-clustered rate bands for speech rates, a composition decomposition,
effect-size ranking with a significance floor, dispersion, matched controls drawn
per stratum, and suppression of definitional network edges. Wilson bounds are not
meeting-clustered, and variation across control seeds is not sampling uncertainty.

**Robustness diagnostics (S1/S5).** Step 18 (`make robustness`) deletes each
meeting in turn from the matched genocide keyness comparison and compares the
current and earlier tokenizers; step 19 adds collocate and speaker profiles with
whole-meeting deletion effects and conditional 95% intervals from meeting-block
resampling; step 10 and step 18's lemma mode compare surface and lemma rankings.
The rules for reading them:

- Deletion effects are descriptive influence ranges, **not confidence intervals**
  or estimates of sampling uncertainty. Controls are held fixed, without
  rematching.
- The resampling intervals assume hypothetical exchangeable meetings; they do not
  measure uncertainty in exhaustive historical counts or rerun matching. An
  interval needs 20 nonempty meetings per arm and five word-supporting meetings
  per arm, and is withheld if more than 5% of draws are undefined. LogDice gets
  deletion ranges, not intervals.
- Exact type overlap between tokenizers or between surface and lemma lists does
  not measure semantic equivalence. Surface tables remain the published
  vocabulary; lemma results are diagnostics.
- The definitional `genocide`/`genocidal` effects are properties of target
  selection, not discoveries.

The last full run of these diagnostics (10 September 2026) predates the tokenizer
and matched-control changes of 24 September (ROADMAP RV3, RV32); its figures are in
git history and in `data/derived/{lexical_robustness,extended_robustness}/` when
built. It found vocabulary concentrated in single meetings and 25 speaker–word rows
whose sign reverses after one deletion; these need close reading before strong
interpretation.

**Remaining S1/S5:** read ranked outputs against the published interpretation;
scrutinise the fragile speaker–word findings and the lemma layer's stopword leaks.
**Deferred S3–S4:** funnel plots with meeting-clustered limits, and exact
vocabulary-intersection tables (never reconstructed from pairwise edges). **S6:**
sequential recurrence by meeting order with exact evidence links; do not call
recurrence interpersonal influence.

Later analytical specifications require a preregistered research question:
conditional vocabulary choice, translation-process sensitivity, membership
comparisons with agenda and actor/year controls, and government-change overlays.
Translation sensitivity cannot recover unmediated vocabulary. E1 joins to votes,
vetoes and resolutions need a hand-verified pilot and must preserve document
identity; association is not causation. E2's former pre-1992 extension is
superseded by the 1946–2024 corpus; independent cross-corpus replication remains
deferred and must pin sources and report overlap discrepancies.

## 7. Interface and evidence contracts

Computed, mixed and model-derived marks describe the actual selected data;
navigation marks describe page capability. Provenance is not a quality score.
Keep URL-restorable filters, exact evidence links, accessible tables, the local
basket, fullscreen figures, persistent contents and concise reading and caveat
text. Extract logic into small tested modules at behaviour boundaries, not to hit
line limits. Colour must not imply a quantity the table does not measure. Show
numerator, denominator, exclusions and uncertainty in the figure's accessible
account.

**Geography.** Enrichment accepts reviewed name variants and Unicode-equivalent
spellings without changing source labels or classifications. Nine source-state
labels still lack reviewed locations: Czechoslovakia, German Democratic Republic,
German Federal Republic, India or Netherland, Republic of Vietnam, Turkish
Federated State of Cyprus, Turkish Federated State of Kibris, Yemen Arab Republic
and Yemen People's Republic. The interface lists exclusions explicitly. Palestine
remains unmapped because the source flags classify that affiliation as `other`;
this is a dataset limitation, not a geopolitical classification by this project.
Regional-group corrections are documented in
[CORPUS.md](CORPUS.md#affiliation-and-institutional-status).

**Performance.** Browser measurements of 7 and 10 September 2026 (git history)
found that loading and startup, not JSON parsing, dominate the concordance wait.
The next performance work should target initial concordance transfer while keeping
full exports, filters and exact evidence links. Physical-device and
model-enriched payload measurements remain open.

### 7.3 Actor display safeguards

Withhold sub-minimum rate slices, never merge speakers because they share an ISO3,
and never present a centroid as the location of a speech. Charts and the accessible
table must use the same artifact and arithmetic; the map is optional navigation.

### 7.5 Export contract

Export the complete selected data, not only virtualised or paginated visible rows.
Carry filters, units, source and provenance, and caveats with CSV and image
exports; an exported image outlives its surrounding page. Navigation and
highlighting must remain correct under term, speaker, meeting and scope filters.

## Roadmap coverage

Stable IDs are kept for code references; they are not separate planning files.

| IDs | Current position |
|---|---|
| I1–I4, A1–A3 | Integrity metadata and contracts, separate candidate stores, identities and annotation machinery implemented. A4 and H1–H2 wait on the coders. |
| U1–U10 | Evidence navigation, URL state, basket, result profiles, page metadata, contents and word budgets implemented; maintain browser coverage. |
| M1–M5 | Shared boundaries, payload measurements, build-graph, cache and export repairs and lexicon-edit instructions implemented; further optimisation is evidence-driven. |
| L1–L8 / C1–C7 | Local model machinery and the cluster safeguards exist. The Qwen preview is published; the Gemma run is not yet merged; human validation is pending. Historical model runs are not current results. |
| R3–R7, R9, R11, R14 | Provenance, confidence removal, fullscreen, published referents, term-only lexicon, scope control, aggression phrase and navigation implemented. |
| R8 | Computed first stage exists; model-dependent interpretation remains gated. |
| R1, R2, R10, R12, R13, R15 | Prepared or awaiting evidence or author decisions, detailed below. |

R7 permits individual terms and declared derived measures, not aggregate register
or set counts. R9's word, vocabulary and debate sets overlap; they are not nested,
and changing the reading set does not silently change the denominator. Lexicon v6
added only the explicit crime(s) of aggression phrase, not generic aggression or
an intensity ranking.

## R2 — accuser and accused: acceptance gate

Wait for usable extracted strings, then seed a controlled accused-actor mapping
from observed evidence and have both coders review it. Cover States, armed groups,
international bodies and individuals. Never guess unmapped strings into a nearby
category. Publish an accuser-by-accused matrix with exact evidence links, a
model-derived mark, explicit missing and unmapped shares, and self-accusation
retained. Unsupported historical schemas must produce a contracted explanatory
empty state.

## R1 — situation, modality and the second referent

Run `python tools/prepare_research_review.py` to regenerate
`data/interim/research_review/candidates.json`. It selects located quotations
from archived runs, keeps occurrence identities and source hashes, and keeps
candidate cues separate from labels. These runs describe the earlier corpus;
their quotes must be checked against the corresponding source. A cue retrieves
a case for reading and does not establish what an occurrence characterises.

The proposed modality review covers armed conflict, persecution, economic
sanctions, intervention or occupation, colonial rule, famine or starvation and
forced displacement. Review the boundaries, overlap and an explicit `unclear`
option. For each candidate, both coders independently record the situation,
modality, secondary situation if any, evidence span, confidence and a boundary
note. Include negative cases where a cue appears elsewhere in the quotation.
Settle whether multiple modalities are possible before adopting a single-valued
field.

Version controlled referents with explicit successors and one group per case;
publish modality and group views with primary-only counts as the default. A
secondary identifier must differ from the primary and is forbidden for reserved
non-case identifiers. An optional primary-or-secondary view counts occurrences
once and publishes the share with a second slot. Publish modality-without-situation
coverage rather than silently dropping those rows.

Schema-4 acceptance fixtures must cover:

| Case | Required behaviour |
|---|---|
| False positive or non-case mention | Modality `not_applicable`, no secondary case |
| Sanctions named without a situation | Modality retained; missing situation counted explicitly |
| Two named cases at one occurrence | One row, distinct primary and secondary controlled identifiers |
| Three or more cases | `other` plus the explicit list, with the bounded loss counted |
| Group collapse | Every case has one group; primary-only totals remain identical |
| Old schema-2/3 run | Read through versioned successors; never infer new labels from old ones |

No modality file is installed in `annotations/`, no existing code is recoded,
and schema 4 cannot be selected for inference yet. Both coders must review the
vocabulary before a run uses it. Prompt v3 and model schema 3.1 implement only
R4; the later reviewed revision therefore needs a new prompt version rather than
overwriting v3.

## R10 — paired counter-concept study

The packet includes candidate quotations for `terroris*` and `humanitarian`.
These are seeds for vocabulary review, not an exhaustive speech-level retrieval.
The final instrument must enumerate full speech bodies: concordance windows
cannot measure speech-level co-occurrence. Add individual reviewed terms rather
than an aggregate humanitarian category.

Use the same meeting as the exact matching stratum. Within it, match genocide-
silent speeches to genocide-bearing speeches on participant type and speech
length, with deterministic tie-breaking and no replacement. Publish exclusions,
unmatched shares, length balance, and coverage by speaker and period. Hold the
referent constant only after a validated referent instrument can assign it;
never impute the referent from the fact that two speeches share a meeting.

Estimate within-pair differences in speech-level term presence. Resample whole
meetings for uncertainty, keeping all their pairs. Report how matching changes
balance and the estimate, without presenting an unadjusted figure as the answer.
Predeclare alternative length calipers and period restrictions and show their
sensitivity. A speech expressing humanitarian language establishes vocabulary,
not an intention to avoid a legal characterisation.

The two hypothesised directions require reviewed speaker-role evidence:
bystander humanitarian vocabulary and accused-party counter-accusation. Until
both can be identified and displayed under the same rules, publish neither as
confirmation. Model disagreement is instrument stability, not accuracy.

## R12 — figure-purpose decision

The current figures remain available pending the author's choice. The decision
is between keeping them with a clear reading purpose and removing the pooled
calendar and proximity views. Record a question, a concrete reading action, and
the inference that is forbidden for each kept figure. A referent-filtered
calendar additionally waits for a usable validated referent layer.

## R13 and R15 — commissioned epistemological page

Proposed route: `/epistemology`, separate from `/methods`. Do not publish or
attribute an unsigned draft to Joël. Once his text and attribution are approved,
link it from the home page and provenance legend, and update the acknowledgement
to an authorship note.

The authoring brief is:

1. Define the historical object: recorded Council speech, addressed to multiple
   audiences, with institutional conventions and an edited documentary form.
2. Explain how corpus exploration directs close reading and what aggregation
   can and cannot establish about historical language.
3. Discuss the constructed instruments: corpus selection, lexicon, regex frames,
   controlled referents, model readings, and human disagreement.
4. State that a delegation's recorded statement is not a timeless national
   position. Governments change; the dataset's state label does not identify
   a leader, cabinet, policy continuity, or intention.
5. Give the reader a concrete account of interpretive uncertainty, avoiding
   a repetition of the pipeline ledger.

Acceptance requires Joël's actual signed argument, permission for the attribution,
and editorial approval. This brief supplies structure, not words credited to him.

## Carried research questions

Revisit only with an explicit purpose: a neighbour-speech second pass over
unresolved referents; evidence-location rates as a figure; Lemkin's conceptual
vocabulary; individual delegates' circulation (requires name disambiguation); and
manual review of noisy adjacent terms such as survivors, commemoration, denial,
glorification and holocaust. Removing aggregates does not make these terms
synonymous with genocide.

## Safeguards in force

The integrity repairs of September 2026 hold these guarantees; each has
regression tests.

| Finding | Guarantee |
|---|---|
| 1 — resume identity | An immutable run identity covers the prompt, referent bytes, schema, corpus occurrence IDs, selected request bodies, runtime and passed probe. A changed instrument cannot append to a run. |
| 2 — interrupted append | A write-ahead speech transaction commits rows, failures and accounting together; a torn tail is replayed once. An operating-system advisory lock excludes a second writer. |
| 3 — reasoning probe | The probe's cache identity covers exact requests, full runtime, prompt and referents. The chosen top level must increase reasoning tokens on every paired speech and have the largest positive median. This is an operational screen, not statistical validation. |
| 4 — build graph | Referents, named runs and prompt archives invalidate their consumers; multi-output stages use grouped targets. |
| 5 — deploy and cache | The Makefile and payload contract are trigger and cache inputs; restored and rebuilt payloads undergo shape, inventory and hash checks. |
| 6 — model readers | Shared duplicate, provenance, schema and compatibility checks serve sampling and frame triangulation; aggregation uses the same row and manifest guard; joins enforce unique occurrence IDs. |
| 7 — browser cache | The service worker's caches belong to the app's base path; activation deletes only this app's old caches. |
| 8 — export boundary | Export assembles and validates a complete staged directory before replacing the previous release. |

The transaction guarantees apply once a response reaches its durable pending
record. A process killed while a request is in flight may need that request again;
token counters report received and checkpointed responses, not a provider bill.
The lock relies on filesystem advisory-lock support; run one annotator per run
directory. Partial runs without `identity.json` are not migrated by guessing their
missing inputs: preserve them and resume from their original checkout, or start a
new run ID.

## Maintaining this document

Keep it to the current position. When work changes, update the state table, the
priorities and the relevant gate. Record measurements and dated checks in
VALIDATION.md and leave execution history to git and the generated step notes;
do not add another status document. Do not mark local implementation as human
validation or a successful deployment.

Before committing, run the applicable full gates: Python pytest and Ruff;
frontend unit tests, lint and type checking; the production build for shipped
routes; browser journeys for interaction changes; producer, consumer and payload
checks for contract changes. Before a release, also complete §1.3.
