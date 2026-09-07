/**
 * Which figure a reader is in, given where the page has been scrolled to.
 *
 * Here rather than in the component, for the reason `docs/PLAN.md` §7 gives and
 * `scroll.ts` already follows: what a visual works out at render time is tested,
 * and logic reachable only by mounting a component is logic nobody will test
 * twice.
 *
 * Two rules, and both are about honesty. A reader still in the standfirst is in
 * no figure at all, so the contents marks nothing rather than pretending they
 * have started; and the bottom of the document belongs to the last figure
 * however short it is, because a final figure that never fills a window would
 * otherwise be the one entry the contents could never point at.
 */

export interface FigureTop {
	id: string;
	/** Distance from the top of the document to the figure's top edge. */
	top: number;
}

export interface Reading {
	scrollY: number;
	viewportHeight: number;
	documentHeight: number;
	/**
	 * How much of the top of the window is covered by whatever is stuck to it —
	 * the masthead and the contents band itself. A figure hidden under those is
	 * not being read, so the reading line sits at their lower edge.
	 */
	obstructed: number;
}

/**
 * Pixels of slack below the reading line.
 *
 * A jump to an anchor parks the figure's top edge on the line and no lower, so
 * without slack the contents answers with the figure the reader has just left —
 * which is the one thing a control for jumping between figures may not do.
 */
export const LANDING_SLACK = 4;

/**
 * The `id` of the figure being read, or `null` above the first of them.
 *
 * The list need not be in document order: the answer is the lowest figure whose
 * top has passed the reading line, which is an ordering the function works out
 * for itself rather than one the caller has to promise.
 */
export function currentFigure(figures: FigureTop[], view: Reading): string | null {
	if (!figures.length) return null;
	const { scrollY, viewportHeight, documentHeight, obstructed } = view;

	let last: FigureTop | null = null;
	let current: FigureTop | null = null;
	const line = scrollY + obstructed;
	for (const figure of figures) {
		if (!last || figure.top > last.top) last = figure;
		if (figure.top <= line + LANDING_SLACK && (!current || figure.top >= current.top))
			current = figure;
	}

	if (scrollY + viewportHeight >= documentHeight - 1) return last!.id;
	return current?.id ?? null;
}
