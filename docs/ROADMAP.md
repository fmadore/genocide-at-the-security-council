# Review roadmap — 24 September 2026

This file tracks the fixes and improvements from the repository review of
24 September 2026, one row per item. [PLAN.md](PLAN.md) remains the project's
priorities and release gates; this is the implementation ledger for the review,
and each row closes with the evidence that it is done. Items that wait on a
person or a GPU say so rather than being marked done.

Every figure below was measured on the pinned Sakamoto–Matsuoka v5.0 corpus,
rebuilt in a scratch data root, against the same pipeline at commit `c981f8b`
as the baseline, and on the committed `2026-09-08-qwen-131k` run.

The change as pushed was rehearsed on 6 October 2026 the way the deploy runs it,
in a fresh worktree from the pinned corpus: `fetch_semantic.py`, then 00–05, 08,
09, 11, 12, 13, 15 `--allow-partial`, 17, 20 and the export, all passing (about
45 minutes, 12 the longest at 17), `export_web.py --check` clean — 9,772 files,
333 MB, 21 artefacts on the contract — and `npm run build` verified on that
payload. The checks workflow passed on the branch, the GNU make regressions
included.

Status: ✅ done · 👥 waits on a human decision or coding · 🖥️ waits on a
cluster run · ⏸ deferred, with the reason

## What still needs a person or the cluster

1. **Code the gold sample** (👥). 453 occurrences, two coders, from the blinded packet
   through the offline page. The probability frame (120) first: the weighted accuracy and
   the corrected shares are computed from 30 units with a reference label.
2. **Review the v4 instrument proposal** (👥, [INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md)):
   engagement categories, sentence evidence, identifiers in the worked examples.
3. **Run the sampling experiment** (🖥️) before releasing Gemma array 780175:
   `scripts/probe_sampling.py`, greedy against the model card, about 100 speeches.
4. **Verify the first events** (👥): `data/interim/genocide_first_events.csv`, 1,884 rows.
5. **Re-embed and re-pin the semantic map** (🖥️) when the 24 trimmed openings are
   restored (RV2), and re-run step 10 so the lemma layer carries the new tokenizer (RV3).

## Correctness

| ID | Item | Status | Evidence |
|---|---|---|---|
| RV1 | Rejection flag measured from the run: leave-one-out base rate, exact test, Benjamini–Hochberg | ✅ | `lib/usage.py::position_rows`. The run's own rate is 2.74%, not the retired corpus's 1.74%. Of 98 speakers with a published share, 15 were flagged against the old constant; 8 are now (India, Sudan, Yugoslavia, Cyprus, Russia, Israel, the DRC, South Africa). Rows carry `base_rejects`, `p_value`, `q_value`. |
| RV2 | Step 02's retired-corpus normalisation | ✅ / 🖥️ | The delivery-language layer is gone: v5.0 carries no `(spoke in …)` markers, every speech was `Unknown`, and the reader printed "spoke in Unknown" beside each one; speeches now carry `language: null` and the chronology loses its one-category split. The form-of-address rule still trims 24 salutations (listed in VALIDATION §4); correcting it changes 24 embedded bodies and waits on the next embedding run. |
| RV3 | Unicode-aware tokenizer, one apostrophe | ✅ / 🖥️ | 5,383 accented word types were cut at the accent (*régime* → `r` + `gime`, 1,892×). Words 86,854,907 → 86,812,574 (−0.05%) at the old speed. The rebuild also caught a counting path that skipped the new rule (`document_vocabulary`); a regression test holds every path together. The lemma layer is refused as stale until step 10 is re-run on the cluster. |
| RV4 | `génocidaires` with its accent enters `genocide` | ✅ | Lexicon v8: 4,136 speeches / 7,787 occurrences (from 4,133 / 7,747). 03 re-ran the v7 rule: every old span is still counted, so no occurrence identity moved. The Qwen run now covers 7,694 of 7,787 and reports the gap. |
| RV5 | A declared widening keeps committed runs and coding compatible | ✅ | `widened_since` / `widened_from` on terms and on the new `anchor:` block, locked by `tools/lock_lexicon.py`, verified on the corpus by `lexicon.check_widenings`. `Lexicon.complete` names the gap. |
| RV6 | Semantic release bound to its geometry; display attributes re-derived at export | ✅ | `corpus_geometry_sha256` pinned from the corpus that matches the release's content fingerprint. The export re-derives year, affiliation, agenda and flag per point and rewrites the copied manifest; on v5.0 three points change, which without this would have refused the map. |
| RV7 | Referent identifiers, ordinals and occurrence count in the output schema | ✅ / 👥 | `lib/llm.py`: a prompt declaring `constraints: referent-enum` gets them; v3 requests are byte-identical. Root cause found: the v3 worked examples write `referent: Rwanda`, which is what 73 of the run's 77 refusals return. Activation is prompt v4, awaiting review. |
| RV8 | Evidence as numbered sentence spans | ✅ / 👥 | `constraints: sentence-evidence` numbers the sentences and asks for a first and last; the span is contiguous and always located. Same activation as RV7. |
| RV9 | Sampling and truncation experiment | ✅ / 🖥️ | `scripts/probe_sampling.py`, with `top_k` support in the request builder. The Qwen3.8-27B card recommends `temperature=1.0, top_p=0.95, top_k=20` for thinking; the run was greedy. Needs a GPU. |
| RV10 | Blinded coder packet | ✅ | `genocide_gold_packet.csv`: one row per occurrence, seeded shuffle, no frame, cue, stratum or probability. |
| RV11 | Prompt worked examples outside the gold frames | ✅ | `tools/map_prompt_examples.py` maps all ten to v5.0 (`model_annotations/genocide/prompt_examples.csv`); 13 excludes them and refuses a stale mapping. |
| RV12 | CI runs the SDK transport tests | ✅ | A separate `Annotation transport` job installs the client, so the main job still proves the lazy import. Verified locally: 14 passed, none skipped. |
| RV32 | Matched controls drawn per stratum, so a change in one debate does not redraw the rest | ✅ | Found while rebuilding: adding RV4's three target speeches replaced 33 of the published top-100 matched keywords. One seeded generator served every stratum in turn, so 52.9% of the 3,950 controls changed; drawn per stratum, 0.1% do. `lib/lexical.py::matched_control`, with a test; applies to 05's and 12's matched tables. |

## Research design

| ID | Item | Status | Evidence |
|---|---|---|---|
| RV13 | Model-stratified gold frame from the single published run | ✅ | `model_strata`: 100 `rejects`, all 9 pre-onset referents, 40 `other`, 60 `reports_without_position`, 60 `conditional`. Sample: 469 rows over 453 occurrences. |
| RV14 | Design-weighted estimates over the union of frames | ✅ / 👥 | `genocide_gold_design.csv`: every unit's probability under each frame and their union (0.021 to 1 over drawn units). `usage.weighted_accuracy`: Hájek estimate, linearised interval. Waiting on coding. |
| RV15 | Gold-corrected aggregate shares | ✅ / 👥 | `usage.corrected_shares` (prediction-powered inference) for `concrete_case` and `speaker_position`; tested on a constructed bias. Waiting on coding. |
| RV16 | Offline coding page | ✅ | `tools/coding_page.py` + `coding_page.html`: passage in its speech, evidence by selection, cascade, local saving, CSV export and import. Checked in a browser; two defects fixed there (a sticky case/position link, and completion not recomputed after the evidence); exported rows pass `audit.merge`. Served by the `coding-page` launch configuration. |
| RV17 | Engagement categories (distance versus denial) proposed for codebook 4 | 👥 | [INSTRUMENT_V4_PROPOSAL.md](INSTRUMENT_V4_PROPOSAL.md), for both coders, with a pilot protocol. |
| RV18 | Rate change split into agenda composition and use | ✅ | `series/decomposition.json`, a table under the chronology. By agenda item the 1980s→1990s rise (+1.53 points) is more than all composition (+2.12) while use within items fell (−0.59); 2010s→2020s splits +0.25 / +0.34. |
| RV19 | Meeting-clustered intervals for speech rates | ✅ | Annual and quarterly measures carry `speech_rate_cluster_low/high` (999 meeting resamples); the chronology draws them. `genocide` 1994: 4.0–9.3% against Wilson's 5.4–7.8%. |
| RV20 | Diffusion risk sets and a first-event review list | ✅ | Each referent carries the delegations that sat in a debate naming it; `/usage` states the number (Rwanda: named by 120 of 254 exposed delegations; Gaza 45 of 168). 1,884 first events listed for review. |
| RV21 | Translation caveat on speaker keyness | ✅ | In the figure's notes; within the word budget. |
| RV22 | Unused `intensity` ladder removed | ✅ | Lexicon v8; a revived key is refused. Its order was also contestable (ICTY *Tadić*, sentencing appeal, 2000). |

## Maintainability

| ID | Item | Status | Evidence |
|---|---|---|---|
| RV23 | One module for the model-annotation store | ✅ | `lib/model_runs.py`: store paths, pointers, population check; 13, 14, 15, 17, the probes and tools use it. Step 15's published and comparison runs share one `validated()` chain. |
| RV24 | Committed lexicon counts | ✅ | `config/lexicon.counts.json`, written by `03_lexicon.py --update-counts`, enforced by 03. Replaced four copies of 4,133 / 7,747, 03's `DOCUMENTED` table, and repaired `tools/synthetic_usage_run.py`, which still asserted 3,273 / 6,092. |
| RV25 | Makefile prerequisites follow each step's imports | ✅ | `tools/lib_deps.py` writes `scripts/deps.mk`; a test holds it to the imports and another checks every variable the Makefile names. Step 01 now depends on 5 modules, not all of `lib/`. The GNU make regressions run on the Linux runner. |
| RV26 | Provenance refuses missing declared inputs | ✅ | `artifacts.provenance` raises; genuinely optional inputs are recorded as `absent_optional`. File hashes are memoised per process. |
| RV27 | Documentation drift, and a test against it | ✅ | README, CORPUS, VALIDATION, CLUSTER, the READMEs, the deploy comments and code comments corrected; `tests/test_docs.py` ties the README and CORPUS figures to the committed counts and keeps retired speech identifiers out of the code, save the one tool that reads them from the prompt's worked examples. Seventeen frame example lines cited retired identifiers: fifteen mapped, two replaced. `tools/recount_run.py` removed (it could not import). |
| RV28 | Payload headroom under the GitHub Pages limit | ✅ | Speech files are gzipped at rest and decompressed in the browser: 609 MB → 188 MB. |
| RV29 | Logic that tests load from numbered scripts moves into `lib/` | ⏸ | Done where a boundary was touched anyway (store, population, semantic points, the run validation chain). The rest — chiefly 13's sampling and 15's refusals — is a mechanical move of about 1,500 lines with no change in behaviour, better reviewed as its own change than inside this one. |
| RV30 | One schema source for payload types | ⏸ | `contract.test.ts` already fails when the dashboard requires a field the pipeline does not write. Generating `types.ts` would discard its field-level documentation; not worth it until a field actually drifts past both checks. |
| RV31 | Large route components | ⏸ | PLAN §7: extract at behaviour boundaries, not to hit line limits. The new chronology table and diffusion note were added without growing any figure's apparatus. |
