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

import { MONTH_NAMES, shortCountry } from './format';
import type { KwicLine } from './types';

/** The query parameter this module owns. */
export const MONTH_PARAM = 'month';

export type ConcordanceSort = 'date' | 'country' | 'agenda' | 'left' | 'right';

export interface ConcordanceState {
	term: string;
	query: string;
	regex: boolean;
	group: string;
	country: string;
	agenda: string;
	spv: string;
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
	agenda: '',
	spv: '',
	from: 1992,
	to: 2023,
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
		agenda: params.get('agenda') ?? '',
		spv: params.get('spv') ?? '',
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
	if (state.agenda) params.set('agenda', state.agenda);
	if (state.spv) params.set('spv', state.spv);
	if (state.from !== CONCORDANCE_DEFAULTS.from) params.set('from', String(state.from));
	if (state.to !== CONCORDANCE_DEFAULTS.to) params.set('to', String(state.to));
	if (state.month !== null) params.set(MONTH_PARAM, String(state.month));
	if (state.sort !== CONCORDANCE_DEFAULTS.sort) params.set('sort', state.sort);
	return params;
}

export interface ConcordanceResult {
	lines: KwicLine[];
	badRegex: boolean;
}

/** Apply the same filtering and corpus-linguistic sort in every consumer. */
export function filterConcordance(
	lines: readonly KwicLine[],
	state: ConcordanceState
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
		if (state.agenda && line.agenda !== state.agenda) return false;
		if (state.spv && line.spv !== state.spv) return false;
		return matcher ? matcher(line) : true;
	});

	const tail = (value: string) =>
		[...value.toLowerCase().replace(/[^a-z ]/g, '')].reverse().join('');
	const by: Record<ConcordanceSort, (a: KwicLine, b: KwicLine) => number> = {
		date: (a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id),
		country: (a, b) => shortCountry(a.country).localeCompare(shortCountry(b.country)),
		agenda: (a, b) => a.agenda.localeCompare(b.agenda),
		left: (a, b) => tail(a.left).localeCompare(tail(b.left)),
		right: (a, b) => a.right.toLowerCase().localeCompare(b.right.toLowerCase())
	};
	return { lines: [...rows].sort(by[state.sort]), badRegex };
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
