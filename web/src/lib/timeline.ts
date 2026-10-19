/**
 * The decisions behind "Cases over time", kept out of the component.
 *
 * The figure answers the periodisation question with the model's labels: which
 * cases the word was applied to in each year, and how much of its use was
 * applied to no case at all — the legal category, a tribunal's or an office's
 * name, a general formula. Three decisions are made here:
 *
 * **Only cases are stacked.** Referents of kind `meta` are the no-case uses
 * themselves, and stacking them beside Rwanda would add a category of use to a
 * list of situations. They are shown as the share in the panel below instead.
 * `other` (a case the controlled list does not hold yet) joins the pooled
 * remainder, so it is never presented as one situation.
 *
 * **The leading cases are chosen over the whole run**, not per year, so a colour
 * means one case on the whole chart.
 *
 * **The no-case share is withheld in a thin year**, below the artefact's own
 * `minimum_occurrences`, on the rule every other share on this page follows:
 * the counts are drawn at every denominator, the share only where it can carry
 * a reading.
 */

import { CONCORDANCE_DEFAULTS, concordanceParams } from './concordance';
import type { Usage, UsageReferent } from './types';

/** Kinds of referent that name a situation the word can be applied to. */
const CASE_KINDS = new Set(['case', 'historical']);

/** The pooled remainder's series id. Not a referent identifier: no link opens it. */
export const OTHER_CASES = '__other_cases';

export interface TimelineSeries {
	id: string;
	label: string;
	/** One count per year in `years`, zeros included. */
	counts: number[];
	total: number;
}

export interface TimelinePlan {
	years: number[];
	/** The leading cases in order of total, then the pooled remainder last. */
	series: TimelineSeries[];
	/**
	 * What the pooled remainder holds in each year, largest first, so a reader
	 * of a year before 1992 — where most cases fall outside the leaders — can
	 * still see which they were.
	 */
	pooled: { label: string; count: number }[][];
	/** Eligible occurrences per year, and how many the model applied to no case. */
	eligible: number[];
	noCase: number[];
	/** `noCase / eligible`, or null where the year falls below `minimum`. */
	noCaseShare: (number | null)[];
	minimum: number;
	refusal: 'no-timeline' | null;
}

export function timelinePlan(data: Usage, leading = 7): TimelinePlan {
	const minimum = data.minimum_occurrences;
	const years = data.timeline.years.map((row) => row.year);
	if (!years.length) {
		return {
			years,
			series: [],
			pooled: [],
			eligible: [],
			noCase: [],
			noCaseShare: [],
			minimum,
			refusal: 'no-timeline'
		};
	}
	const index = new Map(years.map((year, position) => [year, position]));
	const referents = new Map<string, UsageReferent>(data.referents.map((r) => [r.id, r]));
	const isCase = (id: string) => CASE_KINDS.has(referents.get(id)?.kind ?? '') || id === 'other';

	const totals = new Map<string, number>();
	for (const cell of data.timeline.cells) {
		if (!isCase(cell.referent)) continue;
		totals.set(cell.referent, (totals.get(cell.referent) ?? 0) + cell.count);
	}
	const chosen = [...totals.entries()]
		.filter(([id]) => id !== 'other')
		.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
		.slice(0, leading)
		.map(([id]) => id);
	const picked = new Set(chosen);

	const blank = () => years.map(() => 0);
	const counts = new Map(chosen.map((id) => [id, blank()]));
	const rest = blank();
	const pooled: { label: string; count: number }[][] = years.map(() => []);
	for (const cell of data.timeline.cells) {
		if (!isCase(cell.referent)) continue;
		const at = index.get(cell.year);
		if (at === undefined) continue;
		if (picked.has(cell.referent)) counts.get(cell.referent)![at]! += cell.count;
		else {
			rest[at]! += cell.count;
			pooled[at]!.push({
				label: referents.get(cell.referent)?.label ?? cell.referent,
				count: cell.count
			});
		}
	}
	for (const list of pooled)
		list.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));

	const series: TimelineSeries[] = chosen.map((id) => {
		const values = counts.get(id)!;
		return {
			id,
			label: referents.get(id)?.label ?? id,
			counts: values,
			total: values.reduce((a, b) => a + b, 0)
		};
	});
	const restTotal = rest.reduce((a, b) => a + b, 0);
	if (restTotal)
		series.push({ id: OTHER_CASES, label: 'Other cases', counts: rest, total: restTotal });

	const eligible = data.timeline.years.map((row) => row.eligible);
	const noCase = data.timeline.years.map((row) => row.concrete_case.no ?? 0);
	return {
		years,
		series,
		pooled,
		eligible,
		noCase,
		noCaseShare: eligible.map((n, at) => (n >= minimum && n > 0 ? noCase[at]! / n : null)),
		minimum,
		refusal: null
	};
}

/** The concordance, narrowed to one case in one year. Null for the pooled remainder. */
export function timelineLink(referent: string, year: number): string | null {
	if (referent === OTHER_CASES) return null;
	return concordanceParams({
		...CONCORDANCE_DEFAULTS,
		term: 'genocide',
		referent,
		from: year,
		to: year
	}).toString();
}

export const TIMELINE_COLUMNS = [
	'year',
	'eligible',
	'concrete_case_yes',
	'concrete_case_no',
	'concrete_case_unclear',
	'referent',
	'referent_label',
	'referent_kind',
	'count',
	'contested'
];

/**
 * One row per (year, referent) cell, every referent kind included, with the
 * year's case answers repeated beside it; a year without a cell is one row with
 * the referent columns empty, so no year is lost from the file.
 */
export function timelineExportRows(data: Usage): (string | number | boolean | null)[][] {
	const referents = new Map(data.referents.map((r) => [r.id, r]));
	const byYear = new Map<number, typeof data.timeline.cells>();
	for (const cell of data.timeline.cells) {
		const list = byYear.get(cell.year) ?? [];
		list.push(cell);
		byYear.set(cell.year, list);
	}
	return data.timeline.years.flatMap((year) => {
		const head = [
			year.year,
			year.eligible,
			year.concrete_case.yes ?? 0,
			year.concrete_case.no ?? 0,
			year.concrete_case.unclear ?? 0
		];
		const cells = byYear.get(year.year) ?? [];
		if (!cells.length) return [[...head, null, null, null, null, null]];
		return cells.map((cell) => [
			...head,
			cell.referent,
			referents.get(cell.referent)?.label ?? null,
			referents.get(cell.referent)?.kind ?? null,
			cell.count,
			cell.contested
		]);
	});
}
