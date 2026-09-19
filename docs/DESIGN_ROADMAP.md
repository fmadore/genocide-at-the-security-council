# Design roadmap: applying Impeccable to the dashboard

Written 14 September 2026. Scope: the SvelteKit site in `web/`. Copy is out of
scope throughout: no command below rewrites site text, and the word budgets in
`web/scripts/word-budget.mjs` stay as they are.

The roadmap has two standing requirements from the author, and every phase is
measured against them:

1. **Figures, tables and maps use the full page width.** The "How to read this"
   apparatus currently occupies a 21rem right margin beside every figure
   (`web/src/lib/Figure.svelte`, the `.split` grid), which caps every
   visualisation at roughly 55rem on an 82rem page.
2. **The identity stops reading as generic AI output.** The paper ground, the
   serif display over sans UI over mono citations, the uppercase tracked
   micro-labels (`.label`), the four-number stat row on the Overview, and the
   arrow-list "Where to go from here" are the recognisable tells. Impeccable's
   own craft floor names three of them outright: the hero-metric template, the
   kicker or eyebrow label, and monospace worn as a costume for "technical".

## 0. Where the project stands

| Fact | Evidence |
|---|---|
| No `PRODUCT.md`, no `DESIGN.md`, no `.impeccable/` config | `context.mjs` reported `NO_PRODUCT_MD` and `PRODUCT_INIT_REQUIRED` |
| The visual authority lives outside the repo | Claude Design project "The Verbatim Record", `https://claude.ai/design/p/abaf6e65-921e-493d-8cd3-c2082897bcce`; its six rules are enforced in `web/src/app.css` |
| Impeccable's scanner sees no code from the repo root | `context-signals.mjs` reports `hasCode: false` because the app lives under `web/`; every command must be given `--target web/src/...` or run from `web/` |
| Mechanical detector, first run over `web/src` | one hit: a 3px `border-inline-start` side-tab in `web/src/lib/BasketDrawer.svelte:322` |
| Existing quality gates | `npm run lint` (prettier, eslint, word budgets, figure provenance), `npm run check`, `npm run test` (vitest), `npm run test:e2e` (Playwright with axe; specs locate elements by accessible name) |
| Theme bridge | `web/src/lib/theme.ts` reads the CSS custom properties with `getComputedStyle` and hands ECharts literal colours; dark values are declared twice in `app.css` on purpose |
| Surfaces | Overview, Chronology, Words in context, Actors, Concordance, Reader, Usage, Semantic map, Methods; 20-odd figures share one `Figure.svelte` frame |
| Dev server | `.claude/launch.json` entry `dashboard`; Vite serves `http://localhost:5174/genocide-at-the-security-council` when 5173 is busy |

One blocker to clear before Phase 0: the `DesignSync` tool cannot read the
Claude Design project from this session. Either run `/design-login` once from
an interactive Claude Code session on this machine, or export the project's
`Direction - The Verbatim Record.dc.html`, `Audit.dc.html` and `handoff/` tree
into `docs/reference/design/` so Phase 0 can treat them as evidence.

## 1. Mode and the decision that shapes everything

Impeccable asks for the visitor's mode per surface, not per product:

- Overview, Chronology, Words in context, Actors, Usage, Semantic map: **Operate**
  (a researcher completes a comparison or a lookup; scanability and density win).
- Concordance and Reader: **Operate** with a strong **Read** component (passages
  are read at length; measure and typographic rhythm matter).
- Methods: **Read**.

The requirement to stop looking generic is an identity request, and Impeccable
draws a hard line here: *refinement preserves; redesign replaces; never split
the difference into polish on the discarded look.* So the roadmap carries one
decision point (Phase 2) with two possible paths:

- **Path A, refinement.** Keep the Verbatim Record world, remove every AI tell
  inside it, and relocate the apparatus. Cheaper, lower risk to the test suite,
  but the paper-and-serif world itself is part of what reads as generic.
- **Path B, replacement world (recommended).** Keep product truth, content,
  function, the `Figure.svelte` contract, the data registers and the test
  suite; replace the visual world through new-work's direction roll and write a
  new `DESIGN.md`. The old look becomes anti-reference.

The recommendation is Path B because the author's complaint names the identity,
not a component. Phases 0 and 1 are identical on both paths and produce the
evidence the decision needs; nothing visual changes before Phase 2 closes.

## 2. Phases

### Phase 0: Install the Impeccable context (half a day)

| Step | Command | Output | Exit criterion |
|---|---|---|---|
| 0.1 | `/impeccable init` | `PRODUCT.md` at the repo root | Users (social-science researchers checking a claim against the record), purpose, positioning (every number traceable to a script), evidence on hand (`data/`, `docs/CORPUS.md`, `docs/VALIDATION.md`), accessibility target (WCAG AA, axe in CI), platform `web`. No visual language recorded. |
| 0.2 | `/impeccable hooks on` | `.impeccable/config.json`, `.claude/settings.local.json` | Detector fires after each UI edit; `hook.quiet` left off during the redesign. |
| 0.3 | `/impeccable document` (scan mode, target `web/src`) | `DESIGN.md` + `.impeccable/design.json` describing the **incumbent** system | Tokens extracted from `app.css`; the six Verbatim Record rules recorded as Named Rules; the Claude Design files cited as the origin. On Path B this file is later replaced, but it is the record of what is being replaced. |
| 0.4 | `/impeccable doctor` | drift report | Clean, so later `CONTEXT_STALE` findings are real. |
| 0.5 | Live-mode setup (part of init) | `.impeccable/live/config.json` | `live` boots against the `dashboard` launch entry and the subpath base. |

### Phase 1: Baseline evaluation (one day, no edits)

| Step | Command | Target | Output |
|---|---|---|---|
| 1.1 | `/impeccable critique` | `web/src/routes/+page.svelte` (Overview) | Snapshot in `.impeccable/critique/`, heuristic scores, P0/P1 list |
| 1.2 | `/impeccable critique` | `web/src/routes/chronology/+page.svelte` | Same; this route carries the densest figure set and the heatmap |
| 1.3 | `/impeccable critique` | `web/src/routes/concordance/+page.svelte` and `reader/[meeting]` | Same; the Read-heavy path |
| 1.4 | `/impeccable audit` | `web/src` | Scores 0-4 on accessibility, performance, theming, responsive, integrity |
| 1.5 | Mechanical scan, all scopes | `node <impeccable>/scripts/detect.mjs --json web/src` | Baseline finding list (currently one hit) |

Each critique runs its two assessments as isolated subagents, as the playbook
requires; a degraded single-context run must be labelled. The critiques must
record, explicitly, which elements make the design **non-specific**: this is
the evidence Phase 2 argues from. Expected findings, to be confirmed rather
than assumed:

- the marginal apparatus starves the figure of width and leaves blank paper
  under short notes (the `--measure-note` comment in `app.css` already admits
  this trade);
- the stat row on the Overview is the hero-metric template;
- eleven uppercase tracked labels on one screen (`.label` in figure heads,
  table headers, the contents band, the reading-set control);
- the `SOURCE` line and every citation in mono, where only `S/PV.3137` earns it;
- the arrow list under "Where to go from here";
- the identical figure rhythm on every route, which is consistency but also
  the reason the pages are interchangeable;
- audit: the global `0.01ms` reduced-motion kill in `app.css`, which the audit
  playbook flags as destroying useful feedback; the ECharts and MapLibre bundle
  cost on routes that never draw a map.

### Phase 2: Direction (one day)

Run new-work's world workshop, using `PRODUCT.md` and the Phase 1 evidence:

1. Name the mechanism (a versioned script behind every number, a `<mark>` that is
   the interface) and the audience's cultural home: the printed verbatim record
   `S/PV.*`, the UN document grid, the critical edition, the statistical atlas,
   corpus-linguistics concordance software, the parliamentary Hansard, the
   Official Records typography of the 1950s to 1990s.
2. `node <impeccable>/scripts/concept-seed.mjs --scope direction --mode operate`
   deals the direction and its challengers; present them on the decision page
   with the canon exit. The Verbatim Record is one candidate at most, because it
   is the brief's literal reading and therefore in the rut.
3. Lock one direction. Record the direction contract, then replace `DESIGN.md`
   (Path B) or annotate it (Path A). Either way, `PRODUCT.md` is untouched.

Non-negotiables carried into any direction:

- one accent for interaction, never for a datum; the register ramp `--reg-*`
  stays a separate layer (this is an analytical necessity, not a style);
- light and dark both first-class, because `theme.ts` feeds ECharts from the
  computed tokens;
- the citation stays mono, and the `<mark>` stays the one gesture for a found
  term (both are product mechanism, not decoration);
- print stylesheet preserved: figures leave the site.

### Phase 3: Structure, full width first (two days)

This phase delivers requirement 1 regardless of the direction chosen, and it
is done before any identity work so the identity is built on the final
geometry.

| Step | Command | Target | What changes |
|---|---|---|---|
| 3.1 | `/impeccable layout` | `web/src/lib/Figure.svelte` | `.split` becomes a single column at every width. The figure body spans the page. The reading and caveat notes move to the **foot of the figure**, set as two side-by-side columns under the chart (a critical edition's notes at the foot of the page, not in the margin), above the source strip. Full-screen mode inherits the same order. |
| 3.2 | `/impeccable layout` | `web/src/lib/Chart.svelte`, `Heatmap.svelte`, `SmallMultiples.svelte`, `DotPlot.svelte`, `TermMatrix.svelte`, `UsageMatrix.svelte`, `CountryMap.svelte`, `DiffusionChart.svelte` | Each visual resizes to the new container; ECharts `resize()` on the fullscreen callback is re-verified; heatmap cell size and small-multiple row height are re-derived for ~80rem instead of ~55rem. |
| 3.3 | `/impeccable layout` | every `<table>` under a `.data-table` disclosure, the concordance list, the speaker tables on Actors | Tables take the full width; numeric columns right-aligned with tabular numerals (already tokenised); the concordance keyword-in-context line gets the room it has been missing. |
| 3.4 | dataviz pass (the `dataviz` skill, inside the same layout session) | `Chart.svelte`, the change-point figure | What the note used to say is drawn on the chart where possible: the 1978 split as a labelled rule, the axis titles in place, the peak year annotated. The prose note then only says what a mark cannot. Copy inside the notes is not edited; it may simply become shorter because a sentence is now a mark, and any such removal is listed for the author to confirm. |
| 3.5 | `/impeccable adapt` | the same components at 390px and 768px | The foot notes stack to one column; controls bars wrap deliberately; the 62rem breakpoint is retired or renamed to what it now means. |
| 3.6 | `/impeccable distill` | `.controls` bars on Chronology and Actors | The bar mixes three control idioms; reduce to one vocabulary without losing a control. |

Exit criteria for the phase: every figure body's rendered width equals the
`main` content width at 1440px; no horizontal scroll at 390px; `npm run test:e2e`
green, with any spec that located "How to read this" by position updated to the
new position, never removed.

### Phase 4: Identity execution (three to four days, Path B; two days, Path A)

Ordered so each command works on the previous one's result.

| Step | Command | Target | Intent |
|---|---|---|---|
| 4.1 | `/impeccable typeset` | `web/src/app.css`, `+layout.svelte` | The direction's faces and scale. Operate surfaces get a fixed rem scale and one or two families with real jobs; the `.label` eyebrow is deleted as a pattern and its jobs are given to weight, size, and position. Self-hosted, subset, `font-display` chosen deliberately. |
| 4.2 | `/impeccable colorize` | `app.css`, `theme.ts` | Ground, ink and interaction colours from the direction; the register ramp re-derived in OKLCH for both themes with contrast verified on both grounds; ECharts theme re-read from the tokens. |
| 4.3 | `/impeccable bolder` | `web/src/routes/+page.svelte`, the opening viewport | Replace the stat row with the direction's own way of stating four numbers (typeset in running text, a single large figure, or a marginal tally, whichever the world owns). The numbers and their captions are copy and stay verbatim. |
| 4.4 | `/impeccable layout` | `+layout.svelte` masthead, contents band, footer, "Where to go from here" | Navigation and wayfinding in the new world; the arrow list becomes whatever the world's index looks like. |
| 4.5 | `/impeccable delight` | the `<mark>` and the basket | One authored moment: the found word is the site's signature and deserves its one distinctive behaviour (selection, basket add, reader arrival). Nothing else animates for decoration. |
| 4.6 | `/impeccable animate` | `Figure.svelte` fullscreen, `BasketDrawer.svelte`, the disclosure chevron | Reduced-motion gets an intentional alternative rather than the global kill; durations inside 150-250ms. |
| 4.7 | `/impeccable live` | any route, in the browser | Used between steps for the choices a static pass cannot settle (note density under a figure, the masthead at 1024px). |

Every step in this phase ends with the hook's detector findings triaged in the
same session: fix, or record a narrow `ignore-value` with a reason.

### Phase 5: Hardening (one day)

| Step | Command | Target | Cases |
|---|---|---|---|
| 5.1 | `/impeccable harden` | `Actors`, `Concordance`, `Reader`, `ScopeControl.svelte` | 60-character delegation names, a scope with zero matches, a speaker with no country, a meeting with 400 speeches, offline with the service worker serving stale data, 200% zoom, forced-colours mode |
| 5.2 | `/impeccable optimize` | `web/src/routes/semantic`, `CountryMap.svelte`, the ECharts import surface | Lazy-load MapLibre and the semantic map; confirm ECharts tree-shaking; measure LCP on Overview and INP on the concordance filter before and after, using the same Playwright profile as `web/scripts/profile-payload.mjs` |
| 5.3 | `/impeccable audit` | `web/src` | Re-score the five dimensions against Phase 1 |

### Phase 6: Validation and record (one day)

1. `/impeccable polish` on each of the nine routes, reading the Phase 1
   critique snapshots as backlog, desktop and mobile in one batched round each.
2. The finish reviewer subagent (`impeccable-finish-reviewer`) over the shipped
   build against the direction contract; fix its material findings in one batch.
3. Mechanical detector over `web/src` once, all scopes: zero unexplained hits.
4. Repository gates, in this order: `npm run lint`, `npm run check`,
   `npm run test`, `npm run build`, `npm run test:e2e`, `npm run test:e2e:sw`.
   The axe checks in the e2e specs are the accessibility regression floor.
5. Manual checks the tools do not cover: print preview of two figures; dark
   theme on every route; keyboard path through a figure's fullscreen mode and
   the basket; a deep link to a figure anchor landing under the sticky bands.
6. Re-run `/impeccable critique` on the three Phase 1 targets and compare the
   scores and the design-specificity verdict; the verdict must have moved from
   "could be any product" to grounded.
7. `/impeccable document` to refresh `DESIGN.md` and the sidecar from the
   shipped code (the documenter subagent), and `/impeccable doctor` for drift.
8. Record the run in `docs/VALIDATION.md`: what changed, what was measured,
   what was accepted as an exception and why. Add the new DESIGN.md origin to
   the design memory so the Claude Design project is no longer cited as the
   live authority.

## 3. Sequencing and effort

```
Phase 0 (setup)            ─┐
Phase 1 (baseline)          ├─ no visual edits, ~1.5 days
Phase 2 (direction)        ─┘
Phase 3 (full width)        ── first shippable milestone, ~2 days
Phase 4 (identity)          ── second milestone, 2-4 days depending on path
Phase 5 (hardening)         ── 1 day
Phase 6 (validation)        ── 1 day, gates the deploy
```

Phase 3 is deliberately shippable on its own. If the direction round stalls,
the full-width figures still land, on the incumbent identity, without the
split-the-difference trap because nothing in Phase 3 restyles anything.

Work on a branch per phase (`design/phase-3-full-width`, then
`design/phase-4-identity`), one PR each, so the deploy workflow in
`.github/workflows/deploy.yml` never publishes a half-migrated identity.

## 4. Out of scope, stated so it stays out

- Copy: no `clarify`, no rewording of figure questions, notes, captions,
  Methods, or navigation blurbs. Where Phase 3.4 turns a sentence into a mark,
  the sentence's removal is proposed to the author, not made.
- The word budgets, provenance labels and the provenance colour semantics
  (computed, mixed, model) are analytical claims and are not restyled into
  something less legible.
- The data pipeline, the JSON contract in `web/src/lib/data.ts`, and the
  service-worker policy.
- `overdrive`: an Operate surface for researchers has no use for it.

## 5. Risks

| Risk | Mitigation |
|---|---|
| e2e specs locate the apparatus and controls by accessible name and position | Run `test:e2e` after every Phase 3 step; update locators, never delete assertions |
| ECharts reads colours once per theme; a token rename breaks the bridge silently | `theme.ts` fallbacks are updated with the tokens; a vitest case asserts every `--reg-*` resolves |
| A replacement world drifts into decoration on an Operate surface | The Phase 2 contract carries the four non-negotiables; the finish reviewer audits against it |
| The hook's detector produces false positives on the register ramp | Narrow `ignore-value` entries with reasons, never `ignore-rule` |
| DesignSync stays unauthenticated | Export the Claude Design files into `docs/reference/design/` before Phase 0.3 |

## 6. Log

### 14 September 2026: Phases 0 and 1 done, Phase 2 opened

- Phase 0: `PRODUCT.md` written from the author interview; `DESIGN.md` and
  `.impeccable/design.json` record the incumbent (marked as the system being
  replaced); hook config enabled but the automatic hook could not install from
  the plugin cache, so the detector runs manually after each UI edit; live-mode
  config written (no CSP); doctor clean.
- Phase 1 (all on Opus): critiques persisted under `.impeccable/critique/`,
  audit under `.impeccable/audit/`. Scores: Overview 25/36, Chronology 27/40,
  Concordance and Reader 25/40, audit 15/20. One detector finding site-wide.
- Verdict shared by all three reviewers: the apparatus contract, the three
  colour layers, the mark, the KWIC axis and the reference-dates table are
  authored; the scaffold, the controls, the chart defaults, the provenance
  micro-labels and the uniform Figure template are the generic layer. Width is
  wasted three ways: the fixed 21rem margin, the heatmap's own 46rem cap, and
  the Reader's 34rem text inside a 935px column.
- Author decisions: replace the world but keep the apparatus contract, the
  colour layers and the mark as product mechanism; notes go under the figure in
  two columns; the Concordance tab-stop P0, the register-colour lines and the
  false zero on first paint join Phase 3.
- Phase 2: direction seed key `426cd46f` (operate mode) assigned grounded
  candidate 6, "The Programme Grid" (1960s-70s international-organisation
  identity programmes: Swiss grid, one grotesk, flat ink, unit counting).
  Pick card: "The Concordancer". Lexicon challenger competitive; five others
  declined with their disciplines donated as raises. Build path is code-led:
  no image generation is available in this harness.

### 14 September 2026, later: Phases 3 and 4 merged into one build

- The author delegated the direction with the steer "nothing that feels like
  Claude output". Chosen from the evidence: The Programme Grid. The
  Concordancer is monospace-as-costume, the Lexicon is cream and serif, the
  category standard is generic by definition. The contract is the first child
  of the body in `web/src/app.html`, so it survives the build.
- Because a replacement world cannot be split from the frame it lives in,
  Phase 3 (full-width plates, notes beneath, Reader re-proportioned, heatmap
  cap removed) and Phase 4 (tokens, type, controls, masthead, Overview) were
  built together on branch `design/programme-grid`.
- Tokens: white ground, ink `#111111`, one grotesk (Hanken Grotesk, OFL),
  Courier Prime for the citation only, 16px root with a fixed rem scale, 3px
  rules for page and plate, hairlines elsewhere, twelve-column `.grid`,
  page at 90rem. The register hues and state colours are unchanged. The old
  font files are removed.
- New: `UnitField.svelte` counts the corpus in unit squares on the Overview;
  plates are numbered by a CSS counter that the contents band shares.
- Functional fixes in the same build, per the author's Phase 3 scope: the
  Concordance tab-stop P0 and the false zero on first paint; the register-only
  line colour on Chronology (lightness steps and dashes within a register).

### 14 September 2026, evening: Phase 6 validation

- Finish reviewer (Opus) on the code-led build: first disposition `fix` with
  eight material items (the mark was in the blue family and shared with the
  selection; the plate footnote in the typewriter face; Plate 1 below the
  fold; the unit field a hatch at 390px; the semantic map's palette and
  extent; numerals on the exit index; DESIGN.md stale; no dark capture).
  Second pass found two regressions (the zoom rail read as an ink bar; the
  amber calendar ramp competed with the ochre mark). All resolved; final
  disposition `ship`, scoped to the scored fixes and the captured pages.
- Gates at the end: `npm run lint` 0, `npm run check` 0 errors, 553 unit
  tests, Playwright e2e 46/46 with axe, detector over `web/src` empty.
- The sequential ramp is now paper-to-ink; `--mark` is ochre in both themes;
  `::selection` is reversed out; the semantic map derives its fills from the
  tokens through `categoricalData()`.
- Captures for the review live under `.impeccable/review/`.
- Still open, deliberately: the Reader's return path discards the query
  (P2); MapLibre loads at mount on Actors (P2); the Concordance scope band
  governs nothing on that page (a product decision); the exit index keeps
  its seven destinations because copy is frozen.

### 19 September 2026: Phase 5 done, Phase 6 closed out

- **Phase 5.1, harden.** The roadmap's seven cases were run against real data
  rather than invented data. The corpus's longest delegation name is 242
  characters and its longest speaker role 239, well past the 60 the roadmap
  assumed; both wrap without overflow, so nothing needed doing there. The
  largest real meeting is 179 speeches, not 400, and the Reader draws it clean
  at 320px and at 1440px. Zero-match scopes and a missing meeting already had
  empty and error states with a recovery.
  Three cases did need work, and got it: **320px reflow** (three routes put a
  horizontal scrollbar on the document; all nine are clean now), **forced
  colours** (every state drawn as an inset shadow was invisible; each now has a
  twin, and `DESIGN.md` carries the Two Colours Rule and the Shadow Has A Twin
  Rule), and **a dead connection** (the browser's "Failed to fetch" reached the
  reader on three views; there is now one sentence for it, shared with the
  semantic map's own fetch).
- **Phase 5.2, optimize.** MapLibre now arrives with its plate instead of at
  mount: /actors falls from 600.5 kB to 201.2 kB before the map is reached, and
  from 39 requests to 32. ECharts was already tree-shaken and split per route;
  it is confirmed, not changed. Overview LCP and the concordance filter are
  unchanged, which is the expected answer — nothing on those paths was touched.
  One e2e spec now scrolls to the map before asserting on a blocked basemap;
  no assertion was removed.
- **Phase 5.3, audit.** 19/20, up from 15/20 on 14 September, at
  `.impeccable/audit/2026-09-19-web-src.md`. Accessibility holds at 3, but for
  a different reason: the 24px target violations are gone and what holds it
  there now is that a mark's register is told only by the hue of its underline.
  The other four dimensions each gain a point. Detector empty.
- **Phase 6.7, document and doctor.** `DESIGN.md` and the sidecar were
  refreshed rather than regenerated: two named rules, one breakpoint (30rem),
  the segmented group's narrow and shrinking behaviour, and one do and one
  don't. Doctor reports one `mention`: `.impeccable/config.json` records no
  `buildPath`. This project settled that in words on 14 September (code-led, no
  image generation in this harness) and the key is simply unwritten; writing
  `"buildPath": "code"` would silence it.
- **Phase 6.6, the re-run critiques.** Three isolated dual-agent passes
  (Overview, Chronology, Concordance + Reader) under `.impeccable/critique/`.
  The design-specificity verdict moved from "the scaffold is interchangeable" to
  **partly grounded** on all three, which is the movement this phase existed to
  test. Scores: Overview 25/36 → 26/36, Chronology 27/40 → 28/40, Concordance
  25/40 → **22/40**. The Concordance fell, and the reason is worth keeping: the
  redesign delivered width and identity, and that route's losses are in control
  surface and browser history, which no phase of this roadmap touched.
  The critiques found defects the Phase 5.3 audit did not, and six were repaired
  in the same session: a false published number on every meeting page (the
  corpus's `Unknown` language sentinel read as a foreign language), two contrast
  failures under their floors, ECharts' stock palette serialised invisibly into
  every Chronology SVG download, two axis overrides that dropped the design
  system's colour and font, a deep link landing behind a 400px sticky toolbar at
  phone width, and image downloads offered for a figure that does not exist. One
  claim was refuted by a control run and nothing was changed for it.
  Five findings are left open and ranked in the snapshots; the heaviest is the
  calendar heatmap rendering its labels at 2.52 CSS px at 390px.
- **A caveat that applies backwards.** The detector routes any file outside
  `.html`/`.htm` to a text-only path running a subset of its rules: identical
  content scanned as `.svelte` gives one finding and as `.html` gives four. Every
  "detector clean" line in this log — Phase 1's, 14 September's and Phase 5.3's —
  should be read as "no findings from the rules that survive the text path",
  not as a clean markup audit.
- **Phase 6.8.** Recorded in `docs/VALIDATION.md` under "Design hardening and
  payload, 19 September 2026".

### 19 September 2026, later: the calendar

Working the critique backlog rather than the roadmap. The P0 and one P1, both in
the Chronology's month-by-year grid, on branch `design/phase-5-hardening`.

- The grid is built to the width it is given rather than scaled into it, so the
  drawn scale stays at 1 and the labels are stated at the 12px the system sets.
  At 390px they render at 12.1px against 2.5px before, and the cell goes from
  26.9 × 4.5 to 23.3 × 16.2. Measured at 320, 390, 768 and 1440.
- The hatch stood for two different refusals and the key counted one of them:
  475 months drawn, 387 withheld, **86 with no sitting at all**. A month with no
  sitting now carries a mark at its centre and the key names both. The docblock
  in `$lib/heatmap.ts` claiming the state was unreachable is corrected — that
  claim is why the figure had one hatch for two facts.
- Gates green, 46/46 e2e. One spec failed once in a full run and passed both in
  isolation and on re-run, in a file this change does not touch.

### 19 September 2026, later still: the flagship plate's evidence

- Every plotted value in the word-list chart's table is now a link to the
  passages behind it — 316 of them at the default terms, the same destination
  the chart's own click reaches, inert while the disclosure is closed. The grid,
  the pooled months and the split already did this; the plate a reader arrives
  at did not.
- Attempting to guard it turned up a larger gap: the Chronology answered 500
  under the e2e fixture set, so none of the 46 journeys touched the route.

### 19 September 2026: the untested route, and why it was failing

- The three absent fixtures (`series/quarterly.json`, `series/monthly.json`,
  `series/breakdowns.json`) are committed. They carry all three states the
  calendar draws — 25 months divided by, 8 withheld, 3 with no sitting — so the
  encoding repaired earlier today is now held in place by a test.
- Writing them found that the missing files were not the whole reason for the
  500. The page opens on four named terms and the fixture lexicon carries one;
  the chart filtered its selection on whether the artefact carries a measure and
  the table did not, so an absent term reached `allMeasures[name][unit]` on
  undefined and took the route down entirely. The guard is derived once now and
  both readers share it. A release whose lexicon drops one of the four opening
  terms loses a line rather than a page.
- Five journeys cover the route: six plates and axe, a missing term dropped
  rather than fatal, the plotted-value links reached by keyboard, the hatch
  matching what the key counts, and no calendar label under 10 CSS px at 390px.
  46 journeys to 51.
- This is the finding to carry forward: the page with no coverage is the page
  that accumulated a P0 and four P1s. Coverage was the cause, not the symptom.

### Where this leaves the roadmap

Phases 0 to 6 are done. What the last pass makes clear is that the roadmap's own
frame — width, then identity, then hardening — never had a phase for the control
surfaces, and that is where the one route that lost points lost them. A next
round would start from the three critique snapshots rather than from this
document, and its first three items are the heatmap at phone width, the register
ladder's 1.56:1 lines, and the concordance's nine invisible filters.
