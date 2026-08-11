/**
 * The fetch boundary: what it caches, and what it refuses.
 *
 * `data.ts` is the only place the dashboard meets the pipeline's artefacts, so
 * it is where a malformed or missing file has to become a sentence a reader can
 * act on rather than a blank chart. Two of its behaviours are load-bearing and
 * invisible when they work — a failed request being evicted so a retry can
 * succeed, and a successful one being fetched once — so both are pinned here.
 *
 * `json()` already takes the fetcher as an argument, so nothing below touches
 * the network or the filesystem.
 */

import { describe, expect, it, vi } from 'vitest';

/**
 * A fresh copy of the module for each test.
 *
 * The cache in `data.ts` lives at module scope, deliberately: it is what stops
 * a 10 MB concordance being fetched twice as a reader moves between views. That
 * also makes it shared state between tests, and a suite that passes only in the
 * order it happens to be written in is worse than no suite. Each test gets its
 * own module instance instead.
 */
async function fresh() {
	vi.resetModules();
	return import('./data');
}

function responder(payload: unknown, options: { ok?: boolean; status?: number } = {}) {
	const calls = { count: 0 };
	const respond = () => {
		calls.count += 1;
		return Promise.resolve({
			ok: options.ok ?? true,
			status: options.status ?? 200,
			json: () => Promise.resolve(payload)
		} as Response);
	};
	return { fetcher: respond as unknown as typeof fetch, calls };
}

const meta = { script: '04_series.py', generated: '2026-08-09T08:54:11Z' };

const annualPayload = (overrides: Record<string, unknown> = {}) => ({
	meta,
	periods: [1992, 1993],
	corpus: { speeches: [12, 14], tokens: [900, 1100], meetings: [3, 4] },
	terms: {},
	...overrides
});

describe('the cache in front of the artefacts', () => {
	it('drops a failed request so the reader can try again', async () => {
		const { annual } = await fresh();
		const failure = responder(null, { ok: false, status: 503 });
		await expect(annual(failure.fetcher)).rejects.toThrow(/503/);

		// The concordance offers a "Try again" button, and it only works because
		// the rejected promise is deleted from the cache rather than kept and
		// re-thrown for the rest of the session.
		const recovery = responder(annualPayload());
		await expect(annual(recovery.fetcher)).resolves.toMatchObject({ periods: [1992, 1993] });
		expect(recovery.calls.count).toBe(1);
	});

	it('fetches one artefact once, however many views ask for it', async () => {
		const { annual } = await fresh();
		const { fetcher, calls } = responder(annualPayload());
		await annual(fetcher);
		await annual(fetcher);
		expect(calls.count).toBe(1);
	});
});

describe('what a bad response is turned into', () => {
	it('names the status and says the pipeline has probably not been run', async () => {
		const { collocates } = await fresh();
		const { fetcher } = responder(null, { ok: false, status: 404 });
		// A 404 here almost always means `static/data/` was never built. Someone
		// tidying this message would remove the only thing that makes the failure
		// actionable for a reader who has just cloned the repository.
		await expect(collocates(fetcher)).rejects.toThrow(
			/lexical\/collocates\.json is missing \(404\)/
		);
		await expect(collocates(fetcher)).rejects.toThrow(
			/Run the pipeline and scripts\/export_web\.py/
		);
	});

	it('names every missing field at once rather than one per attempt', async () => {
		const { annual } = await fresh();
		const { fetcher } = responder({ meta, periods: [1992] });
		// Reported together because a reader fixing an artefact by hand should
		// not have to reload three times to find out what else is absent.
		await expect(annual(fetcher)).rejects.toThrow(/missing required field\(s\): corpus, terms/);
	});

	it('tells a field that is absent from one that is the wrong kind', async () => {
		const { annual } = await fresh();
		const { fetcher } = responder(annualPayload({ periods: { 1992: true }, terms: [] }));
		// Two different repairs: a missing field is usually a renamed one upstream,
		// a mis-typed field is usually a changed writer. The boundary owns both
		// checks now — the validators hold no `must be an array` lines at all — so
		// this is where the wording has to stay useful.
		await expect(annual(fetcher)).rejects.toThrow(/annual\.json\.periods must be an array/);
		await expect(annual(fetcher)).rejects.toThrow(/annual\.json\.terms must be an object/);
	});

	it('reports a JSON array as a missing `meta`, not as "not an object"', async () => {
		const { json } = await fresh();
		const { fetcher } = responder([]);
		// Pinned as it behaves rather than as the guard reads: `typeof []` is
		// 'object', so an array slips past the shape check and is caught one step
		// later by the required-field check. The message is still true, just not
		// the one the guard above it was written for.
		await expect(json('probe.json', fetcher)).rejects.toThrow(
			/probe\.json is missing required field\(s\): meta/
		);
	});
});

describe('the validators that are about the research rather than the types', () => {
	it('refuses a chronology event with no link to its primary record, naming which one', async () => {
		const { events } = await fresh();
		const { fetcher } = responder({
			meta,
			events: [
				{ date: '1994-04-07', source_url: 'https://digitallibrary.un.org/record/1' },
				{ date: '1995-07-11' }
			]
		});
		// Every annotation on the chronology must link to the institutional record
		// behind it — docs/PLAN.md §1.2 — and this is where that is enforced for
		// anything the dashboard is willing to draw.
		await expect(events(fetcher)).rejects.toThrow(/events\[1\] lacks a date or primary-source URL/);
	});

	it('refuses a corpus series that does not line up with its own periods', async () => {
		const { annual } = await fresh();
		const { fetcher } = responder(
			annualPayload({ corpus: { speeches: [12, 14], tokens: [900], meetings: [3, 4] } })
		);
		// Silently, a short array plots as a truncated line rather than an error,
		// so the misalignment has to be refused here and it has to say which
		// field is short.
		await expect(annual(fetcher)).rejects.toThrow(/corpus\.tokens must align with periods/);
	});

	it.each([
		['NaN', Number.NaN],
		['Infinity', Number.POSITIVE_INFINITY],
		['a string', '0.86']
	])('refuses a keyness coverage of %s', async (_name, coverage) => {
		// `typeof NaN` and `typeof Infinity` are both 'number', so a type check
		// let a coverage that failed to compute through the boundary and into the
		// figure as "NaN%". A validator exists to refuse what the interface
		// cannot honestly draw, and a proportion that is not a finite number is
		// exactly that.
		const { keyness } = await fresh();
		const { fetcher } = responder({
			meta,
			keywords: [],
			keywords_unmatched: [],
			stability: { repetitions: 8 },
			coverage
		});
		await expect(keyness(fetcher)).rejects.toThrow(/coverage must be a finite number/);
	});

	it('accepts an ordinary coverage', async () => {
		const { keyness } = await fresh();
		const { fetcher } = responder({
			meta,
			keywords: [],
			keywords_unmatched: [],
			stability: { repetitions: 8 },
			coverage: 0.8632
		});
		await expect(keyness(fetcher)).resolves.toMatchObject({ coverage: 0.8632 });
	});
});

describe('reading an identifier back to the file it came from', () => {
	it('finds the meeting and the speech behind a concordance line', async () => {
		const { meetingOf, speechOf } = await fresh();
		expect(meetingOf('UNSC_2015_SPV.7481_spch0007#3')).toBe('UNSC_2015_SPV.7481');
		expect(speechOf('UNSC_2015_SPV.7481_spch0007#3')).toBe('UNSC_2015_SPV.7481_spch0007');
	});

	it('leaves an identifier with no occurrence ordinal alone', async () => {
		const { meetingOf, speechOf } = await fresh();
		expect(speechOf('UNSC_2015_SPV.7481_spch0007')).toBe('UNSC_2015_SPV.7481_spch0007');
		expect(meetingOf('UNSC_2015_SPV.7481_spch0007')).toBe('UNSC_2015_SPV.7481');
	});

	it('returns a meeting basename unchanged when there is no speech suffix to strip', async () => {
		const { meetingOf } = await fresh();
		// Documented rather than assumed: the suffix is optional in the regex, so
		// a meeting id passed in comes straight back out.
		expect(meetingOf('UNSC_2015_SPV.7481#1')).toBe('UNSC_2015_SPV.7481');
		expect(meetingOf('UNSC_2015_SPV.7481')).toBe('UNSC_2015_SPV.7481');
	});
});
