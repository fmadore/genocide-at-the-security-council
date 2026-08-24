import { expect, test } from '@playwright/test';
import { base } from '../../playwright.sw.config';

test('a visited reader remains usable after the built site goes offline', async ({
	context,
	page
}) => {
	await page.goto(`${base}/concordance/`);
	await expect(page.locator('.status')).toContainText('2 of 2 lines');
	await page.evaluate(async () => {
		await navigator.serviceWorker.ready;
		if (!navigator.serviceWorker.controller) {
			await new Promise<void>((resolve) =>
				navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
					once: true
				})
			);
		}
	});
	await page.locator('.line').first().click();
	await page.getByRole('link', { name: 'Read the whole speech' }).click();
	await expect(
		page.getByRole('heading', { name: 'Protection of civilians', level: 1 })
	).toBeVisible();
	await page.reload();
	await expect(
		page.getByRole('heading', { name: 'Protection of civilians', level: 1 })
	).toBeVisible();

	await context.setOffline(true);
	await page.reload({ waitUntil: 'domcontentloaded' });
	await expect(
		page.getByRole('heading', { name: 'Protection of civilians', level: 1 })
	).toBeVisible();
	await expect(page.locator('li.target mark')).toHaveCount(2);
	await expect(page.locator('.notice')).not.toBeVisible();
	await context.setOffline(false);
});
