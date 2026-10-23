import { describe, expect, it } from 'vitest';
import type { UsageVictims } from './types';
import { actorPlan, decadePlan, namingPlan, tableStatus } from './victims';

/**
 * Three peoples and one group that names none, over two decades and three
 * speakers: enough for a cap to bite, a tie to break and a share to withhold.
 */
const victims: UsageVictims = {
	table: { rows: 650, checked: 0 },
	groups: [
		{ group: 'Palestinians', unspecified: false, count: 6, actors: 2 },
		{ group: 'Civilians and populations (unspecified)', unspecified: true, count: 4, actors: 2 },
		{ group: 'Tutsi', unspecified: false, count: 3, actors: 1 },
		{ group: 'Jews', unspecified: false, count: 1, actors: 1 }
	],
	decades: [
		{ decade: 1990, eligible: 10, people: 3, unspecified: 1, ungrouped: 1, none: 5 },
		{ decade: 2000, eligible: 40, people: 7, unspecified: 3, ungrouped: 0, none: 30 }
	],
	cells: [
		{ group: 'Tutsi', decade: 1990, count: 3 },
		{ group: 'Civilians and populations (unspecified)', decade: 1990, count: 1 },
		{ group: 'Palestinians', decade: 2000, count: 6 },
		{ group: 'Jews', decade: 2000, count: 1 },
		{ group: 'Civilians and populations (unspecified)', decade: 2000, count: 3 }
	],
	by_actor: [
		{ group: 'Palestinians', actor: 'Algeria', count: 4 },
		{ group: 'Palestinians', actor: 'Bolivia', count: 2 },
		{ group: 'Tutsi', actor: 'Rwanda', count: 3 },
		{ group: 'Jews', actor: 'Bolivia', count: 1 },
		{ group: 'Civilians and populations (unspecified)', actor: 'Algeria', count: 4 }
	]
};

describe('who is named, decade by decade', () => {
	it('ranks the peoples, then puts the groups that name none under a rule', () => {
		const plan = decadePlan(victims);
		expect(plan.columns.map((c) => c.label)).toEqual(['1990s', '2000s']);
		expect(plan.rows.map((r) => r.label)).toEqual([
			'Palestinians',
			'Tutsi',
			'Jews',
			'Civilians and populations (unspecified)'
		]);
		expect(plan.ruleAt).toBe(3);
		expect(plan.rows[0]!.cells).toEqual([0, 6]);
		expect(plan.high).toBe(6);
		expect(plan.refusal).toBeNull();
	});

	it('caps the peoples and says what the cap left out', () => {
		const plan = decadePlan(victims, 1);
		expect(plan.rows.map((r) => r.label)).toEqual([
			'Palestinians',
			'Civilians and populations (unspecified)'
		]);
		expect(plan.hidden).toEqual({ rows: 2, occurrences: 4 });
	});
});

describe('which delegations name which people', () => {
	it('ranks speakers on peoples alone and breaks a tie on the name', () => {
		const plan = actorPlan(victims, (actor) => actor.toUpperCase());
		// Algeria's four unspecified occurrences do not count towards its rank.
		expect(plan.rows.map((r) => [r.key, r.total])).toEqual([
			['Algeria', 4],
			['Bolivia', 3],
			['Rwanda', 3]
		]);
		expect(plan.rows[0]!.label).toBe('ALGERIA');
		expect(plan.columns.map((c) => c.key)).toEqual(['Palestinians', 'Tutsi', 'Jews']);
		expect(plan.rows[1]!.cells).toEqual([2, 0, 1]);
		expect(plan.ruleAt).toBe(-1);
	});
});

describe('naming a people, or not', () => {
	it('gives counts for every decade and shares only above the minimum', () => {
		const [nineties, noughties] = namingPlan(victims, 20);
		expect(nineties!.counts.none).toBe(5);
		expect(nineties!.shares).toBeNull();
		expect(noughties!.shares).toEqual({
			people: 7 / 40,
			unspecified: 3 / 40,
			ungrouped: 0,
			none: 30 / 40
		});
	});
});

describe('the table the figures rest on', () => {
	it('says it was drafted by AI, and how much a person has checked', () => {
		expect(tableStatus(victims)).toBe(
			'The 650 rows of the grouping table were drafted by AI and none has yet been checked by a person.'
		);
		expect(tableStatus({ ...victims, table: { rows: 650, checked: 120 } })).toBe(
			'The grouping table was drafted by AI; 120 of its 650 rows have been checked by a person.'
		);
	});

	it('refuses to draw a grid with nothing in it', () => {
		const empty = { ...victims, groups: [], cells: [], by_actor: [] };
		expect(decadePlan(empty).refusal).toBe('no-victims');
		expect(actorPlan(empty, (a) => a).refusal).toBe('no-victims');
	});
});
