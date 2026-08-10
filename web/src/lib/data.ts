/**
 * Fetching the pipeline's artefacts.
 *
 * Everything is a static JSON file under `static/data/`, so there is no API and
 * no server. What there is instead is a cache: the concordance for one term is
 * up to 10 MB, and a reader who moves between views should not pay for it
 * twice.
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
	Network,
	SlicedCollocates,
	SpeakerKeyness
} from './types';

const cache = new Map<string, Promise<unknown>>();

type JsonRecord = Record<string, unknown>;
type Validator = (payload: JsonRecord, path: string) => void;

const isRecord = (value: unknown): value is JsonRecord =>
	typeof value === 'object' && value !== null && !Array.isArray(value);

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

function validateMeta(record: JsonRecord, path: string): void {
	const meta = requireRecord(record, 'meta', path);
	if (typeof meta.script !== 'string' || typeof meta.generated !== 'string') {
		throw new Error(`${path}.meta must identify its script and generation time.`);
	}
}

const validateAnnual: Validator = (record, path) => {
	validateMeta(record, path);
	const periods = requireArray(record, 'periods', path);
	const corpus = requireRecord(record, 'corpus', path);
	for (const field of ['speeches', 'tokens', 'meetings']) {
		if (requireArray(corpus, field, `${path}.corpus`).length !== periods.length) {
			throw new Error(`${path}.corpus.${field} must align with periods.`);
		}
	}
	requireRecord(record, 'terms', path);
};

const validateBreakdowns: Validator = (record, path) => {
	validateMeta(record, path);
	requireRecord(record, 'measures', path);
};

const validateChangePoints: Validator = (record, path) => {
	validateMeta(record, path);
	requireRecord(record, 'series', path);
	const inference = requireRecord(record, 'inference', path);
	requireRecord(inference, 'series', `${path}.inference`);
};

const validateEvents: Validator = (record, path) => {
	validateMeta(record, path);
	for (const [index, event] of requireArray(record, 'events', path).entries()) {
		if (
			!isRecord(event) ||
			typeof event.date !== 'string' ||
			typeof event.source_url !== 'string'
		) {
			throw new Error(`${path}.events[${index}] lacks a date or primary-source URL.`);
		}
	}
};

const validateLexical: Validator = (record, path) => validateMeta(record, path);

const validateKeyness: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'keywords', path);
	requireRecord(record, 'stability', path);
	// `Number.isFinite`, not `typeof === 'number'`: NaN and the infinities are all
	// of type number, and a coverage that failed to compute upstream would have
	// passed the boundary and reached the figure as "NaN%". The point of
	// validating here is to refuse a payload the interface cannot honestly draw.
	if (!Number.isFinite(record.coverage)) {
		throw new Error(`${path}.coverage must be a finite number.`);
	}
};

const validateNetwork: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'terms', path);
	requireArray(record, 'edges', path);
	requireRecord(record, 'by_period', path);
};

const validateCountries: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'countries', path);
	requireArray(record, 'periods', path);
	requireRecord(record, 'measures', path);
	// The two blocks a consumer must read before drawing anything. Absent, a
	// choropleth keyed on ISO3 paints Zaire under the DRC without saying so, and
	// the minimum-sample gate silently becomes no gate at all.
	requireRecord(record, 'iso3_collisions', path);
	if (!Number.isFinite(record.minimum_speeches)) {
		throw new Error(`${path}.minimum_speeches must be a finite number.`);
	}
	// Substantive, not structural: the interface draws exactly the rows that
	// claim to be sufficient, so a sufficient row without a rate would reach a
	// chart as a null and be drawn as a zero.
	for (const [name, measure] of Object.entries(requireRecord(record, 'measures', path))) {
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
	validateMeta(record, path);
	if (!Number.isFinite(record.minimum_pairs) || !Number.isFinite(record.minimum_coverage)) {
		throw new Error(`${path} must declare both minimums as finite numbers.`);
	}
	// Substantive rather than structural, and the same check `validateCountries`
	// makes for a different reason: the view draws exactly the rows that claim to
	// be sufficient, so a sufficient row with no table would reach the figure as a
	// null and be rendered as an empty ranking rather than as a refusal.
	for (const [index, row] of requireArray(record, 'speakers', path).entries()) {
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

const validateKwicIndex: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'terms', path);
};

const validateKwic: Validator = (record, path) => {
	validateMeta(record, path);
	if (typeof record.term !== 'string') throw new Error(`${path}.term must be a string.`);
	requireArray(record, 'lines', path);
};

const validateMeetingIndex: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'meetings', path);
};

const validateMeeting: Validator = (record, path) => {
	validateMeta(record, path);
	requireArray(record, 'speeches', path);
};

/** Fetch and cache a JSON payload, keyed on its path. */
export function json<T>(
	path: string,
	fetcher: typeof fetch = fetch,
	required: readonly string[] = ['meta'],
	validate?: Validator
): Promise<T> {
	const url = `${base}/data/${path}`;
	if (!cache.has(url)) {
		const request = fetcher(url)
			.then((response) => {
				if (!response.ok) {
					// A 404 here almost always means the pipeline has not been run,
					// so say that rather than letting a parse error surface.
					throw new Error(
						`${path} is missing (${response.status}). Run the pipeline and ` +
							`scripts/export_web.py to build web/static/data/.`
					);
				}
				return response.json() as Promise<unknown>;
			})
			.then((payload) => {
				if (!payload || typeof payload !== 'object') {
					throw new Error(`${path} is not a JSON object.`);
				}
				const record = payload as Record<string, unknown>;
				const missing = required.filter((key) => !(key in record));
				if (missing.length) {
					throw new Error(`${path} is missing required field(s): ${missing.join(', ')}.`);
				}
				validate?.(record, path);
				return payload as T;
			})
			.catch((error) => {
				cache.delete(url);
				throw error;
			});
		cache.set(url, request);
	}
	return cache.get(url) as Promise<T>;
}

export const annual = (f?: typeof fetch) =>
	json<AnnualSeries>(
		'series/annual.json',
		f,
		['meta', 'periods', 'corpus', 'terms'],
		validateAnnual
	);
export const quarterly = (f?: typeof fetch) =>
	json<AnnualSeries>(
		'series/quarterly.json',
		f,
		['meta', 'periods', 'corpus', 'terms'],
		validateAnnual
	);
export const breakdowns = (f?: typeof fetch) =>
	json<Breakdowns>('series/breakdowns.json', f, ['meta', 'measures'], validateBreakdowns);
export const changePoints = (f?: typeof fetch) =>
	json<ChangePoints>(
		'series/change_points.json',
		f,
		['meta', 'series', 'inference'],
		validateChangePoints
	);
export const events = (f?: typeof fetch) =>
	json<Events>('series/events.json', f, ['meta', 'events'], validateEvents);

export const collocates = (f?: typeof fetch) =>
	json<Collocates>('lexical/collocates.json', f, ['meta'], validateLexical);
export const slicedCollocates = (f?: typeof fetch) =>
	json<SlicedCollocates>('lexical/collocates_sliced.json', f, ['meta'], validateLexical);
export const keyness = (f?: typeof fetch) =>
	json<Keyness>('lexical/keyness.json', f, ['meta'], validateKeyness);
export const network = (f?: typeof fetch) =>
	json<Network>('lexical/network.json', f, ['meta'], validateNetwork);

export const countries = (f?: typeof fetch) =>
	json<Countries>(
		'countries/countries.json',
		f,
		['meta', 'countries', 'periods', 'measures', 'minimum_speeches', 'iso3_collisions'],
		validateCountries
	);

export const speakerKeyness = (f?: typeof fetch) =>
	json<SpeakerKeyness>(
		'countries/speaker_keyness.json',
		f,
		['meta', 'speakers', 'minimum_pairs', 'minimum_coverage'],
		validateSpeakerKeyness
	);

export const kwicIndex = (f?: typeof fetch) =>
	json<KwicIndex>('kwic/index.json', f, ['meta'], validateKwicIndex);
export const kwic = (term: string, f?: typeof fetch) =>
	json<KwicFile>(
		`kwic/${encodeURIComponent(term)}.json`,
		f,
		['meta', 'term', 'lines'],
		validateKwic
	);

export const meetingIndex = (f?: typeof fetch) =>
	json<MeetingIndex>('meetings.json', f, ['meta'], validateMeetingIndex);
export const meeting = (basename: string, f?: typeof fetch) =>
	json<Meeting>(
		`speeches/${encodeURIComponent(basename)}.json`,
		f,
		['meta', 'speeches'],
		validateMeeting
	);

/** `UNSC_2015_SPV.7481_spch0007#3` → the meeting file that speech lives in. */
export function meetingOf(lineId: string): string {
	const speech = lineId.split('#')[0];
	return speech.replace(/_spch\d+$/, '');
}

/** `UNSC_2015_SPV.7481_spch0007#3` → `UNSC_2015_SPV.7481_spch0007`. */
export function speechOf(lineId: string): string {
	return lineId.split('#')[0];
}
