/**
 * Words in context, the longest route on the site, with a journey of its own.
 *
 * Its five artefacts (four from 05, one from 17) are cut from a built payload
 * into `e2e/fixtures/data/lexical` and `frames`, keeping every key the pipeline
 * writes and shortening only the lists. Three of its figures are drawn as SVG
 * by components no other page uses — the frame profile, the dot plot and the
 * term matrix — so this is where they are rendered at all.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

const PLATES = [
	'What the word is doing',
	'The words that sit near a term',
	'The profile of a term',
	'The same word in two mouths',
	'Compared with a like-for-like speech',
	'Which terms travel together'
];

const plate = (page: import('@playwright/test').Page, title: string) =>
	page
		.locator('figure.figure')
		.filter({ has: page.getByRole('heading', { name: title, level: 2 }) });

/**
 * The SVG figures are drawn on the server, so seeing them says nothing about
 * whether the page has hydrated. A chart is drawn only in the browser: once
 * one is on screen, the controls answer.
 */
const hydrated = (page: import('@playwright/test').Page) =>
	expect(page.locator('.chart svg').first()).toBeVisible({ timeout: 15_000 });

test('words in context draws its plates from the artefacts', { tag: '@a11y' }, async ({ page }) => {
	const response = await page.goto(`${base}/language/`);
	expect(response?.status()).toBe(200);
	await expect(page.getByRole('heading', { name: 'Words in context', level: 1 })).toBeVisible();
	for (const title of PLATES) {
		await expect(page.getByRole('heading', { name: title, level: 2 })).toBeVisible();
	}

	// The three SVG figures only this route draws, each with marks in it.
	await expect(plate(page, 'What the word is doing').locator('svg circle').first()).toBeVisible();
	await expect(plate(page, 'The profile of a term').locator('svg circle').first()).toBeVisible();
	await expect(
		plate(page, 'Which terms travel together').locator('svg rect').first()
	).toBeVisible();

	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
});

test('a copied address restores the comparison and the matrix period', async ({ page }) => {
	await page.goto(`${base}/language/?align=word&comparison=unmatched&period=2020-2024`);
	await hydrated(page);
	await expect(page.getByRole('button', { name: 'By word' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	// The address is rewritten from the controls, and keeps what it was given.
	await expect(page).toHaveURL(/align=word/);
	await expect(page).toHaveURL(/comparison=unmatched/);
	await expect(page).toHaveURL(/period=2020-2024/);
	// A control moved back to its default leaves the address.
	await page.getByRole('button', { name: 'By rank' }).click();
	await expect(page).not.toHaveURL(/align=/);
	await expect(page).toHaveURL(/comparison=unmatched/);
});

test('every table on the page leaves as a CSV with its provenance', async ({ page }) => {
	await page.goto(`${base}/language/`);
	await hydrated(page);
	const buttons = page.getByRole('button', { name: 'CSV', exact: true });
	const total = await buttons.count();
	expect(total).toBeGreaterThan(0);
	for (let index = 0; index < total; index++) {
		const pending = page.waitForEvent('download');
		await buttons.nth(index).click();
		const download = await pending;
		expect(download.suggestedFilename()).toMatch(/\.csv$/);
	}
	await expect(page.locator('.download .problem')).toHaveCount(0);
});
