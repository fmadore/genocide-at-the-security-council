---
target: Chronology
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-09-14T15-39-39Z
slug: web-src-routes-chronology-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence). Baseline before the Path B redesign.

## Design Health Score (Chronology)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | "Drawing…" with no skeleton; reading-set band absent from served HTML, pops in on hydration (~115px shift) |
| 2 | Match system / real world | 3 | 4.95x painted --state-bad red reads as an error; nav traffic lights read as health |
| 3 | User control and freedom | 3 | 5px chart symbol navigates off-page with no warning; no per-figure reset |
| 4 | Consistency and standards | 2 | Event kinds are a colour filter in figure 2, plain text in the table; heatmap ramp turns mustard in dark |
| 5 | Error prevention | 3 | Nothing stops nine identically coloured terms |
| 6 | Recognition rather than recall | 2 | Primary evidence gesture invisible; teal lines distinguished only by end labels |
| 7 | Flexibility and efficiency | 3 | URL state, bulk select, exports; no shortcuts |
| 8 | Aesthetic and minimalist | 2 | 10,644px tall; 37-control chip wall |
| 9 | Error recovery | 3 | Refusal states explain themselves; figure 6 rests empty |
| 10 | Help and documentation | 4 | Exemplary apparatus |
| Total | | 27/40 | Acceptable |

## Design specificity
Authored: the apparatus, the provenance label, the hatched "no rate" cell (Heatmap.svelte:97-106), the reference-dates table (full width, mono dates, resolving S/RES/955). Interchangeable: four native selects (+page.svelte:915,921,1087,1377), the black-pill chip toggle (:1569-1574) which cancels the register colour it carries, stock blue-link disclosure, red-up/green-down ratio colouring (:1632-1638), untouched ECharts dataZoom and legend defaults, the tan in-cell magnitude bar borrowing --reg-accountability (:1601-1605).
Width: content 1326px, body 935px, and Heatmap.svelte:212 caps the grid at 46rem (782px): the calendar uses 59% of the available width with dead paper on both sides.
Detector overlay: 59 hits, mostly line-length (~110-159 chars in table rows) and tiny-text; one em-dash-overuse (copy, out of scope). Existing ignore covers the chip side-tab.

## Priority issues
- [P1] Register colour makes terms indistinguishable: colourOf (:481-482) colours by register, so LEGAL draws nine identical teal lines. /impeccable colorize
- [P1] "Who says it" is grey fog: five categoricalNeutral lines under five translucent Wilson bands (:784-808). /impeccable colorize
- [P1] Mobile chrome eats the screen: masthead ~265px + band ~215px at 390px; reading-set radios detached from labels (ScopeControl.svelte:108-116). /impeccable adapt
- [P2] Heatmap double-penalised by its 46rem cap inside the margin layout. /impeccable layout
- [P2] The reading set is the only non-sticky band (ScopeControl.svelte:73-76) while the contents band sticks. /impeccable shape
- [P3] Controls read as a 2009 admin form: native selects, black pills, traffic-light provenance. /impeccable polish

## Persona red flags
Alex: no shortcuts; drill gesture is a 5px circle with no affordance. Sam: heatmap is one role=img with numbers behind a details; kind chips convey kind only by a colour the .on fill destroys; chip.small ~22px tall. Riley: no failure timeout on "Drawing…"; unknown series values dropped silently; 79-row table with no scroll container. Dr Okonkwo (1994/1995): 59 unsorted rows at the foot of a 10,000px page; kind chips filter the rail but not the table; 1994 and 1995 are two 20px stripes in an unlabelled grey field.

## Minor
.warn negative margin (:1577); pooled bar ends mid-column; fullscreen offered on the 260px chart but not on figures 3-4; footer p and .says use off-scale 46rem; contents band clips its last entry.

## Questions
1. If the reference-dates table is the most convincing object, why does no figure look like it? 2. Is the reading set a control or figure 1 own control wearing a masthead? 3. What if the calendar were the first figure at full bleed and the line charts its footnotes?
