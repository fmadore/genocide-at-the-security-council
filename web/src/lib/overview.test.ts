import { describe, expect, it } from 'vitest';
import { densest, loudest, overviewTotals } from './overview';
import type { AnnualSeries, Measure } from './types';

const measure = (over: Partial<Measure> = {}): Measure =>
	({
		speeches: [1, 4, 3],
		speech_rate: [0.1, 0.2, 0.1],
		speech_rate_low: [0, 0, 0],
		speech_rate_high: [1, 1, 1],
		occurrences: [1, 6, 8],
		...over
	}) as Measure;

const series = (speakers?: number): AnnualSeries =>
	({
		meta: { script: '04_series.py', generated: 'fixture', ...(speakers ? { speakers } : {}) },
		freq: 'year',
		periods: [1992, 1994, 2023],
		corpus: { speeches: [10, 20, 30], words: [1000, 2200, 3600], meetings: [2, 3, 4] },
		terms: {}
	}) as unknown as AnnualSeries;

describe('the headline figures', () => {
	it('sums the corpus and the headline measure over every period', () => {
		expect(overviewTotals(series(2), measure())).toEqual({
			speeches: 60,
			words: 6800,
			meetings: 9,
			bearing: 8,
			occurrences: 15,
			speakers: 2
		});
	});

	it('counts no occurrences and no speakers where the artefact carries none', () => {
		const totals = overviewTotals(series(), measure({ occurrences: undefined }));
		expect(totals.occurrences).toBe(0);
		expect(totals.speakers).toBe(0);
	});
});

describe('the two years the page names', () => {
	const years = [1992, 1994, 2023];

	it('names the year with the highest share and the year with the most occurrences', () => {
		// They differ in the fixture, which is the point the page makes.
		expect(densest(years, measure())).toBe(1994);
		expect(loudest(years, measure())).toBe(2023);
	});

	it('takes the first year on a tie', () => {
		expect(densest(years, measure({ speech_rate: [0.3, 0.3, 0.1] }))).toBe(1992);
		expect(loudest(years, measure({ occurrences: [2, 9, 9] }))).toBe(1994);
	});

	it('names no year for a measure with no occurrence count', () => {
		expect(loudest(years, measure({ occurrences: undefined }))).toBeUndefined();
	});
});
