/**
 * What the keyness view decides, tested apart from how it is drawn.
 *
 * The cases below are the claims the figure makes about itself: that a withheld
 * speaker is refused with the artefact's own reason rather than shown as an
 * empty table, that self-reference is marked and never filtered, that the two
 * readings are never put on one scale, and that the download is the artefact
 * rather than what happened to be on screen.
 */

import { describe, expect, it } from 'vitest';
import {
	EXPORT_COLUMNS,
	bars,
	exportRows,
	neverPaired,
	pick,
	published,
	removed,
	selfReferenceShare,
	withheld
} from './keyness';
import type { Keyword, SpeakerKeyness, SpeakerKeynessRow } from './types';

const word = (name: string, logRatio: number, self = false, target = 100, g2 = 500): Keyword => ({
	word: name,
	target,
	reference: 10,
	g2,
	log_ratio: logRatio,
	self_reference: self
});

const agenda = {
	held: 10,
	items: 2,
	top: [{ item: 'Rwanda', speeches: 6, share: 0.6 }],
	other: { speeches: 4, share: 0.4 },
	concentration: 0.6
};

const speaker = (over: Partial<SpeakerKeynessRow> = {}): SpeakerKeynessRow => ({
	country_org: 'Utopia',
	pairs: 500,
	held: 520,
	coverage: 0.96,
	short_strata: 3,
	shortfall: 20,
	sufficient: true,
	withheld_because: [],
	target_tokens: 50_000,
	control_tokens: 48_000,
	keywords: [word('utopia', 4, true), word('council', 2), word('report', 1)],
	keywords_unmatched: [word('utopia', 6, true), word('rwanda', 5), word('council', 2.5)],
	stability: {
		repetitions: 10,
		coverage_min: 0.95,
		coverage_max: 0.97,
		keyword_log_ratio: [{ word: 'utopia', median: 4.01, low: 3.8, high: 4.2, p05: 3.9, p95: 4.1 }]
	},
	agenda,
	...over
});

const artefact = (rows: SpeakerKeynessRow[], over: Partial<SpeakerKeyness> = {}) =>
	({
		meta: { script: '12_speaker_keyness.py', generated: 'now' },
		matched_on: ['year', 'agenda_item_manual', 'speaker_group'],
		minimum_pairs: 100,
		minimum_pairs_rule: '',
		minimum_coverage: 0.5,
		minimum_coverage_rule: '',
		control_rule: '',
		unmatched_rule: '',
		reading_rule: '',
		self_reference_rule: '',
		seed: 1,
		repetitions: 10,
		limit: 40,
		speakers_total: 601,
		speakers_considered: rows.length,
		speakers_published: rows.filter((r) => r.sufficient).length,
		speakers_withheld: rows.filter((r) => !r.sufficient).length,
		speakers: rows,
		...over
	}) as SpeakerKeyness;

describe('published and withheld', () => {
	const rows = [
		speaker({ country_org: 'Small', pairs: 60 }),
		speaker({ country_org: 'Big', pairs: 4000 }),
		speaker({
			country_org: 'Withheld',
			pairs: 70,
			sufficient: false,
			withheld_because: ['pairs'],
			keywords: null,
			keywords_unmatched: null
		})
	];

	it('ranks the drawable speakers by the comparison’s own denominator', () => {
		expect(published(artefact(rows)).map((r) => r.country_org)).toEqual(['Big', 'Small']);
	});

	it('keeps the withheld speakers as rows, not as a count', () => {
		// Unlike the actor view's 468: these were considered, so each has a
		// coverage figure and a named reason a reader can be shown.
		expect(withheld(artefact(rows)).map((r) => r.country_org)).toEqual(['Withheld']);
	});

	it('reports the never-paired speakers as the number they are', () => {
		expect(neverPaired(artefact(rows))).toBe(601 - 3);
	});
});

describe('pick', () => {
	it('refuses a withheld speaker with the artefact’s own reason', () => {
		const row = speaker({
			sufficient: false,
			withheld_because: ['coverage'],
			pairs: 123,
			held: 4709,
			coverage: 0.026,
			keywords: null,
			keywords_unmatched: null
		});
		const plan = pick(artefact([row]), 'Utopia');
		expect(plan.rows).toEqual([]);
		expect(plan.refusal).toEqual({
			because: ['coverage'],
			pairs: 123,
			held: 4709,
			coverage: 0.026
		});
		// The evidence for the refusal survives the refusal.
		expect(plan.speaker?.pairs).toBe(123);
	});

	it('distinguishes a speaker that is absent from one that is withheld', () => {
		const plan = pick(artefact([speaker()]), 'Nowhere');
		expect(plan.missing).toBe(true);
		expect(plan.refusal).toBeNull();
	});

	it('is not missing when nothing has been picked yet', () => {
		expect(pick(artefact([speaker()]), null).missing).toBe(false);
	});

	it('draws the reading it is asked for', () => {
		const matched = pick(artefact([speaker()]), 'Utopia', 'matched');
		const unmatched = pick(artefact([speaker()]), 'Utopia', 'unmatched');
		expect(matched.rows.map((r) => r.word)).toEqual(['utopia', 'council', 'report']);
		expect(unmatched.rows.map((r) => r.word)).toEqual(['utopia', 'rwanda', 'council']);
	});
});

describe('bars', () => {
	it('marks self-reference and keeps the row', () => {
		const rows = bars(speaker(), 'matched');
		expect(rows[0]).toMatchObject({ word: 'utopia', selfReference: true });
		expect(rows).toHaveLength(3);
		expect(selfReferenceShare(rows)).toEqual({ marked: 1, of: 3 });
	});

	it('scales within one reading, never across both', () => {
		// utopia is 4 matched and 6 unmatched. If the two shared a scale, the
		// matched bar would be two-thirds; within its own reading it is full.
		expect(bars(speaker(), 'matched')[0].weight).toBe(1);
		expect(bars(speaker(), 'unmatched')[0].weight).toBe(1);
		expect(bars(speaker(), 'matched')[1].weight).toBeCloseTo(0.5);
	});

	it('carries the stability interval only where the artefact has one', () => {
		const rows = bars(speaker(), 'matched');
		// The observed range, not the percentiles: the row prints one draw beside
		// it, and p05 at ten draws can sit above the value it is printed next to.
		expect(rows[0].interval).toEqual({ median: 4.01, low: 3.8, high: 4.2 });
		expect(rows[1].interval).toBeNull();
	});

	it('offers no interval on the unmatched reading, which has none', () => {
		expect(bars(speaker(), 'unmatched').every((row) => row.interval === null)).toBe(true);
	});

	it('draws nothing for a withheld table rather than inventing a row', () => {
		expect(bars(speaker({ keywords: null }), 'matched')).toEqual([]);
	});

	it('cuts the drawing at the limit', () => {
		expect(bars(speaker(), 'matched', 2).map((r) => r.word)).toEqual(['utopia', 'council']);
	});

	it('survives a table whose every effect size is zero', () => {
		const flat = speaker({ keywords: [word('a', 0), word('b', 0)] });
		expect(bars(flat, 'matched').map((r) => r.weight)).toEqual([0, 0]);
	});
});

describe('removed', () => {
	it('is the median fall from the unmatched reading to the matched one', () => {
		// utopia 6→4, rwanda 5→absent (counts as 0), council 2.5→2.
		expect(removed(speaker())).toBe(2);
	});

	it('is null rather than zero when a reading is missing', () => {
		// "No change" and "not computed" are different claims.
		expect(removed(speaker({ keywords: null }))).toBeNull();
		expect(removed(speaker({ keywords_unmatched: [] }))).toBeNull();
	});
});

describe('exportRows', () => {
	it('writes every row the artefact holds, not the ones on screen', () => {
		const rows = exportRows(speaker());
		expect(rows).toHaveLength(6);
		expect(rows.filter((r) => r[1] === 'matched')).toHaveLength(3);
		expect(rows.filter((r) => r[1] === 'unmatched')).toHaveLength(3);
	});

	it('names the reading on every row so the two cannot be merged', () => {
		expect(EXPORT_COLUMNS[1]).toBe('reading');
		expect(exportRows(speaker()).every((row) => row[1] === 'matched' || row[1] === 'unmatched'));
	});

	it('carries the stability interval where it exists and nulls where it does not', () => {
		const rows = exportRows(speaker());
		expect(rows[0].slice(-3)).toEqual([3.8, 4.01, 4.2]);
		expect(rows[1].slice(-3)).toEqual([null, null, null]);
		// The unmatched reading has no interval at all, by construction.
		expect(rows[3].slice(-3)).toEqual([null, null, null]);
	});

	it('has a column for every field it emits', () => {
		expect(exportRows(speaker())[0]).toHaveLength(EXPORT_COLUMNS.length);
	});

	it('emits nothing for a withheld speaker', () => {
		expect(exportRows(speaker({ keywords: null, keywords_unmatched: null }))).toEqual([]);
	});
});
