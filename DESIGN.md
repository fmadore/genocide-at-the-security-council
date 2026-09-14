---
name: Genocide at the Security Council
description: A corpus study set as a 1960s international-organisation programme — flat ink on white, one grotesk, every figure a numbered full-width plate with its notes beneath.
colors:
  paper: "#ffffff"
  paper-sunk: "#f2f2f2"
  paper-raised: "#ffffff"
  rule: "#cfcfcf"
  rule-strong: "#111111"
  ink: "#111111"
  ink-2: "#444444"
  ink-3: "#6b6b6b"
  blue: "#1a56b0"
  blue-mid: "#2f6fd0"
  blue-flag: "#5b92e5"
  mark: "#f5d98a"
  reg-legal: "#2c7069"
  reg-preventive: "#5c7a3a"
  reg-commemorative: "#6b5b95"
  reg-contentious: "#a63d40"
  reg-accountability: "#b07817"
  reg-descriptive: "#8e3f77"
  state-ok: "#4a6b2e"
  state-warn: "#8a6410"
  state-bad: "#98333a"
typography:
  display:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "3.25rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.025em"
  numeral:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariant: "tabular-nums lining-nums"
  headline:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0"
  symbol:
    fontFamily: "Courier Prime, Courier New, Courier, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
    fontVariant: "tabular-nums"
rounded:
  none: "0"
spacing:
  sp-1: "0.25rem"
  sp-2: "0.5rem"
  sp-3: "0.75rem"
  sp-4: "1rem"
  sp-5: "1.5rem"
  sp-6: "2rem"
  sp-7: "3rem"
  sp-8: "4rem"
  sp-9: "6rem"
  sp-10: "8rem"
components:
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 {spacing.sp-3}"
    height: "2.5rem"
  button-hover:
    backgroundColor: "{colors.paper-sunk}"
    textColor: "{colors.ink}"
  button-disabled:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-3}"
  button-compact:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 {spacing.sp-3}"
    height: "2rem"
  segmented-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 {spacing.sp-3}"
    height: "2.5rem"
  segmented-cell-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 {spacing.sp-3}"
    height: "2rem"
  chip-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 {spacing.sp-3}"
    height: "2.5rem"
  select:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 2rem 0 {spacing.sp-3}"
    height: "2.5rem"
  plate:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.sp-3} 0 0"
    width: "100%"
  plate-question:
    textColor: "{colors.ink-2}"
    typography: "{typography.body}"
  plate-note:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
  nav-link:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    height: "2.5rem"
  nav-link-active:
    textColor: "{colors.ink}"
  mark-word:
    backgroundColor: "{colors.mark}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.05em 0.14em"
  dialog-plate:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.sp-5}"
    width: "min(48rem, calc(100vw - 2rem))"
---

# Design System: Genocide at the Security Council

## Overview

**Creative North Star: "The Programme Grid"**

A programme, not a dashboard. The site is set the way a 1960s–70s international
organisation set its printed programme of work: flat ink on white stock, one
Akzidenz-class grotesk doing every job, a strict twelve-column grid, 3px rules
opening the page and each plate, hairlines everywhere else. Every figure is a
numbered plate that takes the whole width with its notes beneath it. Nothing is
boxed, tiled or eyebrowed; the metric-tile-and-card overview is refused
outright, and so is the card, the coloured side rail and the drop shadow.

Three colour layers are kept apart and cannot leak into each other:
ground/ink, interaction, data. UN flag blue carries links, focus and controls
and is never a datum. The six register hues are an analytical classification
and stay quarantined inside the plates. The one warm thing on the page is the
ochre tint on the marked word — the site's single gesture at its own scale,
deliberately outside the blue family so it never reads as a link or a
selection. Dark is the same programme reversed: white ink on a black plate,
still flat, still unboxed.

The reading story the build serves: a researcher arrives with a claim, reads
the counted numbers, opens a plate, reads how to read it and what it does not
show, and leaves with a citable figure or a meeting symbol. The first viewport
is the heavy rule, the wordmark and the sections on one line, the title at
3.25rem, the corpus counted as a field of unit squares with the marked share
filled, then Plate 1 full width. Origin: form candidate "The Programme Grid",
seed 426cd46f.

**Key Characteristics:**
- Pure white ground (`#ffffff`), flat ink, zero radius, zero drop shadows
- One grotesk (Hanken Grotesk) for headings, body, labels, numbers and axes
- Courier Prime reserved for the citation: meeting symbols, script names, paths
- Twelve columns at 90rem; plates full width, notes beneath in two sixes
- 3px heavy rule opens the page, each plate, the footer, the current section
- Blue only for interaction; ochre only for the mark; register hues only inside figures
- Hierarchy carried in weight and position, never in tracked capitals
- Both themes first-class; chart colour read from the CSS tokens at runtime

## Colors

Two grounds and three inks, one interaction blue, one warm ochre, and a
quarantined six-hue data ramp — twenty-two tokens, each declared in both themes.

### Primary
- **Flag Blue** (`{colors.blue}`): links, control text, disclosure summaries and the caret. The interaction layer, and nothing else. Hover lifts to **Flag Blue Lifted** (`{colors.blue-mid}`); the focus ring is **UN Flag Blue** (`{colors.blue-flag}`), the one value identical in both themes.
- **Mark Ochre** (`{colors.mark}`): the flat tint behind every found word, the wordmark's `<mark>`, and the filled share in the unit field's key. The only warm colour on the page. Ink on it is 13:1; in dark it deepens to the same ochre at 7.4:1.

### Secondary — the register layer (data only)
- **Legal Teal** (`{colors.reg-legal}`), **Preventive Olive** (`{colors.reg-preventive}`), **Commemorative Iris** (`{colors.reg-commemorative}`), **Contentious Brick** (`{colors.reg-contentious}`), **Accountability Amber** (`{colors.reg-accountability}`), **Descriptive Mulberry** (`{colors.reg-descriptive}`): the six discursive registers. They appear as chart strokes, as the inset underline under a marked word carrying a register, and as a 0.625rem square swatch before a chip's words. The seventh register, *core*, resolves to ink on purpose: the core word is the text itself.

### Tertiary — provenance states
- **Computed Green** (`{colors.state-ok}`), **Mixed Amber** (`{colors.state-warn}`), **Model Red** (`{colors.state-bad}`): resolved independently of the register ramp. They appear only as a small square before the provenance word in the masthead's page origin and in a plate's head, so the row reads as a key rather than as a row of warnings. Model Red also carries a download failure line.

### Neutral
- **Coated White** (`{colors.paper}`): the ground. Pure white, not a tinted stock.
- **Sunk Stock** (`{colors.paper-sunk}`): the zebra row, the pressed control, the hovered KWIC line, the open disclosure row.
- **Ink** (`{colors.ink}`): body text, headings, every control border, the heavy rule, the filled unit square, the selected segmented cell's ground.
- **Quiet Ink** (`{colors.ink-2}`): apparatus prose, reading notes, nav links at rest, chart axis labels — 9.7:1 on paper.
- **Faint Ink** (`{colors.ink-3}`): plate numbers, bases under a headline number, placeholder text, the loading word — 5.3:1 on paper, 4.7:1 on the sunk stripe.
- **Hairline** (`{colors.rule}`): the rule that separates rows and closes a source strip. **Structural Rule** (`{colors.rule-strong}`) is ink at hairline weight, for the KWIC column header and the skip link.

### Named Rules

**The Three Layers Rule.** Ground/ink, interaction and data are three sealed layers: the accent is never used for a datum, a register hue is never used for a control, and nothing borrows across.

**The One Warm Thing Rule.** The ochre mark is the only warm colour on the page; a magnitude ramp is paper-to-ink (`mix(paper, ink, t)`), never a hue.

**The Blue Is Interaction Rule.** UN flag blue carries links, focus rings and controls. A chart series is ink, a weight of ink, or a register hue — never blue.

**The Quarantine Rule.** Register hues live inside plates. They may not colour a control's edge, a chip's ground, a heading or a page rail; a chip carries its series colour as a 0.625rem square swatch before the words.

## Typography

**Display / Body / Label Font:** Hanken Grotesk (with Helvetica Neue, Helvetica, Arial, sans-serif) — self-hosted variable, roman and italic, weights 100–900
**Citation Font:** Courier Prime (with Courier New, Courier, monospace) — self-hosted static 400

**Character:** One Akzidenz-class grotesk sets the headings, the body, the labels, the numbers and the chart axes; it is neutral, wide-apertured and institutional, the face a programme of work was printed in. The typewriter face appears only where the record itself was typed — a meeting symbol, a script name, a file path — so mono reads as evidence rather than as costume. A fixed rem scale off a 16px root: an Operate surface is read at one distance and should not breathe with the window.

### Hierarchy
- **Display** (700, 3.25rem, line-height 1, -0.025em): the page title only; drops to 2.75rem below 40rem. Carries the `<mark>` in the wordmark's word.
- **Numeral** (700, 2.75rem, -0.02em, tabular lining figures): a headline number in the tally, set as type under a faint-ink term and over a faint-ink base.
- **Headline** (700, 1.5rem, line-height 1.1): a plate's title, capped at 40rem, its own anchor and underlined on hover.
- **Title** (700, 1.25rem, line-height 1.1): section headings and the basket dialog's name.
- **Body** (400, 1rem, line-height 1.5): running prose, capped at the one prose measure of 38rem (~68 characters). A standfirst sets the same face at 1.125rem in quiet ink.
- **Label** (600, 0.875rem, letter-spacing 0, sentence case): the apparatus voice — "How to read this", "What it does not show", "Source", "Reading set", a control's name, a table header, the running-head label.
- **Symbol** (Courier Prime 400, 0.875rem, tabular figures): meeting symbols such as `S/PV.3137`, the script-and-artefact source line, inline code.

### Named Rules

**The Citation Is Typewritten Rule.** Courier Prime is permitted on meeting symbols, script names, file paths and inline code, and nowhere else; everything else — including a figure's note line and every number — is Hanken Grotesk.

**The Sentence Case Rule.** No tracked capitals anywhere. The label voice is sentence case at 600 weight in ink; hierarchy is carried by weight and position, never by letterfit or an uppercase eyebrow.

**The Numbers Are Counted Rule.** A headline number is set as type in a row of four on the grid between two rules, after a field of unit squares that lets the share be counted; it is never tiled, never boxed, never given a card of its own.

## Layout

The page is a single centred column of 90rem (`--page`) with a gutter of 1.5rem
that opens to 2rem at 64rem. Inside it, `.grid` is twelve columns,
`minmax(0, 1fr)` each, with a 1.5rem column gap; children place themselves with
`grid-column` and nothing else about the grid is negotiable.

Spacing is a named 4px-based scale from 0.25rem to 8rem (`sp-1`…`sp-10`); a
value not on the scale is a bug. Plates are separated by 6rem (`sp-9`); main
runs 1.5rem of padding at the top and 6rem at the bottom.

Prose is capped at one measure only: 38rem, about 68 characters of the grotesk
at 1rem. The plate ignores the measure — the evidence gets every column — and
its apparatus returns to it: two notes of six columns each at 48rem, narrowing
to five columns with the second at `7 / span 5` from 64rem, with the overflow
disclosure running full width beneath both. The tally's four numbers run twelve
columns stacked, six at 40rem, three at 64rem. The overview title takes nine of
twelve from 64rem.

Breakpoints observed: 40rem (type and unit-field row length), 44rem (the exit
index collapses to one column), 48rem (apparatus pairs; the running head drops
its label), 64rem (gutter, apparatus fives, 48 squares to a row).

Two sticky bands: the masthead at `z-index: 100`, the figure contents band
directly under it at `90`, with `scroll-padding-top` computed from both plus
0.75rem so a deep link never parks a plate's title behind them. Print restores
pure black on white, drops the masthead, nav and skip link, prints an `http`
link's URL after it in mono, and forbids a break inside a figure or table.

## Elevation & Depth

**This system has no elevation.** There are no drop shadows anywhere — not on
the masthead, not on the sticky contents band, not on the basket dialog, which
explicitly sets `box-shadow: none` and separates itself from the page with an
ink hairline and its own 3px top rule. Depth is carried by three devices only:
rules (1px hairline, 1px ink, 3px heavy), the sunk ground (`paper-sunk`) for a
pressed, hovered or zebra state, and space.

### Shadow Vocabulary
The only `box-shadow` in the build is inset and functions as a drawn rule, not
as light:
- **Current-section underline** (`box-shadow: inset 0 -3px 0 var(--ink)`): marks the active masthead section and the current entry in the running head. An inset rule rather than a border so nothing moves when it appears.
- **Register underline** (`box-shadow: inset 0 -2px 0 var(--reg-*)`): a marked word's register, under the ochre tint, so colour is never the only code.
- **Query-hit underline** (`box-shadow: inset 0 -2px 0 var(--blue-flag)`): in the concordance, the reader's own search term, distinguished from the node's ochre wash.

### Named Rules

**The Nothing Is Boxed Rule.** Separation is a rule or space. Radius is 0 everywhere, drop shadows are banned outright, and the only permitted shadow is an inset underline standing in for a rule.

**The Heavy Rule.** 3px of ink opens the page (the body's top border), each plate, the footer, and marks the current section; 1px of ink is a structural division; 1px of `rule` grey separates rows. There is no fourth weight.

## Shapes

Radius is `0` — declared once as `--radius` and applied to controls, dialogs
and the focus ring alike. Nothing on the site is rounded, pilled or clipped.

The recurring silhouette is the rectangle drawn by a 1px ink hairline: a
button, a chip, a select, a segmented group, a unit square and the basket
dialog are all the same rectangle at different sizes. The second recurring
shape is the 0.625rem square swatch — used before a provenance word, before a
chip's term, and in the unit field's key — which is how every colour key on the
site is stated. Icons are inline stroke SVG at 1rem with `stroke-width` 1.75
and `stroke-linecap: square`, including the select's drawn chevron, which
replaces the native one in ink and reverses to `#f2f2f2` in dark.

## Components

### Buttons
- **Shape:** square (radius 0), 1px ink border.
- **Default:** paper ground, ink text, label type (0.875rem/600 for named labels, 500 inside groups), 0 0.75rem padding, minimum height 2.5rem.
- **Compact:** the same button at 2rem minimum height — used for the full-screen toggle, the download formats, the theme toggle, back-to-top and chips, wherever the control sits inside a plate's strip.
- **Hover / Focus:** ground drops to sunk stock; focus is a 2px `blue-flag` outline at 2px offset with radius 0. Transitions run 160ms on `cubic-bezier(0.2, 0, 0, 1)`.
- **Disabled:** faint ink text, `rule`-grey border, default cursor.

### Segmented Groups
- **Style:** the only button-group pattern on the site. One 1px ink border around the whole group, each cell divided by a 1px ink border-left, cells at the full 2.5rem control height so the group sits on the same centre line as the selects beside it.
- **State:** unselected cells are explicit paper with quiet-ink text (never transparent, so forced-colour modes cannot borrow the neighbour's ground); the selected cell (`aria-pressed`/`aria-current="true"`, or the reading-set radio's checked label) is ink ground with paper text.
- **Uses:** the reading set (real radios drawn by their labels, the input covering the cell at `opacity: 0`), and the CSV/SVG/PNG download group.

### Chips
- **Style:** a 2rem compact control — 1px ink hairline, paper ground, sentence case at 500 — carrying its series colour as a 0.625rem filled square before the words, its border drawn in the series' own dash so the key agrees with the line on the chart.
- **State:** hover sinks the ground; selected inverts to ink ground with paper text, and the swatch gains a 1px paper outline so an ink-coloured key survives the inversion.

### Inputs / Fields
- **Style:** paper ground, 1px ink border, radius 0, 2.5rem minimum height, 0 0.75rem padding, label type. The caret is flag blue; placeholders are faint ink at full opacity.
- **Select:** the native menu kept, the native chevron replaced by a drawn ink chevron at 0.75rem, 2rem of right padding.
- **Checkbox:** the one input exempted from the 2.5rem box — 1rem square with `accent-color: var(--ink)`.
- **Focus:** the global 2px `blue-flag` outline at 2px offset.

### Navigation
- **Masthead:** a rule and the ground colour, never a panel — sticky, paper, closed by a 1px ink border-bottom, under the body's own 3px rule. The wordmark is a marked word in a line of running text at 1rem/700 with a faint-ink subtitle beside it. Section links are label type at 500 in quiet ink, each on the same 2.5rem box whether badged or not; hover goes to ink; the current section is 700 in ink with the 3px inset underline. A page's provenance sits under its name as a coloured square and the word in faint ink.
- **Running head (Contents):** sticky directly beneath the masthead, one row on every viewport, scrolling sideways rather than wrapping. A "On this page" label (hidden below 48rem), then plate numbers from a CSS counter in faint ink followed by titles in quiet ink; the current entry is 600 in ink with the 3px inset underline.
- **Footer:** opened by the 3px heavy rule, label type in quiet ink, prose capped at the measure.

### The Plate (signature)
The component the whole system exists for. A plate is opened by a 3px ink rule
across the full page width and carries, in order: the plate number printed from
a CSS counter ("Plate 3", label voice in faint ink, hidden from assistive
technology), the title as its own anchor, the question in quiet ink at the
prose measure, and a provenance link whose kind is a coloured square before
ink-coloured words. A control bar, if present, is centred between a 1px ink
rule above and a 1px grey rule below. The figure body then runs the full width.
Beneath it, the apparatus sits on the grid behind a 1px ink rule: "How to read
this" in ink and "What it does not show" in quiet ink, six columns each,
with an optional "More on this figure" disclosure (a blue label prefixed `+ `
/ `− `) running under both. A source strip closes the plate behind a 1px grey
rule: the "Source" label, the script-and-artefact path in Courier Prime, then
the download group. No panel, no border, no radius; plates are separated from
each other by 6rem of space. Full screen is an opt-in that expands the plate to
the viewport on paper ground with a 160ms clip-path entrance, honoured only
under `prefers-reduced-motion: no-preference`.

### The Unit Field (signature)
A quantity counted in squares, the way a programme's statistical page did: one
1px-outlined square per unit in a CSS grid, the counted part filled with ink,
0.25rem gaps, 20 to a row below 40rem, 40 by default, 48 from 64rem. The whole
field is one `role="img"` with one accessible name. Squares, never pictograms;
the filled squares force their ink in print.

### Dialog (Basket)
A plate, not a floating card: `min(48rem, 100vw − 2rem)`, 1.5rem padding, 1px
ink border all round with the top edge at 3px, radius 0, `box-shadow: none`,
paper ground. The backdrop is a fixed `rgb(0 0 0 / 0.35)` rather than a tint of
the reversing ink token. A problem line is the sunk stripe with a 1px grey
inline-start rule — never a coloured bar.

### Data Tables
Collapsed borders, full width, 0.875rem, tabular lining figures. Headers are
label voice in ink over a 1px ink rule; cells sit over a 1px grey rule; even
rows take the sunk stock; numeric columns align right. A table is opened by a
disclosure whose summary is blue label type with a chevron — the only thing on
the site that turns (90°, 160ms, disabled under reduced motion).

### Charts
ECharts reads its colours from the CSS tokens at runtime in both themes. Axes
are a hairline of ink with quiet-ink 12px labels in Hanken Grotesk; reference
lines and change points are faint ink, dashed, never the accent. Categorical
series that are not registers are told apart by weight of ink crossed with
three dashes; register series use the register hue crossed with two tones (34%
towards ink, 26% towards paper) and three dashes. A magnitude ramp is
`mix(paper, ink, t)`, square-rooted for placement. The data-zoom slider is the
page's own ground, an 8% ink wash for the window and solid ink handles. The
loading state is a quiet skeleton: the word in faint ink where an axis title
would sit, over the hairline baseline the plot will draw on — nothing moves.

### Named Rules

**The Notes Beneath Rule.** A figure's apparatus sits under the plate on the grid in two columns of six (five from 64rem), never in a margin and never behind a toggle; the reading note is the first thing under the marks.

**The Targets 24px Rule.** Every control is at least 2rem tall and standard controls are 2.5rem; a shorter box in a control bar sits on its own centre line and reads as crooked.

## Do's and Don'ts

### Do:
- **Do** keep the wordmark's `<mark>` on the word *Genocide*: the marked word is the site's one gesture at its own scale and must survive any redesign.
- **Do** open every figure with the plate apparatus — question, "How to read this", "What it does not show", source — behind the 3px ink rule, full width, notes beneath.
- **Do** count a share in the unit field's squares before stating it as a number.
- **Do** keep one grotesk (Hanken Grotesk) for headings, body, labels, numbers and chart axes.
- **Do** keep the ground pure white (`{colors.paper}`) and reverse it whole in dark; both themes are first-class and chart colour is read from the tokens at runtime.
- **Do** hold prose to the single 38rem measure and let plates take all twelve columns.
- **Do** make every figure print and export cleanly: print restores black on white, prints the URL after an external link in mono, and forbids a break inside a figure or table.
- **Do** meet WCAG 2.2 AA as the floor, and code a register or a provenance kind in shape, weight or dash as well as in colour.
- **Do** put a colour key in a 0.625rem square before the words, so the words stay ink.
- **Do** keep hierarchy in weight and position: sentence case at 600 for every label.

### Don't:
- **Don't** put a figure, a number or a section in a card, a panel or a tile; separation is a rule or space, radius stays 0.
- **Don't** build a metric-tile overview — headline numbers are set as type in a row on the grid between two rules.
- **Don't** set an eyebrow, a kicker or a tracked-capital label above anything.
- **Don't** set an arrow-prefixed list or lead a link with a directional glyph in place of a title.
- **Don't** use Courier Prime as costume: it belongs to meeting symbols, script names, file paths and inline code only.
- **Don't** put a coloured side border or a 3px coloured bar on a note, a warning or a row; the rail is an ink hairline.
- **Don't** colour a control, a chip's ground or an edge with a register hue; the register ramp stays inside the plates.
- **Don't** use blue for a datum — no blue series, no blue bar, no blue fill on a chart.
- **Don't** add a drop shadow; the only permitted shadow is an inset underline standing in for a rule.
- **Don't** introduce a spacing, type or rule value that is not on the named scale.
