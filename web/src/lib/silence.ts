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
	const summary = data.silence.periods.find((candidate) => candidate.period === period) ?? null;
	if (!window) {
		return { period: null, summary, rows: [], withheld: 0, minimum, refusal: 'unknown-period' };
	}
	const speakers = new Map(data.countries.map((speaker) => [speaker.country_org, speaker]));
	const here = data.silence.rows.filter(
		(row) =>
			row.period === period && (!states || speakers.get(row.country_org)?.entity_type === 'state')
	);
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
	'sufficient'
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
		row.sufficient
	]);
}
