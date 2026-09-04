/**
 * The basket, as a reader actually uses it: add, annotate, leave, come back.
 *
 * The persistence assertion is what unit tests cannot make. `basket.ts` is
 * pure and its storage round trip is tested there against strings; only a
 * browser can say whether a note written before a reload is there afterwards,
 * which is the single promise this feature makes.
 */

import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { base } from '../../playwright.config';

const concordance = `${base}/concordance/`;

/** Open the first concordance line's detail panel. */
async function openFirstLine(page: import('@playwright/test').Page) {
	await page.goto(concordance);
	await page.locator('.line').first().click();
}

test('an occurrence survives a reload, with the note written on it', async ({ page }) => {
	await openFirstLine(page);
	await page.getByRole('button', { name: 'Add to basket' }).first().click();

	// The masthead count is the feature's only ambient signal.
	const open = page.getByRole('button', { name: /^Basket/ });
	await expect(open).toContainText('1');

	await open.click();
	const drawer = page.getByRole('dialog');
	await expect(drawer.getByRole('heading', { name: /Basket/ })).toBeVisible();
	await expect(drawer).toContainText('We warned that genocide could occur.');
	await expect(drawer).toContainText('S/PV.7000');
	// It must say what it is: one browser, no account, no sync.
	await expect(drawer).toContainText('Kept in this browser only');

	await drawer.getByRole('textbox').fill('Denial, not warning.');
	await drawer.getByRole('textbox').blur();

	await page.reload();
	// The count coming back is the visible signal that storage has been read;
	// waiting for it is both the persistence assertion and the right moment to
	// open the drawer, since the masthead reads an empty basket until then.
	await expect(page.getByRole('button', { name: /^Basket/ })).toContainText('1');
	await page.getByRole('button', { name: /^Basket/ }).click();
	const reopened = page.getByRole('dialog');
	await expect(reopened.getByRole('textbox')).toHaveValue('Denial, not warning.');
	await expect(reopened).toContainText('We warned that genocide could occur.');
});

test('adding the same occurrence twice is refused, not silently ignored', async ({ page }) => {
	await openFirstLine(page);
	await page.getByRole('button', { name: 'Add to basket' }).first().click();

	// The control itself is the disclosure: it says the item is already held.
	const added = page.getByRole('button', { name: 'In the basket' }).first();
	await expect(added).toBeVisible();
	await expect(added).toBeDisabled();
	await expect(page.getByRole('button', { name: /^Basket/ })).toContainText('1');
});

test('the exports carry per-row provenance and read back as what was saved', async ({ page }) => {
	await openFirstLine(page);
	await page.getByRole('button', { name: 'Add to basket' }).first().click();
	await page.getByRole('button', { name: /^Basket/ }).click();
	const drawer = page.getByRole('dialog');
	await drawer.getByRole('textbox').fill('Kept for the paper.');
	await drawer.getByRole('textbox').blur();

	const csvPending = page.waitForEvent('download');
	await drawer.getByRole('button', { name: 'CSV' }).click();
	const csv = await readFile((await (await csvPending).path())!, 'utf8');
	expect(csv).toContain('# Genocide at the Security Council');
	expect(csv).toContain('# licence: CC BY 4.0');
	expect(csv).toContain('each row carries the lexicon version and analytical hash');
	expect(csv).toContain('lexicon_version');
	expect(csv).toContain('SC07000-01-001#1');
	expect(csv).toContain('Kept for the paper.');

	const jsonPending = page.waitForEvent('download');
	await drawer.getByRole('button', { name: 'JSON' }).click();
	const json = JSON.parse(await readFile((await (await jsonPending).path())!, 'utf8'));
	expect(json.version).toBe(1);
	expect(json.licence).toBe('CC BY 4.0');
	expect(json.items).toHaveLength(1);
	expect(json.items[0].id).toBe('SC07000-01-001#1');
	expect(json.items[0].note).toBe('Kept for the paper.');

	const mdPending = page.waitForEvent('download');
	await drawer.getByRole('button', { name: 'Markdown' }).click();
	const markdown = await readFile((await (await mdPending).path())!, 'utf8');
	expect(markdown).toContain('> We warned that genocide could occur.');
	expect(markdown).toContain('**Note.** Kept for the paper.');
});

test('emptying the basket asks first, and the empty state explains itself', async ({ page }) => {
	await openFirstLine(page);
	await page.getByRole('button', { name: 'Add to basket' }).first().click();
	await page.getByRole('button', { name: /^Basket/ }).click();
	const drawer = page.getByRole('dialog');

	await drawer.getByRole('button', { name: 'Empty the basket' }).click();
	await expect(drawer).toContainText('nothing here is recoverable');
	await drawer.getByRole('button', { name: 'Keep it' }).click();
	await expect(drawer).toContainText('We warned that genocide could occur.');

	await drawer.getByRole('button', { name: 'Empty the basket' }).click();
	await drawer.getByRole('button', { name: 'Empty it' }).click();
	await expect(drawer).toContainText('Nothing here yet');
	await expect(page.getByRole('button', { name: /^Basket/ })).not.toContainText('1');

	await expectNoAxeViolations(page);
});

/**
 * The rule that protects a reader's work: a basket written by a version this
 * build does not understand is reported and left alone, never overwritten.
 */
test('a basket from another version is refused without being destroyed', async ({ page }) => {
	await page.goto(concordance);
	const foreign = '{"version":99,"items":[{"kind":"occurrence","id":"kept#1"}]}';
	await page.evaluate((value) => localStorage.setItem('unsc-genocide:basket', value), foreign);
	await page.reload();

	// A refused basket leaves the count at zero, so wait for the page to be
	// interactive rather than for a number that will never change.
	await expect(page.locator('.line').first()).toBeVisible();
	await page.getByRole('button', { name: /^Basket/ }).click();
	const drawer = page.getByRole('dialog');
	await expect(drawer.getByRole('alert')).toContainText('99');
	await expect(drawer.getByRole('alert')).toContainText('untouched');

	// Adding is blocked while the foreign value stands, so nothing overwrites it.
	await expect(await page.evaluate(() => localStorage.getItem('unsc-genocide:basket'))).toBe(
		foreign
	);

	// Only an explicit choice replaces it.
	await drawer.getByRole('button', { name: 'Start a new basket' }).click();
	await expect(drawer).toContainText('Nothing here yet');
	expect(await page.evaluate(() => localStorage.getItem('unsc-genocide:basket'))).not.toBe(foreign);
});

async function expectNoAxeViolations(page: import('@playwright/test').Page) {
	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
}
