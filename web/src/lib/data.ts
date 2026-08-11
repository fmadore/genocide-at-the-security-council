/**
 * Fetching the pipeline's artefacts.
 *
 * Everything is a static JSON file under `static/data/`, so there is no API and
 * no server. What there is instead is a cache: the concordance for one term is
 * up to 10 MB, and a reader who moves between views should not pay for it
 * twice. It has a ceiling — see `KEEP` — because the two artefacts fetched by
 * name have no natural one, and a session that opened every term used to hold
 * all of them.
 */

import { base } from '$app/paths';
import type {
	AnnualSeries,
	Breakdowns,
	ChangePoints,
	Collocates,
	Countries,
	Events,
	Keyness,
	KwicFile,
	KwicIndex,
	Meeting,
	MeetingIndex,
	MonthlySeries,
	Network,
	SlicedCollocates,
	SpeakerKeyness
} from './types';

const cache = new Map<string, Promise<unknown>>();

type JsonRecord = Record<string, unknown>;
type Validator = (payload: JsonRecord, path: string) => void;

/**
 * The four kinds the boundary can check without knowing what an artefact means.
 *
 * `REQUIRED` names a kind per key, and `json()` enforces it, which is why the
 * validators below hold no `must be an array` lines: a structural requirement
 * stated twice is two statements that can disagree, and the one that loses is
 * always the one further from the fetch.
 *
 * `number` is `Number.isFinite` rather than `typeof === 'number'`: NaN and the
 * infinities are all of type number, and a coverage that failed to compute
 * upstream would otherwise pass the boundary and reach a figure as "NaN%".
 */
type Kind = 'object' | 'array' | 'number' | 'string';
type Shape = Readonly<Record<string, Kind>>;

const isRecord = (value: unknown): value is JsonRecord =>
	typeof value === 'object' && value !== null && !Array.isArray(value);

/** The test for each kind, and the sentence a payload that fails it earns. */
const KINDS: Record<Kind, { holds: (value: unknown) => boolean; must: string }> = {
	object: { holds: isRecord, must: 'must be an object' },
	array: { holds: Array.isArray, must: 'must be an array' },
	number: { holds: (value) => Number.isFinite(value), must: 'must be a finite number' },
	string: { holds: (value) => typeof value === 'string', must: 'must be a string' }
};

/**
 * Read a top-level key the shape has already vouched for.
 *
 * Not a check: `json()` has run every entry in the artefact's `REQUIRED` shape
 * over the record before any validator sees it, so re-testing the kind here
 * would be the duplication this arrangement removed. Nested keys are a
 * different matter — `REQUIRED` describes the top level only — and those still
 * go through `requireRecord`/`requireArray`.
 */
const arrayAt = (record: JsonRecord, key: string) => record[key] as unknown[];
const recordAt = (record: JsonRecord, key: string) => record[key] as JsonRecord;

function requireRecord(record: JsonRecord, key: string, path: string): JsonRecord {
	const value = record[key];
	if (!isRecord(value)) throw new Error(`${path}.${key} must be an object.`);
	return value;
}

function requireArray(record: JsonRecord, key: string, path: string): unknown[] {
	const value = record[key];
	if (!Array.isArray(value)) throw new Error(`${path}.${key} must be an array.`);
	return value;
}

/**
 * Every artefact carries a `meta`, and every one of them must say what wrote it
 * and when. Run for all of them from `json()` rather than as the first line of
 * fifteen validators: provenance is the one requirement this project does not
 * let an artefact opt out of.
 */
function validateMeta(record: JsonRecord, path: string): void {
	const meta = recordAt(record, 'meta');
	if (typeof meta.script !== 'string' || typeof meta.generated !== 'string') {
		throw new Error(`${path}.meta must identify its script and generation time.`);
	}
}

const validateAnnual: Validator = (record, path) => {
	const periods = arrayAt(record, 'periods');
	const corpus = recordAt(record, 'corpus');
	for (const field of ['speeches', 'tokens', 'meetings']) {
		if (requireArray(corpus, field, `${path}.corpus`).length !== periods.length) {
			throw new Error(`${path}.corpus.${field} must align with periods.`);
		}
	}
};

const validateMonthly: Validator = (record, path) => {
	validateAnnual(record, path);
	const periods = arrayAt(record, 'periods');
	const years = arrayAt(record, 'years');
	const sufficient = arrayAt(record, 'sufficient');
	// The grid must be complete. The view indexes a cell by (year, month) and a
	// ragged payload would not fail — it would draw January's figure in
	// February's square for every year after the gap.
	if (periods.length !== years.length * 12) {
		throw new Error(
			`${path} must hold a complete grid: ${years.length} years is ${years.length * 12} ` +
				`months, and it carries ${periods.length}.`
		);
	}
	if (sufficient.length !== periods.length) {
		throw new Error(`${path}.sufficient must align with periods.`);
	}
	requireRecord(recordAt(record, 'month_of_year'), 'measures', `${path}.month_of_year`);
	// Substantive rather than structural, and the same check `validateCountries`
	// makes: the figure draws exactly the cells that claim to be sufficient, so a
	// sufficient cell with no rate would reach the grid as a null — and on a
	// heatmap a null is drawn in the colour a measured zero has.
	for (const kind of ['terms', 'registers', 'sets']) {
		for (const [name, measure] of Object.entries(recordAt(record, kind))) {
			if (!isRecord(measure)) throw new Error(`${path}.${kind}.${name} must be an object.`);
			const rates = requireArray(measure, 'speech_rate', `${path}.${kind}.${name}`);
			if (rates.length !== periods.length) {
				throw new Error(`${path}.${kind}.${name}.speech_rate must align with periods.`);
			}
			const wrong = rates.findIndex((rate, index) => sufficient[index] && !Number.isFinite(rate));
			if (wrong >= 0) {
				throw new Error(
					`${path}.${kind}.${name} claims ${periods[wrong]} is sufficient without a rate.`
				);
			}
		}
	}
};

const validateChangePoints: Validator = (record, path) => {
	requireRecord(recordAt(record, 'inference'), 'series', `${path}.inference`);
};

const validateEvents: Validator = (record, path) => {
	for (const [index, event] of arrayAt(record, 'events').entries()) {
		if (
			!isRecord(event) ||
			typeof event.date !== 'string' ||
			typeof event.source_url !== 'string'
		) {
			throw new Error(`${path}.events[${index}] lacks a date or primary-source URL.`);
		}
	}
};

const validateCountries: Validator = (record, path) => {
	// The membership block is drawn as a composition: five bands that fill a
	// speaker's own denominator. If they do not sum to it, the bar comes up short
	// and the missing speeches are drawn as background — a gap that reads as a
	// sixth, unnamed status. 11 reconciles this upstream; the interface refuses a
	// payload it cannot draw honestly rather than trusting that it ran.
	const standing = recordAt(record, 'standing');
	const groups = requireArray(standing, 'groups', `${path}.standing`);
	requireArray(standing, 'seated_groups', `${path}.standing`);
	for (const [index, row] of requireArray(standing, 'rows', `${path}.standing`).entries()) {
		if (!isRecord(row)) throw new Error(`${path}.standing.rows[${index}] must be an object.`);
		const counts = row.groups;
		if (!isRecord(counts)) {
			throw new Error(`${path}.standing.rows[${index}] must carry a count for every group.`);
		}
		const total = groups.reduce<number>(
			(sum, group) => sum + Number(counts[String(group)] ?? 0),
			0
		);
		if (total !== row.held) {
			throw new Error(
				`${path}.standing.rows[${index}] (${row.country_org}, ${row.period}) has group ` +
					`counts summing to ${total} against a denominator of ${row.held}.`
			);
		}
	}
	// Substantive, not structural: the interface draws exactly the rows that
	// claim to be sufficient, so a sufficient row without a rate would reach a
	// chart as a null and be drawn as a zero.
	for (const [name, measure] of Object.entries(recordAt(record, 'measures'))) {
		if (!isRecord(measure)) throw new Error(`${path}.measures.${name} must be an object.`);
		for (const [index, row] of requireArray(
			measure,
			'rows',
			`${path}.measures.${name}`
		).entries()) {
			if (isRecord(row) && row.sufficient === true && !Number.isFinite(row.speech_rate)) {
				throw new Error(
					`${path}.measures.${name}.rows[${index}] claims to be sufficient without a rate.`
				);
			}
		}
	}
};

const validateSpeakerKeyness: Validator = (record, path) => {
	// Substantive rather than structural, and the same check `validateCountries`
	// makes for a different reason: the view draws exactly the rows that claim to
	// be sufficient, so a sufficient row with no table would reach the figure as a
	// null and be rendered as an empty ranking rather than as a refusal.
	for (const [index, row] of arrayAt(record, 'speakers').entries()) {
		if (!isRecord(row)) throw new Error(`${path}.speakers[${index}] must be an object.`);
		if (!Number.isFinite(row.coverage)) {
			throw new Error(`${path}.speakers[${index}].coverage must be a finite number.`);
		}
		if (!Array.isArray(row.withheld_because)) {
			throw new Error(`${path}.speakers[${index}] must say why it was withheld, or say nothing.`);
		}
		if (row.sufficient === true && !Array.isArray(row.keywords)) {
			throw new Error(`${path}.speakers[${index}] claims to be sufficient without a table.`);
		}
		if (row.sufficient === false && row.keywords !== null) {
			throw new Error(`${path}.speakers[${index}] is withheld but carries a table.`);
		}
	}
};

/**
 * How many of the two by-name families a session may hold at once.
 *
 * The cache exists so a reader moving between views does not fetch and parse a
 * 10 MB concordance twice, and for the dozen or so artefacts a route needs to
 * render at all that property is worth keeping for the whole session: they are
 * small, and every one of them is wanted again the moment the reader goes back.
 *
 * The two families fetched by name are the ones with no ceiling of their own —
 * 22 concordances and 6,595 speech files — and a reader who opens every term
 * held all of them at once, in the parsed form, which is several times the
 * transferred size. Those get a least-recently-used bound instead: enough to
 * make going back to the previous term or the previous speech free, not enough
 * to accumulate the corpus in a tab.
 */
const KEEP: { matches: (path: string) => boolean; keep: number }[] = [
	{ matches: (path) => path.startsWith('kwic/') && path !== 'kwic/index.json', keep: 3 },
	{ matches: (path) => path.startsWith('speeches/'), keep: 8 }
];

/** Paths in the order they were last asked for, oldest first. Bounded families only. */
const recent = new Map<string, string>();

function evict(path: string, url: string): void {
	const family = KEEP.find((f) => f.matches(path));
	if (!family) return;
	// Re-inserting moves the key to the end of a Map's iteration order, which is
	// what makes this least-*recently-used* rather than first-in-first-out: a
	// reader returning to a term keeps it.
	recent.delete(url);
	recent.set(url, path);
	const mine = [...recent].filter(([, held]) => family.matches(held));
	for (const [stale] of mine.slice(0, Math.max(0, mine.length - family.keep))) {
		recent.delete(stale);
		cache.delete(stale);
	}
}

/** Fetch and cache a JSON payload, keyed on its path. */
export function json<T>(
	path: string,
	fetcher: typeof fetch = fetch,
	shape: Shape = { meta: 'object' },
	validate?: Validator
): Promise<T> {
	const url = `${base}/data/${path}`;
	evict(path, url);
	if (!cache.has(url)) {
		const request = fetcher(url)
			.then((response) => {
				if (!response.ok) {
					// Two readers, one sentence. A visitor who followed a stale link
					// needs to know the file is not there and that nothing they did
					// caused it; whoever is building the site locally needs the
					// second half, which is why the missing path is named first.
					throw new Error(
						`No data file at ${path} (${response.status}). If you followed a link here, ` +
							`the record it points to is not part of this build. If you are running the ` +
							`site locally, run the pipeline and scripts/export_web.py to build ` +
							`web/static/data/.`
					);
				}
				return response.json() as Promise<unknown>;
			})
			.then((payload) => {
				if (!payload || typeof payload !== 'object') {
					throw new Error(`${path} is not a JSON object.`);
				}
				const record = payload as Record<string, unknown>;
				const keys = Object.keys(shape);
				// Absence first, and all of it at once: a reader repairing an
				// artefact by hand should not have to reload three times to find
				// out what else is not there.
				const missing = keys.filter((key) => !(key in record));
				if (missing.length) {
					throw new Error(`${path} is missing required field(s): ${missing.join(', ')}.`);
				}
				// Then the kinds. Present-but-wrong is a different failure from
				// absent — a field renamed upstream reads as missing, a field whose
				// type changed reads as this — so it gets its own sentence.
				const wrong = keys
					.filter((key) => !KINDS[shape[key]].holds(record[key]))
					.map((key) => `${path}.${key} ${KINDS[shape[key]].must}.`);
				if (wrong.length) throw new Error(wrong.join(' '));
				validateMeta(record, path);
				validate?.(record, path);
				return payload as T;
			})
			.catch((error) => {
				cache.delete(url);
				recent.delete(url);
				throw error;
			});
		cache.set(url, request);
	}
	return cache.get(url) as Promise<T>;
}

/**
 * What each artefact must carry, keyed on its path under `static/data/`, and of
 * what kind.
 *
 * This is the boundary's whole structural requirement: `json()` refuses a
 * payload that is missing a key or carries it as the wrong kind, and the
 * validators below start from a record all of that is already true of. Adding a
 * key here is the entire edit needed to make the dashboard require it.
 *
 * Exported because it is one half of a contract whose other half is written in
 * Python, and until this was a value rather than an argument list nothing could
 * compare the two. `contract.test.ts` checks every entry below against
 * `tests/contract/payload.json` — the committed shape of what the pipeline
 * actually writes — so a field required here that the pipeline does not produce
 * fails a test instead of blanking a figure.
 *
 * The two artefacts fetched by name (`kwic/<term>`, `speeches/<basename>`) are
 * keyed on the pattern their callers build, and the test resolves them against
 * the representative file the contract samples.
 */
export const REQUIRED = {
	'series/annual.json': { meta: 'object', periods: 'array', corpus: 'object', terms: 'object' },
	'series/quarterly.json': { meta: 'object', periods: 'array', corpus: 'object', terms: 'object' },
	'series/monthly.json': {
		meta: 'object',
		periods: 'array',
		corpus: 'object',
		terms: 'object',
		registers: 'object',
		sets: 'object',
		sufficient: 'array',
		years: 'array',
		minimum_speeches: 'number',
		month_of_year: 'object'
	},
	'series/breakdowns.json': { meta: 'object', measures: 'object' },
	'series/change_points.json': { meta: 'object', series: 'object', inference: 'object' },
	'series/events.json': { meta: 'object', events: 'array' },
	'lexical/collocates.json': { meta: 'object' },
	'lexical/collocates_sliced.json': { meta: 'object' },
	'lexical/keyness.json': {
		meta: 'object',
		keywords: 'array',
		stability: 'object',
		coverage: 'number'
	},
	'lexical/network.json': {
		meta: 'object',
		terms: 'array',
		edges: 'array',
		by_period: 'object'
	},
	'countries/countries.json': {
		meta: 'object',
		countries: 'array',
		periods: 'array',
		measures: 'object',
		standing: 'object',
		minimum_speeches: 'number',
		iso3_collisions: 'object'
	},
	'countries/speaker_keyness.json': {
		meta: 'object',
		speakers: 'array',
		minimum_pairs: 'number',
		minimum_coverage: 'number'
	},
	'kwic/index.json': { meta: 'object', terms: 'array' },
	'kwic/*.json': { meta: 'object', term: 'string', lines: 'array' },
	'meetings.json': { meta: 'object', meetings: 'array' },
	'speeches/*.json': { meta: 'object', speeches: 'array' }
} as const satisfies Record<string, Shape>;

export type Artefact = keyof typeof REQUIRED;

/** An accessor for a fixed artefact: its path, what it must carry, and its validator. */
const at =
	<T>(path: Artefact, validate?: Validator) =>
	(f?: typeof fetch) =>
		json<T>(path, f, REQUIRED[path], validate);

export const annual = at<AnnualSeries>('series/annual.json', validateAnnual);
export const quarterly = at<AnnualSeries>('series/quarterly.json', validateAnnual);
export const monthly = at<MonthlySeries>('series/monthly.json', validateMonthly);
export const breakdowns = at<Breakdowns>('series/breakdowns.json');
export const changePoints = at<ChangePoints>('series/change_points.json', validateChangePoints);
export const events = at<Events>('series/events.json', validateEvents);

export const collocates = at<Collocates>('lexical/collocates.json');
export const slicedCollocates = at<SlicedCollocates>('lexical/collocates_sliced.json');
export const keyness = at<Keyness>('lexical/keyness.json');
export const network = at<Network>('lexical/network.json');

export const countries = at<Countries>('countries/countries.json', validateCountries);
export const speakerKeyness = at<SpeakerKeyness>(
	'countries/speaker_keyness.json',
	validateSpeakerKeyness
);

export const kwicIndex = at<KwicIndex>('kwic/index.json');
export const meetingIndex = at<MeetingIndex>('meetings.json');

/* Fetched by name rather than fixed, so the path is built per call. */
export const kwic = (term: string, f?: typeof fetch) =>
	json<KwicFile>(`kwic/${encodeURIComponent(term)}.json`, f, REQUIRED['kwic/*.json']);

export const meeting = (basename: string, f?: typeof fetch) =>
	json<Meeting>(`speeches/${encodeURIComponent(basename)}.json`, f, REQUIRED['speeches/*.json']);

/** `UNSC_2015_SPV.7481_spch0007#3` → the meeting file that speech lives in. */
export function meetingOf(lineId: string): string {
	const speech = lineId.split('#')[0];
	return speech.replace(/_spch\d+$/, '');
}

/** `UNSC_2015_SPV.7481_spch0007#3` → `UNSC_2015_SPV.7481_spch0007`. */
export function speechOf(lineId: string): string {
	return lineId.split('#')[0];
}
