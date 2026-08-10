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
 */

import { readable } from 'svelte/store';

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
	panel: string;
	rule: string;
	ruleSoft: string;
	/** Interaction only — markLines, brush handles, selected state. Never a series. */
	accent: string;
	positive: string;
	negative: string;
	registers: Record<string, string>;
}

function read(name: string, fallback: string): string {
	if (typeof document === 'undefined') return fallback;
	const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	return value || fallback;
}

export function palette(): Palette {
	return {
		ink: read('--ink', '#14171a'),
		inkSoft: read('--ink-2', '#3d444c'),
		inkFaint: read('--ink-3', '#626a74'),
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
