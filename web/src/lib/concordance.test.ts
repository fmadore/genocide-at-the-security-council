/**
 * The month dimension of the concordance URL, tested from both ends.
 *
 * A link builder and a parameter reader that disagree produce the worst version
 * of this feature: a reader follows "June 2014" from the heatmap, the
 * concordance cannot read what the figure wrote, and what opens is the whole
 * corpus under a heading that says June. Nothing in either module would report
 * it, because neither is wrong on its own. So the round trip is the test that
 * matters here, and it is checked for every month rather than for one.
 */

import { describe, expect, it } from 'vitest';
import {
	MONTH_PARAM,
	CONCORDANCE_DEFAULTS,
	cellQuery,
	chronologyEscape,
	concordanceParams,
	describeMonth,
	describeSort,
	facetClick,
	filterConcordance,
	inMonth,
	monthName,
	monthOf,
	pooledQuery,
	profileResult,
	readConcordanceState,
	readMonth,
	topFacet,
	yearClick
} from './concordance';
import type { KwicLine } from './types';

const read = (query: string) => readMonth(new URLSearchParams(query).get(MONTH_PARAM));

describe('reading a month from a URL', () => {
	it('takes the twelve months, padded or not', () => {
		for (let month = 1; month <= 12; month++) {
			expect(readMonth(String(month))).toBe(month);
			expect(readMonth(String(month).padStart(2, '0'))).toBe(month);
		}
	});

	// Each of these could plausibly have been coerced into a month by a more
	// forgiving reading, and each would then filter to a month nobody asked for.
	it.each([
		['13', 'past December'],
		['0', 'before January'],
		['-6', 'negative'],
		['6.5', 'not an integer'],
		['foo', 'not a number'],
		['', 'empty'],
		['   ', 'blank'],
		[null, 'absent'],
		[undefined, 'unset']
	])('refuses %s (%s)', (value: string | null | undefined, reason: string) => {
		expect(readMonth(value), reason).toBeNull();
	});

	// The lenient reading is a decision, not an accident: a typo must not hide
	// evidence. `inMonth` is what makes it safe — null filters nothing — and the
	// select is what stops the interface claiming a month it is not showing.
	it('lets every line through when the month is unreadable', () => {
		expect(inMonth('2014-06-11', readMonth('13'))).toBe(true);
		expect(inMonth('2014-01-11', readMonth('13'))).toBe(true);
	});
});

describe('the predicate', () => {
	it('reads the month out of an ISO date', () => {
		expect(monthOf('1992-11-16')).toBe(11);
		expect(monthOf('2014-06-01')).toBe(6);
	});

	it('keeps only the month asked for', () => {
		expect(inMonth('2014-06-11', 6)).toBe(true);
		expect(inMonth('2014-07-11', 6)).toBe(false);
	});

	it('keeps everything when no month is asked for', () => {
		expect(inMonth('2014-06-11', null)).toBe(true);
		expect(inMonth('2014-07-11', null)).toBe(true);
	});

	// A month is not a year: June 1994 and June 2014 are the same filter, which
	// is what makes one parameter serve the pooled calendar as well as the grid.
	it('does not care which year the date is in', () => {
		expect(inMonth('1994-06-30', 6)).toBe(true);
		expect(inMonth('2014-06-30', 6)).toBe(true);
	});
});

describe('the links a figure builds', () => {
	it('survives the round trip for every month', () => {
		for (let month = 1; month <= 12; month++) {
			expect(read(cellQuery('genocide', 2014, month).query)).toBe(month);
			expect(read(pooledQuery('genocide', month).query)).toBe(month);
		}
	});

	it('bounds a grid cell to its own year', () => {
		const params = new URLSearchParams(cellQuery('genocide', 2014, 6).query);
		expect(params.get('term')).toBe('genocide');
		expect(params.get('from')).toBe('2014');
		expect(params.get('to')).toBe('2014');
	});

	// The row pools every year. Naming the corpus bounds would freeze a range
	// that means "all", so a later corpus would stop matching the figure.
	it('leaves a pooled row unbounded by year', () => {
		const params = new URLSearchParams(pooledQuery('genocide', 6).query);
		expect(params.get('from')).toBeNull();
		expect(params.get('to')).toBeNull();
	});

	it('says what it opens, so the interface does not have to guess', () => {
		expect(cellQuery('genocide', 2014, 6).scope).toBe('June 2014');
		expect(pooledQuery('genocide', 6).scope).toBe('every June');
	});

	it('escapes a term that would otherwise break the query string', () => {
		const params = new URLSearchParams(cellQuery('crimes against humanity', 2014, 6).query);
		expect(params.get('term')).toBe('crimes against humanity');
	});
});

describe('naming a month', () => {
	it('names the twelve', () => {
		expect(monthName(1)).toBe('January');
		expect(monthName(6)).toBe('June');
		expect(monthName(12)).toBe('December');
	});

	it('has no name for no month', () => {
		expect(monthName(null)).toBeNull();
		expect(describeMonth(null)).toBeNull();
	});

	it('writes the filter the way the export lists it', () => {
		expect(describeMonth(6)).toBe('month: June');
	});
});

const line = (over: Partial<KwicLine>): KwicLine => ({
	id: 'UNSC_2014_SPV.7000_spch0001#1',
	spv: 'S/PV.7000',
	date: '2014-06-11',
	country: 'Rwanda',
	iso3: 'RWA',
	group: 'E10',
	type: 'state',
	agenda: 'Protection of civilians',
	start: 20,
	end: 28,
	left: 'warned that ',
	kw: 'genocide',
	right: ' could occur',
	sent: 'We warned that genocide could occur.',
	...over
});

describe('the complete concordance query state', () => {
	it('defaults to the complete 1946–2024 corpus', () => {
		expect(CONCORDANCE_DEFAULTS.from).toBe(1946);
		expect(CONCORDANCE_DEFAULTS.to).toBe(2024);
		expect(readConcordanceState(new URLSearchParams())).toEqual(CONCORDANCE_DEFAULTS);
	});

	it('round-trips every analytical control', () => {
		const state = {
			...CONCORDANCE_DEFAULTS,
			term: 'war_crimes',
			query: 'tribunal',
			regex: true,
			group: 'E10',
			country: 'Rwanda',
			participantType: 'Mentioned',
			agenda: 'Protection of civilians',
			spv: 'S/PV.7000',
			from: 2014,
			to: 2016,
			month: 6,
			sort: 'right' as const
		};
		expect(readConcordanceState(concordanceParams(state))).toEqual(state);
	});

	it('drops invalid discrete values to visible defaults', () => {
		const state = readConcordanceState(
			new URLSearchParams('from=not-a-year&to=2014.5&month=13&sort=unknown')
		);
		expect(state).toEqual(CONCORDANCE_DEFAULTS);
		expect(concordanceParams(state).toString()).toBe('');
	});

	it('filters repeated occurrences and preserves their requested order', () => {
		const rows = [
			line({ id: 'speech#1', right: ' zebra' }),
			line({ id: 'speech#2', right: ' alpha' }),
			line({ id: 'other#1', country: 'France', right: ' beta' })
		];
		const result = filterConcordance(rows, {
			...CONCORDANCE_DEFAULTS,
			country: 'Rwanda',
			sort: 'right'
		});
		expect(result.lines.map((row) => row.id)).toEqual(['speech#2', 'speech#1']);
		expect(result.badRegex).toBe(false);
	});

	it('filters by the normalized participant type carried by KWIC', () => {
		const rows = [line({ id: 'speech#1', type: 'Mentioned' }), line({ id: 'speech#2' })];
		const result = filterConcordance(rows, {
			...CONCORDANCE_DEFAULTS,
			participantType: 'Mentioned'
		});
		expect(result.lines.map((row) => row.id)).toEqual(['speech#1']);
	});

	it('reports a bad regex without hiding otherwise matching evidence', () => {
		const result = filterConcordance([line({})], {
			...CONCORDANCE_DEFAULTS,
			query: '[',
			regex: true
		});
		expect(result.badRegex).toBe(true);
		expect(result.lines).toHaveLength(1);
	});
});

/**
 * Every sort must be a total order, because ties here are the normal case.
 *
 * One delegation speaks hundreds of times and an occurrence opening a speech
 * has no left context at all, so each sort key leaves large blocks of lines
 * equal. `Array.prototype.sort` being stable is not enough: it preserves the
 * order it was given, and what it is given is a filter over a set re-derived
 * whenever anything upstream changes. The test shuffles the input rather than
 * asserting one arrangement, because the property is that the input order does
 * not survive into the output.
 */
describe('sorting a citable table', () => {
	const SORTS = ['date', 'country', 'agenda', 'left', 'right'] as const;

	// Every field these sorts read is identical; only the IDs differ.
	const tied = [
		line({ id: 'UNSC_2014_SPV.7000_spch0001#3' }),
		line({ id: 'UNSC_2014_SPV.7000_spch0001#1' }),
		line({ id: 'UNSC_2014_SPV.7000_spch0001#2' })
	];

	it.each(SORTS)('orders tied lines identically whatever order they arrive in (%s)', (sort) => {
		const one = filterConcordance(tied, { ...CONCORDANCE_DEFAULTS, sort });
		const reversed = filterConcordance([...tied].reverse(), { ...CONCORDANCE_DEFAULTS, sort });
		expect(one.lines.map((row) => row.id)).toEqual(reversed.lines.map((row) => row.id));
		// And the settled order is the ID's own, not whichever arrived first.
		expect(one.lines.map((row) => row.id)).toEqual([
			'UNSC_2014_SPV.7000_spch0001#1',
			'UNSC_2014_SPV.7000_spch0001#2',
			'UNSC_2014_SPV.7000_spch0001#3'
		]);
	});

	// The tiebreaker must not reach the lines the key already separates.
	it.each([
		['date', [line({ id: 'b#1', date: '2014-06-11' }), line({ id: 'a#1', date: '1994-04-07' })]],
		['country', [line({ id: 'b#1', country: 'Rwanda' }), line({ id: 'a#1', country: 'France' })]],
		['agenda', [line({ id: 'b#1', agenda: 'Zimbabwe' }), line({ id: 'a#1', agenda: 'Angola' })]],
		['right', [line({ id: 'b#1', right: ' zebra' }), line({ id: 'a#1', right: ' alpha' })]]
	] as const)('keeps the key ahead of the tiebreaker (%s)', (sort, rows) => {
		const result = filterConcordance(rows, { ...CONCORDANCE_DEFAULTS, sort });
		expect(result.lines.map((row) => row.id)).toEqual(['a#1', 'b#1']);
	});
});

/**
 * The panel counts what the reader selected, and a click delivers what it said.
 *
 * These two properties are the whole contract. The first is tested against a
 * brute-force recount rather than against expected literals, because the point
 * is that one pass over five dimensions agrees with five obvious passes. The
 * second is what forbids minus-one facet previews: a number on screen is a
 * number the filter will produce.
 */
describe('profiling a result set', () => {
	const corpus = [
		line({ id: 'a#1', date: '1994-04-07', country: 'Rwanda', group: 'E10', agenda: 'Rwanda' }),
		line({ id: 'b#1', date: '1994-06-08', country: 'France', group: 'P5', agenda: 'Rwanda' }),
		line({ id: 'c#1', date: '2014-06-11', country: 'France', group: 'P5', agenda: 'Ukraine' }),
		line({
			id: 'd#1',
			date: '2014-06-12',
			country: 'France',
			group: 'P5',
			agenda: 'Ukraine',
			type: 'Guest'
		})
	];

	it('agrees with counting each dimension separately', () => {
		const profile = profileResult(corpus);
		const brute = <T>(key: (line: KwicLine) => T) => {
			const counts = new Map<T, number>();
			for (const row of corpus) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
			return counts;
		};
		expect(profile.total).toBe(corpus.length);
		expect(profile.years).toEqual(brute((row) => Number(row.date.slice(0, 4))));
		expect(profile.country).toEqual(brute((row) => row.country));
		expect(profile.group).toEqual(brute((row) => row.group));
		expect(profile.participantType).toEqual(brute((row) => row.type));
		expect(profile.agenda).toEqual(brute((row) => row.agenda));
	});

	it('counts what the reader selected, not the whole term', () => {
		const filtered = filterConcordance(corpus, { ...CONCORDANCE_DEFAULTS, country: 'France' });
		const profile = profileResult(filtered.lines);
		expect(profile.total).toBe(3);
		expect(profile.years.get(2014)).toBe(2);
		expect(profile.years.get(1994)).toBe(1);
	});

	// The promise the panel makes: this count is what a click returns.
	it('promises a count a click actually delivers', () => {
		const profile = profileResult(corpus);
		for (const [value, expected] of profile.country) {
			const state = facetClick(CONCORDANCE_DEFAULTS, 'country', value);
			expect(filterConcordance(corpus, state).lines).toHaveLength(expected);
		}
		for (const [year, expected] of profile.years) {
			const state = yearClick(CONCORDANCE_DEFAULTS, year);
			expect(filterConcordance(corpus, state).lines).toHaveLength(expected);
		}
	});

	it('has nothing to say about an empty result set', () => {
		const profile = profileResult([]);
		expect(profile.total).toBe(0);
		expect(profile.country.size).toBe(0);
	});
});

describe('the largest values of a dimension', () => {
	const counts = new Map([
		['France', 10],
		['Rwanda', 6],
		['Nigeria', 3],
		['Chile', 1]
	]);

	it('ranks by count, and breaks ties by name so the column cannot drift', () => {
		const tied = new Map([
			['Zimbabwe', 4],
			['Angola', 4]
		]);
		expect(topFacet(tied, 8).rows.map((row) => row.value)).toEqual(['Angola', 'Zimbabwe']);
	});

	it('states what the cut left out, so eight rows do not read as eight values', () => {
		const facet = topFacet(counts, 2);
		expect(facet.rows.map((row) => row.value)).toEqual(['France', 'Rwanda']);
		expect(facet.remainder).toEqual({ values: 2, count: 4 });
	});

	it('always sums to the total', () => {
		const facet = topFacet(counts, 2);
		const shown = facet.rows.reduce((sum, row) => sum + row.count, 0);
		expect(shown + (facet.remainder?.count ?? 0)).toBe(20);
	});

	it('says nothing was left out when nothing was', () => {
		expect(topFacet(counts, 8).remainder).toBeNull();
	});

	// Otherwise the filter in force could rank below the cut and vanish from the
	// panel that set it, leaving no way to clear it there.
	it('keeps the active value however small it is', () => {
		const facet = topFacet(counts, 2, 'Chile');
		expect(facet.rows.map((row) => row.value)).toEqual(['France', 'Rwanda', 'Chile']);
		expect(facet.rows.find((row) => row.value === 'Chile')?.active).toBe(true);
		expect(facet.remainder).toEqual({ values: 1, count: 3 });
	});
});

describe('narrowing from the panel', () => {
	it('applies a facet value that is not in force', () => {
		const state = facetClick(CONCORDANCE_DEFAULTS, 'country', 'Rwanda');
		expect(state.country).toBe('Rwanda');
	});

	it('clears the value that is', () => {
		const applied = facetClick(CONCORDANCE_DEFAULTS, 'country', 'Rwanda');
		expect(facetClick(applied, 'country', 'Rwanda').country).toBe('');
	});

	it.each(['group', 'country', 'participantType', 'agenda'] as const)(
		'toggles %s without disturbing the other filters',
		(dimension) => {
			const busy = { ...CONCORDANCE_DEFAULTS, term: 'war_crimes', query: 'tribunal', month: 6 };
			const state = facetClick(busy, dimension, 'value');
			expect(state[dimension]).toBe('value');
			expect({ ...state, [dimension]: '' }).toEqual({ ...busy, [dimension]: '' });
		}
	);

	it('narrows to a single year', () => {
		const state = yearClick(CONCORDANCE_DEFAULTS, 2014);
		expect([state.from, state.to]).toEqual([2014, 2014]);
	});

	// Not the range that happened to be in force before: the URL carries no such
	// memory, so restoring one would make the same URL behave two ways.
	it('releases a year to the documented range, not a remembered one', () => {
		const narrowed = yearClick({ ...CONCORDANCE_DEFAULTS, from: 2000, to: 2010 }, 2014);
		const released = yearClick(narrowed, 2014);
		expect([released.from, released.to]).toEqual([
			CONCORDANCE_DEFAULTS.from,
			CONCORDANCE_DEFAULTS.to
		]);
	});

	it('replaces one year with another rather than clearing', () => {
		const state = yearClick(yearClick(CONCORDANCE_DEFAULTS, 2014), 2015);
		expect([state.from, state.to]).toEqual([2015, 2015]);
	});
});

describe('the way out to the chronology', () => {
	// The chronology's state carries a series and nothing else this view knows:
	// no speaker, no agenda item, not even a year range.
	it('carries the term and nothing it cannot honour', () => {
		const params = new URLSearchParams(chronologyEscape('war_crimes').query);
		expect(params.get('series')).toBe('war_crimes');
		expect([...params.keys()]).toEqual(['series']);
	});

	it('says the filters are left behind, because they are', () => {
		expect(chronologyEscape('genocide').scope).toContain('left behind');
	});
});

describe('naming a sort', () => {
	// The defect this closes: the control said "Speaker" and the downloaded file
	// said `sorted by: country`, and only the file outlives the tab.
	it('calls the speaker sort what the interface calls it', () => {
		expect(describeSort('country')).toBe('speaker');
	});

	it('names every sort the state can hold', () => {
		for (const sort of ['date', 'country', 'agenda', 'left', 'right'] as const) {
			expect(describeSort(sort)).toBeTruthy();
		}
	});

	// A sort's serialized value is part of the URL contract; its name is prose.
	// Renaming the parameter to match the label would break copied URLs.
	it('does not rename the parameter it describes', () => {
		const params = concordanceParams({ ...CONCORDANCE_DEFAULTS, sort: 'country' });
		expect(params.get('sort')).toBe('country');
	});
});

describe('the referent facet', () => {
	const lines = [
		line({ id: 'a#1', date: '1994-04-21' }),
		line({ id: 'b#1', date: '2014-04-16' }),
		line({ id: 'c#1', date: '2014-04-17' })
	];
	const referents = new Map([
		['a#1', 'rwanda_1994'],
		['b#1', 'rwanda_1994'],
		['c#1', 'bosnia_srebrenica']
	]);

	it('narrows to the occurrences the model placed on a referent', () => {
		const state = { ...CONCORDANCE_DEFAULTS, referent: 'rwanda_1994' };
		expect(filterConcordance(lines, state, referents).lines.map((l) => l.id)).toEqual([
			'a#1',
			'b#1'
		]);
	});

	it('keeps nothing when the referents are not loaded, never the whole corpus', () => {
		const state = { ...CONCORDANCE_DEFAULTS, referent: 'rwanda_1994' };
		expect(filterConcordance(lines, state, null).lines).toEqual([]);
	});

	it('is off by default and survives the URL round trip', () => {
		expect(filterConcordance(lines, CONCORDANCE_DEFAULTS, referents).lines).toHaveLength(3);
		const params = concordanceParams({ ...CONCORDANCE_DEFAULTS, referent: 'rwanda_1994' });
		expect(params.get('referent')).toBe('rwanda_1994');
		expect(readConcordanceState(params).referent).toBe('rwanda_1994');
		expect(concordanceParams(CONCORDANCE_DEFAULTS).has('referent')).toBe(false);
	});
});
