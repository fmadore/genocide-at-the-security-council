/**
 * What `month` means in a concordance URL, and who is allowed to say it.
 *
 * `docs/PLAN.md` §7's fifth item shipped the year × month heatmap with a defect
 * recorded rather than left to be found: the concordance filtered lines by year,
 * so a cell could not open the evidence behind *itself*. The table under the
 * grid linked each year and the interface said so, which made the figure honest
 * about being wider than the square a reader had just looked at. This module is
 * that square closing.
 *
 * **A month of the year, not a `YYYY-MM` period.** The obvious parameter would
 * name the cell — `month=2014-06` — and it would serve one of the two figures.
 * The pooled calendar beside the grid is thirty-two Junes, and a period string
 * cannot express it without a second, incompatible form. A month of the year is
 * orthogonal to the year range the contract already carries, so one parameter
 * serves both: a grid cell is `month=6` inside `from=2014&to=2014`, a calendar
 * row is `month=6` across every year. That is also the shape of the artefact —
 * `monthly.json` publishes the grid and `month_of_year` as two readings of one
 * table — so the URL says what the data says.
 *
 * **An unreadable month does not filter.** `month=13`, `month=foo` and an empty
 * value all read as no month at all, and the alternative was considered: a
 * malformed value could filter to nothing, which announces itself loudly. It
 * would also hide evidence on the strength of a typo, and the concordance's
 * existing year bounds already take the lenient reading — `Number('foo')` is
 * `NaN` and every comparison against it is false, so a broken `from` filters
 * nothing today. What keeps the lenient reading honest is that the control is
 * the disclosure: the select shows "All months" whenever `readMonth` returns
 * null, so the interface never claims a month it is not showing, and the URL
 * effect drops the bad parameter on the first write.
 *
 * **Padded and unpadded are the same month.** Periods are written `2014-06`, so
 * a caller building a link from one will pass `06`. Refusing that would be a
 * contract that fails for the most obvious way to use it.
 */

import { speechOf } from './data';
import { MONTH_NAMES, shortCountry } from './format';
import { readScope, withScope } from './scope';
import type { KwicLine } from './types';

/** The query parameter this module owns. */
export const MONTH_PARAM = 'month';

export type ConcordanceSort = 'date' | 'country' | 'agenda' | 'left' | 'right';

/** Inclusive bounds of the pinned Sakamoto–Matsuoka v5.0 corpus. */
export const CORPUS_START_YEAR = 1946;
export const CORPUS_END_YEAR = 2024;

export interface ConcordanceState {
	term: string;
	query: string;
	regex: boolean;
	group: string;
	country: string;
	participantType: string;
	agenda: string;
	spv: string;
	/**
	 * A referent from the published model run, or empty. Model-derived: the
	 * concordance can narrow to "the occurrences the model placed on Rwanda",
	 * and says so beside the control, but it is a reading and not a coding.
	 */
	referent: string;
	from: number;
	to: number;
	month: number | null;
	sort: ConcordanceSort;
}

export const CONCORDANCE_DEFAULTS: ConcordanceState = {
	term: 'genocide',
	query: '',
	regex: false,
	group: '',
	country: '',
	participantType: '',
	agenda: '',
	spv: '',
	referent: '',
	from: CORPUS_START_YEAR,
	to: CORPUS_END_YEAR,
	month: null,
	sort: 'date'
};

const SORTS = new Set<ConcordanceSort>(['date', 'country', 'agenda', 'left', 'right']);

const year = (value: string | null, fallback: number): number => {
	if (value === null || value.trim() === '') return fallback;
	const parsed = Number(value);
	return Number.isInteger(parsed) ? parsed : fallback;
};

/** Read the complete analytical state from a URL, with explicit safe defaults. */
export function readConcordanceState(params: URLSearchParams): ConcordanceState {
	const askedSort = params.get('sort') as ConcordanceSort | null;
	return {
		term: params.get('term') || CONCORDANCE_DEFAULTS.term,
		query: params.get('q') ?? '',
		regex: params.get('re') === '1',
		group: params.get('group') ?? '',
		country: params.get('country') ?? '',
		participantType: params.get('type') ?? '',
		agenda: params.get('agenda') ?? '',
		spv: params.get('spv') ?? '',
		referent: params.get('referent') ?? '',
		from: year(params.get('from'), CONCORDANCE_DEFAULTS.from),
		to: year(params.get('to'), CONCORDANCE_DEFAULTS.to),
		month: readMonth(params.get(MONTH_PARAM)),
		sort: askedSort && SORTS.has(askedSort) ? askedSort : CONCORDANCE_DEFAULTS.sort
	};
}

/** Serialize only state that differs from the documented concordance defaults. */
export function concordanceParams(state: ConcordanceState): URLSearchParams {
	const params = new URLSearchParams();
	if (state.term !== CONCORDANCE_DEFAULTS.term) params.set('term', state.term);
	if (state.query) params.set('q', state.query);
	if (state.regex) params.set('re', '1');
	if (state.group) params.set('group', state.group);
	if (state.country) params.set('country', state.country);
	if (state.participantType) params.set('type', state.participantType);
	if (state.agenda) params.set('agenda', state.agenda);
	if (state.spv) params.set('spv', state.spv);
	if (state.referent) params.set('referent', state.referent);
	if (state.from !== CONCORDANCE_DEFAULTS.from) params.set('from', String(state.from));
	if (state.to !== CONCORDANCE_DEFAULTS.to) params.set('to', String(state.to));
	if (state.month !== null) params.set(MONTH_PARAM, String(state.month));
	if (state.sort !== CONCORDANCE_DEFAULTS.sort) params.set('sort', state.sort);
	return params;
}

/**
 * The query a link into `/reader/[meeting]` carries, for one occurrence.
 *
 * Everything the reader needs to reproduce what the sender was looking at: the
 * filter in force, so the previous/next occurrence walk the same result set;
 * the speech, so the record opens at it; and the occurrence, so the exact
 * matched span is the one marked and scrolled to.
 *
 * `term` is written even when it is the default. The concordance may omit it
 * from its own URL — that is what a default is for — but the reader needs it to
 * know which term-specific ordinal the occurrence ID names, and a link that
 * relied on the reader guessing would break the day the default changed.
 *
 * The route itself is not built here. `resolve()` is a SvelteKit virtual
 * module, so a component composes `resolve('/reader/[meeting]', …)` with this
 * string — the same division `actors.ts` makes for its concordance links.
 */
export function readerQuery(state: ConcordanceState, lineId: string): string {
	const params = concordanceParams(state);
	params.set('term', state.term);
	params.set('speech', speechOf(lineId));
	params.set('occurrence', lineId);
	return params.toString();
}

export interface ConcordanceResult {
	lines: KwicLine[];
	badRegex: boolean;
}

/** Apply the same filtering and corpus-linguistic sort in every consumer. */
export function filterConcordance(
	lines: readonly KwicLine[],
	state: ConcordanceState,
	/**
	 * Occurrence id → referent id, from `usage/occurrences.json`. Without it a
	 * referent filter keeps nothing rather than everything: a URL that asks for
	 * Rwanda must never show the whole corpus under a heading that says Rwanda.
	 */
	referents: ReadonlyMap<string, string> | null = null
): ConcordanceResult {
	let matcher: ((line: KwicLine) => boolean) | null = null;
	let badRegex = false;
	if (state.query.trim()) {
		if (state.regex) {
			try {
				const pattern = new RegExp(state.query, 'i');
				matcher = (line) => pattern.test(`${line.left} ${line.kw} ${line.right}`);
			} catch {
				badRegex = true;
			}
		} else {
			const needle = state.query.toLowerCase();
			matcher = (line) => `${line.left} ${line.kw} ${line.right}`.toLowerCase().includes(needle);
		}
	}

	const rows = lines.filter((line) => {
		const lineYear = Number(line.date.slice(0, 4));
		if (lineYear < state.from || lineYear > state.to) return false;
		if (!inMonth(line.date, state.month)) return false;
		if (state.group && line.group !== state.group) return false;
		if (state.country && line.country !== state.country) return false;
		if (state.participantType && line.type !== state.participantType) return false;
		if (state.agenda && line.agenda !== state.agenda) return false;
		if (state.spv && line.spv !== state.spv) return false;
		if (state.referent && referents?.get(line.id) !== state.referent) return false;
		return matcher ? matcher(line) : true;
	});

	/**
	 * Every sort ends on the occurrence ID, because ties are the normal case here.
	 *
	 * A delegation speaks hundreds of times, an agenda item names thousands of
	 * lines, and an occurrence at the start of a speech has no left context at
	 * all — so each of these keys leaves large blocks of lines equal. `sort` is
	 * stable in every engine the site supports, but stability only preserves the
	 * *input* order, and the input is a filter over a set that is re-derived
	 * whenever anything upstream changes. `actors.ts` states the standard this
	 * meets: a table that reorders itself is a table a reader cannot cite. The ID
	 * is the tiebreaker because it is the one key that is unique by construction.
	 *
	 * Each line's key is computed once, before the sort, rather than inside the
	 * comparator. A comparison sort calls the comparator about n log n times, so
	 * a key built per call was built some thirty times per line on the largest
	 * terms — and the reversed left context, a string rebuilt character by
	 * character, made that sort take seconds on every filter change and every
	 * previous/next in the reader.
	 */
	const key = SORT_KEYS[state.sort];
	const keyed = rows.map((line) => ({ line, key: key(line) }));
	keyed.sort((a, b) => COLLATOR.compare(a.key, b.key) || COLLATOR.compare(a.line.id, b.line.id));
	return { lines: keyed.map((entry) => entry.line), badRegex };
}

/**
 * The collation every concordance sort uses.
 *
 * One instance rather than `localeCompare` per comparison: with no arguments
 * the two are defined to compare identically, and `localeCompare` constructs
 * the equivalent collator on every call.
 */
const COLLATOR = new Intl.Collator();

/** The left context read backwards, letters and spaces only, so lines group on the word before the match. */
const tail = (value: string) => [...value.toLowerCase().replace(/[^a-z ]/g, '')].reverse().join('');

/** What each sort orders a line by, before the ID breaks the tie. */
const SORT_KEYS: Record<ConcordanceSort, (line: KwicLine) => string> = {
	date: (line) => line.date,
	country: (line) => shortCountry(line.country),
	agenda: (line) => line.agenda,
	left: (line) => tail(line.left),
	right: (line) => line.right.toLowerCase()
};

/**
 * What a sort is called, in the one place both the control and the file read.
 *
 * The serialized value is `country`, and it stays that way: URLs of this site
 * are citable, and renaming a parameter to match a label would break every one
 * a reader has already copied. But the control has always said "Speaker" —
 * `country` on this corpus holds delegations and organisations alike — while
 * the exported filter list said `sorted by: country`. Two names for one choice,
 * one of them visible only after the download. This function is the name, and
 * both callers take it from here.
 */
export function describeSort(sort: ConcordanceSort): string {
	const names: Record<ConcordanceSort, string> = {
		date: 'date',
		country: 'speaker',
		agenda: 'agenda item',
		left: 'the word before the match',
		right: 'the word after the match'
	};
	return names[sort];
}

/**
 * The month a URL asks for, 1–12, or null when it does not honestly ask for one.
 *
 * Integers only: `6.5` is not a month, and `Math.round` would silently make it
 * one. `Number` is what turns `'06'` into 6 and `'foo'` into `NaN`, and
 * `Number.isInteger(NaN)` is false, so both wrong answers fail the same test.
 */
export function readMonth(value: string | null | undefined): number | null {
	if (value === null || value === undefined || value.trim() === '') return null;
	const month = Number(value);
	if (!Number.isInteger(month) || month < 1 || month > 12) return null;
	return month;
}

/** `1992-11-16` → 11. The corpus writes dates ISO-first, which is why this works. */
export const monthOf = (date: string): number => Number(date.slice(5, 7));

/**
 * Whether a line belongs to the filtered month.
 *
 * True for every line when no month is in force, so a caller can apply this
 * unconditionally rather than branching around it — a filter that has to be
 * remembered is a filter that will be forgotten in one of the two places it
 * belongs.
 */
export function inMonth(date: string, month: number | null): boolean {
	return month === null || monthOf(date) === month;
}

/** `6` → `June`. Out of range returns null rather than an off-by-one label. */
export function monthName(month: number | null): string | null {
	return month === null ? null : (MONTH_NAMES[month - 1] ?? null);
}

/**
 * The month as the export's filter list writes it, or null when there is none.
 *
 * §7.5's second constraint: a downloaded file carries what it was narrowed by,
 * so a CSV that outlives the tab still says it holds one month.
 */
export function describeMonth(month: number | null): string | null {
	const name = monthName(month);
	return name === null ? null : `month: ${name}`;
}

/** Where a figure sends a reader for the lines behind one of its own numbers. */
export interface EvidenceQuery {
	/** Query string for `/concordance`, without the leading `?`. */
	query: string;
	/** What the link opens, in words, for the interface that offers it. */
	scope: string;
}

/** Resolve evidence links to a source term, including archived derived inputs. */
export function evidenceTerm(
	measure: string,
	published: { derived_from?: string } | undefined
): string {
	return published?.derived_from ?? measure;
}

/**
 * The lines behind one square of the grid: one term, one month, one year.
 *
 * `from` and `to` are both the cell's year rather than omitted, because the
 * concordance defaults to the whole corpus and a link that leaves them out
 * would open thirty-two Junes from a figure about one.
 */
export function cellQuery(term: string, year: number, month: number): EvidenceQuery {
	const params = new URLSearchParams({
		term,
		[MONTH_PARAM]: String(month),
		from: String(year),
		to: String(year)
	});
	return { query: params.toString(), scope: `${monthName(month) ?? month} ${year}` };
}

/**
 * The lines behind one row of the pooled calendar: one term, one month, every year.
 *
 * The years are left unset on purpose — the row pools all of them, and naming
 * the corpus bounds in the URL would freeze a range that is meant to be "all",
 * so a later corpus extension would quietly stop matching the figure.
 */
export function pooledQuery(term: string, month: number): EvidenceQuery {
	const params = new URLSearchParams({ term, [MONTH_PARAM]: String(month) });
	return { query: params.toString(), scope: `every ${monthName(month) ?? month}` };
}

/* -------------------------------------------------------------------------- *
 * The profile of a result set
 *
 * Everywhere else on this site a count is refused as evidence, because a count
 * of speeches is partly a picture of when the Council met — that is the whole
 * argument of `heatmap.ts` and the reason the grid shades rates and nothing
 * else. Nothing below repeals that. What it does is answer a different
 * question: not "did the Council say this more in 2014" but "what am I
 * currently looking at". The set being counted is one the reader assembled with
 * the filters, and every count exists to be clicked back into that filter, so
 * the honest unit here is the raw line and the component that renders these
 * says so in as many words.
 *
 * Two consequences shape the code. The functions take the lines the view has
 * *already* filtered and never re-filter — the concordance re-derives its
 * filter over as many as 51,000 lines whenever anything upstream moves, and
 * doing that twice for a panel would be paid on every keystroke. And there are
 * no minus-one facet previews: a count shown is a count a click produces, so
 * the panel can never promise a number the filter then fails to deliver.
 * -------------------------------------------------------------------------- */

/** The dimensions a result set can be profiled and narrowed by. */
export type FacetDimension = 'group' | 'country' | 'participantType' | 'agenda';

/** Counts of one result set, by year and by each categorical dimension. */
export interface ResultProfile {
	total: number;
	years: Map<number, number>;
	group: Map<string, number>;
	country: Map<string, number>;
	participantType: Map<string, number>;
	agenda: Map<string, number>;
}

const tally = <T>(counts: Map<T, number>, key: T): void => {
	counts.set(key, (counts.get(key) ?? 0) + 1);
};

/**
 * Count a filtered result set once, along every dimension at once.
 *
 * One pass rather than five: the caller hands over lines that are already the
 * answer to its filter, and a second traversal per dimension would multiply the
 * cost of the largest term by five for no additional truth.
 */
export function profileResult(lines: readonly KwicLine[]): ResultProfile {
	const profile: ResultProfile = {
		total: lines.length,
		years: new Map(),
		group: new Map(),
		country: new Map(),
		participantType: new Map(),
		agenda: new Map()
	};
	for (const line of lines) {
		tally(profile.years, Number(line.date.slice(0, 4)));
		tally(profile.group, line.group);
		tally(profile.country, line.country);
		tally(profile.participantType, line.type);
		tally(profile.agenda, line.agenda);
	}
	return profile;
}

/** One row of a facet column: a value, its count, and whether it is in force. */
export interface FacetRow {
	value: string;
	count: number;
	active: boolean;
}

/** A facet column: the largest values, and an honest account of the rest. */
export interface Facet {
	rows: FacetRow[];
	/** The values not shown, or null when every value is. */
	remainder: { values: number; count: number } | null;
}

/**
 * The largest values of one dimension, with what was left out stated.
 *
 * A top-N cut that does not say it is a cut is the display decision
 * `docs/PLAN.md` §7.5 refuses in exports, and the objection holds on screen:
 * 133 delegations do not fit a panel, but a reader must not conclude from eight
 * rows that there were eight. The remainder row carries both how many values
 * and how many lines are outside the cut, so the column always sums to the
 * total.
 *
 * An active value is kept whatever its rank. Dropping the filter in force out
 * of the bottom of its own column would leave a reader no way to clear it from
 * the panel that set it.
 */
export function topFacet(counts: Map<string, number>, limit: number, active: string = ''): Facet {
	const ordered = [...counts.entries()].sort(
		([leftValue, left], [rightValue, right]) => right - left || leftValue.localeCompare(rightValue)
	);
	const shown = ordered.slice(0, limit);
	if (active && !shown.some(([value]) => value === active)) {
		const found = ordered.find(([value]) => value === active);
		if (found) shown.push(found);
	}
	const rows = shown.map(([value, count]) => ({ value, count, active: value === active }));
	const hidden = ordered.filter(([value]) => !rows.some((row) => row.value === value));
	return {
		rows,
		remainder: hidden.length
			? { values: hidden.length, count: hidden.reduce((sum, [, count]) => sum + count, 0) }
			: null
	};
}

/**
 * Apply a facet value, or clear it when it is the one already in force.
 *
 * Toggling rather than only narrowing is what makes the panel a control instead
 * of a one-way street: the row that set a filter is the row that releases it,
 * and a reader never has to find the select it came from to undo it.
 */
export function facetClick(
	state: ConcordanceState,
	dimension: FacetDimension,
	value: string
): ConcordanceState {
	return { ...state, [dimension]: state[dimension] === value ? '' : value };
}

/**
 * Narrow to one year, or release that year back to the documented range.
 *
 * Releasing restores the defaults rather than whatever range was in force
 * before, and deliberately so. A previous range is state the URL does not
 * carry, so remembering it would make the same URL behave differently
 * depending on how the reader arrived — which is the one thing the query-state
 * contract exists to prevent.
 */
export function yearClick(state: ConcordanceState, year: number): ConcordanceState {
	const only = state.from === year && state.to === year;
	return {
		...state,
		from: only ? CONCORDANCE_DEFAULTS.from : year,
		to: only ? CONCORDANCE_DEFAULTS.to : year
	};
}

/**
 * The chronology of the same term — and an exact account of what is lost.
 *
 * The concordance can say "Rwanda, June, 1994" and the chronology cannot: its
 * query state carries the series, the unit and the grain, but no speaker, no
 * agenda item and not even a year range. So this link cannot preserve the
 * reader's question, and the design decision is to say so in the label rather
 * than to hide the link when filters are active. A link that appears and
 * disappears according to a rule the interface never states is a rule the
 * reader has to reverse-engineer; one that is always there and always honest
 * about its own scope can simply be read.
 */
export function chronologyEscape(term: string): EvidenceQuery {
	return {
		query: new URLSearchParams({ series: term }).toString(),
		scope: 'every speech, the whole corpus, with the filters here left behind'
	};
}

/* --- The concordance's history, its narrowings and its cut ends -------------
   Decisions the route used to make inline, moved here at the boundary where
   they sit (RV31, review of 24 September 2026): what a change does to the
   history, which narrowings are in force and what clearing one leaves, and
   whether a context's hits are all out of sight. The route keeps the controls
   and the measuring; what it does with a measurement is decided here. */

/**
 * The concordance's own query, with the reading set beside it, read back out
 * of any URL that carries it.
 *
 * Read and re-written rather than copied, so two addresses that mean the same
 * concordance compare equal however their parameters were ordered, and a
 * reader URL — which carries the same state plus the speech and occurrence —
 * gives back exactly the concordance it was opened from.
 */
export function concordanceQuery(params: URLSearchParams): URLSearchParams {
	return withScope(concordanceParams(readConcordanceState(params)), readScope(params));
}

/** What a change of state does to the browser's history. */
export type HistoryStep = 'none' | 'replace' | 'push';

/**
 * Push, replace, or leave the history alone.
 *
 * Every change used to replace the entry it was on. Back therefore left the
 * concordance altogether, and "Reset filters" wiped nine narrowings with no
 * way to get them back (review of 19 September 2026). A narrowing — a speaker,
 * an agenda item, the years, a sort, a reset — now pushes an entry of its own.
 * Typing in the search box still replaces: a query is refined a few letters at
 * a time, and one entry per pause would make Back step through spellings. So
 * the replace needs both facts — that the box settled, and that the query is
 * all that changed — because a reset or a chip can clear the search too, and
 * those are steps a reader may want to undo. The first write after the page
 * loads replaces as well: it only puts an address the reader already followed
 * into canonical form.
 */
export function historyStep(
	next: URLSearchParams,
	current: URLSearchParams,
	how: { first: boolean; typing: boolean }
): HistoryStep {
	if (next.toString() === current.toString()) return 'none';
	if (how.first) return 'replace';
	const onlyQuery = [...new Set([...next.keys(), ...current.keys()])].every(
		(key) => key === 'q' || next.get(key) === current.get(key)
	);
	return how.typing && onlyQuery ? 'replace' : 'push';
}

/** A narrowing a reader can see and clear. The sort is not one: it removes no line. */
export type FilterKey =
	'q' | 'group' | 'country' | 'type' | 'agenda' | 'spv' | 'referent' | 'years' | 'month';

export interface FilterChip {
	key: FilterKey;
	/** The control's own name, so the chip reads as the control it undoes. */
	label: string;
	value: string;
	/** Set in the typewriter face: a meeting symbol is a citation. */
	symbol?: boolean;
}

/**
 * Every narrowing in force, in the order the controls stand.
 *
 * Only the meeting filter used to have a chip; the other eight lived as
 * whatever a select happened to show, scattered along a wrapping bar, and a
 * reader arriving from a chart's link could not tell what had been applied to
 * the lines in front of them (review of 19 September 2026). The two lookups are
 * the route's, because the labels they need are loaded there.
 */
export function filtersInForce(
	state: ConcordanceState,
	names: { meeting: (spv: string) => string; referent: (id: string) => string }
): FilterChip[] {
	const chips: FilterChip[] = [];
	if (state.query) {
		chips.push({
			key: 'q',
			label: 'Search',
			value: `${state.query}${state.regex ? ' (regex)' : ''}`
		});
	}
	if (state.group) chips.push({ key: 'group', label: 'Speaker group', value: state.group });
	if (state.country) {
		chips.push({ key: 'country', label: 'Speaker', value: shortCountry(state.country) });
	}
	if (state.participantType) {
		chips.push({ key: 'type', label: 'Participant type', value: state.participantType });
	}
	if (state.agenda) chips.push({ key: 'agenda', label: 'Agenda item', value: state.agenda });
	if (state.spv) {
		chips.push({ key: 'spv', label: 'Meeting', value: names.meeting(state.spv), symbol: true });
	}
	if (state.referent) {
		chips.push({
			key: 'referent',
			label: 'Case or concept',
			value: names.referent(state.referent)
		});
	}
	if (state.from !== CONCORDANCE_DEFAULTS.from || state.to !== CONCORDANCE_DEFAULTS.to) {
		chips.push({
			key: 'years',
			label: 'Years',
			value: state.from === state.to ? String(state.from) : `${state.from}–${state.to}`
		});
	}
	if (state.month !== null) {
		chips.push({
			key: 'month',
			label: 'Month',
			value: monthName(state.month) ?? String(state.month)
		});
	}
	return chips;
}

/** The state with one narrowing cleared and everything else as it was. */
export function clearFilter(state: ConcordanceState, key: FilterKey): ConcordanceState {
	switch (key) {
		case 'q':
			// The pattern switch belongs to the search it qualifies.
			return { ...state, query: '', regex: false };
		case 'group':
			return { ...state, group: '' };
		case 'country':
			return { ...state, country: '' };
		case 'type':
			return { ...state, participantType: '' };
		case 'agenda':
			return { ...state, agenda: '' };
		case 'spv':
			return { ...state, spv: '' };
		case 'referent':
			return { ...state, referent: '' };
		case 'years':
			return { ...state, from: CONCORDANCE_DEFAULTS.from, to: CONCORDANCE_DEFAULTS.to };
		case 'month':
			return { ...state, month: null };
	}
}

/** A box along the line, in viewport pixels. */
interface Span {
	left: number;
	right: number;
}

/**
 * Whether every search hit in a context lies past the edge of its box.
 *
 * A context is loaded at the full width the index declares and drawn at what
 * the column allows: 87 to 90 characters a side on a wide screen, 20 on a
 * phone. Search reads the whole of it, so on a search for "Rwanda" 14 of 60
 * rows matched on a word the reader could not see (review of 19 September
 * 2026). A context with no hits is never "beyond". The slack is the ellipsis,
 * which takes the last few pixels of the box and hides what is under it.
 */
export function hitsBeyond(box: Span, hits: readonly Span[], slack = 8): boolean {
	return (
		hits.length > 0 &&
		hits.every((hit) => hit.right <= box.left + slack || hit.left >= box.right - slack)
	);
}
