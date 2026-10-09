# Review roadmap — 24 September 2026

What is still open from the repository review of 24 September 2026 and the
design critiques of 19 September, followed by a one-line index of every
finished review item. [PLAN.md](PLAN.md) remains the project's priorities and
release gates.

All the code the two reviews asked for is in. What is left waits on a person or
on the cluster. The code cites finished items by number ("ROADMAP RV18"); the
index below keeps those numbers resolvable. The measurements behind them are in
[VALIDATION.md](VALIDATION.md), "24 September 2026 — review fixes", and the
full ledger with its evidence column is in git history (this file before
8 October 2026).

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
   a reviewed prompt v4 declares them.
3. **Verify the first events**: `data/interim/genocide_first_events.csv`, 1,884
   rows (RV20; VALIDATION, "Open human checks" 6a).
4. **Two dashboard items that need new wording**, left by the design round of
   8 October 2026 because site copy is frozen: the Overview's closing index of
   seven equal destinations, and a recovery button for the Chronology calendar's
   two refusal states ("No month reached …", "This measure is not in the data").
   *Wording drafted on 9 October 2026, waiting for FM to read it before it goes
   live:* the index is now a three-step route (Chronology, Actors, Concordance)
   under "Test a claim against the record", and each refusal offers a button to
   the nearest figure that can be drawn.

### Waits on the cluster

5. **Run the sampling experiment** before releasing Gemma array 780175:
   `scripts/probe_sampling.py`, greedy against the model card's sampling, about
   100 speeches (RV9).
6. **Re-embed and re-pin the semantic map** when the 24 trimmed openings are
   restored (RV2), and re-run step 10 so the lemma layer carries the new
   tokenizer (RV3).

## Finished, by number

Code locations are where the item lives now; numbers are in VALIDATION.md.

### Correctness

- **RV1** Rejection flag measured from the run (leave-one-out base rate, exact test, Benjamini–Hochberg): `lib/usage.py::position_rows`.
- **RV2** Retired-corpus delivery-language layer removed; speeches carry `language: null`. The 24 trimmed salutations wait on open item 6.
- **RV3** Unicode-aware tokenizer, one apostrophe: `lib/text.py`. The lemma layer waits on open item 6.
- **RV4** `génocidaires` enters `genocide` (lexicon v8): `config/lexicon.yml`.
- **RV5** Declared widenings keep committed runs and coding valid: `lexicon.check_widenings`, `tools/lock_lexicon.py`.
- **RV6** Semantic release bound to its geometry; display attributes re-derived at export: `lib/semantic_release.py`.
- **RV7** Referent identifiers, ordinals and occurrence count in the output schema: `lib/llm.py`. Activation waits on open item 2.
- **RV8** Evidence as numbered sentence spans: `lib/llm.py`. Activation waits on open item 2.
- **RV9** Sampling and truncation experiment: `scripts/probe_sampling.py`. The run waits on open item 5.
- **RV10** Blinded coder packet: `genocide_gold_packet.csv`, written by step 13.
- **RV11** Prompt worked examples kept out of the gold frames: `tools/map_prompt_examples.py`.
- **RV12** CI runs the SDK transport tests: the `Annotation transport` job in `checks.yml`.
- **RV32** Matched controls drawn per stratum: `lib/lexical.py::matched_control`.

### Research design

- **RV13** Model-stratified gold frame from the published run: `lib/gold_sample.py`.
- **RV14** Design-weighted estimates over the union of frames: `usage.weighted_accuracy`. Waits on open item 1.
- **RV15** Gold-corrected aggregate shares: `usage.corrected_shares`. Waits on open item 1.
- **RV16** Offline coding page: `tools/coding_page.py`, `tools/coding_page.html`.
- **RV17** Engagement categories proposed for codebook 4: open item 2.
- **RV18** Rate change split into agenda composition and use: `series/decomposition.json`, drawn under the chronology.
- **RV19** Meeting-clustered intervals for speech rates: `lib/series.py`, drawn on the chronology.
- **RV20** Diffusion risk sets and a first-event review list: `lib/usage.py`. The review is open item 3.
- **RV21** Translation caveat on speaker keyness: `SpeakerKeyness.svelte`.
- **RV22** Unused `intensity` ladder removed (lexicon v8).

### Maintainability

- **RV23** One module for the model-annotation store: `lib/model_runs.py`.
- **RV24** Committed lexicon counts: `config/lexicon.counts.json`, enforced by step 03.
- **RV25** Makefile prerequisites follow each step's imports: `tools/lib_deps.py` → `scripts/deps.mk`.
- **RV26** Provenance refuses missing declared inputs: `lib/artifacts.py`.
- **RV27** Documentation drift corrected and tested: `tests/test_docs.py`.
- **RV28** Speech files gzipped at rest (609 MB → 188 MB).
- **RV29** Logic the tests load moved from numbered scripts into `lib/` (8 October 2026): `lib/gold_sample.py`, `lib/usage_refusals.py`, `lib/sakamoto.py`, `lib/probes.py` and others; outputs byte-identical.
- **RV30** `types.ts` held to the committed contract (8 October 2026): `web/src/lib/types.contract.test.ts`.
- **RV31** Route decisions moved into tested modules at behaviour boundaries (8 October 2026): `web/src/lib/concordance.ts`, `web/src/lib/multiples.ts`.
