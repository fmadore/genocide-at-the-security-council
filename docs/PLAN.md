# Project focus and release gates

Updated 10 September 2026. This is the single planning and status document.
It replaces the separate improvement roadmap, dated reviews, implementation
report and research-decision packet. Historical discussion remains in Git history;
this document records the current position rather than a chronological work log.

## Current focus

Gemma 4 31B IT is now the selected second model, replacing the planned DeepSeek
run. The pinned checkpoint `842da3794eaa0b77d5f08bae87a17459d91ff475`
has been downloaded and verified on Festus. An isolated Gemma workspace passes
preflight, parser import and the full 4,133-request tokenizer budget audit
(maximum 79,303 tokens against a 131,072-token context). Gemma uses its actual
boolean `enable_thinking` control; low/high in the probe mean off/on, not a
graded effort ladder. No successful GPU inference is claimed yet.

Gemma smoke **768786** is queued after Qwen continuation **768736** ends.
Array **768787** then runs 17 fixed batches of at most 250 speeches, at most
two tasks simultaneously, with two H100s per task. It requires scheduler
success and a complete smoke manifest. Qwen completion is not implied by the
dependency: if its continuation stops incomplete, its checkpoint remains for
another resume. Recurring monitoring remains paused at the user's request.

Future model runs now support fixed speech batches through
`scripts/annotation_batches.py` and Slurm arrays. A plan assigns each speech
once; separate run directories preserve resumability. The merge requires every
batch to be complete, disjoint and instrument-compatible, retaining source
hashes and validation counters. See [CLUSTER.md](CLUSTER.md#independent-batches-for-future-models)
for submission and selective retry commands. The current Qwen run keeps its
existing identity; continuation job **768736** is queued after **760799**.
The downloaded 9 September snapshot has 2,104 completed speeches and 3,608
annotations; partial aggregation passed locally, with publication unselected.

GPU status, 8 September: smoke job **760798 passed at 08:16 CEST**: all 12
speeches and 40 occurrences annotated, zero refusals, all 40 evidence spans
located without relocation. Its nine-response reasoning probe also passed:
median reasoning tokens were 1,389 / 1,914 / 11,603 for low / medium / xhigh.
Full-corpus job **760799 started at 08:16 CEST**, after both scheduler success
and the smoke manifest's completion guard. Its target is 4,133 speeches and
7,747 occurrences; full coverage and results remain pending.

The model is Qwen3.8-27B at xhigh on one Festus H100. The OpenAI-compatible SDK
only connects to loopback vLLM. Corrected code and the current 167,642-speech
corpus are in an isolated workdir, with matching local/remote parquet SHA256.
Startup fixes bound serving concurrency to four, route SDK extensions through
`extra_body`, and set context to 131,072. A pinned-tokenizer audit of every
request found a maximum prompt-plus-output budget of 79,392 tokens. Full text
and output allowances are preserved. The full-run client timeout is one hour,
covering legitimate long responses; staged code hashes and the original smoke
client are retained alongside the logs.

Festus's operating guidance has been checked against the live environment. The
batch script now checks corpus metadata, SDK call compatibility and cached model
shards before server startup; package/compilation caches use `/workdir`, and the
server is isolated from the client overlay. The current-corpus probe and smoke
gates have passed; full-run completeness and research review remain open.

The local integrity repairs and corpus rebuild are complete. The next research
milestone is a reviewed annotation instrument and validated evidence. The Bayreuth
GPU run is in progress; no result or publication run is selected by this work.
The application remains experimental and the human-validation release gate is open.

| Priority | Work | Status and completion gate |
|---|---|---|
| 1 | C1–C7: inspect the Bayreuth result when available | Local transport, runtime, probe and recovery safeguards implemented. Verify actual probe, smoke run, weight/runtime provenance, population coverage and failures before considering publication. Do not restart the running job as part of local cleanup. |
| 2 | R1 / A4 / H1–H2: review and validate the instrument | Candidate packet prepared; both coders review vocabulary, pilot independently, revise, then code and adjudicate. No automated replacement for human verdicts. |
| 3 | R2 / R8 / R10: interpretive extensions | Wait for usable, reviewed role/referent evidence. R10's paired design is prepared below. |
| 4 | R12 / R13 / R15: editorial decisions | Decide disputed figures' purpose; obtain Joël's signed epistemological text and approved attribution. Government overlay remains unadopted. |
| 5 | S1 / S5: interpret robustness results | Full lemma layer and meeting-deletion/bootstrap tables now exist; inspect fragile speaker keywords and retain conditional interval caveats. |
| 6 | M1–M3: measured maintenance | Constrained-network results are recorded below: transfer/startup dominate parsing. Prioritize concordance loading; physical-device and real semantic-payload measurements remain open. |

## Research contract

### Preliminary Qwen prompt review — 10 September 2026

Reviewed the downloaded 9 September checkpoint, not the later live checkpoint:
2,104 completed speeches, 3,608 annotation rows, 40 rejected responses out of
2,144 returned requests. Inspected a purposive 59-occurrence sample: the first
12 in corpus order, examples across position/quotation/case/function values,
and every invalid or relocated evidence quote. This is an assistant spot review,
not an independent human gold set or an estimate of annotation accuracy. The
reproducible sample is in `data/interim/qwen-review-sample.json`; the downloaded
run and partial aggregation remain under `data/interim/festus-2026-09-09/`.

**Keep what works.** SC00228-01-002#1 codes the explicit East Punjab accusation
as an assertion; SC00232-01-005#1–3 recognizes India's explicit rejection;
SC00211-01-007#1–2 distinguishes general/legal references from a case assertion.
These examples support retaining the occurrence-level approach and separate
quotation and position fields. They do not establish corpus-wide reliability.

**First priority: IDs, not labels.** All 38 non-truncation rejections in this
snapshot are unknown referents expressed as display names (Rwanda, Bosnia and
Srebrenica, etc.). The two remaining failures are output truncations. The prompt
requests identifiers but its prose also uses display labels, while the output
schema accepts any string. One invalid referent causes the whole speech response
to be rejected. For a future instrument, constrain the field with an enum built
from the pinned current referent list, and show explicit examples such as
`rwanda`, never `Rwanda`. The list is already hashed in run provenance; it need
not be hard-coded in Python. Changing the schema still changes the recorded
request identity and must not be slipped into the current run. Do not silently
relabel existing responses or relax the referent validator.

**Second priority: contiguous evidence.** Eleven of 3,608 rows (0.30%) have
unlocated evidence. Inspection found omitted middle sentences, reordered text
and spelling changes. SC01253-01-003#2 omits an intervening rhetorical question;
SC03454-02-003#1 removes UNPROFOR's objection between the draft quotation and the
speaker's reply; SC04127-01-006#1 reverses the order of the famine description
and “For Ukraine, genocide is not just a term.” SC01745-01-023#1 changes
“Kassem” to “Kasem”. The current instruction already prohibits this, but asking
for the shortest quote supporting every field encourages compression. Proposed
clarification: one contiguous source span, retaining all intervening text; never
assemble a quotation from separate passages. If support is distributed, retain
the continuous span needed to show the attribution/position, rather than editing
it into a cleaner sentence. Do not repair these quotes by fuzzy acceptance.

**Substantive rules need coder review before revision.** The distancing rule
automatically maps “allegations of genocide” to rejection, and “accused of
genocide” to assertion. Neither mapping alone establishes the speaker's view
of the characterization. SC00235-01-001#3 is coded rejection when Pakistan
denies accusing India's government, immediately before asserting that genocide
occurred (#4): actor responsibility and acceptance of the characterization can
come apart. SC03247-01-039#1 is coded reported speech for “what it termed
‘genocide’”, despite the prompt's overly broad distancing rule. These are
instrument-boundary questions, not proof that every affected model label is
wrong. Explicit endorsement/rejection, neutral attribution and uncertainty
should be tested on paired boundary examples with the human coders.

Also flag SC03656-01-005#7: a future threat to Zaire is assigned to Rwanda,
apparently borrowing the speech's background case; review local versus wider
context. SC06880-01-031#10 gives `own_state_accused=no` while naming no accused
actor in its anniversary/justice passage; review the applicability boundary.

**Decision:** no live prompt, queued job or annotation has been changed by this
review. Prepare a small paired pilot for a proposed v4, including the failures
and these boundary cases. Measure valid-ID output, contiguous evidence and
human-reviewed field decisions separately. Keep Qwen/Gemma on the same v3 for
the current comparison unless both are deliberately rerun under a reviewed v4;
a new prompt/schema needs a new run identity and fresh probe. Human validation
remains open, and partial aggregates remain unsuitable for unqualified trends.

The object is vocabulary in the English UN verbatim record, not private
deliberation, untranslated speech, legal adjudication or inferred intent.
Every quantitative claim needs versioned inputs, an explicit unit/numerator/
denominator, artifact provenance, an evidence path, a stated limitation and a
test of its data contract. Model agreement measures stability, not accuracy;
regex/model agreement is triangulation, not human validation.

Keep the numbered Python pipeline, plain artifact files, static SvelteKit hosting
and lazy evidence loading. No backend, accounts, orchestration framework or model
registry is currently justified. Open weights on university hardware are the
chosen inference path because weights and runtime can be recorded and pinned.

Reference documentation has distinct jobs and is not another roadmap:

- [CORPUS.md](CORPUS.md): canonical source, schema, counts and coverage limits.
- [VALIDATION.md](VALIDATION.md): dated corpus checks and outstanding source checks.
- [CLUSTER.md](CLUSTER.md): optional environments and GPU operating instructions.
- [Pipeline guide](../scripts/README.md) and [web guide](../web/README.md): commands and implementation contracts.
- [Human annotation store](../annotations/README.md), [codebook](../annotations/lexicon/CODEBOOK.md) and [model store](../model_annotations/README.md): versioned instruments and storage rules.

## 1. Validation and citable release

### 1.1 Human audit

Generated candidates and human annotations remain separate. Stable occurrence IDs
and declared sampling frames support occurrence-level and speech-level estimates,
with term-by-period coverage. Freeze and review the current sample before coding;
record verdict, source check and phenomenon independently, then adjudicate.
Publish precision and agreement with denominators and uncertainty. A pattern
change bumps the lexicon version and reopens this gate. A2 occurrence identities
bind the span and matched text; `pattern_since` prevents incompatible patterns
from inheriting verdicts while unchanged patterns retain their compatibility.
Lemma sensitivity never
changes the surface-form lexicon against which the audit is conducted.

### 1.2 Source checks

Complete the manual checks in VALIDATION.md, including OCR-tolerant matches,
repaired records and continuations. Chronology annotations require primary
institutional sources and remain context rather than explanatory variables.
Use current CORPUS.md totals; distinguish speeches, meetings and documents.

### 1.3 Release gate

Before a citable tag: complete the human audit and source checks; rebuild from a
clean checkout; reconcile analytical hashes apart from timestamps/commit metadata;
verify the payload and production browser journeys; align published prose with
the rebuilt figures; archive the audit and reproducible artifacts. Citation
metadata is in CITATION.cff. Code is MIT, project-authored derived work CC BY 4.0,
and source speech text remains CC0 (LICENSE-DATA.md). A DOI/archive and citable
tag remain future release work, not a consequence of a passing build.

## 2. Reproducible publication

The Makefile owns the deterministic DAG. Deployment verifies fresh and cached
payloads, with input-complete cache keys and caches saved only after success.
A cache is an optimization; a clean rebuild must work without it. Retain pinned
source checksums, complete export inventories and atomic replacement boundaries.
An optional corpus mirror must preserve the original pin and checksum checks.

Keep the hashed release environment separate from optional cluster dependencies.
GPU arithmetic is not promised bit-identical across devices; manifests record
the actual hardware/runtime. Operational instructions belong in CLUSTER.md.

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

## 4. Optional topics and embeddings

The user has selected speech similarity and evidence retrieval as the question
for an experimental semantic map (10 September). Step 21 projects complete,
content-validated Qwen3-Embedding-0.6B vectors with a fixed-seed cosine graph and
UMAP. It reports original-space ANN recall against 128 exact queries (minimum
0.8), plus projection trustworthiness and neighbour loss on a deterministic
1,000-speech subsample. The diagnostic is not a human interpretability score.
The interface colours by source affiliation, source agenda category or decade;
filters preserve the projection, and related speeches come from original-vector
similarity, not the drawing. It includes search controls, a paginated table,
evidence links, URL restoration and a waiting state without invented points.

Embedding job **775570** is queued on Festus normal/L40. CPU projection
**775578** depends on its successful completion. Both use isolated workspace
`/workdir/$USER/unsc/analysis-2026-09-10`; annotation runs are separate.
Model revision is immutable; every speech is token-counted, decoded chunks are
rechecked against the token budget, and document prompts are empty. Schema-2
vectors carry checksums, row identity and exact body hashes. The local exporter
requires a complete, checksummed semantic artifact from the same corpus.
Until that artifact is retrieved and deliberately included in a release,
clean CI builds publish the waiting state. A durable release source for these
GPU-produced artifacts remains to be selected when the real result passes.

Topic labels remain deferred. UMAP distance is not diplomatic position or shared
meaning. Compare clustering in the source embedding space and reduced space;
inspect nearest neighbours, stability across seeds and baselines; require blinded
human interpretability/intrusion alongside numerical coherence. A machine score
cannot supply the missing human judgment. Evaluation scripts produce inspection
evidence, not a release result. Generic sentiment and headline topic maps remain
out of scope.

## 5. Model-assisted interpretation

No model output may overwrite corpus text, lexicon counts or human annotations.
Archived runs
from the former corpus remain historical evidence and cannot be silently joined
to current identities. Require a compatible population, unique occurrence IDs,
immutable run identity and validated row/manifest provenance. Keep raw receipts,
located evidence and failures; empty/waiting states are valid published states.
Select a publication/comparison pointer only after inspecting the actual run.
An independent comparison instrument should examine shared model blind spots;
cross-model agreement does not license accuracy claims without the gold sample.

R4 uses prompt v3 and model schema 3.1 without self-reported confidence. R1's
future schema 4 needs a separately reviewed prompt revision. Preserve historical
schemas and prompt archives; never silently relabel old runs.

## 6. Lexical and statistical follow-up

Implemented: meeting-block change-point null, Wilson rate intervals, effect-size
ranking with a significance floor, dispersion, matched controls and suppression
of definitional network edges. These do not complete S1/S5: Wilson bounds are not
meeting-clustered, and variation across control seeds is not sampling uncertainty.

The first S1/S5 diagnostic slice is implemented in
`scripts/18_lexical_robustness.py` (`make robustness`). It asks whether the
matched genocide keyness table depends on one meeting or the tokenizer repair.
The 10 September run uses seed **20260807**, **3,950 matched pairs** (95.57% of
eligible targets), and deletes each of **2,281 meetings** from both selected
arms. Controls are held fixed; there is no rematching, and the remaining arms
can become unbalanced. Primary top-100 words stay fixed, with count and G²
eligibility recalculated after deletion. These are descriptive influence ranges,
**not confidence intervals** or estimates of sampling uncertainty.

The baseline exactly reproduces all 100 published keyword rows and both token
denominators. **61 words** lose eligibility under at least one deletion; no
defined effect reverses direction. Six word/deletion combinations have no
remaining occurrences in either arm and therefore a null effect. No deletion
empties an arm; future runs exclude such deletions explicitly, while missing
meeting symbols abort the run. Examples of concentrated vocabulary include
`bor` (S/PV.7168), `cong` (S/PV.2118), and `sandinistas` (S/PV.2701). Their
large pooled effects should not be read as evidence of corpus-wide dispersion.
The definitional `genocide`/`genocidal` effects remain properties of target
selection, not substantive discoveries.

The historical tokenizer from commit `abdc08a` is applied to those same speech
bodies and pairs, with denominators recomputed. **97 of 100** ranked types
overlap. The current list adds `r2p`, `rebus`, and `rostow`; the earlier list
instead contains `kh-`, `revolutionaries`, and `habr`. This compares exact
surface types, not semantic equivalence. Both tokenizers, code/input hashes,
selection rules, short strata and exclusions are recorded in the manifest.
`data/derived/lexical_robustness/` retains the selected pair IDs, complete
deletion effects in parquet, and CSV tables for meeting influence, deletion
denominators, and tokenizer rank comparison. Published payloads are unchanged.

The surface/lemma sensitivity implementation now supports a separate,
complete **7,900-speech matched layer**, generated from the saved pair IDs by
step 10's `--pairs` mode. The local CPU runtime uses spaCy 3.8.16 and
`en_core_web_sm` 3.8.0. A schema-2 layer binds every lemma sequence to its exact
speech body and tokenizer, and records the parquet checksum. Steps 05 and 18
reject stale content, duplicate/missing IDs, malformed tokens, or unequal token
counts. Full-corpus, matched, and smoke outputs and notes have separate paths.

Step 18's `--lemma-layer` mode compares independently ranked surface/lemma
lists using the same pairs, denominators, and stoplist. It retains every changed
form, reports all observed stopword leaks, and writes meeting-deletion summaries
and complete underlying effects for both representations. Exact type overlap
does not measure semantic equivalence; these remain descriptive diagnostics.
See [the CPU workflow](CLUSTER.md#running) for reproduction commands.

The completed 10 September matched run changed **1,268,220 of 7,985,143 tokens**
(15.9%), reducing 58,221 surface types to 50,472 lemma types. Two speeches
(0.025%) retained surface forms under the alignment failure rule. The top-100
lists share **81 exact types**, with unchanged target/control denominators of
4,958,491 / 3,026,652 tokens. The lemma ranking also has **61 words** that lose
eligibility under at least one meeting deletion, no defined sign reversals,
and six word/deletion combinations with no remaining occurrences.

Lemmatisation does not by itself resolve the interpretive problems. For example,
2,041 instances of `atrocities` become `atrocity`, but 13 target instances and
zero controls remain as `atrocities`; that residual type enters the lemma
top-100. `citizens` similarly leaves 48 target and two control instances.
The comparison CSV now reports counts in both representations and flags types
with both changed and unchanged occurrences. Context-sensitive tagging may
explain such splits; they need inspection before substantive interpretation.
The observed stopword leaks are `further → far` and `further → furth`.
Results remain diagnostic; the published surface vocabulary is unchanged.

Full-corpus follow-through, 10 September: step 19 evaluated the matched genocide
comparison, nine collocate profiles (three nodes × windows 5/8/15), and **144 of
148** candidate speaker profiles meeting the existing matching gates. Its 6,160
ranked-word rows include whole-meeting deletion effects and conditional 95%
percentile intervals from 999 meeting-block resamples, seed 20260807. A meeting
receives the same resampling weight in both arms; selected speeches and ranked
words remain fixed. These intervals assume hypothetical exchangeable meetings;
they do not measure uncertainty in exhaustive historical counts or rerun matching.
The minimum is 20 nonempty meetings per arm and five word-supporting meetings
per arm; more than 5% undefined draws also withholds an interval. **778 intervals
are reported; 5,382 are withheld for sparse word support.** LogDice receives
deletion ranges, not bootstrap intervals. **25 speaker-word rows reverse sign**
after at least one deletion: examples include Poland/`foe` at S/PV.2111 and
Spain/`sids` at S/PV.7499. These require close reading before strong interpretation.
Outputs and their code/input hashes are in `data/derived/extended_robustness/`.

Festus job **775572** completed the full lemma layer: **167,642 speeches**,
86,854,907 tokens, 13,074,246 changed (15.1%), 197,902 surface types reduced to
186,159 lemma types. All returned body hashes/token alignments were validated
locally before promotion. The 38 failed speech alignments retain surface forms.
The model is spaCy 3.8.16 / en_core_web_sm 3.8.0; tagging took 935 seconds.
Observed stopword leaks are `does → doe`, `further → far/furth`, and
`yourselves → yourselve`; these remain explicit sensitivity findings. Worker
processes now keep BLAS/OpenMP threads at one to prevent oversubscription.
Step 05's full lemma collocates, slices, matched keyness and network were also
regenerated in `data/derived/lexical_lemma/`. The comparison retains 3,950 pairs
and the original 4,958,491 / 3,026,652 token denominators. Surface tables remain
the primary published vocabulary.

Step 20 implements S2 annual speaker tables for genocide qualification and raw
genocide: **111,864 rows**, reconciled annually to corpus speeches, word counts
and term occurrences. **808 rows** meet the 125-speech floor. Missing years have
zero counts and withheld rates; historical affiliations remain distinct. The
Actors download retains counts, reasons for withholding and explicitly labelled
Wilson speech-level bounds (not meeting-clustered). Full CSV and manifest live
in `data/derived/actor_year/` and are included in ordinary builds.

Remaining S1/S5: read ranked outputs against published interpretation; scrutinize
the 25 fragile speaker-word findings and the full-layer stopword leaks.
Deferred S3–S4: funnel plots with meeting-clustered limits and exact vocabulary-intersection tables
(never reconstructed from pairwise edges). S6: sequential recurrence by meeting
order with exact evidence links; do not call recurrence interpersonal influence.

Later analytical specifications require a preregistered research question:
conditional vocabulary choice, translation-process sensitivity, membership
comparisons with agenda and actor/year controls, and government-change overlays.
Translation sensitivity cannot recover unmediated vocabulary. E1 joins to votes,
vetoes and resolutions need a hand-verified pilot and preserve document identity;
association is not causation. E2's former pre-1992 extension is superseded by the
completed 1946–2024 corpus migration; independent cross-corpus replication remains
deferred and must pin sources and report overlap discrepancies.

## 7. Interface and evidence contracts

Implemented while the GPU runs are pending: the home page's onward navigation
now includes all six main subpages; Actors has 20-row ranking pages and a
speaker search; concordance has a keyboard-searchable speaker picker and full
searchable facet lists with line counts. CSV exports retain the complete data.
Selecting a shared map point keeps the source affiliations separate.

Geography enrichment now accepts reviewed name variants and Unicode-equivalent
spellings without changing source labels or source classifications. Together
with the missing Madagascar centroid from the cached reference, this restores
30 state-labelled affiliations (172 to 202 mappable). Nine source-state labels
still lack reviewed locations: Czechoslovakia, German Democratic Republic,
German Federal Republic, India or Netherland, Republic of Vietnam, Turkish
Federated State of Cyprus, Turkish Federated State of Kibris, Yemen Arab Republic
and Yemen People's Republic. The interface lists exclusions explicitly. Palestine
remains unmapped because the source flags classify that affiliation as `other`;
this is a dataset limitation, not a geopolitical classification by this project.
Ten legacy regional-group labels were also corrected against the UN DGACM list;
the source and interpretation are documented in [CORPUS.md](CORPUS.md#affiliation-and-institutional-status).

Validation of these changes: 66 geography/configuration/country-step tests,
539 frontend unit tests, and 18 targeted browser tests, including open-combobox
accessibility, URL restoration, full exports, shared map points and mobile width.
The regenerated measures, period aggregates and Council standing counts match
the previous numerical payload exactly.
Frontend lint, Svelte type checking, the production build and desktop/mobile
visual checks pass; the build verifies all 12 static entry points.

The next independent research work remains S1/S5 robustness and the human
instrument pilot. Meeting-block intervals and a compatible full lemma
layer have been implemented; neither replaces the human audit or
licenses publishing the partial model run.

Computed, mixed and model-derived marks describe the actual selected data;
navigation marks describe page capability. Provenance is not a quality score.
Keep URL-restorable filters, exact evidence links, accessible tables, local basket,
fullscreen figures, persistent contents and concise reading/caveat text. Extract
logic into small tested modules at behavior boundaries, not to hit line limits.
Color must not imply a quantity the table does not measure. Show numerator,
denominator, exclusions and uncertainty in the figure's accessible account.

### 7.3 Actor display safeguards

Withhold sub-minimum rate slices, never merge speakers because they share an ISO3,
and never present a centroid as the location of a speech. Charts and the accessible
table must use the same artifact and arithmetic; the map is optional navigation.

### 7.5 Export contract

Export the complete selected data, not only virtualized or paginated visible rows.
Carry filters, units, source/provenance and caveats with CSV and image exports;
an exported image outlives its surrounding page. Navigation and highlighting must
remain correct under term, speaker, meeting and scope filters.

## Roadmap coverage

Stable IDs are retained for code references; they are not separate planning files.

| IDs | Current position |
|---|---|
| I1–I4, A1–A3 | Integrity metadata/contracts, separate candidate stores, identities and annotation machinery implemented. A4/H1–H2 wait on humans. |
| U1–U10 | Evidence navigation, URL state, basket, result profiles, page metadata, contents and word budgets implemented; maintain browser coverage. |
| M1–M5 | Shared boundaries, payload measurements, DAG/cache/export repairs and lexicon-edit instructions implemented; ongoing optimization is evidence-driven. Archival release remains gated. |
| L1–L8 / C1–C7 | Local model machinery exists; current-corpus GPU evidence and human validation remain pending. Historical model runs are not current results. |
| R3–R7, R9, R11, R14 | Provenance, confidence removal, fullscreen, published referents, term-only lexicon, scope control, aggression phrase and navigation implemented. |
| R8 | Computed first stage exists; model-dependent interpretation remains gated. |
| R1, R2, R10, R12, R13, R15 | Prepared or awaiting evidence/author decisions, detailed below. |

R7 permits individual terms and declared derived measures, not aggregate register
or set counts. R9's word, vocabulary and debate sets overlap; they are not nested,
and changing the reading set does not silently change the denominator. Lexicon v6
adds only the explicit crime(s) of aggression phrase, not generic aggression or
an intensity ranking.

## R2 — accuser and accused: acceptance gate

Wait for usable extracted strings, then seed a controlled accused-actor mapping
from observed evidence and have both coders review it. Cover States, armed groups,
international bodies and individuals. Never guess unmapped strings into a nearby
category. Publish an accuser-by-accused matrix with exact evidence links, a
model-derived mark, explicit missing/unmapped shares and self-accusation retained.
Unsupported historical schemas must produce a contracted explanatory empty state.

## R1 — situation, modality and the second referent

Run `python tools/prepare_research_review.py` to regenerate
`data/interim/research_review/candidates.json`. It selects located quotations
from archived runs, retains occurrence identities and source hashes, and keeps
candidate cues separate from labels. These runs describe the earlier corpus;
their quotes must be checked against the corresponding source. A cue retrieves
a case for reading and does not establish what an occurrence characterizes.

The proposed modality review covers armed conflict, persecution, economic
sanctions, intervention/occupation, colonial rule, famine/starvation and forced
displacement. Review the boundaries, overlap and an explicit `unclear` option.
For each candidate, both coders independently record the situation, modality,
secondary situation if any, evidence span, confidence and a boundary note. Include
negative cases where a cue appears elsewhere in the quotation. Settle whether
multiple modalities are possible before adopting a single-valued field.

Version controlled referents with explicit successors and one group per case;
publish modality and group views with primary-only counts as the default. A
secondary identifier must differ from the primary and is forbidden for reserved
non-case identifiers. An optional primary-or-secondary view counts occurrences
once and publishes the share with a second slot. Publish modality-without-situation
coverage rather than silently dropping those rows.

Schema-4 acceptance fixtures must cover:

| Case | Required behavior |
|---|---|
| False positive or non-case mention | Modality `not_applicable`, no secondary case |
| Sanctions named without a situation | Modality retained; missing situation counted explicitly |
| Two named cases at one occurrence | One row, distinct primary and secondary controlled identifiers |
| Three or more cases | `other` plus the explicit list, with the bounded loss counted |
| Group collapse | Every case has one group; primary-only totals remain identical |
| Old schema-2/3 run | Read through versioned successors; never infer new labels from old ones |

No modality file is installed in `annotations/`, no existing code is recoded,
and schema 4 cannot be selected for inference yet. Both coders must review the
vocabulary before a run uses it, as R1 specifies. Prompt v3/model schema 3.1
implements only R4; the later reviewed revision therefore needs a new prompt
version rather than overwriting v3.

## R10 — paired counter-concept study

The packet includes candidate quotations for `terroris*` and `humanitarian`.
These are seeds for vocabulary review, not an exhaustive speech-level retrieval.
The final instrument must enumerate full speech bodies: concordance windows
cannot measure speech-level co-occurrence. Add individual reviewed terms rather
than an aggregate humanitarian category.

Use the same meeting as the exact matching stratum. Within it, match genocide-
silent speeches to genocide-bearing speeches on participant type and speech
length, with deterministic tie breaking and no replacement. Publish exclusions,
unmatched shares, length balance, and coverage by speaker and period. Hold
referent constant only after a validated referent instrument can assign it;
never impute the referent from the fact that two speeches share a meeting.

Estimate within-pair differences in speech-level term presence. Resample whole
meetings for uncertainty, retaining all their pairs. Report how matching changes
balance and the estimate, without presenting an unadjusted figure as the answer.
Predeclare alternative length calipers and period restrictions and show their
sensitivity. A speech expressing humanitarian language establishes vocabulary,
not an intention to avoid a legal characterization.

The two hypothesized directions require reviewed speaker-role evidence:
bystander humanitarian vocabulary and accused-party counter-accusation. Until
both can be identified and displayed under the same rules, publish neither as
confirmation. Model disagreement is instrument stability, not accuracy.

## R12 — figure-purpose decision

The current figures remain available pending the author's choice. The decision
is between retaining them with a clear reading purpose and removing the pooled
calendar/proximity views. Record a question, a concrete reading action, and the
inference that is forbidden for each retained figure. A referent-filtered
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

Revisit only with an explicit purpose: a neighbour-speech second pass over unresolved
referents; evidence-location rates as a figure; Lemkin's conceptual vocabulary;
individual delegates' circulation (requires name disambiguation); and manual review
of noisy adjacent terms such as survivors, commemoration, denial, glorification and
holocaust. Removing aggregates does not make these terms synonymous with genocide.

## Integrity repairs

| Finding | Implementation | Verification |
|---|---|---|
| 1 — resume identity | Immutable run identity covers prompt, referent bytes, schema, corpus occurrence IDs, selected request bodies, runtime and passed probe. A changed instrument cannot append. | Identity mutation regressions |
| 2 — interrupted append | Write-ahead speech transaction commits rows/failures and accounting together; a torn tail is replayed once. OS advisory lock excludes a second writer. | Torn-tail, conflicting-tail, injected manifest failure, repeat recovery and writer-lock regressions |
| 3 — reasoning probe | Cache identity covers exact requests, full runtime, prompt and referents. The chosen top rung must increase reasoning tokens on every paired speech and have the largest positive median. Annotation checks probe request bytes again. | Flat/reversed/zero ladder regressions; operational screen, not statistical validation |
| 4 — build graph | Referents, named runs and prompt archives invalidate their consumers; known multi-output stages use grouped targets, including series, lexical, gold, usage and frames. | All four synthetic invalidation regressions passed using GNU make in the installed Ubuntu/WSL distribution; native Windows pytest skips these four |
| 5 — deploy/cache | Makefile and payload contract are trigger/cache inputs; restored and freshly rebuilt payloads undergo shape, inventory and hash checks. | Workflow regression and local payload verification |
| 6 — model readers | Shared duplicate/provenance/schema/compatibility checks serve sampling and frame triangulation; aggregation uses the same row/manifest guard. Joins enforce unique occurrence IDs. Inputs are recorded in output metadata. | Model-run and existing sampling/usage/frame regressions |
| 7 — browser cache | Service-worker cache ownership includes the app base path. Activation deletes only this app's old caches. Test servers use explicit ports, strict binding and no server reuse. | Offline browser regression seeds an unrelated cache and an old app cache |
| 8 — export boundary | Export assembles and validates a complete staged directory before replacing the previous release. | Late-failure regression retains the old manifest and payload |

The transaction guarantees apply after a response reaches its durable pending
record. A process killed while a request is still in flight may require that
request again; token counters report received/checkpointed responses, not an
unobservable provider bill. Preserve raw receipts for reconciliation. The lock
relies on filesystem advisory-lock support; run one annotator per run directory.

Existing partial runs without `identity.json` are deliberately not migrated by
guessing their missing inputs. Preserve them and use their original checkout to
resume, or start a new run ID with the corrected runner. Historical completed
schema-2 and schema-3 artifacts remain readable. The exact v2 prompt is archived
for the pending Bayreuth result; this work does not restart it.

## Verification record

Verified locally:

- Python: full suite **1,140 passed, 4 skipped** in the Windows interpreter;
  the four skipped GNU make cases subsequently passed through Ubuntu/WSL.
  Linux writer exclusion, release and transaction recovery also passed a
  separate Ubuntu/WSL smoke check.
- Ruff, frontend lint and type checking pass; **539 frontend unit tests**,
  **38 browser journeys** and **1 production service-worker test** pass.
- Same-sized content changes, missing files, missing manifest parts and false
  manifest totals are all rejected by the cache verification command.
- The full corpus's existing annual arrays and genocide concordance rows are
  unchanged. The aggression counts and reconciled speech offsets are recorded
  in [VALIDATION.md](VALIDATION.md).

The complete corpus was rebuilt in `data/review-2026-09-07`, validated, then
promoted locally. All **20 contracted artifact shapes** pass; the web payload
contains **9,512 files, approximately 687 MB**. The retained rehearsal preserves
the original input paths recorded in its provenance. Production build and static
verification pass (12 entrypoints and four icons). No deployment was performed.

Desktop and mobile screenshots confirmed the provenance navigation and locator
layout. A cold-load anchor could previously place a figure heading beneath the
sticky navigation; positioning now waits for fonts and layout, yields to reader
interaction, and has regression coverage at 390 and 1,440 pixels.

## Browser measurements

Production preview, local Chromium, 7 September 2026. Concordance measurements
use fresh contexts with HTTP cache disabled and service workers blocked. These
are single-run local measurements, not slow-network or physical-phone claims.

| Concordance | Raw JSON | Gzip | First line | Detail ready | JSON parse | Sampled peak JS heap | Exact reader occurrence |
|---|---:|---:|---:|---:|---:|---:|---:|
| genocide | 6.22 MB | 1.14 MB | 786 ms | 894 ms | 22 ms | 33.6 MB | 316 ms |
| impunity | 10.76 MB | 2.10 MB | 1,076 ms | 1,172 ms | 15 ms | 46.3 MB | 227 ms |

The Actors table became ready in 439 ms; selection took 188 ms and the map's
loading indicator cleared in 896 ms after scrolling it into view. The latter
uses the same context after a mobile reload and is not a cold-network measure.
The external basemap rendered in the mobile screenshot. Existing large
ECharts/MapLibre chunk warnings remain. Physical mobile, constrained-network and
future model-enriched payload measurements remain the gate for further sharding;
the current measurements do not establish that JSON parsing is the bottleneck.

Reproduce against a running production preview from `web/`:

```sh
node scripts/profile-payload.mjs http://127.0.0.1:4275/genocide-at-the-security-council
```

The script writes resource timings, measurements and desktop/mobile screenshots
under the ignored `web/test-results/review/` directory. Human annotations,
archived run outputs and publication pointers remain unchanged.

### Constrained-network follow-through — 10 September 2026

Production preview in Chromium with fresh contexts, HTTP cache disabled and
service workers blocked. `--slow4g` applies 1.6 Mbps down / 750 kbps up,
150 ms latency and 4× CPU slowdown through CDP. This is one simulated run, not
a physical-phone benchmark. Resource timings and screenshots are retained in
`web/test-results/review-slow4g/`.

| Concordance | First line | Detail ready | JSON parse | Peak sampled heap | Exact reader occurrence |
|---|---:|---:|---:|---:|---:|
| genocide | 11.33 s | 11.90 s | 52 ms | 33.7 MB | 3.50 s |
| impunity | 15.87 s | 16.59 s | 98 ms | 42.7 MB | 3.41 s |

Actors: table ready 5.98 s, selection 354 ms; map loading cleared in 5.98 s
after scrolling into view in the same context after a mobile reload. Loading
and startup dominate the isolated JSON parse in this test. The next performance
work should target initial concordance transfer while preserving full exports,
filters and exact evidence links. Do not infer that a parsing worker would fix
the observed wait. The real semantic payload still requires measurement after
the GPU/CPU chain completes; its page currently loads an explicit waiting state.

Verification for this implementation: 1,206 Python tests pass, with four GNU
make cases skipped on Windows and then executed successfully in Ubuntu using
their existing test bodies. Ruff, frontend lint/type checks, 543 frontend unit
tests and production static verification (13 entrypoints, four icons) pass.
The existing 43 browser journeys passed; both new semantic journeys pass after
fixing reactive pagination. The map was checked at 390 and 1,440 pixels using
explicit test data; this does not constitute validation of the pending embeddings.
Both semantic journeys also pass against the final production build, including
an all-pages CSV download with model identity. Two later development-server
startup timeouts were infrastructure failures before tests ran; production
verification completed normally.
The payload contract and complete checksum inventory pass with 9,515 files.

## Maintaining this document

Update the current-focus table and the relevant acceptance gate when work changes.
Record a dated verification snapshot here; keep detailed execution history in Git
and generated stage notes rather than adding another review or status document.
Do not mark local implementation as human validation or a successful deployment.

Before committing, run the applicable full gates: Python pytest and Ruff;
frontend unit tests, lint and type checking; production build for shipped routes;
browser journeys for interaction changes; producer/consumer and payload checks for
contract changes. Before a tag, also complete section 1's release gate.
