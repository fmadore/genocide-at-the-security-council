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
- Annotate with open weights served on university hardware rather than with hosted commercial
  APIs. A run has to be reproducible from its own record, and a model reachable only as a
  service cannot be pinned the way the corpus, the lexicon and the prompt already are. See
  Phase C; the reason is reproducibility, not cost and not confidentiality.

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
|     6 | R1–R15 the second reader's second review       | Say on each figure where its numbers came from, before adding figures | Both coders review three lists; no coding yet |
|     7 | C1–C7 the models move to the cluster           | Every committed run is stale after the corpus migration, and the next run should be one a reader can repeat | No |
|     8 | H1–H2 human-coded interpretation               | Answer what the term is doing rhetorically                            | Yes                                           |
|     9 | E1–E2 institutional and historical extension   | Add new data sources and new claims only after the core is stable     | No, but substantial research review is needed |

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

**Status: complete on 27 August 2026.** Follow-up in U9.

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

### U10. The referent path, and the page's own map

**Status: complete on 2 September 2026.** Item 11 of the prioritised plan in
[`REVIEW_2026-09-01.md`](REVIEW_2026-09-01.md) §8; §5.3 is its specification.

The historian's question — when, and by whom, was the word used about Rwanda — is a
referent question, and it routed only through the experimental `/usage` page, unsignposted.
Now the concordance carries a **referent** facet for `genocide`, drawn from the published
model run (`usage/occurrences.json` joined on the line id, labels from `usage.json`), marked
*model-derived, experimental* beside the control and carried in the URL as `referent=`;
without the run loaded the filter keeps nothing rather than everything, so a copied link
never shows the whole corpus under a referent's name. A delegation's panel on Actors links
to `/usage?actor=…`. Every `Figure` has an `id` (a slug of its title, from
`$lib/figures.ts`, or one it declares) and its title is its own anchor; the four
multi-figure pages open with a `Contents` list of their figures. The chronology's term
picker is grouped under register headings rather than by a coloured edge; corpus keyness
and per-speaker keyness link to each other from their `more` notes; and the usage unit
toggle's rules, which lived only in `title` tooltips, are printed beside it.

### U9. A word budget for every figure

**Status: complete on 2 September 2026.** Item 3 of the prioritised plan in
[`REVIEW_2026-09-01.md`](REVIEW_2026-09-01.md) §8; §5.1 is its specification.

Every `Figure` is held to a budget: `question` ≤ 20 words, `reading` ≤ 60, `caveat` ≤ 50,
counted with every conditional branch and each `{expression}` as one word, the way the
review counted. `web/scripts/word-budget.mjs` reads every `<Figure>` under `src/` and
fails `npm run lint` on overflow, so the budget is a gate rather than a wish. Overflow a
reader might still want — a withholding rule in full, a second-order caveat, a worked
example — goes in a new `more` snippet, a disclosure in the margin capped at 150 words;
method goes to Methods behind an anchor (`#change-points`, `#keyness`, `#word-list`);
engineering narration and restated marks are deleted. The 26-word download hint under
eighteen figures became the CSV button's tooltip. On the actors page the closing list that
re-ran the figure's caveats is gone, and `minimum_speeches_rule` and `centroid_rule` are
printed once. Apparatus fell from 4,964 words over twenty figures to 2,210.

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

**Amended 2 September 2026** (review §8, item 8; §5.2): MapLibre stays, as a locator. The
circles were sized linearly in the radius by the ranked figure, which overstates every
difference quadratically, and the choropleth shaded a successor state's territory for a
historical speaker and drew the eye to whichever country was large. Both went: every dot
is the same size and the same ink, the selection takes the accent, and the ranked table —
with its Wilson whisker column — is the figure, set above the map inside the same frame.
`$lib/choropleth` and its tests are deleted; `view=` in a copied URL is ignored. The
boundary file `web/static/geo/countries.json` and `tools/build_boundaries.py` are no
longer read by the site and can go when the next static audit runs. The same item
replaced the word cloud with a dot plot (`$lib/DotPlot.svelte`, `dotplot.ts`: position by
log ratio, area by frequency, a spread mark for DP, every word a link) and the force
network with a register-ordered adjacency matrix (`$lib/TermMatrix.svelte`, `matrix.ts`:
shaded by nPMI, hatched below the minimum, crossed where the pair is definitional), and
reserved the register hues for registers: the split-by-category figure, the standing
bands and the stance profile now take weights of ink (`theme.categoricalNeutral`).
`d3-cloud` is removed from the dependencies.

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

**Amended 2 September 2026** (review §8, item 13; §6.4–6.5). The `Makefile` is now the
pipeline's single DAG — one target per step, keyed on the file it writes, declared against
every input it reads, with `raw` phony so 00 always MD5-checks the corpus — and
`deploy.yml` runs `make payload` rather than a copied list; `README.md` and
`docs/CLUSTER.md` point at it. `tests/test_end_to_end.py` runs 04 and 08 as subprocesses
over a deterministic synthetic corpus, with the data, notes and web roots redirected by
`GENOCIDE_DATA_ROOT`, `GENOCIDE_NOTES_ROOT` and `GENOCIDE_WEB_DATA_ROOT`, and compares
their analytical values — rates, intervals, both p-values, KWIC lines — against
`tests/golden/end_to_end_04_08.json`; `UPDATE_GOLDEN=1` regenerates it, and the diff is the
review. Writing it found two places where 04's note formatted a withheld month as a number
and one sentence the review had flagged as unconditional; both are fixed.
`tests/test_requirements.py` holds `requirements.lock` inside the declared ranges, and
`.github/dependabot.yml` groups weekly updates for pip, npm and Actions. 11 and 12 assert
the codebook's totals and refuse a synthetic corpus, so the end-to-end test stops at 04 and
08; 05 needs a corpus large enough for anything to clear the G² floor. **Owed, and not
doable from a runner:** a tagged release with `data/derived/` and the manifests deposited on
Zenodo, so the payload exists somewhere other than an Actions cache that evicts after seven
idle days — the checklist is: run `make payload` on the pinned corpus, tag the commit, attach
`data/derived/manifests/` and `web/static/data/manifest.json`, deposit `data/derived/` on
Zenodo under the CC0 data licence, and write the DOI into `CITATION.cff`.

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

**Status: first slice complete on 2 September 2026, re-calibrated on the corpus the same
day.** This is item 2 of the prioritised plan in [`REVIEW_2026-09-01.md`](REVIEW_2026-09-01.md) §8, and
the review's §3.1, §3.3 and §5.2 are its specification.

Add meeting-block bootstrap intervals and sensitivity to high-volume meetings to existing
actor and time comparisons. Use cluster-robust or beta/negative-binomial alternatives only
where the estimand and observed dispersion warrant them. Publish the unit of resampling,
seed, repetitions and failure/withholding rules.

The first slice lands the two changes the review ranked highest:

1. **The rate change-point test is calibrated against a meeting-block null.**
   `lib/series.py::rate_change_point` takes the per-meeting blocks that
   `series.meeting_blocks` builds (period, count, exposure) and, for every trial, permutes
   the assignment of meetings to years — each year keeps its number of meetings, a meeting
   travels with all of its speeches and all of its hits — before repeating the whole
   search. The published `p_value` is the block one; the parametric independent-speech
   p-value the site used until now is kept beside it as `p_value_independent`, and the
   artefact names the null it used in `null` and the number of blocks in `blocks`.
   `accepted` follows the block p-value. The function refuses blocks that do not add back
   up to the counts and exposure they are meant to calibrate.
2. **Every `speech_rate` carries its Wilson 95% interval.** `series.wilson_interval` is
   the one implementation; `series.measure` writes `speech_rate_low` and
   `speech_rate_high` beside the rate, `withhold_below` blanks all three on the same rule,
   and the bounds reach `series/annual.json`, `quarterly.json`, `monthly.json` (grid and
   pooled calendar), `breakdowns.json` and `countries/countries.json`. The site draws them
   as bands on the chronology's main and split-by-category figures and as a whisker column
   on the actor ranking, and prints the range in every hover box and CSV.

Also in the slice, from the same review section: the findings note is built from the
corrected `inference` block rather than the exploratory one, and no year is typed into its
prose; the change-point figure shows both p-values and marks a best split that is not
accepted as such rather than reporting "no change detected".

Acceptance: `python -m pytest` and `ruff check .` pass; `npm run lint`, `npm run check`,
`npm test` and the Playwright journeys pass on the fixtures; the contract diff is additive
only. **Landed on the corpus** in deploy run 59 of 2 September 2026: the 2017 and 2016
`genocide` splits hold under the block null (p = 0.0010 and 0.0095, against 0.0005 under
the independent one), the 1996 `atrocity_core` split does not (p = 0.0255), and
`README.md`'s change-point paragraph is rewritten from the artefact (`VALIDATION.md`, “The
rate tests under a meeting-block null”). Left for later slices of S1: meeting-block intervals on
the collocate and keyness tables (with S5), the funnel plot (S3), the mixed model (§3.6).

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

**Status: first slice complete on 2 September 2026, run on the corpus the same day; the
re-ranked tables are still to be read.** This is item 7 of the prioritised plan in [`REVIEW_2026-09-01.md`](REVIEW_2026-09-01.md) §8, and
the review's §3.2 is its specification.

For every collocate add distinct meetings, speakers and years; meeting dispersion;
leave-one-meeting-out sensitivity; surface/lemma sensitivity; weighted log-odds; and
meeting-level bootstrap intervals where feasible. Then expose a collocate-by-period matrix
using color for direction/magnitude, size for frequency and a separate mark for dispersion.
Do not add another word cloud.

The first slice changes what a table row is and how a table is ordered:

1. **Significance is a floor, not a rank.** `lib/lexical.py::compare` keeps a row only
   when |G²| clears `G2_FLOOR` (10.83, p < 0.001) and orders the kept rows by effect —
   `log_ratio` for keyword tables, `log_dice` (Rychlý 2008) for collocate tables, which
   now carry it — with G² and then the word as tie-breakers so every run orders alike.
   The floor and the ranking are written into each artefact's `meta`.
2. **Every row carries its dispersion.** `lexical.dispersion` gives the documents and
   distinct meetings a word appears in and Gries's DP over the target speeches (or the
   collocate windows); `DocumentTerms.dispersion` computes the same numbers over the
   speaker-keyness matrix and a test holds the two equal. Collocate tables, the keyness
   table, the sliced profiles and every speaker's keyword table carry `documents`,
   `meetings` and `dp`; the site prints them beside every row and its CSVs export them.
3. **The tokeniser no longer loses the scare-quoted word.** `TOKEN_RE` cannot end on an
   apostrophe or hyphen — `'genocide'` was a type of its own — and may carry a digit after
   its first letter, so `R2P` is one word. Consequence recorded below: the lemma layer
   from `10_lemmatise.py` is aligned token by token to the old pattern and must be
   regenerated before `05 --vocabulary lemma` runs again; `lemmas.tokens` refuses a stale
   row rather than shifting every window after it.
4. **Definitional edges are suppressed by rule, with their reason.** `denial`'s pattern
   contains `genocid`, so the `denial`–`genocide` edge was partly a fact about the lexicon;
   `lexical.definitional_pairs` finds such pairs by running each term's regex over the
   other's declared examples, the network no longer draws them, and the artefact lists
   every suppressed pair with why.

Acceptance: `python -m pytest` and `ruff check .` pass; `npm run lint`, `npm run check`,
`npm test` and the Playwright journeys pass; the contract diff is additive only. **Run on
the corpus** in deploy run 59 of 2 September 2026, its console output recorded in
`VALIDATION.md` (“Lexical tables: a floor, an effect ranking, and dispersion”). **Still
owed:** the re-read of the re-ranked tables from the published language page against the
words `README.md` and `docs/CORPUS.md` §8.5 name; the token count the tokeniser change
moved, which needs the pre-change commit run beside this one; and `10_lemmatise.py` on the
cluster before the lemma sensitivity reading is redrawn. Left
for later slices: leave-one-meeting-out sensitivity, meeting-block intervals on the effect
sizes (the 20-seed band is still control-draw variance only), the collocate-by-period
matrix, and the dot plot that replaces the cloud (review item 8).

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

**Superseded in transport by Phase C, 4 September 2026.** The paid hosted API and its Batch
queue are replaced by an open-weights model served on the cluster. What L3 requires of the
step — the schema, abstention as a value, the committed run, the manifest, the verified
evidence quote, the absence from CI — is unchanged and is why the swap is only a transport
change. The text below stands as the decision that was made at the time.

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

**Counter-instrument changed by Phase C, 4 September 2026.** Gemini 3.7 Flash is replaced by
`deepseek-ai/DeepSeek-V4-Flash-0731`, or by `google/gemma-4-31B-it` if that model cannot be
served on the cluster, read against a published run from `Qwen/Qwen3.8-27B`. The requirement
it satisfies — a second model from a different family, the byte-identical prompt, agreement
computed and never merged — is unchanged, and C6 adds the one thing the new pair needs that
the old one did not. The text below stands as the decision that was made at the time.

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

## Phase R — the second reader's second review

**Source.** A recorded working session with Joël Glasman, in two parts, read on 3 September
2026. Phase L came out of his first round of feedback (implementation log, 28 August); this
is the second round, and it was held over the site as it then stood — the
`2026-08-30-luna-v1` run, prompt v1, referent list v1, *Rwanda 1994* still a column heading.
It is a conversation and not an audit: nothing in it was computed, two figures quoted in it
do not survive checking, and what is recorded below is the author's decision on each point
rather than the transcript. R1–R8 come from the first part, R9–R15 from the second.

**Relation to [`REVIEW_2026-09-01.md`](REVIEW_2026-09-01.md).** The two overlap and were made
independently, which is worth something: where the reader and the review agree, the finding is
not an artefact of either one's method. The review is the more precise instrument on the
prompt (§4.2), the referent list (§4.3), the evaluation design (§4.4) and the figures (§5.2);
the session is the more precise instrument on what the *dashboard* claims about itself, which
the review treated as prose length (§5.1) rather than as provenance. Sections of the review
are cited item by item below. Nothing here supersedes it.

**What the session asked for that is already done**, and should not be reopened: dates out of
referent labels (`rwanda_1994` → `rwanda`, `ukraine_2022` → `ukraine`, `drc_great_lakes` →
`drc`, years demoted to documentation the coding rule ignores); the Great Lakes dissolved into
the DRC; Gaza doubled by an undated `israel_palestine`; the Holodomor separated from Ukraine
and Khojaly from Nagorno-Karabakh; `hypothetical_future` retired; twelve referents added from
the `other` bucket, which v2 projects to reduce by 76.9%; the case question (`concrete_case`)
asked once and before the position, which is the layer separation the session asked for; the
distancing rule; ten worked examples taken from the corpus; and the meeting symbol and agenda
item already passed to the model, with `referent_source` recording when a referent was read
off them alone. The session's proposal that the United States be added as a case was tested
against both runs and refused on evidence (`VALIDATION.md` §7, *What v2 refuses*).

**One figure from the session does not survive checking.** `economic_sanctions_other` holds 14
occurrences in the published run and `cuba_us_sanctions` 5, not the 813 read off the screen
during the conversation. R1 therefore rests on the epistemological argument alone, and the
volume argument is withdrawn.

**The prerequisite.** No run has been made against prompt v2, so the published site still
reads the schema-2 runs: `accused_actor`, `victim_group`, `own_state_accused`, `salience` and
`referent_source` do not exist in any committed row. R2 is entirely blocked on a v2 run, R1
rewrites the vocabulary such a run would use, and R3 and R4 describe surfaces whose columns
that run renames. **Make the run before building on any of it**, on the pilot design already
provisioned in `VALIDATION.md` §7. Nothing in R5, R6 or R7 depends on it.

**The corpus underneath this phase is being replaced.** The session asked whether the record
could be extended past 1992–2023 by scraping the Security Council's own documents. It is
being extended, and not by scraping: the author found a second published corpus and began the
migration on 3 September 2026 — Sakamoto and Matsuoka, *The UNSC Meetings and Speeches*,
Harvard Dataverse `doi:10.7910/DVN/CKPTRB` v5.0, CC0, released 31 March 2026, **1946 to 2024:
167,642 speeches over 9,464 meetings with speeches**, against Schoenfeld et al.'s 106,302 over
6,582. The work is in the tree and uncommitted at the time of writing (`00`, `01`, `02`,
`lib/council.py`, `lib/entities.py`, `lib/paths.py`, the dataset pin, and a new
`tests/test_build_sakamoto.py`); it is not an item of this phase and is recorded here because
every figure in this phase is measured on a corpus that is moving. Scraping is therefore not
proposed: a DOI-pinned, immutably versioned, CC0 corpus is worth more than a crawl of
`undocs.org` on every axis this project cares about — checksums, citability and the fact that
somebody else maintains it.

Two consequences the phase inherits, neither of them optional:

- **The model layer does not follow.** `15_usage.py` drops any row whose `source_sha256` says
  the speech has changed, so a corpus swap does not corrupt `/usage` — it empties it. There
  is no partial credit here and the guard is right. The committed runs cover 3,273 speeches
  and 6,092 occurrences of the old corpus; the new one carries **4,133 genocide-bearing
  speeches and 7,747 occurrences**, a quarter more, and 535 of those speeches are before 1992
  and 445 after 2023 — periods no run has ever seen.
- **Every number in this phase is corpus-dated.** Figures below are marked *(1946–2024)* where
  they were recomputed on the new corpus and *(1992–2023)* where they were not. A number
  without a corpus is not a number here.

**The order of work**, settled in the session and governing R1, R2 and the function layer.
Referents first; then a second model over the same occurrences; then read *only* the
occurrences the two instruments disagree on, and ask whether one of them is systematically
worse or whether the errors are random, because the first case chooses an instrument and the
second does not; then refine the vocabulary on what that reading found. The rhetorical
`function` field waits for all of it — in the session's words, going to function before the
referent is secure would be premature. L8 already builds the comparison run and
`REVIEW_2026-09-01.md` §4.4 already specifies the disagreement-stratified sample; what is new
is that the sequence is now a decision rather than an option.

### R1. Two classifications, not one: the situation, and what is being called genocide

**Decision, 3 September 2026.** The list mixes two questions and answers them in one column.
`darfur`, `rwanda` and `gaza` name situations; `cuba_us_sanctions` and
`economic_sanctions_other` name a *kind of act* being characterised; `colonial_era` names a
period; the three non-case referents name a register of speech. A single column cannot hold
them without the coder — human or model — silently choosing which question to answer, and the
review's §4.3 revision improved the situations without touching the mixture.

Split it. `referent` keeps one job: which situation, event or people the word is applied to. A
second field, `modality`, records what is being characterised — armed conflict, ethnic or
religious persecution, economic sanctions, military intervention or occupation, colonial rule,
famine or starvation, forced displacement. The Iraq sanctions rows then read as *Iraq* +
*economic sanctions* rather than as a category that is neither, and the question the session
kept returning to — is a sanctions regime being called genocide, and by whom, across all the
countries it is claimed of — becomes a column rather than a search.

The cost is real and is not hidden: splitting a populated category makes two sparser ones, and
some rows will carry a modality with no situation to attach it to (`colonial_era`'s 7
occurrences may be exactly that). A modality that ends up on fewer rows than the category it
replaced is a finding about the corpus, not a failure of the split, and it must be published
as one.

Fine categories also destroy the sum. `referents.csv` therefore gains a `group` column —
`great_lakes`, `former_yugoslavia`, `the_sudans`, `iraq_and_syria`, `israel_and_palestine`,
`the_caucasus`, `ukraine_and_russia` — so the matrix can collapse to groups and answer "how
many delegations place the word anywhere in the Great Lakes" without abandoning the
granularity that makes a cell readable.

**One occurrence, two cases.** The second part of the session sharpened this, and it is not
the problem it first looks like. A speech that discusses two genocides produces two
occurrences, each annotated separately with the whole speech as context, and nothing is lost.
The problem is *one* occurrence naming two cases — "genocide in Rwanda and in the Congo" —
where the current rule, code the first named and put the pair in `proposed_referent`, is
exactly the wrong answer: it discards half the evidence and records the loss in a free-text
field that only fires when the model also chose `other`. The convention therefore hides its
own frequency. 44 such pairs appear across the two runs, but only among the 641 `other` rows;
how often a compound was silently flattened onto a controlled identifier is unknown, and
unknowable from the committed runs.

**The decision is a bounded second slot, not a list.** `referent_secondary` takes one further
identifier or nothing; three or more cases in one occurrence stay `other` with the list in
`proposed_referent`. The three alternatives were considered and are recorded so the bound is
not mistaken for an oversight. Making `referent` a list breaks the sentence the matrix is
built on — *a cell is a count of occurrences* — and turns a single-label field into a
multi-label one, which costs Cohen's κ and buys a distribution nobody has asked to see.
Emitting two rows for one occurrence breaks `occurrence_id` as a primary key, which every
join in the pipeline uses. A second slot keeps every existing count valid on the primary
field, needs no new statistics — the pair scores as a set with Jaccard exactly as `function`
already does — and makes the loss measurable for the first time: the share of occurrences
whose secondary slot is filled *is* the measurement of what the old convention was throwing
away. What it still costs is stated rather than hidden: a passage naming three cases is
degraded, and the bound at two is a decision taken on 5% of one bucket, not a finding.

**Change.** `annotations/lexicon/referents.csv` to v3 (`group` column; the two modality-shaped
identifiers retired with successors, per the versioning rule the file already enforces); a new
`annotations/lexicon/modalities.csv` on the same pattern, seeded from the two runs' evidence
quotes rather than invented; codebook to 4 and annotation schema to 4; prompt to v3 with the
modality block and its own worked examples; `15_usage.py` publishes `modality` beside
`referent` and a `group` roll-up; the `/usage` matrix gains a *collapse to groups* control and
a modality axis. **Both coders review the modality list before any run uses it**, as L1
requires of the referent list and for the same reason.

**Acceptance and tests.**

- A run recording referent version 2 is still read under v3 through `superseded_by`; the
  existing staleness refusal covers modality identically.
- The group roll-up is a partition: every case referent belongs to exactly one group, asserted
  in `tests/test_audit.py`, and the collapsed matrix's row totals equal the expanded one's.
- `modality` is `not_applicable` on a false positive and on a non-case mention, by the same
  cascade that governs `referent`, and the cascade test covers it.
- The published figure states how many occurrences carry a modality and no situation.
- `referent_secondary` is empty or one identifier from the same list, never equal to
  `referent`, and never filled when `referent` is a reserved identifier; the matrix publishes
  primary-only counts by default and offers *primary or secondary* as a unit, the way it
  already offers count and share. The share of occurrences using the second slot is
  published, because it is the only measurement of what the previous convention cost.

### R2. The accuser and the accused

**Decision, 3 September 2026.** Schema 3 extracts `accused_actor` and `own_state_accused` and
nothing aggregates either; they appear only in the detail of a single occurrence. The
session's question — how many delegations accuse the United States of genocide, counting Cuba
on the embargo and Iraq on the sanctions together — is not answerable from the site today, and
it is closer to the study's own question than the referent matrix is. A referent matrix says
what the Council talks about. An accuser-by-accused matrix says who the Council accuses, which
is the thing a historian of the institution wants.

`accused_actor` is free text by design, because the passage's own words are the evidence. It
therefore needs the same treatment `referent` got: a controlled list beside it, not a model
normalising itself. `annotations/lexicon/accused.csv` maps observed strings to identifiers
over four kinds — States, non-State armed groups, international bodies and individuals —
seeded from the runs' strings and reviewed by both coders. An unmapped string stays unmapped
and is disclosed; it is never guessed into a neighbour.

The diagonal is not noise. `own_state_accused` already marks the cell where the speaker is the
accused, and those cells are the denials — the most legible rhetorical act in the corpus, and
the one the China example in the session turns on.

**Change.** `annotations/lexicon/accused.csv`; normalisation in `scripts/lib/usage.py` against
that file alone; an `accused` block in `usage/usage.json`; a second matrix on `/usage`, drawn
by the existing `UsageMatrix`, rows the speaking delegation and columns the accused actor,
cells clickable to their occurrences like the first; self-accusation marked, not filtered.

**Acceptance and tests.**

- Blocked on a v2 run: with the schema-2 runs the block is empty and the figure states so
  rather than drawing nothing. The empty state satisfies the same payload contract as the
  computed one, as L8 requires of the comparison block.
- The share of eligible occurrences carrying no accused actor is published beside the figure.
  A passage that accuses no one is data — the prompt says so — and a matrix that hides its own
  denominator would make that look like coverage.
- Every unmapped string is counted, and the count is in the disclosure.
- The figure carries the model-derived mark of R3.

### R3. Provenance on the face of every figure: computed, mixed, model-derived

**Decision, 3 September 2026.** The site marks provenance by page — a ledger on Methods, an
*experimental* blurb in the navigation, a caveat under the `/usage` figures, a *model-derived,
experimental* label beside the concordance's referent facet. The session asked for it by
figure, on a three-step scale: green where the number is computed from the record, red where
it is entirely a model's reading, amber where a figure mixes the two. That is a scale of
**provenance**, not of reliability, and it is the more defensible of the two — a model label
can be right and a computed count can measure the wrong thing.

Two constraints on the implementation.

*The colour is derived, not asserted.* `Figure` already names the script and artefact behind
it in `source`. The mark is a pure function of that string: scripts 01–13 and 17 are computed,
14 and 16 are model-derived, 15 is model-derived because its inputs are, and a figure whose
`source` names both is mixed. An author cannot mislabel a figure without lying about where its
numbers came from, and `web/scripts/word-budget.mjs` already walks every `<Figure>` in the
tree, so the check is a lint rule rather than a convention.

*Green is labelled "computed from the record", never "objective".* The session used the word
with its own scare quotes, and they belong. The lexicon is a hand-built instrument, the
reference dates are a curated overlay and the frames codebook is a hand-written regex; each is
computed and none is neutral. The scale says who produced a number, which is checkable; it
does not say the number is true.

*The mark also belongs in the navigation.* The second part of the session read the site
view by view and sorted it unprompted — concordance and chronology are "the indisputable,
objective thing", Actors is "algorithmic mechanics", Usage "goes into the LLM", Methods is
something else again — which is the same three-step scale applied to pages. A reader choosing
a view should see what kind of thing is behind it before they arrive, not after. A page takes
the weakest mark any figure on it carries, so `/usage` reads model-derived and `/concordance`
reads computed even once R9 puts a model-derived facet on it.

One finding from the same pass belongs here rather than in R14: **the Language view's purpose
did not survive contact with its reader.** "Language, for me, what is that?" is not a
complaint about a figure; it is a view whose name and question do not tell a historian what
it is for. Naming it is part of this item, because a provenance mark on a page nobody can
place does not help.

**Change.** `provenance` derived in `$lib/figures.ts` from `source`, with tests; a mark in
`Figure`'s caption, one legend on Methods, and a link from each mark to it; the four
hand-written restatements on `/usage`, `/concordance` and `+layout.svelte` removed in favour
of the one mark. Nineteen figures across six views; the six ECharts and MapLibre ones carry it
into full screen under R5. The same three values are carried in `+layout.svelte`'s navigation,
derived from the figures each view holds rather than declared a second time, and `/language`
is renamed to say what it answers.

**Acceptance and tests.**

- The derivation is total: every `source` string in the tree resolves to exactly one of three
  values, asserted over the parsed figure list rather than over a hand-kept inventory.
- A figure drawing model output whose mark says computed fails `npm run lint`.
- The mark survives full screen, print and the fallback tables.
- The Methods ledger's four states stay: they describe a *pipeline step*'s standard of proof
  and are a different claim from where a figure's numbers came from.

### R4. `confidence` comes off the model schema and off the page

**Decision, 3 September 2026.** The field measures nothing. Gemini wrote `high` on 6,035 of
6,092 occurrences (99.06%) and `low` on none; Luna wrote `low` four times; neither run
returned a single `uncertain` verdict. `lib/usage.py` already excludes it from Cohen's kappa
for exactly this reason, on the review's §4.5 item 5, and §4.6 lists it among the things
`/usage` should not show. It is nevertheless still requested by the prompt, still stored on
every row, and still printed under every occurrence on the page, where "confidence high" reads
to a visitor as a warrant it is not.

Remove it from the model's schema, from the payload and from the page. The uncertainty signals
that do discriminate are already computed and are not shown: `referent_source`, which
distinguishes a referent read off the passage from one read off the meeting header, and the
cross-instrument contest flag, which is a disagreement between two independent instruments
rather than a model's opinion of itself.

**Keep the human coder's `confidence`.** A person who writes `low` is abstaining, which is the
behaviour the model does not have, and the codebook's instruction to record it is sound. If it
should go from the human schema too, that is a codebook 4 decision and is not taken here.

**Change.** Drop `confidence` from the JSON schema and `MODEL_FIELDS` in `scripts/lib/llm.py`,
from the prompt's FIELDS block in prompt v3, from the `usage/occurrences.json` row and from
`usage/+page.svelte`'s occurrence line. `lib.audit`'s `ANNOTATION_FIELDS` keeps it for the
human file. The two committed runs keep the column they were written with; nothing rewrites a
committed run.

**Acceptance and tests.**

- A schema-3 run's rows still load after the field is dropped from the reader; the payload
  contract is updated on both sides.
- The kappa floor's comment in `lib/usage.py`, which cites the 99.06%, is kept as the record
  of why the field went.

### R5. Full screen on every ECharts and MapLibre figure

**Status: complete on 4 September 2026.** The opt-in now lives on `Figure`, is enabled for
the five ECharts figures, the Actors map and the delegation-by-referent matrix, and carries
the complete caption and provenance apparatus into both the native and fixed-overlay paths.
The matrix browser spec exercises the fallback, reads a real cell, exits with Escape, checks
focus restoration and runs the accessibility scan.

**Decision, 3 September 2026.** Asked for twice in one session, over a table too wide to read
in the column it sits in. Five ECharts figures (`Chart.svelte`: the home page ×2, chronology
×2, language ×1) and the MapLibre map on Actors get a full-screen control — six figures, one
of which is the home page's register chart and so is R7's to re-cut or remove first.

**One correction to the scope.** The table the session actually wanted to enlarge — the
delegation-by-referent matrix — is `UsageMatrix.svelte`, an HTML table, and is neither ECharts
nor MapLibre. Building the control for the chart libraries alone would miss the request that
produced it. Put the affordance on `Figure`, where the caption and the R3 mark already live,
and turn it on for the six chart and map figures **and** the matrix, with the other figures
able to opt in later.

**Change.** A `fullscreen` opt-in on `Figure` using the Fullscreen API, with a CSS
fixed-overlay fallback for iOS Safari, which has no `requestFullscreen` on the phone. Escape
closes it, focus returns to the trigger, and the caption — question, reading, caveat, source,
provenance mark — goes with it: a figure without its account of itself is the decoration
`Figure.svelte` exists to prevent.

**Acceptance and tests.**

- ECharts instances and the map both `resize()` on entering and on leaving; a chart that keeps
  its old canvas size is the defect this control most easily ships with.
- Keyboard: the trigger is reachable, Escape exits, focus is restored, and the overlay traps
  focus while open.
- `prefers-reduced-motion` is honoured on the transition.
- An end-to-end spec opens the matrix full screen and reads a cell, so the original request is
  covered by a test and not only by the chart libraries.

### R6. The referent list is published beside the prompt

**Status: complete on 4 September 2026.** The usage payload now carries the definitions and
version bounds from the controlled list, and the model block records which version the run
saw (with the two pre-field hosted runs correctly read as version 1). The page reconstructs
only the identifiers valid at that version, publishes their definitions and run counts beside
the prompt, and marks an identifier that was retired later with its successor. The browser
spec reads the identifier, definition and count from the disclosure.

**Decision, 3 September 2026.** `/usage` publishes the prompt in full and does not publish the
controlled list the prompt renders into itself — the list that decides what every column of
the main table can possibly say. During the session this was the first thing looked for and
not found. The payload carries `id`, `label`, `kind`, `iso3` and `years`; the `description`,
which is the definition a coder and the model both read, is dropped at the export seam.

Publish it where the prompt is. Both are the instrument, and the prompt without the list is
half of it.

**Change.** `scripts/lib/usage.py` adds `description`, `since`, `retired_in` and
`superseded_by` to the referent block, and the same for the modality and accused lists when R1
and R2 land. `/usage` renders it as a disclosure beside the prompt, one row per identifier
with its occurrence count in the published run, on the pattern of the frames codebook already
on `/language`. Retired identifiers are shown as retired and named with their successor, so a
reader of an older run can see what a column used to be called.

**Acceptance and tests.**

- The list shown is the list the run recorded: it is keyed to the run's referent version, and a
  run recording an earlier version renders that version's rows, not today's file.
- Payload contract fixtures updated on both sides for the new required fields.
- The descriptions are already written for a reader; no second, friendlier copy is authored.

### R7. The lexicon stops aggregating

**Decision, 3 September 2026.** The register and set roll-ups go. A count of *the legal
register* is a count of a category the analyst invented, published as though it were a property
of the corpus, and the reader cannot tell which of six words moved when the line moves. The
site keeps individual terms — a single word or a fixed phrase — and nothing sums over them.

**The positive argument is about who composes the group.** The picker already lets a reader
select several terms at once, so the aggregate was never a capability the site would lose; it
was a *default grouping*, chosen by the analyst and presented as a thing. The session put it
plainly: we do better by letting people compose the group themselves than by offering one,
because a reader who ticks four terms knows what is in their line and a reader who clicks
*legal* believes they understand something they have not been shown. Removing the aggregates
does not remove a measure. It moves the choice of what to add together from the author to the
reader, which is the only place it can be made honestly.

**`r2p_quartet` is the clearest case and goes with them.** The responsibility to protect was
codified in the early 2000s: it does not exist in 1992, and a line drawn across the whole
corpus under that name projects a category backwards over half the record it describes. It is
the Rome Statute anachronism again, in a set rather than in a gloss. The session's second
objection is worse for it — no two jurists agree whether R2P states an obligation or a
possibility — so the label names a thing whose content is contested by the people who made it.
As a selectable curve it invites a reader to believe the Council had a doctrine before it had
one.

**The legal ladder, corrected.** An earlier draft of this item said no convention defines
ethnic cleansing. That is true and incomplete, and the session's own formulation is the one to
use, because it is what the intensity ordinal below is built on. Three tiers, not two:
*genocide* (1948 Convention), *war crimes* (1949 Geneva Conventions) and *crimes against
humanity* are **crimes** in international law; *ethnic cleansing* appears in legal texts but as
an **aggravating qualification of a crime and not a crime itself**; *atrocity* has **no legal
existence at all**. Filing the first four together under `legal` flattened three different
kinds of thing into one.

The review's §3.4 finding is settled by the same change rather than won: it found the register
roll-ups double-counting nested terms, which lexicon v4 repaired; removing them retires the
class of fault.

One objection from the session was already absorbed before it was raised. *Ethnic hatred*
"appears nowhere" — correct, and lexicon v4 renamed `ethnic_hatred` to `ethnic_violence` for
exactly that reason, its own note recording that the pattern always matched *ethnic conflict*
and *ethnic violence* far more often. No change is owed.

Two things survive and one must be corrected. `register` survives as a shelf label for grouping
and colouring the term picker, and `tier` as documentation; neither is a measure. The `tier`
gloss in `config/lexicon.yml` — "the Rome Statute / R2P cluster" — is documentation about a
corpus that begins in 1992, six years before the Rome Statute, and should be re-glossed on the
1948 and 1949 instruments.

**This removes a home-page figure**, and that is the item's real cost. *Register share,
1992–2023* is the second of the two figures on the home page and is drawn from
`has_register_*`. It is re-cut as individual terms or it goes; the choice is the author's and is
not taken here. `README.md`, `PLAN.md` and `/methods#word-list` all describe six registers as a
published measure and follow it.

**The intensity ordinal is adopted, and it is built on legal status.** Not on a feeling of
force, which no two readers would order the same way, but on the three tiers above: a term
that names a crime defined by treaty outranks one that aggravates a crime, which outranks one
with no standing in law at all. That ordering is arguable in public and can be cited to the
instruments, which "how strong does this word feel" cannot. The view it buys asks, for one
situation, whether a delegation climbs the ladder before it uses the word — the euphemism
question of R10, seen from the vocabulary rather than from the meeting. The ordinal is
hand-assigned and reviewed by both coders, which makes any figure drawn from it **mixed**
under R3, not computed.

**Change.** `lib/lexicon.apply` stops writing `n_register_*`, `has_register_*`, `has_set_*`,
`n_lexicon_total` and `n_lexicon_terms`; the `sets:` block leaves `config/lexicon.yml`
altogether, `r2p_quartet` included; `04_series.py` stops publishing the register series; the
chronology picker drops the `register:*` and `set:*` measures and keeps the register as its
grouping, with multi-term selection made obvious enough that a reader reaches for it where the
aggregate used to be; the home page's second figure is re-cut or removed; `intensity` is added
to `config/lexicon.yml` at a new version with a lock refresh.

**Acceptance and tests.**

- No payload carries a summed measure over more than one term; asserted at the export seam,
  not by inspection.
- Every prose claim about "six registers" is found and changed in the same commit — README,
  PLAN, Methods, chronology — or the site describes a measure it no longer publishes.
- The intensity scale is a total order over the terms, and any view drawn from it carries the
  mixed provenance mark.

### R8. The atrocity vocabulary without the word

**Decision, 3 September 2026.** The model layer reads only speeches containing `genocid*`, and
the session's sharpest example is the case that design cannot see. In the published run
`xinjiang_uyghurs` holds two occurrences, both China's, both refusals: the only delegation that
puts the word on Xinjiang is the one being accused. Everyone else frames the case in the
vocabulary of genocide and stops short of the word — which is the object of study, and it is
invisible to an instrument that enumerates the word.

The corpus for it already exists and is already counted. `ethnic_cleansing`,
`crimes_against_humanity` and `war_crimes` are unanchored, so 03 counts them corpus-wide, 08
builds their concordance lines and 09 exports their speeches. Measured on
`speeches_flagged.parquet` *(1946–2024)*: **4,716 speeches carry one of the three and never say
`genocid*`**, holding 8,056 occurrences of the four atrocity terms — war crimes 4,332, crimes
against humanity 2,376, ethnic cleansing 932, mass atrocity 416 — against the genocide layer's
4,133 speeches and 7,747 occurrences. *(On the 1992–2023 corpus the same measurement gave 4,286
and 7,494.)* The session settled the vocabulary at these three: "if we do the three, we are
strong", with the caveat recorded that *war crimes* is specific but *war* and *crimes* are not,
which is why the phrase and not its parts is the pattern.

**Two stages, and only the first is cheap.** The session did not ask for the model run first.
It asked for an **overview**: a second corpus set beside the first, so the chronology can show
what the Council says when it is not saying genocide, and so the project can state
quantitatively that the Council rarely reaches for the word *relative to* the other ugly words.
That is arithmetic over counts the pipeline already has, it needs no model, it is **computed**
under R3, and it can be done now. Fine-grained treatment stays on `genocide` — the session said
so explicitly, and it is a legitimate place to stop. The site-wide control this implies is
R9's.

The second stage is the model layer, and its problem is design rather than price. About a fifth
more occurrences than the run already made puts it near $5 and forty minutes on the Batch API.
But the question is not "was this genocide" — the prompt's task boundary refuses that and must
keep refusing it — it is whether *this passage frames a determinate case in the vocabulary of
genocide without using the word*, a discourse question of the same kind as `concrete_case`. The
expected answer is **no** most of the time: *war crimes* is the Council's routine vocabulary,
and a field that cannot comfortably answer no will manufacture a finding. That is the risk this
item carries, and it is why nothing from it merges into the genocide matrix.

**Change.** *Stage one:* the three terms' speech counts and rates published beside the
genocide series on the chronology, and the genocide-free set named as a corpus in its own right
so R9 can switch to it. *Stage two:* a new enumeration over the three terms in genocide-free
speeches; a `genocide_framing` field (yes / no / unclear) with the same cascade discipline as
`concrete_case`, plus referent and modality; its own run, its own gold sample and its own
agreement figures before anything is published from it; a separate view, never a column added
to the existing matrix.

**Acceptance and tests.**

- Stage one publishes no model output and carries the computed mark; stage two is published
  only behind its own human-coded sample, on the rule `PLAN.md` §5 already sets for the model
  layer. Two full runs and a cheap price are not a warrant.
- The negative rate is a headline of the artefact and not a footnote: an instrument that
  answers yes to most of 8,056 routine occurrences has failed, and the number that says so is
  published first.
- The genocide matrix, the diffusion curves and the position profiles are unchanged by either
  stage.

### R9. The meeting becomes a unit, and the corpus gets a scope

**Decision, 3 September 2026.** Everything on this site is a speech or a delegation. The
meeting exists as a filename and as a destination for the reader, and never as a unit of
analysis — which means the site cannot ask the question the second part of the session kept
returning to: *in the meetings where somebody says genocide, what do the others say?* A
delegation's silence is only legible against the debate it sat in.

The session also asked for a control, and the two asks are one design. R8's genocide-free
atrocity speeches are only interesting **next to** the genocide-bearing ones they shared a
meeting with, so the site needs to be able to say which corpus a view is drawn from. Three
scopes, one control, carried in the URL as U2 requires *(counts on 1946–2024)*:

| scope | what it holds | speeches |
|---|---|---:|
| **the word** | speeches containing `genocid*` — today's implicit default | 4,133 |
| **the vocabulary** | those plus speeches with ethnic cleansing, crimes against humanity or war crimes | 8,849 |
| **the debate** | every speech in a meeting where at least one delegation said `genocid*` | 50,735, in 1,556 meetings |

**The trap this must not fall into.** A scope selects a *reading set*, never a denominator.
The home page's rate is a share of all 167,642 speeches and it must stay one under every
scope, or the headline becomes a number whose base moves when a control is touched — the
opposite of what R14 is trying to repair. The scope says which speeches are listed, tabulated
and drawn; it never says which speeches the corpus has.

This also promotes `/reader/[meeting]` from an escape hatch to a destination: once the meeting
is a unit, the natural move from any figure is into the debate, with every speech in it and
the vocabulary of each marked.

**Change.** A `meetings` artefact carrying, per meeting, its date, agenda, speeches, the
delegations present and the terms each used; a scope control in the layout, URL-carried,
defaulting to *the word* so no existing link changes meaning; the concordance, chronology and
actors views reading it; the reader view showing the whole debate with each speech's
vocabulary marked.

**Acceptance and tests.**

- Every published rate keeps the full corpus as its denominator under all three scopes, and a
  test asserts it rather than a reviewer noticing.
- A URL without a scope parameter renders exactly what it renders today.
- The meeting artefact reconciles to the speech table on speech counts, as every other
  artefact in the pipeline reconciles to its input.
- The scope control states, beside itself, how many speeches each scope holds. A control that
  silently changes a population is a control that produces mistakes.

### R10. Counter-concepts: what is said instead of genocide

**Decision, 3 September 2026.** The session's best research question, and the one this
instrument is furthest from answering. In Koselleck's terms a concept travels with its
opposite, and the history of one cannot be written without the other: the interesting question
is not only when the Council says *genocide* but **what it says in order not to**. Two
candidate counter-vocabularies were named, and they belong to different speakers. The
**humanitarian** register euphemises for the bystander — Rwanda in 1994, Gaza now — because
naming the crime would trigger an obligation to act. **Terrorism** is the counter-accusation of
the accused: the others call it genocide, you call them terrorists. The strong form of the
hypothesis is that the pair *inverts* — the same two words, with the roles exchanged depending
on who is speaking — which would show a shared grammar underneath what looks like each state
saying whatever suits it.

**A measurement that says the naive version of this must not be built.** Taking the meetings
where somebody says genocide, and asking how often the *silent* speeches in those same meetings
use each vocabulary:

| | terroris\* | humanitarian |
|---|---:|---:|
| silent speeches, in genocide meetings *(1946–2024)* | 13.1% | 24.9% |
| speeches in meetings where nobody says it *(1946–2024)* | 12.0% | 18.3% |
| silent speeches, in genocide meetings *(1992–2023)* | 15.3% | 29.7% |
| speeches in meetings where nobody says it *(1992–2023)* | 19.5% | 31.0% |

**The sign of the terrorism contrast flips between the two corpora** — below the baseline on
1992–2023, above it on 1946–2024 — and the humanitarian contrast goes from flat to clearly
positive. A comparison whose direction depends on which decades are included is not measuring
what it claims to measure. The confound is the agenda: a counter-terrorism debate is not a
genocide debate, and the raw contrast is mostly a statement about what the Council had on its
order paper. The item therefore does **not** ship an unadjusted co-occurrence figure. It ships
the paired design the pipeline already uses for keyness — each speech matched to a comparable
one, and the strongest available match is *within the same meeting*, which holds the agenda
exactly rather than approximately, with the referent held too once R1 lands.

**A second measurement, about the instrument rather than the question.** *terroris\* * appears
in 944 of the 4,133 genocide-bearing speeches, 22.8% *(1946–2024)*; on the corpus the session
was looking at, 669 of 3,273. The concordance's ±150-character window showed 66. The window is
right for reading a use and wrong for finding a relation, by a factor of ten, and the session
identified this unaided. Co-occurrence at speech and meeting level is R9's artefact, not the
concordance's.

**Neither vocabulary is in the lexicon.** There is no `terrorism` term and no humanitarian
family in `config/lexicon.yml` today; *terrorism* is reachable only as a free-text filter over
concordance lines. They are added as individual terms under R7's rule — never as a group.

**Change.** `terrorism` and a small humanitarian set of individual terms added to the lexicon
at a new version with a lock refresh; a meeting-paired comparison in `05_lexical.py` or a
sibling, reported with the dispersion and the interval every other lexical table carries; a
figure that answers "when this delegation was silent on genocide in this debate, what did it
say instead", drawn only in the paired form.

**Acceptance and tests.**

- No unadjusted co-occurrence contrast is published. The paired estimate carries its matching
  rule, its interval and how much the pairing itself moves the answer, exactly as the existing
  keyness tables do.
- The figure states that a vocabulary is not an intention: a delegation using humanitarian
  language is not thereby shown to be avoiding anything, and the caption says so.
- Both directions of the hypothesised inversion are drawn, or neither is. Publishing only the
  half that fits is the failure mode this question invites.

### R11. The crime of aggression

**Decision, 3 September 2026.** International law divides in two, and this lexicon only knows
one half. There is the law *against* war — you may not attack your neighbour — and the law
*within* it: you may not kill civilians, prisoners or the wounded. The word list holds war
crimes, crimes against humanity, genocide and the atrocity vocabulary, all of them the second
half. There is no `aggression` pattern in `config/lexicon.yml` at all.

The session's historical note is the argument for adding it. At Nuremberg the tribunal's
obsession was not the killing of the Jews but whether the defendants had attacked their
neighbours; the category that mattered most to the founding moment of this whole vocabulary is
the one missing from the list. For a corpus that now begins in 1946 — the Council's first
meetings, and the years in which that hierarchy was still being argued — the omission is
larger than it was for a corpus beginning in 1992.

**Change.** An `aggression` term in `config/lexicon.yml` at a new version with a lock refresh,
its pattern written for the phrase and not for *aggression* alone, which is ordinary Council
prose; the jus ad bellum / jus in bello distinction recorded in the file's own documentation,
where the tier gloss R7 corrects already lives; the term offered in the picker like any other.

**Acceptance and tests.**

- The pattern's examples are attested in the corpus and quoted with their line ids, on the rule
  every other term follows.
- Adding a term bumps the lexicon version and every downstream count is regenerated, not
  patched.

### R12. Figures whose purpose is not established

**Recorded on 3 September 2026; no decision taken.** The session read the site figure by figure
and three of them did not survive the reading. This item records that, and deliberately stops
there: which figures go is the author's call and is not made here.

- **"The vocabulary's calendar" and "The same twelve months, pooled"** (chronology). The reader
  could not say what question they answer. Worse, the exchange over them shows them inviting a
  wrong one: looking for April 1994 and Rwanda, he found peaks in February, April and June, and
  the explanation is that they are not Rwanda but Bosnia. A within-year seasonal figure over a
  vocabulary that spans every situation on the agenda mixes cases the reader assumes are one.
  If they stay, they need a referent filter, which is R1's; if that filter is what makes them
  legible, they were the wrong figures before it.
- **"Which terms travel together"** (language) and **"The words that sit near a term"**. Read
  as purely statistical proximity, useful to the authors as a development step and not to a
  reader: "once you want a finished thing, this has to go".

The principle behind all three, and the reason this item is not just a list: **the more
information you put in, the harder it is to use the right information.** And behind that, a
strategic reading the author should weigh before deciding anything here — that the project's
centre of gravity should move toward model-assisted classification and corpus exploration, and
away from lexicometry, not because the lexicometry is wrong but because it has been done
elsewhere with simpler tools and is not what is new here. That reframing, if adopted, changes
the information architecture of the whole site and is much larger than three figures. It is
recorded, not adopted.

### R13. The epistemological page

**Decision, 3 September 2026.** Methods answers *how every number was made*. Nothing on the
site answers *why this is a defensible way to study the Council at all* — what the object is,
why a machine-read corpus can bear on it, and what the approach cannot do. The session offered
to write it, and it should be written by the second reader rather than by the pipeline's
author: it is a historian's argument, not an engineering note.

Its content, as the session set it out: why we do this, why it makes sense, and what the
problems are, in the terms of historical and sociological research. The audience argument is
the whole justification — for trained historians it is obvious that both halves are needed;
for a visitor it is not, and a site that publishes only the machinery implies the machinery is
the argument. And the lesson of the project is precisely that all of this has to be watched:
the LLM, the algorithms, the word list, the referent vocabulary. A page that says so is not a
disclaimer, it is the finding.

Methods then becomes what it should be — *if you want to know what happens under the bonnet,
here it is* — rather than the site's only account of itself. This page is also where the
epistemological statements that have nowhere else to go are made: that the tool is an
instrument for targeted reading and not a statistics engine, and R15's point about who is
taken to be speaking.

**Change.** A new view, authored by Joël Glasman and credited to him, linked from the home
page and from every provenance legend; Methods keeps its ledger and loses the burden of being
the epistemology; `README.md`'s acknowledgement becomes an authorship note for that page.

**Acceptance and tests.**

- The page is signed. An unsigned epistemological argument on a site whose whole discipline is
  provenance would be the one unprovenanced thing on it.
- Nothing on it restates the pipeline. If a sentence could go in Methods, it goes in Methods.

### R14. Navigation and legibility of long pages

**Decision, 3 September 2026.** The views descend a long way. `/usage` is 2,207 lines of
component for four figures, `/language` 1,706 for six, `/chronology` 1,576 for five,
`/concordance` 1,147 for one, and a reader who wants the third figure scrolls past two figures,
their apparatus and their evidence lists to reach it. `Contents.svelte` exists and does the
right thing, but it is a flat inline list of figure titles, rendered once at the top of four of
the seven views, and it scrolls away with everything else — so it helps the reader who has not
started and nobody else.

The fix is one of two shapes and the choice is open: **sub-pages in the navigation**, splitting
the long views into named destinations, or **a jump list that persists** — sticky, showing
where the reader is, covering every view including the three that have none. Sub-pages give
shorter pages and better links at the cost of losing the comparison a single scroll allows;
a persistent contents keeps the page whole and does less. Either way the figure anchors already
exist from U10 and `figures.ts` already derives them, so this is presentation and not new
identity.

**One piece of evidence that the problem is not only length.** The reader took the home page's
headline rate to be a share of the genocide-bearing speeches rather than of all of them, and
the author's own response was that it is not clear enough on the page *despite the pile of
text*. That is the strongest possible finding about apparatus: an expert reader, told at
length, still read the wrong denominator. More words made it worse. The headline figure states
its denominator in the figure, in the mark, not in a paragraph near it.

**Change.** A sticky, position-aware contents on every multi-figure view, or a split into
sub-pages — one, decided before implementation, not both; the home page's rate figure states
its base on the axis or in the unit label; the same treatment for any other figure whose
denominator is not visible from the mark.

**Acceptance and tests.**

- Every view with more than one figure offers a way to reach the last one without scrolling
  through the others, and it is reachable by keyboard.
- An end-to-end spec asserts the denominator is present in the rate figure's own accessible
  description, not merely in the prose beside it.
- If sub-pages are chosen, every existing deep link keeps working.

### R15. Governments, not States

**Decision, 3 September 2026 — the statement now, the analysis later.** The site treats a
speech as a State speaking. It is a government speaking, and often the distinction is the
finding: nobody calls Rwanda's killings a genocide until the government changes, and then
everybody does, because the new government legitimates itself by accusing the old one. Read as
*Rwanda's position over time*, that is a puzzle; read as two governments, it is not. The same
mechanism will be behind other reversals in the corpus.

The corpus carries the join. `source_cow_ccode` is present on 158,563 of 167,642 rows over 200
distinct codes, and Correlates of War codes are what the leader and government datasets key on
— so a government-change overlay is a join and not a research project. Candidates to evaluate,
each of which must be checked for coverage against 1946–2024 before it is adopted, because
several stop well short of 2024: **Archigos** (heads of state, COW-keyed), **CHISOLS** (flags
the leader changes that change the *source* of a leader's support, which is exactly the Rwandan
case), **WhoGov** (cabinet composition), **REIGN**, and **V-Dem** for regime characteristics at
country-year. None is adopted here; the item is to check them.

The individual level is harder and is not proposed. `speaker` holds 10,813 distinct name
strings with no stable person identifier, so anything about the circulation of particular
diplomats — the people who specialise in this subject and reappear across situations — needs
name disambiguation first, which is its own project.

**Change.** The epistemological statement goes on R13's page now: what the unit of analysis is,
why it is a government and not a State, and that the site does not currently model the
difference. The dataset evaluation is a note in `docs/CORPUS.md`. Any overlay is deferred and
must be preregistered as a new analysis, on the rule the *Later analytical specifications*
section already sets.

**Acceptance and tests.**

- Nothing is joined before its coverage is stated against the corpus's own span; a leader table
  ending in 2015 laid over a corpus ending in 2024 would silently blank a decade.
- The epistemological statement ships whether or not any dataset is adopted. It costs nothing
  and it is true now.

### Carried, not decided

Raised in the session, not ruled on, and recorded so they are not lost:

- **A second pass over the residue with the meeting's neighbouring speeches.** The prompt
  already passes the meeting symbol and agenda item, and `referent_source` records a referent
  read off them alone; the neighbours are not passed. 343 `other` and 49 `unclear` in the
  published run, of which v2 projects to absorb about three quarters, so the remainder may not
  be worth a second instrument.
- **The evidence-location rate as a figure.** 15 unlocatable spans in 6,092, 99.75% found
  verbatim in the record. It is the strongest honesty claim the layer has, and it is a line of
  disclosure.
- **Lemkin's own vocabulary.** The session began a point about Raphael Lemkin's 1943 coinage
  and the near-synonyms he worked with, and the recording does not carry the end of it. Worth
  asking again: the terms a concept was invented *against* are R10's question moved back to the
  beginning.
- **Circulation of individuals.** R15 defers this on name disambiguation, but the underlying
  question — that some delegates specialise in this subject and reappear across situations and
  decades — is a good one and is now answerable in principle over a corpus that runs from 1946.
- **The noisy adjacent terms** of review §3.4 — `survivors`, `commemoration`, `denial`,
  `glorification`, `holocaust`. R7 removes the aggregates; it does not make these terms measure
  genocide talk.

## Phase C — the models move to the cluster

**Decision, 4 September 2026.** The two instruments of Phase L stop being hosted commercial
APIs. Both become open-weights models served on the University of Bayreuth cluster the
embedding steps already use: `Qwen/Qwen3.8-27B` as the published run and
`deepseek-ai/DeepSeek-V4-Flash-0731` as the counter-instrument, each at its own maximum
reasoning level, behind an OpenAI-compatible vLLM endpoint on a compute node. The families
stay independent, which is what L8 requires of a counter-instrument: 27B dense against 304B
mixture-of-experts, Apache-2.0 against MIT, two laboratories that did not train each other's
model.

**Which of the two is published is a scheduling decision as much as an analytical one.** The
published run is the one that will be made again — after a prompt revision, after a referent
list changes, after a corpus migration like the one that just voided both committed runs — so
it should be the instrument that fits on one card, starts in a queue rather than waiting for a
whole node, and asks nothing of the serving stack that the cluster does not already do. That
is Qwen. DeepSeek is the more demanding model in every respect (C4), and putting it in the
counter-instrument slot means that if it cannot be served, what is lost is a comparison rather
than the layer. If it cannot be served at all, `google/gemma-4-31B-it` takes its place — 31B
dense, Apache-2.0, ungated, a third family, and one card.

The order of the reasons matters, because two of the usual ones do not apply here and citing
them would be false.

**Reproducibility, which is the whole argument.** `gpt-5.6-luna` and `gemini-3.7-flash` name
routes to systems that can be revised, re-routed or retired without notice and without a
version anyone outside the provider can cite. A checkpoint is an artefact: a repository id at
a revision with a digest, which a reader with a GPU can load in five years and run again. This
repository already hashes the prompt into every row, versions the lexicon, pins the corpus by
DOI and gives every occurrence a stable identity. The model was the one input in that chain
that could not be pinned, and it was the input doing the interpreting. C5 makes the weights
carry a revision the way everything else here carries one.

**Measurability of the reasoning level.** Running at maximum reasoning is a claim about the
instrument, and it is checkable only where the request reaches one process whose log can be
read. The sibling repository measured a documented three-level ladder collapsing to on/off
through a hosted router — two levels indistinguishable in latency and in reasoning length, one
backend reporting a single reasoning token while emitting thousands of characters of it. That
is not a fault a hosted run can detect in itself, and C3 turns it into a gate.

**Not cost, and not confidentiality.** A full run over the old corpus was a few dollars and
half an hour through the Batch API; price has never constrained anything in this project and
it is not the reason. Nor is data protection: the corpus is the public verbatim record of the
Security Council, published by the United Nations and re-published on Dataverse. Both are real
arguments in other projects and neither is an argument in this one. Recording that stops
either from being cited later as though it had been the motive.

What the swap gives up is stated with it. The OpenAI and Gemini Batch APIs carried the queue,
the retries and the resumption server-side; a 24-hour Slurm allocation carries none of that,
which is why C4 makes resumability a requirement rather than a convenience. And structured
output is weaker on a server with no router in front of it: an open model behind
`response_format` still fences its JSON or prefaces it with a sentence often enough to need a
recovery path.

**Both runs have to be made again in any case.** The migration to Sakamoto–Matsuoka v5
retired every committed run — their occurrence identities do not address the new corpus, and
both pointer files are already empty. The instrument decision therefore costs no comparability
that the migration had not already spent, which is why it is taken now rather than after
another run. The next run is also the run that carries prompt v3 and annotation schema 4, so
R1, R2 and R4 arrive on the new instruments or not at all.

This phase changes the transport and the instruments. It changes nothing about what the layer
may claim: Phase L's four standing conditions and the closing rule of `PLAN.md` §5 hold
unchanged, and C6 is the one place where the new pair needs a new precaution.

### C1. One transport, two instruments

**Status, 4 September 2026: complete locally.** One vLLM Responses transport now serves both
profiles; the retired Gemini implementation is gone while its committed runs and archived
prompt remain readable. Offline tests cover both reasoning placements, strict JSON recovery,
truncation and the shared row contract.

**Change.** 14 and 16 are two scripts because the OpenAI Batch API and the Gemini Batch API
are two APIs. vLLM makes both instruments the same API, so the counter-instrument stops being
a second script: fold the two into one step against an OpenAI-compatible endpoint, selected by
`--model`, with the endpoint read from the environment and never from an argument or a
catalogue. Where a model is served today is deployment state — on a scheduler it changes with
every job — while what a run must record is the model and the route, which C5 covers.

`scripts/lib/llm.py` keeps everything it already does and is where the value of the layer
actually sits: prompt and referent rendering, the JSON schema, label checking, evidence
location against the speech body, the row shape, and `completed()`. None of that is
provider-specific and none of it should move. `scripts/lib/gemini.py`,
`16_llm_annotate_gemini.py` and `tests/test_gemini.py` retire with the hosted path; the runs
they produced stay committed as provenance, and git history holds the code that made them.

Two transport details the hosted path did not need:

- **JSON recovery.** Parse the response as JSON; failing that, unwrap a Markdown fence;
  failing that, take the outermost balanced span; failing that, record a failure. What is
  never allowed is repair — a response that does not carry a parsable document is a refusal,
  not a value to be reconstructed.
- **A reasoning parser.** vLLM's `--reasoning-parser` keeps the thinking block in
  `reasoning_content`. Without it a thinking model's chain of thought arrives inside
  `content` and every structured answer has to be dug out of an essay. It is a serving flag
  rather than a client behaviour, so C5 records it with the rest of the launch.

**Acceptance and tests.**

- The two instruments differ by `--model` and by their manifests, not by a code path; a row
  from either satisfies one validator and one contract.
- The tests never open a socket, as 14's and 16's never did.
- A fenced or prefaced response is parsed; anything else is a recorded failure with its
  reason, and no field is filled by inference from a malformed response.
- Retiring the Gemini step does not retire its runs: `2026-08-31-gemini-v1` stays readable and
  its prompt stays resolvable through `prompts/`.

### C2. The serving harness, and where it runs

**Status, 4 September 2026: installed on the cluster; GPU smoke queued.** The filtered dirty
working tree was transferred, the client overlay and isolated vLLM 0.28.0 environment were
installed without moving the locked environment, and the exact Qwen revision was downloaded
and checksum-verified. Development-partition allocations 748011 and 748012 were both killed
by Slurm at zero elapsed time before the script opened either log. The equivalent bounded
one-H100 smoke is queued as 748013; this is scheduler evidence, not yet serving evidence.

**Change.** `scripts/cluster/` gains the serving pattern already proven in
`iwac-ai-pipelines/serving/` and, through it, in festus-transcribe: one sourced `env.sh`
holding every site-specific value as `${OVERRIDE:-default}`, a login-node setup script that
builds the environment and prefetches the weights, a batch script that serves the model for
interactive use over an SSH tunnel, and an unattended job that serves, annotates and stops.
The `#SBATCH` defaults name a partition and a GPU type, which are `sinfo` facts rather than
configuration anyone inherits, and every one of them is overridable on the command line.

One thing is simpler here than in the sibling repository, and it is worth saying why rather
than copying the complexity across. There, the corpus sits behind an archive's credentials, so
a sample had to be prepared on the machine holding the keys and shipped to the cluster as a
file. Here the corpus is already on the cluster — `data/` is a symlink to `/workdir` and
`submit_corpus.sh` builds the parquet — and the annotation step needs no key at all once the
endpoint is local. So the unattended job reads `speeches_flagged.parquet`, talks to
`127.0.0.1`, and has nothing to protect: the server binds loopback, there is no port to expose
and no token to manage. A `trap` stops the server on exit, including on `scancel`, because an
orphaned vLLM would hold the GPU for the remainder of the allocation.

vLLM gets its own environment, a third beside locked and extras, on the argument
`docs/CLUSTER.md` already makes for the first split: an inference server resolves its own
torch, and installing it into either existing environment would move a pin that a published
figure depends on. The annotator itself runs **locked** plus `requirements-llm.txt`, whose
only remaining entry is an OpenAI SDK now used as a protocol client. A JSON body crosses
between the environments; an environment does not.

**Acceptance and tests.**

- No account name, host, home directory or token appears in a tracked file; `test_privacy.py`
  covers the new scripts, and `test_cluster.py` covers them the way it covers the existing
  submit scripts.
- The serving environment cannot install into the locked one, and the run's manifest names
  which environment produced it.
- The unattended job leaves no server running after it exits, by any exit path.
- Nothing in the harness requires the author to be at the keyboard when the scheduler starts
  the job.

### C3. Maximum reasoning, declared and demonstrated

**Status, 4 September 2026: gate implemented; demonstration job 748013 queued.** Each profile declares
its full ladder and parameter placement. The unattended job now runs a paired corpus-speech
probe, records latency and reasoning-token medians under `data/interim`, reuses an identical
passed probe on resume, and refuses a flat ladder. No probe artefact exists until the GPU smoke.

**Change.** Both instruments run at their own top level, which is not the same string in each:

| Model | Role | Where the level is sent | Levels | Maximum |
| --- | --- | --- | --- | --- |
| `Qwen/Qwen3.8-27B` | published | `reasoning_effort` inside `chat_template_kwargs` | `low`, `medium`, `xhigh` | `xhigh` |
| `deepseek-ai/DeepSeek-V4-Flash-0731` | counter-instrument | `reasoning_effort` on the request | `low`, `high`, `max` | `max` |
| `google/gemma-4-31B-it` | counter-instrument, if DeepSeek cannot be served | thinking level in `chat_template_kwargs` | documented ladder, measured as on/off | `high` |

Qwen reads the level out of its chat template rather than off the request body, which is why
it travels in `chat_template_kwargs` — vLLM's channel for arguments into a template — and why
sending it the way DeepSeek is sent silently changes nothing. Neither level is defaulted in
code: the requested value is an argument and the effective value is recorded per run.

The third row is the reason the next paragraph exists. Gemma 4 is precisely the model whose
documented ladder was measured, in the sibling repository, as behaving like a switch: the
levels between the ends were indistinguishable in latency and in reasoning length. It is a
capable, ungated, Apache-2.0 model from a third family and a perfectly good counter-instrument
— but it may have two usable settings rather than four, and a run of it must say which of
those it got rather than which one it asked for.

Declaring a level is not the same as getting one. Before either corpus run, a probe over a
handful of speeches at each level records latency and reasoning-token count per level, and a
ladder that turns out to be flat blocks the run rather than annotating 4,133 speeches at a
depth nobody can demonstrate. The probe reads speeches already on disk, writes its table
beside the run, and touches nothing under `model_annotations/` or `annotations/`.

Maximum reasoning also has a consequence for the instrument that is easy to miss. It
lengthens responses — DeepSeek recommends a 384k output ceiling at `high` and `max` — and a
response cut off at `max_tokens` is a refusal that looks like an answer. It must be counted as
a failure and never as an abstention: abstention is a value the model chose, truncation is a
value it never reached, and the distinction is the one the codebook's `unclear` depends on.

**Acceptance and tests.**

- The manifest records the parameter name, the value, and where it was sent, for each run.
- A probe artefact exists per model per run, and a flat ladder refuses the run in words.
- Truncation appears in `failures.jsonl` with its own reason and in the manifest as its own
  count, distinguishable from a parse failure and from an abstention.
- Sampling parameters are recorded as sent, not as recommended by a model card.

### C4. Size the job before submitting it

**Status, 4 September 2026: local durability complete; hardware gates pending.** The 65,536
context and requested hardware are explicit. Raw receipts and validated rows are flushed one
response at a time, and the manifest checkpoints atomically after each response while folding
them into one scheduler pass. Restart skips only complete rows from the same prompt and model;
the dev smoke and the DeepSeek/Gemma serving decision remain open.

**Change.** Compute the run's shape from the corpus before requesting an allocation. Measured
over `data/derived/speeches_flagged.parquet` on 4 September 2026:

- 4,133 speeches carry `genocid*`, holding 7,747 occurrences. The unit of a request is the
  speech, as it is now.
- Their text is 32.7M characters — roughly 8.2M tokens at four characters to the token, before
  the system prompt and the referent list are added to each request.
- The longest is 151,713 characters, about 38k tokens. Six speeches exceed 24k and two exceed
  32k, so the 32,768-token context the sibling repository serves with would truncate the two
  longest speeches in the corpus, which are exactly the plenary records most worth reading.
  Serve 65,536, and check the count above it rather than assuming it.

Hardware, from the partition table in `docs/CLUSTER.md`:

- **Published run.** `Qwen/Qwen3.8-27B` is 27B dense; bf16 weights are about 56 GB and fit one
  H100 with room for the cache at 64k. The official FP8 repository is about half that and would
  fit one L40S on `normal`, which usually starts sooner — but quantisation changes outputs, so
  it is a different instrument and C5 records which one was loaded. One card is the reason this
  is the published run: it can be re-run whenever the prompt moves.
- **Counter-instrument.** `DeepSeek-V4-Flash-0731` is 304B with six of 256 experts active per
  token, fp8 block-quantised, roughly 170 GB across 48 shards. It needs the whole four-H100
  node, and the margin under 320 GB is what the KV cache has to come out of.
- **Its substitute.** `google/gemma-4-31B-it` is 31B dense and Apache-2.0, about 63 GB in bf16
  — one H100 — with an ungated repository and a quantised official variant. It is a third
  family, so L8's independence requirement is met either way.

Walltime: the `GPU` partition's ceiling is 24 hours. The only measured throughput available is
the sibling repository's 127 requests per hour at a middle effort level on two L40s; at
maximum effort, over texts several times longer, 4,133 requests will not fit in one allocation
on that evidence. **Resumability across walltime is therefore a requirement, not a nicety**:
rows appended one at a time, completed occurrences skipped on restart, and rows written under
a different prompt digest ignored rather than reused, so that resuming across a prompt edit
cannot mix two instruments in one file. `lib.llm.completed` already does the skipping; what is
new is that the job is expected to be killed rather than to fail.

Smoke first, over a few dozen speeches: it proves the serving path, the reasoning parser, the
schema and the resume, and — following 06's rule — it writes to its own directory so that a
smoke run can never be mistaken for a corpus run. The 4 September attempt established that
`dev` advertises two idle L40s but can still kill an allocation before the batch script
starts; after two zero-runtime failures, the smoke moved unchanged to one H100 on `GPU`.

**Gate: DeepSeek may not be servable here, and that has to be tested before it is promised.**
It is the counter-instrument rather than the published run precisely because of what follows,
so a failure here costs the comparison and not the layer.
Its own recipes target four GB300s with a `deep_gemm` MoE backend and an fp4 indexer cache.
Hopper has neither; `deep_gemm` wants an `nvcc` the cluster venv does not have, which is why
the sibling repository disables it outright; and the release ships **no Jinja chat template**,
offering an `encoding/` folder of Python scripts instead — which is not what a vLLM
OpenAI-compatible server renders a conversation with. The release also expects
`--trust-remote-code`, which `config/embedding_models.yml` refuses on principle for step 06.
That rule was written for an unattended job pulling arbitrary repositories; this is a manual
run of a named revision under the author's own account, so the two are not the same case — but
the exception is written down with the vLLM version that needed it, and a vLLM with native
`deepseek_v4` support is preferred to granting it.

None of this is known to be fatal and none of it is verified. If the model cannot be served
honestly on this hardware, the substitute is decided in advance rather than improvised:
**`google/gemma-4-31B-it`**, a third family on one card, whose ladder C3 already expects to be
shorter than its documentation. What is not allowed is to quantise the analytical instrument
until it fits, or to slip back to a hosted API without saying so. The decision is recorded
either way, with what was tried and where it failed, because "we used Gemma" and "we wanted
DeepSeek and this cluster could not serve it" are different sentences in a methods section.

**Acceptance and tests.**

- The context length is set from the corpus, and the number of speeches above it is zero,
  checked rather than assumed.
- A job killed at its walltime and resubmitted produces one run, not two, with no duplicated
  occurrence and no row from a foreign prompt digest.
- The smoke run cannot overwrite a corpus run.
- A model that cannot be served is a recorded decision with its evidence, never a silent
  substitution.

### C5. The weights get a digest

**Status, 4 September 2026: complete locally; first real manifest pending.** New manifests
require and publish the immutable repository revision, vLLM version, hardware, serving flags,
reasoning placement, sampling and truncation count. The web boundary rejects a partial runtime
block but accepts both untouched hosted manifests; `/usage` displays revision and hardware.

**Change.** A run's manifest gains what a self-hosted route makes knowable and a hosted one
never did: `route`, the served model id, **the Hugging Face repository revision** — the commit
of the weights, which is the thing that actually reproduces — the quantisation as loaded, the
vLLM version, the GPU model and count, the serving flags that can change output (context
length, reasoning parser, speculative decoding, MoE backend), the reasoning parameter and its
value, the sampling parameters, the output cap and the truncation count.

A model name is a label; a revision is an identity. `deepseek-v4-flash` names a family,
`DeepSeek-V4-Flash-0731` names a release, and a repository can be updated under either without
changing the string a manifest holds. This is the first time in this project that a model
input can be pinned as hard as the corpus is pinned by its DOI, and it should be pinned that
hard — otherwise the move to open weights buys the *possibility* of reproduction without
recording the fact needed to perform it.

Speculative decoding gets its own field rather than a footnote. DSpark ships inside the
DeepSeek checkpoint and switches on with a flag, and whether it leaves outputs identical to the
target model on this hardware is not something to assume in a manifest — record that it was
on, at what draft depth, and leave the claim about equivalence to whoever measures it.

**Acceptance and tests.**

- A manifest naming a model but no revision fails review, the way a run naming no prompt hash
  would.
- The serving command can be rebuilt from the manifest alone.
- The `/usage` apparatus names the served model and its revision, not a marketing name, and
  the disclosure sentence says the run was made on hardware the project controls.
- The two committed hosted runs keep their manifests unchanged; the new fields are absent
  there rather than back-filled with guesses.

### C6. Two laboratories under one regulator is a shared blind spot

**Status, 4 September 2026: first slice complete.** New failure rows carry a machine-readable
`transport_refusal`, `truncation` or `validation_failure` kind, distinct from abstention values
inside a valid schema. Their per-referent denominators, withholding and paired UI have not yet
been implemented; they depend on the actual pair that clears the serving smoke.

**Decision.** L8's sentence — agreement between two models measures stability across
instruments, never accuracy — was written because two models can share training habits and be
confidently wrong together. The new pair sharpens that from a caution into a specific,
checkable exposure, and the phase that creates it is the phase that has to say so.

Qwen and DeepSeek are released by laboratories operating under one national regulatory
framework for generative models, and the corpus is a record of States accusing one another of
genocide. Where that framework bears on the subject matter — accusations involving China, and
the situations it is sensitive about — a shared reticence would not appear as disagreement. It
would appear as agreement, or as abstention on both sides, and both of those currently read as
stability. The retired pair had its own shared exposure, two American laboratories with their
own content policies and their own silences; the point is not that one pair is compromised and
the other clean, but that the exposure is different, is knowable, and has never been
displayed.

Substituting Gemma 4 for DeepSeek (C4) changes this exposure without removing the need to
measure it. That pair spans two regulatory regimes rather than one, which is a real gain, and
it trades it for a model with well-documented refusal behaviour of its own. Either way the
check below is the same, and which pair actually shipped is a sentence the page has to carry —
the shared blind spot named is a property of the pair, not a fixed paragraph.

**Change.** 15 publishes, per referent and per instrument, the abstention rate, the refusal
rate and the validation-failure rate, each with the denominator that qualifies it and each
subject to the same withholding floor as every other share on the site — a case below the
floor says so rather than vanishing. The `/usage` apparatus shows them beside the agreement
table, under the stability-not-validation sentence they qualify. The gold sample keeps its
role as the only calibration, and L2's stratification is checked to reach the contested cases
the corpus actually contains rather than assumed to have covered them.

**Acceptance and tests.**

- Per-referent abstention, refusal and failure rates for each instrument appear in the payload
  and on the page, with denominators.
- A refusal to answer is distinguishable in the artefacts from an abstention chosen inside the
  schema and from a response that failed validation.
- The limit is stated in words where the stability-not-validation sentence already is, and
  names the exposure the pair that actually shipped has, rather than gesturing at "model bias"
  or describing a pair that was not used.
- No agreement figure is published without the abstention figures beside it.

### C7. Documentation, the ledger and the acknowledgement

**Status, 4 September 2026: documentation migrated; acknowledgement wording pending.** The
current run books, environment example, dependency files and methods mapping describe the
keyless vLLM route. The exact DFG acknowledgement still needs confirmation before it can be
placed in `CITATION.cff`, the README and every model-derived page.

**Change.** The documents that currently describe a paid hosted run, in the order a reader
meets them:

- `docs/CLUSTER.md`: a serving section, the third environment, and step 14 in the "What runs
  where" table, which today knows only 06, 07 and 10 as cluster work.
- `scripts/README.md`: the run book for 14 replaced end to end — no key, no cost, a smoke run,
  a resumable job, and the pointer files as reviewed diffs.
- `model_annotations/README.md`: the manifest fields of C5, and the sentence that a run is now
  reproducible from its own record rather than only auditable against it.
- `.env.example`: `OPENAI_API_KEY` and the two Gemini variables go; the serving values arrive;
  the file keeps saying that no Python step reads it.
- `requirements-llm.txt`: `google-genai` goes, `openai` stays with its comment rewritten — it
  is a protocol client for an endpoint we run, not a vendor SDK, and the header sentence about
  spending money is no longer true.
- `docs/PLAN.md` §5: requirement (4) is where the revision belongs, and the dated mapping
  gains a line for the transport change.
- `docs/VALIDATION.md`: register entries for the reasoning probe, the truncation count and the
  per-referent abstention check.
- `README.md`: the status row names both instruments and says the layer runs on university
  hardware.

**The acknowledgement.** `docs/CLUSTER.md` records that work on the cluster carries the DFG
hardware acknowledgement for project 523317330. Until now that touched only the embeddings,
on which no published figure depends. Once the model layer runs there, every model-derived
figure on the site does. If any such figure is published, the acknowledgement goes into
`CITATION.cff`, the README and the Methods page — with the current wording confirmed with the
HPC team rather than copied from a sibling repository.

**Acceptance.**

- A reader can run the layer from `scripts/README.md` alone, on the cluster, without a key.
- No document still says that 14 needs an API key or costs money.
- The acknowledgement decision is recorded either way, so that a later reader can tell it was
  considered rather than forgotten.

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
| 2026-09-01 | Lexicon v3 (review §3.4, item 1) | complete   | pending | `python -m pytest` (all passed on the merged tree; `tests/test_lexicon.py` new, `tests/test_config.py` +4, `tests/test_usage.py` +5); `ruff check .`; the v2 literal `war crime` shown to count 0 where the regex counts 1 on `war\ncrimes` | Two counting corrections from `docs/REVIEW_2026-09-01.md`: prefilters made whitespace-free and provably contained in every match, and register/total roll-ups summed over `lexicon.summable` so a nested term is not counted on top of its parent. No pattern changed. `pattern_since` per term, pinned by `config/lexicon.lock.json` and `tools/lock_lexicon.py`, and `Lexicon.compatible` let 15 and the annotation merge accept v2 artefacts under v3; `summable` walks the whole nesting chain and the loader refuses self-nesting and cycles; `09_export_speeches.py` now reconciles per-term counts rather than the de-duplicated total. Corpus-level effect to be recorded in `VALIDATION.md` on the next run of 03; the network policy of the environment the fix was written in did not reach Dataverse. |
| 2026-09-02 | S1, first slice (review §8, item 2) | complete   | pending | `python -m pytest` (858 passed; `tests/test_series.py` +17 for `wilson_interval`, `meeting_blocks` and the block null); `ruff check .`; a synthetic 32-year corpus with two dense debates run through `build_series`, `build_change_points`, `build_monthly`, `build_breakdowns` and `build_note` — the token-rate split read p = 0.015 under the independent null and 0.69 under the block null; `npm run lint`; `npm run check` (0 errors); `npm test` (452 passed, `chronology.test.ts` +4); `npm run test:e2e` (26 Chromium journeys) and `npm run test:e2e:sw` (1 built-site journey, which is also the fixture build) on the fixtures, run through a throwaway config pointing at the environment's pre-installed Chromium because the pinned headless shell was absent; the contract diff is 43 insertions and no deletion. `npm run build` prerenders against `web/static/data/`, which this environment cannot populate, so it was not run. | The rate change-point null now permutes meetings across years (`series.meeting_blocks`, `rate_change_point(blocks=…)`); the independent-speech p-value is published beside the block one as `p_value_independent`, the artefact names its `null` and its `blocks`, and `accepted` follows the block p. Every `speech_rate` — annual, quarterly, monthly, pooled calendar, breakdown row, speaker row — carries Wilson 95% bounds, blanked by the same withholding rule as the rate; the site draws them as bands (chronology, split figure) and a whisker column (actors), and prints them in hovers and CSVs. The findings note reads the corrected `inference` block and types no year into its prose. Contract, TS types and fixtures moved together, with the new fields required rather than optional because the pipeline always writes them. **Owed:** the corpus re-run, blocked on Dataverse from this environment; `README.md` says which of its numbers are still the independent-null ones. |
| 2026-09-02 | S5, first slice (review §8, item 7) | complete   | pending | `python -m pytest` (879 passed; `tests/test_lexical.py` +21 for the floor, the ranking, dispersion, logDice, the tokeniser and definitional pairs; `tests/test_keyness.py` +2 holding the matrix dispersion equal to the pure-Python one); `ruff check .`; a synthetic corpus run through `build_collocates`, `build_slices`, `build_keyness`, `build_network` and `build_note`, and `lib.keyness.speaker_keyness` on the same; `npm run lint`; `npm run check` (0 errors); `npm test` (452 passed); `npm run test:e2e` (26 journeys) and `npm run test:e2e:sw` through the throwaway Chromium config; the contract diff is 119 insertions and no deletion. | Tables are ranked by effect among rows clearing G² 10.83 — log ratio for keywords, logDice for collocates, which now carry it — and every row carries `documents`, `meetings` and `dp`. `TOKEN_RE` cannot end on an apostrophe or hyphen and may carry a digit, so `'genocide'` and `R2P` are the words they are. Definitional pairs are found from the declared examples and listed with their reason; the `denial`–`genocide` edge is no longer drawn. The language page prints the spread beside every row, the speaker keyness table too, and the standfirst says the floor and the rank. **Owed:** the corpus re-run of 05 and 12, and 10 on the cluster for the lemma layer, which the tokeniser change makes stale. |
| 2026-09-02 | U9 word budget; M2 amended (review §8, items 3 and 8) | complete   | pending | `node web/scripts/word-budget.mjs` (20 figures, 2,210 words, no slot over); `npm run lint` (now includes the budget); `npm run check` (0 errors, 0 warnings); `npm test` (440 passed: the cloud's 43 tests went with it, `dotplot.test.ts` +7, `matrix.test.ts` +6, `language.test.ts` +7 for the profile selection); `npm run test:e2e` (26 journeys) and `npm run test:e2e:sw` through the throwaway Chromium config; `ruff check .` for the 05 docstring | Item 3: a `more` snippet on `Figure`, the download hint as a tooltip, Methods anchors, every figure rewritten to budget and the budget enforced on lint; the actors page loses its duplicated apparatus and the change-point test is explained once, on Methods. Item 8: the word cloud is a dot plot, the force network a matrix, the map a uniform-dot locator under the ranked table with no choropleth, and the register hues mean registers only. No number moved. The one URL contract change is `view=`, now ignored. |
| 2026-09-02 | Item 15: legal milestones, the event rail, meeting labels | complete   | pending | `python -m pytest tests/test_series.py -q` and `series.load_events()` over the committed file (43 events, 6 kinds); `npm test` (`format.test.ts` new); `npm run check`; `npm run lint`; the journeys | Eight legal milestones join `config/events.csv` (Akayesu, Krstić, S/2005/60, *Bosnia v. Serbia*, the first al-Bashir warrant, S/PV.7155, Karadžić, Mladić), registered in `VALIDATION.md` as an open check on their dates. The chronology draws reference dates as ticks on a rail under the axis, on a second grid that shares the zoom, one series per kind with kind chips, in place of 35 full-height rules. `meetingLabel` prints a resumed sitting as the UN titles it (`S/PV.3745 (Resumption 1)`) in the concordance and the reader, and the Digital Library search uses the base symbol. |
| 2026-09-02 | U10 referent path and page anchors (review §8, item 11) | complete   | pending | `npm test` (`concordance.test.ts` +3 for the facet, `figures.test.ts` new); `npm run check`; `npm run lint` (budget unchanged); the journeys | Referent facet in the concordance from the published run, marked model-derived; `/usage?actor=` link from the actor panel; figure ids and a Contents list on the four multi-figure pages; the term picker grouped by register; keyness pages cross-linked; the usage unit rules visible. |
| 2026-09-02 | M4 amended: the DAG, the end-to-end test, lock sync, Dependabot (review §8, item 13) | complete   | pending | `make -n payload` (twelve steps in dependency order); `python -m pytest` (882 passed: `test_end_to_end.py` and `test_requirements.py` new); `ruff check .`; nothing written under `notes/`, `data/` or `web/static/data/` by the test | `Makefile` as the single DAG and `deploy.yml` calling `make payload`; `README.md` and `docs/CLUSTER.md` point at it. The end-to-end test runs 04 and 08 over a synthetic corpus with redirected roots against golden JSON, and found two withheld-rate formatting faults and the unconditional calendar sentence in 04's note. Lock-sync test and grouped Dependabot. **Owed:** the tagged release and the Zenodo deposit, which need the corpus and an account. |
| 2026-09-02 | The corpus run: v3 re-count, block-null re-calibration, lexical counts recorded | complete   | pending | Deploy run 59 (`make payload` on the merged tree; every step through `15_usage.py` completed before `export_web.py` refused the hand-edited contract, corrected in PR #6), its console output read from the job log; deploy run 60 dispatched by hand, because PR #6 touched only `tests/`, which the workflow's path filter ignores, and cancelled by the push that started run 61, which published; `ruff check .`; claims read back against `VALIDATION.md`, `README.md` and `docs/CORPUS.md` §8 | `genocide` holds at 3,273 / 6,092; the six terms whose v2 prefilter carried a space grew (`war_crimes` +347 occurrences, `icc` +737, `responsibility_to_protect` +218, `mass_atrocity` +51, `genocide_convention` +43, `never_again` +18) and no other moved, three of them back to the reconnaissance figures; `n_register_legal` nets −343. The block null keeps the two `genocide` splits (p = 0.0010, 0.0095) and drops the 1996 `atrocity_core` one (0.0255); the README paragraph is rewritten from the artefact. Surface vocabulary 58,904,180 tokens, 109,949 types; every whole-corpus collocate table keeps 100 rows above the floor; speaker keyness publishes 126 of 133. **Open:** the re-read of the re-ranked tables from the site, the tokeniser delta (the previous run's counts were never committed), the two `has_` unions in CORPUS.md §8, the lemma layer. Two lessons: a deploy that fails after the pipeline still leaves its numbers in the job log, and a fix under `tests/` alone does not redeploy. |
| 2026-09-02 | Items 4 and 5: the annotation faults, the disagreement frame, `/usage` | complete | pending | `python -m pytest` (921 passed, from 883); `ruff check .`; `npm run check` (0 errors), `npm test` (457), `npm run lint` (20 figures, 2,200 words); 13 and 15 run end to end against a scratch data root, 13 twice byte-identically; `tools/recount_run.py` against the Gemini run's raw receipts | §4.5 fixed but for `cost_usd`. Counters count work: requests at job creation, returns per new `custom_id`, `passes` per pass; `gather`/manifest/refusal lifted into `lib/annotate.py` and the parity test asserts identity, not constants; 14 gains 16's duplicate-row guard; the ceiling rises to `32,000 + 1,200×n` on the run's own regression. The locator gains a folding pass and recovers 10 of the 18 unplaced quotes. κ is withheld below a 1% minority mass with PABAK beside it; per-class rates below 20 reference occurrences are withheld and their counts are not; macro-F1 is over measurable classes with a support-weighted figure beside it. `MINIMUM_OCCURRENCES` was deliberately **not** raised as the review asked: a threshold separating 5% from the 1.7% base rate needs ≈220 occurrences and would discard Sudan and Serbia, the finding the column exists for; a Wilson interval and a `separated` flag replace the ranking. The gold sample gains a disagreement frame of 535 rows over six disjoint strata, 688 distinct occurrences, and two of the review's stratum sizes are corrected from the runs: `other` is 410 not 641 (the two runs added rather than unioned), pre-onset is 42 and is taken whole. Gemini's manifest recounted: 7,966 → 3,274 sent, 4,474 → 3,273 returned, 19.1M → 13.86M input tokens; the per-pass history is unrecoverable and the manifest says so. Owed: `cost_usd` (no price table exists in the repository) and the prompt v2 / referents v2 pilot. |
| 2026-09-02 | Item 6: grammatical frames of the node (review §3.6, item 2) | complete | pending | `python -m pytest` (974 passed; `tests/test_node_frames.py` new at 90); `ruff check .`; `17_frames.py` run over the corpus from a scratch data root — 6,092 occurrences reconciling to `n_genocide`, both committed runs joining 100% on `occurrence_id`; `npm run check` (0 errors); `npm test` (470, `nodeframes.test.ts` +20); `npm run lint` (21 figures, 2,332 words); `npx playwright test` (26 journeys, one `goto` flake on the first run, clean on re-run) | Seventeen constructions and a published `unframed` residue over a ±90-character window, ordered in five tiers so a treaty title is not counted as prevention; `matched` publishes what each pattern reached before precedence, so the ordering can be priced. The catalogue is 1,446 occurrences (23.7%) and rose from 12.4% to 26.6% at 2002; the residue fell from 34.1% to 16.7% in the same year, so the codebook's reach is itself non-stationary and the artefact says so. Five of eight tested shares survive the meeting-block null; `prevention` and `named_case` would have survived the independent one and do not — the first case in this repository where item 2 changes a conclusion. Triangulation is free and it works: `mandate_or_office` is `neutral_legal_reference` in 176/176 in both runs, `commemoration` is `asserts` in 98% of both, and `distancing` holds 1.3% of occurrences but a quarter of each run's `rejects_or_denies`; the triad and `distancing` are where the two models part, on the report/assert boundary §4.1 names. The morphological split partitions the same 6,092 and reconciles to the 6,061 headline. Also fixed: `word-budget.mjs` could not run on Windows (`URL.pathname` → `C:\C:\…`), so the budget had been enforced only on the deploy runner. Owed: the human reading of the codebook against the concordance, registered as an open check; the figure was never rendered in a browser. |
| 2026-09-02 | Item 9: the word denominator, `genocidaires`, sentence anchors, five new terms, five repairs, lexicon v4 | complete | pending | `python -m pytest` (898 passed, from 883); `ruff check .`; `tools/lock_lexicon.py --check` clean; `npm run check` clean, `npm test` (452), `npm run lint` clean; the effect measured by applying v4 to `speeches_norm.parquet` read-only | Denominator: counted words once (58,904,180) rather than relabelling the unit — every token rate ×1.1271, no count or speech rate moves. `genocidaires` is its own term nested under `genocide`, and the published headline is the derived `genocide_qualification` = `genocide` − `genocidaires` (6,061 / 3,268); `genocide`'s pattern is untouched, so occurrence identities, the gold sample and the four committed model runs stand and `15_usage.py` keeps aggregating. **Decision, taken by the author against the first implementation**, which split the pattern and would have stopped `make payload` at step 15 until a fresh run was paid for; the disjoint version is a two-line edit the day a v4 run is made. The subtraction is declared in a `derived:` block in `config/lexicon.yml`, validated at load — every subtrahend must be `nested_under` its minuend, or the subtraction is an arithmetic accident — and `apply()` refuses a negative difference. Seven terms anchored to the sentence (`commemoration` 6,533 → 321 occurrences, `survivors` 4,013 → 106); `never_again` and `holocaust` deliberately not, with the cost measured. `crime of crimes` (2 occurrences) and `persecution` (a human-rights register) measured and rejected. Seventh register `descriptive`, with a hue in both themes. Effect measured on the corpus read-only and recorded in `VALIDATION.md` rather than owed. Owed: the pipeline run itself. |
| 2026-09-02 | Item 9, follow-up: the headline rule in one place | complete | pending | PR #8's Dashboard job: `evidence.spec.ts:51` found the home page's heading and no chart, three retries; locally `npx playwright test` 26 passed with `--retries=1` (the first `goto('/')` on a cold `vite dev` can abort while it re-optimises echarts); `npm run check` 0 errors; `npm test` 489 (`headline.test.ts` +4); `npm run lint` unchanged at 2,332 words | The chronology and the actor table fell back from `genocide_qualification` to the raw term; the home page did not, read the derived key directly, and crashed on the e2e fixture, which is an artefact cut before v4 and carries only `genocide`. The rule now lives once in `web/src/lib/headline.ts` and all three views use it; the exported SVG names the measure actually drawn, and the caveat's *genocidaires* sentence is shown only when the derived measure is what the figure draws. The fixture is left as it is on purpose: it is the pre-v4 artefact the fallback exists for, and the derived path is what every real payload takes. |
| 2026-09-02 | The deploy after PR #9: three faults behind 03, found by rehearsing the pipeline over the corpus | complete | pending | Deploy run 33649536447 on `main` at 07f377e failed in 03 (`Coverage sample size 100 is smaller than its 109 strata`); 02, 03, 04, 08, 11, 13, 15 and 17 then run in sequence over the real corpus in a scratch data root (`GENOCIDE_DATA_ROOT` and its two siblings), each exit code read; `lib.contract.check` over the twelve artefacts they write: 0 problems; `python -m pytest` 1,028 passed (`test_audit.py` +1); `ruff check .`; `UPDATE_GOLDEN=1` on `test_end_to_end.py` and the diff read; `npm test` 489 | 03's coverage frame promises one occurrence per term and period, and 28 terms make 109 strata for a sample of 100: the step sizes the frame up to its strata and says so (100 → 109, 210 candidates). Two more faults were waiting behind it, both from the headline's move to `genocide_qualification` in item 9: 04 still ran the Poisson test on the raw term, so the inference block had a member with no `speech_rate` and the contract would have refused the payload in `export_web.py`; 11 had renamed `TRACKED` and kept five reads of `computed["genocide"]` and a prevalence over `has_genocide` on columns it no longer read, and died on the first. The test moves to the derived measure (2016, p = 0.0095, unchanged year), 11 names its headline once, and the contract's monthly block says `words`. The rehearsal is the lesson: an agent that measures a lexicon read-only never runs the step, and `test_end_to_end.py` runs 04, 08 and 17 but not 03 or 11. 11 asserts the real corpus totals and cannot join the synthetic run, so `tests/test_countries_step.py` runs its builders on exactly the frame `load_corpus` hands them and holds its source to reaching the headline through `HEADLINE`; 03's sizing fault needs the real lexicon against the real periods and is guarded by the unit test in `test_audit.py`, not by a synthetic run. 12 and 09 were rehearsed too (126 of 133 speakers published; 6,000 meetings, 373 MB) and their artefacts check clean. Owed: 05 alone was not rehearsed — its change since the last deploy is a docstring — and the deploy's log is its check. |
| 2026-09-02 | Item 4: prompt v2, referents v2 onto main, annotation schema 3, the pilot provisioned | complete | pending | `python -m pytest` (1,059 passed on the branch, from 1,027); `ruff check .`; `15_usage.py` run end to end from a scratch data root against both the real v1 pair and a synthetic schema-3 pair, both satisfying one contract; `npm run check` (0 errors); `npm test` (490); `npm run lint` (21 figures, 2,332 words); `npx playwright test` (26); then, after the merge with the deploy repair, 13, 15 and 17 rehearsed over the corpus and the contract checked by the orchestrator | Referents v2 merged onto main; `referents_version` recorded once in `lib/annotate.py::write_manifest`, and the two legacy row shapes become one. `PROMPT.md`'s digest no longer has to equal today's file: `prompts/v<n>.md` keeps every superseded wording and 15 resolves a run by digest, refusing only one it has never seen — the escape that makes editing the prompt possible at all, after the price was refused twice on 2 September. The archive holds superseded versions only; an archive holding every version costs a state in which two copies of one version differ, and a test refuses it. Prompt v2 splits `stance` into `speaker_position` and `concrete_case`, locked at one value; defines `reports_without_position` positively with a settled legal status counted as an assertion; adds six fields and ten worked examples drawn verbatim from the corpus with their line ids; and writes down the distancing, commemoration, title and accountability rules — two of which state what both committed runs already do in 98% and 176/176 of cases. Codebook 3 / annotation schema 3 follows, and no committed run is refused: `llm.resolve_row` translates a schema-2 row, `audit.concrete_case_from_v1` derives the case decision from the recorded referent, and the six added fields are reported absent rather than guessed — 6,092 rows of a v1 run. Two things the translation measured: 800 Luna rows and 535 Gemini rows take the abstract-or-concrete decision twice and differently, and asked apart the two instruments agree on it at 0.951/κ 0.893 against 0.812/κ 0.688 asked together. Prompt caching added on both providers with `cached_tokens` reported from each provider's own counter; the v2 prefix is 7,700 tokens against v1's 3,400, so caching is the condition on which v2 is affordable rather than an optimisation. Owed: the pilot and the full run, both the author's decision, and `cost_usd`, which still has no price table. |
| 2026-09-03 | Phase R defined: the second reader's second review | documented | pending | Documentation only; no code changed, so no gate was re-run. Every claim in the phase was recomputed from committed artefacts: the confidence distributions from the two `annotations.jsonl` (Gemini `high` 6,035/6,092, no `low`; Luna `low` 4), the referent counts and `comparison.state: "none"` from `web/build/data/usage/usage.json`, the schema-2 field list from the head of `runs/2026-08-30-luna-v1/annotations.jsonl`, and R8's corpus size with pandas over `data/derived/speeches_flagged.parquet` (4,286 speeches carrying `ethnic_cleansing`, `crimes_against_humanity` or `war_crimes` and no `genocid*`; 7,494 occurrences of the four atrocity terms in them). `grep` confirms no test or script reads this file. | A recorded working session with Joël Glasman, the second after the one that produced Phase L, read against the site as it stood on the `2026-08-30-luna-v1` run. Recorded as a phase rather than as untracked edits, on the precedent of the 28 August entry, and cited section by section against `REVIEW_2026-09-01.md`, which was made independently and reaches several of the same findings. Eight items, all decided by the author: R1 splits the referent column into situation + modality with a `group` roll-up (referents v3, schema 4, prompt v3); R2 adds the accuser-by-accused matrix the study's own question wants, from schema 3's `accused_actor`; R3 puts a derived provenance mark — computed / mixed / model-derived — on every figure, read off `Figure`'s `source` string so it cannot be asserted falsely, and labelled "computed from the record" rather than "objective" because the lexicon is a hand-built instrument; R4 removes `confidence` from the model schema and the page and keeps it for human coders, who do abstain; R5 adds full screen, extended past the requested ECharts and MapLibre figures to the matrix that prompted the request and is neither; R6 publishes the referent list beside the prompt it is rendered into; R7 removes the register and set aggregates, adopts an intensity ordinal, and accepts that this re-cuts or removes the home page's second figure; R8 sizes the run over atrocity vocabulary in speeches that never say the word. Two things the session said are corrected here rather than carried: the 813 occurrences read off the screen for the sanctions category are 14, so R1 rests on the epistemological argument alone; and R2 is entirely blocked on a run against prompt v2, since no committed row carries `accused_actor`. Nothing is implemented; R1–R4 wait on that v2 run, R5–R7 do not. |
| 2026-09-03 | Phase R extended: the session's second part, R9-R15 | documented | pending | Documentation only; no code changed. New claims recomputed from artefacts: the corpus swap read from `config/dataset-pin.json`, `data/raw/dataset-manifest.json` and `data/derived/manifests/01_build_parquet.json` (Sakamoto-Matsuoka v5.0, `doi:10.7910/DVN/CKPTRB`, 167,642 speeches over 9,464 meetings, 1946-2024); R8's and R9's counts and R10's contrasts recomputed with pandas over the new `speeches_flagged.parquet` (4,133 genocide-bearing speeches, 7,747 occurrences; 4,716 speeches with the three atrocity terms and no `genocid*`; 1,556 meetings holding 50,735 speeches); R15's join key from `source_cow_ccode` (158,563 of 167,642 rows, 200 codes); R14's page sizes from `wc -l` over the routes and `Contents.svelte` read for what it does. | The second half of the same recorded session. Seven new items and five amendments. Amendments: R1 gains `referent_secondary`, a bounded second slot chosen over a list field (which would break "a cell is a count of occurrences" and cost Cohen's kappa) and over a second row (which would break `occurrence_id`); R3 carries the provenance mark into the navigation and names `/language`'s unclear purpose; R7 gains the composition argument (the reader ticks the terms, the author does not pre-group them), retires `r2p_quartet` on the 1992-vs-2000s anachronism, and rebuilds the intensity ordinal on legal status after correcting this document's own claim about ethnic cleansing - it is cited in legal texts as an aggravating qualification of a crime, not as a crime, which is a third tier the earlier draft collapsed; R8 splits into a cheap computed overview and the model layer, on the session's own sequencing. New: R9 makes the meeting a unit and adds a three-value corpus scope, with the rule that a scope never moves a denominator; R10 records the counter-concept question and the measurement that refuses its naive form - the terrorism contrast changes sign between the two corpora (13.1% vs 12.0% on 1946-2024; 15.3% vs 19.5% on 1992-2023), so the unadjusted comparison measures the agenda and the item ships only a meeting-paired design; R11 adds the crime of aggression, absent from the lexicon and central at Nuremberg; R12 records three figures whose purpose did not survive their reader, explicitly without deciding; R13 commissions a signed epistemological page from the second reader; R14 takes the long-page navigation and the home page's misread denominator; R15 states the government/State distinction now and defers the leader-dataset join. The corpus migration is recorded in the preamble rather than as an item: it is the author's work in progress and it answers the session's scraping question by making scraping unnecessary. |
| 2026-09-04 | Phase C defined: the models move to the cluster | documented | pending | Documentation only; no code changed, so no gate was re-run. New claims computed rather than quoted: the run's shape from `data/derived/speeches_flagged.parquet` with pandas (4,133 speeches carrying `genocid*`, 7,747 occurrences, 32.7M characters, longest 151,713 characters and six above ~24k tokens at four characters to the token); the three checkpoints read off the Hugging Face repositories on 4 September 2026 (`Qwen/Qwen3.8-27B`, 27B dense, Apache-2.0, `reasoning_effort` low/medium/xhigh inside `chat_template_kwargs`; `deepseek-ai/DeepSeek-V4-Flash-0731`, 304B, fp8 block-quantised, 48 shards totalling ~170 GB, `reasoning_effort` low/high/max, no Jinja chat template, recipes targeting 4xGB300 with a `deep_gemm` MoE backend; `google/gemma-4-31B-it`, 31B dense, Apache-2.0, ungated, whose ladder the sibling repository measured as a switch); the partition table and the environment split from `docs/CLUSTER.md`; the serving pattern and the one measured throughput figure from `iwac-ai-pipelines/serving/`. | The model layer stops calling hosted commercial APIs and moves to open weights served with vLLM on the Bayreuth cluster: Qwen3.8-27B as the published run, DeepSeek-V4-Flash-0731 as the counter-instrument with Gemma 4 31B named in advance as its substitute, each at its own maximum reasoning level. The published slot goes to the model that fits one card, because the published run is the one that gets made again after every prompt revision, and it puts the demanding model where a serving failure costs a comparison rather than the layer. The argument is reproducibility and the measurability of a reasoning level, and the phase says in its own preamble that cost and confidentiality are **not** the reasons here, so neither can be cited later as though it had been. C1 folds 14 and 16 into one step because vLLM makes both instruments one API; C2 puts the harness in `scripts/cluster/` with a third venv for vLLM and an unattended job that needs no key at all, the corpus already being on the cluster; C3 makes maximum reasoning a measured claim, with a probe that blocks a run whose ladder is flat and with truncation counted as failure rather than as abstention; C4 sizes the job (65,536-token context, one H100 for Qwen, the whole four-H100 node for DeepSeek, resumability across a 24-hour wall as a requirement) and gates the DeepSeek path on a `dev` smoke test, since Hopper has neither the MoE backend nor the fp4 indexer its recipes assume, the release ships no chat template, and it wants the `--trust-remote-code` step 06 refuses on principle; C5 records the weights' repository revision, which is the first time a model input can be pinned as hard as the corpus is by its DOI; C6 states the new pair's shared regulatory exposure — one national framework over both labs, on a corpus about who accuses whom — says how substituting Gemma changes it, and makes per-referent abstention and refusal publishable so that a shared silence cannot read as stability; C7 lists the documents that still describe a paid run and puts the DFG acknowledgement (523317330) in scope for every model-derived figure. L3 and L8 are not rewritten: each gains a dated pointer saying what Phase C supersedes and what it leaves standing. Nothing is implemented, and the phase is timed by the corpus migration — both pointer files are already empty, so the instrument swap costs no comparability that the v5 migration had not already spent, and the next run is also R1's prompt v3 and schema 4. |
| 2026-09-04 | Phase C implementation, local slice: C1–C5 and C7 | in progress | pending | `python -m pytest` (1,076 passed); `ruff check .`; Bash `-n` over the cluster harness; `npm test` (492); `npm run check` (0 errors, 0 warnings); `npm run lint` (21 figures, 2,332 words); `npm run build` (13 entry points, 4 icons); `npm run test:e2e` (26 journeys) | Replaced both hosted transports with one keyless OpenAI-compatible vLLM path; preserved legacy run readability; added strict fence/balanced-JSON recovery without repair; pinned Qwen, DeepSeek and Gemma revisions; added isolated serving/client environments, offline downloads, loopback serving and an unattended cleanup trap; made responses, rows, failures and manifest counters durable one response at a time across scheduler walltime; added a blocking, resumable reasoning-ladder probe; and published validated runtime provenance on `/usage`. C6 remains open. Cluster installation and smoke are not claimed: the read-only VPN/SSH check found the repository and an idle dev GPU, but transferring the working tree was withheld because it requires explicit authorisation to copy repository contents to the remote system. |
