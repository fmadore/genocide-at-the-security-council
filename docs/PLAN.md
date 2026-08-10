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

Status: the table exists; the view does not, and waits on the first validated release.

`scripts/11_countries.py` writes `data/derived/countries/countries.json`: per canonical
`country_org` and per period, the speaker's own denominator, its `genocide`-bearing
speeches and occurrences, both rates computed by the same `lib/series.py` helpers 04 uses,
its ISO3, UN group and centroid where `config/entities.csv` has them, and a `sufficient`
flag. This is what §7 requires to exist before anything is drawn, and it is deliberately
all that was built — a table is not a profile, and publishing one does not license the
other.

Three decisions in it are the gate's, not the author's. **The minimum is derived rather
than declared**: 100 speeches, because at the corpus prevalence of 3.1% a country needs
about 96 before a *zero* means "quieter than the Council" rather than "not heard from
enough". Below it the rates are written as null, so a slice under the minimum cannot be
drawn by a consumer that forgot to check. **Historical states stay separate**: Yugoslavia,
Serbia and Montenegro and Zaire carry a successor's ISO3 so they can be placed at all,
which makes the code ambiguous; merging them would build a denominator no state ever had,
so the collisions are published in `iso3_collisions` instead. **Centroids are labelled as
navigation**, in the artifact rather than only here, and every row carries a `mappable`
flag so the UN Secretariat is excluded on purpose rather than by having no coordinate.

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

Status: **evaluated on 10 August 2026, and not adopted.** The apparatus was run in full on
20,000 speeches with five stability seeds; the numbers are below and in
`data/derived/topics/evaluation.json`. One gate remains open by design — the blinded
intrusion task needs a person — but the measured gates do not support adoption, so the
open one is not what is holding it back.

Do not make a topic model part of the release pipeline until there is a written research
question that collocates and agenda labels cannot answer. That question does not yet exist,
and nothing below creates one.

### What the run found

**Neither model is stable under a 10% resample.** Adjusted Rand index across five seeds:
the NMF baseline averages **0.532** (worst pair 0.454), the embedding model **0.697**
(worst 0.643). Both sit below the 0.7 the script treats as stable, and the embedding model
does not agree with itself about how many topics exist — 62, 61, 64, 66, 62 across the five
fits. A partition that moves that much under a change of sample is a property of a fit.

**The coherence advantage does not survive equal abstention.** Left to their own thresholds
the embedding model leads by 0.037 NPMI. Forced to HDBSCAN's own 15.0% abstention, the
baseline scores **+0.240** against **+0.281** — a gap of **0.041**, below the 0.05 this
phase declares as too small to justify preferring an opaque model over one whose topics can
be checked against a concordance. That comparison is the reason the abstention threshold had
to be calibrated; at the old constant it could not have been made at all.

**Nearly half the sample has no topic more concentrated than noise.** The calibrated
threshold is **0.490** against a floor of 1/k = 0.040, and it leaves **43.8%** of documents
unassigned. The corpus does beat the null — real documents concentrate at a median share of
0.53 against 0.22 for the same words dealt at random, so the model is finding something —
but for 44% of speeches what it finds is not more concentrated than shuffled text.

**The space groups by agenda item, not by speaker.** This is the one result that runs
*against* the caution in this section, and it is recorded as such. In the 2D diagnostic,
74.3% of a point's 25 nearest neighbours share its hand-coded agenda item — a lift of 22.9
over chance — while only 1.8% share its speaker (lift 11.8) and 19.9% its year (lift 4.8).
06's finding that a genocide-bearing speech's nearest neighbour is the same delegation 55.4%
of the time had suggested the space recovered the occasion through the speaker; over 25
neighbours in the projection it does not. An agenda item is still substantially the
occasion, so this does not license a thematic reading — but it is a better result than this
section anticipated, and the next person to weigh adoption should weigh it rather than
inherit the earlier expectation.

**The picture is faithful to the space that was clustered**, which removes one objection
rather than confirming it: trustworthiness of the 2D projection against the 5D reduction is
**0.981**, though 29.1% of each point's 5D neighbours are still absent from its 2D
neighbourhood.

**What would change the decision.** A research question first, per the paragraph above.
Then: stability at or above 0.7 for whichever model is proposed, a coherence margin at
equal abstention that clears 0.05, and a completed intrusion task showing a reader can pick
the intruder well above the 1-in-6 chance rate. Failing stability is the binding constraint
today, and the k sweep suggests it is not a matter of choosing k better: coherence rises
only from +0.210 to +0.249 across k = 15, 25, 40 while the unassigned share falls from 50.7%
to 38.8%.

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
  this corpus; the interpretability half is a word-intrusion task, and **remains open until
  a human completes it**. A score generated automatically here would repeat the error §1.1
  forbids for the lexicon audit. The task was blinded properly on 10 August 2026, and the
  correction is worth recording because the first version was not. 07 wrote one file whose
  columns were `topic, words, intruder, intruder_position, intruder_from_topic, verdict` —
  the answer three columns left of the blank a reader fills in, which is not a blinded task
  whatever this section called it. Two further leaks sat behind that one: `nmf.json` and
  `embedding.json` publish every topic's top words, so an item labelled with its model and
  topic was answerable by subtraction without reading the six words; and the two models'
  items were concatenated rather than interleaved, so the file changed register halfway
  through. It is now `intrusion_task.csv` (an opaque id, the words, a blank) beside
  `intrusion_key.csv`, with the items shuffled together and each carrying the model it came
  from. That last column is not tidiness: both models label topics from zero, so without it
  a completed task scores the pair jointly and cannot say which model a reader could read —
  which is the comparison this whole section exists to make. `scripts/score_intrusion.py`
  joins the two afterwards and reports accuracy per model, with its denominator and beside
  the 1-in-6 chance rate, counting abstentions and answers that were never offered
  separately rather than as wrong;
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
influence or categorical separation.

07 does now write a 2D projection, and it is worth being exact about what changed, because
the sentence that used to stand here said it never would. **The projection is a diagnostic
whose purpose is inverted from the usual one: it exists to argue against a thematic reading
of the embedding space, not to support one.** It is fitted after the clustering, from the
same vectors and the same seed; the five-dimensional reduction HDBSCAN is fitted in is
untouched; no cluster is fitted on the 2D coordinates, no label is derived from them, and
the coordinates are not written to disk, so there is no column to join onto a speech and
call a topic. What is written is `projection.json` and three PNGs, in
`data/derived/topics/`, which is not a release artefact and which `export_web.py` cannot
reach — a guarantee `tests/test_cluster.py` now asserts file by file.

What makes it evidence rather than decoration is that it is measured. For each point,
`projection.json` reports the share of its 25 nearest neighbours **in the 2D coordinates**
that share its speaker, delegation, year, period, hand-coded agenda item, NMF topic and
HDBSCAN cluster, each beside the base rate a randomly chosen other speech would give, so
the figure is a lift rather than a bare fraction. That settles the question the bullet
above only poses: if purity by speaker greatly exceeds purity by agenda item and by NMF
topic, the picture is a picture of speakers, and the note says so in words with the numbers
in them rather than referring a reader to a figure. The HDBSCAN row is reported as a
ceiling, not as a result — the clusters and the picture are two reductions of the same
vectors and are bound to agree to some degree.

The same file also measures how far the picture is from the space that was actually
clustered: trustworthiness of the 2D embedding against the 5D reduction, and the plainer
figure of what share of each point's nearest neighbours in 5D are absent from its
neighbourhood in 2D. Both run on a deterministic subsample whose size and seed are recorded
in the artefact, because the ranks the measure needs are an n-by-n matrix at 20,000 points.
That is the arithmetic reason a thematic map would mislead: points the clustering called
neighbours can sit far apart in the figure. The purity and trustworthiness maths is written
out in numpy, like the adjusted Rand index and the NPMI coherence beside it, so it is
testable in an environment with no scikit-learn; only the UMAP call and the matplotlib
figures need the cluster's packages, and both are imported inside the functions that use
them. `matplotlib` is in `requirements-cluster.txt` for that reason, and the figures select
the Agg backend explicitly because the compute node has no display.

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

Status: item 2 shipped; item 1 in progress; items 3 and 4 gated. Nothing here may precede
the table it depicts.

The project's charts are currently rates over time, the event overlay and the
concordance. Four additions are worth building, in this order:

1. **Word clouds over the lemma collocate table.** 05 has always argued that a cloud is
   a rendering of the collocate table rather than a separate artifact, and that shipping
   it as its own file would invite it to drift from the numbers it claims to depict. That
   argument stands: a cloud must be generated from `collocates.json` at render time,
   sized by log ratio over a stated stoplist, with the table reachable from it. The lemma
   layer is what makes it worth drawing — a cloud showing `crimes` and `crime` as two
   words is a picture of English morphology, not of the Council.

   It must also be **facetable**: `collocates_sliced.json` already carries `by_period`,
   `by_speaker_group` and `by_country` with a declared `minimum_speeches`, and a cloud
   that cannot be cut by period or speaker is a decoration where a comparison was
   available. The facet is a selection over that artifact, not a property of the renderer.
   Which is the argument against `echarts-wordcloud`: it is canvas-only, so no word can
   be a link or be read aloud, it has been unpublished since 2022, and its peer dependency
   is `echarts ^5` against this project's `^6` — a major downgrade bought for a layout
   algorithm. Positions come from `d3-cloud` instead, which computes placement and draws
   nothing, so the words are rendered as SVG anchors that reach the concordance and can be
   read aloud. Its randomness is seeded from the facet key: a cloud that reshuffles
   between renders is not a depiction of a table.
2. ~~**The co-occurrence network as a graph.**~~ **Shipped.** `network.json` carries PMI
   and nPMI edges between lexicon terms, whole-corpus and per period, and the Language
   view draws it as a force graph. Both constraints hold in the shipped version: stroke
   width and opacity derive from **nPMI**, not raw PMI, so a rare term cannot buy
   prominence with rarity alone; and the four nested edges the lexicon implies
   (`atrocity`/`mass_atrocity`, `genocide`/`genocide_convention`,
   `genocide`/`prevention_of_genocide`, `genocide`/`genocidal_ideology`) are suppressed in
   the artifact, listed there under `suppressed_nested_edges`, and named in the figure's
   caveat rather than silently dropped. `min_speeches` is 20 and declared in the artifact,
   so no sub-minimum edge is drawn, and the edge table sits beside the graph.
3. **Actor-view visuals** (Phase 3): speech and term-bearing rates per speaker with
   membership shading, and matched keyness with minimum-sample disclosure. Country
   centroids may support navigation but must never imply that a diplomat is located at
   that point. **The table now exists** — `countries.json`, written by
   `11_countries.py` — and nothing is drawn from it yet. Read its `minimum_speeches` and
   `iso3_collisions` before drawing anything: 468 of 601 speakers carry no rate by
   design, and two ISO3 codes are shared by more than one speaker, so a choropleth keyed
   on the code without reading that block will silently paint one row over another.
4. **A 2D semantic projection**, only if Phase 4 is approved, and only as exploratory
   navigation. Distance on a UMAP plot is not evidence of influence or of categorical
   separation, and any such map must carry that statement in the interface rather than
   in a methods note nobody opens. **The projection 07 writes is not this and must not be
   promoted into it.** It is a diagnostic against a thematic reading (§4), it lives in
   `data/derived/topics/`, its coordinates are never written, and its own numbers are the
   argument for leaving it there: the neighbourhood purities say how much of the picture
   is speaker and occasion rather than subject. Shipping it would mean re-deriving the
   coordinates for the dashboard and answering the §4 gates first — not copying a PNG.

Requirements that apply to all four:

- every visual links to the table behind it, and the two are generated from one artifact;
- no visual introduces a number that does not exist in a JSON artifact with a manifest;
- colour must not encode a quantity the underlying table does not support;
- a slice below the declared minimum sample is not drawn, in any of them;
- **the arithmetic a visual performs at render time is tested.** The research contract
  requires a test that fails when a data contract changes unexpectedly, and until the word
  cloud that requirement was met only on the Python side: the dashboard had no test runner,
  so a filter, a minimum-sample gate or a scale computed in the browser was covered by
  nothing but `svelte-check`, which checks types rather than behaviour. The rule that
  follows is architectural — a visual's decisions live in a plain module that can be
  called from a test, and the Svelte component is a renderer over it. Logic reachable only
  by mounting a component is logic nobody will test twice. `web/src/lib/data.ts` validates
  every payload at the fetch boundary and throws on a malformed one; those validators are
  covered in the same pass. Two of their checks are substantive rather than structural and
  are worth naming: an event without a primary-source URL is refused there, which is §1.2
  enforced at the boundary rather than trusted upstream; and a failed request is evicted
  from the cache, which is the only reason the concordance's retry can ever succeed.

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
6. Add the faceted word cloud, generated from the artifact it depicts. (The co-occurrence
   graph that stood beside it here is shipped — see §7.2.)
7. Add CSV and image export beside every chart and generated table (§7.5).
8. ~~Decide whether topics answer a question the current methods cannot.~~ Decided on
   10 August 2026: not on this evidence — see §4. Reopen only with a research question and
   a model that clears stability, not by rerunning the same comparison.
9. Consider the LLM evaluation only after a human coding protocol exists.

Steps 5 and 6 are deliberately after the release, not before it: both change or add to
what a reader sees, and neither is worth doing on figures the audit has not yet cleared.

This ordering keeps the next release modest and defensible while leaving clear gates for
more ambitious digital-humanities work.
