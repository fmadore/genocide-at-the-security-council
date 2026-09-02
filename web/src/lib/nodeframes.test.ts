import { describe, expect, it } from 'vitest';
import {
	facetLabel,
	facets,
	member,
	members,
	morphology,
	movers,
	outside,
	position,
	profile,
	track,
	UNFRAMED
} from './nodeframes';
import type { FrameShare, NodeFrames } from './types';

const share = (frame: string, occurrences: number, of: number, spread = 0.05): FrameShare => ({
	frame,
	occurrences,
	share: occurrences / of,
	share_low: Math.max(0, occurrences / of - spread),
	share_high: Math.min(1, occurrences / of + spread)
});

const withheld = (frame: string, occurrences: number): FrameShare => ({
	frame,
	occurrences,
	share: null,
	share_low: null,
	share_high: null
});

/** A four-frame artefact: enough to rank, to slice and to withhold. */
function artefact(): NodeFrames {
	return {
		meta: { script: '17_frames.py', generated: '2026-09-02T00:00:00Z', lexicon_version: 3 },
		term: 'genocide',
		pattern: '\\bgenocid\\w*',
		window: 90,
		occurrences: 100,
		speeches: 60,
		minimum_occurrences: 40,
		minimum_occurrences_rule: '',
		precedence_rule: '',
		unframed_rule: '',
		denominator_rule: '',
		codebook: [
			{
				frame: 'atrocity_triad',
				precedence: 1,
				gloss: 'One item of the standing list.',
				pattern: 'x',
				cased_pattern: null,
				example: 'war crimes and genocide',
				example_line: 'UNSC_2016_SPV.7829_spch0006#1'
			},
			{
				frame: 'prevention',
				precedence: 2,
				gloss: 'The duty, stated as a norm.',
				pattern: 'y',
				cased_pattern: null,
				example: 'to prevent genocide',
				example_line: 'UNSC_2004_SPV.5100Resumption1_spch0021#3'
			},
			{
				frame: 'distancing',
				precedence: 3,
				gloss: 'The label marked as somebody else’s.',
				pattern: 'z',
				cased_pattern: null,
				example: 'so-called genocide',
				example_line: 'UNSC_2020_S_2020_339_spch0018#1'
			}
		],
		totals: {
			frames: [
				share('atrocity_triad', 50, 100),
				share('prevention', 20, 100),
				share('distancing', 5, 100),
				share(UNFRAMED, 25, 100)
			],
			frames_per_occurrence: [
				{ matched: 0, occurrences: 25 },
				{ matched: 1, occurrences: 75 }
			]
		},
		morphology: {
			categories: [
				{ category: 'noun', occurrences: 90 },
				{ category: 'adjective', occurrences: 10 },
				{ category: 'perpetrator_noun', occurrences: 0 },
				{ category: 'other', occurrences: 0 }
			],
			forms: [
				{ form: 'genocide', occurrences: 85, category: 'noun' },
				{ form: 'genocides', occurrences: 5, category: 'noun' },
				{ form: 'genocidal', occurrences: 10, category: 'adjective' }
			]
		},
		by_year: { years: [2014], occurrences: [100], minimum_occurrences: 40, frames: {} },
		slices: {
			period: [
				{
					member: '2016-2023',
					occurrences: 60,
					sufficient: true,
					frames: [
						share('atrocity_triad', 42, 60),
						share('prevention', 6, 60),
						share('distancing', 3, 60),
						share(UNFRAMED, 9, 60)
					]
				},
				{
					member: '1992-1999',
					occurrences: 10,
					sufficient: false,
					frames: [
						withheld('atrocity_triad', 2),
						withheld('prevention', 4),
						withheld('distancing', 0),
						withheld(UNFRAMED, 4)
					]
				}
			],
			speaker_group: [
				{
					member: 'P5',
					occurrences: 50,
					sufficient: true,
					frames: [
						share('atrocity_triad', 25, 50),
						share('prevention', 10, 50),
						share('distancing', 3, 50),
						share(UNFRAMED, 12, 50)
					]
				}
			]
		},
		change: {
			method: '',
			null: 'meeting_block_permutation',
			minimum_occurrences: 250,
			familywise_alpha: 0.05,
			per_test_alpha: 0.0063,
			correction: '',
			trials: 2000,
			caveat: '',
			tested: []
		},
		triangulation: { rule: '', runs: [] }
	};
}

describe('the facets a reader can choose between', () => {
	it('reads them off the payload rather than hard-coding them', () => {
		expect(facets(artefact())).toEqual(['period', 'speaker_group']);
	});

	it('prints a label rather than a column name', () => {
		expect(facetLabel('speaker_group')).toBe('Speaker group');
		expect(facetLabel('agenda')).toBe('agenda');
	});

	it('keeps the artefact’s order, which is largest member first', () => {
		expect(members(artefact(), 'period').map((row) => row.member)).toEqual([
			'2016-2023',
			'1992-1999'
		]);
	});

	it('falls back to the largest member rather than to nothing', () => {
		expect(member(artefact(), 'period', 'no such block')?.member).toBe('2016-2023');
		expect(member(artefact(), 'no such facet', 'x')).toBeNull();
	});
});

describe('the profile', () => {
	it('ranks by the corpus share so the rows do not reshuffle under the control', () => {
		const data = artefact();
		const byPeriod = profile(data, member(data, 'period', '2016-2023')).map((row) => row.frame);
		const byGroup = profile(data, member(data, 'speaker_group', 'P5')).map((row) => row.frame);
		expect(byPeriod).toEqual(['atrocity_triad', UNFRAMED, 'prevention', 'distancing']);
		expect(byGroup).toEqual(byPeriod);
	});

	it('keeps the residue in the ranking rather than pinning it to the bottom', () => {
		const data = artefact();
		expect(profile(data, null)[1].frame).toBe(UNFRAMED);
	});

	it('carries the codebook gloss, and its own sentence for the residue', () => {
		const rows = profile(artefact(), null);
		expect(rows.find((row) => row.frame === 'prevention')?.gloss).toContain('duty');
		expect(rows.find((row) => row.frame === UNFRAMED)?.gloss).toContain('No pattern');
	});

	it('reports the shift in points between the slice and the corpus', () => {
		const data = artefact();
		const rows = profile(data, member(data, 'period', '2016-2023'));
		const triad = rows.find((row) => row.frame === 'atrocity_triad');
		expect(triad?.overall).toBeCloseTo(0.5, 6);
		expect(triad?.share).toBeCloseTo(0.7, 6);
		expect(triad?.shift).toBeCloseTo(0.2, 6);
	});

	it('withholds a shift wherever the slice withheld its share', () => {
		const data = artefact();
		const rows = profile(data, member(data, 'period', '1992-1999'));
		expect(rows.every((row) => row.share === null && row.shift === null)).toBe(true);
		// The counts survive the withholding: a reader is entitled to the four.
		expect(rows.find((row) => row.frame === UNFRAMED)?.occurrences).toBe(4);
	});

	it('draws the corpus profile alone when no slice is chosen', () => {
		const rows = profile(artefact(), null);
		expect(rows.every((row) => row.share === null)).toBe(true);
		expect(rows.find((row) => row.frame === 'atrocity_triad')?.overall).toBeCloseTo(0.5, 6);
	});
});

describe('the share axis', () => {
	it('is anchored at zero, because these are shares of a whole', () => {
		expect(track(profile(artefact(), null)).low).toBe(0);
	});

	it('clears the widest interval on screen and rounds up', () => {
		const data = artefact();
		const rows = profile(data, member(data, 'period', '2016-2023'));
		const scale = track(rows);
		const widest = Math.max(...rows.map((row) => row.high ?? 0));
		expect(scale.high).toBeGreaterThanOrEqual(widest);
		expect(scale.high * 100).toBeCloseTo(Math.round(scale.high * 100), 6);
	});

	it('ticks in even steps from zero to the top', () => {
		const scale = track(profile(artefact(), null), 0.1);
		expect(scale.ticks[0]).toBe(0);
		expect(scale.ticks.at(-1)).toBeCloseTo(scale.high, 6);
	});

	it('places a larger share further right and clamps to the track', () => {
		const scale = track(profile(artefact(), null));
		expect(position(0.4, scale)).toBeGreaterThan(position(0.1, scale));
		expect(position(0, scale)).toBe(0);
		expect(position(9, scale)).toBe(1);
	});
});

describe('what the figure is entitled to mark', () => {
	it('marks a row whose interval does not cover the corpus share', () => {
		const row = { ...profile(artefact(), null)[0], share: 0.7, low: 0.6, high: 0.8 };
		expect(outside(row)).toBe(true);
	});

	it('marks nothing where the interval covers it, or where there is none', () => {
		const rows = profile(artefact(), null);
		expect(outside({ ...rows[0], share: 0.52, low: 0.42, high: 0.62 })).toBe(false);
		expect(outside(rows[0])).toBe(false);
	});

	it('offers the largest marked shifts first', () => {
		const data = artefact();
		const rows = profile(data, member(data, 'period', '2016-2023'));
		const found = movers(rows, 2);
		expect(found[0].frame).toBe('atrocity_triad');
		expect(found.length).toBeLessThanOrEqual(2);
	});

	it('offers nothing from a slice whose shares were withheld', () => {
		const data = artefact();
		expect(movers(profile(data, member(data, 'period', '1992-1999')))).toEqual([]);
	});
});

describe('the morphological split', () => {
	it('names the forms behind each category', () => {
		const rows = morphology(artefact());
		expect(rows.map((row) => row.category)).toEqual(['noun', 'adjective']);
		expect(rows[0].forms).toEqual(['genocide', 'genocides']);
		expect(rows[0].share).toBeCloseTo(0.9, 6);
	});

	it('leaves out a category the corpus never used', () => {
		expect(morphology(artefact()).map((row) => row.category)).not.toContain('perpetrator_noun');
	});
});
