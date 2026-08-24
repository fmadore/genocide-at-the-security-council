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

const UNITS: readonly ChronologyUnit[] = ['speech_rate', 'token_rate', 'occurrences', 'speeches'];

const defaultSeries = (choices: ChronologyChoices, grain: ChronologyGrain) => {
	const available = choices.series[grain];
	return available.includes('genocide') ? ['genocide'] : available.slice(0, 1);
};

export function chronologyDefaults(choices: ChronologyChoices): ChronologyState {
	const calendarMeasures = Object.keys(choices.calendar);
	const calendarMeasure = choices.calendar.genocide ? 'genocide' : (calendarMeasures[0] ?? '');
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
	params: URLSearchParams,
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
