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

const REGISTERS = ['core', 'legal', 'preventive', 'commemorative', 'contentious', 'accountability'];

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
		ink: read('--ink', '#14171a'),
		inkSoft: read('--ink-2', '#3d444c'),
		inkFaint: read('--ink-3', '#626a74'),
		paper: read('--paper', '#f1f2ee'),
		panel: read('--paper-raised', '#fbfbf8'),
		rule: read('--rule-strong', '#b7bcaf'),
		ruleSoft: read('--rule', '#d6d9cf'),
		accent: read('--blue', '#1b5fa8'),
		positive: read('--state-ok', '#4a6b2e'),
		negative: read('--state-bad', '#98333a'),
		registers: Object.fromEntries(
			REGISTERS.map((r) => [
				r,
				// core resolves to var(--ink); read the computed value, not the var().
				r === 'core' ? read('--ink', '#14171a') : read(`--reg-${r}`, '#626a74')
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

/** A categorical ramp for series that are not registers. */
export function categorical(p = palette()): string[] {
	return REGISTERS.map((r) => p.registers[r]);
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
	const top = p.registers.accountability ?? p.ink;
	return (t: number) => mix(p.paper, top, t);
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

export const FONT = 'Archivo, system-ui, -apple-system, sans-serif';
export const MONO = 'IBM Plex Mono, ui-monospace, SFMono-Regular, monospace';

/**
 * Room for labels, and nothing wasted on chrome. `right` is generous because
 * series are labelled at their right-hand end rather than in a legend.
 *
 * `outerBoundsMode`/`outerBoundsContain` are ECharts 6's replacement for
 * `containLabel`, which it deprecated: the pair below is the documented
 * equivalent, and it keeps the axis labels inside the rect these numbers
 * describe rather than letting them hang off the edge of the figure. The
 * right-hand reservation stays outside that containment, because it is there
 * for the end labels rather than for the axis.
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

/** Label a line at its right-hand end instead of in a legend. */
export const endLabel = (colour: string, name: string) => ({
	show: true,
	formatter: name,
	color: colour,
	fontFamily: FONT,
	fontSize: 12,
	fontWeight: 600 as const,
	distance: 6
});

/** Axis lines light enough not to compete with the data they frame. */
export const axisX = (p: Palette) => ({
	axisLine: { lineStyle: { color: p.rule, width: 1 } },
	axisTick: { show: false },
	axisLabel: { color: p.inkFaint, fontSize: 12, fontFamily: MONO },
	splitLine: { show: false }
});

export const axisY = (p: Palette) => ({
	axisLine: { show: false },
	axisTick: { show: false },
	axisLabel: { color: p.inkFaint, fontSize: 12, fontFamily: MONO },
	splitLine: { lineStyle: { color: p.ruleSoft, width: 1 } }
});

/** Reference dates and change points: ink, dashed, never the accent. */
export const markLine = (p: Palette) => ({
	silent: true,
	symbol: 'none' as const,
	lineStyle: { color: p.inkFaint, width: 1, type: 'dashed' as const },
	label: { color: p.inkFaint, fontFamily: FONT, fontSize: 11 }
});

export const textStyle = { fontFamily: FONT };
