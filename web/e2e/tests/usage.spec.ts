/**
 * The experimental layer, exercised through the real routes over tiny fixtures.
 *
 * What these journeys hold is the part of the view a unit test cannot: that the
 * marking is on the page before any figure is, that a cell is a control a
 * reader can actually reach, and that the label in it reads back to the
 * sentence and the speech it came from. The arithmetic beneath all of that —
 * which rows are drawn, what is withheld, where a key press goes — is pinned in
 * `src/lib/usage.test.ts` and is not re-asserted here.
 */

import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { base } from '../../playwright.config';

const usage = `${base}/usage/`;

async function expectNoAxeViolations(page: Page) {
	const { violations } = await new AxeBuilder({ page }).analyze();
	expect(violations).toEqual([]);
}

/**
 * Open the view and wait for the client to have taken it over.
 *
 * The page is server-rendered, so the matrix is on screen and inert for a
 * moment before hydration attaches its handlers, and a click inside that window
 * is simply lost. The gate is a behaviour rather than a timeout: a control the
 * URL cannot be read for is dropped on the first write the client makes, so the
 * unreadable `sort` disappearing is the client arriving — and asserting it here
 * is also the only place that rule is exercised in a browser.
 */
async function openUsage(page: Page) {
	await page.goto(`${usage}?sort=vibes`);
	await expect(page).toHaveURL(/\/usage\/$/);
}

/** The matrix figure, picked out by its own heading rather than by position. */
const matrixOf = (page: Page) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: 'Which genocide each delegation means', level: 2 })
	});

/** The diffusion figure, likewise. */
const diffusionOf = (page: Page) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: 'When each delegation first said it', level: 2 })
	});

/** The reading list of passages the two runs read differently. */
const contestedOf = (page: Page) =>
	page.locator('figure.figure').filter({
		has: page.getByRole('heading', { name: 'The contested passages', level: 2 })
	});

test('the page says whose reading this is before it draws anything', async ({ page }) => {
	await openUsage(page);
	await expect(
		page.getByRole('heading', { name: 'What the word was doing', level: 1 })
	).toBeVisible();

	// The standing apparatus block, above the first figure in the document.
	const experiment = page.locator('section.experiment');
	await expect(experiment).toContainText('Experimental — model-derived');
	await expect(experiment).toContainText('The human labels are the authority');
	await expect(experiment).toContainText('chatgpt-5.6-luna-2026-08-01');
	await expect(experiment).toContainText('sha256:0f1e2d3c4b5a…');
	await expect(experiment).toContainText('12 of 12 occurrences');
	// An untouched gold sample is reported as untouched, never as a zero score.
	await expect(experiment).toContainText('not started — 0 of 200 coded');

	const matrix = matrixOf(page);
	// Referents ranked by weight, with the meta referent moved past the cases
	// even though it ties the largest of them on count — and the abstention code
	// given no column at all, because an occurrence carrying it is not placed.
	await expect(matrix.locator('thead th button')).toHaveText([
		'Rwanda (1994)',
		'Bosnia and Srebrenica',
		'The Holocaust',
		'Genocide Convention and legal definition'
	]);
	const speakers = matrix.locator('th.who button');
	await expect(speakers).toHaveCount(3);
	await expect(speakers.nth(0)).toContainText('Rwanda');
	await expect(speakers.nth(2)).toContainText('European Union');

	// The cut and the empty column are stated rather than left to be noticed.
	await expect(matrix.locator('p.disclosure')).toContainText(
		'3 of 3 delegations with anything placed are drawn here'
	);
	await expect(matrix.locator('p.disclosure')).toContainText(
		'1 referent on the list is used by no delegation drawn here'
	);

	await expectNoAxeViolations(page);
});

test('a cell opens the occurrences behind it, and a way into the record', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);

	await matrix.getByRole('button', { name: /^Rwanda × Rwanda \(1994\): 2 occurrences/ }).click();
	await expect(page).toHaveURL(/\?actor=Rwanda&referent=rwanda_1994$/);

	const evidence = page.locator('section.evidence');
	await expect(
		page.getByRole('heading', { name: 'Rwanda on Rwanda (1994)', level: 2 })
	).toBeVisible();
	await expect(evidence.locator('ol.quotations li')).toHaveCount(2);
	await expect(evidence.locator('blockquote').first()).toHaveText(
		'We warned that genocide could occur.'
	);
	await expect(evidence.locator('.speaker_position').first()).toHaveText('Conditional');
	await expect(evidence.locator('.speaker_position').nth(1)).toHaveText('Rejects');

	// Annotation schema 3's six fields, shown where the run answered them and
	// absent where it did not. The first occurrence in the fixture stands for a
	// run coded against schema 3 and the rest for one coded against schema 2,
	// which has no image of any of the six: an empty value is "never asked" and
	// must not be rendered as an answer.
	const answered = evidence.locator('ol.quotations li').nth(0).locator('dl.schema-fields');
	await expect(answered.locator('dt')).toHaveText([
		'Referent read from',
		'Accused',
		'Victim group',
		'Speaker’s own State accused',
		'Salience',
		'Rationale'
	]);
	await expect(answered.locator('dd').first()).toHaveText('passage');
	await expect(evidence.locator('ol.quotations li').nth(1).locator('dl.schema-fields')).toHaveCount(
		0
	);

	// The link carries the term, the speech and the exact occurrence, so the
	// reader opens on the span the label was read from.
	await expect(
		evidence.getByRole('link', { name: 'Read the whole speech' }).first()
	).toHaveAttribute(
		'href',
		`${base}/reader/UNSC_2014_SPV.7000?term=genocide&speech=UNSC_2014_SPV.7000_spch0001&occurrence=UNSC_2014_SPV.7000_spch0001%231`
	);
	// The concordance cannot name one line, so the link lands on the delegation
	// and the record it came from.
	await expect(evidence.getByRole('link', { name: 'See in concordance' }).first()).toHaveAttribute(
		'href',
		`${base}/concordance?term=genocide&country=Rwanda&spv=S%2FPV.7000`
	);

	await expectNoAxeViolations(page);
});

test('the unit toggle is written into the URL and hatches what it withholds', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);
	const eu = matrix.getByRole('button', { name: /^European Union × Rwanda \(1994\)/ });

	// A count is published at every denominator; the same cell as a share is not.
	await expect(eu).toHaveAttribute('data-state', 'drawn');

	await page.getByRole('button', { name: 'Share of its own' }).click();
	await expect(page).toHaveURL(/\?unit=share$/);
	await expect(eu).toHaveAttribute('data-state', 'withheld-share');
	await expect(eu).toHaveAttribute('aria-label', /share withheld — fewer than 3 eligible/);
	await expect(matrix.locator('.key')).toContainText('share withheld (1)');
});

test('a copied URL restores the same reading of the matrix', async ({ page }) => {
	await page.goto(`${usage}?actor=France&referent=bosnia_srebrenica&unit=share&sort=name`);

	await expect(page.getByRole('button', { name: 'Share of its own' })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(page.getByRole('combobox', { name: 'Ordered by' })).toHaveValue('name');
	await expect(
		page.getByRole('heading', { name: 'France on Bosnia and Srebrenica', level: 2 })
	).toBeVisible();

	const evidence = page.locator('section.evidence');
	await expect(evidence.locator('ol.quotations li')).toHaveCount(2);
	await expect(evidence.locator('blockquote').first()).toHaveText(
		'The Council must call this genocide by its name.'
	);
	// The model's own span is narrower than the sentence, so it is shown as well.
	await expect(evidence.locator('ol.quotations li').first()).toContainText("Model's evidence span");
	await expect(evidence.locator('ol.quotations li').first()).toContainText(
		'“must call this genocide by its name”'
	);
	await expect(page).toHaveURL(
		/\/usage\/\?actor=France&referent=bosnia_srebrenica&unit=share&sort=name$/
	);
});

test('the diffusion figure draws one referent and lists the firsts behind it', async ({ page }) => {
	await openUsage(page);
	const figure = diffusionOf(page);

	// With nothing selected the figure falls back to the first named case the
	// chronology carries, and the curve's own key names what was drawn.
	await expect(figure.getByRole('combobox', { name: 'Referent' })).toHaveValue('rwanda_1994');
	await expect(figure.locator('.key')).toContainText('Placed the word on it');
	await expect(figure.locator('.key')).toContainText('Refused the word for it');
	await expect(figure.getByRole('img')).toHaveAttribute(
		'aria-label',
		/Cumulative delegations for Rwanda \(1994\)/
	);

	// The chronology is the accessible figure: the same steps, in order, as text.
	const rows = figure.locator('table.chronology tbody tr');
	await expect(rows).toHaveCount(4);
	await expect(rows.nth(0)).toContainText('Rwanda');
	await expect(rows.nth(0)).toContainText('Placed the word on it');
	await expect(rows.nth(1)).toContainText('Refused the word for it');
	await expect(rows.nth(3)).toContainText('European Union');
	await expect(rows.nth(3)).toContainText('Asserted it');

	// The link into the record is built from the line identifier alone, and the
	// concordance link needs a record symbol this fixture has no line for.
	await expect(rows.nth(0).getByRole('link').first()).toHaveAttribute(
		'href',
		`${base}/reader/UNSC_2014_SPV.7000?term=genocide&speech=UNSC_2014_SPV.7000_spch0001&occurrence=UNSC_2014_SPV.7000_spch0001%231`
	);
	await expect(rows.nth(2).getByRole('link', { name: 'concordance' })).toHaveCount(0);

	await expectNoAxeViolations(page);
});

test('the referent picker moves both figures, and the URL carries it', async ({ page }) => {
	await openUsage(page);
	const figure = diffusionOf(page);

	await figure.getByRole('combobox', { name: 'Referent' }).selectOption('bosnia_srebrenica');
	await expect(page).toHaveURL(/\?referent=bosnia_srebrenica$/);

	// One state, two figures: the matrix column is now the selected one.
	await expect(
		matrixOf(page).getByRole('button', { name: 'Bosnia and Srebrenica', exact: true })
	).toHaveAttribute('aria-pressed', 'true');

	// France's first placed use of the word here was already the assertion, so
	// the envelope is the assertion curve drawn twice and is not drawn at all.
	const rows = figure.locator('table.chronology tbody tr');
	await expect(rows).toHaveCount(1);
	await expect(rows.nth(0)).toContainText('France');
	await expect(figure.locator('.key')).not.toContainText('Placed the word on it');

	// The record symbol comes from the concordance file, and it is what makes the
	// second link addressable at all.
	await expect(rows.nth(0).getByRole('link', { name: 'concordance' })).toHaveAttribute(
		'href',
		`${base}/concordance?term=genocide&country=France&spv=S%2FPV.7481`
	);
});

test('the whole matrix is one tab stop, and the arrow keys move inside it', async ({ page }) => {
	await openUsage(page);
	const matrix = matrixOf(page);

	const first = matrix.getByRole('button', { name: /^Rwanda × Rwanda \(1994\)/ });
	await first.focus();
	await page.keyboard.press('ArrowRight');

	const next = matrix.getByRole('button', {
		name: 'Rwanda × Bosnia and Srebrenica: no occurrence placed here.'
	});
	await expect(next).toBeFocused();
	// Every other cell is out of the tab order while one of them holds it.
	await expect(first).toHaveAttribute('tabindex', '-1');
	await expect(next).toHaveAttribute('tabindex', '0');

	await page.keyboard.press('Enter');
	await expect(page).toHaveURL(/referent=bosnia_srebrenica/);
	// A pairing the matrix counts and the quotation file has nothing for says so
	// rather than showing an empty list.
	await expect(page.locator('section.evidence')).toContainText(
		'No annotated occurrence in this build carries that pairing'
	);
});

/* ---- the second opinion --------------------------------------------------- *
 * A comparison run is a second model given the byte-identical prompt and the
 * same occurrences. What these journeys hold is that the page never lets it be
 * read as a correction: both models are named, the sentence about what agreement
 * measures is on screen beside every number, and a contested passage carries
 * both readings rather than one replaced by the other.
 * --------------------------------------------------------------------------- */

test('the apparatus names the second opinion and what agreement between two models is', async ({
	page
}) => {
	await openUsage(page);
	const second = page.locator('section.experiment .second-opinion');
	await expect(page.getByRole('heading', { name: 'Second opinion', level: 2 })).toBeVisible();

	await expect(second).toContainText('gemini-3-pro-2026-07-15');
	await expect(second).toContainText('2026-09-06-gemini-v1');
	// The same question, asked the same way: 15 refuses to publish a comparison
	// made from other instructions, and the page states that rather than assuming it.
	await expect(second).toContainText('byte-identical prompt');
	await expect(second).toContainText(
		'agreement between two models measures stability across instruments, never accuracy'
	);
	await expect(second).toContainText('4 carry a label from both runs');

	const rows = second.locator('table tbody tr');
	await expect(rows).toHaveCount(4);
	await expect(rows.nth(0)).toContainText('verdict');
	// With every row in one category there is no chance agreement to correct for,
	// and a kappa of 0.00 would read as two runs agreeing by luck alone.
	await expect(rows.nth(0).locator('td').nth(2)).toHaveText('—');
	await expect(rows.nth(2)).toContainText('50.00%');
	await expect(second).toContainText('0.88');
	await expect(second).toContainText('2 of 4 compared occurrences');

	await expectNoAxeViolations(page);
});

test('a contested quotation is marked, and carries the other reading in place', async ({
	page
}) => {
	await page.goto(`${usage}?actor=Rwanda&referent=rwanda_1994`);
	const quotations = page.locator('section.evidence ol.quotations li');
	await expect(quotations).toHaveCount(2);

	// The two runs agreed about the first occurrence and not about the second, so
	// only the second is marked.
	await expect(quotations.nth(0).locator('.contested')).toHaveCount(0);
	await expect(quotations.nth(1).locator('.contested')).toHaveText('Contested: speaker position');

	const reading = quotations.nth(1).locator('.second-reading');
	await expect(reading).toContainText('The second model read');
	await expect(reading).toContainText('Reports without a position');
	// Both readings, side by side. Neither replaces the other.
	await expect(reading).toContainText('— this run read Rejects');
	await expect(quotations.nth(1).locator('.speaker_position')).toHaveText('Rejects');
});

test('the contested filter narrows the quotations and the URL carries it', async ({ page }) => {
	await page.goto(`${usage}?actor=Rwanda&referent=rwanda_1994`);
	const evidence = page.locator('section.evidence');
	await expect(evidence.locator('ol.quotations li')).toHaveCount(2);

	const filter = page.getByRole('checkbox', { name: /Contested only/ });
	await expect(filter).toBeVisible();
	await filter.check();

	await expect(page).toHaveURL(/\?actor=Rwanda&referent=rwanda_1994&contested=1$/);
	await expect(evidence.locator('ol.quotations li')).toHaveCount(1);
	await expect(evidence.locator('ol.quotations li .contested')).toHaveText(
		'Contested: speaker position'
	);
	// The denominator travels with the filtered count, so a narrowed list never
	// reads as the whole of what was behind the cell.
	await expect(evidence).toContainText('1 occurrence, of 2 behind this pairing');
});

test('a copied URL restores the contested filter', async ({ page }) => {
	await page.goto(`${usage}?actor=Rwanda&referent=rwanda_1994&contested=1`);
	await expect(page.getByRole('checkbox', { name: /Contested only/ })).toBeChecked();
	await expect(page.locator('section.evidence ol.quotations li')).toHaveCount(1);
	await expect(page).toHaveURL(/\/usage\/\?actor=Rwanda&referent=rwanda_1994&contested=1$/);
});

test('the reading list ranks the contested passages hardest first', async ({ page }) => {
	await openUsage(page);
	const figure = contestedOf(page);
	const rows = figure.locator('table.contested-table tbody tr');
	await expect(rows).toHaveCount(2);

	// Three fields apart in 2015 above one field apart in 2014: the order is how
	// much the two instruments disagree, not the date.
	await expect(rows.nth(0)).toContainText('France');
	await expect(rows.nth(0)).toContainText('8 July 2015');
	await expect(rows.nth(0).locator('.field')).toHaveText([
		'speaker position',
		'function',
		'referent'
	]);
	await expect(rows.nth(0).locator('.reading.other')).toHaveText([
		'Rejects',
		'accusation or qualification',
		'Genocide Convention and legal definition'
	]);
	await expect(rows.nth(0).locator('.reading:not(.other)')).toHaveText([
		'Asserts',
		'accusation or qualification, accountability',
		'Bosnia and Srebrenica'
	]);
	await expect(rows.nth(1)).toContainText('Rwanda');

	// The reader link idiom the chronology uses: the identifier is the link.
	await expect(rows.nth(0).getByRole('link').first()).toHaveAttribute(
		'href',
		`${base}/reader/UNSC_2015_SPV.7481?term=genocide&speech=UNSC_2015_SPV.7481_spch0007&occurrence=UNSC_2015_SPV.7481_spch0007%231`
	);
	await expect(rows.nth(0).getByRole('link', { name: 'concordance' })).toHaveAttribute(
		'href',
		`${base}/concordance?term=genocide&country=France&spv=S%2FPV.7481`
	);

	await expect(figure.locator('p.disclosure')).toContainText(
		'2 of 2 contested occurrences are drawn here, out of 4'
	);
	await expect(figure).toContainText(
		'Agreement between two models measures stability across instruments, never accuracy.'
	);

	await expectNoAxeViolations(page);
});

test('a build with no second opinion shows none of it', async ({ page }) => {
	const body = await readFile(
		new URL('../fixtures/data/usage/usage.json', import.meta.url),
		'utf8'
	);
	const payload = JSON.parse(body) as { comparison: Record<string, unknown> };
	// The artefact's own empty state, which is what the published payload carries
	// until a comparison run is bought: same keys, no run, nothing computed.
	payload.comparison = {
		state: 'none',
		run_id: '',
		model: '',
		run_date: '',
		reasoning_effort: '',
		prompt_sha256: '',
		occurrences_annotated: 0,
		overlap: 0,
		evidence_invalid: 0,
		abstention: { verdict_uncertain: 0, referent_unclear: 0, position_unclear: 0 },
		fields: [],
		function_jaccard: null,
		function_contested: 0,
		contested_any: 0
	};
	await page.route('**/data/usage/usage.json', (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
	);

	// Interception sees browser requests, and the first load of a page is answered
	// by the server. Arriving from another section runs the view's load in the
	// browser, which is where the variant payload can be substituted.
	await page.goto(`${base}/`);
	await page
		.getByRole('navigation', { name: 'Sections' })
		.getByRole('link', { name: 'Usage' })
		.click();
	await expect(
		page.getByRole('heading', { name: 'What the word was doing', level: 1 })
	).toBeVisible();

	// The standing marking is untouched; everything the comparison added is gone.
	await expect(page.locator('section.experiment')).toContainText('Experimental — model-derived');
	await expect(page.locator('section.experiment .second-opinion')).toHaveCount(0);
	await expect(page.getByRole('heading', { name: 'Second opinion' })).toHaveCount(0);
	await expect(contestedOf(page)).toHaveCount(0);

	// And the filter, even with a cell open: an empty shell is not the honest
	// shape here, an absence is.
	await matrixOf(page)
		.getByRole('button', { name: /^Rwanda × Rwanda \(1994\): 2 occurrences/ })
		.click();
	await expect(page.locator('section.evidence ol.quotations li')).toHaveCount(2);
	await expect(page.getByRole('checkbox', { name: /Contested only/ })).toHaveCount(0);
	await expect(page.locator('section.evidence .contested')).toHaveCount(0);

	await expectNoAxeViolations(page);
});
