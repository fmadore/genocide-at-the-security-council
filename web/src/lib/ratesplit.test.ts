/**
 * What the drawn two-rate split decides.
 *
 * Ways to be wrong while looking right: an unaccepted split drawn as a
 * finding, the independent-speech p-value standing in for the block one, a
 * p-value at the simulation floor printed as if measured, the token rate drawn
 * per word beside an axis per 100,000 words, and a unit with no split drawn as
 * a flat line.
 */

import { describe, expect, it } from 'vitest';
import {
	RATE_EXPORT_COLUMNS,
	annualPoints,
	formatP,
	formatRate,
	isStep,
	pFloor,
	rateCeiling,
	rateExportRows,
	rateStep,
	rateSteps,
	valueTicks,
	verdict,
	yearTicks
} from './ratesplit';
import type { RateStep } from './ratesplit';
import type { ChangePoints, RateBreak } from './types';

const periods = Array.from({ length: 81 }, (_, i) => 1946 + i);

function found(extra: Partial<RateBreak> = {}): RateBreak {
	return {
		index: 32,
		label: '1978',
		family: 'binomial',
		gain: 1075,
		null: 'meeting_block_permutation',
		blocks: 9919,
		p_value: 0.0005,
		p_value_independent: 0.0005,
		alpha: 0.025,
		accepted: true,
		before: 0.0059,
		before_ci95: [0.0052, 0.0067],
		after: 0.0307,
		after_ci95: [0.0298, 0.0316],
		ratio: 5.19,
		counts: [248, 4328],
		exposure: [41850, 140834],
		...extra
	};
}

function breaks(series: Record<string, RateBreak | null>): ChangePoints {
	return {
		meta: { script: '04_series.py', generated: 'x', lexicon_version: 8 },
		method: 'm',
		parameters: { min_size: 5 },
		caveat: 'c',
		series: {
			genocide: {
				speech_rate: [
					{
						index: 30,
						label: '1976',
						gain: 1,
						p_value: 0.01,
						before: 0.01,
						after: 0.02,
						ratio: 2,
						interval_start: 28,
						interval_stop: 33
					}
				]
			}
		},
		inference: {
			method: 'm',
			null: 'meeting_block_permutation',
			familywise_alpha: 0.05,
			per_test_alpha: 0.025,
			correction: 'Bonferroni across 2 planned rate tests',
			trials: 2000,
			caveat: 'c',
			series: { genocide: series }
		}
	};
}

const step = (extra: Partial<RateBreak> = {}, unit: 'speech_rate' | 'token_rate' = 'speech_rate') =>
	rateStep(unit, found(extra), periods, 2000) as RateStep;

describe('the steps', () => {
	it('spans the whole series, split where the artefact labels the later segment', () => {
		const s = step();
		expect(s.start).toBe(1946);
		expect(s.end).toBe(2027);
		expect(s.split).toBe(1978);
		expect(s.before).toEqual({ value: 0.0059, low: 0.0052, high: 0.0067 });
	});

	it('draws the token rate per 100,000 words, matching its axis', () => {
		const s = step(
			{ before: 2.9e-5, before_ci95: [2.7e-5, 3.1e-5], after: 1.2e-4, after_ci95: [1.1e-4, 1.3e-4] },
			'token_rate'
		);
		expect(s.before.value).toBeCloseTo(2.9, 9);
		expect(s.after.high).toBeCloseTo(13, 9);
		expect(formatRate('token_rate', s.before.value)).toBe('2.90');
		expect(formatRate('speech_rate', 0.0307)).toBe('3.07%');
	});

	it('keeps a unit with no split as a refusal, and leaves out an absent unit', () => {
		const rows = rateSteps(breaks({ speech_rate: null }), periods);
		expect(rows).toHaveLength(1);
		expect(isStep(rows[0]!)).toBe(false);
		expect(rateStep('token_rate', undefined, periods, 2000)).toBeNull();
	});

	it('scales the panel to the highest bound or yearly point, never below them', () => {
		const s = step();
		expect(rateCeiling(s)).toBeGreaterThan(0.0316);
		expect(rateCeiling(s, [0.05, null])).toBeGreaterThan(0.05);
	});
});

describe('the verdict', () => {
	it('says an accepted split clears the threshold, block p first, independent beside it', () => {
		const text = verdict(step({ p_value: 0.004, p_value_independent: 0.0005 }));
		expect(text).toMatch(/clears the corrected threshold of 0\.025/);
		expect(text).not.toMatch(/does not clear/);
		expect(text.indexOf('0.0040')).toBeLessThan(text.indexOf('0.0005'));
		expect(text).toMatch(/whole meetings moved between years/);
		expect(text).toMatch(/speeches treated as independent/);
	});

	it('says an unaccepted split does not clear it', () => {
		const s = step({ accepted: false, p_value: 0.31, p_value_independent: 0.12 });
		expect(s.accepted).toBe(false);
		expect(verdict(s)).toMatch(/does not clear the corrected threshold/);
		expect(verdict(s)).toMatch(/p = 0\.3100/);
	});

	it('marks a p-value at the floor of the simulations', () => {
		expect(pFloor(2000)).toBe(0.0005);
		expect(step().atFloor).toBe(true);
		expect(verdict(step())).toMatch(/p ≤ 0\.0005/);
		expect(step({ p_value: 0.004 }).atFloor).toBe(false);
		expect(formatP(0.0005, true)).toBe('≤ 0.0005');
	});

	it('names the independent null alone where the artefact used no blocks', () => {
		const text = verdict(step({ null: 'independent_parametric', blocks: null, p_value: 0.01 }));
		expect(text).toMatch(/speeches treated as independent\)\.$/);
		expect(text).not.toMatch(/whole meetings/);
	});
});

describe('the yearly dots', () => {
	it('keeps a withheld year as null rather than zero', () => {
		const points = annualPoints(
			{
				periods: [1946, 1947],
				terms: {
					genocide: {
						speeches: [1, 0],
						speech_rate: [0.01, null],
						speech_rate_low: [],
						speech_rate_high: [],
						token_rate: [1.5, null]
					}
				}
			},
			'speech_rate'
		);
		expect(points).toEqual([
			{ year: 1946, value: 0.01 },
			{ year: 1947, value: null }
		]);
		expect(annualPoints(null, 'token_rate')).toEqual([]);
	});
});

describe('the download', () => {
	it('carries the test the plate draws, a no-split unit as empty cells, and the exploratory rows', () => {
		const rows = rateExportRows(breaks({ speech_rate: found(), token_rate: null }));
		expect(rows.every((r) => r.length === RATE_EXPORT_COLUMNS.length)).toBe(true);
		const at = (name: string) => RATE_EXPORT_COLUMNS.indexOf(name);
		expect(rows.map((r) => r[at('method')])).toEqual([
			'two_rate_test',
			'two_rate_test',
			'exploratory'
		]);
		expect(rows[0]![at('rate_before_ci95_low')]).toBe(0.0052);
		expect(rows[0]![at('accepted')]).toBe(true);
		expect(rows[1]![at('rate_before')]).toBeNull();
		expect(rows[2]![at('interval_start')]).toBe(28);
	});
});

describe('ticks', () => {
	it('places year and value ticks inside the span', () => {
		expect(yearTicks(1946, 2027, 20)).toEqual([1960, 1980, 2000, 2020]);
		expect(valueTicks(0.034)).toEqual([0, 0.01, 0.02, 0.03]);
		expect(valueTicks(0)).toEqual([0]);
	});
});
