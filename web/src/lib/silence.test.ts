/**
 * What "Who stays silent when others say it" decides, apart from how it is drawn.
 *
 * Two ways for this figure to be wrong while looking right: a withheld share
 * ranked as a zero, which on this figure reads as a delegation that never joined
 * in, and a whole-corpus row mixed with a period's. The cases below are those.
 */

import { describe, expect, it } from 'vitest';
import { EXPORT_COLUMNS, exportRows, plan } from './silence';
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
		expect(gambia.slice(3)).toEqual([12, 0, null, null, null, false]);
	});
});
