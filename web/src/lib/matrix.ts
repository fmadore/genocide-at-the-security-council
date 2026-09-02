/**
 * The adjacency matrix that replaced the force-directed network (review of
 * 1 September 2026, §5.2). A force layout of 22 nodes has positions that
 * mean nothing and differ between two loads of the page, which is the
 * objection the cloud's own caveat raised about clouds. A matrix ordered by
 * register has one position per pair, the same on every load, and a cell
 * can say why it is empty. The decisions live here so they can be tested.
 */
import type { Edge, Network } from './types';

export interface MatrixTerm {
	name: string;
	register: string;
	speeches: number;
}

/**
 * Terms in register order, then by speeches within a register, so the blocks
 * a reader expects — the legal terms together, the accountability terms
 * together — appear along the diagonal without a layout algorithm deciding.
 */
export function orderTerms(
	terms: readonly MatrixTerm[],
	registers: readonly string[]
): MatrixTerm[] {
	const rank = new Map(registers.map((register, index) => [register, index]));
	return [...terms].sort((a, b) => {
		const byRegister = (rank.get(a.register) ?? 99) - (rank.get(b.register) ?? 99);
		if (byRegister !== 0) return byRegister;
		if (b.speeches !== a.speeches) return b.speeches - a.speeches;
		return a.name.localeCompare(b.name);
	});
}

export type CellState =
	/** The diagonal: the term itself, carrying its speech count. */
	| 'self'
	/** An edge: enough shared speeches, and nPMI at or above zero. */
	| 'drawn'
	/** An edge whose nPMI is negative: the two co-occur less than chance. */
	| 'negative'
	/** Fewer shared speeches than the artefact's minimum: nothing to say. */
	| 'below'
	/** Co-occurrence written into the lexicon; never a finding. */
	| 'definitional';

export interface MatrixCell {
	row: string;
	col: string;
	state: CellState;
	npmi: number | null;
	speeches: number | null;
	/** Why a definitional pair is not drawn, from the artefact. */
	reason: string | null;
}

const key = (a: string, b: string) => (a < b ? `${a} ${b}` : `${b} ${a}`);

/**
 * One cell per ordered pair, including both triangles: a symmetric matrix is
 * easier to read along a row than a triangle is, and the cost is 22 x 22
 * rectangles.
 */
export function matrixCells(
	terms: readonly MatrixTerm[],
	edges: readonly Edge[],
	suppressed: Network['suppressed_nested_edges']
): MatrixCell[] {
	const byPair = new Map(edges.map((edge) => [key(edge.source, edge.target), edge]));
	const definitional = new Map(
		(suppressed ?? []).map((pair) => [key(pair.source, pair.target), pair.reason ?? 'nested'])
	);
	const out: MatrixCell[] = [];
	for (const row of terms) {
		for (const col of terms) {
			if (row.name === col.name) {
				out.push({
					row: row.name,
					col: col.name,
					state: 'self',
					npmi: null,
					speeches: row.speeches,
					reason: null
				});
				continue;
			}
			const pair = key(row.name, col.name);
			const reason = definitional.get(pair);
			if (reason !== undefined) {
				out.push({
					row: row.name,
					col: col.name,
					state: 'definitional',
					npmi: null,
					speeches: null,
					reason
				});
				continue;
			}
			const edge = byPair.get(pair);
			if (!edge) {
				out.push({
					row: row.name,
					col: col.name,
					state: 'below',
					npmi: null,
					speeches: null,
					reason: null
				});
				continue;
			}
			out.push({
				row: row.name,
				col: col.name,
				state: edge.npmi >= 0 ? 'drawn' : 'negative',
				npmi: edge.npmi,
				speeches: edge.speeches,
				reason: null
			});
		}
	}
	return out;
}
