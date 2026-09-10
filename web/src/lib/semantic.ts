import type { BaseMeta } from './types';
import { provenanceOf, type ExportRequest } from './export';
export type Point = [string, number, number, number, number, number, boolean];
export interface SemanticMap {
	meta: BaseMeta & {
		schema: number;
		model_repo: string;
		model_revision: string;
		speeches: number;
		neighbour_shards: number;
		evaluation: { neighbours_lost_share: number; ann_recall_at_10: number; points: number };
	};
	countries: string[];
	agendas: string[];
	points: Point[];
}
export function validateMap(value: unknown): SemanticMap {
	const data = value as SemanticMap;
	if (
		!data ||
		data.meta?.schema !== 1 ||
		!Array.isArray(data.points) ||
		!Array.isArray(data.countries) ||
		!Array.isArray(data.agendas) ||
		![...data.countries, ...data.agendas].every((x) => typeof x === 'string') ||
		data.meta.speeches !== data.points.length ||
		data.meta.neighbour_shards !== 256 ||
		typeof data.meta.model_repo !== 'string' ||
		!/^[a-f0-9]{40}$/.test(data.meta.model_revision) ||
		!Number.isFinite(data.meta.evaluation?.neighbours_lost_share) ||
		data.meta.evaluation.neighbours_lost_share < 0 ||
		data.meta.evaluation.neighbours_lost_share > 1 ||
		!Number.isFinite(data.meta.evaluation.ann_recall_at_10) ||
		data.meta.evaluation.ann_recall_at_10 < 0.8 ||
		data.meta.evaluation.ann_recall_at_10 > 1
	)
		throw new Error('The semantic map failed its data checks.');
	const ids = new Set<string>();
	for (const row of data.points) {
		if (
			!Array.isArray(row) ||
			row.length !== 7 ||
			typeof row[0] !== 'string' ||
			!/^SC\d+-\d+-\d+$/.test(row[0]) ||
			ids.has(row[0]) ||
			!row.slice(1, 4).every(Number.isFinite) ||
			!Number.isInteger(row[3]) ||
			!Number.isInteger(row[4]) ||
			row[4] < 0 ||
			row[4] >= data.countries.length ||
			!Number.isInteger(row[5]) ||
			row[5] < 0 ||
			row[5] >= data.agendas.length ||
			typeof row[6] !== 'boolean'
		)
			throw new Error('Invalid speech coordinates or metadata.');
		ids.add(row[0]);
	}
	return data;
}
export function validateNeighbours(
	value: unknown,
	selected: string,
	known: Set<string>
): [string, number][] {
	const rows = (value as Record<string, unknown>)?.[selected];
	if (!Array.isArray(rows) || rows.length > 10)
		throw new Error('Related speeches are unavailable.');
	const seen = new Set([selected]);
	let previous = Infinity;
	for (const row of rows) {
		if (
			!Array.isArray(row) ||
			row.length !== 2 ||
			!known.has(row[0]) ||
			seen.has(row[0]) ||
			!Number.isFinite(row[1]) ||
			row[1] < -1 ||
			row[1] > 1 ||
			row[1] > previous
		)
			throw new Error('Invalid related-speech ranking.');
		seen.add(row[0]);
		previous = row[1];
	}
	return rows as [string, number][];
}

export function semanticExport(data: SemanticMap, rows: Point[], filters: string[]): ExportRequest {
	return {
		title: 'Semantic speech map',
		columns: [
			'speech_id',
			'umap_x',
			'umap_y',
			'year',
			'affiliation',
			'agenda',
			'mentions_genocide'
		],
		rows: rows.map((p) => [p[0], p[1], p[2], p[3], data.countries[p[4]], data.agendas[p[5]], p[6]]),
		provenance: provenanceOf(data.meta, 'semantic/map.json'),
		filters: [
			...filters,
			`model: ${data.meta.model_repo}@${data.meta.model_revision}`,
			'UMAP axes have no substantive units; distance is not diplomatic agreement'
		],
		scope:
			'all speeches matching the filters, across every table page; coordinates retain published precision'
	};
}
