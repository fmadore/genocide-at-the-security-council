/**
 * The decisions behind the membership view, kept out of the component.
 *
 * `docs/PLAN.md` §3 wrote this table before it allowed anything to draw it, and
 * the reason is the finding in the table itself: **membership is a property of a
 * speech, not of a country**. The elected ten rotate, so a speaker has no single
 * status — Rwanda spoke as an elected member in 1994 and 2013–14 and as a
 * non-member in every other year of the corpus. 105 of the 601 speakers spoke
 * both from a seat and from outside one, 5 only ever from a seat, and 491 never.
 *
 * That rules out the obvious visual. Shading a speaker with one membership
 * colour would be wrong about the first group, which is the group worth looking
 * at, and §7.3 says so in as many words. So a row here is a **composition** —
 * the five counts that sum to the speaker's own denominator — and never a label.
 *
 * Three further decisions are the artefact's rather than this module's, and are
 * honoured rather than re-derived:
 *
 * **All five counts are drawn, not just the seated total.** "Not seated" covers
 * three different situations — a state that was not on the Council, the UN
 * Secretariat which never can be, and an invited non-state speaker — and a
 * single share erases the difference. The two seated groups are the Charter's
 * two kinds of membership; the interface gives those one visual family and the
 * other three another, which is the distinction `seated_rule` describes.
 *
 * **There is no minimum here.** Every other figure over this artefact withholds
 * below 100 speeches. This one does not, and the asymmetry is the point: a share
 * of a speaker's own known speeches is a fact about the record, not an estimate
 * from a sample. Nothing in this module filters on a denominator, and
 * `categorise()` uses the integer counts rather than the share so that a
 * speaker's category never turns on a floating-point comparison.
 *
 * **A whole-corpus row is not a sum of the period rows.** A speaker can be
 * seated for a decade and not for the corpus. `plan()` works within one period
 * and reports which, so the two are never added.
 */

import type { CountryPeriod, Countries, Speaker, StandingRow } from './types';

/**
 * What a speaker's record looks like across the whole of a period.
 *
 * `changed` is the group that makes this a composition rather than a label, and
 * it is named first because it is the one a reader should look at.
 */
export type Category = 'changed' | 'always' | 'never';

export type Ordering = 'held' | 'seated_share' | 'name';

export interface Segment {
	group: string;
	count: number;
	/** Of the speaker's own denominator. */
	share: number;
	/** Cumulative percentages, so a caller can lay the row out in one pass. */
	from: number;
	to: number;
	seated: boolean;
}

export interface StandingEntry {
	speaker: Speaker | undefined;
	row: StandingRow;
	category: Category;
	/** Only the groups the speaker actually spoke in; the table shows the zeros. */
	segments: Segment[];
}

export interface StandingPlan {
	rows: StandingEntry[];
	/** Every speaker in the period, by category — including those not drawn. */
	counts: Record<Category, number>;
	period: CountryPeriod | undefined;
	order: Ordering;
	category: Category | 'all';
	groups: string[];
	seatedGroups: Set<string>;
	refusal: 'no-period' | 'none-in-category' | null;
}

export interface StandingRequest {
	data: Countries;
	period: string;
	category?: Category | 'all';
	order?: Ordering;
}

/**
 * Which of the three records a row is.
 *
 * On the integer counts, never on `seated_share`: a share of 0.9999999 is a
 * speaker that changed, and comparing a float to 1 would put it with the five
 * that never did. The counts are exact and their sum is checked upstream.
 */
export function categorise(row: StandingRow): Category {
	if (row.seated === 0) return 'never';
	if (row.seated === row.held) return 'always';
	return 'changed';
}

/**
 * A row's composition, as cumulative bands.
 *
 * Zero-count groups are left out of the bands and kept in the table: a band of
 * no width draws nothing but adds a stop to every gradient, and a column of
 * zeros is information — it says the speaker was never in that position, which
 * is different from the group not existing.
 */
export function segments(row: StandingRow, groups: string[], seated: Set<string>): Segment[] {
	const out: Segment[] = [];
	let cursor = 0;
	for (const group of groups) {
		const count = row.groups[group] ?? 0;
		if (count <= 0) continue;
		const share = row.held > 0 ? count / row.held : 0;
		const from = cursor;
		cursor = Math.min(cursor + share * 100, 100);
		out.push({ group, count, share, from, to: cursor, seated: seated.has(group) });
	}
	// Rounding can leave the last band a hair short of the full width, which
	// reads as a sliver of background at the end of a complete row.
	if (out.length) out[out.length - 1].to = 100;
	return out;
}

/** The speakers to draw for one period, and how many were left out of the cut. */
export function plan(request: StandingRequest): StandingPlan {
	const { data, period, category = 'changed', order = 'held' } = request;
	const standing = data.standing;
	const groups = standing?.groups ?? [];
	const seatedGroups = new Set(standing?.seated_groups ?? []);
	const found = data.periods.find((candidate) => candidate.key === period);

	const empty = (refusal: StandingPlan['refusal']): StandingPlan => ({
		rows: [],
		counts: { changed: 0, always: 0, never: 0 },
		period: found,
		order,
		category,
		groups,
		seatedGroups,
		refusal
	});

	if (!found) return empty('no-period');

	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	const counts: Record<Category, number> = { changed: 0, always: 0, never: 0 };
	const rows: StandingEntry[] = [];

	for (const row of standing.rows) {
		if (row.period !== period) continue;
		// A speaker with no speeches in this period has no composition to draw.
		// It is not withheld — there is nothing there — so it is not counted either.
		if (row.held <= 0) continue;
		const kind = categorise(row);
		counts[kind] += 1;
		if (category !== 'all' && kind !== category) continue;
		rows.push({
			speaker: speakers.get(row.country_org),
			row,
			category: kind,
			segments: segments(row, groups, seatedGroups)
		});
	}

	rows.sort(compare(order));
	return {
		rows,
		counts,
		period: found,
		order,
		category,
		groups,
		seatedGroups,
		refusal: rows.length ? null : 'none-in-category'
	};
}

/**
 * Descending by the chosen figure, then by name.
 *
 * The name breaks ties so the order is total: a table that reorders itself
 * between renders is a table a reader cannot cite.
 */
function compare(order: Ordering) {
	return (a: StandingEntry, b: StandingEntry) => {
		if (order === 'name') return a.row.country_org.localeCompare(b.row.country_org);
		const left = order === 'held' ? a.row.held : (a.row.seated_share ?? 0);
		const right = order === 'held' ? b.row.held : (b.row.seated_share ?? 0);
		if (left !== right) return right - left;
		return a.row.country_org.localeCompare(b.row.country_org);
	};
}

/**
 * The clearest single case of a speaker whose status changed.
 *
 * Returned rather than written into the prose, because a sentence naming Japan
 * would quietly become false the day the corpus or the membership config moves.
 * The pick is the changed speaker with the most speeches, which is also the one
 * whose composition carries the most evidence.
 */
export function exemplar(rows: StandingEntry[]): StandingEntry | null {
	const changed = rows.filter((entry) => entry.category === 'changed');
	if (!changed.length) return null;
	return changed.reduce((best, entry) => (entry.row.held > best.row.held ? entry : best));
}

export const EXPORT_COLUMNS = (groups: string[]) => [
	'country_org',
	'entity_type',
	'period',
	'speeches_held',
	'seated',
	'seated_share',
	'record',
	...groups.map((group) => `speeches_as_${group.toLowerCase().replace(/[^a-z0-9]+/g, '_')}`)
];

/**
 * Every speaker in every period, whatever the figure was showing.
 *
 * §7.5's first constraint: the file is the artefact, not the cut on screen. The
 * `record` column carries the category so a reader can recover the partition the
 * view offered without re-deriving it — and the five counts go in whole, because
 * a file with only `seated` would erase the distinction between a state that was
 * not on the Council, the Secretariat, and an invited speaker.
 */
export function exportRows(data: Countries): (string | number | boolean | null)[][] {
	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	return data.standing.rows.map((row) => [
		row.country_org,
		speakers.get(row.country_org)?.entity_type ?? null,
		row.period,
		row.held,
		row.seated,
		row.seated_share,
		row.held > 0 ? categorise(row) : null,
		...data.standing.groups.map((group) => row.groups[group] ?? 0)
	]);
}
