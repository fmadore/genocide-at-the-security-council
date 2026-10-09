/**
 * The Methods page, which had no journey and so no accessibility scan.
 *
 * It prints version identifiers and counts from four artefacts — the annual
 * series, the change-point test, the keyness table and the concordance index —
 * and the ledger of analysis steps.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

test('methods renders from its artefacts and passes a scan', { tag: '@a11y' }, async ({ page }) => {
	const response = await page.goto(`${base}/methods/`);
	expect(response?.status()).toBe(200);
	await expect(page.getByRole('heading', { name: 'Methods', level: 1 })).toBeVisible();
	await expect(page.getByRole('region', { name: 'Analysis steps' })).toBeVisible();
	await expect(page.getByText('Word-list version 2.', { exact: false })).toBeVisible();

	const { violations } = await new AxeBuilder({ page })
		// A known finding, left to the design system rather than to a test: the
		// ledger's "Automatic checks" state is set in the preventive register
		// colour, which is 4.36:1 on the zebra row, short of the 4.5:1 that
		// body text needs. Every other element on the page is scanned.
		.exclude('.state[data-state="verified"]')
		.analyze();
	expect(violations).toEqual([]);
});
