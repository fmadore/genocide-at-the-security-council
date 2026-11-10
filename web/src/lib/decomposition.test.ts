/**
 * What "Agenda or usage?" decides, apart from how it is drawn.
 *
 * Ways for this figure to be wrong while looking right: a part drawn on the
 * wrong side of the zero line, parts that do not add to the change drawn as if
 * they did, a thin decade drawn at full weight, a part-decade passed off as a
 * whole one, and a download that holds only the grouping on screen.
 */

import { describe, expect, it } from 'vitest';
import {
	ADDITIVITY_TOLERANCE,
	EXPORT_COLUMNS,
	PARTS_PARAM,
	THIN_USING,
	availableSplits,
	decadeBases,
	decadeLabel,
	defaultPair,
	equation,
	exportRows,
	incompleteEnd,
	isThin,
	plan,
	pp,
	readPartsSplit,
	residual,
	sharedDomain,
	tickText,
	ticks,
	writePartsSplit
} from './decomposition';
import type { AnnualBase } from './decomposition';
import type { Decomposition, DecompositionRow } from './types';

const meta = { script: '04_series.py', generated: '2026-11-03T00:00:00Z' };

function row(
	from: number,
	composition: number,
	within: number,
	extra: Partial<DecompositionRow> = {}
): DecompositionRow {
	return {
		from,
		to: from + 10,
		rate_from: 0.01,
		rate_to: 0.01 + composition + within,
		change: Number((composition + within).toFixed(6)),
		composition,
		within,
		largest: [{ group: 'A', contribution: composition + within }],
		group_column: 'agenda_item_manual',
		...extra
	};
}

function payload(splits: Record<string, DecompositionRow[]>): Decomposition {
	return {
		meta,
		term: 'genocide',
		unit: 'speech_rate',
		periods: 'decade',
		method: 'Kitagawa',
		splits
	};
}

/** Years 1946–2026, 1,000 speeches a year; `using` per decade spread evenly. */
function annual(usingByDecade: Record<number, number>, lastDate?: string): AnnualBase {
	const periods: number[] = [];
	for (let year = 1946; year <= 2026; year += 1) periods.push(year);
	const years = (decade: number) => periods.filter((y) => Math.floor(y / 10) * 10 === decade);
	const using = periods.map((year) => {
		const decade = Math.floor(year / 10) * 10;
		const total = usingByDecade[decade] ?? 0;
		const here = years(decade);
		// Put the remainder on the first year so the decade sums exactly.
		return Math.floor(total / here.length) + (year === here[0] ? total % here.length : 0);
	});
	return {
		periods,
		corpus: {
			speeches: periods.map(() => 1000),
			words: periods.map(() => 0),
			meetings: periods.map(() => 0)
		},
		terms: {
			genocide: {
				speeches: using,
				speech_rate: [],
				speech_rate_low: [],
				speech_rate_high: []
			}
		},
		...(lastDate ? { record: { first_date: '1946-01-17', last_date: lastDate } } : {})
	};
}

describe('signs and the sum', () => {
	it('keeps each part on its own side of zero', () => {
		const result = plan({
			data: payload({ agenda_item_manual: [row(1980, 0.021134, -0.005601)] }),
			split: 'agenda_item_manual',
			annual: null
		});
		const [pair] = result.pairs;
		expect(pair!.composition).toBeGreaterThan(0);
		expect(pair!.within).toBeLessThan(0);
		expect(pp(pair!.within)).toBe('−0.56');
		expect(pp(pair!.composition)).toBe('+2.11');
		expect(equation(pair!)).toBe('+1.55 = +2.11 − 0.56');
	});

	it('checks that the parts add to the change, and flags a pair that does not', () => {
		const good = row(1990, 0.004091, -0.00895, { change: -0.004859 });
		const bad = row(2000, 0.001, 0.001, { change: 0.003 });
		expect(Math.abs(residual(good))).toBeLessThanOrEqual(ADDITIVITY_TOLERANCE);
		const result = plan({
			data: payload({ agenda_item_manual: [good, bad] }),
			split: 'agenda_item_manual',
			annual: null
		});
		expect(result.pairs.map((p) => p.adds)).toEqual([true, false]);
		expect(result.pairs[1]!.residual).toBeCloseTo(0.001, 9);
	});

	it('prints zero without a sign', () => {
		expect(pp(0)).toBe('0.00');
		expect(pp(-0.000001)).toBe('0.00');
		expect(tickText(0)).toBe('0');
		expect(tickText(-0.01)).toBe('−1');
		expect(tickText(0.005)).toBe('+0.5');
	});
});

describe('one axis for both groupings', () => {
	it('takes the domain over every split, zero included', () => {
		const data = payload({
			agenda_item_manual: [row(1980, 0.02, -0.005)],
			speaker_group: [row(1980, -0.007, 0.022)]
		});
		expect(sharedDomain(data)).toEqual([-0.007, 0.022]);
		const all = payload({ speaker_group: [row(1980, 0.002, 0.001)] });
		expect(sharedDomain(all)[0]).toBe(0);
	});

	it('ticks on whole steps that cover the domain', () => {
		const out = ticks([-0.010084, 0.022751], 8);
		expect(out[0]).toBeLessThanOrEqual(-0.010084);
		expect(out.at(-1)).toBeGreaterThanOrEqual(0.022751);
		expect(out).toContain(0);
		expect(out.length - 1).toBeLessThanOrEqual(8);
		expect(ticks([-0.010084, 0.022751], 5).length - 1).toBeLessThanOrEqual(5);
	});
});

describe('thin and incomplete decades', () => {
	it('reads speeches and speeches using the word per decade from the annual series', () => {
		const bases = decadeBases(annual({ 1940: 22, 1950: 14, 1960: 108 }), 'genocide');
		expect(bases.get(1940)).toMatchObject({ speeches: 4000, using: 22, first: 1946, last: 1949 });
		expect(bases.get(1950)).toMatchObject({ speeches: 10_000, using: 14 });
		expect(bases.get(2020)).toMatchObject({ first: 2020, last: 2026 });
	});

	it('mutes a pair when either decade has fewer than the threshold using the word', () => {
		const bases = decadeBases(
			annual({ 1940: 22, 1950: 14, 1960: THIN_USING, 1970: 161 }),
			'genocide'
		);
		expect(isThin(bases.get(1940), bases.get(1950))).toBe(true);
		expect(isThin(bases.get(1950), bases.get(1960))).toBe(true);
		expect(isThin(bases.get(1960), bases.get(1970))).toBe(false);
	});

	it('says unknown, not sufficient, where the annual series cannot tell', () => {
		expect(isThin(undefined, undefined)).toBeNull();
		const result = plan({
			data: payload({ agenda_item_manual: [row(1980, 0.01, 0.01)] }),
			split: 'agenda_item_manual',
			annual: null
		});
		expect(result.pairs[0]!.thin).toBeNull();
	});

	it('names a decade the record holds only part of', () => {
		const bases = decadeBases(annual({}), 'genocide');
		expect(decadeLabel(1940, bases.get(1940))).toBe('1940s (1946–49)');
		expect(decadeLabel(1980, bases.get(1980))).toBe('1980s');
		expect(decadeLabel(2020, bases.get(2020))).toBe('2020s (2020–26)');
		expect(decadeLabel(1980, null)).toBe('1980s');
	});

	it('reports where the record stops, with the date when the payload has one', () => {
		const older = annual({});
		expect(incompleteEnd(older, decadeBases(older, 'genocide'))).toEqual({
			decade: 2020,
			lastYear: 2026,
			lastDate: null
		});
		const newer = annual({}, '2026-06-30');
		expect(incompleteEnd(newer, decadeBases(newer, 'genocide'))?.lastDate).toBe('2026-06-30');
	});
});

describe('the grouping control and the address', () => {
	const data = payload({
		speaker_group: [row(1980, 0.01, 0.01)],
		agenda_item_manual: [row(1980, 0.01, 0.01)],
		empty: []
	});

	it('lists the known groupings first and leaves out empty ones', () => {
		expect(availableSplits(data)).toEqual(['agenda_item_manual', 'speaker_group']);
		expect(availableSplits(null)).toEqual([]);
	});

	it('reads only a grouping the payload holds, and writes nothing for the default', () => {
		const available = availableSplits(data);
		expect(readPartsSplit(new URLSearchParams('parts=speaker_group'), available)).toBe(
			'speaker_group'
		);
		expect(readPartsSplit(new URLSearchParams('parts=nonsense'), available)).toBe(
			'agenda_item_manual'
		);
		const base = new URLSearchParams('unit=speech_rate');
		expect(writePartsSplit(base, 'agenda_item_manual', available).has(PARTS_PARAM)).toBe(false);
		expect(writePartsSplit(base, 'speaker_group', available).get(PARTS_PARAM)).toBe(
			'speaker_group'
		);
		expect(base.get('unit')).toBe('speech_rate');
	});

	it('refuses rather than drawing an empty plate', () => {
		expect(plan({ data: null, split: 'x', annual: null }).refusal).toBe('no-splits');
		expect(plan({ data: payload({}), split: 'x', annual: null }).refusal).toBe('no-splits');
	});

	it('opens on the largest net change', () => {
		const result = plan({
			data: payload({
				agenda_item_manual: [row(1960, 0.001, 0.001), row(1980, 0.02, -0.005), row(1990, 0, -0.005)]
			}),
			split: 'agenda_item_manual',
			annual: null
		});
		expect(defaultPair(result.pairs)).toBe(1);
		expect(defaultPair([])).toBe(-1);
	});
});

describe('the download', () => {
	it('holds every row of both groupings, with the decade bases and the thin flag', () => {
		const data = payload({
			agenda_item_manual: [row(1950, 0.008, -0.001), row(1940, 0.0006, -0.0006)],
			speaker_group: [row(1940, 0.0002, -0.0002), row(1950, 0.002, 0.005)]
		});
		const rows = exportRows(data, annual({ 1940: 22, 1950: 14, 1960: 108 }));
		expect(rows).toHaveLength(4);
		expect(rows.every((r) => r.length === EXPORT_COLUMNS.length)).toBe(true);
		const at = (name: string) => EXPORT_COLUMNS.indexOf(name);
		expect(rows.map((r) => [r[at('split')], r[at('decade_from')]])).toEqual([
			['agenda_item_manual', 1940],
			['agenda_item_manual', 1950],
			['speaker_group', 1940],
			['speaker_group', 1950]
		]);
		expect(rows[0]![at('speeches_from')]).toBe(4000);
		expect(rows[0]![at('speeches_using_from')]).toBe(22);
		expect(rows[0]![at('years_from')]).toBe('1946-1949');
		expect(rows[0]![at('thin')]).toBe(true);
		expect(rows[0]![at('residual')]).toBe(0);
		expect(String(rows[0]![at('largest_groups')])).toMatch(/^A: /);
	});

	it('leaves the bases empty, never zero, without an annual series', () => {
		const rows = exportRows(payload({ speaker_group: [row(1980, 0.01, 0.01)] }), null);
		const at = (name: string) => EXPORT_COLUMNS.indexOf(name);
		expect(rows[0]![at('speeches_from')]).toBeNull();
		expect(rows[0]![at('thin')]).toBeNull();
	});
});
