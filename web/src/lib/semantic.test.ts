import { describe, expect, it } from 'vitest';
import { validateMap, validateNeighbours, semanticExport } from './semantic';
const data = () => ({
	meta: {
		script: '21_semantic_map.py',
		generated: '2026-09-10',
		schema: 1,
		model_repo: 'Qwen/test',
		model_revision: 'a'.repeat(40),
		speeches: 2,
		neighbour_shards: 256,
		evaluation: { neighbours_lost_share: 0.4, ann_recall_at_10: 0.9, points: 2 }
	},
	countries: ['A'],
	agendas: ['B'],
	points: [
		['SC00001-01-001', 0, 0, 2000, 0, 0, true],
		['SC00001-01-002', 1, 1, 2000, 0, 0, false]
	]
});
describe('semantic data boundary', () => {
	it('exports every selected row with readable metadata and model identity', () => {
		const map = validateMap(data());
		const exported = semanticExport(map, map.points, ['year: 2000']);
		expect(exported.rows).toHaveLength(2);
		expect(exported.rows[0].slice(4, 6)).toEqual(['A', 'B']);
		expect(exported.filters?.join(' ')).toContain('Qwen/test@');
		expect(exported.scope).toContain('every table page');
	});
	it('accepts aligned coordinates and metadata', () =>
		expect(validateMap(data()).points).toHaveLength(2));
	it('rejects duplicate IDs and invalid categories', () => {
		const bad = data();
		bad.points[1][0] = bad.points[0][0];
		expect(() => validateMap(bad)).toThrow();
		const categories = data();
		categories.points[0][4] = 2;
		expect(() => validateMap(categories)).toThrow();
	});
	it('rejects self, unknown and incorrectly ranked neighbours', () => {
		const known = new Set(['a', 'b', 'c']);
		expect(
			validateNeighbours(
				{
					a: [
						['b', 0.9],
						['c', 0.8]
					]
				},
				'a',
				known
			)
		).toHaveLength(2);
		for (const rows of [
			[['a', 1]],
			[['unknown', 0.8]],
			[
				['b', 0.7],
				['c', 0.8]
			]
		])
			expect(() => validateNeighbours({ a: rows }, 'a', known)).toThrow();
	});
});
