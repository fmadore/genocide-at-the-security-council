/**
 * What the sticky contents decides, tested apart from how it is drawn.
 *
 * The cases below are the claims it makes: that nothing is marked before the
 * first figure, that the mark follows the reading line rather than the top of
 * the window, and that the foot of the document belongs to the last figure even
 * when that figure is too short to fill a window on its own.
 */

import { describe, expect, it } from 'vitest';
import { LANDING_SLACK, currentFigure } from './contents';

const WINDOW = 800;
const BAND = 100;

const figures = [
	{ id: 'first', top: 1000 },
	{ id: 'second', top: 3000 },
	{ id: 'third', top: 5000 }
];

const at = (scrollY: number, documentHeight = 6000) => ({
	scrollY,
	viewportHeight: WINDOW,
	documentHeight,
	obstructed: BAND
});

describe('currentFigure', () => {
	it('marks nothing while the reader is still in the standfirst', () => {
		expect(currentFigure(figures, at(0))).toBeNull();
		expect(currentFigure(figures, at(880))).toBeNull();
	});

	it('marks a figure once its top has passed under the sticky band', () => {
		// 900 + 100 is the first figure's own top edge, and not a window earlier.
		expect(currentFigure(figures, at(890))).toBeNull();
		expect(currentFigure(figures, at(900))).toBe('first');
		expect(currentFigure(figures, at(2901))).toBe('second');
	});

	it('marks the figure a jump has just landed on, not the one before it', () => {
		// A jump parks the top edge on the line, and rounding puts it a pixel or
		// two under: without the slack the contents would answer 'first'.
		expect(currentFigure(figures, at(2900 - LANDING_SLACK + 1))).toBe('second');
	});

	it('gives the foot of the document to the last figure', () => {
		// A short final figure never reaches the reading line on its own.
		const short = [
			{ id: 'first', top: 1000 },
			{ id: 'last', top: 5900 }
		];
		expect(currentFigure(short, { ...at(5200), documentHeight: 6000 })).toBe('last');
	});

	it('reads the list in any order, and an empty one as no answer', () => {
		expect(currentFigure([...figures].reverse(), at(3100))).toBe('second');
		expect(currentFigure([], at(3100))).toBeNull();
	});
});
