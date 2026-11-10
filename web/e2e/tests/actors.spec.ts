/**
 * Two figures of the actors page that no browser test had drawn.
 *
 * *What a delegation says that the room does not* had a fixture with no
 * speakers, so its table, its bars and the conservative estimate they are
 * drawn from (review of 9 November 2026, A5) were never rendered. The fixture
 * now holds one sufficient speaker, Rwanda, with three matched keywords ranked
 * by `lrc`, one of them its own name, and the stability rows the brackets read.
 *
 * *Who stays silent when others say it* reads the ordered counts (A4); the
 * fixture's row for Rwanda carries both readings, 148 of 214 and 120 of 160,
 * so the figure has to print the second.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { base } from '../../playwright.config';

const figureTitled = (page: Page, title: string) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: title, level: 2 })
	});

test(
	'a sufficient delegation is drawn by its conservative estimate',
	{ tag: '@a11y' },
	async ({ page }) => {
		await page.goto(`${base}/actors/`, { waitUntil: 'networkidle' });
		const figure = figureTitled(page, 'What a delegation says that the room does not');
		await expect(figure).toBeVisible();
		await expect(figure.getByRole('combobox', { name: 'Speaker' })).toHaveValue('Rwanda');

		const table = figure.locator('table.bars');
		await expect(table.locator('thead th')).toContainText(['Word', 'Conservative', 'Log ratio']);
		const rows = table.locator('tbody tr');
		await expect(rows).toHaveCount(3);
		// Ranked as the artefact ranks them, by `lrc`.
		await expect(rows.locator('th .word')).toHaveText(['rwanda*', 'interahamwe', 'reconciliation']);

		// The conservative estimate printed first, the counted ratio beside it with
		// its bracket from the repeated draws.
		const second = rows.nth(1);
		await expect(second.locator('td').nth(0)).toHaveText('+1.75');
		await expect(second.locator('td').nth(1)).toContainText('+4.38');
		await expect(second.locator('td').nth(1)).toContainText('[+3.90, +4.60]');

		// The bar is the estimate against the widest drawn: 1.75 of 3.10.
		const weight = await second
			.locator('.bar')
			.evaluate((bar) => Number(getComputedStyle(bar).getPropertyValue('--weight')));
		expect(weight).toBeCloseTo(1.75 / 3.1, 3);
		const width = await second.locator('.bar').evaluate((bar) => bar.getBoundingClientRect().width);
		expect(width).toBeGreaterThan(0);

		// The speaker's own name is marked, and counted.
		await expect(rows.first().locator('abbr')).toHaveAttribute(
			'title',
			"A word from this speaker's own name."
		);
		await expect(figure.locator('.note-self')).toContainText('1 of the 3 rows drawn');
		await expect(figure).toContainText('Rows rank by a conservative estimate');

		const { violations } = await new AxeBuilder({ page }).include('#speaker-keyness').analyze();
		expect(violations).toEqual([]);
	}
);

test('the whole-corpus reading draws its own table, without brackets', async ({ page }) => {
	await page.goto(`${base}/actors/`, { waitUntil: 'networkidle' });
	const figure = figureTitled(page, 'What a delegation says that the room does not');
	await figure.getByRole('combobox', { name: 'Compared against' }).selectOption('unmatched');
	const rows = figure.locator('table.bars tbody tr');
	await expect(rows.locator('th .word')).toHaveText(['rwanda*', 'interahamwe', 'tribunal']);
	await expect(rows.nth(2).locator('td').nth(0)).toHaveText('+1.90');
	await expect(figure.locator('table.bars .interval')).toHaveCount(0);
});

test('who stays silent reads the order of speaking', async ({ page }) => {
	await page.goto(`${base}/actors/`, { waitUntil: 'networkidle' });
	const figure = figureTitled(page, 'Who stays silent when others say it');
	await expect(figure).toContainText('after another speaker had already used the word');
	// The room's share on the ordered reading, 13.38%, not the 11.52% of any order.
	await expect(figure).toContainText('13.38%');

	const row = figure.locator('tbody tr').filter({ hasText: 'Rwanda' });
	await expect(row.locator('td').nth(0)).toHaveText('75.00%');
	await expect(row.locator('td.num')).toContainText(['75.00%', '160', '120']);
});
