---
target: Concordance and Reader
total_score: 22
max_score: 40
na_heuristics:
p0_count: 2
p1_count: 2
timestamp: 2026-09-19T13-55-00Z
slug: web-src-routes-concordance-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence),
isolated. Phase 6.6 of docs/DESIGN_ROADMAP.md, compared against the
14 September baseline. Covers the Concordance (scored) and the Reader (noted).

**Method note, stated because it affects one reading.** The language defect in
claim 1 was found, confirmed against the corpus data and fixed by the parent
session *while* Assessment B was measuring the live page. B therefore measured
the repaired page, reported the claim REFUTED, and read the fix's own comment as
the reviewer having quoted a comment as output. The defect was real: all 9,634
speeches sampled across 526 meetings carry `language: "Unknown"`, and the source
before the fix filtered on `s.language && s.language.toLowerCase() !== 'english'`.
B's other seven claims were unaffected.

## Design Health Score (Concordance; Reader noted)
| # | Heuristic | C | R | Δ (C) | Key issue |
|---|---|---|---|---|---|
| 1 | Visibility of system status | 2 | 1 | = | The reader's own search term is invisible on 14 of 60 rendered rows |
| 2 | Match system / real world | 3 | 2 | +1 | "Search looks within this displayed passage" is not what the search does |
| 3 | User control and freedom | 1 | 1 | −1 | Back never undoes a filter: `replaceState` for nine narrowings, `goto` for the reading set |
| 4 | Consistency and standards | 3 | 3 | = | Speaker gets a combobox; Agenda item's 252 options get a bare select |
| 5 | Error prevention | 3 | 3 | = | Regex opt-in, caught and explained; "Reset filters" destroys nine narrowings with no undo |
| 6 | Recognition rather than recall | 1 | 2 | −2 | Only `spv` gets a removable chip; the other eight narrowings exist only as scattered select values |
| 7 | Flexibility and efficiency | 2 | 2 | +1 | 47–49 tab stops before the first result; the skip link is itself stop 14–16 |
| 8 | Aesthetic and minimalist | 1 | 1 | −1 | First KWIC row at y=1208 (1440) and y=2263 (390) |
| 9 | Error recovery | 3 | 3 | = | `loading` starts true so a false zero never blames the reader's filters |
| 10 | Help and documentation | 3 | 2 | −1 | The best apparatus on the site, wrong on the one number it exists to give |
| Total | | 22/40 | 20/40 | −3 | Acceptable |

The score fell. Phase 3 and 4 delivered the width and the identity; this route's
losses are in control surface and history, which neither phase touched, and two
of them (history, filter legibility) the baseline scored more generously than the
measurements now support.

## Design specificity — **partly grounded**

Authored: the KWIC axis itself — `--kwic: 9rem minmax(0,1fr) minmax(4rem,auto)
minmax(0,1fr)` declared once and read by the header and every row, with
`direction: rtl` on the left context so it clips at its far end and an inner
`.ltr` span restores logical order. Measured at 1440: 144 | 550 | 64 | 550px. A
true node axis, not a data table. Paired with the reversed-string left sort,
recurring grammatical frames stack as shapes in the column. Two marks with two
jobs. The Reader's roll including the silent delegations, with the reason stated.

Interchangeable: the filter bar — six labelled native selects, two number inputs
and a reset button in a wrapping flex row; the expanded key-value `<dl>`; the
profile folded into a disclosure, a faceted sidebar with the sidebar removed.

The structural gap: DESIGN.md has no long-form reading role. The Reader is the
only sustained-reading surface on the site and the system hands it `body` at the
prose measure; the file quietly overrides `line-height` to 1.68 because 1.5 was
unreadable at length. That override is correct and undocumented.

## Evidence (Assessment B)

Detector on both files: `[]`, exit 0 — and B's self-test established that a
scratch `.svelte` file stuffed with `width:100vw`, `outline:none`,
`font-size:10px`, a bare `onclick` div and an `img` with no alt also returns
`[]`. The parent session confirmed and quantified this: identical content scanned
as `.svelte` yields 1 finding, as `.html` yields 4. Treat "detector clean" here
as a non-result, not a clean bill.

Measured and CONFIRMED:

- **KWIC context.** The page promises 150 characters twice — the standfirst and
  the apparatus, both interpolating `data.index.meta.width`. Drawn: **87–90**
  characters per side at 1440 (59% of what is loaded) and **20** at 390 (13%).
  The apparatus also says "Search looks within this displayed passage"; the
  search runs over the full loaded context, so on a search for "Rwanda"
  (1,731 of 7,747 lines) **14 of 60 rendered rows have every hit clipped outside
  the visible box**. The copy is falsified twice over by one measurement.
- **The query-hit rule.** `--blue-flag` measured **3.14:1** on paper and
  **2.80:1** on the zebra row — under the 3:1 non-text floor, on the only code
  the reader's own search term carries. It was also the focus-ring token, so one
  colour said two things on the same row. **Fixed this pass** (`--blue`, 7.0:1;
  re-measured as `rgb(26,86,176)`).
- **History.** Three sort changes: `history.length` 4 → 4 → 4. Three reading-set
  changes: 4 → 5 → 6 → 7. Back undoes the population and not the query.
- **Tab stops.** 47 before the first result (49 counting each scope radio
  separately); the page's own "Skip to results" is stop 14 (16), behind the
  masthead nav, the basket, the theme toggle and a scope radio.
- **The Reader's deep link.** With `occurrence=` in the URL at 390×780: toolbar
  **399.4px** tall, stuck bottom **y=455.4**, `mark.occurrence` top **y=448.0** —
  the linked word 7.4px behind the bar. Clear by 338px at 1440. **Fixed this
  pass**: the toolbar is a third sticky band that the programme does not allow,
  and below 48rem it now scrolls away; re-measured, the mark is clear at both
  widths and `--toolbar-h` publishes 0 when the bar is not stuck.
- **The Reader's column.** `main` inner width 1361px, `.speeches` capped at
  654.4px: **706.6px** of empty column beside the record, all on one side.
- **The Reader's headings.** Exactly one: the H1. 179 speeches, no `h2`–`h6`,
  no `role="heading"`. A screen-reader user has no skim path through the record.

No horizontal overflow on either page at either width.

## Fixed in this pass
- The `Unknown` language sentinel read as a foreign language: the apparatus
  published "N speeches carry a non-English language label" with N as the total,
  on every meeting page, and printed "spoke in Unknown" under every speaker. The
  predicate now lives in `$lib/format.ts` with seven unit tests.
- The query-hit underline's contrast, and its collision with the focus ring.
- The Reader's deep link landing behind its own sticky toolbar at phone width.

## Open, ranked
1. **P1** The 150-character promise, and "search looks within this displayed
   passage". Copy, so the author's call — but one of the two has to give.
2. **P1** Back does not undo a filter, and "Reset filters" destroys nine
   narrowings plus up to 33 "Show 240 more" clicks with no undo.
3. **P2** No active-filter summary: eight of nine narrowings are invisible as
   state.
4. **P2** The Reader's return links discard the query (the roadmap has carried
   this as deliberately open since 14 September).
5. **P2** 706px of empty column beside the record at 1440.
6. **P2** The record is one undifferentiated slab: 13 paragraphs, 0 blank lines,
   90 lines without a pause, in first-person testimony about mass atrocity.
7. **P3** 179 speeches with no heading structure.
