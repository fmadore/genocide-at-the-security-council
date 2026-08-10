/**
 * What the membership view decides, tested apart from how it is drawn.
 *
 * `docs/PLAN.md` §3 names one way this figure can be wrong while looking right,
 * and it is not arithmetic so much as a category error: **a speaker has no
 * single membership**. The elected ten rotate, so shading a delegation with one
 * colour is wrong about the 105 speakers that spoke both from a seat and from
 * outside one — the group that is worth looking at in the first place.
 *
 * The tests below hold the three things that follow. A row is a composition
 * that fills its own denominator; the three records are told apart on integer
 * counts rather than on a float; and no denominator is too small to publish
 * here, because a share of a speaker's own known speeches is a fact about the
 * record rather than an estimate from a sample.
 */

import { describe, expect, it } from 'vitest';
import { categorise, exemplar, exportRows, plan, segments } from './standing';
import type { Countries, Speaker, Standing, StandingRow } from './types';

const meta = { script: '11_countries.py', generated: '2026-08-10T00:00:00Z', lexicon_version: 2 };

const GROUPS = ['P5', 'E10', 'Non-member state', 'UN', 'Non-state'];
const SEATED = ['P5', 'E10'];

function row(name: string, counts: Partial<Record<string, number>>, period = 'all'): StandingRow {
	const groups = Object.fromEntries(GROUPS.map((g) => [g, counts[g] ?? 0]));
	const held = Object.values(groups).reduce((a, b) => a + b, 0);
	const seated = SEATED.reduce((sum, g) => sum + groups[g], 0);
	return {
		country_org: name,
		period,
		held,
		seated,
		seated_share: held > 0 ? seated / held : null,
		groups
	};
}

const speaker = (name: string, extra: Partial<Speaker> = {}): Speaker => ({
	country_org: name,
	entity_type: 'state',
	iso3: name.slice(0, 3).toUpperCase(),
	un_regional_group: 'Asia-Pacific Group',
	centroid: [10, 20],
	mappable: true,
	speeches: 100,
	first_year: 1992,
	last_year: 2023,
	...extra
});

function corpus(rows: StandingRow[], speakers?: Speaker[]): Countries {
	const standing: Standing = {
		groups: GROUPS,
		seated_groups: SEATED,
		seated_rule: 'P5 and E10 are the Charter’s two kinds of membership.',
		membership_rule: 'Membership is a property of a speech, not of a country.',
		rows
	};
	return {
		meta,
		minimum_speeches: 100,
		minimum_speeches_rule: 'withheld below 100 speeches',
		rate_per_tokens: 100_000,
		centroid_rule: 'Country centroids are navigation aids.',
		iso3_collisions: {},
		periods: [
			{
				key: 'all',
				label: '1992-2023',
				first_year: 1992,
				last_year: 2023,
				speeches: 106_302,
				tokens: 66_392_703,
				speakers: 601,
				speakers_at_minimum: 133,
				speeches_at_minimum: 103_236
			}
		],
		countries: speakers ?? [...new Set(rows.map((r) => r.country_org))].map((n) => speaker(n)),
		standing,
		measures: {}
	};
}

describe('the three records', () => {
	it('tells them apart on the counts, not on the share', () => {
		expect(categorise(row('Japan', { E10: 1602, 'Non-member state': 453 }))).toBe('changed');
		expect(categorise(row('Always', { P5: 40 }))).toBe('always');
		expect(categorise(row('Never', { 'Non-member state': 40 }))).toBe('never');
	});

	it('does not call a speaker seated throughout on a rounded share', () => {
		// 9,999,999 of 10,000,000 is a share that prints as 1 and is not one. On
		// the counts it is what it is: a speaker whose status changed.
		const almost = row('Almost', { E10: 9_999_999, 'Non-member state': 1 });
		expect(almost.seated_share).toBeCloseTo(1);
		expect(categorise(almost)).toBe('changed');
	});
});

describe('a row is a composition', () => {
	it('fills the speaker’s own denominator', () => {
		const bands = segments(
			row('Japan', { E10: 1602, 'Non-member state': 453 }),
			GROUPS,
			new Set(SEATED)
		);
		expect(bands).toHaveLength(2);
		expect(bands[0].from).toBe(0);
		expect(bands[bands.length - 1].to).toBe(100);
		expect(bands[0].share).toBeCloseTo(1602 / 2055);
	});

	it('marks which bands are a seat, from the artefact’s own list', () => {
		const bands = segments(
			row('Mixed', { P5: 10, E10: 10, UN: 10, 'Non-state': 10 }),
			GROUPS,
			new Set(SEATED)
		);
		expect(bands.map((b) => b.seated)).toEqual([true, true, false, false]);
	});

	it('leaves an empty group out of the bands and keeps it in the counts', () => {
		const record = row('Only UN', { UN: 12 });
		expect(segments(record, GROUPS, new Set(SEATED))).toHaveLength(1);
		// The zeros survive in the row, because "never in that position" and "the
		// group does not exist" are different statements.
		expect(Object.keys(record.groups)).toHaveLength(5);
		expect(record.groups.P5).toBe(0);
	});
});

describe('the cut', () => {
	const rows = [
		row('Japan', { E10: 1602, 'Non-member state': 453 }),
		row('Rwanda', { E10: 200, 'Non-member state': 100 }),
		row('France', { P5: 900 }),
		row('Yemen', { 'Non-member state': 40 }),
		row('UN Secretariat', { UN: 4709 })
	];

	it('draws the speakers whose status changed, and counts the rest', () => {
		const result = plan({ data: corpus(rows), period: 'all' });
		expect(result.rows.map((entry) => entry.row.country_org)).toEqual(['Japan', 'Rwanda']);
		expect(result.counts).toEqual({ changed: 2, always: 1, never: 2 });
	});

	it('publishes a small denominator, because a count is not an estimate', () => {
		// Yemen gave 40 speeches. Every rate in this artefact is withheld under
		// 100; this figure has no minimum, and that asymmetry is the point.
		const result = plan({ data: corpus(rows), period: 'all', category: 'never' });
		expect(result.rows.map((entry) => entry.row.country_org)).toContain('Yemen');
		expect(result.rows.find((e) => e.row.country_org === 'Yemen')?.row.seated_share).toBe(0);
	});

	it('orders by evidence, then by name, so the table is citable', () => {
		const result = plan({ data: corpus(rows), period: 'all', category: 'all' });
		expect(result.rows.map((entry) => entry.row.country_org)).toEqual([
			'UN Secretariat',
			'Japan',
			'France',
			'Rwanda',
			'Yemen'
		]);
	});

	it('refuses a period the artefact does not hold', () => {
		expect(plan({ data: corpus(rows), period: '1970s' }).refusal).toBe('no-period');
	});

	it('says when a category is empty rather than showing a blank table', () => {
		const only = [row('France', { P5: 900 })];
		expect(plan({ data: corpus(only), period: 'all' }).refusal).toBe('none-in-category');
	});

	it('never mixes periods', () => {
		const mixed = [
			row('Japan', { E10: 100, 'Non-member state': 20 }, 'all'),
			row('Japan', { E10: 60 }, '2010-2019')
		];
		const decade = plan({ data: corpus(mixed), period: 'all', category: 'all' });
		expect(decade.rows).toHaveLength(1);
		expect(decade.rows[0].row.held).toBe(120);
	});
});

describe('the case worth naming', () => {
	it('picks the changed speaker with the most speeches rather than a hard-coded one', () => {
		const rows = [
			row('Japan', { E10: 1602, 'Non-member state': 453 }),
			row('Rwanda', { E10: 200, 'Non-member state': 100 }),
			row('France', { P5: 900 })
		];
		const result = plan({ data: corpus(rows), period: 'all', category: 'all' });
		expect(exemplar(result.rows)?.row.country_org).toBe('Japan');
	});

	it('names nobody when nobody changed', () => {
		const result = plan({
			data: corpus([row('France', { P5: 900 })]),
			period: 'all',
			category: 'all'
		});
		expect(exemplar(result.rows)).toBeNull();
	});
});

describe('what leaves in a file', () => {
	it('carries every speaker, every period and all five counts', () => {
		const rows = [
			row('Japan', { E10: 1602, 'Non-member state': 453 }),
			row('Japan', { E10: 60 }, '2010-2019')
		];
		const exported = exportRows(corpus(rows));
		expect(exported).toHaveLength(2);
		// country, type, period, held, seated, share, record, then the five groups.
		expect(exported[0].slice(-5)).toEqual([0, 1602, 453, 0, 0]);
		expect(exported[0][6]).toBe('changed');
		expect(exported[1][2]).toBe('2010-2019');
	});
});
