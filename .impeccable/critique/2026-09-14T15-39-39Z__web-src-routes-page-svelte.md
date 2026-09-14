---
target: Overview
total_score: 25
max_score: 36
na_heuristics: 9
p0_count: 0
p1_count: 3
timestamp: 2026-09-14T15-39-39Z
slug: web-src-routes-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence). Baseline before the Path B redesign.

## Design Health Score (Overview)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Figure 1 loads as the bare word "Drawing…" in a 400px void; no skeleton |
| 2 | Match system / real world | 3 | Nav sub-labels Mixed/Model in amber/red read as a health warning |
| 3 | User control and freedom | 3 | Bar click routes to /concordance with no warning and no return path |
| 4 | Consistency and standards | 3 | Figure 1 offers CSV/SVG/PNG, figure 2 only CSV, same-looking strip |
| 5 | Error prevention | 3 | Dual-axis crossing artefact never warned about |
| 6 | Recognition rather than recall | 2 | 59 reference dates live only in a title attribute; sparkline registers have no key |
| 7 | Flexibility and efficiency | 2 | No tabindex on the chart SVG; "select a year" is mouse-only; 14 tab stops before figure 1 |
| 8 | Aesthetic and minimalist | 3 | 345px apparatus column half empty; exit list repeats the sticky nav |
| 9 | Error recovery | n/a | No inputs, no fetch surface on this page |
| 10 | Help and documentation | 4 | Question / reading / caveat / source per figure, CI-enforced |
| Total | | 25/36 | Acceptable |

## Design specificity
Authored: radius 0, no shadow, headline numbers as a band of type between hairlines (+page.svelte:542-561), three non-mixing colour layers (app.css:20-34), the provenance link, the apparatus contract (Figure.svelte:35-60) with the source strip (241-247). Interchangeable: the scaffold (h1 + standfirst, four-across KPI row, contents band, stacked figures, seven-row exit list with a sliding Lucide arrow at +page.svelte:635-643). The site's one gesture, the <mark>, is absent from the Overview's h1 (:274), standfirst (:280) and stat label (:297); only the masthead marks it.
Detector: 1 finding site-wide (BasketDrawer.svelte:322 side-tab). Overlay on this page: 7 hits, of which mark gray-on-color is a false positive (14.49:1) and two tiny-text hits are 0x0 unrendered drawer text. Measured: .body 935px, .apparatus 357px of a 1394px main at 1425px (67.1% / 25.6%); no overflow at 390px; all five contrast pairs pass AA.

## Priority issues
- [P1] Apparatus column fixed at 21rem; at 1280px the plot is ~800px for 79 bars and 1994 is an unlabelled tick; lower third blank beside figure 1. Fix: make it yield (clamp column, higher fold, two-up band under the figure). /impeccable layout
- [P1] The <mark> is missing from the page that introduces the word (+page.svelte:274,280,297). /impeccable shape
- [P1] Figure 1 inverts its hierarchy: occurrences (the headline number) drawn at opacity 0.32, the derived share at full ink 2px (+page.svelte:147-170); dual-axis artefact unwarned. /impeccable clarify (copy part out of scope; the mark hierarchy is design)
- [P2] 59 reference ticks are mouse-only (title attr at :240). /impeccable harden
- [P2] Exit list duplicates the masthead in the end position (:455-522). /impeccable distill

## Persona red flags
Alex: 14 tab stops to figure 1; no keyboard route into the chart; SVG export inconsistent between figures. Sam: chart interaction unreachable; ticks title-only; register hues without a key; focus ring at the 3:1 floor. Ingrid (historian, 1994): the stat band answers her, then 1994 falls between labelled ticks and clicking it drops her on /concordance with no way back; no meeting symbol appears on the Overview.

## Minor
.figures resolves to six grid tracks with two at 0px; figure 2 note repeats its caveat verbatim; .onward-list 9rem label column wraps "Words in context"; contents band lists two entries; nothing handles forced-colors.

## Questions
1. Why is the Overview the only page where the word is never marked? 2. What if the apparatus were sticky to the figure rather than parallel to it? 3. What would the Overview be if it shipped only what a historian testing 1994 needs?
