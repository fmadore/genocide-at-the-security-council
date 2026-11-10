/**
 * What "Who stays silent when others say it" decides, apart from how it is drawn.
 *
 * Two ways for this figure to be wrong while looking right: a withheld share
 * ranked as a zero, which on this figure reads as a delegation that never joined
 * in, and a whole-corpus row mixed with a period's. The cases below are those.
 */

import { describe, expect, it } from 'vitest';
import {
	EXPORT_COLUMNS,
	exportRows,
	niceCeil,
	ordered,
	orderedSummary,
	plan,
	stripAt,
	stripScale
} from './silence';
import type { Countries, Silence, SilenceRow, Speaker } from './types';

const meta = { script: '11_countries.py', generated: '2026-10-19T00:00:00Z', lexicon_version: 8 };

function row(
	name: string,
	exposed: number,
	joined: number,
	period = 'all',
	minimum = 30
): SilenceRow {
	const sufficient = exposed >= minimum;
	const share = joined / exposed;
	return {
		country_org: name,
		period,
		exposed,
		joined,
		share: sufficient ? share : null,
		share_low: sufficient ? Math.max(0, share - 0.05) : null,
		share_high: sufficient ? Math.min(1, share + 0.05) : null,
		sufficient
	};
}

const speaker = (name: string): Speaker => ({
	country_org: name,
	entity_type: 'state',
	iso3: name.slice(0, 3).toUpperCase(),
	un_regional_group: null,
	centroid: null,
	mappable: false,
	speeches: 100,
	first_year: 1946,
	last_year: 2024
});

function corpus(rows: SilenceRow[]): Countries {
	const silence: Silence = {
		measure: 'genocide',
		minimum_meetings: 30,
		informative_zero_minimum: 25,
		rule: 'A meeting counts when another speaker used the word.',
		periods: [
			{
				period: 'all',
				meetings: 1500,
				exposed: 27_000,
				joined: 3_100,
				room_share: 0.115,
				speakers_at_minimum: 3
			},
			{
				period: '1990-1999',
				meetings: 300,
				exposed: 5_000,
				joined: 600,
				room_share: 0.12,
				speakers_at_minimum: 1
			}
		],
		rows
	};
	return {
		meta,
		minimum_speeches: 125,
		minimum_speeches_rule: 'withheld below 125 speeches',
		rate_per_tokens: 100_000,
		centroid_rule: 'Country centroids are navigation aids.',
		iso3_collisions: {},
		periods: [
			{
				key: 'all',
				label: '1946-2024',
				first_year: 1946,
				last_year: 2024,
				speeches: 167_642,
				words: 86_812_574,
				speakers: 708,
				speakers_at_minimum: 200,
				speeches_at_minimum: 160_000
			},
			{
				key: '1990-1999',
				label: '1990-1999',
				first_year: 1990,
				last_year: 1999,
				speeches: 20_000,
				words: 10_000_000,
				speakers: 200,
				speakers_at_minimum: 60,
				speeches_at_minimum: 18_000
			}
		],
		countries: [...new Set(rows.map((r) => r.country_org))].map(speaker),
		standing: { groups: [], seated_groups: [], seated_rule: '', membership_rule: '', rows: [] },
		silence,
		measures: {}
	};
}

const DATA = corpus([
	row('China', 934, 27),
	row('United States of America', 969, 135),
	row('Rwanda', 214, 148),
	row('Gambia', 12, 0),
	row('Rwanda', 40, 30, '1990-1999')
]);

describe('the ranking', () => {
	it('puts the quietest first and never ranks a withheld share', () => {
		const result = plan({ data: DATA, period: 'all', order: 'quietest' });
		expect(result.rows.map((e) => e.row.country_org)).toEqual([
			'China',
			'United States of America',
			'Rwanda'
		]);
		// Gambia was exposed twelve times and joined none: a zero over twelve
		// meetings is what the room's average predicts, so it is counted, not ranked.
		expect(result.withheld).toBe(1);
		expect(result.refusal).toBeNull();
	});

	it('reverses for the most outspoken, and orders by exposure on request', () => {
		expect(plan({ data: DATA, period: 'all', order: 'loudest' }).rows[0]!.row.country_org).toBe(
			'Rwanda'
		);
		expect(plan({ data: DATA, period: 'all', order: 'exposed' }).rows[0]!.row.country_org).toBe(
			'United States of America'
		);
	});

	it('keeps states only on request, and counts the withheld within that selection', () => {
		const mixed = corpus([
			row('China', 934, 27),
			row('United Nations', 696, 76),
			row('Gambia', 12, 0)
		]);
		mixed.countries = mixed.countries.map((s) =>
			s.country_org === 'United Nations' ? { ...s, entity_type: 'un' } : s
		);
		const states = plan({ data: mixed, period: 'all', order: 'quietest', states: true });
		expect(states.rows.map((e) => e.row.country_org)).toEqual(['China']);
		expect(states.withheld).toBe(1);
		expect(plan({ data: mixed, period: 'all', order: 'quietest' }).rows).toHaveLength(2);
	});

	it('keeps a period apart from the whole corpus', () => {
		const decade = plan({ data: DATA, period: '1990-1999', order: 'quietest' });
		expect(decade.rows.map((e) => e.row.exposed)).toEqual([40]);
		expect(decade.summary?.meetings).toBe(300);
	});

	it('says so when nobody reaches the minimum, and refuses a period it does not know', () => {
		const thin = corpus([row('Gambia', 12, 0)]);
		expect(plan({ data: thin, period: 'all', order: 'quietest' }).refusal).toBe('none-sufficient');
		expect(plan({ data: DATA, period: '1800-1809', order: 'quietest' }).refusal).toBe(
			'unknown-period'
		);
	});
});

describe('the download', () => {
	it('carries every row, the withheld ones with their nulls, one cell per column', () => {
		const rows = exportRows(DATA);
		expect(rows).toHaveLength(5);
		for (const cells of rows) expect(cells).toHaveLength(EXPORT_COLUMNS.length);
		const gambia = rows.find((cells) => cells[0] === 'Gambia')!;
		// The ordered columns are empty on a payload that does not carry them.
		expect(gambia.slice(3)).toEqual([
			12,
			0,
			null,
			null,
			null,
			false,
			null,
			null,
			null,
			null,
			null,
			null
		]);
	});
});

/* The figure's sentence is "took the floor after the word had been used". The
   unordered counts say only that someone used it somewhere in the meeting, and
   a third of them are speakers who had finished first. */
describe('the order of speaking', () => {
	const after = (base: SilenceRow, exposed: number, joined: number, minimum = 30): SilenceRow => ({
		...base,
		exposed_after: exposed,
		joined_after: joined,
		share_after: exposed >= minimum ? joined / exposed : null,
		share_after_low: exposed >= minimum ? 0 : null,
		share_after_high: exposed >= minimum ? 1 : null,
		sufficient_after: exposed >= minimum
	});

	it('reads the ordered counts where the artefact carries them', () => {
		const read = ordered(after(row('France', 1054, 118), 599, 97));
		expect([read.exposed, read.joined, read.sufficient]).toEqual([599, 97, true]);
		expect(read.share).toBeCloseTo(97 / 599);
	});

	it('withholds on the ordered denominator, which is the smaller one', () => {
		// Forty meetings where someone said the word; in twenty-five the speaker spoke after.
		const read = ordered(after(row('Zambia', 40, 5), 25, 5));
		expect(read.sufficient).toBe(false);
		expect(read.share).toBeNull();
	});

	it('leaves an older payload exactly as it was', () => {
		const old = row('France', 1054, 118);
		expect(ordered(old)).toBe(old);
		const summary = DATA.silence.periods[0]!;
		expect(orderedSummary(summary)).toBe(summary);
		expect(plan({ data: DATA, period: 'all', order: 'quietest' }).ordered).toBe(false);
	});

	it('ranks on the ordered share and drops a speaker never exposed in order', () => {
		const data: Countries = {
			...DATA,
			silence: {
				...DATA.silence,
				rows: [
					after(row('Loud', 100, 50), 60, 45),
					after(row('Quiet', 100, 10), 80, 4),
					// Always spoke before anyone used the word: nothing to rank or withhold.
					after(row('Early', 50, 0), 0, 0)
				]
			}
		};
		const result = plan({ data, period: 'all', order: 'quietest' });
		expect(result.ordered).toBe(true);
		expect(result.rows.map((entry) => entry.row.country_org)).toEqual(['Quiet', 'Loud']);
		expect(result.rows[0]!.row.exposed).toBe(80);
		expect(result.withheld).toBe(0);
	});
});

describe('the interval strip', () => {
	it('rounds the end up to a printable figure', () => {
		expect(niceCeil(0.339)).toBe(0.5);
		expect(niceCeil(0.21)).toBe(0.25);
		expect(niceCeil(0.106)).toBe(0.2);
		expect(niceCeil(0.05)).toBe(0.05);
		expect(niceCeil(0)).toBe(0);
	});

	it('ends at the 90th-percentile upper bound, not at the outlier', () => {
		const uppers = [0.1, 0.12, 0.14, 0.16, 0.18, 0.2, 0.2, 0.21, 0.22, 0.76];
		const scale = stripScale(uppers);
		expect(scale.end).toBe(0.25);
		expect(scale.clipped).toBe(1);
	});

	it('keeps the room on the strip and ignores withheld rows', () => {
		expect(stripScale([0.01, 0.02, null, undefined], 0.3).end).toBe(0.5);
		expect(stripScale([]).end).toBeGreaterThan(0);
	});

	it('holds a position to the end of the strip', () => {
		expect(stripAt(0.1, 0.2)).toBe('50.00%');
		expect(stripAt(0.7, 0.2)).toBe('100.00%');
		expect(stripAt(-1, 0.2)).toBe('0.00%');
	});
});
