import { describe, expect, it } from 'vitest';
import {
	DEFAULT_SCOPE,
	SCOPE_IDS,
	rankedDelegations,
	readScope,
	reading,
	scopeOf,
	speechInScope,
	withScope
} from './scope';
import type { ScopeIndex } from './types';

/* Small, and every number in it chosen so a wrong denominator shows: the two
   years hold twenty speeches each whatever the scope selects out of them. */
const fixture: ScopeIndex = {
	meta: {
		script: '09_export_speeches.py',
		generated: '2026-09-05T00:00:00Z'
	} as ScopeIndex['meta'],
	corpus: { speeches: 40, meetings: 9 },
	scopes: [
		{ id: 'word', label: 'The word', definition: 'genocid*', speeches: 8, meetings: 4 },
		{
			id: 'vocabulary',
			label: 'The vocabulary',
			definition: 'four terms',
			speeches: 12,
			meetings: 6
		},
		{ id: 'debate', label: 'The debate', definition: 'whole meetings', speeches: 30, meetings: 4 }
	],
	years: [
		{ year: 1994, held: 20, scopes: { word: 6, vocabulary: 9, debate: 18 } },
		{ year: 1995, held: 20, scopes: { word: 2, vocabulary: 3, debate: 12 } }
	],
	delegations: [
		{ country_org: 'Chad', held: 4, scopes: { word: 3, vocabulary: 3, debate: 4 } },
		{ country_org: 'France', held: 16, scopes: { word: 2, vocabulary: 4, debate: 14 } },
		{ country_org: 'Rwanda', held: 12, scopes: { word: 5, vocabulary: 5, debate: 12 } }
	]
};

describe('the corpus scope URL contract', () => {
	it('keeps an old URL on the word scope', () => {
		expect(readScope(new URLSearchParams())).toBe(DEFAULT_SCOPE);
	});

	it('falls back from an unknown scope without preserving it', () => {
		const params = new URLSearchParams('scope=everything&term=genocide');
		expect(readScope(params)).toBe('word');
		expect(withScope(params, readScope(params)).toString()).toBe('term=genocide');
	});

	it('carries a non-default scope without dropping page filters', () => {
		const params = withScope(new URLSearchParams('term=war_crimes&from=1992'), 'debate');
		expect(params.get('scope')).toBe('debate');
		expect(params.get('term')).toBe('war_crimes');
		expect(params.get('from')).toBe('1992');
	});

	it('removes the default from a previously scoped URL', () => {
		const params = withScope(new URLSearchParams('scope=vocabulary&series=genocide'), 'word');
		expect(params.toString()).toBe('series=genocide');
	});
});

describe('what a view draws once it has a scope', () => {
	it('names a reading set by id rather than by position', () => {
		expect(scopeOf(fixture, 'debate').speeches).toBe(30);
		expect(() => scopeOf({ ...fixture, scopes: [] } as unknown as ScopeIndex, 'word')).toThrow(
			/declares no reading set/
		);
	});

	it('divides every scope by the population the cut came out of', () => {
		// The trap R9 names. Under all three scopes the 1994 share is a share of
		// the twenty speeches the Council held that year, and never of the reading
		// set the control selected.
		const year = fixture.years[0];
		for (const scope of SCOPE_IDS) expect(reading(year, scope).held).toBe(20);
		expect(reading(year, 'word').share).toBeCloseTo(6 / 20);
		expect(reading(year, 'debate').share).toBeCloseTo(18 / 20);
	});

	it('keeps the corpus denominator fixed across every cut and every scope', () => {
		// R9's acceptance criterion, asserted rather than left to review. The
		// denominator a rate divides by is read back out of `reading` under each
		// scope in turn: if any of the three ever supplied its own base, one of
		// these sums would come out smaller than the corpus.
		for (const scope of SCOPE_IDS) {
			const years = fixture.years.map((year) => reading(year, scope));
			expect(years.reduce((sum, year) => sum + year.held, 0)).toBe(fixture.corpus.speeches);
			for (const cut of fixture.delegations) {
				expect(reading(cut, scope).held).toBe(cut.held);
			}
			expect(scopeOf(fixture, scope).speeches).toBeLessThanOrEqual(fixture.corpus.speeches);
		}
	});

	it('withholds a share the population is too small to carry', () => {
		expect(
			reading({ held: 4, scopes: { word: 2, vocabulary: 2, debate: 4 } }, 'word', 10).share
		).toBeNull();
	});

	it('ranks delegations by their own record and drops the unrankable', () => {
		const ranked = rankedDelegations(fixture, 'word', 10, 10);
		expect(ranked.map((row) => row.country_org)).toEqual(['Rwanda', 'France']);
		expect(ranked[0].share).toBeCloseTo(5 / 12);
		// Chad sat under the minimum, so it is not ranked above delegations whose
		// share is measured; the debate scope does not rescue it either.
		expect(rankedDelegations(fixture, 'debate', 10, 10).map((r) => r.country_org)).not.toContain(
			'Chad'
		);
	});
});

describe('membership inside one meeting record', () => {
	const hits = [{ genocide: [[0, 8]] }, { war_crimes: [[0, 10]] }, { icc: [[0, 3]] }, {}] as Record<
		string,
		unknown
	>[];
	const saysTheWord = hits.some((h) => 'genocide' in h);

	it('agrees with the count the export published for the same record', () => {
		// `meeting_scope_counts` in 09 counts a speech once however many terms it
		// carries, and gives the whole record to the debate as soon as one speech
		// says the word. The reader recomputes that from the offsets it has, so
		// the two must not be able to disagree.
		const under = (scope: (typeof SCOPE_IDS)[number]) =>
			hits.filter((h) => speechInScope(h, scope, saysTheWord)).length;
		expect(under('word')).toBe(1);
		expect(under('vocabulary')).toBe(2);
		expect(under('debate')).toBe(4);
	});

	it('gives a silent record nothing under any scope', () => {
		for (const scope of SCOPE_IDS) expect(speechInScope({}, scope, false)).toBe(false);
	});
});
