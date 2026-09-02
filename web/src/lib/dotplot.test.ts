import { describe, expect, it } from 'vitest';
import { dotPosition, dotRadius, dotScale, spreadFill } from './dotplot';
import type { Word } from './types';

const word = (name: string, target: number, logRatio: number, dp = 0.3): Word => ({
	word: name,
	target,
	reference: 100,
	g2: 50,
	log_ratio: logRatio,
	documents: 5,
	meetings: 4,
	dp
});

describe('the dot plot scale', () => {
	it('always spans zero, so the zero rule is drawn', () => {
		const scale = dotScale([word('a', 10, 2), word('b', 10, 4)]);
		expect(scale.low).toBeLessThanOrEqual(0);
		expect(scale.high).toBeGreaterThan(4);
		expect(dotPosition(0, scale)).toBeGreaterThan(0);
	});

	it('places a higher log ratio further right and clamps to the track', () => {
		const scale = dotScale([word('a', 10, 1), word('b', 10, 3)]);
		expect(dotPosition(3, scale)).toBeGreaterThan(dotPosition(1, scale));
		expect(dotPosition(99, scale)).toBe(1);
		expect(dotPosition(-99, scale)).toBe(0);
	});

	it('ticks every whole log ratio inside the range', () => {
		expect(dotScale([word('a', 10, 2.4), word('b', 10, -1.2)]).ticks).toEqual([-1, 0, 1, 2]);
	});

	it('does not divide by zero on a single row at zero', () => {
		const scale = dotScale([word('a', 10, 0)]);
		expect(dotPosition(0, scale)).toBeGreaterThan(0);
		expect(dotPosition(0, scale)).toBeLessThan(1);
	});
});

describe('the marks', () => {
	it('gives the dot an area proportional to the frequency', () => {
		const quarter = dotRadius(25, 100, 0, 10);
		const full = dotRadius(100, 100, 0, 10);
		expect(full / quarter).toBeCloseTo(2, 6);
	});

	it('keeps a rare word hoverable and never lets one exceed the cap', () => {
		expect(dotRadius(1, 10_000)).toBeGreaterThanOrEqual(3);
		expect(dotRadius(10_000, 10_000)).toBe(11);
		expect(dotRadius(20_000, 10_000)).toBe(11);
	});

	it('fills the spread mark more for a word spread more evenly', () => {
		expect(spreadFill(0.1)).toBeGreaterThan(spreadFill(0.9));
		expect(spreadFill(0)).toBe(1);
		expect(spreadFill(1)).toBe(0);
	});
});
