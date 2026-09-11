import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { base } from '../../playwright.config';

test('semantic filters, pagination and original-vector neighbours work on mobile', async ({
	page
}) => {
	const points = Array.from({ length: 25 }, (_, i) => [
		`SC00001-01-${String(i + 1).padStart(3, '0')}`,
		i,
		Math.sin(i),
		2000,
		i % 2,
		0,
		true
	]);
	await page.route('**/data/semantic/map.json', (route) =>
		route.fulfill({
			json: {
				meta: {
					schema: 1,
					speeches: 25,
					neighbour_shards: 256,
					model_repo: 'Qwen/test',
					model_revision: 'a'.repeat(40),
					evaluation: { neighbours_lost_share: 0.5, ann_recall_at_10: 0.9, points: 25 }
				},
				countries: ['A', 'B'],
				agendas: ['Peacekeeping'],
				points
			}
		})
	);
	await page.route('**/data/semantic/neighbours/20.json', (route) =>
		route.fulfill({ json: { 'SC00001-01-021': [['SC00001-01-001', 0.9]] } })
	);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`${base}/semantic/?colour=agenda`);
	await expect(page.locator('tbody tr')).toHaveCount(20);
	await page.getByRole('button', { name: 'Next', exact: true }).click();
	await expect(page.locator('tbody tr')).toHaveCount(5);
	const downloading = page.waitForEvent('download');
	await page.getByRole('button', { name: 'CSV', exact: true }).click();
	const csv = await readFile((await (await downloading).path())!, 'utf8');
	for (const point of points) expect(csv).toContain(String(point[0]));
	expect(csv).toContain('Qwen/test@');
	await page.getByRole('button', { name: 'SC00001-01-021', exact: true }).click();
	const selected = page.getByRole('complementary', { name: 'Selected speech' });
	await expect(selected.getByRole('link', { name: /A · 2000/ })).toHaveAttribute(
		'href',
		/reader\/SC00001-01\?speech=SC00001-01-001/
	);
	const picker = page.getByRole('combobox', { name: 'Affiliation', exact: true });
	await picker.fill('B');
	await page.getByRole('option', { name: 'B', exact: true }).click();
	await expect(page.locator('tbody tr')).toHaveCount(12);
	await expect(selected).toContainText('outside the current filters');
	await expect(page.locator('.legend')).toContainText('Peacekeeping (12)');
	await expect(page.locator('.legend')).not.toContainText('Other');
	await expect(page).toHaveURL(/country=B/);
	await page.reload();
	await expect(page.locator('tbody tr')).toHaveCount(12);
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
		true
	);
	expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
	await page.locator('#semantic-map').scrollIntoViewIfNeeded();
	await page.screenshot({ path: 'test-results/semantic-mobile.png' });
	await page.setViewportSize({ width: 1440, height: 1000 });
	await page.screenshot({ path: 'test-results/semantic-desktop.png' });
});

test('semantic waiting state displays no invented points', async ({ page }) => {
	await page.route('**/data/semantic/map.json', (route) =>
		route.fulfill({ json: { status: 'pending', schema: 1 } })
	);
	await page.goto(`${base}/semantic/`);
	await expect(page.getByRole('status')).toContainText('not available in this release');
	await expect(page.locator('canvas')).toHaveCount(0);
});
