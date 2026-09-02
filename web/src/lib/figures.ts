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
