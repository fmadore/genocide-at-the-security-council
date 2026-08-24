import { describe, expect, it } from 'vitest';
import {
	languageParams,
	readLanguageState,
	type LanguageChoices,
	type LanguageState
} from './language';

const choices: LanguageChoices = {
	nodes: { genocide: ['5', '10'], war_crimes: ['10'] },
	slices: {
		by_country: ['Rwanda', 'United States Of America', 'France'],
		by_period: ['1992–2001', '2002–2011'],
		by_speaker_group: ['Permanent member', 'Other member']
	},
	periods: ['whole', '1992–2001', '2002–2011'],
	cloudDefault: { node: 'genocide', width: '5' }
};

describe('language URL state', () => {
	it('round-trips the active controls across all five analytical figures', () => {
		const state: LanguageState = {
			node: 'war_crimes',
			width: '10',
			sliceKind: 'by_period',
			sliceA: '2002–2011',
			sliceB: '1992–2001',
			align: 'word',
			cloudFacet: 'by_country',
			cloudNode: 'genocide',
			cloudWidth: '5',
			cloudMember: 'France',
			cloudLimit: '60',
			cloudFloor: '25',
			keynessView: 'unmatched',
			period: '2002–2011'
		};
		expect(readLanguageState(languageParams(state, choices), choices)).toEqual(state);
	});

	it('normalizes invalid values and node-specific windows', () => {
		const state = readLanguageState(
			new URLSearchParams(
				'node=war_crimes&width=5&slice=agenda&left=unknown&cloud=by_country&cloud-member=unknown&words=500&floor=3&period=future'
			),
			choices
		);
		expect(state.node).toBe('war_crimes');
		expect(state.width).toBe('10');
		expect(state.sliceKind).toBe('by_country');
		expect(state.sliceA).toBe('Rwanda');
		expect(state.cloudMember).toBe('Rwanda');
		expect(state.cloudLimit).toBe('40');
		expect(state.cloudFloor).toBe('0');
		expect(state.period).toBe('whole');
	});

	it('omits inactive whole-corpus cloud controls for a sliced cloud', () => {
		const state = readLanguageState(new URLSearchParams('cloud=by_period'), choices);
		state.cloudNode = 'war_crimes';
		state.cloudWidth = '10';
		expect(languageParams(state, choices).toString()).toBe('cloud=by_period');
	});
});
