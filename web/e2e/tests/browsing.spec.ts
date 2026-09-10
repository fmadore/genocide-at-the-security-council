import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { base } from '../../playwright.config';

test('home onward navigation includes every main subpage', async ({ page }) => {
	await page.goto(`${base}/`);
	const onward = page.locator('.onward');
	for (const route of [
		'chronology',
		'language',
		'actors',
		'concordance',
		'usage',
		'semantic',
		'methods'
	]) {
		const link = onward.locator(`a[href$="/${route}"]`);
		await expect(link).toBeVisible();
		expect(
			await link.evaluate((element) => new URL((element as HTMLAnchorElement).href).pathname)
		).toBe(`${base}/${route}`);
	}
});

test('speaker search supports keyboard selection, cancellation and clearing', async ({ page }) => {
	await page.goto(`${base}/concordance/?scope=debate`);
	await expect(page.locator('.status')).toContainText('4 of 4 lines');
	const speaker = page.getByRole('combobox', { name: 'Speaker', exact: true });
	await speaker.fill('rwan');
	await expect(page.getByRole('option', { name: 'Rwanda', exact: true })).toBeVisible();
	await speaker.press('ArrowDown');
	await speaker.press('Enter');
	await expect(speaker).toHaveValue('Rwanda');
	await expect(page).toHaveURL(/country=Rwanda/);
	await expect(page).toHaveURL(/scope=debate/);
	await speaker.fill('no such speaker');
	await expect(page.getByRole('status').filter({ hasText: 'No matching options.' })).toBeVisible();
	await speaker.press('Escape');
	await expect(speaker).toHaveValue('Rwanda');
	await speaker.click();
	const all = page
		.getByRole('listbox', { name: 'Speaker', exact: true })
		.getByRole('option', { name: 'All', exact: true });
	await expect(all).toBeVisible();
	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
	await all.click();
	await expect(page).not.toHaveURL(/country=/);
	await expect(page.locator('.status')).toContainText('4 of 4 lines');
});

test('all profile speakers remain selectable beyond the first eight', async ({ page }) => {
	const fixture = JSON.parse(
		await readFile(new URL('../fixtures/data/kwic/genocide.json', import.meta.url), 'utf8')
	);
	fixture.lines = Array.from({ length: 30 }, (_, index) => ({
		...fixture.lines[0],
		id: `sample-${index}`,
		country: `Speaker ${String(index).padStart(2, '0')}`
	}));
	fixture.count = fixture.lines.length;
	await page.route('**/data/kwic/genocide.json', (route) => route.fulfill({ json: fixture }));
	await page.goto(`${base}/concordance/`);
	const picker = page.getByRole('combobox', { name: 'Browse all 30 speaker options' });
	await picker.fill('Speaker 29');
	await page.getByRole('option', { name: 'Speaker 29 (1 line)' }).click();
	await expect(page).toHaveURL(/country=Speaker\+29/);
	await expect(page.locator('.status')).toContainText('1 of 30 lines');
});

test('ranking pages, search and full CSV retain every speaker', async ({ page }) => {
	const fixture = JSON.parse(
		await readFile(new URL('../fixtures/data/countries/countries.json', import.meta.url), 'utf8')
	);
	const names = Array.from({ length: 25 }, (_, index) => `Actor ${String(index).padStart(2, '0')}`);
	fixture.countries = names.map((country_org) => ({ ...fixture.countries[0], country_org }));
	fixture.measures.genocide.rows = names.map((country_org, index) => ({
		...fixture.measures.genocide.rows[0],
		country_org,
		speech_rate: 0.5 - index / 100
	}));
	await page.route('**/data/countries/countries.json', (route) => route.fulfill({ json: fixture }));
	await page.goto(`${base}/`);
	await expect(page.locator('.chart svg').first()).toBeVisible();
	await page
		.locator('.onward')
		.getByRole('link', { name: /^Actors/ })
		.click();
	const table = page.locator('#speakers-by-rate table');
	await expect(table.locator('tbody tr')).toHaveCount(20);
	const pages = page.getByRole('navigation', { name: 'Speaker ranking pages' });
	await pages.getByRole('button', { name: 'Next' }).click();
	await expect(page).toHaveURL(/page=2/);
	await expect(table.locator('tbody tr')).toHaveCount(5);
	await expect(pages).toContainText('21–25 of 25');
	await pages.getByRole('button', { name: 'Previous' }).click();
	await expect(table.locator('tbody tr')).toHaveCount(20);
	await page.getByRole('searchbox', { name: 'Find a ranked speaker' }).fill('Actor 24');
	await expect(page).toHaveURL(/q=Actor\+24/);
	await expect(page).not.toHaveURL(/page=2/);
	await expect(table.locator('tbody tr')).toHaveCount(1);
	await expect(pages).toContainText('Page 1 of 1');
	await table.getByRole('button', { name: 'Actor 24' }).click();
	await expect(page.locator('aside.picked h2')).toHaveText('Actor 24');
	const pending = page.waitForEvent('download');
	await page.locator('#speakers-by-rate').getByRole('button', { name: 'CSV', exact: true }).click();
	const download = await pending;
	const csv = await readFile((await download.path())!, 'utf8');
	for (const name of names) expect(csv).toContain(name);
	await page.getByRole('searchbox', { name: 'Find a ranked speaker' }).fill('missing');
	await expect(pages).toContainText('0–0 of 0');
	await expect(page.getByText('No ranked speakers match this search.')).toBeVisible();
});

test('ranking search restores from a link and clamps an unavailable page', async ({ page }) => {
	await page.goto(`${base}/actors/?q=Rwanda&page=999&scope=debate`);
	await expect(page.getByRole('searchbox', { name: 'Find a ranked speaker' })).toHaveValue(
		'Rwanda'
	);
	await expect(page.locator('#speakers-by-rate tbody tr')).toHaveCount(1);
	await expect(page.getByRole('navigation', { name: 'Speaker ranking pages' })).toContainText(
		'Page 1 of 1'
	);
	await expect(page).not.toHaveURL(/page=999/);
	await expect(page).toHaveURL(/scope=debate/);
});
