/**
 * The densest route on the site, and until now the only one with no journey.
 *
 * It had none because it could not have one: `series/quarterly.json`,
 * `series/monthly.json` and `series/breakdowns.json` were absent from the
 * fixtures, so `/chronology` answered 500 and every spec that tried to visit it
 * failed at the door. Six plates, the calendar, the change-point test and the
 * split were therefore the least-tested code in the project — which is a
 * plausible reason this page accumulated a P0 and four P1s in review while
 * better-covered routes did not.
 *
 * The fixtures carry all three states the calendar can draw — months divided
 * by, months too thin to divide by, and months the Council did not sit in —
 * because a fixture that holds only one cannot catch the day two of them merge.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { base } from '../../playwright.config';

test('the chronology draws its six plates from the artefacts', async ({ page }) => {
	const response = await page.goto(`${base}/chronology/`);
	expect(response?.status()).toBe(200);

	await expect(page.getByRole('heading', { name: 'Chronology', level: 1 })).toBeVisible();
	for (const plate of [
		'The reading set, year by year',
		'The word list over time',
		"The vocabulary's calendar",
		'The same twelve months, pooled',
		'Testing for a change in the rate',
		'Who says it, and in what debate'
	]) {
		await expect(page.getByRole('heading', { name: plate })).toBeVisible();
	}

	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
});

test('a term the artefact does not carry is dropped, not fatal', async ({ page }) => {
	// The page opens on four named terms and the fixture lexicon carries one.
	// The chart had always filtered on "is this measure in the payload"; the
	// table had not, so an absent term reached `allMeasures[name][unit]` and
	// took the whole route down with a 500 rather than showing the three plates
	// that had nothing to do with it.
	await page.goto(`${base}/chronology/`);

	const table = page.locator('details.data-table').first();
	await table.locator('summary').click();
	const headers = table.locator('thead th');
	await expect(headers).toHaveText(['Period', 'genocide']);
	await expect(table.locator('tbody tr')).toHaveCount(3);
});

test('every plotted value opens the passages behind it', async ({ page }) => {
	// The chart offers this on a click. Until the table carried the same links a
	// click was the only way to it, on a page where the grid, the pooled months
	// and the split all carry links in their own tables.
	await page.goto(`${base}/chronology/`);
	const table = page.locator('details.data-table').first();
	await table.locator('summary').click();

	const row = table.locator('tbody tr').filter({ hasText: '1994' }).first();
	const value = row.getByRole('link').first();
	await expect(value).toHaveAttribute(
		'href',
		`${base}/concordance?term=genocide&from=1994&to=1994`
	);

	// Reached the way a keyboard reader reaches it, not by a synthetic click.
	await value.focus();
	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/from=1994&to=1994/);
});

test('the calendar tells a withheld month from one the Council did not sit in', async ({
	page
}) => {
	await page.goto(`${base}/chronology/`);
	const grid = page.locator('svg.grid');
	await expect(grid).toBeVisible();

	const counts = await grid.evaluate((svg) => {
		const cells = [...svg.querySelectorAll('rect')].filter((r) => r.querySelector('title'));
		const bucket = { drawn: 0, withheld: 0, unobserved: 0 };
		for (const cell of cells) {
			const title = cell.querySelector('title')?.textContent ?? '';
			if (/withheld/.test(title)) bucket.withheld += 1;
			else if (/held no speeches/.test(title)) bucket.unobserved += 1;
			else bucket.drawn += 1;
		}
		const hatched = cells.filter((r) => (r.getAttribute('fill') ?? '').includes('url(')).length;
		const key = [...svg.querySelectorAll('text')]
			.map((t) => t.textContent ?? '')
			.filter((t) => /no rate|no sitting/.test(t));
		return { cells: cells.length, ...bucket, hatched, key };
	});

	// The complete grid, and every cell in exactly one state.
	expect(counts.cells).toBe(36);
	expect(counts.drawn + counts.withheld + counts.unobserved).toBe(36);
	expect(counts.withheld).toBeGreaterThan(0);
	expect(counts.unobserved).toBeGreaterThan(0);

	// The hatch means one thing, and the key counts exactly what it marks. Both
	// refusals used to be hatched while the key named only the first of them.
	expect(counts.hatched).toBe(counts.withheld);
	expect(counts.key).toEqual([`no rate (${counts.withheld})`, `no sitting (${counts.unobserved})`]);
});

test('the calendar stays legible at a phone width', async ({ page }) => {
	// The grid used to be drawn at a fixed 1,220 user units and scaled into its
	// column, which at 390px rendered every label at 2.52 CSS pixels.
	await page.setViewportSize({ width: 390, height: 780 });
	await page.goto(`${base}/chronology/`);
	const grid = page.locator('svg.grid');
	await expect(grid).toBeVisible();

	// Polled: the drawing is built from its measured column, so the first frame
	// carries the size it was rendered at on the server and the observer corrects
	// it on the next one.
	await expect
		.poll(
			() =>
				grid.evaluate((svg) => {
					const box = svg.getBoundingClientRect();
					const viewBox = Number((svg.getAttribute('viewBox') ?? '0 0 1 1').split(' ')[2]);
					const scale = box.width / viewBox;
					const sizes = [...svg.querySelectorAll('text')].map(
						(t) => Number(t.getAttribute('font-size')) * scale
					);
					return Math.round(Math.min(...sizes) * 10) / 10;
				}),
			{ message: 'the smallest label the calendar draws, in CSS pixels' }
		)
		.toBeGreaterThanOrEqual(10);

	// And the page still does not scroll sideways at the reflow width.
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
