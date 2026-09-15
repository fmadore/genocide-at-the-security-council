/**
 * The containment a tooltip carries, tested apart from the chart that shows it.
 *
 * Every figure's tooltip is built by spreading `tooltip(palette)`, so the two
 * settings that keep a hover box inside its figure — `confine`, and the width
 * cap in `extraCssText` — are written once and can be dropped once. Measured
 * on *The word list over time*, dropping either put the box up to 94px above
 * the plot, or 164px past the right edge of a 327px-wide chart on a phone.
 * These assertions are here so the next edit to the tooltip's styling cannot
 * take the containment out with it.
 */

import { describe, expect, it } from 'vitest';
import { tooltip, type Palette } from './theme';

const PALETTE: Palette = {
	ink: '#121212',
	inkSoft: '#444444',
	inkFaint: '#767676',
	paper: '#ffffff',
	panel: '#f2f2f2',
	rule: '#121212',
	ruleSoft: '#dddddd',
	accent: '#1a4bd8',
	positive: '#2f6f4f',
	negative: '#8c2f2f',
	registers: {}
};

describe('tooltip', () => {
	it('confines the box to the chart it belongs to', () => {
		expect(tooltip(PALETTE).confine).toBe(true);
	});

	it('caps the box at the width of the chart, and lets a long row wrap', () => {
		// ECharts writes `white-space: nowrap` onto the box itself, and the box's
		// containing block is the chart container, so these two are what make
		// `max-width` reachable at all.
		const css = tooltip(PALETTE).extraCssText;
		expect(css).toContain('max-width: 100%');
		expect(css).toContain('white-space: normal');
	});
});
