/**
 * The decisions behind the year x month grid, kept out of the component.
 *
 * `docs/PLAN.md` §7's fifth item scoped this figure before anything was drawn,
 * and it scoped it against its own finding: a month resolution does recover a
 * calendar, but not the commemorative one a reader expects. April, the Rwanda
 * commemoration month, runs *below* the corpus rate; June and December run at
 * twice it, and the agenda items behind those speeches are the international
 * tribunals, which reported to the Council semi-annually. The most visible
 * feature of this figure is the Council's own reporting cycle.
 *
 * Four decisions follow from that, and all four are here rather than in the
 * component:
 *
 * **A withheld cell is drawn as withheld, never as white.** 53 of the 384
 * months hold too few speeches for a rate — white on a heatmap reads as zero,
 * which is the `?? 0` failure §7 records, in a form that covers 53 cells.
 * `grid()` gives every cell a state and no cell a substitute number, so the
 * component has nothing to fill in.
 *
 * **The ramp starts at zero, not at the smallest month.** Zero is attainable
 * and meaningful here — plenty of months carry no occurrence of the word — so a
 * scale anchored on the observed minimum would spend its whole range on the
 * difference between 1.5% and 2%, and make a quiet month look like an absent
 * one. High is the largest drawn cell; low is zero, always.
 *
 * **Rates only.** The chronology offers counts because the contrast between a
 * count and a rate is its argument. Here a count would be a picture of when the
 * Council met, which is precisely the confound this figure has to disclose
 * rather than reproduce — and a count needs no minimum, so two of four units
 * would quietly have no withheld cells and no legend for them.
 *
 * **The column read is a second figure.** `calendar()` returns the twelve
 * pooled months with their own scale and their own denominator. Thirty-two
 * Junes pooled is not a margin of the grid, and nothing here lets the two share
 * a range.
 *
 * One thing this view cannot do, recorded rather than left to be noticed: the
 * concordance filters lines by year, so a cell cannot open the lines behind
 * *itself*. The link opens the cell's year and the interface names the year, so
 * what a reader is offered is wider than the cell and says so.
 */

import type { AgendaItem, CalendarMeasure, MonthlyMeasure, MonthlySeries } from './types';

/** The units a normalised grid can honestly carry. See the note above. */
export type Unit = 'speech_rate' | 'token_rate';

export const MONTH_NAMES = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

/** `2014-06` → `June 2014`. */
export const monthLabel = (period: string): string => {
	const [year, month] = period.split('-');
	return `${MONTH_NAMES[Number(month) - 1] ?? month} ${year}`;
};

/**
 * What a cell is, before it is a colour.
 *
 * `unobserved` is separated from `withheld` although both refuse to be drawn:
 * "the Council did not meet" and "the Council met too little to divide by" are
 * different facts, and a reader who hovers deserves the one that is true. Every
 * month in the present corpus is observed, so the state is unreachable today —
 * it exists because a grid is written complete, and the day one is empty the
 * figure should not have to be changed to say so.
 */
export type CellState = 'drawn' | 'withheld' | 'unobserved';

export interface Cell {
	period: string;
	year: number;
	/** 1–12. */
	month: number;
	/** The month's own denominator: speeches the Council held in it. */
	held: number;
	/** Speeches bearing the measure's terms. A count, so never withheld. */
	speeches: number;
	occurrences: number | null;
	/** The chosen unit, or null when this cell may not be drawn. */
	value: number | null;
	state: CellState;
	/** 0–1 against the largest drawn cell, from a floor of zero. 0 when not drawn. */
	weight: number;
	/**
	 * Where the cell sits on the ramp, which is not `weight`. See :func:`tone`.
	 * A length must never use this; a length is read as a proportion.
	 */
	tone: number;
}

export interface HeatmapPlan {
	cells: Cell[];
	years: number[];
	months: number[];
	/** What it was actually drawn in, which is not always what was asked for. */
	unit: Unit;
	/** The top of the ramp. The bottom is zero by construction. */
	high: number;
	drawn: number;
	withheld: number;
	unobserved: number;
	minimum: number;
	refusal: 'no-measure' | 'none-drawable' | null;
}

export interface HeatmapRequest {
	data: MonthlySeries;
	measure: string;
	unit?: Unit;
}

/** Every measure the artefact holds, whatever kind it is. */
export function measures(data: MonthlySeries): Record<string, MonthlyMeasure> {
	return { ...data.terms, ...data.registers, ...data.sets };
}

/**
 * The units a measure can honestly be drawn in.
 *
 * A set is a union of overlapping terms, so it has no occurrence count and no
 * rate per token — `04_series.py` withholds both rather than double-counting a
 * speech that used two members. Read through `?? 0` that silence becomes
 * `0.00 per 100,000 words`, so the absence is detected once, here, and the
 * control never offers a unit the grid is not in.
 */
export function units(measure: MonthlyMeasure | undefined): Unit[] {
	return measure?.token_rate ? ['speech_rate', 'token_rate'] : ['speech_rate'];
}

/**
 * The grid for one measure in one unit.
 *
 * The partition is the artefact's own `sufficient` flag rather than a
 * comparison recomputed here: `04_series.py` derived the threshold and already
 * applied it, nulling the rates it governs, so a second implementation of the
 * rule in TypeScript could only drift from the one that wrote the data.
 */
export function grid(request: HeatmapRequest): HeatmapPlan {
	const { data, measure, unit: asked = 'speech_rate' } = request;
	const found = measures(data)[measure];
	const months = data.months ?? [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

	if (!found) {
		return {
			cells: [],
			years: data.years,
			months,
			unit: asked,
			high: 0,
			drawn: 0,
			withheld: 0,
			unobserved: 0,
			minimum: data.minimum_speeches,
			refusal: 'no-measure'
		};
	}

	const unit = units(found).includes(asked) ? asked : 'speech_rate';
	const values = unit === 'token_rate' ? (found.token_rate ?? []) : found.speech_rate;

	const cells: Cell[] = data.periods.map((period, index) => {
		const held = data.corpus.speeches[index] ?? 0;
		const value = data.sufficient[index] ? (values[index] ?? null) : null;
		const state: CellState =
			held === 0 ? 'unobserved' : data.sufficient[index] && value !== null ? 'drawn' : 'withheld';
		const [year, month] = period.split('-');
		return {
			period,
			year: Number(year),
			month: Number(month),
			held,
			speeches: found.speeches[index] ?? 0,
			occurrences: found.occurrences?.[index] ?? null,
			value: state === 'drawn' ? value : null,
			state,
			weight: 0,
			tone: 0
		};
	});

	// The top of the ramp is the largest cell that is actually drawn. A withheld
	// cell never enters the range: it has no number, and a range computed from
	// counts it does not carry would be a range of something else.
	const high = cells.reduce((top, cell) => Math.max(top, cell.value ?? 0), 0);
	for (const cell of cells) {
		cell.weight = cell.value !== null && high > 0 ? Math.min(cell.value / high, 1) : 0;
		cell.tone = cell.value !== null ? tone(cell.weight) : 0;
	}

	const drawn = cells.filter((cell) => cell.state === 'drawn').length;
	return {
		cells,
		years: data.years,
		months,
		unit,
		high,
		drawn,
		withheld: cells.filter((cell) => cell.state === 'withheld').length,
		unobserved: cells.filter((cell) => cell.state === 'unobserved').length,
		minimum: data.minimum_speeches,
		refusal: drawn ? null : 'none-drawable'
	};
}

/**
 * Where a cell's share of the maximum lands on the ramp.
 *
 * The square root, and the reason is in the data rather than in taste. These
 * rates are heavily skewed — the median drawn month is 2.2% against a maximum
 * of 19.2% — so a ramp proportional to the value puts half the grid inside the
 * bottom eighth of the scale, and a figure in which most cells are the colour
 * of the page understates what it is drawing as badly as one that overstates
 * it. The transform is monotone and clips nothing: every cell keeps its order
 * and its own colour, and no cell is capped at a ceiling that hides how far
 * past it the cell went.
 *
 * It is applied to *colour* and never to a length. A bar is read as a
 * proportion — half the width means half the number — so `calendar()`'s rows
 * keep the linear `weight`. Colour carries no such promise, which is why it can
 * take a transform, and why the figure has to say that it did.
 */
export const tone = (weight: number): number => Math.sqrt(Math.min(Math.max(weight, 0), 1));

/** The cell at a year and month, or undefined where the grid has none. */
export function at(plan: HeatmapPlan, year: number, month: number): Cell | undefined {
	return plan.cells.find((cell) => cell.year === year && cell.month === month);
}

export interface CalendarRow {
	month: number;
	name: string;
	/** Pooled across every year: a denominator no cell in the grid has. */
	held: number;
	speeches: number;
	value: number | null;
	/** The same figure with the artefact's control years dropped. */
	without: number | null;
	weight: number;
	sufficient: boolean;
	/** What the month's term-bearing speeches were debating, largest first. */
	agenda: AgendaItem[];
}

export interface CalendarPlan {
	rows: CalendarRow[];
	unit: Unit;
	high: number;
	excludedYears: number[];
	/** The item that leads in the two strongest months, when it is the same one. */
	shared: string | null;
	refusal: 'no-measure' | null;
}

/**
 * The twelve calendar months, pooled.
 *
 * Scaled within itself and never against `grid()`. The two figures answer
 * different questions with different denominators, and a shared ramp would
 * invite a reader to compare a month of one year with thirty-two of them.
 *
 * `shared` is the finding stated as a value rather than as prose: when the same
 * agenda item leads both of the strongest months, that is the reporting cycle,
 * and the figure may say so. When it is not, the figure must not.
 */
export function calendar(
	data: MonthlySeries,
	measure: string,
	unit: Unit = 'speech_rate'
): CalendarPlan {
	const block: CalendarMeasure | undefined = data.month_of_year.measures[measure];
	if (!block) {
		return {
			rows: [],
			unit,
			high: 0,
			excludedYears: data.month_of_year.excluded_years,
			shared: null,
			refusal: 'no-measure'
		};
	}

	const usable: Unit = unit === 'token_rate' && !block.token_rate ? 'speech_rate' : unit;
	const read = (source: CalendarMeasure['excluding'], index: number) =>
		source.sufficient[index]
			? ((usable === 'token_rate' ? source.token_rate?.[index] : source.speech_rate[index]) ?? null)
			: null;

	const rows: CalendarRow[] = data.month_of_year.months.map((month, index) => ({
		month,
		name: MONTH_NAMES[month - 1] ?? String(month),
		held: block.held[index] ?? 0,
		speeches: block.speeches[index] ?? 0,
		value: read(block, index),
		without: read(block.excluding, index),
		weight: 0,
		sufficient: block.sufficient[index] ?? false,
		agenda: block.agenda[index] ?? []
	}));

	const high = rows.reduce((top, row) => Math.max(top, row.value ?? 0), 0);
	for (const row of rows) row.weight = row.value !== null && high > 0 ? row.value / high : 0;

	const strongest = [...rows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0)).slice(0, 2);
	const leaders = strongest.map((row) => row.agenda[0]?.item ?? null);
	const shared =
		leaders.length === 2 && leaders[0] !== null && leaders[0] === leaders[1] ? leaders[0] : null;

	return {
		rows,
		unit: usable,
		high,
		excludedYears: data.month_of_year.excluded_years,
		shared,
		refusal: null
	};
}

export const GRID_COLUMNS = [
	'period',
	'year',
	'month',
	'measure',
	'kind',
	'speeches_held',
	'tokens',
	'term_bearing_speeches',
	'speech_rate',
	'occurrences',
	'token_rate_per_100k',
	'sufficient'
];

/**
 * Every cell of every measure, for the download.
 *
 * The whole artefact rather than the measure on screen, and the withheld months
 * with their nulls intact beside a `sufficient` column — §7.5's first
 * constraint. A reader handed only the drawable cells cannot recover the 53
 * that were left out, or know that they were.
 */
export function gridRows(data: MonthlySeries): (string | number | boolean | null)[][] {
	const rows: (string | number | boolean | null)[][] = [];
	const kinds: [string, Record<string, MonthlyMeasure>][] = [
		['terms', data.terms],
		['registers', data.registers],
		['sets', data.sets]
	];
	for (const [kind, block] of kinds) {
		for (const [name, measure] of Object.entries(block)) {
			data.periods.forEach((period, index) => {
				rows.push([
					period,
					Number(period.slice(0, 4)),
					Number(period.slice(5)),
					name,
					kind,
					data.corpus.speeches[index] ?? 0,
					data.corpus.tokens[index] ?? 0,
					measure.speeches[index] ?? 0,
					measure.speech_rate[index] ?? null,
					measure.occurrences?.[index] ?? null,
					measure.token_rate?.[index] ?? null,
					data.sufficient[index] ?? false
				]);
			});
		}
	}
	return rows;
}

export const CALENDAR_COLUMNS = [
	'month',
	'month_name',
	'measure',
	'kind',
	'speeches_held',
	'term_bearing_speeches',
	'speech_rate',
	'token_rate_per_100k',
	'speech_rate_excluding_control_years',
	'sufficient',
	'agenda_rank',
	'agenda_item',
	'agenda_speeches',
	'agenda_share'
];

/**
 * The pooled months for every measure, with the agenda attribution beside them.
 *
 * One row per (measure, month, agenda item) rather than per month, so the
 * confound travels in the file. A calendar table downloaded without it is the
 * misleading half of this figure on its own.
 */
export function calendarRows(data: MonthlySeries): (string | number | boolean | null)[][] {
	const rows: (string | number | boolean | null)[][] = [];
	for (const [name, block] of Object.entries(data.month_of_year.measures)) {
		data.month_of_year.months.forEach((month, index) => {
			const base = [
				month,
				MONTH_NAMES[month - 1] ?? String(month),
				name,
				block.kind,
				block.held[index] ?? 0,
				block.speeches[index] ?? 0,
				block.speech_rate[index] ?? null,
				block.token_rate?.[index] ?? null,
				block.excluding.speech_rate[index] ?? null,
				block.sufficient[index] ?? false
			];
			const agenda = block.agenda[index] ?? [];
			if (!agenda.length) {
				rows.push([...base, null, null, null, null]);
				return;
			}
			agenda.forEach((item, rank) => {
				rows.push([...base, rank + 1, item.item, item.speeches, item.share]);
			});
		});
	}
	return rows;
}
