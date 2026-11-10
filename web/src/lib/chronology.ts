import type { ReadonlyURLSearchParams } from '$app/state';
import type { LineSeriesOption } from 'echarts';
import { headlineMeasure } from './headline';
import {
	registerMark,
	registerStroke,
	type NeutralStroke,
	type Palette,
	type RegisterMark
} from './theme';

export type ChronologyUnit = 'speech_rate' | 'token_rate' | 'occurrences' | 'speeches';
export type ChronologyGrain = 'year' | 'quarter';
export type CalendarUnit = 'speech_rate' | 'token_rate';

export interface ChronologyState {
	unit: ChronologyUnit;
	grain: ChronologyGrain;
	series: string[];
	calendarMeasure: string;
	calendarUnit: CalendarUnit;
	split: string;
}

export interface ChronologyChoices {
	series: Record<ChronologyGrain, readonly string[]>;
	calendar: Record<string, readonly CalendarUnit[]>;
	splits: readonly string[];
}

const EVIDENCE_FILTERS: Readonly<Record<string, string>> = {
	speaker_group: 'group',
	participanttype: 'type',
	agenda_item_manual: 'agenda'
};

export interface SplitEvidenceQuery {
	query: string;
	scope: string;
}

/** Link a breakdown cell only when KWIC carries the same normalized category. */
export function splitEvidenceQuery(
	term: string,
	split: string,
	category: string,
	period: string | number
): SplitEvidenceQuery | null {
	const filter = EVIDENCE_FILTERS[split];
	if (!filter) return null;
	const year = String(period);
	const params = new URLSearchParams({ term, [filter]: category, from: year, to: year });
	return { query: params.toString(), scope: `${category} in ${year}` };
}

const UNITS: readonly ChronologyUnit[] = ['speech_rate', 'token_rate', 'occurrences', 'speeches'];

export const ATROCITY_COMPARISON = [
	'genocide',
	'ethnic_cleansing',
	'crimes_against_humanity',
	'war_crimes'
] as const;

/* The headline rule is shared with the home page and the actor table; see
   `#lib/headline`. Falling back through the raw term keeps an older artefact
   drawable rather than opening on whatever sorts first. */
const defaultSeries = (choices: ChronologyChoices, grain: ChronologyGrain) => {
	const available = choices.series[grain];
	if (ATROCITY_COMPARISON.every((name) => available.includes(name))) {
		return [...ATROCITY_COMPARISON];
	}
	const headline = headlineMeasure(available);
	return headline ? [headline] : available.slice(0, 1);
};

export function chronologyDefaults(choices: ChronologyChoices): ChronologyState {
	const calendarMeasures = Object.keys(choices.calendar);
	const calendarMeasure = headlineMeasure(calendarMeasures) ?? calendarMeasures[0] ?? '';
	return {
		unit: 'speech_rate',
		grain: 'year',
		series: defaultSeries(choices, 'year'),
		calendarMeasure,
		calendarUnit: choices.calendar[calendarMeasure]?.includes('speech_rate')
			? 'speech_rate'
			: (choices.calendar[calendarMeasure]?.[0] ?? 'speech_rate'),
		split: choices.splits.includes('none') ? 'none' : (choices.splits[0] ?? '')
	};
}

/** Parse a copied chronology URL, dropping unknown values and restoring documented defaults. */
export function readChronologyState(
	params: ReadonlyURLSearchParams,
	choices: ChronologyChoices
): ChronologyState {
	const defaults = chronologyDefaults(choices);
	const grain = params.get('grain') === 'quarter' ? 'quarter' : defaults.grain;
	const askedUnit = params.get('unit') as ChronologyUnit | null;
	const unit = askedUnit && UNITS.includes(askedUnit) ? askedUnit : defaults.unit;

	let series = defaultSeries(choices, grain);
	if (params.has('series')) {
		const asked = params.getAll('series');
		if (asked.length === 1 && asked[0] === '') {
			series = [];
		} else {
			const available = new Set(choices.series[grain]);
			const valid = [...new Set(asked.filter((name) => available.has(name)))];
			if (valid.length) series = valid;
		}
	}

	const askedCalendar = params.get('calendar');
	const calendarMeasure =
		askedCalendar && choices.calendar[askedCalendar] ? askedCalendar : defaults.calendarMeasure;
	const askedCalendarUnit = params.get('calendarUnit') as CalendarUnit | null;
	const calendarUnit =
		askedCalendarUnit && choices.calendar[calendarMeasure]?.includes(askedCalendarUnit)
			? askedCalendarUnit
			: choices.calendar[calendarMeasure]?.includes(defaults.calendarUnit)
				? defaults.calendarUnit
				: (choices.calendar[calendarMeasure]?.[0] ?? defaults.calendarUnit);
	const askedSplit = params.get('split');
	const split = askedSplit && choices.splits.includes(askedSplit) ? askedSplit : defaults.split;

	return { unit, grain, series, calendarMeasure, calendarUnit, split };
}

/** Keep copied URLs compact by omitting every artefact-aware default. */
export function chronologyParams(
	state: ChronologyState,
	choices: ChronologyChoices
): URLSearchParams {
	const defaults = chronologyDefaults(choices);
	const defaultSelected = defaultSeries(choices, state.grain);
	const params = new URLSearchParams();
	if (state.unit !== defaults.unit) params.set('unit', state.unit);
	if (state.grain !== defaults.grain) params.set('grain', state.grain);
	if (
		state.series.length !== defaultSelected.length ||
		state.series.some((name, index) => name !== defaultSelected[index])
	) {
		if (state.series.length === 0) params.set('series', '');
		else for (const name of state.series) params.append('series', name);
	}
	if (state.calendarMeasure !== defaults.calendarMeasure) {
		params.set('calendar', state.calendarMeasure);
	}
	if (state.calendarUnit !== defaults.calendarUnit) params.set('calendarUnit', state.calendarUnit);
	if (state.split !== defaults.split) params.set('split', state.split);
	return params;
}

/* --- A way out of the calendar's two refusals --------------------------------
   The calendar refuses in two ways, and a refusal with no next step leaves a
   reader with a centred grey sentence and nothing to press (critique of 19
   September 2026, heuristic 9). The way out is the nearest figure that can be
   drawn: another measure of the same calendar where the asked-for one is not in
   the data, and otherwise the same measure by year, where all but the
   thinnest year of the record clears the minimum. */

export type CalendarRecovery =
	/** Draw the calendar for another measure the monthly artefact does carry. */
	| { kind: 'measure'; measure: string }
	/** Show the word list by year, with this measure added when it has a series. */
	| { kind: 'yearly'; measure: string | null };

export function calendarRecovery(
	refusal: 'no-measure' | 'none-drawable' | null,
	measure: string,
	monthly: readonly string[],
	yearly: readonly string[]
): CalendarRecovery | null {
	if (!refusal) return null;
	if (refusal === 'no-measure') {
		const fallback = headlineMeasure(monthly) ?? monthly[0];
		if (fallback && fallback !== measure) return { kind: 'measure', measure: fallback };
	}
	// No month reaches the minimum whatever the measure, because the minimum is
	// on the month's own speeches: changing measure would refuse again.
	return { kind: 'yearly', measure: yearly.includes(measure) ? measure : null };
}

/* --- One stroke per term ----------------------------------------------------
   The word-list figure used to draw every term of a register in the register's
   one hue, so selecting the legal shelf put nine identical teal lines on the
   chart and the only thing separating them was the end label. The hue is an
   analytical claim and stays: a term drawn in teal is a term on the legal
   shelf. What changes is that the hue is now a family rather than a single
   value — `registerStroke` steps its lightness and turns a dash inside it. */

/** A term's line: a stroke inside its register's hue, at a weight, with its marker. */
export interface TermStroke extends NeutralStroke {
	width: number;
	/** Turns with the lightness step, so a shared dash is never told apart by shade alone. */
	mark: RegisterMark;
}

/** The headline term's line, in full ink: the figure's one reference line. */
export const HEADLINE_STROKE_WIDTH = 2;

/** Every other term, a shade under it so the headline still reads as first. */
export const TERM_STROKE_WIDTH = 1.8;

/**
 * A stroke for each of `names`, keyed by name.
 *
 * The step handed to `registerStroke` is the term's position among the terms of
 * its own register in `names`, which is the lexicon's order. Pass the whole
 * measure list rather than the reader's selection: the position has to be a
 * property of the term, or dropping one chip would restyle every line after it
 * and the same figure would export differently on two visits.
 *
 * The headline term takes full ink, solid, and the heavier weight, and still
 * consumes its slot in the core register so nothing downstream of it shifts.
 */
export function termStrokes(
	names: readonly string[],
	registerOf: (name: string) => string | undefined,
	p: Palette
): Map<string, TermStroke> {
	const headline = headlineMeasure(names);
	const taken = new Map<string, number>();
	const strokes = new Map<string, TermStroke>();
	for (const name of names) {
		if (strokes.has(name)) continue;
		const register = registerOf(name) ?? '';
		const index = taken.get(register) ?? 0;
		taken.set(register, index + 1);
		strokes.set(
			name,
			name === headline
				? { color: p.ink, dash: 'solid', width: HEADLINE_STROKE_WIDTH, mark: 'circle' }
				: {
						...registerStroke(register, index, p),
						width: TERM_STROKE_WIDTH,
						mark: registerMark(index)
					}
		);
	}
	return strokes;
}

/**
 * A stroke's dash as SVG writes it, matching what ECharts draws: zrender sets
 * `dashed` at four widths on, two off, and `dotted` at one on, one off. The
 * term chips draw a short sample of each line with this, so the key beside
 * the chart is the line on it rather than a description of it.
 */
export function dashArray(stroke: {
	dash: NeutralStroke['dash'];
	width: number;
}): string | undefined {
	if (stroke.dash === 'dashed') return `${4 * stroke.width} ${2 * stroke.width}`;
	if (stroke.dash === 'dotted') return `${stroke.width}`;
	return undefined;
}

/**
 * The bounds a band is drawn between: the wider, point by point, of the Wilson
 * interval and the meeting-clustered one where the artefact carries both.
 *
 * Wilson treats every speech as independent and is too narrow in a year whose
 * word sits in a few debates; the clustered bounds resample whole meetings
 * (RV19). But a percentile bootstrap can only return rates its own resamples
 * produce. In a period where no meeting used the word every resample is zero,
 * and the clustered interval is 0 to 0 — 73 of the 314 quarters for `genocide`,
 * and 7 of 81 years — where Wilson correctly says the rate could be as high as
 * 3/n. With a single hit it is narrower than Wilson again. Until November 2026
 * the clustered bounds were drawn wherever they existed, so in about half the
 * quarters the band the caption said "widens" was narrower than the interval
 * it replaced, and in the emptiest periods it claimed no uncertainty at all.
 * The clustered interval is there to add the between-meeting variance, never
 * to remove the binomial one, so the band is the envelope of the two.
 *
 * `clustered` says whether the clustered reading entered at all. A bound that
 * is null in the Wilson arrays is a withheld rate and stays null.
 */
export function bandBounds(measure: {
	speech_rate_low: readonly (number | null)[];
	speech_rate_high: readonly (number | null)[];
	speech_rate_cluster_low?: readonly (number | null)[];
	speech_rate_cluster_high?: readonly (number | null)[];
}): { low: readonly (number | null)[]; high: readonly (number | null)[]; clustered: boolean } {
	const clusterLow = measure.speech_rate_cluster_low;
	const clusterHigh = measure.speech_rate_cluster_high;
	if (!clusterLow || !clusterHigh) {
		return { low: measure.speech_rate_low, high: measure.speech_rate_high, clustered: false };
	}
	const wider = (
		wilson: readonly (number | null)[],
		cluster: readonly (number | null)[],
		pick: (a: number, b: number) => number
	) =>
		wilson.map((bound, index) => {
			if (bound == null) return null;
			const other = cluster[index];
			return other == null ? bound : pick(bound, other);
		});
	return {
		low: wider(measure.speech_rate_low, clusterLow, Math.min),
		high: wider(measure.speech_rate_high, clusterHigh, Math.max),
		clustered: true
	};
}

/* --- A rate its denominator cannot carry -------------------------------------
   The month grid has always withheld a rate below the artefact's minimum. Since
   the record was extended to 1946 the same is true of a year (1959 holds 86
   speeches), of a quarter (39 hold fewer than 125) and above all of a cell of
   the split figure, where one non-state speech in 1993 that used the word is a
   "rate" of 100% and used to set the chart's axis. The artefact now writes
   null and `sufficient`; these two helpers are how a figure reads them, and
   they apply the same test to a payload written before it did. */

/** The minimum the pipeline declares (`MIN_SPEECHES_PER_PERIOD`), for a payload that predates it. */
export const FALLBACK_MINIMUM = 125;

/** A breakdown cell's rate, or null where its speeches are too few to divide by. */
export function splitRate(
	row: { held: number; speech_rate: number | null; sufficient?: boolean },
	minimum: number = FALLBACK_MINIMUM
): number | null {
	if (row.sufficient === false || row.held < minimum) return null;
	return row.speech_rate;
}

/** How many of a series' periods are withheld: counts published, no rate. */
export function withheldPeriods(series: { sufficient?: readonly boolean[] }): number {
	return (series.sufficient ?? []).filter((enough) => !enough).length;
}

/* --- Uncertainty bands ------------------------------------------------------
   Every `speech_rate` comes with its bounds (see `bandBounds`). A band is drawn as two
   stacked line series: an invisible floor at the lower bound and a filled
   strip of height (high − low) on top of it. Both are named after the line
   they belong to with a suffix, so a tooltip or a legend can tell them apart
   from the line and leave them out. */

export const BAND_SUFFIX = ' · 95% interval';

/** Whether a series name is one half of an interval band rather than a line. */
export const isIntervalBand = (seriesName: string | undefined): boolean =>
	typeof seriesName === 'string' && seriesName.endsWith(BAND_SUFFIX);

/** The line a band series belongs to, or the name unchanged if it is not a band. */
export const bandOwner = (seriesName: string): string =>
	isIntervalBand(seriesName) ? seriesName.slice(0, -BAND_SUFFIX.length) : seriesName;

/**
 * The two ECharts series that draw a band between `low` and `high`.
 *
 * Where either bound is missing the band has a gap, never a guess: a null in
 * `low` makes both series null at that index. `high` is stored as the strip's
 * height rather than its value because ECharts stacks by addition.
 */
export function intervalBand(
	name: string,
	colour: string,
	low: readonly (number | null)[],
	high: readonly (number | null)[],
	opacity = 0.14
): [LineSeriesOption, LineSeriesOption] {
	const floor = low.map((value, index) => (value == null || high[index] == null ? null : value));
	const height = high.map((value, index) => {
		const base = low[index];
		return value == null || base == null ? null : Math.max(value - base, 0);
	});
	const shared = {
		type: 'line' as const,
		stack: `${name}${BAND_SUFFIX}`,
		symbol: 'none' as const,
		silent: true as const,
		/* The colour matters even at zero opacity. Left unset, ECharts assigns
		   the next entry of its stock palette, and the band's two invisible
		   edges were serialised into every SVG download as `#5070dd`,
		   `#b6d634`, `#505372`, `#ff994d` — off-token strokes, one of them
		   blue, in a file governed by "blue is never a datum". Anything that
		   drops opacity on the way to a slide brings them back. */
		lineStyle: { color: colour, opacity: 0 },
		emphasis: { disabled: true as const },
		tooltip: { show: false as const },
		z: 1
	};
	return [
		{ ...shared, name: `${name}${BAND_SUFFIX}`, data: floor },
		{
			...shared,
			name: `${name}${BAND_SUFFIX}`,
			data: height,
			areaStyle: { color: colour, opacity }
		}
	];
}

/**
 * Decimals a percentage axis needs so that neighbouring ticks read differently.
 *
 * An axis of shares was labelled to one decimal whatever it held. Drawn alone,
 * a term used in 0.2% of speeches got ticks 0.025 points apart and labels
 * reading 0.0%, 0.0%, 0.1%, 0.1%, 0.1%. ECharts places about five ticks, so
 * the step is near a fifth of the largest drawn value; the decimals are what
 * that step needs, between one and three.
 */
export function percentDecimals(largest: number): number {
	if (!(largest > 0)) return 1;
	const step = (largest * 100) / 5;
	return Math.min(3, Math.max(1, Math.ceil(-Math.log10(step)) + 1));
}

/** How many terms may each carry a band before only the headline keeps one. */
export const BANDED_TERMS = 2;

/**
 * Which of the drawn terms carry an interval band.
 *
 * Every term, while there are at most two. Past that only the headline term,
 * if it is drawn: four overlapping bands at a low opacity merged into one grey
 * mass in light and nearly vanished in dark (review of 10 November 2026), and
 * the band is now the envelope of two intervals, so it is wider than it was.
 * The intervals stay in the tooltip for every term either way.
 */
export function bandedTerms(names: readonly string[]): string[] {
	if (names.length <= BANDED_TERMS) return [...names];
	const headline = headlineMeasure(names);
	return headline ? [headline] : [];
}
