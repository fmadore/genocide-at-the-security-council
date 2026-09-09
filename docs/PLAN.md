# Project focus and release gates

Updated 9 September 2026. This is the single planning and status document.
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
| 5 | S1 / S5: finish robustness work | Read re-ranked lexical tables; distinguish existing Wilson intervals and control-draw variance from meeting-clustered uncertainty. Regenerate compatible lemmas before sensitivity analysis. |
| 6 | M1–M3: measured maintenance | Keep small pure modules and MapLibre. Local deep-link measurements are recorded below; measure constrained networks and physical mobile before choosing further sharding. |

## Research contract

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

Topics and semantic projection are deferred until a specific research question
and evaluation justify them. UMAP distance is not diplomatic position or shared
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

Remaining S1/S5 work: re-read ranked outputs against published interpretation;
measure tokenizer sensitivity against the earlier version; regenerate the lemma
layer; test leave-one-meeting-out and surface/lemma sensitivity; add meeting-block
intervals on effect sizes where justified. Declare seed, resampling unit,
repetitions, exclusions and failure rules. Any new plot must answer an explicit
question and retain the underlying table.

Deferred S2–S4: actor-by-year prevalence with denominators/withholding, funnel
plots with meeting-clustered limits, and exact vocabulary-intersection tables
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

## Maintaining this document

Update the current-focus table and the relevant acceptance gate when work changes.
Record a dated verification snapshot here; keep detailed execution history in Git
and generated stage notes rather than adding another review or status document.
Do not mark local implementation as human validation or a successful deployment.

Before committing, run the applicable full gates: Python pytest and Ruff;
frontend unit tests, lint and type checking; production build for shipped routes;
browser journeys for interaction changes; producer/consumer and payload checks for
contract changes. Before a tag, also complete section 1's release gate.
