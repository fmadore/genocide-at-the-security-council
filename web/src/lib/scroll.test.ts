/**
 * What the back-to-top control decides, tested apart from how it is drawn.
 *
 * The cases below are the claims it makes about itself: that a short page never
 * offers it, that it appears higher than it withdraws, and that a viewport it
 * cannot measure is a reason to say nothing rather than to show itself.
 */

import { describe, expect, it } from 'vitest';
import { MINIMUM_PAGE, OFFER_AT, WITHDRAW_AT, offersTop } from './scroll';

const WINDOW = 800;

const at = (scrollY: number, documentHeight = WINDOW * 10) => ({
	scrollY,
	viewportHeight: WINDOW,
	documentHeight
});

describe('offersTop', () => {
	it('says nothing at the top of a long page', () => {
		expect(offersTop(at(0), false)).toBe(false);
	});

	it('appears once a reader is past OFFER_AT windows', () => {
		expect(offersTop(at(WINDOW * OFFER_AT - 1), false)).toBe(false);
		expect(offersTop(at(WINDOW * OFFER_AT + 1), false)).toBe(true);
	});

	it('withdraws lower than it appeared, so it cannot blink', () => {
		// Between the two thresholds the answer depends on which way the reader
		// came: already showing it stays, not yet showing it waits.
		const between = at(WINDOW * ((OFFER_AT + WITHDRAW_AT) / 2));
		expect(offersTop(between, true)).toBe(true);
		expect(offersTop(between, false)).toBe(false);
		expect(WITHDRAW_AT).toBeLessThan(OFFER_AT);
	});

	it('withdraws for good below WITHDRAW_AT', () => {
		expect(offersTop(at(WINDOW * WITHDRAW_AT - 1), true)).toBe(false);
	});

	it('is never offered on a page barely longer than the window', () => {
		const short = WINDOW * (MINIMUM_PAGE - 0.5);
		// Far enough down to clear the scroll threshold, on a page too short to
		// have earned a control: the masthead is a flick away.
		expect(offersTop(at(WINDOW * 2, short), false)).toBe(false);
		expect(offersTop(at(WINDOW * 2, short), true)).toBe(false);
	});

	it('refuses a viewport it cannot measure', () => {
		// Server-side render, or a hidden document: no height means no judgement,
		// and a control that shows itself by default would show itself there.
		expect(offersTop({ scrollY: 5000, viewportHeight: 0, documentHeight: 0 }, false)).toBe(false);
	});
});
