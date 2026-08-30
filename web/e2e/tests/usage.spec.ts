/**
 * The experimental layer, exercised through the real routes over tiny fixtures.
 *
 * What these journeys hold is the part of the view a unit test cannot: that the
 * marking is on the page before any figure is, that a cell is a control a
 * reader can actually reach, and that the label in it reads back to the
 * sentence and the speech it came from. The arithmetic beneath all of that —
 * which rows are drawn, what is withheld, where a key press goes — is pinned in
 * `src/lib/usage.test.ts` and is not re-asserted here.
 */

import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { base } from '../../playwright.config';

const usage = `${base}/usage/`;

async function expectNoAxeViolations(page: Page) {
	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
}

/**
 * Open the view and wait for the client to have taken it over.
 *
 * The page is server-rendered, so the matrix is on screen and inert for a
 * moment before hydration attaches its handlers, and a click inside that window
 * is simply lost. The gate is a behaviour rather than a timeout: a control the
 * URL cannot be read for is dropped on the first write the client makes, so the
 * unreadable `sort` disappearing is the client arriving — and asserting it here
 * is also the only place that rule is exercised in a browser.
 */
async function openUsage(page: Page) {
	await page.goto(`${usage}?sort=vibes`);
	await expect(page).toHaveURL(/\/usage\/$/);
}

/** The matrix figure, picked out by its own heading rather than by position. */
const matrixOf = (page: Page) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: 'Which genocide each delegation means', level: 2 })
	});

test('the page says whose reading this is before it draws anything', async ({ page }) => {
	await openUsage(page);
	await expect(
		page.getByRole('heading', { name: 'What the word was doing', level: 1 })
	).toBeVisible();

	// The standing apparatus block, above the first figure in the document.
	const experiment = page.locator('section.experiment');
	await expect(experiment).toContainText('Experimental — model-derived');
	await expect(experiment).toContainText('The human labels are the authority');
	await expect(experiment).toContainText('chatgpt-5.6-luna-2026-08-01');
	await expect(experiment).toContainText('sha256:0f1e2d3c4b5a…');
	await expect(experiment).toContainText('12 of 12 occurrences');
	// An untouched gold sample is reported as untouched, never as a zero score.
	await expect(experiment).toContainText('not started — 0 of 200 coded');

	const matrix = matrixOf(page);
	// Referents ranked by weight, with the meta referent moved past the cases
	// even though it ties the largest of them on count — and the abstention code
	// given no column at all, because an occurrence carrying it is not placed.
	await expect(matrix.locator('thead th button')).toHaveText([
		'Rwanda (1994)',
		'Bosnia and Srebrenica',
		'The Holocaust',
		'Genocide Convention and legal definition'
	]);
	const speakers = matrix.locator('th.who button');
	await expect(speakers).toHaveCount(3);
	await expect(speakers.nth(0)).toContainText('Rwanda');
	await expect(speakers.nth(2)).toContainText('European Union');

	// The cut and the empty column are stated rather than left to be noticed.
	await expect(matrix.locator('p.disclosure')).toContainText(
		'3 of 3 delegations with anything placed are drawn here'
	);
	await expect(matrix.locator('p.disclosure')).toContainText(
		'1 referent on the list is used by no delegation drawn here'
	);

	await expectNoAxeViolations(page);
});

test('a cell opens the occurrences behind it, and a way into the record', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);

	await matrix.getByRole('button', { name: /^Rwanda × Rwanda \(1994\): 2 occurrences/ }).click();
	await expect(page).toHaveURL(/\?actor=Rwanda&referent=rwanda_1994$/);

	const evidence = page.locator('section.evidence');
	await expect(
		page.getByRole('heading', { name: 'Rwanda on Rwanda (1994)', level: 2 })
	).toBeVisible();
	await expect(evidence.locator('ol.quotations li')).toHaveCount(2);
	await expect(evidence.locator('blockquote').first()).toHaveText(
		'We warned that genocide could occur.'
	);
	await expect(evidence.locator('.stance').first()).toHaveText('Hypothetical or conditional');
	await expect(evidence.locator('.stance').nth(1)).toHaveText('Rejects or denies');

	// The link carries the term, the speech and the exact occurrence, so the
	// reader opens on the span the label was read from.
	await expect(
		evidence.getByRole('link', { name: 'Read the whole speech' }).first()
	).toHaveAttribute(
		'href',
		`${base}/reader/UNSC_2014_SPV.7000?term=genocide&speech=UNSC_2014_SPV.7000_spch0001&occurrence=UNSC_2014_SPV.7000_spch0001%231`
	);
	// The concordance cannot name one line, so the link lands on the delegation
	// and the record it came from.
	await expect(evidence.getByRole('link', { name: 'See in concordance' }).first()).toHaveAttribute(
		'href',
		`${base}/concordance?term=genocide&country=Rwanda&spv=S%2FPV.7000`
	);

	await expectNoAxeViolations(page);
});

test('the unit toggle is written into the URL and hatches what it withholds', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);
	const eu = matrix.getByRole('button', { name: /^European Union × Rwanda \(1994\)/ });

	// A count is published at every denominator; the same cell as a share is not.
	await expect(eu).toHaveAttribute('data-state', 'drawn');

	await page.getByRole('button', { name: 'Share of its own' }).click();
	await expect(page).toHaveURL(/\?unit=share$/);
	await expect(eu).toHaveAttribute('data-state', 'withheld-share');
	await expect(eu).toHaveAttribute('aria-label', /share withheld — fewer than 3 eligible/);
	await expect(matrix.locator('.key')).toContainText('share withheld (1)');
});

test('a copied URL restores the same reading of the matrix', async ({ page }) => {
	await page.goto(`${usage}?actor=France&referent=bosnia_srebrenica&unit=share&sort=name`);

	await expect(page.getByRole('button', { name: 'Share of its own' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(page.getByRole('combobox', { name: 'Ordered by' })).toHaveValue('name');
	await expect(
		page.getByRole('heading', { name: 'France on Bosnia and Srebrenica', level: 2 })
	).toBeVisible();

	const evidence = page.locator('section.evidence');
	await expect(evidence.locator('ol.quotations li')).toHaveCount(2);
	await expect(evidence.locator('blockquote').first()).toHaveText(
		'The Council must call this genocide by its name.'
	);
	// The model's own span is narrower than the sentence, so it is shown as well.
	await expect(evidence.locator('ol.quotations li').first()).toContainText("Model's evidence span");
	await expect(evidence.locator('ol.quotations li').first()).toContainText(
		'“must call this genocide by its name”'
	);
	await expect(page).toHaveURL(
		/\/usage\/\?actor=France&referent=bosnia_srebrenica&unit=share&sort=name$/
	);
});

test('the whole matrix is one tab stop, and the arrow keys move inside it', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);

	const first = matrix.getByRole('button', { name: /^Rwanda × Rwanda \(1994\)/ });
	await first.focus();
	await page.keyboard.press('ArrowRight');

	const next = matrix.getByRole('button', {
		name: 'Rwanda × Bosnia and Srebrenica: no occurrence placed here.'
	});
	await expect(next).toBeFocused();
	// Every other cell is out of the tab order while one of them holds it.
	await expect(first).toHaveAttribute('tabindex', '-1');
	await expect(next).toHaveAttribute('tabindex', '0');

	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/referent=bosnia_srebrenica/);
	// A pairing the matrix counts and the quotation file has nothing for says so
	// rather than showing an empty list.
	await expect(page.locator('section.evidence')).toContainText(
		'No annotated occurrence in this build carries that pairing'
	);
});
