---
target: Overview
total_score: 26
max_score: 36
na_heuristics: 9
p0_count: 0
p1_count: 3
timestamp: 2026-09-19T13-55-00Z
slug: web-src-routes-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence),
isolated. Phase 6.6 of docs/DESIGN_ROADMAP.md, compared against the
14 September baseline taken before the Path B redesign.

## Design Health Score (Overview)
| # | Heuristic | Score | Δ | Key issue |
|---|---|---|---|---|
| 1 | Visibility of system status | 3 | +1 | The contents band lists the 2 plates but neither prose H2, so the page map and the page disagree |
| 2 | Match system / real world | 3 | = | "Colour groups related terms" names no group; the study's register vocabulary never appears |
| 3 | User control and freedom | 3 | = | A bar click routes to /concordance with no warning and no return path |
| 4 | Consistency and standards | 3 | = | Was: Courier Prime on numbers in one plate and the grotesk on the same numbers in its table. Fixed this pass |
| 5 | Error prevention | 3 | = | Exemplary refusals, undercut by one falsifiable label ("59 reference dates" over 40 marks) |
| 6 | Recognition rather than recall | 2 | = | Three register hues with no key; per-row scaling held across six rows; two peaks in one cell |
| 7 | Flexibility and efficiency | 2 | = | No keyboard route to the year drill; Plate 2 has no image export |
| 8 | Aesthetic and minimalist | 3 | = | Masthead 210px at 390px; the exit index repeats the sticky nav |
| 9 | Error recovery | n/a | = | No inputs and no fetch surface this page owns |
| 10 | Help and documentation | 4 | = | Question / reading / caveat / source per plate, CI-enforced |
| Total | | 26/36 | +1 | Acceptable |

## Design specificity — **partly grounded** (was: scaffold interchangeable)

Authored, and not liftable: the unit field (168 outlined squares, 4 filled,
countable at 48/40/20 per row and still 9.8px at 320px); the ochre `<mark>` on
*Genocide*, now present in the h1 and the standfirst where the baseline found it
missing; the central figure's encoding (bars `--ink-2`, line `--ink`, no hue, no
blue — measured); the plate apparatus with its `04_series.py → series/annual.json`
source line; Plate 2's caveat set as type ("Nothing here is added together").

Interchangeable: the seven-row "Where to go from here" index, which duplicates
all eight masthead sections already sticky in the same viewport; the two `.finding`
prose blocks, the second of which restates Plate 1's own reading note ~400px away;
the four-up tally, correctly un-tiled but still the shape of every analytics
overview — redeemed by the field above it, not by itself.

Measured share: roughly 1,100px of a 3,477px document at 1440×900 is
interchangeable material; ~1,900px of 5,752px at 390px.

## Evidence (Assessment B)

Detector over the target and over `web/src/lib`: `[]`, exit 0. See the caveat in
`.impeccable/audit/2026-09-19-web-src.md` — the `.svelte` path runs a subset of
the rules.

- Contrast: 32 pairs in light, **zero failures** (worst 5.33:1). Dark: **one
  failure**, `p.standfirst > mark` at **4.14:1** — the ochre's budget is written
  against `--ink` and this mark inherited `--ink-2`. **Fixed this pass**
  (`mark { color: var(--ink) }`); all three marks now measure 6.45:1 in dark.
- Horizontal overflow: none at 1440, 390 or 320.
- Targets: 87 under 24px, **zero flagged** — every one is inside a `p`, `li`,
  `td`, `th` or `figcaption`, and none sits within 24px of another target.
- Figure body vs `main`: both plates 1361/1361px at 1440, 342/342 at 390.

Claims verified: "59 reference dates" over **40 distinct tick positions**
CONFIRMED (cause: `eventTicks` buckets by year; 12 ticks carry multi-date titles
totalling 59). Courier Prime on `.summary`/`.scale` CONFIRMED. Register colour
with no key PARTIAL — "legal" does appear, but as a count of *event kinds*, so it
reads as a key and is not one. Masthead 210px/241px CONFIRMED exactly. Plate 1
CSV/SVG/PNG, Plate 2 CSV only CONFIRMED. `aria.decal` hatch serialising into the
SVG export CONFIRMED (79 pattern-filled paths).

**Refuted:** the claim that the year drill has no pointer affordance. A control
run with the proposed fix removed measured `cursor: pointer` on hover anyway —
ECharts' default was already correct, and the original `cursor: auto` reading was
taken from unhovered shapes. The rest of that finding stands: no hover emphasis,
no focus target, no keyboard route.

## Fixed in this pass
- The standfirst mark's dark-theme contrast (4.14:1 → 6.45:1).
- Courier Prime on the small multiples' percentages and year scale.
- The right axis's label override, which replaced the whole `axisLabel` to add a
  formatter and dropped the system's quiet ink and font family with it.

## Open, ranked
1. **P1** "59 reference dates" labels 40 marks. Copy, so the author's call.
2. **P1** Plate 2's three register hues decode to nothing: no swatch, no register
   column in its table, the words never on the page.
3. **P1** Plate 2 offers CSV but no SVG or PNG, against a product commitment that
   figures leave as CSV, SVG and PNG.
4. **P2** The masthead is 210px at 390px and 241px at 320px — 27% and 30% of the
   viewport, four of eight entries reading "Computed".
5. **P2** The corpus-level English-transcripts caveat sits ~3,400px below the
   2.47% it qualifies.
6. **P3** The `aria.decal` hatch ships inside downloaded SVGs.
