import { describe, expect, it } from 'vitest';
import {
	COMPARED_WORDS,
	alignedRows,
	compareTop,
	languageParams,
	matrixEdges,
	matrixTerms,
	readLanguageState,
	topWords,
	type LanguageChoices,
	type LanguageState,
	profilePlan
} from './language';
import type { CollocateBlock, Network, Word } from './types';

const choices: LanguageChoices = {
	nodes: { genocide: ['5', '10'], war_crimes: ['10'] },
	slices: {
		by_country: ['Rwanda', 'United States Of America', 'France'],
		by_period: ['1992–2001', '2002–2011'],
		by_speaker_group: ['Permanent member', 'Other member']
	},
	periods: ['whole', '1992–2001', '2002–2011'],
	profileDefault: { node: 'genocide', width: '5' }
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
			profileFacet: 'by_country',
			profileNode: 'genocide',
			profileWidth: '5',
			profileMember: 'France',
			profileLimit: '60',
			profileFloor: '25',
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
		expect(state.profileMember).toBe('Rwanda');
		expect(state.profileLimit).toBe('40');
		expect(state.profileFloor).toBe('0');
		expect(state.period).toBe('whole');
	});

	it('omits inactive whole-corpus cloud controls for a sliced cloud', () => {
		const state = readLanguageState(new URLSearchParams('cloud=by_period'), choices);
		state.profileNode = 'war_crimes';
		state.profileWidth = '10';
		expect(languageParams(state, choices).toString()).toBe('cloud=by_period');
	});
});

const word = (name: string, target: number, g2: number, logRatio: number): Word => ({
	word: name,
	target,
	reference: 1000,
	g2,
	log_ratio: logRatio,
	documents: 12,
	meetings: 9,
	dp: 0.4
});

const block = (collocates: Word[], speeches?: number): CollocateBlock => ({
	occurrences: 500,
	window_tokens: 5000,
	collocates,
	speeches
});

/** A descending run of plausible rows: frequent and confident first. */
const rows = (n: number) =>
	Array.from({ length: n }, (_, index) =>
		word(`word${index}`, 500 - index * 4, 900 - index * 8, 9 - index * 0.05)
	);

describe('choosing what a profile shows', () => {
	it('refuses a slice under the declared minimum rather than substituting the whole corpus', () => {
		const result = profilePlan({
			block: block(rows(40), 12),
			minimumSpeeches: 20,
			limit: 40,
			floor: 0
		});
		expect(result.refusal).toEqual({
			kind: 'below-minimum',
			speeches: 12,
			minimum: 20,
			floor: null
		});
		expect(result.rows).toEqual([]);
	});

	it('withholds the table too, so the two never disagree about a refused slice', () => {
		const result = profilePlan({
			block: block(rows(40), 3),
			minimumSpeeches: 20,
			limit: 40,
			floor: 0
		});
		expect(result.rows).toHaveLength(0);
		expect(result.available).toBe(40);
	});

	it('does not gate the whole corpus, which is not a slice and has no minimum', () => {
		const result = profilePlan({
			block: block(rows(10)),
			minimumSpeeches: null,
			limit: 40,
			floor: 0
		});
		expect(result.refusal).toBeNull();
		expect(result.rows).toHaveLength(10);
	});

	it('tells an emptied filter apart from a withheld slice', () => {
		const result = profilePlan({
			block: block(rows(10), 900),
			minimumSpeeches: 20,
			limit: 40,
			floor: 10_000
		});
		expect(result.refusal?.kind).toBe('no-rows');
		expect(result.refusal?.floor).toBe(10_000);
	});

	it('says how many rows the limit removed rather than truncating in silence', () => {
		const result = profilePlan({
			block: block(rows(100), 900),
			minimumSpeeches: 20,
			limit: 25,
			floor: 0
		});
		expect(result.rows).toHaveLength(25);
		expect(result.truncated).toBe(75);
		expect(result.filtered).toBe(0);
	});

	it('says how many rows the frequency floor removed', () => {
		const result = profilePlan({
			block: block(rows(100), 900),
			minimumSpeeches: 20,
			limit: 100,
			floor: 300
		});
		expect(result.rows.every((row) => row.target >= 300)).toBe(true);
		expect(result.filtered).toBe(100 - result.rows.length);
	});

	it('hands the table and the plot one array, in one order', () => {
		const result = profilePlan({
			block: block(rows(30), 900),
			minimumSpeeches: 20,
			limit: 12,
			floor: 0
		});
		expect(result.rows.map((row) => row.word)).toEqual(
			rows(30)
				.slice(0, 12)
				.map((row) => row.word)
		);
	});
});

describe('two profiles side by side', () => {
	const a = block([
		word('crime', 50, 300, 4),
		word('prevent', 40, 200, 3),
		word('tribunal', 30, 100, 1)
	]);
	const b = block([word('tribunal', 60, 400, 5), word('crime', 20, 80, 0.5)]);

	it('lists each side’s strongest words, to the same depth', () => {
		expect(topWords(block(rows(30)))).toHaveLength(COMPARED_WORDS);
		expect(topWords(undefined)).toEqual([]);
	});

	it('aligns one word per row, strongest first, with a gap where a side lacks it', () => {
		const aligned = alignedRows(a, b);
		expect(aligned.map((row) => row.word)).toEqual(['tribunal', 'crime', 'prevent']);
		expect(aligned[0]?.a?.log_ratio).toBe(1);
		expect(aligned[0]?.b?.log_ratio).toBe(5);
		expect(aligned[2]?.b).toBeNull();
	});

	it('reads a word’s figures from the whole profile, not only the top list', () => {
		// `crime` is past the other side's top list here and still has its figure.
		const deep = block([...rows(COMPARED_WORDS), word('crime', 5, 10, 0.2)]);
		const row = alignedRows(a, deep).find((entry) => entry.word === 'crime');
		expect(row?.b?.log_ratio).toBe(0.2);
	});

	it('scales both columns to one top, whichever arrangement is shown', () => {
		expect(compareTop('rank', a, b)).toBe(5);
		expect(compareTop('word', a, b)).toBe(5);
		// Nothing positive to scale by: the unit scale rather than a division by zero.
		expect(compareTop('rank', block([word('x', 1, 1, -2)]), undefined)).toBe(1);
		expect(compareTop('word', undefined, undefined)).toBe(1);
	});
});

describe('the co-occurrence matrix', () => {
	const network = {
		meta: { script: '05_lexical.py', generated: 'fixture' },
		min_speeches: 5,
		terms: [
			{ name: 'genocide', tier: 'core', register: 'core', speeches: 900 },
			{ name: 'war_crimes', tier: 'legal', register: 'legal', speeches: 400 }
		],
		edges: [{ source: 'genocide', target: 'war_crimes', speeches: 120 }],
		by_period: {
			'1992–2001': {
				terms: [{ name: 'genocide', speeches: 300 }],
				edges: [{ source: 'genocide', target: 'war_crimes', speeches: 40 }]
			}
		},
		suppressed_nested_edges: []
	} as unknown as Network;

	it('divides by the whole corpus, or by the chosen period where it lists the term', () => {
		expect(matrixTerms(network, 'whole').map((t) => t.speeches)).toEqual([900, 400]);
		expect(matrixTerms(network, '1992–2001').map((t) => t.speeches)).toEqual([300, 400]);
		expect(matrixTerms(network, '1992–2001')[0]).toEqual({
			name: 'genocide',
			register: 'core',
			speeches: 300
		});
	});

	it('draws the chosen period’s edges, and none for a period it does not hold', () => {
		expect(matrixEdges(network, 'whole')).toBe(network.edges);
		expect(matrixEdges(network, '1992–2001')).toHaveLength(1);
		expect(matrixEdges(network, '2012–2021')).toEqual([]);
	});
});
