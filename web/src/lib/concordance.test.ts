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
	clearFilter,
	concordanceParams,
	concordanceQuery,
	describeMonth,
	describeSort,
	evidenceTerm,
	exportFilters,
	facetClick,
	filterConcordance,
	filtersInForce,
	historyStep,
	hitsBeyond,
	inMonth,
	monthName,
	monthOf,
	occurrenceInResult,
	pooledQuery,
	profileResult,
	readConcordanceState,
	readMonth,
	referentMap,
	topFacet,
	yearClick
} from './concordance';
import { shortCountry } from './format';
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

	/**
	 * The keys are computed once per line rather than per comparison, and the
	 * order a reader cites must not move because of it. The reference below is
	 * the comparator as it was written before, applied to a set built to collide
	 * on every key: shared speakers and agenda items, empty and punctuated left
	 * contexts, case and accents in the right context, and dates repeated.
	 */
	it.each(SORTS)('orders a colliding set exactly as the per-comparison sort did (%s)', (sort) => {
		const words = ['Genocide', 'genocide,', 'rwanda', 'Rwanda.', 'état', 'etat', '', 'the  law'];
		let seed = 7;
		const pick = <T>(items: readonly T[]): T => {
			seed = (seed * 48271) % 2147483647;
			return items[seed % items.length] as T;
		};
		const rows = Array.from({ length: 400 }, (_, index) =>
			line({
				id: `SC${String(index % 37).padStart(5, '0')}-01-${String(index % 11).padStart(3, '0')}#${index}`,
				date: pick(['1994-04-07', '1994-04-07', '2014-06-11', '1993-11-02']),
				country: pick(['Rwanda', 'France', 'United Kingdom of Great Britain and Northern Ireland']),
				agenda: pick(['The situation in Rwanda', 'Angola', 'the situation in rwanda']),
				left: `${pick(words)} ${pick(words)}`.trim(),
				right: ` ${pick(words)} ${pick(words)}`
			})
		);
		const tail = (value: string) =>
			[...value.toLowerCase().replace(/[^a-z ]/g, '')].reverse().join('');
		const keyOf: Record<(typeof SORTS)[number], (row: KwicLine) => string> = {
			date: (row) => row.date,
			country: (row) => shortCountry(row.country),
			agenda: (row) => row.agenda,
			left: (row) => tail(row.left),
			right: (row) => row.right.toLowerCase()
		};
		const reference = [...rows]
			.sort((a, b) => keyOf[sort](a).localeCompare(keyOf[sort](b)) || a.id.localeCompare(b.id))
			.map((row) => row.id);
		const result = filterConcordance(rows, { ...CONCORDANCE_DEFAULTS, sort });
		expect(result.lines.map((row) => row.id)).toEqual(reference);
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

/** Synthetic derived inputs exercise generic evidence-link compatibility. */
describe('the term a measure opens', () => {
	/** What `kwic/index.json` lists, in miniature: a file per term, nothing derived. */
	const HELD = new Set(['genocide', 'excluded_form', 'war_crimes']);

	/** As `04_series.py` and `11_countries.py` publish them, derived measure included. */
	const PUBLISHED: Record<string, { derived_from?: string }> = {
		genocide: {},
		excluded_form: {},
		war_crimes: {},
		term_subset: { derived_from: 'genocide' }
	};

	it.each(Object.keys(PUBLISHED))('%s opens a term the concordance holds', (measure) => {
		expect(HELD).toContain(evidenceTerm(measure, PUBLISHED[measure]));
	});

	it('leaves a measure that is its own term alone', () => {
		expect(evidenceTerm('war_crimes', PUBLISHED.war_crimes)).toBe('war_crimes');
	});

	it('resolves a subtraction to what it subtracts from', () => {
		expect(evidenceTerm('term_subset', PUBLISHED.term_subset)).toBe('genocide');
	});

	// An archived payload predates `derived_from` and carries only raw terms; a
	// name with nothing published under it is not a measure to invent a term for.
	it('names the measure itself when the artefact says nothing about it', () => {
		expect(evidenceTerm('genocide', undefined)).toBe('genocide');
	});
});

describe('what a change does to the history', () => {
	const at = (query: string) => new URLSearchParams(query);
	const later = { first: false, typing: false };

	it('leaves an unchanged address alone, however its parameters were ordered', () => {
		const next = concordanceQuery(at('from=1994&to=1994&q=Rwanda'));
		const current = concordanceQuery(at('q=Rwanda&to=1994&from=1994'));
		expect(historyStep(next, current, later)).toBe('none');
	});

	it('pushes a narrowing, so Back undoes it', () => {
		expect(historyStep(at('q=Rwanda&group=E10'), at('q=Rwanda'), later)).toBe('push');
		expect(historyStep(at('q=Rwanda&sort=right'), at('q=Rwanda'), later)).toBe('push');
	});

	it('replaces when only the settled search box moved, so Back skips spellings', () => {
		expect(historyStep(at('q=Rwandan'), at('q=Rwanda'), { first: false, typing: true })).toBe(
			'replace'
		);
	});

	it('pushes a reset or a cleared chip that empties the search, which typing did not do', () => {
		// The diff alone is "only the query changed"; what decides is how.
		expect(historyStep(at(''), at('q=Rwanda'), later)).toBe('push');
	});

	it('pushes when typing lands together with another narrowing', () => {
		expect(
			historyStep(at('q=Rwandan&country=France'), at('q=Rwanda'), { first: false, typing: true })
		).toBe('push');
	});

	it('replaces on the first write, which only puts a followed address in canonical form', () => {
		expect(
			historyStep(at('q=Rwanda'), at('q=Rwanda&from=1946'), { first: true, typing: false })
		).toBe('replace');
	});

	it('reads a reader URL back to the concordance it was opened from', () => {
		const reader = at(
			'term=genocide&q=warned&from=2014&to=2014&scope=debate&speech=SC07000-01-001&occurrence=SC07000-01-001%231'
		);
		expect(concordanceQuery(reader).toString()).toBe('q=warned&from=2014&to=2014&scope=debate');
	});
});

describe('the narrowings in force', () => {
	const names = {
		meeting: (spv: string) => `S/PV.${spv}`,
		referent: (id: string) => id.toUpperCase()
	};
	const state = {
		...CONCORDANCE_DEFAULTS,
		query: 'warned',
		regex: true,
		country: 'France',
		spv: '7000',
		referent: 'rwanda',
		from: 2014,
		to: 2014,
		month: 6
	};

	it('names each one by its control, in the order the controls stand', () => {
		expect(filtersInForce(state, names)).toEqual([
			{ key: 'q', label: 'Search', value: 'warned (regex)' },
			{ key: 'country', label: 'Speaker', value: 'France' },
			{ key: 'spv', label: 'Meeting', value: 'S/PV.7000', symbol: true },
			{ key: 'referent', label: 'Case or concept', value: 'RWANDA' },
			{ key: 'years', label: 'Years', value: '2014' },
			{ key: 'month', label: 'Month', value: 'June' }
		]);
	});

	it('counts neither the defaults nor the sort as a narrowing', () => {
		expect(filtersInForce({ ...CONCORDANCE_DEFAULTS, sort: 'right' }, names)).toEqual([]);
		expect(
			filtersInForce({ ...CONCORDANCE_DEFAULTS, from: 1990, to: 1999 }, names).map((c) => c.value)
		).toEqual(['1990–1999']);
	});

	it('clears one and leaves the rest as they were', () => {
		const cleared = clearFilter(state, 'years');
		expect(cleared.from).toBe(CONCORDANCE_DEFAULTS.from);
		expect(cleared.to).toBe(CONCORDANCE_DEFAULTS.to);
		expect(filtersInForce(cleared, names).map((c) => c.key)).toEqual([
			'q',
			'country',
			'spv',
			'referent',
			'month'
		]);
	});

	it('takes the pattern switch away with the search it qualifies', () => {
		const cleared = clearFilter(state, 'q');
		expect(cleared.query).toBe('');
		expect(cleared.regex).toBe(false);
	});

	it('writes every chip into the exported file, the referent included', () => {
		// Every chip is a narrowing of the rows, so every one belongs in the file:
		// a download filtered to one referent has to say so.
		const everything = {
			...state,
			group: 'E10',
			participantType: 'Mentioned',
			agenda: 'Protection of civilians',
			country: 'United Kingdom of Great Britain and Northern Ireland'
		};
		expect(exportFilters(everything, names)).toEqual([
			'search: warned (regex)',
			'group: E10',
			// The file writes the speaker as the corpus does, not as the chip shortens it.
			'speaker: United Kingdom of Great Britain and Northern Ireland',
			'participant type: Mentioned',
			'agenda: Protection of civilians',
			'meeting: 7000',
			'referent: RWANDA',
			'years: 2014–2014',
			'month: June',
			'sorted by: date'
		]);
		expect(
			exportFilters(everything, names).filter((entry) => !entry.startsWith('sorted by'))
		).toHaveLength(filtersInForce(everything, names).length);
	});

	it('exports the sort alone when nothing narrows the lines', () => {
		expect(exportFilters({ ...CONCORDANCE_DEFAULTS, sort: 'left' }, names)).toEqual([
			'sorted by: the word before the match'
		]);
	});
});

describe('an occurrence opened from a filtered concordance', () => {
	const rows = [
		line({ id: 'a#1', date: '1994-04-07' }),
		line({ id: 'b#1', date: '1995-01-01', country: 'France' }),
		line({ id: 'c#1', date: '1996-01-01' }),
		line({ id: 'd#1', date: '1997-01-01' })
	];
	const placements = referentMap([
		{ id: 'a#1', referent: 'rwanda_1994' },
		{ id: 'b#1', referent: 'rwanda_1994' },
		{ id: 'c#1', referent: '' },
		{ id: 'd#1', referent: 'rwanda_1994' }
	]);

	it('leaves unplaced occurrences out of the referent map', () => {
		expect([...placements.keys()]).toEqual(['a#1', 'b#1', 'd#1']);
	});

	it('walks previous and next through the referent filter it was opened under', () => {
		const state = { ...CONCORDANCE_DEFAULTS, referent: 'rwanda_1994' };
		const found = occurrenceInResult(rows, state, 'b#1', placements);
		expect(found.line?.id).toBe('b#1');
		expect(found.position).toEqual({ position: 2, total: 3, previous: 'a#1', next: 'd#1' });
	});

	it('keeps the occurrence when the referent placements did not load', () => {
		// Without the map the filter keeps nothing. The occurrence is still the
		// one in the URL, so quoting, keeping and citing it must survive; only the
		// walk through a result set nobody can rebuild is withheld.
		const state = { ...CONCORDANCE_DEFAULTS, referent: 'rwanda_1994' };
		const found = occurrenceInResult(rows, state, 'b#1', null);
		expect(found.line?.id).toBe('b#1');
		expect(found.position).toBeNull();
	});

	it('keeps an occurrence the other filters exclude, without a position', () => {
		const state = { ...CONCORDANCE_DEFAULTS, country: 'Rwanda' };
		const found = occurrenceInResult(rows, state, 'b#1');
		expect(found.line?.id).toBe('b#1');
		expect(found.position).toBeNull();
		expect(occurrenceInResult(rows, state, 'c#1').position).toEqual({
			position: 2,
			total: 3,
			previous: 'a#1',
			next: 'd#1'
		});
	});

	it('finds nothing for an id the term does not carry', () => {
		expect(occurrenceInResult(rows, CONCORDANCE_DEFAULTS, 'z#9')).toEqual({
			line: null,
			position: null
		});
	});
});

describe('a search hit past the cut end of its context', () => {
	const box = { left: 100, right: 400 };

	it('is beyond when every hit lies outside the box', () => {
		expect(hitsBeyond(box, [{ left: 10, right: 60 }])).toBe(true);
		expect(hitsBeyond(box, [{ left: 420, right: 480 }])).toBe(true);
	});

	it('is not beyond when any hit shows', () => {
		expect(
			hitsBeyond(box, [
				{ left: 10, right: 60 },
				{ left: 200, right: 250 }
			])
		).toBe(false);
	});

	it('treats a hit under the ellipsis as hidden', () => {
		expect(hitsBeyond(box, [{ left: 395, right: 450 }])).toBe(true);
	});

	it('is never beyond with no hits at all', () => {
		expect(hitsBeyond(box, [])).toBe(false);
	});
});
