/**
 * *Agenda or usage?*, drawn in a browser (review of 9 November 2026, C1).
 *
 * The plate reads `series/decomposition.json`, which the fixtures did not
 * carry, so the figure had unit tests over `#lib/decomposition` and no journey:
 * nothing had ever clicked its switch, walked its rows by keyboard or opened
 * its table. The fixture holds three decade pairs under both splits, and in
 * every row the composition and within parts add exactly to the change, so
 * whatever the page prints can be checked by hand against the file.
 */
import { expect, test, type Page } from '@playwright/test';
import { base } from '../../playwright.config';

const plate = (page: Page) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: 'Agenda or usage?', level: 2 })
	});

test('the plate renders its three decade pairs and sits after the rate test', async ({ page }) => {
	await page.goto(`${base}/chronology/`, { waitUntil: 'networkidle' });
	const figure = plate(page);
	await expect(figure).toBeVisible();
	await expect(figure.locator('g.pair')).toHaveCount(3);

	// The first row is the largest change, so it is the one described on arrival:
	// +1.50 points, +0.90 from composition and +0.60 within.
	const detail = figure.locator('.detail');
	await expect(detail).toContainText('+1.50 pts: +0.90 pts from composition and +0.60 pts within');
	await expect(detail.locator('ol.largest li').first()).toContainText(
		'The situation concerning Rwanda'
	);

	const links = page.getByRole('navigation', { name: 'Figures on this page' }).getByRole('link');
	const titles = await links.allTextContents();
	expect(titles.indexOf('Agenda or usage?')).toBe(
		titles.indexOf('Testing for a change in the rate') + 1
	);
});

test('the split switch redraws the parts and is carried in the URL', async ({ page }) => {
	await page.goto(`${base}/chronology/`, { waitUntil: 'networkidle' });
	const figure = plate(page);
	const group = figure.getByRole('group', { name: 'Split the change' });
	const agenda = group.getByRole('button', { name: 'By agenda item' });
	const speakers = group.getByRole('button', { name: 'By speaker group' });
	await expect(agenda).toHaveAttribute('aria-pressed', 'true');
	await expect(speakers).toHaveAttribute('aria-pressed', 'false');
	// The default split is left out of the address.
	expect(new URL(page.url()).searchParams.has('parts')).toBe(false);

	await speakers.click();
	await expect(speakers).toHaveAttribute('aria-pressed', 'true');
	await expect(page).toHaveURL(/[?&]parts=speaker_group/);
	// Same change, different parts: +0.20 from composition, +1.30 within.
	await expect(figure.locator('.detail')).toContainText(
		'+1.50 pts: +0.20 pts from composition and +1.30 pts within'
	);
	await expect(figure.locator('.detail ol.largest')).toContainText('P5');

	// A copied address opens on the same split.
	await page.reload();
	await expect(plate(page).getByRole('button', { name: 'By speaker group' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(plate(page).locator('.detail')).toContainText('+0.20 pts from composition');
});

test('a row is chosen by keyboard and its largest groups are listed as text', async ({ page }) => {
	await page.goto(`${base}/chronology/`, { waitUntil: 'networkidle' });
	const figure = plate(page);
	const rows = figure.locator('g.pair');
	await expect(rows).toHaveCount(3);

	await rows.first().focus();
	await expect(rows.first()).toHaveAttribute('aria-pressed', 'true');
	await page.keyboard.press('ArrowDown');

	const second = rows.nth(1);
	await expect(second).toBeFocused();
	await expect(second).toHaveAttribute('aria-pressed', 'true');
	await expect(rows.first()).toHaveAttribute('aria-pressed', 'false');
	await expect(second).toHaveAccessibleName(/change −0\.50 pts, composition −0\.70 pts/);

	// The groups are text a screen reader reaches, not a tooltip.
	const detail = figure.locator('.detail');
	await expect(detail).toContainText('−0.50 pts: −0.70 pts from composition and +0.20 pts within');
	await expect(detail.locator('ol.largest li')).toHaveText([
		/Reports on the Sudan\s*−0\.30 pts/,
		/Children and armed conflict\s*\+0\.10 pts/
	]);

	// Enter on the last row chooses it too.
	await page.keyboard.press('ArrowDown');
	await page.keyboard.press('Enter');
	await expect(rows.nth(2)).toHaveAttribute('aria-pressed', 'true');
	await expect(detail.locator('ol.largest li')).toHaveText([
		/The situation in the Middle East\s*\+0\.50 pts/
	]);
});

test('the table fallback holds every row of the split shown', async ({ page }) => {
	await page.goto(`${base}/chronology/`, { waitUntil: 'networkidle' });
	const figure = plate(page);
	const table = figure.locator('details.data-table');
	await table.locator('summary').click();
	const body = table.locator('tbody tr');
	await expect(body).toHaveCount(3);
	await expect(body.nth(0)).toContainText('2.00% → 3.50%');
	await expect(body.nth(0).locator('td')).toContainText(['+1.50 pts', '+0.90 pts', '+0.60 pts']);
	await expect(body.nth(1).locator('td')).toContainText(['−0.50 pts', '−0.70 pts', '+0.20 pts']);
	await expect(body.nth(2).locator('td')).toContainText(['+0.60 pts', '+0.40 pts', '+0.20 pts']);
	await expect(body.nth(2)).toContainText('The situation in the Middle East (+0.50 pts)');
});
