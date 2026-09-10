/** Local production-build measurements; supply the base URL of a running preview. */
import { chromium } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import { join } from 'node:path';

const base = process.argv[2]?.replace(/\/$/, '');
if (!base)
	throw new Error(
		'Usage: node scripts/profile-payload.mjs http://127.0.0.1:4275/genocide-at-the-security-council'
	);
const constrained = process.argv.includes('--slow4g');
const output = constrained ? 'test-results/review-slow4g' : 'test-results/review';
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const network = {
	offline: false,
	latency: 150,
	downloadThroughput: 1_600_000 / 8,
	uploadThroughput: 750_000 / 8
};
async function throttle(session) {
	await session.send('Network.enable');
	await session.send('Network.setCacheDisabled', { cacheDisabled: true });
	if (constrained) {
		await session.send('Network.emulateNetworkConditions', network);
		await session.send('Emulation.setCPUThrottlingRate', { rate: 4 });
	}
}
const result = {
	base,
	generated: new Date().toISOString(),
	profile: constrained
		? { simulated: true, network, cpuSlowdown: 4, cache: 'disabled', serviceWorkers: 'blocked' }
		: 'unthrottled',
	measurements: []
};
try {
	for (const term of ['genocide', 'impunity']) {
		const bytes = await readFile(`static/data/kwic/${term}.json`);
		const file = JSON.parse(bytes.toString());
		const target = file.lines.at(-1);
		const context = await browser.newContext({
			serviceWorkers: 'block',
			viewport: { width: 1440, height: 1000 }
		});
		const page = await context.newPage();
		const session = await context.newCDPSession(page);
		await throttle(session);
		page.setDefaultTimeout(constrained ? 180000 : 30000);
		page.setDefaultNavigationTimeout(constrained ? 180000 : 30000);
		await session.send('Performance.enable');
		await session.send('Network.enable');
		await session.send('Network.setCacheDisabled', { cacheDisabled: true });
		let peak = 0;
		const sample = setInterval(async () => {
			try {
				const heap = await session.send('Runtime.getHeapUsage');
				peak = Math.max(peak, heap.usedSize);
			} catch {
				/* context closed */
			}
		}, 100);
		sample.unref();
		const query = new URLSearchParams({ term, spv: target.spv, country: target.country });
		const start = performance.now();
		await page.goto(`${base}/concordance/?${query}`, { waitUntil: 'domcontentloaded' });
		await page.locator('.line').first().waitFor();
		const ready = performance.now() - start;
		await page.locator('.line').first().click();
		await page.getByRole('link', { name: 'Read the whole speech' }).waitFor();
		const detail = performance.now() - start;
		clearInterval(sample); // exclude the isolated parse benchmark's own allocation
		const parse = await page.evaluate((text) => {
			const start = performance.now();
			JSON.parse(text);
			return performance.now() - start;
		}, bytes.toString());
		const resources = await page.evaluate(() =>
			performance.getEntriesByType('resource').map((entry) => ({
				name: entry.name,
				transfer: entry.transferSize,
				decoded: entry.decodedBodySize,
				duration: entry.duration
			}))
		);
		clearInterval(sample);
		await page.evaluate(() => window.scrollTo(0, 0));
		await page.screenshot({ path: join(output, `${term}-desktop.png`), fullPage: false });
		await page.setViewportSize({ width: 390, height: 844 });
		await page.screenshot({ path: join(output, `${term}-mobile.png`), fullPage: false });
		const speech = target.id.split('#')[0];
		const meeting = speech.split('-').slice(0, 2).join('-');
		const readerStart = performance.now();
		await page.goto(
			`${base}/reader/${meeting}?${new URLSearchParams({ term, speech, occurrence: target.id })}`
		);
		await page.locator(`[data-occurrence="${target.id}"]`).waitFor();
		const exactOccurrenceMs = performance.now() - readerStart;
		result.measurements.push({
			term,
			target: target.id,
			exactOccurrenceMs,
			rawBytes: bytes.length,
			gzipBytes: gzipSync(bytes).length,
			firstLineMs: ready,
			detailMs: detail,
			isolatedJsonParseMs: parse,
			sampledPeakJsHeapBytes: peak,
			resources
		});
		await context.close();
	}
	const context = await browser.newContext({
		serviceWorkers: 'block',
		viewport: { width: 1440, height: 1000 }
	});
	const page = await context.newPage();
	await throttle(await context.newCDPSession(page));
	page.setDefaultTimeout(constrained ? 180000 : 30000);
	page.setDefaultNavigationTimeout(constrained ? 180000 : 30000);
	const start = performance.now();
	await page.goto(`${base}/actors/#speakers-by-rate`, { waitUntil: 'domcontentloaded' });
	await page.locator('#speakers-by-rate table tbody tr').first().waitFor();
	result.actors = {
		tableReadyMs: performance.now() - start,
		resources: await page.evaluate(() =>
			performance
				.getEntriesByType('resource')
				.map((entry) => ({ name: entry.name, transfer: entry.transferSize }))
		)
	};
	await page.screenshot({ path: join(output, 'actors-desktop.png') });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.reload();
	await page.locator('#speakers-by-rate table tbody tr').first().waitFor();
	await page.screenshot({ path: join(output, 'actors-mobile.png') });
	const selectionStart = performance.now();
	await page.getByRole('button', { name: 'Rwanda', exact: true }).first().click();
	await page
		.locator('aside.picked')
		.getByRole('heading', { name: 'Rwanda', exact: true })
		.waitFor();
	result.actors.selectionMs = performance.now() - selectionStart;
	const mapStart = performance.now();
	const map = page.getByRole('group', { name: /^Map locating the ranked speakers/ });
	await map.scrollIntoViewIfNeeded();
	try {
		await map.locator('..').getByRole('status').waitFor({ state: 'hidden', timeout: 10000 });
		result.actors.mapReadyMs = performance.now() - mapStart;
	} catch {
		result.actors.mapStatus = await map.locator('..').getByRole('status').textContent();
	}
	result.actors.afterMapResources = await page.evaluate(() =>
		performance
			.getEntriesByType('resource')
			.map((entry) => ({ name: entry.name, transfer: entry.transferSize }))
	);
	await page.screenshot({ path: join(output, 'map-mobile.png') });
	await context.close();
} finally {
	await browser.close();
}
await writeFile(join(output, 'measurements.json'), JSON.stringify(result, null, 2) + '\n');
console.log(
	JSON.stringify(
		{
			...result,
			measurements: result.measurements.map(({ resources, ...row }) => ({
				...row,
				requests: resources.length
			})),
			actors: {
				...result.actors,
				resources: undefined,
				afterMapResources: undefined,
				requests: result.actors.resources.length,
				requestsAfterMap: result.actors.afterMapResources.length
			}
		},
		null,
		2
	)
);
