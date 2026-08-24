import { describe, expect, it } from 'vitest';
import {
	chronologyParams,
	readChronologyState,
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
