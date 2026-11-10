/**
 * The decisions behind "Agenda or usage?", kept out of the component.
 *
 * `04_series.py` splits each decade-to-decade change in the share of speeches
 * carrying the word into two parts (Kitagawa 1955): **composition**, the part
 * that comes from the Council spending more of its speeches on groups where the
 * word was already common, and **within**, the part that comes from the word
 * becoming commoner inside the same groups. The two add to the change exactly,
 * and the figure exists to let a reader see that they do.
 *
 * Four things here are about honesty rather than drawing:
 *
 * **Additivity is checked, not assumed.** Each pair carries the residual
 * `change − (composition + within)`, and a pair whose parts do not add to its
 * change within the payload's rounding is flagged rather than drawn as if they
 * did.
 *
 * **Thin decades are muted, not hidden.** A decade's rate is a share of the
 * speeches that used the word; with a few dozen such speeches one debate moves
 * it. The decade's speeches are read from `series/annual.json`, whose decade
 * shares agree with the decomposition's own, and a pair either of whose decades
 * holds fewer than {@link THIN_USING} speeches using the word is drawn muted.
 * Where the annual series cannot say, the pair is not muted and `thin` is null:
 * unknown is not the same as sufficient, and the caveat says so in words.
 *
 * **Incomplete decades are named.** The record begins in 1946 and ends part-way
 * through the 2020s; a decade the record does not cover whole says which years
 * it holds.
 *
 * **One scale for both splits.** Switching the grouping should change the
 * bars, not the axis, or the reader compares two drawings at two magnifications.
 */

import type { ReadonlyURLSearchParams } from '$app/state';
import type { AnnualSeries, Decomposition, DecompositionRow } from './types';

/** The groupings the figure offers, in the order the control lists them. */
export const PARTS_SPLITS = [
	{ id: 'agenda_item_manual', label: 'By agenda item' },
	{ id: 'speaker_group', label: 'By speaker group' }
] as const;

export type PartsSplit = string;

/** The URL parameter the grouping is stored in. */
export const PARTS_PARAM = 'parts';

/**
 * Speeches using the word below which a decade's share is called thin.
 *
 * About a 10% relative error on the decade's rate (1/√100) before any
 * clustering of speeches within meetings, which only widens it.
 */
export const THIN_USING = 100;

/** Rounding the payload writes at (six decimals), with room for two roundings. */
export const ADDITIVITY_TOLERANCE = 5e-6;

/** Decade facts read off the annual series. */
export interface DecadeBase {
	decade: number;
	/** Every speech the record holds in the decade's years. */
	speeches: number;
	/** Speeches in those years that used the word. */
	using: number;
	/** The first and last year of the decade that the record holds. */
	first: number;
	last: number;
}

/** The part of the annual series this figure reads; older payloads lack `record`. */
export type AnnualBase = Pick<AnnualSeries, 'periods' | 'corpus' | 'terms' | 'record'>;

export interface PartsPair {
	from: number;
	to: number;
	rateFrom: number;
	rateTo: number;
	change: number;
	composition: number;
	within: number;
	/** `change − (composition + within)`; zero up to the payload's rounding. */
	residual: number;
	adds: boolean;
	largest: { group: string; contribution: number }[];
	baseFrom: DecadeBase | null;
	baseTo: DecadeBase | null;
	/** Either decade under {@link THIN_USING}; null where the annual series cannot say. */
	thin: boolean | null;
}

export interface PartsPlan {
	split: PartsSplit;
	splits: { id: PartsSplit; label: string }[];
	pairs: PartsPair[];
	/** One domain for every split the payload holds, in proportions, zero included. */
	domain: [number, number];
	refusal: 'no-splits' | 'empty' | null;
}

const decadeOf = (year: number) => Math.floor(year / 10) * 10;

/** Every decade the annual series holds, with its speeches and its years. */
export function decadeBases(annual: AnnualBase | null, term: string): Map<number, DecadeBase> {
	const out = new Map<number, DecadeBase>();
	if (!annual) return out;
	const using = annual.terms[term]?.speeches;
	if (!using) return out;
	annual.periods.forEach((period, index) => {
		const year = Number(period);
		if (!Number.isInteger(year)) return;
		const decade = decadeOf(year);
		const held = annual.corpus.speeches[index] ?? 0;
		const found = out.get(decade);
		if (found) {
			found.speeches += held;
			found.using += using[index] ?? 0;
			found.first = Math.min(found.first, year);
			found.last = Math.max(found.last, year);
		} else {
			out.set(decade, {
				decade,
				speeches: held,
				using: using[index] ?? 0,
				first: year,
				last: year
			});
		}
	});
	return out;
}

/** Whether the record covers all ten years of the decade. */
export const wholeDecade = (base: DecadeBase) =>
	base.first === base.decade && base.last === base.decade + 9;

/** "1980s", or "1940s (1946–49)" where the record holds only part of it. */
export function decadeLabel(decade: number, base: DecadeBase | null | undefined): string {
	const name = `${decade}s`;
	if (!base || wholeDecade(base)) return name;
	const last = base.last === base.first ? '' : `–${String(base.last).slice(-2)}`;
	return `${name} (${base.first}${last})`;
}

export function splitLabel(id: string): string {
	return PARTS_SPLITS.find((split) => split.id === id)?.label ?? `By ${id.replace(/_/g, ' ')}`;
}

/** The splits the payload holds, known ones first in the control's order. */
export function availableSplits(data: Decomposition | null): PartsSplit[] {
	if (!data) return [];
	const held = Object.keys(data.splits).filter((id) => (data.splits[id]?.length ?? 0) > 0);
	const known = PARTS_SPLITS.map((split) => split.id as string).filter((id) => held.includes(id));
	return [...known, ...held.filter((id) => !known.includes(id)).sort()];
}

export function defaultSplit(available: readonly PartsSplit[]): PartsSplit {
	return available[0] ?? PARTS_SPLITS[0].id;
}

/** The grouping the address asks for, if the payload holds it. */
export function readPartsSplit(
	params: URLSearchParams | ReadonlyURLSearchParams,
	available: readonly PartsSplit[]
): PartsSplit {
	const asked = params.get(PARTS_PARAM);
	return asked && available.includes(asked) ? asked : defaultSplit(available);
}

/** Write the grouping into a query, leaving it out where it is the default. */
export function writePartsSplit(
	params: URLSearchParams,
	split: PartsSplit,
	available: readonly PartsSplit[]
): URLSearchParams {
	params.delete(PARTS_PARAM);
	if (available.length && split !== defaultSplit(available) && available.includes(split)) {
		params.set(PARTS_PARAM, split);
	}
	return params;
}

export function residual(row: Pick<DecompositionRow, 'change' | 'composition' | 'within'>) {
	return row.change - (row.composition + row.within);
}

export function isThin(
	from: DecadeBase | null | undefined,
	to: DecadeBase | null | undefined
): boolean | null {
	if (!from || !to) return null;
	return from.using < THIN_USING || to.using < THIN_USING;
}

function pair(row: DecompositionRow, bases: Map<number, DecadeBase>): PartsPair {
	const baseFrom = bases.get(row.from) ?? null;
	const baseTo = bases.get(row.to) ?? null;
	const gap = residual(row);
	return {
		from: row.from,
		to: row.to,
		rateFrom: row.rate_from,
		rateTo: row.rate_to,
		change: row.change,
		composition: row.composition,
		within: row.within,
		residual: gap,
		adds: Math.abs(gap) <= ADDITIVITY_TOLERANCE,
		largest: row.largest ?? [],
		baseFrom,
		baseTo,
		thin: isThin(baseFrom, baseTo)
	};
}

/** The smallest and largest of every bar and every net change, with zero. */
export function sharedDomain(data: Decomposition): [number, number] {
	let low = 0;
	let high = 0;
	for (const rows of Object.values(data.splits)) {
		for (const row of rows ?? []) {
			for (const value of [row.change, row.composition, row.within]) {
				low = Math.min(low, value);
				high = Math.max(high, value);
			}
		}
	}
	return [low, high];
}

/**
 * Tick positions in proportions on a step of 0.25, 0.5, 1 or 2 points, the
 * first that gives no more than `most` intervals; the domain is widened to
 * whole steps so the outermost bar never touches the frame.
 */
export function ticks([low, high]: [number, number], most = 8): number[] {
	const steps = [0.0025, 0.005, 0.01, 0.02, 0.05];
	let step = steps.at(-1)!;
	for (const candidate of steps) {
		const span = Math.ceil(high / candidate - 1e-9) - Math.floor(low / candidate + 1e-9);
		if (span <= most) {
			step = candidate;
			break;
		}
	}
	const first = Math.floor(low / step + 1e-9);
	const last = Math.max(Math.ceil(high / step - 1e-9), first + 1);
	const out: number[] = [];
	for (let k = first; k <= last; k += 1) out.push(Number((k * step).toFixed(6)));
	return out;
}

export function plan({
	data,
	split,
	annual
}: {
	data: Decomposition | null;
	split: PartsSplit;
	annual: AnnualBase | null;
}): PartsPlan {
	const available = availableSplits(data);
	const splits = available.map((id) => ({ id, label: splitLabel(id) }));
	if (!data || !available.length) {
		return { split, splits, pairs: [], domain: [0, 0], refusal: 'no-splits' };
	}
	const chosen = available.includes(split) ? split : defaultSplit(available);
	const bases = decadeBases(annual, data.term);
	const pairs = [...(data.splits[chosen] ?? [])]
		.sort((a, b) => a.from - b.from)
		.map((row) => pair(row, bases));
	return {
		split: chosen,
		splits,
		pairs,
		domain: sharedDomain(data),
		refusal: pairs.length ? null : 'empty'
	};
}

/** The pair to open on: the largest net change, the one a reader asks about first. */
export function defaultPair(pairs: readonly PartsPair[]): number {
	let best = -1;
	let size = -1;
	pairs.forEach((candidate, index) => {
		if (Math.abs(candidate.change) > size) {
			size = Math.abs(candidate.change);
			best = index;
		}
	});
	return best;
}

/**
 * The decade the record stops part-way through, with the date it stops on
 * where the annual series carries one (an optional field older payloads lack).
 */
export function incompleteEnd(
	annual: AnnualBase | null,
	bases: Map<number, DecadeBase>
): { decade: number; lastYear: number; lastDate: string | null } | null {
	const decades = [...bases.values()].sort((a, b) => a.decade - b.decade);
	const final = decades.at(-1);
	if (!final || final.last === final.decade + 9) return null;
	return {
		decade: final.decade,
		lastYear: final.last,
		lastDate: annual?.record?.last_date ?? null
	};
}

/** A share as the figure prints it: two places, because the early shares are tenths of a percent. */
export const shareText = (value: number) => `${(value * 100).toFixed(2)}%`;

/** Percentage points, signed with a true minus, without the unit. */
export function pp(value: number): string {
	const size = Math.abs(value * 100).toFixed(2);
	if (Number(size) === 0) return '0.00';
	return `${value > 0 ? '+' : '−'}${size}`;
}

/** An axis label: "0", "+0.5", "−1". */
export function tickText(value: number): string {
	const size = Number(Math.abs(value * 100).toFixed(2));
	if (size === 0) return '0';
	return `${value > 0 ? '+' : '−'}${size}`;
}

/** "+2.11 − 0.56": composition and within, written as the sum they are. */
export function sum(row: Pick<PartsPair, 'composition' | 'within'>): string {
	const within = Math.abs(row.within * 100).toFixed(2);
	const sign = row.within < 0 && Number(within) !== 0 ? '−' : '+';
	return `${pp(row.composition)} ${sign} ${within}`;
}

/** "+1.55 = +2.11 − 0.56": the change, then composition and within. */
export function equation(row: Pick<PartsPair, 'change' | 'composition' | 'within'>): string {
	return `${pp(row.change)} = ${sum(row)}`;
}

/** Every row of every split, in proportions as the artefact writes them. */
export const EXPORT_COLUMNS = [
	'split',
	'decade_from',
	'decade_to',
	'rate_from',
	'rate_to',
	'change',
	'composition',
	'within',
	'residual',
	'speeches_from',
	'speeches_to',
	'speeches_using_from',
	'speeches_using_to',
	'years_from',
	'years_to',
	'thin',
	'largest_groups'
];

export function exportRows(
	data: Decomposition,
	annual: AnnualBase | null
): (string | number | boolean | null)[][] {
	const bases = decadeBases(annual, data.term);
	const years = (base: DecadeBase | null) => (base ? `${base.first}-${base.last}` : null);
	const out: (string | number | boolean | null)[][] = [];
	for (const split of availableSplits(data)) {
		for (const row of [...(data.splits[split] ?? [])].sort((a, b) => a.from - b.from)) {
			const p = pair(row, bases);
			out.push([
				split,
				row.from,
				row.to,
				row.rate_from,
				row.rate_to,
				row.change,
				row.composition,
				row.within,
				Number(p.residual.toFixed(6)),
				p.baseFrom?.speeches ?? null,
				p.baseTo?.speeches ?? null,
				p.baseFrom?.using ?? null,
				p.baseTo?.using ?? null,
				years(p.baseFrom),
				years(p.baseTo),
				p.thin,
				p.largest.map((item) => `${item.group}: ${item.contribution}`).join(' | ')
			]);
		}
	}
	return out;
}
