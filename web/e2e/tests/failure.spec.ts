/**
 * A page whose data does not arrive says which file and why.
 *
 * Every route loads its artefacts in `+page.ts`, and SvelteKit replaces the
 * message of an error it did not raise with "Internal Error". The sentences
 * `$lib/data` writes — no connection, not in this release, refused by the
 * boundary — are the ones a reader offline most needs on a page load, so the
 * hook in `hooks.client.ts` passes them through.
 *
 * Each failure is staged on a client-side navigation, because that is where the
 * browser fetches for itself: the first page of a visit arrives with its data
 * already in the document.
 */
import { expect, test, type Page } from '@playwright/test';
import { base } from '../../playwright.config';

async function openChronologyFrom(page: Page) {
	await page.goto(`${base}/concordance/`);
	await expect(page.locator('.status')).toContainText('4 of 4 lines');
	await page
		.getByRole('navigation', { name: 'Sections' })
		.getByRole('link', { name: /Chronology/ })
		.click();
}

test('a file the server refuses is named with its status', async ({ page }) => {
	await page.route('**/data/series/annual.json', (route) => route.fulfill({ status: 503 }));
	await openChronologyFrom(page);
	await expect(
		page.getByText('Could not load series/annual.json (HTTP 503).', { exact: false })
	).toBeVisible();
	await expect(page.getByText('Internal Error')).toHaveCount(0);
});

test('a file that cannot be reached says so, and how to recover', async ({ page }) => {
	await page.route('**/data/series/annual.json', (route) => route.abort('internetdisconnected'));
	await openChronologyFrom(page);
	await expect(
		page.getByText('Could not reach series/annual.json.', { exact: false })
	).toBeVisible();
	await expect(page.getByText('Reconnect and reload the page', { exact: false })).toBeVisible();
	await expect(page.getByText('Internal Error')).toHaveCount(0);
});

test('a file the boundary refuses carries the refusal to the page', async ({ page }) => {
	await page.route('**/data/series/annual.json', (route) =>
		route.fulfill({ json: { meta: { script: 'fixture', generated: 'fixture' }, periods: [] } })
	);
	await openChronologyFrom(page);
	await expect(
		page.getByText('series/annual.json is missing required field(s): corpus, terms.')
	).toBeVisible();
	await expect(page.getByText('Internal Error')).toHaveCount(0);
});

test('a decomposition that is present and refused is not drawn around', async ({ page }) => {
	// The one artefact the chronology may do without is the one most likely to
	// fail quietly: only its absence may become "no data", never a refusal.
	await page.route('**/data/series/decomposition.json', (route) =>
		route.fulfill({ json: { meta: { script: 'fixture', generated: 'fixture' }, term: 'genocide' } })
	);
	await openChronologyFrom(page);
	await expect(
		page.getByText('series/decomposition.json is missing required field(s): splits.')
	).toBeVisible();
});
