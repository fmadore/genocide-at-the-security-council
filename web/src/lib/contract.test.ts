/**
 * The half of the artefact contract that Python cannot see.
 *
 * `scripts/lib/contract.py` reduces the built payload to its shape and
 * `export_web.py` refuses to publish one that has drifted from
 * `tests/contract/payload.json`. That catches a field the pipeline stopped
 * writing. It cannot catch the opposite mistake — a field the *dashboard* has
 * started requiring that the pipeline never wrote — because nothing on the
 * Python side knows what `data.ts` asks for.
 *
 * This is that check, and it runs in CI with no data present, because the
 * committed contract is the shape rather than the payload: 32 kB of keys and
 * types standing in for 491 MB of JSON.
 *
 * What it does not do is validate the contract's *contents* against the
 * validators in `data.ts` — a skeleton has no values, so `coverage must be a
 * finite number` has nothing to be finite. Those refusals are exercised against
 * built payloads in `data.test.ts`, which is the right place for them: they are
 * about what the interface may honestly draw, not about what the pipeline
 * emits.
 */

import { describe, expect, it } from 'vitest';
import { REQUIRED } from './data';
/**
 * The committed shape, imported rather than read off disk.
 *
 * `node:fs` would work under vitest and fail `svelte-check`, which types this
 * file against the browser configuration the rest of `src/` is written for —
 * and adding Node's types to that configuration to satisfy one test would give
 * every route file a `process` and a `Buffer` it has no business seeing. A JSON
 * import needs neither: `resolveJsonModule` is already on, and nothing in
 * `src/routes` imports this, so the 32 kB never reaches a bundle.
 */
import payload from '../../../tests/contract/payload.json';

const contract: Record<string, Record<string, unknown>> = payload;

/**
 * The two artefacts fetched by name are contracted through one representative
 * file, because each is written by a single loop: 6,595 documents and 22
 * concordances share one shape apiece, and sampling 425 MB to confirm that
 * twice over would slow the export for no extra finding.
 */
const SAMPLED: Record<string, (path: string) => boolean> = {
	'kwic/*.json': (path) => path.startsWith('kwic/') && path !== 'kwic/index.json',
	'speeches/*.json': (path) => path.startsWith('speeches/')
};

const resolve = (artefact: string): string | undefined => {
	if (artefact in contract) return artefact;
	const matches = SAMPLED[artefact];
	return matches ? Object.keys(contract).find(matches) : undefined;
};

describe('what the dashboard requires against what the pipeline writes', () => {
	it.each(Object.keys(REQUIRED))('%s has a declared shape', (artefact) => {
		// A new accessor with no entry in the contract is the gap this whole
		// mechanism exists to close, so it fails here rather than at a reader's
		// browser. Add the artefact to `contract.TRACKED` and re-run
		// `export_web.py --update-contract`.
		expect(resolve(artefact), `no skeleton in tests/contract/payload.json`).toBeDefined();
	});

	it.each(Object.entries(REQUIRED))(
		'%s carries every field it is fetched for',
		(artefact, required) => {
			const sampled = resolve(artefact);
			if (!sampled) return; // Reported by the test above; not worth failing twice.
			const shape = contract[sampled];
			const absent = Object.keys(required).filter((key) => !(key in shape));
			expect(absent, `${sampled} does not carry ${absent.join(', ')}`).toEqual([]);
		}
	);

	/**
	 * How each kind `data.ts` demands appears in the committed skeleton, which
	 * writes a scalar as the name of its Python type and a container as itself.
	 *
	 * Presence alone was the weaker half of this check: the dashboard can require
	 * `minimum_speeches` to be a finite number while the pipeline writes it as a
	 * string, and nothing in either direction would notice until the gate that
	 * depends on it silently stopped being a gate.
	 */
	const WRITTEN_AS: Record<string, (value: unknown) => boolean> = {
		object: (value) => typeof value === 'object' && value !== null && !Array.isArray(value),
		array: Array.isArray,
		number: (value) => value === 'int' || value === 'float',
		string: (value) => value === 'str'
	};

	it.each(Object.entries(REQUIRED))(
		'%s is fetched for the kinds it is written as',
		(artefact, required) => {
			const sampled = resolve(artefact);
			if (!sampled) return;
			const shape = contract[sampled];
			const mismatched = Object.entries(required as Record<string, string>)
				.filter(([key]) => key in shape)
				.filter(([key, kind]) => !WRITTEN_AS[kind](shape[key]))
				.map(
					([key, kind]) => `${key} is fetched as ${kind}, written as ${JSON.stringify(shape[key])}`
				);
			expect(mismatched, mismatched.join('; ')).toEqual([]);
		}
	);

	it('contracts nothing the dashboard does not fetch', () => {
		// The other direction, so the two lists cannot quietly diverge: an
		// artefact tracked in Python but read by nobody is either a fetch that was
		// removed and left behind, or one that was never wired up.
		const claimed = Object.keys(contract).filter(
			(path) => !(path in REQUIRED) && !Object.values(SAMPLED).some((matches) => matches(path))
		);
		expect(claimed, `tracked in contract.py but fetched by nothing: ${claimed.join(', ')}`).toEqual(
			[]
		);
	});
});

describe('the shape of the blocks a figure would silently mis-draw', () => {
	it('keeps the nullable rates nullable', () => {
		// `speech_rate` is null wherever a speaker is under the minimum, and the
		// whole `?? 0` argument in `$lib/actors` rests on that null surviving the
		// pipeline. If it ever arrives as a plain number the withheld rows become
		// measured zeros and the ranking gains 468 speakers that said nothing.
		const rows = (contract['countries/countries.json'].measures as Record<string, never>)['*'];
		const row = (rows as unknown as { rows: [Record<string, string>] }).rows[0];
		expect(row.speech_rate).toContain('null');
	});

	it('keeps a set free of the occurrence count it must not have', () => {
		// `atrocity_core` is a union of overlapping terms, so summing occurrences
		// would double-count a speech that used two of them. `04_series.py`
		// withholds the figure; `$lib/heatmap` and `$lib/actors` both detect the
		// absence rather than reading it through `?? 0`. A set that grew an
		// `occurrences` array would make both of them start publishing a wrong
		// number, and neither would raise anything.
		const sets = contract['series/annual.json'].sets as Record<string, Record<string, unknown>>;
		expect(Object.keys(sets['*'])).not.toContain('occurrences');
		expect(Object.keys(sets['*'])).not.toContain('token_rate');
	});
});
