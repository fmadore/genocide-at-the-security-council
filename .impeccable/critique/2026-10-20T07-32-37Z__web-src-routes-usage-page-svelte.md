---
target: usage page
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-10-20T07-32-37Z
slug: web-src-routes-usage-page-svelte
---
Method: dual-agent (A: design review · B: detector + browser evidence), 20 October 2026, dev server.

## Design Health Score (Usage)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | A matrix click lists its quotations ~470px below the fold; focus stays in the grid; nothing announced |
| 2 | Match system / real world | 3 | Raw `speaker_position` in copy (:859); lower-case raw values in the contested table |
| 3 | User control and freedom | 3 | Clear selection, URL round-trips, Back works; "Show more" adds 40 at a time |
| 4 | Consistency and standards | 2 | Plate 5 vs four Contents entries; retired hue ramp on the matrix; "amber" copy for a brick-red curve; four of five plates CSV-only |
| 5 | Error prevention | 3 | Withheld shares, the F1 ≥ 0.8 gate, counts-only rejects |
| 6 | Recognition rather than recall | 3 | 18 of 38 rotated column heads truncated, full name only in a hover title |
| 7 | Flexibility and efficiency | 2 | Excellent roving-tabindex grid; but 806 quotations = 20 clicks; no basket action on this page |
| 8 | Aesthetic and minimalist design | 2 | 1,574px of apparatus before Plate 1 at 1440; ~4 screens on a phone |
| 9 | Error recovery | 3 | Load failure offers Try again; every refusal names its reason |
| 10 | Help and documentation | 3 | Reading notes, codebook, links to Methods |
| **Total** | | **26/40** | **Acceptable** |

## Design specificity: authored for this product

Built from the study's own parts (provenance square, plate apparatus, sentence-labelled matrix cells, refusals that name their threshold). Where it goes wrong it is drift from DESIGN.md, not generic styling. Detector: CLI clean on 11 files (text-only path, weak evidence); in-page overlay found line-length on wide one-line notes (mostly false positives: nowrap row heads in scrollers), 11px axis titles in CasesOverTime (real, minor), cramped-padding on the segmented control (false positive).

## Priority issues

1. **[P1] The second-opinion statistics front-load the page.** `.second-opinion` (+page.svelte:511-672) sits inside the marking block; comments at :120-123 and :508-510 still say the published payload has no comparison, which stopped being true when Gemma was published. Fix: move it to its own section beside "Comparison with human coding"; keep a one-line pointer. `/impeccable layout`
2. **[P1] Plate numbers disagree with the Contents list.** Contents (:675-682) is hard-coded to four figures; the contested-passages plate is counted by the CSS counter, so "Who rejects the word" prints Plate 5. Fix: add the contested plate to the array when the comparison is computed; test that Contents count equals rendered figures. `/impeccable harden`
3. **[P1] Colour-layer drift, and copy that now misleads.** UsageMatrix.svelte:234 and :403 fill cells with `--reg-accountability` (DESIGN.md: a magnitude ramp is paper-to-ink, never a hue; theme.ts records this ramp's retirement). DiffusionChart.svelte:183-206 draws "asserts" in `--reg-contentious`. Reading notes at :735 and :968 still say "amber". Fix: ink ramp for the matrix, ink weight/dash for the curve; copy wording through Fred. `/impeccable polish`
4. **[P2] Four of five plates are CSV-only** against DESIGN.md's three exports. DiffusionChart is already SVG but no `chart` is passed (:964). `/impeccable harden`
5. **[P2] Drill-down gives no feedback at the point of action.** No polite status under the matrix; results render off-screen. Fix: a status line with an in-page link to the evidence heading; a "Show all". `/impeccable clarify`

## Persona red flags

- Alex: 806 quotations in steps of 40; no basket; truncated column heads; matrix click silently re-points the diffusion plate.
- Sam: selection never announced; matrix scroll container has no role/label unlike the other seven; "Who rejects" ink bands under 3:1 against each other (sr-only sentence covers it).
- Historian: cites "Plate 5" that the index lists as 4; no SVG/PNG of the matrix; reading note says amber, curve is red; model's first-person rationale labelled plainly "Rationale".

## Minor observations

- "1 further affiliations" (:792) and "5 speaker position" (:485-486) plurals.
- Five "Model-derived · experimental" plate links measure 204×21 at 390: below WCAG 2.2's 24px and not inline (Figure.svelte; site-wide).
- CasesOverTime paging legend: page counter 3.68:1 in dark (no `pageTextStyle`; same gap in theme.ts `legend()`); arrows not keyboard-reachable.
- Two stacked-bar series below 3:1 on white (2.56, 2.98).
- Matrix cell labels: position term lower-case after a full stop.
- "Top" button overlays the right column of wide tables at 1440.

## Questions

1. If the second opinion leaves the marking block, does the page still say whose reading this is before the first number?
2. Should "Who rejects the word" rank delegations while the rejects label is unmeasured?
3. Would the first matrix view be better as the 8-10 columns holding most of the mass?
