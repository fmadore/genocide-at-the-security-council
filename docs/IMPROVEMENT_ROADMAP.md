# Improvement roadmap

Status: adopted on 24 August 2026; implementation has started. A task is complete only when
its own status and the implementation log say so.

This roadmap turns the external assessment of commit `752ef66` into small, testable changes.
It supplements the longer design record in [`PLAN.md`](PLAN.md); it does not replace that
record or propose a rewrite.

## Decisions already made

- Keep the numbered Python pipeline, static SvelteKit deployment and lazy-loaded evidence.
- Keep MapLibre. A local SVG-map replacement is out of scope unless later measurements show
  a concrete accessibility, reliability or performance problem that cannot be fixed in the
  existing map.
- Build safe annotation machinery now, but do not pretend that an empty coding exercise has
  validated the lexicon. Human coding, adjudication and any model-assisted classification
  remain explicitly gated on the arrival of annotators.
- Prefer small modules and plain files over new services. No backend, account system,
  workflow engine, annotation platform or model registry is currently justified.
- Preserve static hosting. The 491 MB payload is mostly lazy-loaded evidence, so optimize
  requests that users actually make rather than treating total generated size as a defect.
- Do not revive topic modelling or add generic sentiment analysis without a new research
  question and evidence that the method answers it reliably.

## Baseline and working rules

At the start of this roadmap, on commit `752ef66`:

- `python -m pytest`: 608 passed;
- `npm test` in `web/`: 262 passed;
- the audit has no human verdicts;
- the published application is intentionally untagged.

These counts are a dated baseline, not a value to repeat in user-facing prose. Documentation
should name the test commands and CI gates; CI itself is the source of truth for the current
count.

Every implementation task gets one stable ID from this document. A task is complete only
when:

1. its acceptance criteria pass;
2. focused regression tests cover the changed behavior;
3. the relevant full test/lint/typecheck gates pass;
4. public or methodological behavior is documented;
5. the change is entered in the implementation log at the end of this file.

Use one focused commit per task where practical. If a task proves too large for a reviewable
commit, split it in the log without inventing a new architectural layer.

## Priority summary

| Order | Workstream                                     | Why now                                                               | Human annotators needed?                      |
| ----: | ---------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------- |
|     1 | I1–I4 research-integrity fixes                 | Prevent loss and false provenance before more artifacts are generated | No                                            |
|     2 | A1–A3 annotation preparation                   | Make future coding durable and statistically interpretable            | No                                            |
|     3 | U1–U8 evidence navigation and browser coverage | Make existing claims reproducible and test complete user journeys     | No                                            |
|     4 | M1–M5 maintainability and payload access       | Reduce change risk without a broad refactor                           | No                                            |
|     5 | S1–S6 stronger descriptive analysis            | Add uncertainty and views that expose evidence, not decoration        | No, except where noted                        |
|     6 | H1–H2 human-coded interpretation               | Answer what the term is doing rhetorically                            | Yes                                           |
|     7 | E1–E2 institutional and historical extension   | Add new data sources and new claims only after the core is stable     | No, but substantial research review is needed |

## Phase I — research integrity

These are the first implementation tasks. They are independent of manual coding and should
be finished before adding a new visualization.

### I1. Record dirty working trees correctly

**Status: complete on 24 August 2026.**

**Change.** Make `scripts/lib/artifacts.py::git_commit` append `-dirty` when tracked files
are modified, staged files differ from `HEAD`, or untracked files are present. Retain the
existing `.git-commit` fallback for cluster copies without a repository.

**Keep it small.** Use Git commands directly; do not add GitPython.

**Acceptance and tests.**

- A temporary real repository reports its clean commit.
- Modified, staged and untracked files each produce `<sha>-dirty`.
- Ignored files do not make the tree dirty.
- A directory without `.git` still accepts a valid clean or dirty stamp and rejects an
  invalid one.

### I2. Correct the frontend metadata types

**Status: complete on 24 August 2026.**

**Change.** Split `Meta` in `web/src/lib/types.ts` into a `BaseMeta` containing fields every
artifact actually has and a lexicon-aware extension containing `lexicon_version`. Assign
the narrow type to each payload, including speaker keyness, instead of making one field
fictitiously universal.

**Acceptance and tests.**

- `svelte-check` succeeds without casts that hide the mismatch.
- Type-level fixtures cover one payload with and one without `lexicon_version`.
- Runtime validators continue rejecting genuinely absent required metadata.

### I3. Preserve requiredness in the generated data contract

**Status: complete on 24 August 2026.**

**Change.** Extend the existing contract representation so a key present in only some
array or opaque-object members is recorded as optional rather than silently unioned as if
it were universal. Compare both type and requiredness during export.

**Keep it small.** Evolve `scripts/lib/contract.py` and the committed compact shape. Do not
introduce a general schema framework unless this minimal representation proves unable to
express a real payload variant.

**Acceptance and tests.**

- Dropping a required field from one member fails the contract test.
- A declared optional field may be absent.
- Nullable values remain distinct from missing keys.
- Discriminated variants and opaque lexicon-keyed collections have explicit fixtures.
- The Python producer and TypeScript consumer tests agree on the new representation.

### I4. Remove documentation drift and add a stable analytical hash

**Status: complete on 24 August 2026.**

This task has two small parts that touch the same provenance/documentation boundary.

1. Remove exact live test counts from README, methods and web documentation, except for the
   dated baseline in this roadmap.
2. Add an `analysis_hash` derived from canonical analytical content while excluding
   volatile fields such as generation time and Git dirtiness. Keep the human-readable
   timestamp and Git commit alongside it.

**Acceptance and tests.**

- No public prose claims a current number of tests.
- Equal analytical data generated at different times has the same hash.
- Changing analytical data or a declared analytical configuration changes the hash.
- Volatile provenance remains available but is not part of the analytical hash.

## Phase A — annotation preparation without annotators

The goal of this phase is to make future human work safe. It does not close the validation
gate and does not generate a headline quality score.

### A1. Separate candidates from annotations

**Status: complete on 24 August 2026.**

**Change.** Replace the single overwritten
`data/interim/lexicon_audit_sample.csv` workflow with three explicit artifacts:

- generated candidate/sample files, safe to regenerate;
- a versioned annotation file owned by human coders;
- a generated merged review table joining the two by stable ID.

The annotation file must never be recreated with blank values over nonempty work. A merge
must fail loudly on duplicate candidate/coder keys, unknown IDs, incompatible schema
versions or conflicting labels.

**Minimal storage choice.** Use documented UTF-8 CSV plus a small schema/codebook in the
repository. Do not build an annotation web application before multiple annotators have
actually found CSV inadequate.

**Acceptance and tests.**

- Rerunning step 03 cannot erase a nonempty annotation.
- Candidate row order changes do not break the join.
- Changed source text or span identity creates a new occurrence ID rather than silently
  attaching an old verdict; an incompatible lexicon version blocks automatic carry-over.
- Atomic-write behavior is retained.

### A2. Give every sampled occurrence a stable identity and explicit sampling frame

**Status: complete on 24 August 2026.**

**Change.** Construct an ID from stable speech/source identity, canonical term, exact span
and matched source text. Store the lexicon version beside the ID rather than inside it, so
an unchanged occurrence keeps its identity across releases while a merge can still refuse
automatic carry-over after an incompatible pattern change. Store the sampling frame,
inclusion probability or sampling weight, seed, schema version and candidate-generation
hash with every sampled row.

Produce separate files for:

1. a simple probability sample used to estimate overall precision;
2. a coverage sample spanning terms, periods and known edge cases, used for diagnosis rather
   than an unweighted global estimate;
3. a negative/high-recall sample drawn from plausible non-matches, used to investigate
   missed occurrences.

Keep speech-level sampling only when it answers a separately named estimand; do not pool it
with occurrence-level rows into one precision percentage.

**Acceptance and tests.**

- The same inputs, configuration and seed produce the same IDs and samples.
- Reordering the source frame does not change membership.
- Probability and coverage samples are distinguishable in both files and metadata.
- Every reported sampling weight can be reconstructed from recorded frame counts.
- Negative candidates cannot overlap positive matches for the same term/span.

### A3. Publish the codebook and annotation schema

**Change.** Replace the overloaded `phenomenon` column with separate fields:

- `verdict`: true positive, false positive, uncertain;
- `quotation`: direct, attributed/reporting, none, unclear;
- `stance`: asserts, attributes/reports, rejects/denies, hypothetical/conditional,
  neutral legal reference, unclear;
- `function`: multi-label accusation/qualification, warning/prevention, commemoration,
  accountability, institutional title/mandate, other, unclear;
- `referent`: controlled case/entity identifier plus other or unclear;
- `source_checked`, `evidence_span`, `confidence`, `coder`, `coded_at`, `comment`.

Include examples and boundary rules. The schema must allow abstention and multi-label
function; it must state that coding classifies discourse, not whether genocide occurred.

**Acceptance and tests.**

- A validator rejects unknown labels, missing coder/date, invalid multi-label values and
  evidence spans outside the context.
- Older schema versions are refused or migrated explicitly.
- The codebook has at least one positive, negative and ambiguous example for each field
  whose interpretation is not self-evident.

### A4. Score completed annotations — blocked until humans code data

Implement this only when real labels exist. Report weighted overall precision from the
probability sample; diagnostic results by term, tier and period from appropriate samples;
recall-oriented findings from the negative sample; uncertainty intervals; disagreement;
and inter-coder reliability where double-coding permits it. Never manufacture an agreement
statistic from single-coded data, and never mix the coverage sample into an unweighted
overall estimate.

**Release gate.** No citable release until the agreed sample is coded, a planned fraction
is double-coded and adjudicated, the primary-source checks in `VALIDATION.md` are complete,
and the scored report is archived with the exact corpus, lexicon and candidate versions.
Then freeze the generated payload and manifest, create a version tag, and deposit a
reproducibility package with a DOI. The release record must link corpus version, application
commit/tag, analytical hash, audit schema/version and audit report explicitly.

## Phase U — evidence navigation and end-to-end confidence

### U1. Add a minimal browser-test harness

Add Playwright coverage for the journeys unit tests cannot establish, with automated
accessibility checks on the same small set of pages. Start with Chromium only; add other
browsers only after a real compatibility need appears.

First journeys:

- a copied filtered URL restores the same state;
- a concordance hit opens and highlights the exact occurrence;
- CSV and image downloads reflect the stated filters and provenance;
- keyboard users can operate the map fallback, filters and evidence links;
- direct navigation works under the repository base path;
- offline/service-worker failure and retry states are intelligible;
- one narrow and one wide viewport do not hide essential controls.

Use tiny committed fixtures rather than the 491 MB production payload.

### U2. Encode analytical state in URLs

**Status: complete on 24 August 2026.**

Create one tested query-state module and adopt it route by route: chronology, language,
actors, then concordance. Encode only state that changes the analytical reading: date or
period, measure/tier/terms, denominator, actor/group, language register, meeting/case and
selected comparison. Preserve browser history and make invalid values visibly fall back to
documented defaults.

Do not centralize purely presentational state such as an open help panel.

### U3. Link to the exact occurrence

Carry the stable hit ID through KWIC, URLs and the reader. On navigation, scroll to and
highlight that occurrence, including repeated uses of the same term in one speech.

Then add, in this order:

1. copy occurrence permalink;
2. previous/next occurrence in the current result set;
3. copy quotation with a plain project citation;
4. CSL-JSON, RIS and BibTeX only after the underlying speech metadata is sufficient and
   round-trip fixtures are defined.

**Step 4 complete on 27 August 2026, with its gate assessed rather than assumed.** The corpus
gives the delegation, the S/PV symbol, the meeting date and ordinal, the agenda item, the
verbatim sentence, a stable occurrence ID and -- in the reader, where the meeting is loaded --
the personal speaker and role. It does not give paragraph or page locators of the official
record, and the UN Digital Library is reached by *search* rather than by a stable document URL.
So a citation uses this project's own occurrence ID as its locator and its permalink as its
URL, and never presents a search link as a document URI. That is sufficient for all three
formats. CSL uses type `speech`; RIS uses `GOVDOC`, the nearest type that format has; BibTeX
uses `@misc` with the container and symbol in `howpublished`. The fixtures are golden strings
plus parse-backs, including a record carrying the apostrophes, accents and TeX metacharacters
the corpus actually contains — which is how the unescaped `%` in a percent-encoded permalink
was caught before it could comment out half a `.bib` entry.

### U4. Expose existing participant type

**Status: complete on 24 August 2026.**

Add `participanttype` as a chronology split/filter using existing normalized data. Publish
its denominator and evidence link exactly as for current splits. This is intentionally a
small feature before any new analytical pipeline.

### U5. Local research basket — optional after U1–U4

**Status: complete on 27 August 2026.**

Allow bookmarking occurrence IDs and speeches in local browser storage, with a note and
CSV/JSON/Markdown export. No accounts, synchronization or backend. Treat schema migration,
storage limits, deletion and export provenance as acceptance criteria. Build it only after
exact occurrence IDs are stable.

**As built.** Items keep a snapshot of the sentence and its identifying context alongside the
stable ID, plus the lexicon version and analytical hash of the artefact they came from. That is
what lets the basket render with no fetches — necessary offline, where `static/data/` is
outside the service worker on purpose — and what keeps an item meaningful after a rebuild
renumbers occurrences: it becomes stale, with its recorded text intact, rather than empty.

An envelope written by an unknown version is reported and left in storage untouched; only an
explicit "start a new basket" overwrites it. A full basket and an over-long note are refused in
words rather than evicting or truncating. The export carries provenance per row, because a
basket spans artefacts and possibly lexicon versions and a single header block would have to
name one of them and be false about the rest.

It is a dialog rather than a route: every other URL on this site determines what a reader sees,
and a basket URL would be the one exception, naming a page whose contents live in one browser.
`basket.svelte.ts` is a second documented exception to the no-global-stores rule, on the same
grounds as the theme store — reader-owned, persistent, analytically inert.

### U6. Page metadata and discoverability — low risk, low urgency

**Status: complete on 24 August 2026.**

Add route-specific titles/descriptions and canonical URLs, then a sitemap, Open Graph data
and conservative JSON-LD for the software and dataset. Avoid describing generated figures
as separately published datasets unless they have stable public identifiers.

### U7. Profile of a concordance result set

External feedback reported the concordance's filters as the strongest part of the site and
asked for two things the view does not yet do: a way to see how a filtered result set is
composed, and a path from the concordance back to time. Both are readable from lines the
browser has already loaded, so neither needs a new artifact or pipeline step.

**Change.** Add pure profile functions to `web/src/lib/concordance.ts` and one presentational
component that renders them inside the existing concordance figure:

1. counts of the current filtered result set by speaker, speaker group, participant type and
   agenda item, top-N with an explicit remainder row, each row applying its own filter;
2. the same result set by year, as a strip across the full corpus range, each year applying
   itself as a one-year range;
3. a link to the chronology of the same term, labelled with exactly what it opens.

Clicking an active value clears it. No previous range is remembered, because the URL carries
no such memory.

**Counts are apparatus here, and must say so.** Everywhere else on this site a count is
refused as evidence, because a count is partly a picture of when the Council met. This panel
summarizes a selection the reader has already made and exists to be clicked, so raw counts
are the honest unit — but the panel states that it is navigation and names the two pages that
carry rates. It is therefore not a `Figure` and must not acquire question/reading/caveat/source
props.

**Keep it small.** Profile the already-filtered lines in one pass; do not re-filter, and do not
compute minus-one facet previews. Do not put filtered counts inside the filter selects, which
would make a control's own labels shift as it is used.

**Also fix, while the file is open.** The `country`, `agenda`, `left` and `right` comparators
lack the identity tiebreaker `date` carries, so equal keys leave a citable table free to
reorder. The sort disclosure in the export says `country` while the control says "Speaker";
route both through one function rather than changing the serialized parameter, which would
break copied URLs.

**Acceptance and tests.**

- Profiled counts equal a brute-force recount of the same filtered lines, and the remainder
  row's count and value tally with the top-N rows.
- Applying a facet or year from the panel produces exactly the count the panel showed.
- Clicking an active facet clears it; clicking an active year restores the documented default
  range rather than a remembered one.
- Every sort is a total order under shuffled input.
- The chronology link carries the term and nothing else, and its label says the filters are
  left behind.
- The panel's own state is not serialized into the URL.

### U8. Titles and prose that name what they do

**Status: complete on 27 August 2026.**

The same feedback reported two pages as unclear. Both causes are prose, not analysis.

**Change.**

1. The year × month heatmap is the only figure on the site whose title is a question; house
   style puts the declarative noun phrase in `title` and the question in `question`. Rename it
   in both places it appears, including the CSV title, without touching the `question` prop.
2. That figure's finding — the darkest months follow the tribunals' twice-yearly reporting
   timetable rather than a commemorative calendar — is stated only in the caveat, where a
   reader meets it after forming the wrong expectation. Promote one sentence into the reading
   note, under the same data condition the caveat uses and from the same computed values, so
   prose cannot drift from the figure.
3. The language page never names collocation, keyness or the co-occurrence network in its
   standfirst, so a reader trained on these methods cannot recognize them. Name and gloss each
   in the standfirst, keeping the existing account of G² and log ratio verbatim.

**Acceptance and tests.**

- No figure title on the site ends in a question mark.
- The promoted sentence appears and disappears with the same data condition as the caveat it
  was drawn from, and reuses the computed months rather than restating them as literals.
- The full frontend and browser gates pass, and the built site is inspected, because this is
  production-facing prose with no unit surface of its own.

## Phase M — maintainability and measured payload improvements

### M1. Refactor large routes opportunistically

Do not split components by line count alone. When U2–U4 touches chronology, language or
concordance, extract only:

- pure query/filter state;
- chart-option builders;
- export row construction;
- a figure component with a clear input/output boundary.

Keep analytical decisions in plain tested TypeScript modules and Svelte components focused
on rendering. Stop when the changed feature is easy to test; do not launch a route-wide
component rewrite.

### M2. Keep and harden MapLibre

Retain the map and its current geography. During actor-page work:

- isolate selection, keyboard-navigation and fallback logic from rendering where useful;
- test lost WebGL context, tile/style failure and the accessible non-map path;
- document third-party requests and avoid making a tile request a prerequisite for reading
  the underlying actor table;
- measure the route bundle and first interaction before attempting optimization.

No SVG-map replacement is planned.

### M3. Optimize evidence access from observed requests

Instrument locally or inspect hosting logs if available before changing sharding. Candidate
changes, in order:

1. fetch one speech and one occurrence for deep links;
2. shard only KWIC files whose measured transfer/parse cost is material, probably by year or
   period;
3. ensure a citation link does not load an entire term history.

Each change needs before/after transfer, request-count and interaction measurements. Do not
add a query service while static files meet the need.

### M4. Small pipeline and deployment cleanup

Do these independently, only when the relevant file is already being changed:

- narrow deployment cache keys so optional cluster experiments do not invalidate the
  release payload;
- pin GitHub Actions by commit SHA and use automated updates;
- render generated narrative notes from completed analytical artifacts when editorial-only
  changes currently force expensive analysis;
- add a tiny stage registry with declared inputs/outputs and `--from`, `--to`, `--force`
  only if duplicated stage invocation causes an actual maintenance error.

Snakemake or another workflow platform is explicitly deferred.

### M5. Document how the lexicon is changed

**Status: complete on 27 August 2026.**

The word list is the study's central scholarly choice and the roadmap already calls it a
proposal rather than a result. External readers ask how to add terms, and the answer is
currently spread between the configuration file's own header and the numbered steps.

**Change.** Add one short section to `scripts/README.md` recording: which fields a term needs
in `config/lexicon.yml` and that its `note` carries the rationale, because a term is a
recorded decision rather than a configuration tweak; the version bump; the steps to rerun in
order and what each regenerates; and the consequences worth knowing in advance — an
incompatible version blocks automatic carry-over of existing annotations, the frontend needs
no code change because the term list is read from the exported index, and provenance picks up
the new version by itself.

**Keep it small.** Documentation only, no new file if an existing one is the place a reader
already looks.

**Acceptance.**

- A reader can add a term and regenerate the site without reading the pipeline source.
- The stated rerun order matches the steps' actual dependencies.
- Claims about annotation carry-over and contract stability match A2 and the contract test.

## Phase S — stronger descriptive analysis

Each item starts with a machine-readable table, denominator, uncertainty/withholding rule
and concordance path. The visualization is a consumer of that table, never the first
artifact.

### S1. Meeting-clustered uncertainty

Add meeting-block bootstrap intervals and sensitivity to high-volume meetings to existing
actor and time comparisons. Use cluster-robust or beta/negative-binomial alternatives only
where the estimand and observed dispersion warrant them. Publish the unit of resampling,
seed, repetitions and failure/withholding rules.

### S2. Actor-by-year prevalence matrix

Rows are actors, columns are years and cells are the share of that actor's speeches using
the selected vocabulary. Show denominator, hatch/withhold under the declared minimum,
support meaningful sorting and link every drawable cell to evidence. This is the first new
visualization because it extends an existing actor artifact and answers a clear gap between
four broad periods.

### S3. Funnel plot for actor comparison

Plot actor denominator against term-bearing speech share with Council-wide reference and
meeting-clustered 95%/99% limits. Use it to display sampling volatility, not to label actors
as statistically deviant without substantive review.

### S4. Exact atrocity-vocabulary combinations

Build an UpSet-style table/plot for exact intersections among genocide, war crimes, crimes
against humanity, ethnic cleansing and Responsibility to Protect. Filters must retain their
own denominators and evidence paths. Do not derive exact combinations from a pairwise
network.

### S5. Lexical robustness and shift

For every collocate add distinct meetings, speakers and years; meeting dispersion;
leave-one-meeting-out sensitivity; surface/lemma sensitivity; weighted log-odds; and
meeting-level bootstrap intervals where feasible. Then expose a collocate-by-period matrix
using color for direction/magnitude, size for frequency and a separate mark for dispersion.
Do not add another word cloud.

### S6. Sequential recurrence within meetings

Use `speech_number` to identify first use, later recurrence and speech distance by meeting,
actor role and agenda. A meeting barcode can visualize the resulting table and link each
segment to an exact hit. Call the pattern “sequential recurrence” or “uptake,” never
interpersonal influence.

### Later analytical specifications

These may follow S1–S6 when a publication question requires them:

- estimate genocide choice conditional on any atrocity-core vocabulary;
- compare explicit English records with translated records as translation-process
  sensitivity;
- use within-actor Council-membership changes with actor and year effects, agenda controls
  and meeting-clustered errors.

They must be preregistered as new analyses rather than quietly added to the descriptive
dashboard.

## Phase H — human-coded interpretive layer

### H1. Pilot, revise, then conduct coding

When annotators arrive:

1. train on a small shared pilot outside the scored sample;
2. revise and version the codebook;
3. code roughly 300–500 contexts, with 20–25% independently double-coded;
4. adjudicate disagreements while preserving original labels;
5. publish per-class results, uncertainty and the adjudication protocol.

Final sizes should follow the desired precision and observed class prevalence, not the
round numbers above. Protect annotator identity where necessary while retaining stable
coder pseudonyms.

### H2. Consider rules or model assistance only after H1

Any classifier must predict stance/function/referent, return an evidence span, permit
abstention and be evaluated on untouched human-coded cases with per-class precision,
recall and macro-F1. Human labels remain the authority. The classifier must never be framed
as deciding whether an event legally constituted genocide.

## Phase L — model-assisted usage layer (experimental)

**Decision, 28 August 2026.** External feedback asked the two questions this dashboard cannot
answer from counts: which genocide a delegation is invoking, and whether the speaker asserts
the characterization or rejects it. Both are properties of a usage rather than of a frequency,
so no denominator, series or collocate table will produce them. This phase builds a
model-assisted layer that proposes those properties for every occurrence of `genocide`, and
ships it as an experiment rather than as a result.

That contradicts H2, which admits model assistance only after H1. The tension is recorded here
rather than removed by rewording H2. Shipping ahead of the full H1 campaign is the owner's
decision, and it is gated instead on four conditions that hold for as long as the layer exists:

1. every model-derived surface — route, figure, table, export and payload — carries a standing
   experimental marking naming the model and the run, which no interaction dismisses;
2. a gold sample of roughly 200 occurrences is coded independently by both coders, 100%
   double-coded, and the human/model agreement it yields is shown beside the model output
   rather than filed in a report;
3. human labels remain the authority: a disagreement is published as a disagreement and never
   settled by editing the human row;
4. the closing rule of `PLAN.md` §5 stands unchanged — no model output may overwrite corpus
   text, lexicon counts or human annotations.

Three further limits belong to the same decision. The scope is the single term `genocide`, not
the lexicon: the study's question is about that word, and one term keeps the gold sample large
enough per class to support any statement at all. The annotating model is recorded per run
rather than declared once in prose, because the layer is expected to be re-run against
different models and a comparison is worthless if the output does not carry its own
provenance. And Joël Glasman, who asked for this analysis and codes the gold sample alongside
the author, is credited as a coder in the codebook and acknowledged in README and Methods;
`CITATION.cff` is unchanged, because the sole-authorship decision in `PLAN.md` §1.3 stands and
coding a gold sample is not authorship of the study.

This phase does not open A4's release gate. An experimental view is not a citable result, and
the §1.1 audit remains the condition for a tag.

### L1. Seed the referent vocabulary

**Change.** Give `annotations/lexicon/referents.csv` the descriptive columns `kind` (`case`,
`historical`, `meta`, `reserved`), `iso3` and `years`, and seed roughly thirty referents: the
situations actually argued before the Council, the memory cases that predate the corpus, and
the meta referents a passage carries when it names no case at all. `audit.read_referents`
requires only `id`, `label` and `description` and tolerates further columns, so the descriptive
columns cost no code change.

One list serves both coders and the model prompt. A referent invented separately on either side
cannot be compared with the other, which is the whole point of the gold sample.

Descriptions name the discourse referent and never adjudicate whether an event legally
constitutes genocide — the codebook's own rule. Where a binding legal finding exists, plain
naming is accurate; elsewhere the description says that speeches invoke the situation as
genocide or genocidal.

Move the codebook to version 2.1: the seeded list, the descriptive columns and the two-coder
protocol for the gold sample. No field definition and no controlled value changes, which is why
this is 2.1 and not schema version 3.

**Acceptance and tests.**

- `audit.read_referents` accepts the real committed file and the three reserved IDs survive.
- IDs are unique, nonempty and match `^[a-z0-9_]+$`, so a spelling variant cannot fragment one
  referent.
- Every `kind` is one of the four declared values and the reserved rows carry `reserved`.
- Both coders have reviewed the list before any scored coding or model run begins.

### L2. Genocide gold sample and its two-coder protocol

**Change.** `scripts/13_gold_sample.py` draws a stratified sample of about 200 genocide
occurrences — a probability frame that carries a weight, and a coverage frame spanning period
and usage cues such as negation, quotation, conditional phrasing and institutional titles — into
`data/interim/genocide_gold_*.csv`. Human work lives in the new versioned
`annotations/genocide/annotations.csv`, under the schema and codebook the lexicon audit already
uses, and no script writes it.

Both coders, `FM` and `JG`, code every sampled occurrence independently. The double-coded
fraction is 100% rather than H1's 20–25%, because these 200 rows are the model's entire
evaluation set and a single-coded row cannot say whether a model/human difference is a model
error. A shared pilot outside the scored sample precedes scored coding, and disagreements are
adjudicated by codebook step 6, which preserves both originals and records the resolution as a
separate row.

**Acceptance and tests.**

- The same corpus, configuration and seed reproduce the same sample and the same IDs, and the
  IDs are the audit occurrence IDs, not a second identifier scheme.
- Both frames are distinguishable in the file and the metadata, and every weight can be
  reconstructed from recorded frame counts.
- Regenerating the sample cannot write, clear or reorder anything under `annotations/`.
- Each declared stratum is represented, and a sample too small to cover them fails loudly.

### L3. Annotate every genocide occurrence

**Change.** `scripts/lib/llm.py` and `scripts/14_llm_annotate.py` annotate all genocide
occurrences with the codebook's own schema — verdict, quotation, stance, function, referent,
evidence quote, confidence — with abstention an allowed value in every field rather than a
missing one. The step runs by hand only; it is never invoked from CI or the deploy workflow,
which must rebuild the site without an API key.

Output is committed under `model_annotations/genocide/runs/<run_id>/` beside a manifest
recording the model identifier, the SHA-256 of the prompt, token usage, the run date and the
corpus and lexicon versions it was run against. Every evidence quote is verified against the
speech body; a quote that is not there is flagged in the output and counted, never repaired and
never silently dropped.

**Keep it small.** A committed run is a curated input like `config/entities.csv`. No model
registry, no serving layer and no scheduler.

**Acceptance and tests.**

- Offline fixtures cover the whole path; the tests never call an API.
- An unknown label, a malformed record or a quote absent from the source is refused or flagged,
  and cannot enter the run as a plausible-looking value.
- Abstention is a recorded value, distinguishable from a field the model failed to return.
- The step writes nothing under `annotations/`, `data/derived/` or `config/`.

### L4. Aggregate the run into the usage payload

**Change.** `scripts/15_usage.py` and `scripts/lib/usage.py` join the committed run, the gold
annotations and the flagged corpus into `data/derived/usage/usage.json` and
`data/derived/usage/occurrences.json` under the existing payload contract. Cells below a
declared minimum number of occurrences are withheld rather than drawn, as elsewhere on this
site, and each carries the denominator that made it withheld. Per-class human/model agreement is
computed from the gold rows alone and travels with the payload.

**Also fix, while the file is open.** `deploy.yml` triggers on `config/**` and `scripts/**` and
keys its derived cache on the same globs, although step 03 already reads
`annotations/lexicon/annotations.csv`: coding a row today would not rebuild the site. Add
`annotations/**` and `model_annotations/**` to both the trigger paths and the cache key, and add
step 15 to the build.

**Acceptance and tests.**

- Producer and consumer fixtures agree on the payload shape, and the contract test fails when a
  field's requiredness changes.
- Agreement is computed on gold rows only and can never be reported over the full run.
- A withheld cell exposes its denominator and is distinguishable from a zero.
- A coded occurrence missing from the run, and a run row missing from the corpus, are both
  reported rather than dropped.

### L5. The `/usage` view

**Change.** A new route, marked experimental everywhere it appears, that discloses the model
identifier, the run date and the prompt verbatim, and reports the abstention rate and the gold
agreement beside the figures they qualify. Its first figure is the matrix external feedback
asked for: speaking actor by referent, with stance counts inside each cell, so a reader sees who
invokes which genocide and in which direction. Every drawable cell drills down to the
quotations behind it, and every quotation links into the reader and the concordance at the exact
occurrence.

Add methods-ledger rows for steps 13, 14 and 15 with a new `experimental` state beside the
existing `verified`, `open` and `unadopted`, because none of the three is honest here.

**Acceptance and tests.**

- The experimental marking is present on the route, on every model-derived figure and in every
  export, and no interaction removes it.
- The prompt shown is the one the manifest hashes.
- A cell below the declared minimum withholds and says so; a drilled-down quotation resolves to
  the occurrence it names.
- The route's analytical state round-trips through the URL like every other view.

### L6. Close the documentation

**Change.** A README status row naming the layer as experimental and model-derived; a dated
mapping in `PLAN.md` §5 of its six preconditions to what this phase did, partly did and did not
do; `VALIDATION.md` register entries for the human checks this phase opens; a `scripts/README.md`
run book for 13, 14 and 15 stating that they are manual, what they need and what they write; and
the acknowledgment of Joël Glasman.

**Also fix, while the file is open.** `VALIDATION.md` §2 still says the referent list "contains
only reserved values". L1 made that false.

**Acceptance.**

- A reader can tell from the README alone which parts of the site are model-derived and
  unvalidated.
- `PLAN.md` §5 states which of its six steps are met and which are not, rather than leaving a
  reader to assume the phase satisfied all six.
- No per-class threshold is claimed that a 200-occurrence sample cannot support.

### L7. Diffusion of the word, by referent

**Decision, 30 August 2026.** The second round of the same external feedback asks for the
diffusion picture: for each referent, when each delegation first said `genocide` about it,
first asserted the characterization, and first rejected the word — so that Rwanda's April–July
1994 turn, and every later case, can be read as a dated sequence of adoptions and refusals
rather than as a total. The run's schema already carries everything this needs — every
annotated occurrence is a dated speech by a delegation with a referent and a stance — so L7 is
an aggregation and a figure, not a new model call: no prompt change, no new run, no new cost.

**Change.** `scripts/lib/usage.py` gains `diffusion_rows`: over assigned occurrences, per
referent and delegation, the first occurrence in each of three milestone classes — `mention`
(any assigned occurrence), `asserts`, and `rejects_or_denies` — each event carrying its date
and its KWIC line id, so the chronology stays clickable down to the speech. `usage.json` gains
the resulting `diffusion` block under the existing contract. On `/usage`, a cumulative step
figure counts the delegations that have asserted a selected referent against those that have
rejected the word for it, over the corpus span; the chronology itself — which delegation, which
date, which record — sits beneath the curve as the primary deliverable, and the referent
selection is the same URL state the matrix already carries.

**Limits.** The curve counts delegations *speaking in this corpus*. Only a delegation that
took the floor can appear; absence is not refusal; and participation varies with Council
membership and the open-debate calendar, so the ceiling of the curve is the speaking record,
never the membership of the United Nations. The figure states this in its own apparatus
rather than leaving it to a methods page.

**Acceptance and tests.**

- An event is the minimum of `(date, line_id)` for its class, deterministically, and the same
  occurrence may legitimately open both the `mention` and a stance milestone.
- Ineligible and unassigned occurrences produce no event; a blank date refuses rather than
  sorts first.
- The block appears in the payload contract, and the fabricated fixture exercises all three
  milestone classes.
- The figure and its export carry the experimental marking and the speaking-record caveat, and
  the chronology resolves to the reader at the exact occurrence.

### L8. The second opinion — a comparison run from an independent model

**Decision, 31 August 2026.** One model's labels carry one model's habits — the near-zero
abstention of the first run is exactly the kind of artefact a single instrument cannot see in
itself. L8 adds a *comparison run*: a second model from a different family (Google Gemini 3.7
Flash) annotates the same occurrences with the byte-identical prompt, and the aggregation
computes where the two instruments disagree. Disagreement is the working signal: an occurrence
two independent models read differently is, with high probability, a passage worth a
historian's attention — ambiguity, irony, entangled attribution, damaged OCR.

The limit is stated with the feature, because it is the feature's most likely misreading:
**agreement between two models measures stability across instruments, never accuracy.** Two
models can share training habits and be confidently wrong together. Convergence validates
nothing; the human gold sample remains the only calibration, and it scores both runs, so a
disagreement the humans have adjudicated also says which instrument erred.

**Change.** `scripts/16_llm_annotate_gemini.py` (+ `scripts/lib/gemini.py`) — the Gemini
sibling of 14: manual, paid, never in CI, same enumeration, same prompt file and hash, rows
byte-compatible with the committed run shape. `model_annotations/genocide/comparison_run.txt`
names the counter-instrument run the way `current_run.txt` names the authority; 15 reads
both, refuses a comparison made against a different prompt, and publishes a `comparison`
block (per-field observed agreement, Cohen's kappa, contested counts) plus per-occurrence
`contested`/`alt` fields, all computed and never merged — the matrix, the stance profiles and
the diffusion stay drawn from the published run alone. The `/usage` view marks contested
occurrences in the drill-down, can filter to them, reports the agreement table in the
apparatus, and lists the most contested passages as a reading list with a full CSV.

**Acceptance and tests.**

- A comparison run with a different prompt hash is refused in words; identity checks are the
  published run's own.
- `function` disagreement is set inequality over the pipe-split labels; evidence quotes and
  confidence are never compared.
- The empty state (no comparison run) satisfies the same payload contract as the computed one.
- Every surface that shows a disagreement names both models and carries the
  stability-not-validation sentence.

## Phase E — institutional and historical extension

### E1. Rhetoric and formal Council action

Prototype a versioned join from meetings/speeches to draft resolutions, adopted resolutions,
votes and vetoes. Preserve document identifiers and distinguish preambular from operative
text. Start with a small hand-verified period before drawing a full timeline. Describe
temporal association and textual uptake, not causal effect.

### E2. Cross-corpus replication and pre-1992 extension

Pin the newer all-years corpus independently and reproduce the current 1992–2023 measures
on the overlap. Publish discrepancies by source field and measure as corpus-construction
sensitivity. Only extend before 1992 after the overlap comparison is understood; never
silently merge the corpora.

## Deliberate non-goals

- Rewriting the pipeline or replacing static hosting.
- Dropping MapLibre without measured cause.
- Adding a backend, user accounts or collaborative annotation platform now.
- Adding Snakemake, a general schema framework or a model registry pre-emptively.
- Restoring BERTopic/UMAP as a headline result.
- Generic sentiment scores, more word clouds or another location choropleth.
- Treating translation robustness as access to a speaker's unmediated vocabulary.
- Publishing a citable release while the human validation gate is open.

## Test matrix

Run the narrowest relevant test during development and the full applicable gate before a
task is marked complete.

| Change                              | Focused checks                                                          | Completion gate                                                     |
| ----------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Python pipeline/provenance/analysis | Targeted `pytest` module, deterministic fixtures, malformed-input cases | `python -m pytest` and `ruff check .`                               |
| Frontend logic or Svelte            | Targeted Vitest file; fixture contract tests                            | `npm test`, `npm run check`, `npm run lint`                         |
| Browser journey/accessibility       | Targeted Playwright spec against tiny fixtures                          | All frontend gates plus browser suite at wide and narrow viewport   |
| Shared payload contract             | Python producer and TypeScript consumer fixtures                        | Both full Python and frontend gates; static export contract check   |
| Production-facing route/build       | Relevant browser journey and base-path fixture                          | `npm run build` when the generated/static test payload is available |
| Analytical result                   | Unit tests, invariance/sensitivity tests, denominator reconciliation    | Full Python gates plus regenerated manifest and documented review   |

Before a tag, additionally rebuild the release payload from a clean tree, verify its
manifest and analytical hashes, run the browser smoke suite against the built site, archive
the audit report and perform the manual source checks in `VALIDATION.md`.

## Proposed first implementation slice

Start with four reviewable changes, in this order:

1. **I1:** dirty-worktree provenance and real-repository tests;
2. **I2:** `BaseMeta`/lexicon-aware metadata types;
3. **I3:** requiredness-aware contract fixtures and representation;
4. **A1:** safe separation of generated candidates and human annotations.

I1 and I2 are small corrections. I3 protects the cross-language boundary before A1 adds a
new artifact. A1 removes the risk of destroying human work before anyone begins it. A2–A3
are now complete; continue with U1–U3. Do not start a new visualization until those
integrity and evidence-navigation foundations are passing.

## Implementation log

Append one row for every completed or materially revised task. Record commands, not just
“tests passed,” so another person can reproduce the check. Commit identifiers may remain
`pending` until the work is committed.

| Date       | Task                              | Status     | Commit  | Verification                                                                                                                                                                                                            | Notes/decision                                                                                                                                                                                                                                                                                 |
| ---------- | --------------------------------- | ---------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-24 | Roadmap baseline                  | documented | pending | `python -m pytest` (608 passed); `npm test` (262 passed)                                                                                                                                                                | No implementation task started; MapLibre retained and annotation work split into preparation vs human execution.                                                                                                                                                                               |
| 2026-08-24 | I1 dirty-worktree provenance      | complete   | pending | `python -m pytest tests/test_artifacts.py -q` (19 passed); `python -m pytest` (613 passed); `ruff check .`                                                                                                              | Real temporary repositories cover clean, modified, staged, untracked and ignored states; the cluster stamp fallback remains covered.                                                                                                                                                           |
| 2026-08-24 | I2 metadata type hierarchy        | complete   | pending | `npm test` (263 passed); `npm run check`; `npm run lint`                                                                                                                                                                | `BaseMeta` now covers universal provenance; `LexiconMeta` is required by lexicon-derived payloads while speaker keyness uses the base.                                                                                                                                                         |
| 2026-08-24 | I3 contract requiredness          | complete   | pending | `python -m pytest` (617 passed); `ruff check .`; `npm test` (264 passed); `npm run check`; `npm run lint`                                                                                                               | Compact `?` markers distinguish optional collection fields; nullable values remain separate and Python/TypeScript fixtures agree.                                                                                                                                                              |
| 2026-08-24 | I4 stable analytical hash         | complete   | pending | `python -m pytest tests/test_artifacts.py -q` (23 passed); `python -m pytest` (643 passed); `ruff check .`; `npm test` (284 passed); `npm run check`; `npm run lint`; `npm run build`                                   | Nested-meta JSON artefacts receive a canonical SHA-256 identity automatically. Generation time, Git commit/dirtiness and a prior hash are excluded; analytical content, inputs and declared configuration remain included. Exact live test counts were removed from public prose.              |
| 2026-08-24 | A1 durable annotation boundary    | complete   | pending | `python -m pytest tests/test_audit.py -q` (12 passed); `python -m pytest` (629 passed); `ruff check .`                                                                                                                  | Generated candidates and review files are atomic and replaceable; human annotations are versioned separately and never written by the pipeline.                                                                                                                                                |
| 2026-08-24 | A2 interpretable sampling frames  | complete   | pending | `python -m pytest tests/test_audit.py -q` (16 passed); `python -m pytest` (633 passed); `ruff check .`; `python scripts/03_lexicon.py` (201 candidates; annotation SHA-256 unchanged)                                   | Equal-probability precision, term-period coverage and declared-pattern negative samples carry reconstructable probabilities, weights, seeds and hashes.                                                                                                                                        |
| 2026-08-24 | A3 annotation schema and codebook | complete   | pending | `python -m pytest tests/test_audit.py -q` (22 passed); `python -m pytest` (639 passed); `ruff check .`; `python scripts/03_lexicon.py` (201 candidates; annotation SHA-256 unchanged)                                   | Schema v2 separates match validity, quotation, stance, function, referent and evidence; controlled labels and offsets are validated before outputs write.                                                                                                                                      |
| 2026-08-24 | U1 minimal browser-test harness   | complete   | pending | `npm test` (265 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (7 Chromium journeys); `npm run test:e2e:sw` (1 built-site journey)                                                                        | Tiny committed fixtures cover base-path navigation, concordance URL restoration, exact-occurrence evidence navigation, filtered CSV and SVG provenance, retry, responsive controls, map fallback/keyboard access, production service-worker recovery and axe scans.                            |
| 2026-08-24 | U2 shared analytical URL state    | complete   | pending | `npm test` (281 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (7 Chromium journeys); `npm run test:e2e:sw` (1 built-site journey); `npm run build`                                                       | Concordance/reader, Actors, Chronology and Language restore their analytical controls from compact validated query strings. Presentational state—selected table row, contextual marks, chart zoom and graph arrangement—remains local.                                                         |
| 2026-08-24 | U3 exact occurrence navigation    | complete   | pending | `python -m pytest tests/test_kwic.py -q` (31 passed); `npm test` (272 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (7 Chromium journeys); `npm run test:e2e:sw` (1 built-site journey); `npm run build` | Stable hit IDs support exact scroll/highlight, copyable permalinks, continuous previous/next navigation, and a verbatim pipeline sentence copied with a plain project citation. CSL-JSON/RIS/BibTeX remain deliberately deferred until speech metadata and round-trip fixtures are sufficient. |
| 2026-08-24 | U4 participant-type evidence      | complete   | pending | `npm test` (284 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (7 Chromium journeys); production Chromium deep-link smoke; `npm run test:e2e:sw`; `npm run build`                                         | Chronology exposes the existing `participanttype` breakdown with its per-category/year denominator and keyboard-accessible evidence links. Concordance restores, filters and exports the normalized type; Reader navigation preserves the same result set.                                     |
| 2026-08-24 | U6 metadata and discoverability   | complete   | pending | `npm test` (289 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (7 Chromium journeys); `npm run test:e2e:sw` (1 built-site journey); `npm run build`; emitted HTML/XML inspection                          | Public routes share unique titles, descriptions, canonicals and Open Graph/Twitter cards. Generated sitemap and robots endpoints list only stable public pages; one software and one derived-data JSON-LD record identify the corpus DOI without promoting individual figures to datasets.     |
| 2026-08-27 | U7/U8/M5 defined                  | documented | pending | None; documentation only                                                                                                                                                                                                | External feedback on the deployed site asked for result-set composition and a concordance-to-time path, and reported the calendar title and language standfirst as unclear. Both became tasks rather than untracked edits. M5 records the lexicon-change workflow the same feedback asked for. |
| 2026-08-27 | U7, part 1: citable sort order    | complete   | pending | `npx vitest run src/lib/concordance.test.ts` (40 passed); `npm test` (301 passed); `npm run check`; `npm run lint`                                                                                                       | All five sorts now end on the occurrence ID, so tied keys — a delegation's hundreds of lines, an empty left context — settle the same way whatever order the filter produced. `describeSort` gives the control and the exported `sorted by:` line one name; the serialized `sort=country` is unchanged, so copied URLs keep their meaning. |
| 2026-08-27 | U7, part 2: result profile        | complete   | pending | `npx vitest run src/lib/concordance.test.ts` (60 passed); `npm test` (321 passed); `npm run check`; `npm run lint`; `npx playwright test e2e/tests/evidence.spec.ts` (8 Chromium journeys); `npm run build`                | The concordance profiles the set the reader assembled — by year and by speaker, group, participant type and agenda — and every row narrows or releases it. Counts are declared apparatus in the panel's own copy, which is why it is not a `Figure`. The chronology link carries the term and says the filters are left behind, because chronology state has no year range to receive them. The KWIC fixture gained a second speaker, year, agenda and participant type; three existing count assertions moved with it. |
| 2026-08-27 | U8 titles and prose               | complete   | pending | `npm test` (321 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (8 Chromium journeys); `npm run build`; both pages read on the built site against the real payload                                            | The calendar figure is "The vocabulary's calendar"; no figure title on the site now ends in a question mark, and the interrogative stays in the `question` prop where the house style puts it. Its reading note opens with the reporting-timetable expectation, drawn from the same computed months and shared agenda item as the caveat and shown under the same condition, so a reader meets the finding before reading the darkest squares as commemoration. The language standfirst names and glosses collocation, keyness and the co-occurrence network; the G²/log-ratio account is unchanged. The nav blurb "The words it sits next to" was reviewed and kept: it names the lead instrument, and the standfirst now carries the full inventory. |
| 2026-08-27 | U5 local research basket          | complete   | pending | `npx vitest run src/lib/basket.test.ts` (33 passed); `npm test` (354 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (13 Chromium journeys); `npm run test:e2e:sw` (1 built-site journey); `npm run build`                | Occurrences and whole speeches are kept in one browser with a note, and survive a reload. Items carry a snapshot plus the lexicon version and analytical hash they were taken under, so the drawer needs no fetches and a rebuilt corpus makes an item stale rather than empty. A basket from an unknown version is reported and left untouched; caps refuse in words. Exports carry provenance per row. Built as a dialog rather than a route, so no page metadata, sitemap or verify-static entries were added. The e2e KWIC fixture change also moved one count assertion in the service-worker journey. |
| 2026-08-27 | U3 step 4: citation formats       | complete   | pending | `npx vitest run src/lib/citation.test.ts` (18 passed); `npm test` (369 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (13 Chromium journeys); `npm run test:e2e:sw`; `npm run build` | The gate was assessed rather than assumed and written into U3: the occurrence ID is the locator because the official record gives no paragraph numbering here, and the UN Digital Library link stays labelled a search. CSL `speech`, RIS `GOVDOC`, BibTeX `@misc`, offered from the reader where the meeting is loaded so a citation can name the representative and not only the delegation. Golden fixtures plus parse-backs; the hostile-characters fixture caught an unescaped `%` in the percent-encoded permalink, which would have opened a TeX comment and swallowed the rest of the entry. |
| 2026-08-27 | M5 lexicon change workflow        | complete   | pending | `python -m pytest tests/test_contract.py -q` (20 passed); `python -m pytest` (all passed); `ruff check .`; claims read against `config/lexicon.yml`, `scripts/lib/contract.py` and A2 | `scripts/README.md` gains "Changing the lexicon": the fields a term needs and that its `note` carries the rationale, the version bump, the rerun order, and the four consequences worth knowing in advance — every downstream number moves, annotations do not carry over across an incompatible pattern change, the dashboard needs no code change because the term list comes from the exported index, and the contract needs no edit because it tracks one representative term file and contracts lexicon-keyed collections on presence and type. That last claim was checked against `contract.py` rather than assumed. The same file still printed exact test counts that I4 removed elsewhere; they are now gone. |
| 2026-08-28 | U8 follow-up: term picker         | complete   | pending | `npm test` (369 passed); `npm run check`; `npm run lint`; `npm run test:e2e` (13 Chromium journeys); `npm run test:e2e:sw`; `npm run build`; the deployed URL re-read against the real payload | Reported from the published site: the control that decides what the first chronology figure draws sat after the whole figure, below `Source` and the download row, so the apparatus stood between a reader and the one thing they came to change. The term chips now sit directly under the chart, above the value table and the footer, set as a subsection of the figure rather than a section of the page. This also removed a small untruth: the figure's own reading note said "pick terms from the list below the chart", and the list was below the figure. |
| 2026-08-28 | Phase L defined; L1 vocabulary     | documented | pending | `python -m pytest tests/test_audit.py -q` (25 passed); `ruff check .`; `audit.read_referents` over the committed file (29 identifiers) | Joël Glasman's feedback asked which genocide each delegation invokes and whether the speaker asserts or rejects the characterization. Neither is answerable from a count, so both became a phase rather than untracked edits: L1–L6 define the referent vocabulary, the double-coded gold sample, the model run, the aggregation, an experimental `/usage` view and its documentation. The conflict with H2 — model assistance only after H1 — is recorded in the phase's own decision rather than resolved by rewording H2, and is gated on standing experimental marking, displayed human/model agreement, human labels as the authority and the closing rule of `PLAN.md` §5. Scope is `genocide` alone; `CITATION.cff` is unchanged. L1's list is seeded in the same pass — 29 referents over `case`, `historical`, `meta` and `reserved`, with `iso3` and `years` as documentation the coding rule ignores — and the codebook moves to 2.1 with the two-coder protocol and the rule that model output is evaluated against human rows, never merged into them. The schema stays at version 2 because no field or controlled value moved. L1 is not complete: both coders must review the list before any scored coding or model run. |
| 2026-08-30 | L2 gold sample                     | complete   | pending | `python scripts/13_gold_sample.py` (three runs, byte-identical CSVs); `python -m pytest tests/test_gold_sample.py tests/test_occurrences.py -q` (36 passed); `python -m pytest` (754 passed at close of phase); `ruff check .` | 200 candidates over 195 distinct occurrences: 120 equal-probability, 80 coverage over decade × cue strata (rejection, quotation, commemorative, dense meeting, plain). The coverage frame exists for the stance question — equal probability alone would have sampled one rejection cue; it holds six. Human rows go to the new `annotations/genocide/annotations.csv`, its own file because `audit.merge` refuses annotations foreign to the candidates it is handed, so gold rows in the lexicon audit's file would crash 03. The cue is a sampling stratum, never a label, and the module comment says which near-misses it deliberately does not count. Coding itself is the open human check in `docs/VALIDATION.md` §6. |
| 2026-08-30 | L3 model annotation layer          | complete   | pending | `python -m pytest tests/test_llm.py -q` (32 passed, offline); `ruff check .`; `lib.llm` imports with no `openai` installed; 14 refuses without `OPENAI_API_KEY` before any read; `git check-ignore data/interim/llm_raw` | Code complete; **no run exists yet** — 14 is manual, paid, and never run by CI or the deploy. The prompt lives only in `model_annotations/genocide/PROMPT.md` (`## System` / `## User template`), hashed raw into every row and manifest, so an edited prompt is visibly a new run. One request per speech over the Batch API (`/v1/responses`), `--live` for the pilot, resumable by `--poll`; a speech failing validation lands in `failures.jsonl` rather than being retried until plausible. Target model verified against developers.openai.com on 2026-08-30: `gpt-5.6-luna` exactly (the `gpt-5.6` alias routes to Sol); effort set none–max enforced as argparse choices; the 100k output ceiling sits under Luna's 128k. |
| 2026-08-30 | L4 usage aggregation and contract  | complete   | pending | `tools/synthetic_usage_run.py` then `python scripts/15_usage.py --run-dir data/interim/synthetic_run` twice (identical but `meta.generated`; equal `analysis_hash`); `python scripts/export_web.py` (18 artefacts match); `--update-contract` diff = 174 insertions, 0 deletions, only the two usage entries; `python -m pytest -q` (754 passed); `ruff check .` | 15 aggregates a committed run, the gold rows and the corpus into `usage/{usage,occurrences}.json`, refusing in words a missing run, a stale lexicon or prompt, an unjoinable or duplicated row, a label outside the codebook, and a coverage gap (`--allow-partial` records the gap instead). Eligible = true-positive with verifiable evidence; assigned = eligible with a concrete referent; shares withheld below 20. `deploy.yml` gains the step and — fixing a live gap 03 already suffered — `annotations/**` and `model_annotations/**` in both the trigger paths and the derived cache key. The deploy now fails while `current_run.txt` is empty, which is the merge gate working as designed. |
| 2026-08-30 | L5 the `/usage` view               | complete   | pending | `npx vitest run` (413 passed incl. the two-way contract test); `npm run check` (0 errors); `npm run lint`; `npm run test:e2e` (18 journeys, 5 on `/usage`, 2 axe scans); `npm run build` (13 static entry points incl. `usage/index.html`) | The experimental apparatus opens the page: model id, run and prompt identity, coverage, abstention, the gold state, and the sentence that governs it — model-derived, human labels the authority. The matrix is one tab stop with roving arrow-key focus; abstention codes can never become referent columns; the 70-row cap is disclosed in words with the remainder in the CSV. Drill-down joins the KWIC lines and links each quotation into the reader and the concordance through the same `readerQuery` the concordance itself now uses. Methods gains rows 13–15 and an `experimental` state on `--state-warn`. Everything drawn so far draws from the clearly-labelled synthetic run. |
| 2026-08-30 | L6 documentation closure           | complete   | pending | claims read back against `README.md`, `docs/PLAN.md` §5, `docs/VALIDATION.md` §§2·6·7, `scripts/README.md`; `python -m pytest -q`; `ruff check .` | README moves the extraction row from deferred to experimental, counts seven views, and acknowledges Joël Glasman as instigator and second coder — `CITATION.cff` untouched per the recorded decision. PLAN §5 keeps its six requirements verbatim and maps where each now lives, naming what is still owed (sensitivity run, promotion thresholds). VALIDATION gains the gold sample (§6) and the model-run register (§7), and §2 no longer claims the referent list holds only reserved values. scripts/README documents 13–15, the run book with `gpt-5.6-luna` spelled exactly, and the price of editing the `genocide` pattern: new sample, new coding, new run. |
| 2026-08-30 | L7 diffusion of the word           | complete   | pending | `python -m pytest -q` (766 passed, `tests/test_usage.py` at 52); `ruff check .`; `--update-contract` diff = 19 insertions, 0 deletions, all inside the `diffusion` shapes; `npm test`; `npm run check`; `npm run lint`; `npm run test:e2e` (2 new `/usage` journeys, axe clean); `npm run build`; the synthetic render read in the browser | Same feedback, second round: the diffusion question — when each delegation first said, first asserted, first rejected the word for each referent. No new model call: `usage.json` gains a `diffusion` block of dated first events per (referent, delegation) in three milestone classes, each carrying its KWIC line id; on the synthetic fixture the `mention` events equal the matrix cells exactly (1,801), which is the invariant that says the two blocks count the same population. `/usage` gains a cumulative step figure (assertion solid, refusal dashed, mention drawn only when it differs from assertion) over a fixed cross-referent time axis, with the chronology table — the historian's deliverable — beneath it, driven by the same `?referent=` state as the matrix, and the caveat in the figure's own apparatus: the curve counts delegations speaking in this corpus, absence is not refusal. |
| 2026-08-31 | L8 the second opinion              | complete   | pending | `python -m pytest -q` (803 passed; `tests/test_gemini.py` 26, all offline; the request-parity and same-population tests bind 14 and 16); `ruff check .`; contract diff = 33 insertions, only the comparison shapes; `15_usage.py` verified in both states — synthetic pair (overlap 5,952, contested 1,642) and real run + empty comparison — against the same contract; `npm test` (448); `npm run check`; `npm run lint`; `npm run test:e2e` (26 journeys incl. the none-state variant); `npm run build` against the real payload, unchanged | Gemini 3.7 Flash as counter-instrument (API surface verified on ai.google.dev, 2026-08-31; `gemini-3.7-flash`, thinking high, Batch at half price, `responseJsonSchema` passthrough). 16 is 14's sibling; a test asserts both providers are sent byte-identical messages and schema, and another that they annotate the same documented population. `comparison_run.txt` names the counter-instrument; 15 refuses a different prompt hash and a self-comparison, computes per-field observed/kappa and per-occurrence `contested`/`alt`, and never redraws matrix, stance or diffusion from it. The view marks contested rows, filters on `contested=1`, tables the agreement in the apparatus and lists the most contested passages with a full CSV — each surface carrying the sentence that governs the phase: agreement between two models is stability across instruments, never accuracy. **No comparison run exists yet**: `comparison_run.txt` is empty, the live payload renders the none state, and the run waits on a `GEMINI_API_KEY` (~$12 in Batch). |
| 2026-09-01 | Lexicon v3 (review §3.4, item 1) | complete   | pending | `python -m pytest` (all passed on the merged tree; `tests/test_lexicon.py` new, `tests/test_config.py` +4, `tests/test_usage.py` +5); `ruff check .`; the v2 literal `war crime` shown to count 0 where the regex counts 1 on `war\ncrimes` | Two counting corrections from `docs/REVIEW_2026-09-01.md`: prefilters made whitespace-free and provably contained in every match, and register/total roll-ups summed over `lexicon.summable` so a nested term is not counted on top of its parent. No pattern changed. `pattern_since` per term and `Lexicon.compatible` let 15 accept the v2 model runs under v3; `09_export_speeches.py` now reconciles per-term counts rather than the de-duplicated total. Corpus-level effect to be recorded in `VALIDATION.md` on the next run of 03; the network policy of the environment the fix was written in did not reach Dataverse. |
