import { describe, expect, it } from 'vitest';
import { matrixCells, orderTerms } from './matrix';

const terms = [
	{ name: 'impunity', register: 'accountability', speeches: 900 },
	{ name: 'genocide', register: 'core', speeches: 3000 },
	{ name: 'war_crimes', register: 'legal', speeches: 2000 },
	{ name: 'atrocity', register: 'legal', speeches: 2500 },
	{ name: 'denial', register: 'contentious', speeches: 400 }
];
const registers = [
	'core',
	'legal',
	'preventive',
	'commemorative',
	'contentious',
	'accountability',
	'descriptive'
];

describe('the order of the matrix', () => {
	it('seriates by register, then by speeches, so the register blocks sit on the diagonal', () => {
		expect(orderTerms(terms, registers).map((t) => t.name)).toEqual([
			'genocide',
			'atrocity',
			'war_crimes',
			'denial',
			'impunity'
		]);
	});

	it('puts an unlisted register last rather than dropping it', () => {
		const ordered = orderTerms([...terms, { name: 'x', register: 'odd', speeches: 1 }], registers);
		expect(ordered.at(-1)?.name).toBe('x');
	});
});

describe('the cells', () => {
	const edges = [
		{ source: 'genocide', target: 'war_crimes', speeches: 800, pmi: 1.2, npmi: 0.3 },
		{ source: 'atrocity', target: 'impunity', speeches: 30, pmi: -0.4, npmi: -0.05 }
	];
	const suppressed = [{ source: 'genocide', target: 'denial', reason: 'pattern' }];
	const cells = matrixCells(orderTerms(terms, registers), edges, suppressed);
	const at = (row: string, col: string) => cells.find((c) => c.row === row && c.col === col)!;

	it('draws an edge in both triangles with the same numbers', () => {
		expect(at('genocide', 'war_crimes')).toMatchObject({
			state: 'drawn',
			npmi: 0.3,
			speeches: 800
		});
		expect(at('war_crimes', 'genocide')).toMatchObject({
			state: 'drawn',
			npmi: 0.3,
			speeches: 800
		});
	});

	it('tells a negative association from a missing one', () => {
		expect(at('atrocity', 'impunity').state).toBe('negative');
		expect(at('atrocity', 'denial').state).toBe('below');
	});

	it('marks a definitional pair with its reason and never as a finding', () => {
		expect(at('denial', 'genocide')).toMatchObject({ state: 'definitional', reason: 'pattern' });
	});

	it('carries the speech count on the diagonal', () => {
		expect(at('genocide', 'genocide')).toMatchObject({ state: 'self', speeches: 3000 });
		expect(cells).toHaveLength(25);
	});
});
