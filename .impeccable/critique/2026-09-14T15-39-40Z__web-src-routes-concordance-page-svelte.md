---
target: Concordance and Reader
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-09-14T15-39-40Z
slug: web-src-routes-concordance-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence). Baseline before the Path B redesign. Covers Concordance and the Reader.

## Design Health Score (Concordance; Reader noted)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | First paint shows "0 of 0 lines / No passages match" while 6.2MB loads (:214 returns before loading=true). Reader +1 |
| 2 | Match system / real world | 2 | Scope band above results it does not filter; chips silently re-key |
| 3 | User control and freedom | 2 | Reader crumb links to bare /concordance (reader:400), discarding query, sort and position |
| 4 | Consistency and standards | 3 | BasketDrawer:443 paints delete in --reg-contentious; Speaker gets a combobox, Agenda a bare select. Reader -1: toolbar top 3.4rem vs 73px masthead |
| 5 | Error prevention | 3 | Regex guarded, impossible month degrades, basket empty confirmed |
| 6 | Recognition rather than recall | 3 | Reader register legend is the first note and scrolls away |
| 7 | Flexibility and efficiency | 1 | 150 tab stops before the first result (247 total); no shortcuts, no bulk basket |
| 8 | Aesthetic and minimalist | 2 | First 1440x900 viewport contains zero concordance lines; at 375px the first row is at y=4,415 |
| 9 | Error recovery | 3 | "Try again" on fetch failure; regex error via aria-describedby |
| 10 | Help and documentation | 4 | Excellent apparatus |
| Total | | 25/40 | Acceptable |

## Design specificity
Authored: a true KWIC axis with rtl left context (concordance/+page.svelte:1029-1044), two marks with two jobs (node wash, query underline :1059-1062), injection-proof highlight.ts, provenance carried into exports. Interchangeable: the Figure template applied verbatim to a chart, a 7,747-row concordance and a transcript (reader:790-795); the coloured provenance micro-labels in the masthead; the uppercase tracked .label for all apparatus.
Width: contexts show ~53 of 150 characters (149 chars into 343px); the Reader strands 357px inside its own body column (.text capped at --measure 578px, reader:912). Full width alone will not fix the Reader; columns must be re-proportioned.
Detector overlay: 148 hits, of which 78 gray-on-color on mark are one false positive repeated per row (14.49:1) and 60 cramped-padding are the segmented sort controls.

## Priority issues
- [P0] 150 tab stops before the first result. Fix: collapse ResultProfile in a details, roving tabindex on the year strip, "Skip to results" link. /impeccable harden
- [P1] First painted state asserts a false, blaming zero. Fix: initialise loading=true; distinguish not-yet from nothing-matched. /impeccable clarify (state logic; copy stays)
- [P1] Scope band governs nothing on this page while re-keying the chips. /impeccable clarify
- [P2] Both layouts waste width: run the KWIC full width with the apparatus folded above; Reader grid var(--measure) var(--measure-note). /impeccable layout
- [P2] Return path discards the query (reader:400). /impeccable polish

## Persona red flags
Alex: no / j k Enter; no multi-select to basket. Sam: 150 tab stops; .columns aria-hidden so rows announce four unnamed spans; legend scrolls away. Casey (mobile): first result at y=4,415; contexts start and end mid-word; scope radios misaligned (ScopeControl:99 legend float). Mei (40 passages): no return to filtered position; basket has no ordering or bulk note; no live-region on add.

## Minor
Zero-state header row collapses; scroll-margin-top 8rem vs 9rem disagreement (:808, :918); --masthead-h 3.4rem vs measured 73px; Reader apparatus sticky but taller than the viewport; scope band static while the "in set" tags stay; "Show 240 more" gives no remaining count.

## Questions
1. If the argument of the concordance is the vertical axis through the node, why does the node get 66px of 1,394? 2. Is a control that must explain why it does not apply still a control? 3. What should be on screen when Mei returns from her fortieth passage?
