/**
 * Chart styling, read from the CSS custom properties in `app.css`.
 *
 * ECharts cannot resolve `var(--ink)`, so the values are read off the document
 * once and handed over as literals. That keeps one definition of the palette
 * rather than two that drift, and it means the charts follow the light/dark
 * switch instead of ignoring it.
 *
 * The fragments below are deliberately returned as plain inferred objects
 * rather than as slices of `EChartsOption`. Spreading out of that type widens
 * an axis to `XAXisOption | XAXisOption[]`, and every chart that composed one
 * would then have to be cast back. Composed at the call site into an object
 * annotated `EChartsOption`, they type-check exactly.
 */

import { readable } from 'svelte/store';

/** Reactive colour-scheme signal; chart option builders subscribe to this. */
export const colourScheme = readable<'light' | 'dark'>('light', (set) => {
	if (typeof window === 'undefined') return;
	const query = window.matchMedia('(prefers-color-scheme: dark)');
	const update = () => set(query.matches ? 'dark' : 'light');
	update();
	query.addEventListener('change', update);
	return () => query.removeEventListener('change', update);
});

const REGISTERS = ['core', 'legal', 'preventive', 'commemorative', 'contentious', 'accountability'];

export interface Palette {
	ink: string;
	inkSoft: string;
	inkFaint: string;
	panel: string;
	rule: string;
	ruleSoft: string;
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
		ink: read('--ink', '#16181d'),
		inkSoft: read('--ink-soft', '#4a4f5a'),
		inkFaint: read('--ink-faint', '#767c88'),
		panel: read('--panel', '#ffffff'),
		rule: read('--rule', '#e2e2dd'),
		ruleSoft: read('--rule-soft', '#efefea'),
		accent: read('--accent', '#8a2b2b'),
		positive: read('--positive', '#2d6a4f'),
		negative: read('--negative', '#8a2b2b'),
		registers: Object.fromEntries(REGISTERS.map((r) => [r, read(`--register-${r}`, '#8a2b2b')]))
	};
}

/** Colour for a register, falling back to the accent for anything unlisted. */
export function registerColour(register: string, p = palette()): string {
	return p.registers[register] ?? p.accent;
}

/** A categorical ramp for series that are not registers. */
export function categorical(p = palette()): string[] {
	return REGISTERS.map((r) => p.registers[r]);
}

export const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

/** Room for labels, and nothing wasted on chrome. */
export const grid = () => ({
	left: 8,
	right: 16,
	top: 28,
	bottom: 8,
	containLabel: true
});

export const tooltip = (p: Palette) => ({
	backgroundColor: p.panel,
	borderColor: p.rule,
	borderWidth: 1,
	padding: [8, 11],
	textStyle: { color: p.ink, fontSize: 13 },
	extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 4px;'
});

export const legend = (p: Palette) => ({
	type: 'scroll' as const,
	top: 0,
	icon: 'roundRect',
	itemWidth: 11,
	itemHeight: 11,
	textStyle: { color: p.inkSoft, fontSize: 12 }
});

/** Axis lines light enough not to compete with the data they frame. */
export const axisX = (p: Palette) => ({
	axisLine: { lineStyle: { color: p.rule } },
	axisTick: { show: false },
	axisLabel: { color: p.inkFaint, fontSize: 12 },
	splitLine: { show: false }
});

export const axisY = (p: Palette) => ({
	axisLine: { show: false },
	axisTick: { show: false },
	axisLabel: { color: p.inkFaint, fontSize: 12 },
	splitLine: { lineStyle: { color: p.ruleSoft } }
});

export const textStyle = { fontFamily: FONT };
