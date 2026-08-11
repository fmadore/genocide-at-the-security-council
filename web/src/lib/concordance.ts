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

import { MONTH_NAMES } from './format';

/** The query parameter this module owns. */
export const MONTH_PARAM = 'month';

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
