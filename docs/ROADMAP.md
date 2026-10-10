# Review roadmap

What is still open from the repository reviews of 24 September and
8 October 2026 and the design critiques of 19 September, followed by a
one-line index of every finished review item. [PLAN.md](PLAN.md) remains the
project's priorities and release gates.

All the code the reviews asked for is in. What is left waits on a person or on
the cluster. The code cites finished items by number ("ROADMAP RV18"); the index
below keeps those numbers resolvable. The measurements behind RV1–RV32 are in
[VALIDATION.md](VALIDATION.md), "24 September 2026 — review fixes", and the
full ledger with its evidence column is in git history (this file before
8 October 2026). The review of 8 October is
[REVIEW_2026-10-08.md](REVIEW_2026-10-08.md); its codes (B1, C7, …) are given
beside each item it produced, and the commit messages carry the measurements.

## Open

### Waits on a person

1. **Code the gold sample.** 453 occurrences, two coders, from the blinded packet
   through the offline page (`tools/coding_page.py`). The probability frame (120)
   first: the weighted accuracy and the corrected shares (RV14, RV15) are computed
   from 30 units with a reference label. `annotations/genocide/annotations.csv`
   holds its header row only.
2. **Review the v4 instrument proposal** ([INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md)):
   engagement categories (RV17), sentence evidence (RV8), identifiers in the
   worked examples (RV7). The schema constraints are built and switched off until
   a reviewed prompt v4 declares them. Decide it, with the rest of the
   evaluation plan ([EVALUATION_PLAN.md](EVALUATION_PLAN.md) §12: statistics,
   thresholds, the rule for a failing figure, adjudication), before item 1
   starts (RV35).
3. **Verify the first events**: `data/interim/genocide_first_events.csv`, 1,884
   rows (RV20; VALIDATION, "Open human checks" 6a).
4. **Read the drafted site wording before it goes live.** FM approved drafting
   new wording on 9 October 2026; it was written the same day, one commit per
   change with the new text quoted in the message (`git log --grep "^Wording:"`):
   counts only in "Who rejects the word" and the run's status on its downloads
   (RV36), the data build in the footer, "What this record is not" and the
   intervals paragraph on Methods (RV38), a way out of the Chronology calendar's
   two refusals and a three-step route closing the Overview (the two items the
   design round of 8 October left for new wording), and an exact offline note.
5. **Cut the first citable release** ([RELEASING.md](RELEASING.md)): switch on the
   Zenodo integration in the owner's own account, then release "v0.1 —
   unvalidated preview" with the derived tables and the built site (RV33).
6. **Two colour-contrast findings** that need a design decision rather than a
   restyle, found when the accessibility scans began to run in dark mode as
   well (RV63): the Methods page's "Automatic checks" state colour on the zebra
   row (4.36:1, light mode) and the Actors table's selected row (3.45:1, dark
   mode). The scans exclude those two elements, with a comment, until then.

### Waits on the cluster

7. **The sampling experiment** (RV9) was meant to run before Gemma array 780175
   was released; the array ran without it. `scripts/probe_sampling.py`, greedy
   against the model card's sampling over about 100 speeches, still measures
   what the comparison run's sampling setting costs.
8. **Re-embed and re-pin the semantic map** when the 24 trimmed openings are
   restored (RV2), and re-run step 10 so the lemma layer carries the new
   tokenizer (RV3).

### Small, found while doing the review of 8 October

9. **`kwic/index.json`'s `analysis_hash` moves when step 08's code changes.** The
   index records each concordance file's size, and each file now carries the
   list of code that wrote it (RV44), so an edit to a module 08 imports changes
   the sizes and the hash although no line of the concordance changed. Record
   the size of the lines alone, or leave the size out of the hashed part.

### Considered in the review of 8 October and not done

- A shared occurrences table written by 03 and one word-count matrix shared by
  05, 12 and 19 (C5): they would save a few minutes more, at the cost of new
  artefacts and Makefile edges through 08, 13, 15, 17 and 19.
- `make -j` in the deploy (C4): not without measured memory per step on the
  16 GB runner, which the deploy log now records.
- A prefilter for `lexicon.check_widenings`: nothing guarantees a widening's new
  literals occur in what the old pattern matched, so it still re-runs the
  replaced pattern over every speech.
- `submit_embed.sh` keeps `--mem`: the safe per-card figure is not measured.
- Screenshot comparison of the dashboard: the charts, map and fonts make it
  brittle, and the accessibility scans cover the regressions that matter.

## Finished, by number

Code locations are where the item lives now; numbers are in VALIDATION.md.

### Correctness

- **RV1** Rejection flag measured from the run (leave-one-out base rate, exact test, Benjamini–Hochberg): `lib/usage.py::position_rows`. Not shown on the site until the gold sample measures `rejects` (RV36).
- **RV2** Retired-corpus delivery-language layer removed; speeches carry `language: null`. The 24 trimmed salutations wait on open item 8.
- **RV3** Unicode-aware tokenizer, one apostrophe: `lib/text.py`. The lemma layer waits on open item 8.
- **RV4** `génocidaires` enters `genocide` (lexicon v8): `config/lexicon.yml`.
- **RV5** Declared widenings keep committed runs and coding valid: `lexicon.check_widenings`, `tools/lock_lexicon.py`.
- **RV6** Semantic release bound to its geometry; display attributes re-derived at export: `lib/semantic_release.py`.
- **RV7** Referent identifiers, ordinals and occurrence count in the output schema: `lib/llm.py`. Activation waits on open item 2.
- **RV8** Evidence as numbered sentence spans: `lib/llm.py`, `lib/evidence.py`. Activation waits on open item 2.
- **RV9** Sampling and truncation experiment: `scripts/probe_sampling.py`. The run is open item 7.
- **RV10** Blinded coder packet: `genocide_gold_packet.csv`, written by step 13.
- **RV11** Prompt worked examples kept out of the gold frames: `tools/map_prompt_examples.py`.
- **RV12** CI runs the SDK transport tests: the `Annotation transport` job in `checks.yml`.
- **RV32** Matched controls drawn per stratum: `lib/lexical.py::matched_control`.

### Research design

- **RV13** Model-stratified gold frame from the published run: `lib/gold_sample.py`.
- **RV14** Design-weighted estimates over the union of frames: `gold_estimates.weighted_accuracy`. Waits on open item 1.
- **RV15** Gold-corrected aggregate shares: `gold_estimates.corrected_shares`. Waits on open item 1.
- **RV16** Offline coding page: `tools/coding_page.py`, `tools/coding_page.html`.
- **RV17** Engagement categories proposed for codebook 4: open item 2.
- **RV18** Rate change split into agenda composition and use: `series/decomposition.json`, drawn under the chronology.
- **RV19** Meeting-clustered intervals for speech rates: `lib/series.py`, drawn on the chronology.
- **RV20** Diffusion risk sets and a first-event review list: `lib/usage.py::diffusion_rows`. The review is open item 3.
- **RV21** Translation caveat on speaker keyness: `SpeakerKeyness.svelte`.
- **RV22** Unused `intensity` ladder removed (lexicon v8).

### Maintainability

- **RV23** One module for the model-annotation store: `lib/model_runs.py`, which since RV56 also holds the run-file readers and writers.
- **RV24** Committed lexicon counts: `config/lexicon.counts.json`, enforced by step 03.
- **RV25** Makefile prerequisites follow each step's imports: `tools/lib_deps.py` → `scripts/deps.mk`.
- **RV26** Provenance refuses missing declared inputs: `lib/artifacts.py`.
- **RV27** Documentation drift corrected and tested: `tests/test_docs.py`.
- **RV28** Speech files gzipped at rest (609 MB → 188 MB).
- **RV29** Logic the tests load moved from numbered scripts into `lib/` (8 October 2026): `lib/gold_sample.py`, `lib/usage_refusals.py`, `lib/sakamoto.py`, `lib/probes.py` and others; outputs byte-identical.
- **RV30** `types.ts` held to the committed contract (8 October 2026): `web/src/lib/types.contract.test.ts`.
- **RV31** Route decisions moved into tested modules at behaviour boundaries (8 October 2026): `web/src/lib/concordance.ts`, `web/src/lib/multiples.ts`.

### Review of 8 October 2026

Research practice:

- **RV33** Citation metadata ready for a first release: `CITATION.cff` (the models with their revisions; the corpus cited as Dataverse cites it), `.zenodo.json`, `docs/RELEASING.md`. The release is open item 5. (A2)
- **RV34** Third-party reference files removed and linked at their source; the data licence covers the project's own prose only: `LICENSE-DATA.md`. (A6)
- **RV35** Evaluation plan drafted for the two coders: `docs/EVALUATION_PLAN.md`. Its decisions are open item 2. (A3)
- **RV36** "Who rejects the word" shows counts only until the gold sample measures `rejects`, and model-derived downloads say what run they come from and that it is unvalidated: `web/src/routes/usage/+page.svelte`, `web/src/lib/export.ts`. (A1)
- **RV37** The 59 passages read against Qwen's labels before coding are flagged, never dropped (FM, 9 October 2026): `annotations/genocide/prior_review.csv`, rebuilt by `tools/prior_review.py`, carried by step 13 outside the coders' packet; step 15 reports every gold figure with and without them. Five fall in the current sample. (A3)
- **RV38** The record's limits stated: translation, informal consultations, meetings without speeches, counts as minimums, unmeasured lexicon precision. `docs/CORPUS.md`, and "What this record is not" on the Methods page. (A4, A5)
- **RV39** Documentation for reviewers: `docs/PLAN.md` holds the current position only, the retired corpus's records are an appendix of `VALIDATION.md`, the v4 proposal is in English, and `docs/DATASHEET.md`, `docs/CLAIMS.md` and `docs/RUNBOOK.md` are new; `model_annotations/README.md` says what the published run's record means. (A7, A8)
- **RV40** The batch retry dispatcher is in the repository, not only on the cluster: `scripts/cluster/retry_batches.sh`. (A9)

Correctness:

- **RV41** A failed load says what failed rather than "Internal Error": `web/src/hooks.client.ts`. (B1)
- **RV42** The reader keeps its tools under a referent filter, and a filtered CSV names the filter: `web/src/routes/reader/[meeting]`, `web/src/routes/concordance`. (B2, B3)
- **RV43** Two open tabs share one basket: `web/src/lib/basket.svelte.ts`. (B4)
- **RV44** Every step records the code it ran, outside `analysis_hash`: `artifacts.provenance`, `artifacts.lib_closure`. (B5)
- **RV45** Step 15 applies the partial-run allowance itself, and its refusal names the right resume command: `model_runs.partial_allowed`, `lib/usage_refusals.py`. (B6, B7)
- **RV46** CSVs are written with LF line endings on every platform: `artifacts.atomic_write_csv`. (B8)
- **RV47** The end-to-end test's leak check can fail, and golden values compare within one part in a billion: `tests/test_end_to_end.py`. (B9, E4)
- **RV48** `make clean` removes only what `make payload` rebuilds; `make wipe-data` asks first; GNU make older than 4.3 stops with an error. (B10)
- **RV49** Annotation jobs request memory per GPU: `scripts/cluster/submit_annotate.sh`, `serve_annotation.sh`. (B11)
- **RV50** The deploy publishes only after the checks pass: `.github/workflows/deploy.yml`. (B12)
- **RV51** Step 11's note shows a dash for a period without speeches instead of failing.

Speed:

- **RV52** Steps 12, 03 and 05 use 5.5, 3.8 and 2.2 times less processor time; 13, 15 and 17 stop re-reading the corpus; 04 reads only the columns it uses. Every output byte-identical. (C1, C2, C5, C6)
- **RV53** The deploy cache is keyed on the Python the payload runs, read off the Makefile (`make payload-code`, `.github/actions/payload-cache-keys`), and the deploy log shows each step's time and memory. (C3, C4)
- **RV54** The concordance computes each sort key once; ECharts loads with the first chart; the offline cache is bounded; links preload on tap; every prerendered page inlines its own data. (C7, C8, C10)
- **RV55** The payload trimmed from 341 to 329 MB and held to a size budget at the export: the concordance and the reader fetch a 271 KB referent map, `usage/referents.json`, instead of the 6.9 MB usage rows; step 17's per-occurrence rows stay out of the payload; the meeting files' shared provenance is written once, in `meetings.json`, with every `analysis_hash` unchanged. A full rebuild from the pinned corpus before and after the review compared 10,102 files: every number and `analysis_hash` equal, and a build in 26 minutes instead of 66. (C9)

Maintainability:

- **RV56** Large modules split along their seams, outputs byte-identical: `usage` into `agreement`, `gold_estimates` and `usage_comparison`; `llm` into `prompts`, `evidence` and `model_runs`; `topics` into `projection`; `audit` into `schema` and `sampling`; `lexicon` into `lexicon_lock`; step 04's builders into `series_payload`; the notes' tables into `notes`. (D3)
- **RV57** Shared values and paths named once (`paths`, `model_runs`, `keyness.MATCH_ON`), and one parser for `referents.csv`: `lib/referents.py`. (D1, D2)
- **RV58** Library code raises `console.Refusal`; scripts exit through `console.main`. (D4)
- **RV59** Dead code removed (FM approved the three deletions on 9 October 2026) and comments the corpus migration made untrue corrected. (D5, D7)
- **RV60** mypy over `scripts/lib` in CI; pytest strict about markers and settings and failing on `FutureWarning`; coverage reported, never enforced, for both halves. (D6, E7)
- **RV61** Python tests: the meeting bootstrap and the rate decomposition tested and held in the golden file; steps 05, 11 and 12 run end to end; Wilson and G² pinned to outside values with property-based tests beside them; fake corpora from one factory held to the real columns; source-text checks replaced by behaviour tests. (E1, E2, E5, E6, E8)
- **RV62** Dashboard structure: a `urlState` helper, a `Resource` and a `ScrollRegion` shared by the routes, decisions moved into tested modules, ragged CSV rows refused, indexed reads checked, unawaited promises a lint error. (D8, D9)
- **RV63** Dashboard tests: Language and Methods have browser tests, every accessibility scan also runs in dark mode, every fixture is held to the payload contract, the clustered band is drawn in a test, and a flaky test fails CI. (E1, E3, E7)
- **RV64** Cluster scripts: `fetch_results.sh` watches over one connection and fetches model runs, `push_code.sh` removes code deleted from the repository, and shellcheck runs in CI. (E6, F)
