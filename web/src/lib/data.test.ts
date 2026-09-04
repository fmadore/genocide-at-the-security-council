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
	corpus: { speeches: [12, 14], words: [900, 1100], meetings: [3, 4] },
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

	it('holds three concordances and drops the least recently read', async () => {
		const { kwic } = await fresh();
		const line = (term: string) => ({ meta, term, lines: [] });
		const fetchers = Object.fromEntries(
			['a', 'b', 'c', 'd'].map((term) => [term, responder(line(term))])
		);
		const load = (term: string) => kwic(term, fetchers[term].fetcher);

		await load('a');
		await load('b');
		await load('c');
		// `a` is the oldest by insertion but the most recently *read*, and the
		// ceiling is about what a reader is moving between, not what they opened
		// first. Reading it again is what keeps it.
		await load('a');
		await load('d');

		await load('a');
		expect(fetchers.a.calls.count, 'a was read most recently and should be held').toBe(1);
		await load('b');
		expect(fetchers.b.calls.count, 'b was the least recently read of four').toBe(2);
	});

	it('keeps every small artefact for the whole session', async () => {
		const { annual, kwic } = await fresh();
		const series = responder(annualPayload());
		await annual(series.fetcher);
		// The bounded families must not evict anything outside themselves: the
		// dozen files a route needs to render are small, and every one of them is
		// wanted again the moment the reader goes back.
		for (const term of ['a', 'b', 'c', 'd', 'e']) {
			await kwic(term, responder({ meta, term, lines: [] }).fetcher);
		}
		await annual(series.fetcher);
		expect(series.calls.count).toBe(1);
	});
});

describe('what a bad response is turned into', () => {
	it('names the status and says the pipeline has probably not been run', async () => {
		const { collocates } = await fresh();
		const { fetcher } = responder(null, { ok: false, status: 404 });
		// This message is read by two people and has to serve both. A visitor who
		// followed a stale link needs to know the record is not in this build;
		// someone who has just cloned the repository needs the build command.
		// Tidying either half away removes the only thing that makes the failure
		// actionable for one of them.
		await expect(collocates(fetcher)).rejects.toThrow(
			/No data file at lexical\/collocates\.json \(404\)/
		);
		await expect(collocates(fetcher)).rejects.toThrow(/not part of this build/);
		await expect(collocates(fetcher)).rejects.toThrow(
			/run the pipeline and scripts\/export_web\.py/
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
			annualPayload({ corpus: { speeches: [12, 14], words: [900], meetings: [3, 4] } })
		);
		// Silently, a short array plots as a truncated line rather than an error,
		// so the misalignment has to be refused here and it has to say which
		// field is short.
		await expect(annual(fetcher)).rejects.toThrow(/corpus\.words must align with periods/);
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

	/**
	 * The smallest usage payload the boundary accepts, so that each refusal below
	 * fails for the one reason it is about rather than for a missing key.
	 */
	const usagePayload = (overrides: Record<string, unknown> = {}) => ({
		meta,
		model: { id: 'chatgpt-5.6-luna-2026-08-01', prompt_sha256: 'a'.repeat(64) },
		prompt: 'Read the occurrence and say what it refers to.',
		referents: [{ id: 'rwanda_1994' }],
		actors: [{ country_org: 'Rwanda' }],
		minimum_occurrences: 20,
		matrix: [],
		position_by_actor: [],
		diffusion: { milestones: ['mention'], referents: [] },
		comparison: { state: 'none', model: '', overlap: 0, contested_any: 0, fields: [] },
		gold: { state: 'not_started' },
		...overrides
	});

	const selfHostedModel = () => ({
		id: 'Qwen/Qwen3.8-27B',
		prompt_sha256: 'a'.repeat(64),
		runtime: {
			route: 'openai-compatible-responses',
			served_model: 'Qwen/Qwen3.8-27B',
			model_revision: '1'.repeat(40),
			quantization: 'none',
			vllm_version: '0.28.0',
			environments: { annotator: 'locked+llm-client-overlay', server: 'vllm' },
			hardware: { gpu_model: 'NVIDIA H100 80GB HBM3', gpu_count: 1 },
			serving: {
				max_model_len: 65536,
				reasoning_parser: 'qwen3',
				tensor_parallel_size: 1,
				prefix_caching: true,
				speculative_decoding: null,
				moe_backend: null
			},
			reasoning: {
				parameter: 'reasoning_effort',
				value: 'xhigh',
				location: 'chat_template_kwargs'
			},
			sampling: { temperature: 0, top_p: 1 },
			max_output_tokens: 65536
		}
	});

	const occurrence = (extra: Record<string, unknown>) => ({
		meta,
		occurrences: [
			{
				id: 'UNSC_2014_SPV.7000_spch0001#1',
				evidence_valid: false,
				evidence_quote: '',
				contested: [],
				alt: null,
				...extra
			}
		]
	});

	it('refuses a second opinion that says it was not made and reports numbers anyway', async () => {
		const { usage } = await fresh();
		// A whole section of the page appears under `computed` and nothing at all
		// under `none`, so numbers carried here would be numbers nobody ever sees.
		const { fetcher } = responder(
			usagePayload({
				comparison: {
					state: 'none',
					model: '',
					overlap: 12,
					contested_any: 0,
					fields: [{ field: 'speaker_position', n: 12, observed: 1, kappa: null, contested: 0 }]
				}
			})
		);
		await expect(usage(fetcher)).rejects.toThrow(
			/comparison says no second opinion was run and reports 1 agreement rows over 12/
		);
	});

	it('accepts complete self-hosted provenance and refuses an incomplete runtime block', async () => {
		const { usage } = await fresh();
		const valid = responder(usagePayload({ model: selfHostedModel() }));
		await expect(usage(valid.fetcher)).resolves.toMatchObject({
			model: { runtime: { model_revision: '1'.repeat(40) } }
		});

		const { usage: second } = await fresh();
		const model = selfHostedModel();
		model.runtime.model_revision = '';
		const incomplete = responder(usagePayload({ model }));
		await expect(second(incomplete.fetcher)).rejects.toThrow(
			/model_revision must be a non-empty string/
		);
	});

	it('refuses a second opinion that does not name the model it was, and one that contests more than it compared', async () => {
		const { usage } = await fresh();
		const nameless = responder(
			usagePayload({
				comparison: { state: 'computed', model: '  ', overlap: 4, contested_any: 1, fields: [] }
			})
		);
		await expect(usage(nameless.fetcher)).rejects.toThrow(
			/claims a second opinion and does not name the model/
		);

		const { usage: second } = await fresh();
		const impossible = responder(
			usagePayload({
				comparison: {
					state: 'computed',
					model: 'gemini-3-pro-2026-07-15',
					overlap: 4,
					contested_any: 9,
					fields: []
				}
			})
		);
		// A part larger than the whole: the page states the one as a share of the other.
		await expect(second(impossible.fetcher)).rejects.toThrow(
			/contests 9 of 4 compared occurrences/
		);
	});

	it('refuses an occurrence contested on a field that reads back to nothing', async () => {
		const { usageOccurrences } = await fresh();
		const { fetcher } = responder(
			occurrence({ contested: ['tone'], alt: { tone: 'sharper than the published run' } })
		);
		await expect(usageOccurrences(fetcher)).rejects.toThrow(
			/is contested on tone, which is not among the compared fields/
		);
	});

	it('refuses a disagreement with no second reading, and a second reading with no disagreement', async () => {
		const { usageOccurrences } = await fresh();
		const silent = responder(occurrence({ contested: ['speaker_position'], alt: null }));
		await expect(usageOccurrences(silent.fetcher)).rejects.toThrow(
			/is contested on speaker_position and carries no second reading/
		);

		const { usageOccurrences: second } = await fresh();
		const unasked = responder(occurrence({ contested: [], alt: { speaker_position: 'asserts' } }));
		await expect(second(unasked.fetcher)).rejects.toThrow(
			/is contested on nothing, so its second reading must be null and is a reading/
		);

		const { usageOccurrences: third } = await fresh();
		const partial = responder(
			occurrence({ contested: ['speaker_position'], alt: { referent: 'bosnia' } })
		);
		await expect(third(partial.fetcher)).rejects.toThrow(
			/is contested on speaker_position and its second reading says nothing there/
		);
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
		const { meetingOf, occurrenceOf, speechOf } = await fresh();
		expect(meetingOf('SC00232-01-005#3')).toBe('SC00232-01');
		expect(speechOf('SC00232-01-005#3')).toBe('SC00232-01-005');
		expect(occurrenceOf('SC00232-01-005#3')).toBe(3);
	});

	it('leaves an identifier with no occurrence ordinal alone', async () => {
		const { meetingOf, speechOf } = await fresh();
		expect(speechOf('SC00232-01-005')).toBe('SC00232-01-005');
		expect(meetingOf('SC00232-01-005')).toBe('SC00232-01');
	});

	it('returns a meeting basename unchanged when there is no speech ordinal to strip', async () => {
		const { meetingOf } = await fresh();
		// The part number a record carries — the `-01` of `SC00232-01` — looks like
		// a speech ordinal on its own, so this asserts the one case that would make
		// the reader ask for a file that cannot exist.
		expect(meetingOf('SC00232-01#1')).toBe('SC00232-01');
		expect(meetingOf('SC00232-01')).toBe('SC00232-01');
	});

	it('rejects a missing, zero-based, or malformed occurrence ordinal', async () => {
		const { occurrenceOf } = await fresh();
		expect(occurrenceOf('SC00232-01-005')).toBeNull();
		expect(occurrenceOf('SC00232-01-005#0')).toBeNull();
		expect(occurrenceOf('SC00232-01-005#third')).toBeNull();
	});
});
