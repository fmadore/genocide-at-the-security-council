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

### U4. Expose existing participant type

**Status: complete on 24 August 2026.**

Add `participanttype` as a chronology split/filter using existing normalized data. Publish
its denominator and evidence link exactly as for current splits. This is intentionally a
small feature before any new analytical pipeline.

### U5. Local research basket — optional after U1–U4

Allow bookmarking occurrence IDs and speeches in local browser storage, with a note and
CSV/JSON/Markdown export. No accounts, synchronization or backend. Treat schema migration,
storage limits, deletion and export provenance as acceptance criteria. Build it only after
exact occurrence IDs are stable.

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
