/**
 * Figure identity: the `id` a figure is deep-linked by, derived from its
 * title so a page's contents list and the figure itself cannot disagree.
 */
export function slug(title: string): string {
	return title
		.toLowerCase()
		.replace(/&[a-z]+;/g, ' ')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '');
}

export interface FigureEntry {
	title: string;
	/** Defaults to `slug(title)`; a figure that sets its own `id` passes it here too. */
	id?: string;
}

export const figureId = (entry: FigureEntry): string => entry.id ?? slug(entry.title);

export type ProvenanceKind = 'computed' | 'mixed' | 'model';
export const PROVENANCE_LABELS: Record<ProvenanceKind, string> = {
	computed: 'Computed from the record',
	mixed: 'Computed and model-derived',
	model: 'Model-derived · experimental'
};

/** Only sources determine the mark; a caller cannot override it with a label. */
export function provenance(source: string): ProvenanceKind {
	const steps = [...source.matchAll(/\b(\d{2})_[a-z_]+\.py\b/g)].map((match) => Number(match[1]));
	if (!steps.length || steps.some((step) => step < 1 || step > 21)) {
		throw new Error(`Unclassified figure source: ${source}`);
	}
	const model = steps.some((step) => [6, 7, 14, 15, 16, 21].includes(step));
	const computed = steps.some((step) => ![6, 7, 14, 15, 16, 21].includes(step));
	return model ? (computed ? 'mixed' : 'model') : 'computed';
}
