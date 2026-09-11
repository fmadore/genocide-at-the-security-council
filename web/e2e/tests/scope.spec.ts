import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

/**
 * R9's corpus scope, checked in a browser rather than in a unit test, because
 * the two claims it has to keep are both about navigation: an old URL must mean
 * what it meant, and a new one must survive the page rewriting its own query.
 */

test('a URL carrying no scope renders the site the way it rendered before R9', async ({ page }) => {
	await page.goto(`${base}/concordance/`);

	const band = page.getByRole('region', { name: 'Reading set' });
	await expect(band.getByRole('radio', { name: /The word/ })).toBeChecked();
	await expect(band).toContainText('120');
	await expect(page.locator('.status')).toContainText('4 of 4 lines');
	await expect(page).toHaveURL(/\/concordance\/$/);
});

test('choosing a reading set is carried in the URL and drawn by the page', async ({ page }) => {
	await page.goto(`${base}/concordance/`);

	await page.getByRole('radio', { name: /The debate/ }).check();
	await expect(page).toHaveURL(/\?scope=debate$/);

	const set = page.locator('section.reading-set');
	await expect(set.getByRole('heading', { level: 2 })).toHaveText('The reading set: the debate');
	await expect(page.getByRole('region', { name: 'Reading set' })).toContainText('400');
	// Rwanda holds 200 of the debate set and 90 of the word set, so the chip's
	// count is evidence that the population moved rather than only the label.
	await expect(set.getByRole('button', { name: /Rwanda/ })).toContainText('200');
});

test('a scoped delegation shortcut filters the lines it names', async ({ page }) => {
	await page.goto(`${base}/concordance/?scope=debate`);
	await expect(page.locator('.status')).toContainText('4 of 4 lines');

	await page
		.locator('section.reading-set')
		.getByRole('button', { name: /Rwanda/ })
		.click();
	await expect(page.getByRole('combobox', { name: 'Speaker', exact: true })).toHaveValue('Rwanda');
	// The page rewrites its own query from its own controls; the scope must
	// still be in it afterwards.
	await expect(page).toHaveURL(/country=Rwanda/);
	await expect(page).toHaveURL(/scope=debate/);
});

test('the actors table ranks the reading set against each delegation’s own record', async ({
	page
}) => {
	await page.goto(`${base}/actors/?scope=vocabulary`);

	const figure = page.locator('section.table-wrap').first();
	const rwanda = figure.getByRole('row', { name: /Rwanda/ });
	// 120 of Rwanda's own 300 speeches, and the denominator is Rwanda's record —
	// not the reading set, which is the one thing a scope may never move.
	await expect(rwanda).toContainText('300');
	await expect(rwanda).toContainText('120');
	await expect(rwanda).toContainText('40.00%');

	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
});

test('the reader marks which speeches of a whole debate the reading set holds', async ({
	page
}) => {
	await page.goto(`${base}/reader/SC07000-01/?scope=word`);

	await expect(page.getByRole('heading', { name: 'Protection of civilians' })).toBeVisible();
	const apparatus = page.locator('aside.apparatus');
	await expect(apparatus).toContainText('1 of 1 speeches belong to the reading set');
	// The delegation roll, including what each one used: R9's reason for making
	// the meeting a unit at all.
	await expect(apparatus.locator('.roll')).toContainText('Rwanda');
	await expect(apparatus.locator('.roll')).toContainText('genocide');
});
