/**
 * Chart styling, read from the CSS custom properties in `app.css`.
 *
 * ECharts cannot resolve `var(--ink)`, so the values are read off the document
 * once and handed over as literals. One definition of the palette, not two that
 * drift, and the charts follow the theme switch instead of ignoring it.
 *
 * Two rules the fragments below enforce:
 *   1. The accent is for interaction. A datum is never drawn in `--blue`.
 *   2. Nothing is framed. Axis lines are hairlines in `--rule`; there is no
 *      chart border, no shadow, no rounded tooltip.
 *
 * The `Palette` keys are unchanged from the previous version so existing route
 * code keeps compiling; only the tokens they read have moved.
 *
 * **Why not ECharts 6's `setTheme()`.** It can swap a theme at runtime without
 * re-initialising the instance, which sounds like exactly what the toggle
 * wants. Taking it would mean registering an ECharts theme object — a second
 * place where `--blue` is written down, and the drift this file exists to
 * prevent. What it would save is re-serialising an option on a theme toggle,
 * and no figure here is large enough for that rebuild to be visible. Rejected
 * on purpose, not overlooked.
 */

import { derived, readable } from 'svelte/store';

export type Scheme = 'light' | 'dark';

/** Resolve the theme the way app.html's boot script does. */
function current(): Scheme {
	if (typeof document === 'undefined') return 'light';
	const set = document.documentElement.dataset.theme;
	if (set === 'dark' || set === 'light') return set;
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Reactive colour-scheme signal; chart option builders subscribe to this.
 * Watches the `data-theme` attribute first and the media query as a fallback,
 * so an explicit user choice and the OS setting both redraw the charts.
 */
export const colourScheme = readable<Scheme>('light', (set) => {
	if (typeof window === 'undefined') return;
	const update = () => set(current());
	update();

	const observer = new MutationObserver(update);
	observer.observe(document.documentElement, {
		attributes: true,
		attributeFilter: ['data-theme']
	});

	const query = window.matchMedia('(prefers-color-scheme: dark)');
	query.addEventListener('change', update);

	return () => {
		observer.disconnect();
		query.removeEventListener('change', update);
	};
});

/**
 * The registers in the order every figure lists them. Exported so a matrix
 * or a legend can seriate by register without keeping a second copy of the
 * order that would drift from this one.
 */
export const REGISTER_ORDER = [
	'core',
	'legal',
	'preventive',
	'commemorative',
	'contentious',
	'accountability',
	'descriptive'
] as const;
const REGISTERS: readonly string[] = REGISTER_ORDER;

export interface Palette {
	ink: string;
	inkSoft: string;
	inkFaint: string;
	/** The page's own background. The floor of a sequential ramp. */
	paper: string;
	panel: string;
	rule: string;
	ruleSoft: string;
	/** Interaction only — markLines, brush handles, selected state. Never a series. */
	accent: string;
	positive: string;
	negative: string;
	registers: Record<string, string>;
}

export function palette(): Palette {
	// One style resolution for the whole palette. Sixteen separate calls to
	// `getComputedStyle` returned sixteen answers that could in principle
	// straddle a change; these come from one snapshot of one element.
	const style = typeof document === 'undefined' ? null : getComputedStyle(document.documentElement);
	const read = (name: string, fallback: string) => style?.getPropertyValue(name).trim() || fallback;

	return {
		ink: read('--ink', '#111111'),
		inkSoft: read('--ink-2', '#444444'),
		inkFaint: read('--ink-3', '#6b6b6b'),
		paper: read('--paper', '#ffffff'),
		panel: read('--paper-raised', '#ffffff'),
		rule: read('--rule-strong', '#111111'),
		ruleSoft: read('--rule', '#cfcfcf'),
		accent: read('--blue', '#1a56b0'),
		positive: read('--state-ok', '#4a6b2e'),
		negative: read('--state-bad', '#98333a'),
		registers: Object.fromEntries(
			REGISTERS.map((r) => [
				r,
				// core resolves to var(--ink); read the computed value, not the var().
				r === 'core' ? read('--ink', '#111111') : read(`--reg-${r}`, '#6b6b6b')
			])
		)
	};
}

/**
 * The palette as a store: `$colours` in any component, re-read on every theme
 * change.
 *
 * `palette()` takes no argument and reads nothing that Svelte can track — it
 * asks the document for computed values, which the toggle has already changed
 * by the time this runs. The dependency has to be declared, and it used to be
 * declared four times, as `void $colourScheme; return palette();` in
 * `Heatmap.svelte` and three routes. The `void` was load-bearing and looked
 * like a mistake, which is the worst combination: delete it and the chart
 * silently keeps the colours of the theme the reader has just left. Declared
 * once here instead.
 */
export const colours = derived(colourScheme, () => palette());

/** Colour for a register, falling back to ink for anything unlisted. */
export function registerColour(register: string, p = palette()): string {
	return p.registers[register] ?? p.ink;
}

/**
 * The register hues, in register order. For registers only: the review of
 * 1 September 2026 found them standing for speaker groups, agenda regions,
 * Council standing and stances on four figures, so teal meant "legal" on one
 * figure and "African Group" on the next. Anything that is not a register
 * takes `categoricalNeutral`.
 */
export function categorical(p = palette()): string[] {
	return REGISTERS.map((r) => p.registers[r]);
}

/**
 * Eight fills for a categorical series that is not a register and cannot carry
 * a dash — a scatter, where the only codes available are hue and lightness.
 *
 * `categoricalNeutral` is the first answer for anything that is not a register,
 * and it stays the first answer for lines. It cannot serve a point cloud: its
 * discrimination comes from the dash crossed with the weight, and a 5px symbol
 * has no dash, which leaves six weights of grey at 65% opacity over a cloud
 * dense enough to overplot. Tested against this ramp on the semantic map, the
 * eight largest groups were not tellable apart.
 *
 * So hue, but not the register hues as such: those are an analytical claim
 * about the lexicon, and a country or an agenda category is not a register.
 * Each fill is one documented step off a register hue — the same two steps
 * `REGISTER_TONES` uses, one towards the ink and one towards the page — so the
 * family is visibly adjacent to the site's palette without borrowing a meaning
 * from it, and it follows the theme rather than being written down twice.
 *
 * Light and dark alternate down the list so that neighbouring ranks are told
 * apart by lightness even where two hues are close, and `commemorative` is left
 * out: in dark mode its periwinkle sits in the same family as `--blue`, which
 * never carries a datum.
 */
export function categoricalData(p = palette()): string[] {
	const towardsInk = (register: string) => mix(registerColour(register, p), p.ink, 0.34);
	const towardsPaper = (register: string) => mix(registerColour(register, p), p.paper, 0.26);
	return [
		p.ink,
		towardsPaper('accountability'),
		towardsInk('legal'),
		towardsPaper('contentious'),
		towardsInk('preventive'),
		towardsPaper('descriptive'),
		towardsInk('accountability'),
		towardsPaper('preventive')
	];
}

/** A stroke for a series that is not a register: a weight of ink and a dash. */
export interface NeutralStroke {
	color: string;
	/** ECharts `lineStyle.type`; also readable as a CSS `border-style` word. */
	dash: 'solid' | 'dashed' | 'dotted';
}

/**
 * Series that carry a category but not a register — speaker groups, agenda
 * regions, participant types — told apart by weight of ink and by dash rather
 * than by hue. Six weights by three dashes is eighteen strokes before any
 * repeats; a figure that needs more should be asking whether it needs a
 * legend at all. Greys survive greyscale and print, which a hue key does not,
 * and they leave the register hues meaning one thing on the whole site.
 */
export function categoricalNeutral(p = palette()): NeutralStroke[] {
	const weights = [0.95, 0.72, 0.55, 0.42, 0.32, 0.24];
	const dashes: NeutralStroke['dash'][] = ['solid', 'dashed', 'dotted'];
	const out: NeutralStroke[] = [];
	for (const dash of dashes) {
		for (const weight of weights) out.push({ color: mix(p.paper, p.ink, weight), dash });
	}
	return out;
}

/** The dashes a register's strokes cycle through, in order. */
const REGISTER_DASHES: readonly NeutralStroke['dash'][] = ['solid', 'dashed', 'dotted'];

/**
 * Lightness steps inside one register's hue: the hue itself, the hue deepened
 * towards ink, the hue lifted towards the page. Written as mixes rather than as
 * three hand-picked hex values so the ladder follows the theme — in dark mode
 * `ink` is the light end and `paper` the dark one, and the same two mixes step
 * the other way without a second table to keep in sync.
 *
 * Both steps are bounded by something. The lift stops at 0.26 because a third
 * of the way to the page puts a teal line under 3:1 against white, which is the
 * floor for a graphical object. The deepening stops at 0.34 because past that a
 * dark register hue reads as ink, and ink on this figure is the headline term:
 * at 0.45 the deepened teal sat within 1.8:1 of the `genocide` line and the
 * figure had two lines claiming to be the reference one.
 */
const REGISTER_TONES: readonly ((hue: string, p: Palette) => string)[] = [
	(hue) => hue,
	(hue, p) => mix(hue, p.ink, 0.34),
	(hue, p) => mix(hue, p.paper, 0.26)
];

/** How many distinct strokes one register's hue yields before they repeat. */
export const REGISTER_STROKES = REGISTER_DASHES.length * REGISTER_TONES.length;

/**
 * The `index`-th stroke inside a register's hue.
 *
 * A register is a shelf and not a sum, so the hue has to stay the register's:
 * it is the analytical claim the colour layer makes, and nine terms on the
 * legal shelf are nine terms on the legal shelf. But nine lines in one teal are
 * nine lines a reader tells apart only by chasing their end labels. So the hue
 * family stays and the stroke varies inside it: three lightness steps of the
 * same hue, crossed with the three dashes `categoricalNeutral` already uses, so
 * that colour is never the only code and the pair survives greyscale and print.
 *
 * The dash turns fastest, because it is the stronger signal of the two and the
 * first few terms of a shelf are the ones most often drawn together. Nine
 * strokes covers the largest register in the lexicon exactly; past that the
 * ladder repeats rather than inventing a tenth hue, and a figure asking for
 * more than one shelf's worth of one hue should be asking for a different
 * figure.
 *
 * `index` is the term's position in its register, not in the reader's
 * selection, so a term keeps its stroke whatever else is on the chart and an
 * exported SVG matches what was on screen.
 */
export function registerStroke(register: string, index: number, p = palette()): NeutralStroke {
	const step = Math.max(0, Math.trunc(index));
	const tone = REGISTER_TONES[Math.floor(step / REGISTER_DASHES.length) % REGISTER_TONES.length];
	return {
		color: tone(registerColour(register, p), p),
		dash: REGISTER_DASHES[step % REGISTER_DASHES.length]
	};
}

/** Series that carry no category at all: one weight of ink, never the accent. */
export function neutral(p = palette()): string {
	return p.inkFaint;
}

const channels = (hex: string): [number, number, number] => {
	const value = hex.trim().replace('#', '');
	const full =
		value.length === 3
			? value
					.split('')
					.map((c) => c + c)
					.join('')
			: value;
	return [
		parseInt(full.slice(0, 2), 16) || 0,
		parseInt(full.slice(2, 4), 16) || 0,
		parseInt(full.slice(4, 6), 16) || 0
	];
};

/**
 * Two colours mixed, as `#rrggbb`.
 *
 * In sRGB, which is only good enough because the ramp below is a single hue:
 * mixing between two hues in this space runs through a muddy midpoint, and
 * anything needing that should use CSS `color-mix(in oklab, …)` — as the word
 * cloud does — rather than reaching for this.
 */
export function mix(from: string, to: string, t: number): string {
	const amount = Math.min(Math.max(t, 0), 1);
	const [r1, g1, b1] = channels(from);
	const [r2, g2, b2] = channels(to);
	const channel = (a: number, b: number) =>
		Math.round(a + (b - a) * amount)
			.toString(16)
			.padStart(2, '0');
	return `#${channel(r1, r2)}${channel(g1, g2)}${channel(b1, b2)}`;
}

/**
 * A sequential ramp for a magnitude: the page's own background at 0, a data
 * colour at 1.
 *
 * Single-hue on purpose. A grid is read for which cells are hot, and a
 * multi-hue ramp buys discrimination in the middle at the cost of a reader
 * having to learn an order. Amber rather than the accent, because `--blue`
 * belongs to what a reader can act on and never to a datum — the same rule the
 * word cloud follows when it builds its scale out of the register colours.
 *
 * Returned as resolved hex rather than a CSS expression: these fills are
 * written as SVG attributes so that a downloaded figure, which carries none of
 * this site's stylesheet, is still the colour it was on screen.
 */
export function sequential(p = palette()): (t: number) => string {
	// Ink, since the Programme Grid: a magnitude is a weight of the page's own
	// ink, which is what a printed statistical plate did, and it leaves the
	// ochre of the marked word as the one warm thing on the page. The ramp
	// used to top out in the accountability amber, which was a register hue
	// carrying a quantity and, once the mark went ochre, the larger warm object
	// on the Chronology (finish review, 14 September 2026).
	return (t: number) => mix(p.paper, p.ink, t);
}

/**
 * Where a share of the maximum lands on the ramp above.
 *
 * The square root, and the reason is in the data rather than in taste. Both
 * figures that use this ramp are heavily skewed in the same way. The median
 * drawn month of the chronology runs at 2.2% against a maximum of 19.2%; the
 * median drawn speaker of the actor view at 2.65% against 28.2%. Proportional
 * to the value, that puts half of either figure inside the bottom eighth of the
 * scale, and a picture in which most of what is drawn is the colour of the page
 * understates what it shows as badly as one that overstates it. The transform is
 * monotone and clips nothing: every cell and every country keeps its order and
 * its own colour, and nothing is capped at a ceiling that hides how far past it
 * the value went.
 *
 * It is applied to *colour* and never to a length. A bar is read as a
 * proportion — half the width means half the number — so the pooled calendar's
 * rows and the map's circle radii keep their linear weight. Colour carries no
 * such promise, which is why it can take a transform, and why a figure that
 * applies it has to say so.
 *
 * It lives here rather than with either figure because it is one half of a pair:
 * `sequential()` builds the ramp and this decides where on it a value sits. Two
 * copies of that decision, one per figure, is the drift this module exists to
 * prevent.
 */
export const tone = (weight: number): number => Math.sqrt(Math.min(Math.max(weight, 0), 1));

/* One family for the drawing as for the page. The mono is the citation's face
   and appears in a figure only where a meeting symbol does. */
export const FONT = 'Hanken Grotesk, Helvetica Neue, Helvetica, Arial, sans-serif';
export const MONO = 'Courier Prime, Courier New, Courier, monospace';

/** What an end label has to fit in: the reservation below, less its offset. */
export const END_LABEL_ROOM = 90;

/**
 * Room for labels, and nothing wasted on chrome. `right` is generous because
 * series are labelled at their right-hand end rather than in a legend.
 *
 * `outerBoundsMode`/`outerBoundsContain` are ECharts 6's replacement for
 * `containLabel`, which it deprecated: the pair below is the documented
 * equivalent, and it keeps the axis labels inside the rect these numbers
 * describe rather than letting them hang off the edge of the figure. The
 * right-hand reservation stays outside that containment, because it is there
 * for the end labels rather than for the axis — which is why a long name wraps
 * inside it rather than widening it; see `endLabel`.
 */
export const grid = (labelled = true) => ({
	left: 2,
	right: labelled ? 96 : 16,
	top: 18,
	bottom: 4,
	outerBoundsMode: 'same' as const,
	outerBoundsContain: 'axisLabel' as const
});

export const tooltip = (p: Palette) => ({
	backgroundColor: p.panel,
	borderColor: p.rule,
	borderWidth: 1,
	padding: [8, 11] as [number, number],
	textStyle: { color: p.ink, fontSize: 13, fontFamily: FONT },
	extraCssText: 'box-shadow: none; border-radius: 0;'
});

/**
 * A legend is a lookup table the reader has to hold in their head. Prefer
 * `endLabel` on each series; keep this for the few charts that must page
 * through more series than can be labelled in place.
 */
export const legend = (p: Palette) => ({
	type: 'scroll' as const,
	top: 0,
	icon: 'rect',
	itemWidth: 10,
	itemHeight: 2,
	itemGap: 18,
	textStyle: { color: p.inkSoft, fontSize: 12, fontFamily: FONT }
});

/**
 * Label a line at its right-hand end instead of in a legend.
 *
 * The label wraps inside the reservation `grid` makes for it. That reservation
 * is finite and a measure's name is not: at 12px semibold, *crimes against
 * humanity* ran 40px past the figure's right edge and was cut there, with no
 * ellipsis to say so, before any name on this site was lengthened. Wrapping
 * costs two lines of vertical space next to the line it names; widening the
 * reservation instead would have cost a fifth of the plot.
 */
export const endLabel = (colour: string, name: string) => ({
	show: true,
	formatter: name,
	color: colour,
	fontFamily: FONT,
	fontSize: 12,
	fontWeight: 600 as const,
	distance: 6,
	width: END_LABEL_ROOM,
	overflow: 'break' as const
});

/* The baseline is a hairline of ink, the way a programme's chart is ruled;
   the gridlines behind the data stay the soft rule. Axis numbers are set in
   the text face with tabular figures, not in the citation's mono. */
export const axisX = (p: Palette) => ({
	axisLine: { lineStyle: { color: p.rule, width: 1 } },
	axisTick: { show: false },
	axisLabel: { color: p.inkSoft, fontSize: 12, fontFamily: FONT },
	splitLine: { show: false }
});

export const axisY = (p: Palette) => ({
	axisLine: { show: false },
	axisTick: { show: false },
	axisLabel: { color: p.inkSoft, fontSize: 12, fontFamily: FONT },
	splitLine: { lineStyle: { color: p.ruleSoft, width: 1 } }
});

/**
 * A zoom slider ruled like the rest of the page rather than in ECharts' stock
 * blue.
 *
 * The control is chrome, not a datum, but it is also not an accent: the accent
 * marks what a reader can act on *inside* a figure, and a scrollbar under the
 * plate is furniture. So it is drawn the way a rule is — a hairline box on the
 * page's own ground, the window a thin wash of ink, the handles solid ink and
 * square, because nothing on this site has a corner radius.
 *
 * `color-mix()` is a CSS function and ECharts takes literals, so the wash is
 * computed here with `mix` and follows the theme with everything else.
 */
export const dataZoom = (p: Palette) => ({
	type: 'slider' as const,
	// A hairline rail, not a bar: the frame is the soft rule and only the two
	// handles are ink, so a full-width slider is not mistaken for a plate rule.
	height: 12,
	bottom: 2,
	backgroundColor: p.paper,
	borderColor: p.ruleSoft,
	borderRadius: 0,
	fillerColor: mix(p.paper, p.ink, 0.08),
	dataBackground: {
		lineStyle: { color: p.ruleSoft, width: 1 },
		areaStyle: { color: 'transparent' }
	},
	selectedDataBackground: {
		lineStyle: { color: p.inkFaint, width: 1 },
		areaStyle: { color: 'transparent' }
	},
	// A rectangle, drawn edge to edge: ECharts' default handle is a rounded pin.
	handleIcon: 'path://M0,0 L1,0 L1,1 L0,1 Z',
	handleSize: '100%',
	handleStyle: { color: p.ink, borderColor: p.ink },
	moveHandleSize: 0,
	brushSelect: false,
	textStyle: { color: p.inkSoft, fontSize: 11, fontFamily: FONT }
});

/** Reference dates and change points: ink, dashed, never the accent. */
export const markLine = (p: Palette) => ({
	silent: true,
	symbol: 'none' as const,
	lineStyle: { color: p.inkFaint, width: 1, type: 'dashed' as const },
	label: { color: p.inkFaint, fontFamily: FONT, fontSize: 11 }
});

export const textStyle = { fontFamily: FONT };
