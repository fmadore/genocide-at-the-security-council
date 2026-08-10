/**
 * When a page has lost its top, and how to give it back.
 *
 * The decision is here rather than in the component for the reason `docs/PLAN.md`
 * §7 gives: what a visual works out at render time is tested, and logic reachable
 * only by mounting a component is logic nobody will test twice.
 *
 * Two rules, and both are about not becoming furniture. A page barely longer
 * than the window does not need a control — the reader is one flick from the
 * masthead, which is sticky anyway — so nothing is offered until the document is
 * `MINIMUM_PAGE` windows tall. And the offer appears and withdraws at different
 * heights, because a single threshold makes the control blink on and off while a
 * reader scrolls across it.
 */

/** Windows of scroll before the control appears. */
export const OFFER_AT = 1.5;

/** Windows of scroll below which it withdraws again. Lower than `OFFER_AT`. */
export const WITHDRAW_AT = 0.75;

/** Windows of document below which the control is never offered at all. */
export const MINIMUM_PAGE = 2.5;

export interface Position {
	/** `window.scrollY`. */
	scrollY: number;
	/** `window.innerHeight`. Never zero in a browser; guarded here for tests. */
	viewportHeight: number;
	/** `document.documentElement.scrollHeight`. */
	documentHeight: number;
}

/**
 * Should the control be on screen?
 *
 * `showing` is the current state, and it is a parameter rather than something
 * this module remembers: the hysteresis is the whole point, and a pure function
 * of the position alone cannot express it.
 */
export function offersTop(position: Position, showing: boolean): boolean {
	const { scrollY, viewportHeight, documentHeight } = position;
	if (!(viewportHeight > 0)) return false;
	if (documentHeight < viewportHeight * MINIMUM_PAGE) return false;
	const threshold = showing ? WITHDRAW_AT : OFFER_AT;
	return scrollY > viewportHeight * threshold;
}
