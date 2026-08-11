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
	MonthlySeries,
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

const validateMonthly: Validator = (record, path) => {
	validateAnnual(record, path);
	const periods = requireArray(record, 'periods', path);
	const years = requireArray(record, 'years', path);
	const sufficient = requireArray(record, 'sufficient', path);
	if (!Number.isFinite(record.minimum_speeches)) {
		throw new Error(`${path}.minimum_speeches must be a finite number.`);
	}
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
	requireRecord(requireRecord(record, 'month_of_year', path), 'measures', `${path}.month_of_year`);
	// Substantive rather than structural, and the same check `validateCountries`
	// makes: the figure draws exactly the cells that claim to be sufficient, so a
	// sufficient cell with no rate would reach the grid as a null — and on a
	// heatmap a null is drawn in the colour a measured zero has.
	for (const kind of ['terms', 'registers', 'sets']) {
		for (const [name, measure] of Object.entries(requireRecord(record, kind, path))) {
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
	// The membership block is drawn as a composition: five bands that fill a
	// speaker's own denominator. If they do not sum to it, the bar comes up short
	// and the missing speeches are drawn as background — a gap that reads as a
	// sixth, unnamed status. 11 reconciles this upstream; the interface refuses a
	// payload it cannot draw honestly rather than trusting that it ran.
	const standing = requireRecord(record, 'standing', path);
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

/**
 * What each artefact must carry, keyed on its path under `static/data/`.
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
	'series/annual.json': ['meta', 'periods', 'corpus', 'terms'],
	'series/quarterly.json': ['meta', 'periods', 'corpus', 'terms'],
	'series/monthly.json': [
		'meta',
		'periods',
		'corpus',
		'sufficient',
		'years',
		'minimum_speeches',
		'month_of_year'
	],
	'series/breakdowns.json': ['meta', 'measures'],
	'series/change_points.json': ['meta', 'series', 'inference'],
	'series/events.json': ['meta', 'events'],
	'lexical/collocates.json': ['meta'],
	'lexical/collocates_sliced.json': ['meta'],
	'lexical/keyness.json': ['meta'],
	'lexical/network.json': ['meta'],
	'countries/countries.json': [
		'meta',
		'countries',
		'periods',
		'measures',
		'standing',
		'minimum_speeches',
		'iso3_collisions'
	],
	'countries/speaker_keyness.json': ['meta', 'speakers', 'minimum_pairs', 'minimum_coverage'],
	'kwic/index.json': ['meta'],
	'kwic/*.json': ['meta', 'term', 'lines'],
	'meetings.json': ['meta'],
	'speeches/*.json': ['meta', 'speeches']
} as const satisfies Record<string, readonly string[]>;

export type Artefact = keyof typeof REQUIRED;

/** An accessor for a fixed artefact: its path, what it must carry, and its validator. */
const at =
	<T>(path: Artefact, validate?: Validator) =>
	(f?: typeof fetch) =>
		json<T>(path, f, REQUIRED[path], validate);

export const annual = at<AnnualSeries>('series/annual.json', validateAnnual);
export const quarterly = at<AnnualSeries>('series/quarterly.json', validateAnnual);
export const monthly = at<MonthlySeries>('series/monthly.json', validateMonthly);
export const breakdowns = at<Breakdowns>('series/breakdowns.json', validateBreakdowns);
export const changePoints = at<ChangePoints>('series/change_points.json', validateChangePoints);
export const events = at<Events>('series/events.json', validateEvents);

export const collocates = at<Collocates>('lexical/collocates.json', validateLexical);
export const slicedCollocates = at<SlicedCollocates>(
	'lexical/collocates_sliced.json',
	validateLexical
);
export const keyness = at<Keyness>('lexical/keyness.json', validateKeyness);
export const network = at<Network>('lexical/network.json', validateNetwork);

export const countries = at<Countries>('countries/countries.json', validateCountries);
export const speakerKeyness = at<SpeakerKeyness>(
	'countries/speaker_keyness.json',
	validateSpeakerKeyness
);

export const kwicIndex = at<KwicIndex>('kwic/index.json', validateKwicIndex);
export const meetingIndex = at<MeetingIndex>('meetings.json', validateMeetingIndex);

/* Fetched by name rather than fixed, so the path is built per call. */
export const kwic = (term: string, f?: typeof fetch) =>
	json<KwicFile>(`kwic/${encodeURIComponent(term)}.json`, f, REQUIRED['kwic/*.json'], validateKwic);

export const meeting = (basename: string, f?: typeof fetch) =>
	json<Meeting>(
		`speeches/${encodeURIComponent(basename)}.json`,
		f,
		REQUIRED['speeches/*.json'],
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
