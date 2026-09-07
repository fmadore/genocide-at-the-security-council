import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

/**
 * R14, checked in a browser because neither claim survives a unit test. One is
 * about where a page has been scrolled to and what a Tab key reaches; the other
 * is about what a screen reader is handed in place of a drawing, which is the
 * exact place the prose beside the figure was not read.
 */

const contents = (page: import('@playwright/test').Page) =>
	page.getByRole('navigation', { name: 'Figures on this page' });

test('the rate figure names its base on the axis and in its own description', async ({ page }) => {
	await page.goto(`${base}/`);
	const figure = page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: /Occurrences and share of speeches/, level: 2 })
	});
	const chart = figure.locator('.chart');
	await expect(chart.locator('svg')).toBeVisible({ timeout: 15_000 });

	// The denominator is in the figure's own accessible description: 8 of the
	// fixture's 60 speeches. A reader who never reaches the prose still gets it.
	await expect(chart).toHaveAccessibleName(/8 of 60 speeches/);
	await expect(chart).toHaveAccessibleName(/share of all speeches held that year/);
	// And on the axis, where the eye is.
	await expect(chart.locator('svg')).toContainText('share of all speeches held that year');
});

test('the contents reaches the last figure by keyboard alone', async ({ page }) => {
	await page.goto(`${base}/`);
	const last = contents(page).getByRole('link').last();
	await expect(last).toHaveText(/The vocabulary, word by word/);

	// Tabbed to, not focused programmatically: the claim is that the band is in
	// the tab order and lets go of the focus again, and a cap on the loop is what
	// makes "not a keyboard trap" a failing test rather than a hung one.
	await page.locator('#top').focus();
	let reached = false;
	for (let step = 0; step < 40 && !reached; step += 1) {
		await page.keyboard.press('Tab');
		reached = await last.evaluate((node) => node === document.activeElement);
	}
	expect(reached).toBe(true);

	await page.keyboard.press('Enter');
	const figure = page.locator('figure.figure').last();
	await expect(figure).toBeFocused();
	await expect(figure).toBeInViewport();
	// The figure it skipped is off the top now, which is what "without scrolling
	// through the others" means.
	await expect(
		page.getByRole('heading', { name: /Occurrences and share of speeches/, level: 2 })
	).not.toBeInViewport();
});

test('the contents stays on screen and marks where the reader is', async ({ page }) => {
	await page.goto(`${base}/usage/`);
	const band = contents(page);
	const marked = band.locator('a[aria-current="location"]');

	await expect(marked).toHaveCount(0);
	await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

	await expect(band).toBeInViewport();
	await expect(marked).toHaveCount(1);
	await expect(marked).toHaveText('Who rejects the word');

	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
});
