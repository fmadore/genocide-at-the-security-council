/**
 * What the year x month grid decides, tested apart from how it is drawn.
 *
 * `docs/PLAN.md` §7's fifth item names two ways this figure can be wrong while
 * looking right, and both are arithmetic:
 *
 * **A gap drawn as white.** 53 of the 384 months hold too few speeches for a
 * rate. White is the colour a zero has, so a withheld cell that reaches the
 * renderer carrying `0` is published as a measurement — the `?? 0` failure the
 * actor view shipped and fixed. The tests below check that a withheld cell
 * carries no number at all, and that its state says which kind of silence it is.
 *
 * **The column read taken as a margin of the grid.** Pooling thirty-two Junes
 * gives a denominator no cell has. `calendar()` is scaled inside itself, and the
 * test that matters is that its range never comes from `grid()`.
 */

import { describe, expect, it } from 'vitest';
import {
	at,
	calendar,
	calendarRows,
	grid,
	gridRows,
	monthLabel,
	tone,
	units,
	type Unit
} from './heatmap';
import type { CalendarMeasure, MonthlyMeasure, MonthlySeries } from './types';

const meta = { script: '04_series.py', generated: '2026-08-10T00:00:00Z', lexicon_version: 2 };

const YEARS = [1992, 1993];
const PERIODS = YEARS.flatMap((year) =>
	Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`)
);

/** Every month holds 200 speeches except the two named, which hold too few. */
function corpus(short: string[] = ['1992-02'], empty: string[] = []): number[] {
	return PERIODS.map((period) => (empty.includes(period) ? 0 : short.includes(period) ? 40 : 200));
}

function measure(rates: (number | null)[], extra: Partial<MonthlyMeasure> = {}): MonthlyMeasure {
	return {
		speeches: rates.map((rate) => (rate === null ? 1 : Math.round(rate * 200))),
		speech_rate: rates,
		occurrences: rates.map(() => 7),
		token_rate: rates.map((rate) => (rate === null ? null : rate * 100)),
		tier: 'core',
		register: 'core',
		...extra
	};
}

function calendarBlock(extra: Partial<CalendarMeasure> = {}): CalendarMeasure {
	const twelve = <T>(value: T) => Array.from({ length: 12 }, () => value);
	return {
		kind: 'terms',
		held: twelve(8000),
		tokens: twelve(5_000_000),
		speeches: twelve(200),
		speech_rate: [0.02, 0.02, 0.02, 0.029, 0.02, 0.06, 0.023, 0.02, 0.02, 0.02, 0.02, 0.05],
		sufficient: twelve(true),
		occurrences: twelve(300),
		token_rate: twelve(6),
		excluding: {
			held: twelve(7000),
			tokens: twelve(4_000_000),
			speeches: twelve(180),
			speech_rate: [0.02, 0.02, 0.02, 0.027, 0.02, 0.0587, 0.022, 0.02, 0.02, 0.02, 0.02, 0.05],
			sufficient: twelve(true)
		},
		agenda: Array.from({ length: 12 }, (_, i) =>
			i === 5 || i === 11
				? [{ item: 'International Tribunals', speeches: 213, share: 0.36 }]
				: [{ item: 'Protection Of Civilians', speeches: 43, share: 0.21 }]
		),
		...extra
	};
}

function payload(options: Partial<MonthlySeries> = {}): MonthlySeries {
	const speeches = options.corpus?.speeches ?? corpus();
	const sufficient = options.sufficient ?? speeches.map((held) => held >= 100);
	// Deliberately not the calendar block's range: a test that the two figures
	// are scaled apart is worth nothing if the fixture gives them one maximum.
	const rates = sufficient.map((ok, i) => (ok ? 0.005 + (i % 6) * 0.005 : null));
	return {
		meta,
		freq: 'month',
		periods: PERIODS,
		corpus: {
			speeches,
			tokens: speeches.map((held) => held * 1000),
			meetings: speeches.map(() => 12)
		},
		sufficient,
		terms: { genocide: measure(rates) },
		registers: {},
		sets: {
			atrocity_core: measure(rates, {
				occurrences: undefined,
				token_rate: undefined,
				members: ['genocide', 'war_crimes']
			})
		},
		years: YEARS,
		months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
		minimum_speeches: 100,
		minimum_speeches_rule: 'withheld below 100 speeches',
		informative_zero_minimum: 96,
		corpus_speech_prevalence: 0.0308,
		coverage: {
			months: 24,
			months_observed: 24,
			months_at_minimum: sufficient.filter(Boolean).length,
			speeches: speeches.reduce((a, b) => a + b, 0),
			speeches_at_minimum: 0,
			share_at_minimum: 0.97
		},
		month_of_year: {
			months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
			rule: 'A calendar month pooled across every year.',
			excluded_years: [1994, 1995],
			excluding_rule: 'The same twelve figures with 1994 and 1995 dropped.',
			agenda_column: 'agenda_item_manual',
			agenda_rule: 'The agenda items behind each month.',
			measures: { genocide: calendarBlock(), atrocity_core: calendarBlock({ kind: 'sets' }) }
		},
		...options
	};
}

describe('the grid', () => {
	it('covers every month of every year', () => {
		const plan = grid({ data: payload(), measure: 'genocide' });
		expect(plan.cells).toHaveLength(24);
		expect(at(plan, 1993, 12)?.period).toBe('1993-12');
	});

	it('gives a withheld cell no number to be drawn with', () => {
		const plan = grid({ data: payload(), measure: 'genocide' });
		const short = at(plan, 1992, 2)!;
		expect(short.state).toBe('withheld');
		expect(short.value).toBeNull();
		// The weight is what a renderer reaches for. Zero here is not a rate of
		// zero: the state says the cell is not drawn at all, and every consumer
		// must branch on that before it reads a weight.
		expect(short.weight).toBe(0);
	});

	it('keeps a withheld cell’s counts, because a count is a fact', () => {
		const plan = grid({ data: payload(), measure: 'genocide' });
		const short = at(plan, 1992, 2)!;
		expect(short.held).toBe(40);
		expect(short.speeches).toBe(1);
	});

	it('separates a month nobody spoke in from one with too few speeches', () => {
		const speeches = corpus(['1992-02'], ['1992-03']);
		const plan = grid({
			data: payload({ corpus: { speeches, tokens: speeches, meetings: speeches } }),
			measure: 'genocide'
		});
		expect(at(plan, 1992, 2)?.state).toBe('withheld');
		expect(at(plan, 1992, 3)?.state).toBe('unobserved');
		expect(plan.withheld).toBe(1);
		expect(plan.unobserved).toBe(1);
	});

	it('anchors the ramp at zero rather than at the smallest month', () => {
		const data = payload();
		const rates: (number | null)[] = data.sufficient.map((ok) => (ok ? 0.04 : null));
		rates[0] = 0.05;
		rates[2] = 0.04;
		const plan = grid({
			data: { ...data, terms: { genocide: measure(rates) } },
			measure: 'genocide'
		});
		expect(plan.high).toBeCloseTo(0.05);
		// Anchored on the observed minimum, 0.04 would sit at the bottom of the
		// ramp and read as an empty month. Anchored at zero it sits at four fifths.
		expect(at(plan, 1992, 3)?.weight).toBeCloseTo(0.8);
	});

	it('spreads colour on the square root and keeps the length linear', () => {
		const plan = grid({ data: payload(), measure: 'genocide' });
		for (const cell of plan.cells) {
			if (cell.state === 'drawn') expect(cell.tone).toBeCloseTo(Math.sqrt(cell.weight));
		}
		// Monotone and unclipped: the order of every cell survives the transform,
		// and the strongest is still the strongest rather than one of several at a
		// ceiling. A ramp that capped would hide how far past it a cell went.
		expect(tone(0)).toBe(0);
		expect(tone(1)).toBe(1);
		expect(tone(0.115)).toBeGreaterThan(0.115);
	});

	it('gives a withheld cell no tone either', () => {
		const plan = grid({ data: payload(), measure: 'genocide' });
		expect(at(plan, 1992, 2)?.tone).toBe(0);
	});

	it('never lets a withheld cell into the range', () => {
		const data = payload();
		// A rate written beside a false `sufficient` must not reach the scale: it
		// would set the top of the ramp and flatten every cell that is drawn.
		const smuggled = measure(data.sufficient.map((ok) => (ok ? 0.02 : 0.9)));
		const plan = grid({ data: { ...data, terms: { genocide: smuggled } }, measure: 'genocide' });
		expect(plan.high).toBeCloseTo(0.02);
		expect(at(plan, 1992, 2)?.value).toBeNull();
	});

	it('refuses a measure the artefact does not hold', () => {
		const plan = grid({ data: payload(), measure: 'nonesuch' });
		expect(plan.refusal).toBe('no-measure');
		expect(plan.cells).toEqual([]);
	});

	it('reports that nothing is drawable rather than drawing an empty grid', () => {
		const speeches = PERIODS.map(() => 10);
		const plan = grid({
			data: payload({ corpus: { speeches, tokens: speeches, meetings: speeches } }),
			measure: 'genocide'
		});
		expect(plan.refusal).toBe('none-drawable');
		expect(plan.drawn).toBe(0);
	});
});

describe('the units a measure can carry', () => {
	it('offers a per-token rate only where there is an occurrence count', () => {
		const data = payload();
		expect(units(data.terms.genocide)).toEqual(['speech_rate', 'token_rate']);
		// A set is a union of overlapping terms and has no occurrence count at
		// all; offering one would publish a withheld figure as 0.00 per 100,000.
		expect(units(data.sets.atrocity_core)).toEqual(['speech_rate']);
	});

	it('falls back rather than drawing a unit the measure is not in', () => {
		const plan = grid({ data: payload(), measure: 'atrocity_core', unit: 'token_rate' as Unit });
		expect(plan.unit).toBe('speech_rate');
		expect(plan.drawn).toBeGreaterThan(0);
	});
});

describe('the calendar read', () => {
	it('is scaled inside itself, never against the grid', () => {
		const data = payload();
		const column = calendar(data, 'genocide');
		const plan = grid({ data, measure: 'genocide' });
		expect(column.high).toBeCloseTo(0.06);
		expect(plan.high).toBeCloseTo(0.03);
		// The strongest month is the top of its own ramp. Scaled against the grid
		// it would be off the end of the scale; scaled against a shared one, every
		// cell in the grid would be crushed into the bottom fifth.
		expect(column.rows[5].weight).toBe(1);
		expect(column.rows[0].weight).toBeCloseTo(0.02 / 0.06);
	});

	it('carries the pooled denominator, which is not any cell’s', () => {
		const column = calendar(payload(), 'genocide');
		expect(column.rows[0].held).toBe(8000);
	});

	it('publishes the control reading beside the first one', () => {
		const column = calendar(payload(), 'genocide');
		expect(column.excludedYears).toEqual([1994, 1995]);
		expect(column.rows[5].without).toBeCloseTo(0.0587);
	});

	it('names the shared agenda item behind the two strongest months', () => {
		const column = calendar(payload(), 'genocide');
		expect(column.shared).toBe('International Tribunals');
		expect(column.rows[5].agenda[0].speeches).toBe(213);
	});

	it('says nothing when the strongest months have different items behind them', () => {
		const data = payload();
		const block = calendarBlock({
			agenda: Array.from({ length: 12 }, (_, i) => [
				{ item: `Item ${i}`, speeches: 10, share: 0.5 }
			])
		});
		const column = calendar(
			{ ...data, month_of_year: { ...data.month_of_year, measures: { genocide: block } } },
			'genocide'
		);
		expect(column.shared).toBeNull();
	});

	it('refuses a measure the calendar block does not hold', () => {
		expect(calendar(payload(), 'nonesuch').refusal).toBe('no-measure');
	});
});

describe('what leaves in a file', () => {
	it('exports every measure and every month, not the one on screen', () => {
		const rows = gridRows(payload());
		expect(rows).toHaveLength(2 * 24);
		expect(rows.map((row) => row[3])).toContain('atrocity_core');
	});

	it('keeps a withheld month in the file with its null and its flag', () => {
		const row = gridRows(payload()).find((entry) => entry[0] === '1992-02')!;
		expect(row[8]).toBeNull();
		expect(row[11]).toBe(false);
		// The count survives, so a reader can see what was excluded and why.
		expect(row[5]).toBe(40);
	});

	it('carries the agenda attribution into the calendar file', () => {
		const rows = calendarRows(payload());
		const june = rows.find((row) => row[0] === 6 && row[2] === 'genocide')!;
		expect(june[11]).toBe('International Tribunals');
		expect(june[8]).toBeCloseTo(0.0587);
	});
});

describe('labels', () => {
	it('reads a period as a month and a year', () => {
		expect(monthLabel('2014-06')).toBe('June 2014');
	});
});
