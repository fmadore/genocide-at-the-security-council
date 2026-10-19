/**
 * What "Cases over time" decides, apart from how it is drawn.
 *
 * Three ways for the figure to mislead while looking right: a no-case category
 * stacked as though it were a situation, a colour that means a different case in
 * different years, and a share drawn over a handful of occurrences. The cases
 * below are those, plus the file that leaves the page.
 */

import { describe, expect, it } from 'vitest';
import {
	OTHER_CASES,
	TIMELINE_COLUMNS,
	timelineExportRows,
	timelineLink,
	timelinePlan
} from './timeline';
import type { Usage, UsageReferent, UsageTimeline } from './types';

const referent = (id: string, kind = 'case'): UsageReferent => ({
	id,
	label: id.replace(/_/g, ' '),
	description: '',
	kind,
	iso3: '',
	years: '',
	since: 1,
	retired_in: null,
	occurrences: 0,
	retired: false,
	superseded_by: ''
});

function corpus(timeline: UsageTimeline, minimum = 4): Usage {
	return {
		referents: [
			referent('rwanda'),
			referent('bosnia'),
			referent('gaza'),
			referent('holocaust', 'historical'),
			referent('genocide_convention_law', 'meta'),
			referent('other', 'reserved')
		],
		minimum_occurrences: minimum,
		timeline
	} as unknown as Usage;
}

const year = (y: number, yes: number, no: number, unclear = 0) => ({
	year: y,
	eligible: yes + no + unclear,
	concrete_case: { yes, no, unclear }
});

const cell = (y: number, referent: string, count: number, contested = 0) => ({
	year: y,
	referent,
	count,
	contested
});

const DATA = corpus({
	answers: ['yes', 'no', 'unclear'],
	years: [year(1994, 6, 1), year(1995, 0, 0), year(1996, 2, 4)],
	cells: [
		cell(1994, 'rwanda', 5),
		cell(1994, 'genocide_convention_law', 1),
		cell(1994, 'holocaust', 1),
		cell(1996, 'bosnia', 1),
		cell(1996, 'gaza', 1),
		cell(1996, 'other', 1),
		cell(1996, 'genocide_convention_law', 3)
	]
});

describe('the stacked cases', () => {
	it('stacks cases and historical referents, never the no-case categories', () => {
		const plan = timelinePlan(DATA, 3);
		expect(plan.series.map((s) => s.id)).toEqual(['rwanda', 'bosnia', 'gaza', OTHER_CASES]);
		expect(plan.series.find((s) => s.id === 'rwanda')!.counts).toEqual([5, 0, 0]);
	});

	it('pools what falls outside the leading cases, `other` included, as one remainder', () => {
		const plan = timelinePlan(DATA, 3);
		// Holocaust (1 in 1994) and `other` (1 in 1996) are below the three leaders.
		expect(plan.series.at(-1)).toMatchObject({ id: OTHER_CASES, counts: [1, 0, 1], total: 2 });
		expect(plan.pooled).toEqual([
			[{ label: 'holocaust', count: 1 }],
			[],
			[{ label: 'other', count: 1 }]
		]);
	});

	it('chooses the leaders over the whole run, so a colour means one case throughout', () => {
		const plan = timelinePlan(DATA, 1);
		expect(plan.series.map((s) => s.id)).toEqual(['rwanda', OTHER_CASES]);
	});
});

describe('the no-case share', () => {
	it('is drawn where the year can carry it and withheld where it cannot', () => {
		const plan = timelinePlan(DATA);
		expect(plan.noCase).toEqual([1, 0, 4]);
		expect(plan.eligible).toEqual([7, 0, 6]);
		expect(plan.noCaseShare[0]).toBeCloseTo(1 / 7);
		expect(plan.noCaseShare[1]).toBeNull();
		expect(plan.noCaseShare[2]).toBeCloseTo(4 / 6);
		expect(timelinePlan(corpus(DATA.timeline, 7)).noCaseShare).toEqual([1 / 7, null, null]);
	});

	it('refuses to draw an empty run', () => {
		expect(timelinePlan(corpus({ answers: [], years: [], cells: [] })).refusal).toBe('no-timeline');
	});
});

describe('links and the download', () => {
	it('opens one case in one year, and nothing for the pooled remainder', () => {
		expect(timelineLink('rwanda', 1994)).toBe('referent=rwanda&from=1994&to=1994');
		expect(timelineLink(OTHER_CASES, 1994)).toBeNull();
	});

	it('writes every cell with its year, and an empty year as one row', () => {
		const rows = timelineExportRows(DATA);
		for (const cells of rows) expect(cells).toHaveLength(TIMELINE_COLUMNS.length);
		expect(rows.filter((cells) => cells[0] === 1995)).toEqual([
			[1995, 0, 0, 0, 0, null, null, null, null, null]
		]);
		expect(rows.filter((cells) => cells[0] === 1996)).toHaveLength(4);
		expect(rows.find((cells) => cells[5] === 'genocide_convention_law')).toEqual([
			1994,
			7,
			6,
			1,
			0,
			'genocide_convention_law',
			'genocide convention law',
			'meta',
			1,
			0
		]);
	});
});
