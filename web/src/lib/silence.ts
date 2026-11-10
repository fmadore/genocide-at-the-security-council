/**
 * The decisions behind "Who stays silent when others say it", kept out of the
 * component.
 *
 * Silence means something only where the word was available. A delegation that
 * never says *genocide* in a debate about fisheries has avoided nothing; one that
 * takes the floor just after another delegation used the word, and does not use
 * it, has made a choice the record can show. So the denominator here is a
 * speaker's **exposed meetings**, which `11_countries.py` counts, and the share
 * is the part of them in which the speaker joined in.
 *
 * Two decisions are the artefact's and are honoured rather than re-derived:
 *
 * **Shares below the minimum are withheld, not drawn small.** The rows that fall
 * short are counted and named in the caveat; they are never ranked.
 *
 * **A whole-corpus row is not a sum of the period rows.** `plan()` works within
 * one period and says which.
 */

import type { Countries, CountryPeriod, SilencePeriod, SilenceRow, Speaker } from './types';

/**
 * A row on the ordered reading, in the shape of the unordered one.
 *
 * "Exposed" used to mean only that someone else used the word somewhere in the
 * meeting. A delegation that spoke third, before the tenth speaker said it,
 * had nothing to join while it held the floor, and it was counted as staying
 * silent all the same: 10,456 of 30,752 exposed attendances. Where the artefact
 * carries the ordered counts — meetings in which the speaker took the floor
 * after another's first use — the figure reads those, because they are what
 * its own sentence describes. The unordered counts stay in the download. A
 * payload written before the artefact carried them is drawn as it always was,
 * and `plan().ordered` says which the reader is looking at.
 */
export function ordered(row: SilenceRow): SilenceRow {
	if (row.exposed_after === undefined || row.joined_after === undefined) return row;
	return {
		...row,
		exposed: row.exposed_after,
		joined: row.joined_after,
		share: row.share_after ?? null,
		share_low: row.share_after_low ?? null,
		share_high: row.share_after_high ?? null,
		sufficient: row.sufficient_after ?? false
	};
}

/** A period's totals on the ordered reading, likewise. */
export function orderedSummary(summary: SilencePeriod): SilencePeriod {
	if (summary.exposed_after === undefined || summary.joined_after === undefined) return summary;
	return {
		...summary,
		exposed: summary.exposed_after,
		joined: summary.joined_after,
		room_share: summary.room_share_after ?? null,
		speakers_at_minimum: summary.speakers_at_minimum_after ?? 0
	};
}

/** How the table is ordered. Quietest first is the question the figure asks. */
export type Ordering = 'quietest' | 'loudest' | 'exposed' | 'name';

export interface SilenceEntry {
	row: SilenceRow;
	speaker: Speaker | null;
}

export interface SilencePlan {
	period: CountryPeriod | null;
	summary: SilencePeriod | null;
	/** Speakers with a published share, in the chosen order. */
	rows: SilenceEntry[];
	/** Speakers exposed at least once whose share is withheld. */
	withheld: number;
	minimum: number;
	/** Whether the counts follow the order of speaking; false on an older payload. */
	ordered: boolean;
	refusal: 'unknown-period' | 'none-sufficient' | null;
}

const byName = (a: SilenceEntry, b: SilenceEntry) =>
	a.row.country_org.localeCompare(b.row.country_org);

const ORDERS: Record<Ordering, (a: SilenceEntry, b: SilenceEntry) => number> = {
	quietest: (a, b) => (a.row.share ?? 0) - (b.row.share ?? 0) || b.row.exposed - a.row.exposed,
	loudest: (a, b) => (b.row.share ?? 0) - (a.row.share ?? 0) || b.row.exposed - a.row.exposed,
	exposed: (a, b) => b.row.exposed - a.row.exposed || byName(a, b),
	name: byName
};

/**
 * The ranked rows for one period.
 *
 * `states` keeps delegations of states only, which is the default view: the UN
 * Secretariat, a tribunal or an NGO briefer is invited to report, and its not
 * using a word is a different fact from a government's. The withheld count is
 * taken within the same selection, so the caveat never counts speakers the
 * table could not have shown.
 */
export function plan({
	data,
	period,
	order,
	states = false
}: {
	data: Countries;
	period: string;
	order: Ordering;
	states?: boolean;
}): SilencePlan {
	const minimum = data.silence.minimum_meetings;
	const window = data.periods.find((candidate) => candidate.key === period) ?? null;
	const found = data.silence.periods.find((candidate) => candidate.period === period) ?? null;
	const summary = found ? orderedSummary(found) : null;
	const inOrder = data.silence.rows.some((row) => row.exposed_after !== undefined);
	if (!window) {
		return {
			period: null,
			summary,
			rows: [],
			withheld: 0,
			minimum,
			ordered: inOrder,
			refusal: 'unknown-period'
		};
	}
	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	const here = data.silence.rows
		.filter(
			(row) =>
				row.period === period && (!states || speakers.get(row.country_org)?.entity_type === 'state')
		)
		.map(ordered)
		// A speaker never exposed on the ordered reading has no share to withhold.
		.filter((row) => row.exposed > 0);
	const rows = here
		.filter((row) => row.sufficient && row.share !== null)
		.map((row) => ({ row, speaker: speakers.get(row.country_org) ?? null }))
		.sort(ORDERS[order]);
	return {
		period: window,
		summary,
		rows,
		withheld: here.length - rows.length,
		minimum,
		ordered: inOrder,
		refusal: rows.length ? null : 'none-sufficient'
	};
}

/** Every row of every period, withheld ones included with their nulls. */
export const EXPORT_COLUMNS = [
	'country_org',
	'period',
	'entity_type',
	'exposed_meetings',
	'joined_meetings',
	'share_joined',
	'share_joined_wilson95_low',
	'share_joined_wilson95_high',
	'sufficient',
	// The ordered reading the figure draws: only meetings in which the speaker
	// took the floor after another speaker's first use of the word.
	'exposed_after_first_use',
	'joined_after_first_use',
	'share_joined_after',
	'share_joined_after_wilson95_low',
	'share_joined_after_wilson95_high',
	'sufficient_after'
];

export function exportRows(data: Countries): (string | number | boolean | null)[][] {
	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	return data.silence.rows.map((row) => [
		row.country_org,
		row.period,
		speakers.get(row.country_org)?.entity_type ?? null,
		row.exposed,
		row.joined,
		row.share,
		row.share_low,
		row.share_high,
		row.sufficient,
		row.exposed_after ?? null,
		row.joined_after ?? null,
		row.share_after ?? null,
		row.share_after_low ?? null,
		row.share_after_high ?? null,
		row.sufficient_after ?? null
	]);
}

/**
 * The shared scale of an interval strip: one end for every row of a table.
 *
 * Both interval tables on the Actors page ("Who stays silent" and "Speakers by
 * rate") used to end their strip at the table's largest upper bound. One
 * outlier — a delegation with few meetings and a wide interval — set the scale
 * for all of them: at 0.756 against a median upper bound of 0.207, most
 * intervals occupied ten pixels and the room's average touched every bar
 * (review of 10 November 2026).
 *
 * So the end is the upper bound at the 90th percentile, rounded up to a figure
 * a reader can print (1, 1.5, 2, 2.5, 3, 4, 5, 6 or 8 of a power of ten), and never short of
 * `floor` — the room's average, or on a table ranked by its own estimate the
 * largest of them, so that every tick stays on the strip. It is one scale
 * for the whole table, printed in the column head, and a row reaching past it
 * is not shortened silently: `past` says whether to draw the overflow mark,
 * and `clipped` counts the rows that carry one.
 */
export interface StripScale {
	end: number;
	clipped: number;
}

const NICE = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];

/** The smallest printable step (see `NICE`) times a power of ten that is at least `value`. */
export function niceCeil(value: number): number {
	if (!(value > 0) || !Number.isFinite(value)) return 0;
	const power = 10 ** Math.floor(Math.log10(value));
	const step = NICE.find((n) => n * power >= value - 1e-12) ?? 10;
	return Number((step * power).toPrecision(12));
}

export function stripScale(
	uppers: (number | null | undefined)[],
	floor = 0,
	quantile = 0.9
): StripScale {
	const values = uppers
		.filter((v): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0)
		.sort((a, b) => a - b);
	const at = values.length ? values[Math.max(0, Math.ceil(quantile * values.length) - 1)]! : 0;
	const end = niceCeil(Math.max(at, floor)) || 1e-6;
	return { end, clipped: values.filter((v) => v > end).length };
}

/** A value's place on the strip, as a CSS percentage, held to the strip's end. */
export function stripAt(value: number, end: number): string {
	const share = end > 0 ? Math.min(Math.max(value / end, 0), 1) : 0;
	return `${(share * 100).toFixed(2)}%`;
}

/** The strip's end as the column head prints it: a percentage without trailing zeros. */
export function stripEnd(end: number): string {
	return `${Number((end * 100).toFixed(2))}%`;
}
