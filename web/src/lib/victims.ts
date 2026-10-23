/**
 * The decisions behind the three victim figures, kept out of the components.
 *
 * All three read `usage.victims`: the model's free-text `victim_group`, grouped
 * by `annotations/lexicon/victim_groups.csv`. Both layers are a model's or a
 * draft's reading — the label is the model's, and the table was drafted by
 * Claude and is checked row by row — so every figure says how many rows of the
 * table a person has checked, from `table`, rather than taking it on trust.
 *
 * Three decisions are made here:
 *
 * **Peoples and the groups that name none are kept apart.** "Civilians" and
 * "victims and survivors" are not peoples, and ranking them among the
 * Palestinians and the Tutsi would make a count of a way of speaking look like
 * a count of a population. They are listed after the peoples, under a rule.
 *
 * **The leaders are chosen over the whole run**, not per decade, so a row means
 * one group on the whole grid, and what the cap leaves out is said beneath it.
 *
 * **A decade's shares are withheld below the artefact's minimum**, as every
 * share on this page is: the counts are given at every denominator, a share
 * only where it can carry a reading.
 */

import type { Usage, UsageVictims } from './types';

/** The four kinds an eligible occurrence falls in, in the order they are stacked. */
export const KINDS = ['people', 'unspecified', 'ungrouped', 'none'] as const;
export type VictimKind = (typeof KINDS)[number];

export const KIND_LABELS: Record<VictimKind, string> = {
	people: 'Names a people',
	unspecified: 'Names no particular people',
	ungrouped: 'Label not yet grouped',
	none: 'Names no victim'
};

export interface GridRow {
	key: string;
	label: string;
	/** True for the groups that name no particular people, drawn under a rule. */
	unspecified: boolean;
	total: number;
	/** One count per column, zeros included. */
	cells: number[];
}

export interface GridPlan {
	columns: { key: string; label: string }[];
	rows: GridRow[];
	/** Index of the first unspecified row, or -1 when there is none. */
	ruleAt: number;
	/** The largest cell drawn: the top of the ramp. */
	high: number;
	/** What the cap left out: rows, and the occurrences in them. */
	hidden: { rows: number; occurrences: number };
	refusal: 'no-victims' | null;
}

const decadeLabel = (decade: number) => `${decade}s`;

function grid(
	columns: { key: string; label: string }[],
	rows: GridRow[],
	hidden: GridPlan['hidden']
): GridPlan {
	const ordered = [...rows.filter((r) => !r.unspecified), ...rows.filter((r) => r.unspecified)];
	const high = Math.max(0, ...ordered.flatMap((row) => row.cells));
	return {
		columns,
		rows: ordered,
		ruleAt: ordered.some((r) => r.unspecified) ? ordered.findIndex((r) => r.unspecified) : -1,
		high,
		hidden,
		refusal: ordered.length ? null : 'no-victims'
	};
}

/**
 * Who is named, decade by decade: the `leading` peoples over the whole run,
 * then every group that names no particular people.
 */
export function decadePlan(victims: UsageVictims, leading = 15): GridPlan {
	const columns = victims.decades.map((d) => ({
		key: String(d.decade),
		label: decadeLabel(d.decade)
	}));
	const peoples = victims.groups.filter((g) => !g.unspecified);
	const kept = [...peoples.slice(0, leading), ...victims.groups.filter((g) => g.unspecified)];
	const left = peoples.slice(leading);
	const rows = kept.map((group) => {
		const cells = columns.map(
			(column) =>
				victims.cells.find((c) => c.group === group.group && String(c.decade) === column.key)
					?.count ?? 0
		);
		return {
			key: group.group,
			label: group.group,
			unspecified: group.unspecified,
			total: group.count,
			cells
		};
	});
	return grid(columns, rows, {
		rows: left.length,
		occurrences: left.reduce((sum, g) => sum + g.count, 0)
	});
}

/**
 * Which delegations name which peoples: the `speakers` delegations that name a
 * people most often, across the `groups` peoples named most often. The groups
 * that name no particular people are left out here; the decade grid has them.
 */
export function actorPlan(
	victims: UsageVictims,
	name: (actor: string) => string,
	speakers = 20,
	groups = 10
): GridPlan {
	const peoples = victims.groups.filter((g) => !g.unspecified).slice(0, groups);
	const named = new Set(victims.groups.filter((g) => !g.unspecified).map((g) => g.group));
	const totals = new Map<string, number>();
	for (const cell of victims.by_actor) {
		if (named.has(cell.group)) totals.set(cell.actor, (totals.get(cell.actor) ?? 0) + cell.count);
	}
	// The name breaks every tie, so the order is total and the figure citable.
	const ranked = [...totals].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
	const columns = peoples.map((g) => ({ key: g.group, label: g.group }));
	const rows = ranked.slice(0, speakers).map(([actor, total]) => ({
		key: actor,
		label: name(actor),
		unspecified: false,
		total,
		cells: columns.map(
			(column) =>
				victims.by_actor.find((c) => c.actor === actor && c.group === column.key)?.count ?? 0
		)
	}));
	const left = ranked.slice(speakers);
	return grid(columns, rows, {
		rows: left.length,
		occurrences: left.reduce((sum, [, total]) => sum + total, 0)
	});
}

export interface NamingDecade {
	decade: number;
	label: string;
	eligible: number;
	counts: Record<VictimKind, number>;
	/** Each kind's share of `eligible`, or null below `minimum`. */
	shares: Record<VictimKind, number> | null;
}

/** Naming a people, or not: each decade's eligible occurrences by kind. */
export function namingPlan(victims: UsageVictims, minimum: number): NamingDecade[] {
	return victims.decades.map((d) => {
		const counts = Object.fromEntries(KINDS.map((k) => [k, d[k]])) as Record<VictimKind, number>;
		const shares =
			d.eligible >= minimum && d.eligible > 0
				? (Object.fromEntries(KINDS.map((k) => [k, d[k] / d.eligible])) as Record<
						VictimKind,
						number
					>)
				: null;
		return { decade: d.decade, label: decadeLabel(d.decade), eligible: d.eligible, counts, shares };
	});
}

/** The sentence every victim figure carries about the table it rests on. */
export function tableStatus(victims: UsageVictims): string {
	const { rows, checked } = victims.table;
	return checked === 0
		? `The ${rows.toLocaleString('en')} rows of the grouping table were drafted by AI and none has yet been checked by a person.`
		: `The grouping table was drafted by AI; ${checked.toLocaleString('en')} of its ${rows.toLocaleString('en')} rows have been checked by a person.`;
}

export const DECADE_COLUMNS = ['group', 'unspecified', 'decade', 'count'];
export const ACTOR_COLUMNS = ['group', 'unspecified', 'speaker', 'count'];
export const NAMING_COLUMNS = ['decade', 'eligible', ...KINDS];

const unspecified = (data: Usage) =>
	new Set(data.victims.groups.filter((g) => g.unspecified).map((g) => g.group));

/** Every (group, decade) count the artefact holds, not only the grid's leaders. */
export function decadeExportRows(data: Usage): (string | number | boolean)[][] {
	const loose = unspecified(data);
	return data.victims.cells.map((c) => [c.group, loose.has(c.group), c.decade, c.count]);
}

/** Every (group, speaker) count, including the groups and speakers the grid leaves out. */
export function actorExportRows(data: Usage): (string | number | boolean)[][] {
	const loose = unspecified(data);
	return data.victims.by_actor.map((c) => [c.group, loose.has(c.group), c.actor, c.count]);
}

export function namingExportRows(data: Usage): (string | number)[][] {
	return data.victims.decades.map((d) => [d.decade, d.eligible, ...KINDS.map((k) => d[k])]);
}
