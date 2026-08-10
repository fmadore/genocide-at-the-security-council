# Roadmap and release gates

This roadmap separates work that makes the existing claims trustworthy from optional
analyses that would create new claims. The order is deliberate: a topic model, map or LLM
layer is not a substitute for validating the corpus, lexicon and denominators it consumes.

Status: 10 August 2026.

## Research contract

The project studies how genocide vocabulary appears in the English UN verbatim record. It
does not measure private Council deliberation, what was said before translation, whether an
event caused a change in language, or whether a speech describes conduct that legally
constitutes genocide.

Every public quantitative claim must have:

- a versioned input and configuration;
- an explicit numerator, denominator and unit;
- a machine-readable artifact carrying hashes, package versions and the generating commit;
- a readable table or concordance path behind any chart;
- a stated uncertainty or limitation;
- a test that fails when its data contract changes unexpectedly.

## Where the work runs

Steps 00–05, 08 and 09 run on a laptop. Steps 06 (embeddings), 07 (the topic
comparison) and 10 (the lemma layer) run on the University of Bayreuth GPU cluster;
`docs/CLUSTER.md` is the walkthrough, and nothing in the repository names an account
or a host.

Two environments, deliberately: the release pipeline installs `requirements.lock`
with hashes and nothing else, while the optional steps install `requirements-cluster.txt`
resolved freely. They cannot be shared — `umap-learn` needs `numba`, which does not
support the numpy the lock pins, and pip resolves that by silently downgrading numpy.
Splitting them means an optional step can never move the environment that produces a
published figure. The consequence is intended and visible: a manifest from step 06 or
10 names a different numpy from one written by step 01. Lift the split when numba
catches up.

Reduced-precision GPU arithmetic is not bit-exact across devices. Embedding artifacts
are reproducible against the device and package versions their manifest records, not
by hash — which is a weaker guarantee than the corpus has, and is why nothing in the
release depends on them.

## Phase 0 — Correct and harden the existing pipeline

Status: complete in the current implementation; regenerated artifacts still require the
release checks below.

- Pin Harvard Dataverse v6.1 by default; make “latest” an explicit opt-in.
- Validate checksums, strict UTF-8 decoding, tab counts, repaired record counts, dates,
  joins, entity coordinates and complete Council-year coverage.
- Correct the singular/plural atrocity patterns. Require examples and safe literal
  prefilters for every regex.
- Distinguish explicit non-English delivery languages, inferred in-person English and
  unknown VTC delivery language.
- Write parquet, JSON directories, audit samples and exports atomically.
- Record input/config hashes, package versions, Git commit and generation time.
- Replace raw-value breakpoint claims with denominator-aware binomial and Poisson models;
  retain wild binary segmentation only as an exploratory diagnostic.
- Use true paired target/control samples for keyness and report sensitivity across seeds.
- Merge overlapping collocation windows and suppress lexicon edges implied by nesting.
- Validate web payloads at the fetch boundary and verify every public static route.

Exit gate: full Python, Ruff, Svelte, ESLint, Prettier and production-build checks pass from
a clean environment.

## Phase 1 — Validation freeze and first citable release

Status: in progress.

### 1.1 Human lexicon audit

`scripts/03_lexicon.py` draws a deterministic 200-row sample with two complementary
sampling frames:

- occurrence-level rows estimate the experience of opening a random concordance hit;
- speech-level rows prevent repetitive speeches from dominating the estimate;
- term × period anchors ensure rare terms and all four periods are inspectable.

A human reviewer records `verdict`, `source_checked` and `phenomenon`. Report precision
with its denominator for the core term and for the broader lexicon; do not silently turn an
AI review into a human verdict. Any pattern edit bumps the lexicon version and restarts this
gate.

### 1.2 Source and data checks

- All chronology annotations must link to the primary institutional record. They remain a
  contextual overlay, never an explanatory variable.
- Resolve the single OCR-tolerant `genecide` case against the printed S/PV record.
- Spot-check repaired TSV rows and continuation speeches against source documents as listed
  in `docs/VALIDATION.md`.
- Record the difference between 6,595 corpus documents and 6,582 distinct meeting symbols;
  never label one as the other.

### 1.3 Release metadata

- ~~Choose an explicit licence for repository code and project-authored derived
  artifacts.~~ Settled on 10 August 2026: code MIT (`LICENSE`), derived artifacts CC BY 4.0
  (`LICENSE-DATA.md`). Three layers, not two — the source corpus remains CC0 by its
  depositors, and verbatim speech text extracted from a derived table stays CC0 rather than
  acquiring an attribution requirement it was never under. CC BY covers the selection,
  arrangement and computation this project contributes, which is the part that has an
  author.
- ~~Confirm author names, ORCIDs and contributors in `CITATION.cff`.~~ Confirmed by the
  author on 10 August 2026: sole author, ORCID 0000-0003-0959-2092, University of Bayreuth.
  The corpus depositors stay in the `references` block, which is where they belong: they
  are cited, not credited as contributors here.
- Tag the release only after all generated notes and dashboard prose match the regenerated
  figures.

Exit gate: human audit complete, primary-source links present, licence selected, citation
metadata confirmed, and a clean rebuild reproduces artifact hashes apart from timestamps
and commit metadata.

## Phase 2 — Reproducible publication

Status: implemented; first live deployment still depends on repository Pages settings.

The Pages workflow rebuilds the 488 MB payload from Dataverse v6.1 rather than committing
generated data or relying on one workstation. It installs the hashed Python lock, runs steps
00–09 plus `export_web.py`, builds every public route and uploads the static artifact.

Operational checks:

- Pages source is set to GitHub Actions;
- direct visits to overview, chronology, language, concordance and methods work under the
  repository base path;
- the reader fallback loads a meeting and preserves concordance highlighting;
- manifest hashes and the visible lexicon version agree;
- a failed data fetch shows a useful retry state, not a blank chart.

## Phase 3 — Actor view

Status: planned after the first validated release.

An actor profile is the strongest next addition because the normalized corpus already has
speaker identity, Council status and denominators. It should show:

- speeches and term-bearing speech rates over time;
- membership-aware P5/E10/non-member status;
- agenda composition and matched keyness with minimum-sample disclosure;
- quotations linked to the concordance and source reader.

Gate: no profile or ranking for a slice below the declared minimum; aliases and membership
must pass existing crosswalk tests. Country centroids may support navigation, but they must
not imply that a diplomatic speaker is geographically located at that point.

## Phase 4 — Optional topics and semantic projection

Status: adoption still deferred by design; the evaluation is now runnable.

Do not make a topic model part of the release pipeline until there is a written research
question that collocates and agenda labels cannot answer. That question does not yet exist,
and nothing below creates one.

What has been built is the apparatus for deciding, not the decision. `scripts/06_embed.py`
encodes the corpus on a GPU and `scripts/07_topics.py` runs the comparison this phase
requires — a count-based NMF baseline against a UMAP/HDBSCAN approach on a frozen,
period-stratified sample, both seeing the same documents. Neither writes a release
artifact: `export_web.py` does not read `data/derived/topics/`, and the dashboard does not
know it exists. Both run on the Bayreuth cluster; see `docs/CLUSTER.md`.

Required evaluation, and where it now stands:

- stability across seeds and plausible topic counts — measured, as the adjusted Rand index
  between refits that resample 90% of the frozen sample and change the solver seed, plus a
  sweep over k;
- topic coherence plus blinded human interpretability — NPMI coherence is computed against
  this corpus; the interpretability half is emitted as `intrusion_task.csv`, a word-intrusion
  task with its answer key, and **remains open until a human completes it**. A score
  generated automatically here would repeat the error §1.1 forbids for the lexicon audit;
- sensitivity to long speeches, formulaic Council language and time period — reported per
  topic as median and p90 length, the share of words appearing in over half of all speeches,
  and the dominant period;
- nearest-neighbour inspection for the 3,273 genocide-bearing speeches — written by 06.
  Read the same-year and same-speaker shares first: if the neighbours are mostly the same
  debate, the space has recovered the occasion, and a topic model built on it will return
  agenda items dressed as themes;
- an explicit “unassigned/uncertain” outcome rather than forced labels — HDBSCAN's noise
  label is kept, and the NMF baseline is given the same abstention through a minimum
  document-topic weight, so the comparison does not reward one model for a candour the
  other was never offered.

The last of those took two attempts, and the first attempt is worth recording. A
document's NMF share is its largest topic weight over the sum of them, so it can never
fall below 1/k. The threshold was a constant, 0.05: unreachable at k=15, a rounding error
above the floor at k=25, and binding only at k=40 — one number meaning three things across
the sweep it was swept over. The run of 10 August 2026 showed the consequence, 0.0%
unassigned in every NMF fit against 15–23% for HDBSCAN, which is precisely the asymmetry
the bullet exists to prevent.

The threshold is now calibrated rather than declared. Every token of the frozen sample is
pooled, shuffled and dealt back into documents of the same lengths; the same vocabulary and
idf are applied; the model is refitted; and the threshold is the 95th percentile of the
shares that null produces. A document is assigned only when its best topic is more
concentrated than the model manages on text with no co-occurrence structure at all. The
quantile is declared in `scripts/lib/topics.py` before any run, each k in the sweep is
calibrated against its own floor, and the threshold is then held fixed across the stability
refits — recalibrating inside each refit would make the adjusted Rand index measure the
threshold moving as much as the topics moving.

Because the two models still abstain at different rates, the baseline is read a second time
at HDBSCAN's rate — same factorisation, same topics, only the line moved — so a coherence
gap cannot be an artefact of one model having declined to answer more often. Both readings,
the null and observed share distributions, and the unassigned share across a range of
thresholds are written to `evaluation.json`.

Two limits on what a passing evaluation would license. Reduced-precision GPU arithmetic is
not bit-exact across devices, so embedding artifacts are reproducible only against the
device and package versions their manifest records, not by hash. And a 2D projection remains
exploratory navigation only — distances on a UMAP plot are not evidence of historical
influence or categorical separation, which is why 07 writes no map.

## Phase 5 — Optional LLM structured extraction

Status: deferred until Phases 1–2 are complete.

The LLM layer may classify a bounded question such as referent, speech act or legal stance;
it must not decide whether genocide occurred. Build it as a frozen evaluation before a
corpus-wide run:

1. Define a small schema with evidence spans, an abstention value and no free-form hidden
   rationale.
2. Create a stratified human-coded gold set including difficult negatives, quoted/denied
   claims, commemorative uses and OCR damage.
3. Measure per-class precision, recall, macro F1, abstention and evidence-span validity.
4. Run prompt/model sensitivity and negative controls; keep model and prompt versions in
   every output.
5. Require a second human coder on a subset and report agreement. Adjudicate disagreements
   before setting thresholds.
6. Ship only categories that meet predeclared thresholds. Mark all model-derived fields in
   the interface and always expose the supporting quotation.

No model output may overwrite corpus text, lexicon counts or human annotations.

## Phase 6 — Lemma-based lexicometry

Status: built and runnable; not adopted, and not part of the release.

Inflection splits every table in 05: `crimes` and `crime` occupy two of the hundred rows
a collocate list has, each carrying a fraction of the evidence they jointly support.
`scripts/10_lemmatise.py` builds a lemma layer over the corpus and
`05_lexical.py --vocabulary lemma` counts it, writing to `data/derived/lexical_lemma/`.
Measured on the full corpus: 15.3% of running text collapses (9.0M of 58.9M tokens), and
merging `crimes`/`crime` and `committed`/`commit` promotes `punishment` into the top
collocates of `genocide` — the Convention's own title, previously held below the cutoff
by inflection alone.

Three constraints are structural, not incidental:

- **The lexicon is never lemmatised.** `config/lexicon.yml` matches surface forms and
  §1.1 gates a human audit on those patterns. Folding `genocides` into `genocide` before
  step 03 would move every published count and restart that audit.
- **The surface tables are never overwritten.** Lemma mode writes to its own directory.
  The dashboard reads the surface tables, and so does the audit in progress.
- **A missed merge is preferred to a wrong one.** A lemma is accepted only when the
  tagger and `lib.lexical.tokenise` agree on the token's extent *and* the lemma is itself
  a word. Both rules were added after a run produced wrong output rather than an error:
  hyphenated compounds inheriting their first fragment's lemma (`Secretary-General` →
  `secretary`, 71,703 occurrences) and document symbols entering the vocabulary
  (`S/24232`). Hyphenated compounds consequently do not collapse. 1.7% of tokens have a
  lemma offered and refused, and that figure is reported.

Every merge is recorded in `data/derived/lemmas/mapping.csv`, most frequent first, so a
reader who distrusts a lemma table can see what was merged into what without rerunning
anything.

Open decisions before this could become the default reading:

- `further` lemmatises to `far`, which the stoplist does not cover. Adding `far` to
  `config/stopwords.txt` would also change the surface tables, so the leak is reported
  and left for a human.
- Adoption would change published collocate and keyness figures, so it cannot precede
  the §1.1 audit closing.

Gate: adopt as the default only with the audit closed, the mapping table reviewed at
least down to the frequency where a wrong merge stops mattering, and both readings
published side by side for the release they first appear in.

## Phase 7 — Visualisation

Status: planned. Nothing here may precede the table it depicts.

The project's charts are currently rates over time, the event overlay and the
concordance. Four additions are worth building, in this order:

1. **Word clouds over the lemma collocate table.** 05 has always argued that a cloud is
   a rendering of the collocate table rather than a separate artifact, and that shipping
   it as its own file would invite it to drift from the numbers it claims to depict. That
   argument stands: a cloud must be generated from `collocates.json` at render time,
   sized by log ratio over a stated stoplist, with the table reachable from it. The lemma
   layer is what makes it worth drawing — a cloud showing `crimes` and `crime` as two
   words is a picture of English morphology, not of the Council.
2. **The co-occurrence network as a graph.** `network.json` already carries PMI and nPMI
   edges between lexicon terms, whole-corpus and per period. Edge weight must be nPMI,
   not raw PMI, or rare terms buy prominence with rarity alone; suppressed nested edges
   must stay suppressed and be shown as such.
3. **Actor-view visuals** (Phase 3): speech and term-bearing rates per speaker with
   membership shading, and matched keyness with minimum-sample disclosure. Country
   centroids may support navigation but must never imply that a diplomat is located at
   that point.
4. **A 2D semantic projection**, only if Phase 4 is approved, and only as exploratory
   navigation. Distance on a UMAP plot is not evidence of influence or of categorical
   separation, and any such map must carry that statement in the interface rather than
   in a methods note nobody opens.

Requirements that apply to all four:

- every visual links to the table behind it, and the two are generated from one artifact;
- no visual introduces a number that does not exist in a JSON artifact with a manifest;
- colour must not encode a quantity the underlying table does not support;
- a slice below the declared minimum sample is not drawn, in any of them.

### 7.5 Export what is on screen

Every chart and every generated table should be downloadable — the numbers as CSV, the
chart as an image — from beside the thing itself. The concordance already does the CSV half
(`web/src/routes/concordance/+page.svelte` builds a Blob from the filtered rows); nothing
else does, so a reader who wants to check a collocate table or replot a series has to clone
the repository and run the pipeline.

Three constraints, or the export becomes a second source of truth:

- **Export the artifact's numbers, not the chart's pixels.** A CSV is written from the same
  JSON the chart is drawn from, at full precision, including rows a zoom or a top-N cut is
  currently hiding. A file containing only what happened to be visible is a screenshot with
  commas in it.
- **The file carries its own provenance.** Leading comment rows, or a companion column,
  naming the generating script, the artifact, the lexicon version and the manifest hash —
  the same identifiers the dashboard shows — so a CSV that outlives the tab it came from
  can still be traced. A downloaded table with no version is an orphan the moment a figure
  is regenerated.
- **Chart images state their filters.** A PNG of a filtered or zoomed view must carry the
  term, window, unit and period in the rendered image, not only in the filename.

This belongs after the release, with the word cloud and the graph: it changes what a reader
can take away, not what the figures say, and it is not worth building against figures the
§1.1 audit has not cleared.

## Priority order

1. Complete the human audit and source-document spot checks.
2. ~~Select the code/derived-artifact licence and confirm citation identities.~~ Done,
   10 August 2026 — see §1.3.
3. Run the first reproducible Pages release and archive its manifest.
4. Build the actor view.
5. Review the lemma mapping table and decide whether the lemma reading becomes the
   default, or stays a second reading published beside the surface one.
6. Add the word cloud and the co-occurrence graph, each generated from the artifact it
   depicts.
7. Add CSV and image export beside every chart and generated table (§7.5).
8. Decide whether topics answer a question the current methods cannot.
9. Consider the LLM evaluation only after a human coding protocol exists.

Steps 5 and 6 are deliberately after the release, not before it: both change or add to
what a reader sees, and neither is worth doing on figures the audit has not yet cleared.

This ordering keeps the next release modest and defensible while leaving clear gates for
more ambitious digital-humanities work.
