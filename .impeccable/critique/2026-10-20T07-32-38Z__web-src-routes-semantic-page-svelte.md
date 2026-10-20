---
target: semantic map page
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-10-20T07-32-38Z
slug: web-src-routes-semantic-page-svelte
---
Method: dual-agent (A: design review · B: detector + browser evidence), 20 October 2026, dev server, map rebuilt the same day.

## Design Health Score (Semantic map)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Selecting from the table inserts the panel 432px above the focused row, pushing it off-screen; nothing announced; no hover feedback |
| 2 | Match system / real world | 2 | Speaks in internal IDs (SC07192-01-008); no S/PV symbol, speaker or date |
| 3 | User control and freedom | 2 | `replaceState` (:183): Back does not undo a filter; no zoom reset; wheel captured by the map |
| 4 | Consistency and standards | 2 | Round swatches, two label styles, CSV only, no full screen, IDs not in mono |
| 5 | Error prevention | 3 | Empty-filter message suggests a fix; off-filter selection flagged; colours fixed under filters |
| 6 | Recognition rather than recall | 2 | A point has no identity until clicked; 76% of points share the "Other" grey |
| 7 | Flexibility and efficiency | 2 | URL state good; no jump to ID or page: 207 pages by Previous/Next |
| 8 | Aesthetic and minimalist design | 3 | Restrained; diagnostic paragraph runs 1,361px wide |
| 9 | Error recovery | 3 | Errors carry an action |
| 10 | Help and documentation | 3 | Standfirst and apparatus; axes never explained on screen |
| **Total** | | **24/40** | **Acceptable** |

## Design specificity: frame specific, instrument generic

The plate apparatus, provenance square and printed check results belong to this product. The plot inside is a stock ECharts scatter with round legend dots and a top-8-plus-Other scheme, paged 20 rows at a time. Detector: CLI clean on 5 files (text-only path); overlay found line-length on two page paragraphs (:326, :355, real: outside `--measure`) and three site-wide footer paragraphs; nothing at 390.

## Priority issues

1. **[P1] The page invites over-reading the map; its strongest caveat is hidden.** Reading note (:269) says nearby points suggest similar wording; the page's own check (:355-362) says the flat map lost 68.1% of close neighbours, in small grey type at full width. The axis sentence exists only in the CSV export; projection method and model revision are not on screen. Fix: lead "What it does not show" with the diagnostic; surface the export's axis sentence (author's call); add projection and revision to the source strip. `/impeccable clarify`
2. **[P1] Keyboard path breaks.** Tab from either SearchSelect combobox drops focus to BODY: the list opens on focus (SearchSelect.svelte:76), Chrome makes the scrollable `ul` (max-height 16rem, overflow auto) a tab stop, `onblur` unmounts it. Shared with Concordance and ResultProfile. Selection from the table is not announced and the panel renders above the focused row. Fix: keep the list out of the tab order; announce selection through the status region and keep or move focus deliberately. `/impeccable harden`
3. **[P1] Phone: the map traps scrolling; points unusable by touch.** `inside` dataZoom on both axes (:157-159) takes wheel and swipe (scrollY unchanged after a 300px swipe at 390 and 320); 5px points, no tap tolerance; table needs sideways scroll (38rem min-width) with a clipped caption; map.json 8.9 MB raw / 1.9 MB gzip for a default view of 2.5% of its points. Fix: Ctrl-wheel zoom and explicit zoom buttons; stacked table below 48rem; split map.json by corpus set. `/impeccable adapt`
4. **[P2] Colour says little by default and uses hue where ink belongs.** 76% "Other" under affiliation; decades (ordinal) get categorical hues and the 1950s fall into Other; light-mode point contrast 1.79-3.58 for most groups at 0.65 opacity; circle swatches with an off-scale 0.4rem gap. Fix: decades as a paper-to-ink ramp; highlight a filtered group in ink; square swatches. `/impeccable polish`
5. **[P2] The selected-speech panel cannot be cited; plate departs from the system.** No symbol, speaker, date or excerpt; cosine to 3 decimals; no basket; prose at 1,361px; CSV only; no full screen; reading notes after a 1,200px table. `/impeccable layout`

## Persona red flags

- Alex: no jump to ID/page; wheel zooms instead of scrolling; Back does not undo; "Full corpus" draws 167,600 points unwarned.
- Sam: two Tab stops land on BODY; selection silent; ECharts' nested role=img label of raw coordinates (probably pruned).
- Casey: swipe on the map does not scroll; 5px points; legend 108-166px tall; map more than a screen down; 1.9 MB.
- Historian: nothing citable on the page; revision and projection invisible; "nearby" note more confident than the 68.1% figure.

## Minor observations

- H1 "Similar speeches" vs nav, title and plate "Semantic map".
- `th, td { padding: 0.5rem }` literal instead of `--sp-2`.
- The data-zoom slider is unlabelled and x-only.
- Both reviewers' browser tabs hung after theme/viewport changes on this page while the pane was hidden; worth one manual check.

## Questions

1. Should the related-speech list (exact) be the evidence and the map (lossy) the secondary view?
2. What does a reader cite from this page? If a meeting symbol and a passage, the panel should lead with both.
3. Does colouring by one of 708 affiliations answer a question, or should a chosen group be drawn in ink against the rest?
