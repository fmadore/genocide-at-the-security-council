/**
 * The decisions behind the drawn two-rate split on "Testing for a change in
 * the rate", kept out of the component.
 *
 * `04_series.py` searches every year for the best split of the genocide series
 * into two constant rates and asks, by simulation, whether that best split is
 * better than a single rate would produce by chance. The drawing shows the two
 * rates as steps with their 95% intervals, the year the search chose, and the
 * verdict in words. Three things it decides:
 *
 * **An unaccepted split is not drawn as a finding.** A best split exists for
 * any series; one that does not clear the corrected threshold is drawn muted
 * and dashed, and its verdict says so.
 *
 * **The block p-value comes first.** `accepted` follows the p-value under the
 * meeting-block null, so the verdict leads with it and sets the
 * independent-speech p-value beside it, never in its place.
 *
 * **A p-value at the simulation floor says so.** With 2,000 simulations the
 * smallest p-value the test can return is about 1 in 2,000; a printed 0.0005
 * is "no simulation did as well", not a measured 0.05%.
 */

import type { AnnualSeries, ChangePoints, RateBreak } from './types';

export type RateUnit = 'speech_rate' | 'token_rate';

export const RATE_UNITS: readonly { id: RateUnit; label: string; axis: string }[] = [
	{ id: 'speech_rate', label: 'Share of speeches', axis: 'share of speeches' },
	{ id: 'token_rate', label: 'Per 100,000 words', axis: 'per 100,000 words' }
];

/** The factor from the artefact's rate to the number the reader is shown. */
export const DISPLAY_SCALE: Record<RateUnit, number> = { speech_rate: 1, token_rate: 100_000 };

export interface RateLevel {
	value: number;
	low: number;
	high: number;
}

export interface RateStep {
	unit: RateUnit;
	label: string;
	/** First year of the later segment, as the artefact labels it. */
	split: number;
	/** The span the steps cover: the first year and the year after the last. */
	start: number;
	end: number;
	before: RateLevel;
	after: RateLevel;
	accepted: boolean;
	pBlock: number;
	pIndependent: number;
	/** Whether the block null was the one used; false on an older artefact. */
	blocked: boolean;
	alpha: number;
	/** Whether `pBlock` is the smallest the simulations can return. */
	atFloor: boolean;
	ratio: number | null;
	/** Speeches (or occurrences) and their exposure on each side. */
	counts: [number, number];
	exposure: [number, number];
}

export interface RateNone {
	unit: RateUnit;
	label: string;
	none: true;
}

export type RateRow = RateStep | RateNone;

export const isStep = (row: RateRow): row is RateStep => !('none' in row);

const level = (value: number, interval: [number, number], scale: number): RateLevel => ({
	value: value * scale,
	low: interval[0] * scale,
	high: interval[1] * scale
});

/** The smallest p-value `trials` simulations can give, as the artefact rounds it. */
export function pFloor(trials: number): number {
	return trials > 0 ? Number((1 / (trials + 1)).toFixed(5)) : 0;
}

/** One unit's split, in display units, or a refusal where the search found none. */
export function rateStep(
	unit: RateUnit,
	found: RateBreak | null | undefined,
	periods: readonly (number | string)[],
	trials: number
): RateRow | null {
	const label = RATE_UNITS.find((u) => u.id === unit)!.label;
	if (found === undefined) return null;
	if (found === null) return { unit, label, none: true };
	const years = periods.map(Number).filter(Number.isInteger);
	const split = Number(found.label);
	const scale = DISPLAY_SCALE[unit];
	return {
		unit,
		label,
		split,
		start: years.length ? Math.min(...years) : split,
		end: years.length ? Math.max(...years) + 1 : split + 1,
		before: level(found.before, found.before_ci95, scale),
		after: level(found.after, found.after_ci95, scale),
		accepted: found.accepted,
		pBlock: found.p_value,
		pIndependent: found.p_value_independent,
		blocked: found.null === 'meeting_block_permutation',
		alpha: found.alpha,
		atFloor: found.p_value <= pFloor(trials) + 1e-12,
		ratio: found.ratio,
		counts: found.counts,
		exposure: found.exposure
	};
}

/** Both units, in the order the table lists them, absent ones left out. */
export function rateSteps(
	breaks: Pick<ChangePoints, 'inference'>,
	periods: readonly (number | string)[],
	term = 'genocide'
): RateRow[] {
	const found = breaks.inference.series[term] ?? {};
	return RATE_UNITS.map(({ id }) =>
		rateStep(id, found[id], periods, breaks.inference.trials)
	).filter((row): row is RateRow => row !== null);
}

/** A p-value as printed: four places, or "≤" the floor where it sits there. */
export function formatP(p: number, floor: boolean): string {
	return floor ? `≤ ${p.toFixed(4)}` : p.toFixed(4);
}

/** The verdict, in words, with both p-values. */
export function verdict(step: RateStep): string {
	const clears = step.accepted
		? 'clears the corrected threshold'
		: 'does not clear the corrected threshold';
	const block = `p ${step.atFloor ? '≤' : '='} ${step.pBlock.toFixed(4)}`;
	const lead = step.blocked
		? `${block} with whole meetings moved between years`
		: `${block} with speeches treated as independent`;
	const beside = step.blocked
		? `; ${step.pIndependent.toFixed(4)} with speeches treated as independent`
		: '';
	return `A split in ${step.split} ${clears} of ${step.alpha} (${lead}${beside}).`;
}

/** The value range the panel draws: zero to just above the highest bound or point. */
export function rateCeiling(step: RateStep, points: readonly (number | null)[] = []): number {
	const top = Math.max(step.before.high, step.after.high, ...points.map((v) => v ?? 0));
	return top > 0 ? top * 1.08 : 1;
}

/**
 * The annual rates behind the steps, in display units, for the faint dots the
 * steps are drawn over. A withheld year stays null: it is left undrawn, never
 * set at zero.
 */
export function annualPoints(
	annual: Pick<AnnualSeries, 'periods' | 'terms'> | null,
	unit: RateUnit,
	term = 'genocide'
): { year: number; value: number | null }[] {
	const measure = annual?.terms[term];
	if (!annual || !measure) return [];
	// The annual token rate is already per 100,000 words; the share is a share.
	const values = unit === 'speech_rate' ? measure.speech_rate : (measure.token_rate ?? []);
	return annual.periods.map((period, index) => ({
		year: Number(period),
		value: values[index] ?? null
	}));
}

/** A rate as the reader is shown it. */
export function formatRate(unit: RateUnit, value: number): string {
	return unit === 'speech_rate' ? `${(value * 100).toFixed(2)}%` : value.toFixed(2);
}

/**
 * The plate's CSV: the two-rate test the drawing shows, then the exploratory
 * method's candidates, in one table with a `method` column. Rates are the
 * artefact's own (a share, or occurrences per word), not the display units.
 * A unit whose search found no split is a row with its rates empty, never a
 * row of zeros.
 */
export const RATE_EXPORT_COLUMNS = [
	'method',
	'measure',
	'unit',
	'label',
	'index',
	'rate_before',
	'rate_before_ci95_low',
	'rate_before_ci95_high',
	'rate_after',
	'rate_after_ci95_low',
	'rate_after_ci95_high',
	'ratio',
	'gain',
	'p_value',
	'p_value_independent',
	'null',
	'alpha',
	'accepted',
	'count_before',
	'count_after',
	'exposure_before',
	'exposure_after',
	'interval_start',
	'interval_stop'
];

type Cell = string | number | boolean | null;

export function rateExportRows(breaks: Pick<ChangePoints, 'inference' | 'series'>): Cell[][] {
	const rows: Cell[][] = [];
	for (const [measure, units] of Object.entries(breaks.inference.series)) {
		for (const [unit, found] of Object.entries(units)) {
			if (!found) {
				rows.push(['two_rate_test', measure, unit, ...Array<Cell>(21).fill(null)]);
				continue;
			}
			rows.push([
				'two_rate_test',
				measure,
				unit,
				found.label,
				found.index,
				found.before,
				found.before_ci95[0],
				found.before_ci95[1],
				found.after,
				found.after_ci95[0],
				found.after_ci95[1],
				found.ratio,
				found.gain,
				found.p_value,
				found.p_value_independent,
				found.null,
				found.alpha,
				found.accepted,
				found.counts[0],
				found.counts[1],
				found.exposure[0],
				found.exposure[1],
				null,
				null
			]);
		}
	}
	for (const [measure, units] of Object.entries(breaks.series)) {
		for (const [unit, found] of Object.entries(units)) {
			for (const point of found) {
				rows.push([
					'exploratory',
					measure,
					unit,
					point.label,
					point.index,
					point.before,
					null,
					null,
					point.after,
					null,
					null,
					point.ratio,
					point.gain,
					point.p_value,
					null,
					null,
					null,
					null,
					null,
					null,
					null,
					null,
					point.interval_start,
					point.interval_stop
				]);
			}
		}
	}
	return rows;
}

/** Year ticks for the span: every 20 years on a narrow plate, every 10 on a wide one. */
export function yearTicks(start: number, end: number, every: number): number[] {
	const out: number[] = [];
	for (let year = Math.ceil(start / every) * every; year < end; year += every) out.push(year);
	return out;
}

/** Value ticks from zero on a 1, 2 or 5 step, at most five of them. */
export function valueTicks(ceiling: number): number[] {
	if (!(ceiling > 0)) return [0];
	const raw = ceiling / 4;
	const power = 10 ** Math.floor(Math.log10(raw));
	const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
	const out: number[] = [];
	for (let k = 0; k * step <= ceiling + 1e-12; k += 1) out.push(Number((k * step).toPrecision(6)));
	return out;
}
