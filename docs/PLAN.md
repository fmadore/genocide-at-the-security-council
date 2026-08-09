# Roadmap and release gates

This roadmap separates work that makes the existing claims trustworthy from optional
analyses that would create new claims. The order is deliberate: a topic model, map or LLM
layer is not a substitute for validating the corpus, lexicon and denominators it consumes.

Status: 9 August 2026.

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

- Choose an explicit licence for repository code and project-authored derived artifacts.
  The underlying corpus remains CC0 regardless of that choice.
- Confirm author names, ORCIDs and contributors in `CITATION.cff`; do not guess missing
  identities.
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

Status: deferred by design.

Do not make a topic model part of the release pipeline until there is a written research
question that collocates and agenda labels cannot answer. If approved, compare at least one
transparent count-based baseline with one embedding-based approach on a frozen sample.

Required evaluation:

- stability across seeds and plausible topic counts;
- topic coherence plus blinded human interpretability;
- sensitivity to long speeches, formulaic Council language and time period;
- nearest-neighbour inspection for the 3,273 genocide-bearing speeches;
- an explicit “unassigned/uncertain” outcome rather than forced labels.

A 2D projection is exploratory navigation only. Distances on a UMAP plot are not evidence
of historical influence or categorical separation.

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

## Priority order

1. Complete the human audit and source-document spot checks.
2. Select the code/derived-artifact licence and confirm citation identities.
3. Run the first reproducible Pages release and archive its manifest.
4. Build the actor view.
5. Decide whether topics answer a question the current methods cannot.
6. Consider the LLM evaluation only after a human coding protocol exists.

This ordering keeps the next release modest and defensible while leaving clear gates for
more ambitious digital-humanities work.
