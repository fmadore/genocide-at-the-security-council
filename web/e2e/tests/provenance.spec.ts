import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

test('provenance follows the model filter and survives print', async ({ page }) => {
	await page.goto(`${base}/concordance/`);
	const mark = page.locator('figure .provenance');
	await expect(mark).toHaveAttribute('data-provenance', 'computed');
	const referent = page.getByRole('combobox', { name: /^Referent/ });
	await expect(referent).toBeEnabled();
	const value = await referent.locator('option').nth(1).getAttribute('value');
	await referent.selectOption(value!);
	await expect(mark).toHaveAttribute('data-provenance', 'mixed');
	await page.emulateMedia({ media: 'print' });
	await expect(mark).toBeVisible();
	await page.emulateMedia({ media: 'screen' });
	await referent.selectOption('');
	await expect(mark).toHaveAttribute('data-provenance', 'computed');
	await expect(
		page
			.getByRole('navigation', { name: 'Sections' })
			.getByRole('link', { name: 'Usage', exact: true })
	).toHaveAttribute('title', /Model-derived/);
});
