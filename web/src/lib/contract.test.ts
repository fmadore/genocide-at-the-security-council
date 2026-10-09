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
 * types standing in for hundreds of megabytes of JSON.
 *
 * What it does not do is validate the contract's *contents* against the
 * validators in `data.ts` — a skeleton has no values, so `coverage must be a
 * finite number` has nothing to be finite. Those refusals are exercised against
 * built payloads in `data.test.ts`, which is the right place for them: they are
 * about what the interface may honestly draw, not about what the pipeline
 * emits.
 *
 * What `types.ts` *declares*, as against what `data.ts` requires, is held to
 * the same skeleton field by field in `types.contract.test.ts`.
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
import fixtureScopes from '../../e2e/fixtures/data/scopes.json';

const contract: Record<string, Record<string, unknown>> = payload;

/**
 * The two artefacts fetched by name are contracted through one representative
 * file, because each is written by a single loop: 9,464 documents and 29
 * concordances share one shape apiece, and sampling every one of them to
 * confirm that would slow the export for no extra finding.
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
	it('keeps the root layout scope fixture available to browser tests', () => {
		expect(fixtureScopes.scopes.map((scope) => scope.id)).toEqual(['word', 'vocabulary', 'debate']);
	});

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
			const absent = Object.keys(required).filter(
				(key) => !(key in shape!) && !(`${key}?` in shape!)
			);
			expect(absent, `${sampled} does not carry ${absent.join(', ')}`).toEqual([]);
			const optional = Object.keys(required).filter((key) => `${key}?` in shape!);
			expect(optional, `${sampled} does not always carry ${optional.join(', ')}`).toEqual([]);
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
				.filter(([key]) => key in shape!)
				.filter(([key, kind]) => !WRITTEN_AS[kind]!(shape![key]))
				.map(
					([key, kind]) => `${key} is fetched as ${kind}, written as ${JSON.stringify(shape![key])}`
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
	it('keeps every actor-measure row sufficient flag required', () => {
		const measures = contract['countries/countries.json']!.measures as Record<string, never>;
		const row = (measures['*'] as unknown as { rows: [Record<string, string>] }).rows[0];
		expect(Object.keys(row)).toContain('sufficient');
		expect(Object.keys(row)).not.toContain('sufficient?');
	});

	it('keeps the nullable rates nullable', () => {
		// `speech_rate` is null wherever a speaker is under the minimum, and the
		// whole `?? 0` argument in `$lib/actors` rests on that null surviving the
		// pipeline. If it ever arrives as a plain number the withheld rows become
		// measured zeros and the ranking gains 468 speakers that said nothing.
		const rows = (contract['countries/countries.json']!.measures as Record<string, never>)['*'];
		const row = (rows as unknown as { rows: [Record<string, string>] }).rows[0];
		expect(row.speech_rate).toContain('null');
	});

	it('publishes no measure summed over more than one term', () => {
		// R7. `registers` and `sets` were blocks of measures over families of
		// words: a reader watching the legal line move could not tell which of
		// six words moved it, and `atrocity_core` had to withhold its occurrence
		// count entirely, because summing five overlapping phrases double-counts
		// a speech that uses two. The contract is where their return would show.
		const annual = contract['series/annual.json'];
		expect(annual).not.toHaveProperty('registers');
		expect(annual).not.toHaveProperty('sets');
		expect(contract['series/monthly.json']).not.toHaveProperty('registers');
		expect(contract['series/monthly.json']).not.toHaveProperty('sets');
	});
});

/* --- The browser fixtures, held to the same skeleton ---------------------------
   The Playwright suite runs the real routes over hand-cut files in
   `e2e/fixtures/data`. A fixture that carries a field the pipeline no longer
   writes, or lacks one it always writes, tests a page against a payload that
   cannot exist — and a feature drawn from the missing field is never drawn in a
   test at all. So each fixture is compared with the committed contract, in both
   directions, with three allowances a hand-cut file needs and a built one does
   not: it may carry fewer members of a map keyed by the data (three countries
   rather than eight), its provenance block may be a placeholder, and a leaf the
   contract only ever saw as null may hold any value. */

type Skeleton = string | Skeleton[] | { [key: string]: Skeleton };

/** A skeleton key and whether a `?` marks it absent from some members. */
const fieldOf = (key: string): [string, boolean] =>
	key.endsWith('?') ? [key.slice(0, -1), true] : [key, false];

/**
 * Whether a contract object is a map keyed by the data: the opaque `*`, or
 * several members that are objects of one shape (terms, countries, frames,
 * widths). A fixture may carry any subset of such a map.
 */
function keyedByData(shape: { [key: string]: Skeleton }): boolean {
	if ('*' in shape || '*?' in shape) return true;
	const members = Object.values(shape);
	if (members.length < 2) return false;
	const first = JSON.stringify(members[0]);
	return members.every(
		(member) =>
			typeof member === 'object' && !Array.isArray(member) && JSON.stringify(member) === first
	);
}

/** Whether a value is one the contract's leaf was written as. */
function leafHolds(written: string, value: unknown): boolean {
	const kinds = new Set(written.split('|'));
	// The sample held nothing but nulls here, so it says nothing about the type.
	if (kinds.size === 1 && kinds.has('null')) return true;
	if (value === null) return kinds.has('null');
	if (typeof value === 'number') {
		return kinds.has('float') || (Number.isInteger(value) && kinds.has('int'));
	}
	if (typeof value === 'string') return kinds.has('str');
	if (typeof value === 'boolean') return kinds.has('bool');
	return kinds.has('object');
}

/** Every way a fixture differs from the skeleton of what the pipeline writes. */
function fixtureDrift(written: Skeleton, found: unknown, path = '', inMeta = false): string[] {
	const where = path || '(root)';
	if (typeof written === 'string') {
		return leafHolds(written, typeof found === 'object' && found !== null ? {} : found)
			? []
			: [`${where}: written as ${written}, the fixture holds ${JSON.stringify(found)}`];
	}
	if (Array.isArray(written)) {
		if (!Array.isArray(found)) return [`${where}: written as an array`];
		const element = written[0];
		if (element === undefined) return [];
		return found.flatMap((item, index) => fixtureDrift(element, item, `${path}[${index}]`, inMeta));
	}
	if (typeof found !== 'object' || found === null || Array.isArray(found)) {
		return [`${where}: written as an object`];
	}
	const fixture = found as Record<string, unknown>;
	// A map the sample held no member of says nothing about the members.
	if (!Object.keys(written).length) return [];
	const fields = new Map(
		Object.entries(written).map(([key, value]) => {
			const [name, optional] = fieldOf(key);
			return [name, { optional, value }];
		})
	);
	if (keyedByData(written)) {
		const sibling = [...fields.values()][0]!.value;
		return Object.entries(fixture).flatMap(([key, value]) =>
			fixtureDrift(fields.get(key)?.value ?? sibling, value, `${path}.${key}`, inMeta)
		);
	}
	const differences: string[] = [];
	for (const [key, value] of Object.entries(fixture)) {
		const field = fields.get(key);
		if (!field) differences.push(`${path}.${key}: not written by the pipeline`);
		else
			differences.push(
				...fixtureDrift(field.value, value, `${path}.${key}`, inMeta || key === 'meta')
			);
	}
	if (!inMeta) {
		for (const [key, { optional }] of fields) {
			if (!optional && !(key in fixture))
				differences.push(`${path}.${key}: missing from the fixture`);
		}
	}
	return differences;
}

const FIXTURES = import.meta.glob<unknown>('../../e2e/fixtures/data/**/*.json', {
	eager: true,
	import: 'default'
});

/** The fixture path under `data/`, and the contracted artefact it stands for. */
const fixtures = Object.entries(FIXTURES).map(([file, data]) => {
	const path = file.replace('../../e2e/fixtures/data/', '');
	const artefact = Object.keys(contract).find(
		(name) => name === path || (SAMPLED['kwic/*.json']!(path) && SAMPLED['kwic/*.json']!(name))
	);
	return { path, artefact, data };
});

/**
 * The speech file is stored gzipped, as the payload's are, so it cannot be
 * imported as JSON. `node:fs` is reached by a dynamic import of a computed
 * name: the test runs in Node, and the browser types this file is checked
 * against never see it.
 */
async function speechFixture(): Promise<unknown> {
	const fs = (await import(/* @vite-ignore */ 'node:fs' as string)) as {
		readFileSync: (path: URL) => Uint8Array<ArrayBuffer>;
	};
	const bytes = fs.readFileSync(
		new URL('../../e2e/fixtures/data/speeches/SC07000-01.json.gz', import.meta.url)
	);
	const text = await new Response(
		new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))
	).text();
	return JSON.parse(text) as unknown;
}

describe('the browser fixtures against what the pipeline writes', () => {
	it('contracts every fixture but the semantic map, which the pipeline does not track', () => {
		expect(fixtures.filter((entry) => !entry.artefact).map((entry) => entry.path)).toEqual([]);
	});

	it.each(fixtures.filter((entry) => entry.artefact).map((entry) => [entry.path, entry]))(
		'%s carries the shape the pipeline writes',
		(_, entry) => {
			const drift = fixtureDrift(contract[entry.artefact!] as Skeleton, entry.data);
			expect(drift, drift.join('\n')).toEqual([]);
		}
	);

	it('the speech fixture carries the shape of a speech file', async () => {
		const sample = Object.keys(contract).find(SAMPLED['speeches/*.json']!)!;
		const drift = fixtureDrift(contract[sample] as Skeleton, await speechFixture());
		expect(drift, drift.join('\n')).toEqual([]);
	});

	it('reports what a drifted fixture lacks, adds or changes', () => {
		const written: Skeleton = {
			meta: { script: 'str', git_commit: 'str' },
			periods: ['int'],
			terms: { '*': { rate: ['float|null'], kind: 'str' } },
			note: 'null'
		};
		expect(
			fixtureDrift(written, { meta: { script: 's' }, periods: [1992], terms: {}, note: 3 })
		).toEqual([]);
		expect(
			fixtureDrift(written, {
				meta: { script: 's', extra: 1 },
				periods: [1992.5],
				terms: { genocide: { rate: [0.1, 'x'] } },
				invented: true
			})
		).toEqual([
			'.meta.extra: not written by the pipeline',
			'.periods[0]: written as int, the fixture holds 1992.5',
			'.terms.genocide.rate[1]: written as float|null, the fixture holds "x"',
			'.terms.genocide.kind: missing from the fixture',
			'.invented: not written by the pipeline',
			'.note: missing from the fixture'
		]);
	});
});
