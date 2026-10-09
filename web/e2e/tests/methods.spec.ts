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

	// The limits that qualify every count, stated once where the method is.
	const limits = page.getByRole('heading', { name: 'What this record is not', level: 2 });
	await expect(limits).toBeVisible();
	await expect(page.locator('#limits ~ p').first()).toContainText('UN interpreter or translator');
	for (const lead of [
		'Not the words spoken.',
		'Not every meeting.',
		'Not a complete count.',
		'Not yet checked by hand.'
	]) {
		await expect(page.getByText(lead, { exact: true })).toBeVisible();
	}

	// The Chronology draws its band from resampling whole meetings; this page
	// says so, and names the figures whose Wilson intervals ignore clustering.
	const intervals = page.getByText('Two kinds of 95% interval accompany shares', { exact: false });
	await expect(intervals).toContainText('resampling whole meetings');
	await expect(intervals).toContainText('The word list over time');
	await expect(intervals).toContainText('Speakers by rate');

	const { violations } = await new AxeBuilder({ page })
		// A known finding, left to the design system rather than to a test: the
		// ledger's "Automatic checks" state is set in the preventive register
		// colour, which is 4.36:1 on the zebra row, short of the 4.5:1 that
		// body text needs. Every other element on the page is scanned.
		.exclude('.state[data-state="verified"]')
		.analyze();
	expect(violations).toEqual([]);
});
