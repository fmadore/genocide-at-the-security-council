---
target: Chronology
total_score: 28
max_score: 40
na_heuristics:
p0_count: 1
p1_count: 3
timestamp: 2026-09-19T13-55-00Z
slug: web-src-routes-chronology-page-svelte
---
Method: dual-agent (A: Opus design review · B: Opus detector + browser evidence),
isolated. Phase 6.6 of docs/DESIGN_ROADMAP.md, compared against the
14 September baseline taken before the Path B redesign. Assessment A's own
summary line read 26/36; its table sums to 28/40 and no heuristic was marked
`n/a`, so 28/40 is the score.

## Design Health Score (Chronology)
| # | Heuristic | Score | Δ | Key issue |
|---|---|---|---|---|
| 1 | Visibility of system status | 3 | +1 | "475 of 948 months drawn" is exemplary; Plate 6 renders empty with no status saying why |
| 2 | Match system / real world | 4 | +1 | The study's own terminology; reference dates stated as context, not cause |
| 3 | User control and freedom | 3 | = | URL state and preserved zoom; a chart click still navigates away with no undo but Back |
| 4 | Consistency and standards | 2 | = | Hand-rolled dataZoom where `theme.ts` exports one; 9px SVG text against the system's 12px |
| 5 | Error prevention | 2 | −1 | Plate 6's image formats were enabled with no chart. Fixed this pass |
| 6 | Recognition rather than recall | 2 | = | End labels give way to a legend above 8 series, where three swatches are near-identical |
| 7 | Flexibility and efficiency | 3 | = | Shelves, URL state, four units, full screen; no keyboard path to the drill |
| 8 | Aesthetic and minimalist | 3 | +1 | 10,451px desktop / 21,058px mobile; the study's finding is Plate 5 of 6 |
| 9 | Error recovery | 2 | −1 | Two refusal states are centred grey text with no next action |
| 10 | Help and documentation | 4 | = | Every plate states what it does not show; the withholding rule is in `more` |
| Total | | 28/40 | +1 | Acceptable |

## Design specificity — **partly grounded**

Authored: `linkable = gridTerms.length === 1`, an epistemic refusal encoded in
the interface — a measure resolving to several terms declines to offer one
member's lines as evidence. The chip swatch whose `border-style` is the series'
own dash, so the key literally agrees with the line (verified live: dashed and
dotted teal swatches against `stroke-dasharray` 7.2,3.6 and 1.8). The ratio
column set in ink "whichever way it points", refusing red-up/green-down. The
hatch for a withheld month drawn inside the SVG so a downloaded file still says
what its colours mean. The tooltip cut at 8 rows that names the threshold it cut
at.

Interchangeable: the figure forms themselves — a 12×79 calendar with a sqrt
ramp, a line chart with end labels and a zoom brush, a month-of-year table with
an inline bar. The authored layer sits around the marks, rarely in them. And the
running order is declaration order rather than a reading story: Plate 1 charts
the reading set's own coverage and then disclaims its relevance to everything
below it, in the researcher's first viewport.

## Evidence (Assessment B)

Detector: `[]`, exit 0, and confirmed live rather than assumed — scratch files
under the same invocation did produce findings. One caveat and one stale entry:

- The `.svelte` path runs a subset of the rules (see the audit record).
- `.impeccable/config.json` carries an `ignoreValues` entry scoped to this file,
  rule `side-tab`, value `*`, whose stated reason is a 3px left border at
  `+page.svelte:1262-1264`. The current chip has no left border at all. The
  suppression is stale and suppresses nothing today — but it would silence a
  real finding on this file if one appeared.

Measured and CONFIRMED:

- **Heatmap text at 390px.** `viewBox="0 0 1220 1480"` rendered at 342×414.88 →
  scale 0.2803. `font-size="9"` labels compute to **2.52 CSS px** (rect height
  4.00px); the key's 8.5px labels to 2.38px. At 1440 the same labels are 10.04px
  — still under the 12px the system sets. Cells at 390 are 26.91 × 4.48px.
- **The `legal` shelf.** 10 series; within each dash class the strokes differ
  only in lightness. Lowest three pairs all **1.564:1** (`#2c7069` / `#23504b`);
  full range 1.564–2.686:1, every one under the 3:1 non-text floor. Above 8
  series the end labels are replaced by a legend, so the last positional code
  goes too.
- **The hatch.** 474 hatched rects, of which 473 are cells: **387** titled
  "withheld, under the 125-speech minimum" and **86** "the Council held no
  speeches". The in-SVG key reads `no rate (387)`. Two epistemic states drawn
  identically, and the key undercounts the squares by 86.
- **Off-palette strokes in exports.** `intervalBand()` set `lineStyle: {opacity: 0}`
  with no colour, so ECharts assigned its stock palette: `#5070dd`, `#b6d634`,
  `#505372`, `#ff994d` at `stroke-opacity="0"`, in a file governed by "blue is
  never a datum". **Fixed this pass**; the bands' invisible edges now carry the
  band's own colour (re-measured: only `#2c7069`, `#23504b`, `#111111`).
- **Axis labels.** y-axis `--ink-3`, x-axis `--ink-2`, on two charts of three, via
  overrides that replaced the whole `axisLabel` to add a formatter — dropping the
  font family with the colour. **Fixed this pass.**
- **Reference-date kind swatches.** Six weights of one ink; adjacent contrast
  1.227–2.226:1. In the default all-pressed state `atrocity`'s `#1d1d1d` swatch
  sits at 1.10:1 on its own chip ground, visible only by the 1px paper outline.
- **Plate 6.** Empty by default with CSV, SVG and PNG all enabled; the image
  formats failed into "The figure is still loading", blaming a load for a state
  the reader chose. **Fixed this pass** — image formats now appear only when
  there is a figure.

No horizontal overflow at 1440 or 390. Every figure body is the full page column
(1361/1361 at 1440). The only control under 24px is the 16px reference-dates
checkbox, and it is not within 24px of another control.

## Fixed in this pass
- The off-palette invisible band strokes.
- The two axis-label overrides that dropped the system's colour and font.
- Image download formats offered on a plate with nothing drawn.

## Open, ranked
1. **P0** The calendar heatmap is illegible at 390px (2.52px labels) with no
   legible fallback — the table beneath it is closed and its summary does not say
   it is the readable version.
2. **P1** Within a register shelf, lines are told apart by lightness at
   1.56–2.69:1, and above 8 series the end labels give way to a legend.
3. **P1** The hatch conflates "withheld" with "no Council sat", and its key
   counts 387 of 473.
4. **P1** Plate 2's evidence is mouse-only: its own data table renders 0 links
   where Plates 3, 4 and 6 all carry them.
5. **P2** Plate 4 draws a magnitude bar across six columns with no key and no
   mention in its apparatus.
6. **P2** Plate 1 is first and governs nothing else on the page; the page's one
   citable result (4.95×, p = 0.0005) is at 58% depth.
7. **P3** The stale `side-tab` suppression in `.impeccable/config.json`.
