import { describe, expect, it } from 'vitest';
import {
	chronologyParams,
	readChronologyState,
	splitEvidenceQuery,
	type ChronologyChoices,
	type ChronologyState
} from './chronology';

const choices: ChronologyChoices = {
	series: {
		year: ['genocide', 'war_crimes', 'register:core', 'set:atrocity_core'],
		quarter: ['genocide', 'war_crimes', 'register:core', 'set:atrocity_core']
	},
	calendar: {
		genocide: ['speech_rate', 'token_rate'],
		atrocity_core: ['speech_rate']
	},
	splits: ['none', 'speaker_group', 'delivery_language']
};

describe('the headline the chronology opens on', () => {
	/* Since lexicon v4 the published headline is the derived
	   `genocide_qualification` — the `genocide` term minus its `genocidaires`
	   actor label. A reader who opens the page with no query string must land
	   on it, and a reader of an artefact that predates it must still land on
	   something drawable. */
	const withDerived: ChronologyChoices = {
		series: {
			year: ['genocide', 'genocide_qualification', 'war_crimes'],
			quarter: ['genocide', 'genocide_qualification', 'war_crimes']
		},
		calendar: {
			genocide: ['speech_rate'],
			genocide_qualification: ['speech_rate', 'token_rate']
		},
		splits: ['none']
	};
	const withAtrocityComparison: ChronologyChoices = {
		...withDerived,
		series: {
			year: ['genocide_qualification', 'ethnic_cleansing', 'crimes_against_humanity', 'war_crimes'],
			quarter: [
				'genocide_qualification',
				'ethnic_cleansing',
				'crimes_against_humanity',
				'war_crimes'
			]
		}
	};

	it('opens on the derived measure, not the raw term', () => {
		const state = readChronologyState(new URLSearchParams(''), withDerived);
		expect(state.series).toEqual(['genocide_qualification']);
		expect(state.calendarMeasure).toBe('genocide_qualification');
	});

	it('opens the R8 comparison as four explicit terms when all are available', () => {
		const state = readChronologyState(new URLSearchParams(''), withAtrocityComparison);
		expect(state.series).toEqual([
			'genocide_qualification',
			'ethnic_cleansing',
			'crimes_against_humanity',
			'war_crimes'
		]);
	});

	it('falls back to the raw term when the artefact has no derived measure', () => {
		const state = readChronologyState(new URLSearchParams(''), choices);
		expect(state.series).toEqual(['genocide']);
		expect(state.calendarMeasure).toBe('genocide');
	});

	it('still lets a reader ask for the raw term', () => {
		const state = readChronologyState(new URLSearchParams('series=genocide'), withDerived);
		expect(state.series).toEqual(['genocide']);
	});
});

describe('chronology URL state', () => {
	it('round-trips every analytical control, including ordered multi-series state', () => {
		const state: ChronologyState = {
			unit: 'token_rate',
			grain: 'quarter',
			series: ['war_crimes', 'genocide'],
			calendarMeasure: 'atrocity_core',
			calendarUnit: 'speech_rate',
			split: 'delivery_language'
		};
		expect(readChronologyState(chronologyParams(state, choices), choices)).toEqual(state);
	});

	it('preserves an intentionally empty series selection', () => {
		const state = readChronologyState(new URLSearchParams('series='), choices);
		expect(state.series).toEqual([]);
		expect(chronologyParams(state, choices).toString()).toBe('series=');
	});

	it('uses the selected grain when its available series differ', () => {
		const divergent: ChronologyChoices = {
			...choices,
			series: { ...choices.series, quarter: ['responsibility'] }
		};
		const state = readChronologyState(new URLSearchParams('grain=quarter'), divergent);
		expect(state.series).toEqual(['responsibility']);
		expect(chronologyParams(state, divergent).toString()).toBe('grain=quarter');
	});

	it('normalizes unknown and unsupported controls to visible defaults', () => {
		const state = readChronologyState(
			new URLSearchParams(
				'unit=ratio&grain=month&series=unknown&calendar=atrocity_core&calendarUnit=token_rate&split=region'
			),
			choices
		);
		expect(state).toEqual({
			unit: 'speech_rate',
			grain: 'year',
			series: ['genocide'],
			calendarMeasure: 'atrocity_core',
			calendarUnit: 'speech_rate',
			split: 'none'
		});
	});
});

describe('chronology breakdown evidence', () => {
	it('links participant type to its exact concordance category and year', () => {
		const link = splitEvidenceQuery('genocide', 'participanttype', 'Mentioned', 2014)!;
		const params = new URLSearchParams(link.query);
		expect(params.get('term')).toBe('genocide');
		expect(params.get('type')).toBe('Mentioned');
		expect(params.get('from')).toBe('2014');
		expect(params.get('to')).toBe('2014');
		expect(link.scope).toBe('Mentioned in 2014');
	});

	it('refuses a split whose category is absent from KWIC', () => {
		expect(splitEvidenceQuery('genocide', 'delivery_language', 'French', 2014)).toBeNull();
	});
});

describe('interval bands', () => {
	it('draws a floor at the lower bound and a strip of the interval height', async () => {
		const { intervalBand } = await import('./chronology');
		const [floor, strip] = intervalBand('genocide', '#123456', [0.01, 0.02], [0.03, 0.05]);
		expect(floor.data).toEqual([0.01, 0.02]);
		const heights = strip.data as number[];
		expect(heights[0]).toBeCloseTo(0.02, 12);
		expect(heights[1]).toBeCloseTo(0.03, 12);
		expect(strip.areaStyle).toEqual({ color: '#123456', opacity: 0.14 });
		expect(floor.stack).toBe(strip.stack);
		expect(floor.tooltip?.show).toBe(false);
		expect(floor.silent).toBe(true);
	});

	it('leaves a gap where a bound is withheld rather than guessing', async () => {
		const { intervalBand } = await import('./chronology');
		const [floor, strip] = intervalBand('g', '#000', [0.01, null, 0.02], [0.03, 0.04, null]);
		expect(floor.data).toEqual([0.01, null, null]);
		const heights = strip.data as (number | null)[];
		expect(heights[0]).toBeCloseTo(0.02, 12);
		expect(heights.slice(1)).toEqual([null, null]);
	});

	it('never draws a negative strip', async () => {
		const { intervalBand } = await import('./chronology');
		const [, strip] = intervalBand('g', '#000', [0.05], [0.04]);
		expect(strip.data).toEqual([0]);
	});

	it('tells a band from the line it belongs to', async () => {
		const { isIntervalBand, bandOwner, BAND_SUFFIX } = await import('./chronology');
		expect(isIntervalBand(`Genocide${BAND_SUFFIX}`)).toBe(true);
		expect(isIntervalBand('Genocide')).toBe(false);
		expect(isIntervalBand(undefined)).toBe(false);
		expect(bandOwner(`Genocide${BAND_SUFFIX}`)).toBe('Genocide');
		expect(bandOwner('Genocide')).toBe('Genocide');
	});
});
