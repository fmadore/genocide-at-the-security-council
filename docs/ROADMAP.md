# Review roadmap

What is still open from the repository reviews of 24 September, 8 October and
9 November 2026, the design critiques of 19 September and the design review of
20 October, followed by a
one-line index of every finished review item. [PLAN.md](PLAN.md) remains the
project's priorities and release gates.

All the code the reviews up to 8 October asked for is in; what is left of
those waits on a person or on the cluster. The review of 20 October left code
to do (items 12 to 14). The code cites finished items by number ("ROADMAP RV18"); the index
below keeps those numbers resolvable. The measurements behind RV1–RV32 are in
[VALIDATION.md](VALIDATION.md), "24 September 2026 — review fixes", and the
full ledger with its evidence column is in git history (this file before
8 October 2026). The review of 8 October is
[REVIEW_2026-10-08.md](REVIEW_2026-10-08.md); its codes (B1, C7, …) are given
beside each item it produced, and the commit messages carry the measurements.
The review of 9 November is [REVIEW_2026-11-09.md](REVIEW_2026-11-09.md); its
code is done (RV65–RV75), and what is left of it waits on a person (items 15
to 18) or on the cluster (item 8). The audit of 19 November 2026 was not
committed as a file; what it found and nothing above already tracks is items
19 to 72, each re-checked in the code unless it says "the audit measured".

## Open

### Waits on a person

1. **Code the gold sample.** 458 occurrences in 469 rows, two coders, from the blinded packet
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

### Waits on the cluster

7. **The sampling experiment** (RV9) was meant to run before Gemma array 780175
   was released; the array ran without it. `scripts/probe_sampling.py`, greedy
   against the model card's sampling over about 100 speeches, still measures
   what the comparison run's sampling setting costs.
8. **Re-embed and re-pin the semantic map** when the 24 trimmed openings are
   restored (RV2), and re-run step 10 so the lemma layer carries the new
   tokenizer (RV3). The same run writes the map's local fidelity among every
   point (`evaluation.local`, RV72), which needs the embeddings; the page shows
   it once a release carries it.

### Small, found while doing the review of 8 October

9. **`kwic/index.json`'s `analysis_hash` moves when step 08's code changes.** The
   index records each concordance file's size, and each file now carries the
   list of code that wrote it (RV44), so an edit to a module 08 imports changes
   the sizes and the hash although no line of the concordance changed. Record
   the size of the lines alone, or leave the size out of the hashed part.

### From the design review of 20 October

Critiques of the Usage page (26/40) and the Semantic map (24/40), and a
site-wide audit (16/20, down from 19/20 mostly through closer measurement):
`.impeccable/critique/2026-10-20T07-3*` and
[`.impeccable/audit/2026-10-20-web-src.md`](../.impeccable/audit/2026-10-20-web-src.md).
The access faults it found are fixed: focus lost after the search boxes, the
unnamed "to" year, the Semantic map stopping the page from scrolling, three
Words in context plates drawn at under 5px on a phone, and the phone menu
staying open when focus left it. Still open:

10. **Decided by FM on 20 October.** The Semantic map page now leads with the
    chosen speech and its related list, read from the full vectors, and the
    flat map follows as an overview. "Who rejects the word" keeps its ranking,
    with the caveat it already carries. Wording written for the reordered page
    is in item 11.
11. **Wording to draft and approve.** The Usage reading notes call the matrix
    shading and the asserts curve "amber"; neither is. The Semantic map's
    68% caveat sits in small type below a reading note that says nearby points
    are similar, and its axis sentence exists only in the CSV export. The
    reorder (item 10) added three sentences, quoted in its "Wording:" commit:
    the map's new question, the prompt shown before a speech is chosen, and
    the map's screen-reader description, which now points to the table above
    it.
12. **Usage page.** The second-opinion statistics sit inside the marking block,
    ahead of every plate (the comments there predate Gemma's publication); the
    Contents list omits "The contested passages", so the last plate prints as
    Plate 5 against four entries; the matrix shades by a register hue and the
    asserts curve is drawn in one, against DESIGN.md's paper-to-ink rule; four
    of five plates export CSV only; a matrix click lists results off-screen
    without saying so.
13. **Semantic map.** The selected speech carries no meeting symbol, speaker or
    date and cannot go to the basket; Back does not undo a filter (`replaceState`);
    decades are coloured as categories; `map.json` is 1.9 MB gzipped for a
    default view of 2.5% of its points; the table needs sideways scrolling on a
    phone.
14. **Site-wide.** `/actors` carries 4.5 MB of data in its HTML; the five
    "Model-derived · experimental" plate links are 21px tall; `browsing.spec.ts:104` is flaky; a few spacing values and
    2px rules off the scales.

### From the review of 9 November 2026, waiting on a person

Each is argued in [REVIEW_2026-11-09.md](REVIEW_2026-11-09.md), section B.

15. **The coder packet's order** (B1). `packet()` puts the probability frame's
    120 first and every model- or cue-selected passage after it, so position
    reveals the frame. Shuffle with a seed of its own, or keep the order as a
    stated choice (item 1 wants the probability frame coded first) and say in
    the evaluation plan that position reveals the frame.
16. **Two frames share a seed** (B2). The coverage frame's random fill ranks by
    seed 23, the third frame's own, so `union_inclusion` overstates `pi_union`
    for the 269 model-stratified units. Nothing is coded yet: give the fill its
    own seed and redraw, which changes which 43 passages it holds.
17. **The unit of the `rejects` test** (B3). `usage.position_rows` treats each
    occurrence as a trial; 235 occurrences sit in 154 speeches. Before the
    markers return (RV36), make the speech the unit or resample speeches.
18. **Wording to approve** (B4). Every fix that changed a sentence, and both new
    Chronology figures, carry text without a `Wording:` commit; the review
    lists the places.

### From the audit of 19 November 2026

An outside audit of `main` at `cfed32e`. Its quick fixes to the live site (1959
drawn as 0.00%, the v5.0 figures on Methods, Language Plate 3's export, v6.0
meeting symbols, the service worker's cache writes, two wheel traps, the two
contrast findings that were item 6, `TermMatrix`'s random id, the PNG caption,
printing from dark mode, three charts without a table) are done: RV76 to RV79
below. What items 12, 13, 14 and 17 already hold is not repeated.

#### Pipeline correctness: published numbers change, one rerun

19. **Hyphenated compounds count as their own collocate.** `TOKEN_RE` keeps the
    hyphen, so `post-genocide` starts before the match, and `bisect_left` in
    `lib/lexical.py` skips the token holding the node: `post-genocide` is Rwanda's
    seventh collocate in `notes/05_lexical.md`. Test tokens by interval overlap.
20. **Sliced collocations divide by the whole corpus.** `by_period`, `by_country`
    and `by_speaker_group` give `log_dice` a slice's counts and a reference
    frequency from all 92.5 M words (`lib/lexical.py:908`). Take the reference
    from the slice.
21. **Unmatched keyness leaves the unmatched targets in the reference.** The
    numerator counts matched targets only and subtracts them from the whole
    corpus, so unmatched `genocide` speeches (212, the audit measured) sit in the
    control arm: `genocide` scores +7.45 unmatched against +13.06 matched.
    Compare every target with its exact complement, in 05 and 12.
22. **Steps 05 and 12 keep procedural turns in the matching pools**, unlike step
    11's exposure. The audit measured 1,224 words per target speech against 742
    per matched control.
23. **The co-occurrence network keeps pairs that can only meet inside
    `genocide` speeches.** `definitional_pairs` drops (anchored term, `genocide`)
    but keeps two anchored or nested terms (`commemoration`–`survivors`), whose
    nPMI over every speech gains about 5.3 bits by selection alone. Drop them,
    or publish PMI given `has_genocide`.
24. **The Python notes still take medians over made-up zeros**, which RV70
    removed from the site: `notes/05_lexical.md` gives `tutsis` +0.00 matched,
    and `notes/12_speaker_keyness.md` its median drops the same way.
25. **Smaller keyness points.** Step 12's `_stability` follows `log_ratio`, not
    `lrc`, the ranking statistic; `self_reference` misses possessives
    (`france's`); bursts of a few meetings and OCR noise (`wlilch`, `cted`) reach
    the top of some rankings, which a ranking by dispersion over meetings
    (Egbert and Biber) would expose.
26. **Frames: explicit negation counts as assertion.** In `lib/node_frames.py`,
    `qualification` accepts `not\s+` (*this is not genocide*) and `occurrence`
    accepts `no\s+` (*there was no genocide*). Take them out and add a
    `negation` frame ahead of both.
27. **Frames: `génocidaires` falls into `other`.** `_MORPHOLOGY`'s
    `^genocid(?:es?|aires?)$` has no `é`; the audit counted 44 of the 45 `other`
    rows in `frames.json` as `génocidaires`.
28. **Frames, smaller.** The `distancing` quote pair takes any opening quote with
    any closing one, apostrophe included, up to 25 characters on; `annual_block`
    omits the seven years without an occurrence (the gap RV66 closed for
    quarters); `slices.period` cuts eight-year blocks off the site's decades.
29. **"Who stays silent" can count the delegation that introduced the word.**
    If A uses it at turn 2, B at turn 5, and A speaks again at turn 8 without it,
    `lib/actors.py::exposure` counts A as exposed after and silent
    (`other_first` is 5, `last_use` 2). Treat a delegation's own earlier use as
    joining; check the `*_after` totals in `reconcile_exposure`.
30. **The calendar control drops 1994 and 1995 as "the two largest years"**; on
    v6.0, 2024 (1,096 occurrences) and 2014 (659) are larger, the audit
    measured. Derive the years from the data:
    `lib/series_payload.py::CALENDAR_CONTROL_YEARS`.
31. **The rate split's intervals.** `before_ci95` and `after_ci95`, drawn by
    `RateSplit.svelte`, treat speeches as independent while the test resamples
    meetings; a zero Poisson count takes `-log(0.05)/exposure`, a one-sided
    bound, where two-sided 95% wants `-log(0.025)` (`lib/series.py:852`).
32. **`share_rejects` divides by occurrences that cannot reject.**
    `usage.position_rows` keeps `no_position` rows (`concrete_case == "no"`) in
    the denominator. Filter to concrete cases, with item 17.
33. **Diffusion risk sets keep procedural turns and trust one pre-onset label.**
    `usage.exposure_rows` does not drop `source_procedural`, and a single
    `pre_onset_referent` puts a whole meeting at risk decades early.

#### Gold sample and coding tool: before coding starts (item 1)

34. **Done on branch `gold-prep` (RV80).** Weighted estimates under partial
    coding.
35. **Done on branch `gold-prep` (RV81).** `corrected_shares` over one
    population.
36. **Done on branch `gold-prep` (RV82).** Step 13's note and manifest report
    the model-stratified frame.
37. **Decided by FM on 19 November 2026 (RV84).** `DENSE_MEETINGS` kept as
    drawn.
38. **The coding page, what is left.** The evidence span, the BOM, the import
    command and the Digital Library link are done (RV83). Still to do: tests for
    the page's own script, keyboard shortcuts, "next uncoded" and a search of
    the passages.
39. **Prompt v4, evidence, agreement.** `PROMPT.md` still says 1946-2024, and
    worked example 4 puts deniers in `accused_actor`; `locate_evidence` stops at
    the first pass matching anywhere in the speech, even away from the
    occurrence (the audit's reading); `per_label_kappa` lacks the minority floor
    and PABAK that the field-level figures carry.

#### Site and figures

40. **`DotPlot` and `FrameProfile`.** `dotRadius` floors a square-root scale, so a
    word at 1% of the largest count draws 12% of its area; both are 720 units
    wide drawn at 100%, so a desktop scales them to about 1,376 px with 23 px
    labels, the audit measured. Scale area from zero and cap the width.
41. **Exported SVGs lose their font.** `DotPlot`, `FrameProfile` and
    `TermMatrix` write `var(--sans)`, which nothing resolves outside the page.
    (The caption's long lines now wrap: RV76.)
42. **Back does not undo a filter** on Chronology, Actors, Language and Usage:
    they call `urlState` without `step` and `restore`, which only the
    Concordance passes (the Semantic map is item 13).
43. **Figure defects.** `Decomposition.svelte`'s legend and right-hand notes
    leave its 720-unit `viewBox`; `RateSplit.svelte` has no label collision
    handling and no `<title>` on its points; the Chronology legend hides the
    dashed lines, and a series turned off leaves its band.
44. **The Concordance's "show more" window** ignores the referent and regex
    filters when it resets (`concordance/+page.svelte:159`).
45. **Text that no longer matches its figure.** Language's "A blue mark flags"
    over a `FrameProfile` drawn in ink; `VictimFigures.svelte`'s "the figure
    beside this one" for one below; the Reader's register key without
    `descriptive`; `config/events.csv:49`'s "Two days before the corpus ends";
    `VictimGrid.svelte` shaded in a register hue with no scale key; the
    Methods step register, which leaves out steps 00, 18, 19 and 20 and
    `export_web.py`. Wording waits on FM.
46. **Wide tables outside `ScrollRegion`** cannot be scrolled from the keyboard
    (the audit named none individually; find them with the phone-width scan).
47. **Additions within DESIGN.md.** A dashed mark at the accepted break year on
    Overview Plate 1; each small multiple's peak year and value; heatmap
    months linking to the concordance; one delegation followed across Actors
    Plates 2 to 5; Semantic map neighbours that open on click; the
    `DiffusionChart` axis read against the risk set.

#### Payload and performance

48. **`/usage` downloads 15.1 MB on open.** `wanted = $derived(selected ||
    comparison.computed)` holds as soon as the comparison is published, so
    `usage/occurrences.json` (8.55 MB) and `kwic/genocide.json` (6.89 MB) load at
    mount, against `usage/+page.ts`'s comment. Ship a small contested preview and
    load the rest on first use.
49. **Prerendered pages of several MB**, refetched network-first: beyond
    `/actors` (item 14), `usage/index.html` (2.87 MB, 1.18 MB of it the matrix
    table) and `chronology/index.html` (2.63 MB, inlining monthly, quarterly and
    breakdown series the first view does not draw), the audit measured.
50. **The concordance files, 71 MB of a 354 MB payload** (400 MB budget). Every
    line of `kwic/genocide.json` carries `"iso3": null` (8,611 of 8,611);
    country, agenda, group and type repeat as strings; `sent` repeats the
    window's text. Drop `iso3`, index repeated strings as `map.json` does.
51. **The Semantic map page** rebuilds a 182,684-key `Set` on every click and
    re-sorts the years on every render (`semantic/+page.svelte:253`, `:334`);
    splitting `map.json` is item 13.
52. **MapLibre is 1.6 MB of JavaScript** for uniform points on the Actors map:
    load it when the map scrolls into view, or draw on an SVG base.
53. **The offline cache keeps the two largest files** (`map.json`,
    `occurrences.json`) in `OFFLINE_KEEP` with no bound of their own; Safari's
    quota is the likely limit.

#### Build, CI and release

54. **The Makefile does not declare `config/council_membership.csv` or
    `config/country_aliases.csv`**, so editing either leaves the payload as it is.
55. **`tools/carry_over_runs.py --write` fails today**: `run_rows()` globs every
    run under `runs/`, the v6.0 runs of 3 November included, whose rows v5.0
    lacks.
56. **`export_web.py` copies about 9,900 meeting files (197 MB) into staging on
    every export**; hard links with a copy fallback keep the swap atomic.
57. **`word-budget.mjs` finds figures with `indexOf`**; parse with
    `svelte/compiler` as `figure-provenance.mjs` does, which in turn skips
    nested routes such as `reader/[meeting]`.
58. **CI.** A push to `main` that deploys runs Checks twice (its own trigger and
    the deploy's `workflow_call`); Playwright downloads Chromium every run;
    actions float on major tags while pip and shellcheck are pinned by hash.
59. **What the checks cover.** `contract.py` leaves out `semantic/map.json` and
    `actor_year.csv`; mypy covers `scripts/lib` only, not `export_web.py` or
    `tools/`.
60. **Repository hygiene.** Ignore `.claude/worktrees/`; decide whether the 14
    `.impeccable/` files stay versioned; drop `docs/reference/**` from
    `.gitattributes`.
61. **Before release v0.1 (item 5).** `CITATION.cff` says Gemma's run "is not
    yet published"; check it with `cffconvert` in CI; `RELEASING.md`'s warning
    about `make clean` predates RV48; an `export_web.py --release` flag for the
    footer's `release`; `tools/package_release.py` for archives and
    `SHA256SUMS.txt`.

#### Research decisions, not bugs

62. **Lexicon v9.** `prevention_of_genocide` wants `of` after `preventing` and
    misses "prevent genocide" and "preventing genocide" (118 sentences against
    262 matches, the audit measured); `genocide_convention`'s second branch and
    `special adviser on the prevention` do not require `genocide`, though
    nested under it, and step 03 does not check nesting; `early_warning` (2,169,
    20 beside `genocid*`) and `impunity` (15,547) are council-wide vocabulary:
    anchor them or say so, as for `massacre`. With item 2.
63. **The sentence splitter's abbreviations.** `lib/text.py::ABBREVIATIONS` lacks
    `u.s.s.r`, `res`, `doc`, `rev`, `add`, `corr` and ranks such as `col`; the
    one-capital rule blocks a sentence end after `I.` It drives the seven
    anchored terms and v4's sentence evidence: decide before the gold freeze.
64. **More than one change point.** With one break over 81 years, `speech_rate`
    splits at 1978 and `token_rate` at 1992; a penalised multiple-break
    segmentation calibrated on meeting blocks would read the regimes better.
65. **The decomposition and new agendas.** Setting `r1 = r2` for an item present
    in one decade gives every new conflict, and every renamed item, wholly to
    composition (`lib/series.py:389`). Show both agenda codings, the share off
    common support, and meeting-block intervals.
66. **The retention floor in meetings.** The 125-speech rule assumes independent
    speeches and serves terms a hundred times rarer than `genocide`; add a
    minimum number of meetings.
67. **Silence against the same meetings.** Raw `share_after` sets a permanent
    member's thousand meetings beside a delegation heard in dedicated debates;
    an observed-to-expected ratio at the room's rate in the same meetings
    compares like with like.
68. **Embeddings.** Near-identical procedural turns crowd the UMAP graph:
    project substantive speeches; `recall@10` draws 128 unstratified queries;
    `local_fidelity` measures trustworthiness, not continuity;
    `embeddings.pool` averages unnormalised chunk vectors. With item 8.
69. **Names across regimes.** COW codes put the USSR under Russia and the ROC
    under China; `broad_agenda` keeps the first Repertoire category only. Show
    the period's name in evidence rows and the crosswalk in exports.
70. **The meeting unit.** Numbered meetings with several records (9,919 records,
    9,467 numbers): test scope, exposure and clustering by meeting number too.
71. **Procedural turns in the denominator.** Prevalence is 2.505% over all turns
    and 4.061% without the source's procedural ones: publish both where the
    choice matters.
72. **New figures from what is built**: concentration by meeting, atrocity
    vocabulary without `genocide` (`genocide_free_atrocity` in `lib/scopes.py`),
    and Qwen–Gemma agreement case by case once gold labels exist.

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

### Review of 9 November 2026

- **RV65** Rates and both intervals withheld below 125 speeches for a year, a quarter and a breakdown cell, as for a month; counts always, `sufficient` beside them, withheld values drawn as gaps: `lib/series_payload.py::MIN_SPEECHES_PER_PERIOD`, `web/src/lib/chronology.ts`. (A1)
- **RV66** The quarterly series is a complete grid, 322 quarters of which 275 carry a rate: `lib/series.py::quarter_grid`. (A2)
- **RV67** The band is the envelope of the Wilson and meeting-clustered intervals; the bootstrap's docstring says it is 0 to 0 where no meeting used the word: `web/src/lib/chronology.ts::bandBounds`. (A3)
- **RV68** "Who stays silent" counts in speaking order (`exposed_after`, `joined_after`) and the download carries both readings: `lib/actors.py::exposure`, `web/src/lib/silence.ts::ordered`. Keeping the ordered default is FM's call. (A4)
- **RV69** Keyword tables ranked by the conservative log ratio (`lrc`), the selection word's own rows marked (`node`): `lib/lexical.py::conservative_log_ratio`, `web/src/lib/keyness.ts`. (A5)
- **RV70** The matching summary counts the words that left the matched table and takes a median only over words in both, withheld below five: `web/src/lib/keyness.ts::removed`. (A6)
- **RV71** The series publish `record.first_date` and `last_date`; the overview outlines the part-year and compares the last whole year; the month grid has a `beyond` state for months outside the record: `lib/series_payload.py`, `web/src/lib/overview.ts`, `web/src/lib/heatmap.ts::beyondRecord`. (A7)
- **RV72** The semantic map's local fidelity, among every point, written by step 21 as `evaluation.local`: `lib/projection.py::local_fidelity`. The figure waits on open item 8. (A8)
- **RV73** Smaller: the profile table gated as its figure is, the agenda list showing the eight items its remainder excludes, "<1%" for a non-empty cell, axis decimals for rare terms, `corpus_words` for the CSV column that holds words: `web/src/routes/language`, `web/src/lib/SpeakerKeyness.svelte`, `web/src/routes/usage`, `web/src/routes/chronology`. (A9)
- **RV74** Two new Chronology figures, *Agenda or usage?* over `series/decomposition.json` and the rate-split drawing in *Testing for a change in the rate*, both drawn in the browser tests: `web/src/lib/Decomposition.svelte`, `web/src/lib/RateSplit.svelte`, `web/e2e/tests/decomposition.spec.ts`. (C1)
- **RV75** Eleven visual defects fixed, among them the split figure's axis, the delegation keyword figure's register hues and "darker is stronger" in dark mode; ECharts' label layout is registered, so `moveOverlap` and `hideOverlap` take effect: `web/src/lib/echarts.ts`. (C2)

### Audit of 19 November 2026

- **RV76** Figures and exports: a withheld rate reads "withheld", never `0.00%`, in the Overview's tables and tooltip (`web/src/lib/format.ts::rateCell`); Methods' meeting-record figures are v6.0's (10,636 records, 717 without speeches, 690 closed); Language Plate 3 exports its own slice from the artefact it draws (`profileTable`); the PNG takes the captioned SVG's own height and long caption lines wrap (`web/src/lib/export.ts::wrapCaption`, `svgHeight`).
- **RV77** v6.0 meeting symbols (`S/PV.3336(Resumption2)`, `(PartII)`, `(communiqué)`) print as the record is titled and search the Digital Library by their base symbol: `web/src/lib/format.ts::meetingLabel`, `meetingBase`.
- **RV78** Accessibility: the two contrast findings that were open item 6 are fixed and both scans run without exclusions (Methods' "Automatic checks" in `--state-ok`, as DESIGN.md's Quarantine Rule asks, 5.5:1 on the zebra row; the Actors selected row's button in ink); the plain wheel scrolls the page over every chart, Ctrl with the wheel zooms (`web/src/lib/Chart.svelte`); *Cases over time*, *Naming a people, or not* and *The reading set, year by year* have tables, the first with each count linking to its concordance view; `TermMatrix`'s pattern id comes from `$props.id()`.
- **RV79** Robustness: the service worker writes its cache under `waitUntil` after answering, and a full cache no longer fails a good network response (`web/src/service-worker/index.ts::keep`); a page printed from the dark theme prints in light tokens, its charts redrawn light before the snapshot (`web/src/app.css`, `web/src/lib/theme.ts::printInLight`), and the figure contents band prints.
- **RV80** The gold sample's weighted figures follow the coding done so far: only frames whose whole draw is coded count, combined as the draws are, and only the units they drew are scored, so coding the probability frame first no longer under-weights the rare classes and a census stratum is not given zero variance while partly coded. Scaling each frame by its coded share was tried and rejected: a unit drawn by two frames counts as coded in both. `lib/gold_estimates.py::effective_inclusion`, `resolved_units`. (Branch `gold-prep`.)
- **RV81** The corrected shares are shares of the eligible occurrences inside the sampling design (a `true_positive` verdict with located evidence; no prompt examples), with the rectifier measured over the same units and no superpopulation variance added to a population mean; both weighted figures wait while any disagreement on the field is unadjudicated and say how many (`pending_adjudication`). `lib/gold_estimates.py::corrected_shares`, `pending_adjudication`. (Branch `gold-prep`.)
- **RV82** Step 13's frame table, third-frame section and manifest block name the frame actually drawn, so `model_strata`'s 269 rows are counted and the table adds up to the 469 candidate rows. `scripts/13_gold_sample.py::build_note`, `stratum_rows`. (Branch `gold-prep`.)
- **RV83** The coding page records the evidence sentence from `lib.text.sentence_bounds` (39 of the 458 packet passages had been cut at `Mr.` or the like), drops Excel's byte-order mark on restore, and links the meeting symbol to the UN Digital Library; `tools/coding_page.py --import` checks a coder's export with `lib.audit.merge` and, with `--write`, folds it into `annotations/genocide/annotations.csv` in one atomic write, refusing a silent revision without `--replace`. (Branch `gold-prep`.)
- **RV84** `DENSE_MEETINGS` kept as drawn (decided by FM on 19 November 2026): it is the `dense_meeting` coverage stratum, so changing it would redraw the 469-row sample, and on v6.0 the seven still hold 661 of 8,611 occurrences (7.7%) with five of them the five densest; S/PV.9540 (77) and S/PV.9651 (58) now outrank S/PV.3453 and S/PV.9069 (55 each), and no meeting before 1992 is among the twelve densest. The comment says so and no longer cites the missing `CORPUS.md` §8.6. `lib/gold_sample.py`. (Branch `gold-prep`.)
