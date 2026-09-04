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
	NodeFrames,
	SlicedCollocates,
	SpeakerKeyness,
	Usage,
	UsageOccurrences
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
	for (const field of ['speeches', 'words', 'meetings']) {
		if (requireArray(corpus, field, `${path}.corpus`).length !== periods.length) {
			throw new Error(`${path}.corpus.${field} must align with periods.`);
		}
	}
	// A band drawn from bounds one period short would slide every later year's
	// interval onto the wrong year without failing anywhere.
	for (const kind of ['terms', 'registers', 'sets']) {
		if (!(kind in record)) continue;
		for (const [name, measure] of Object.entries(recordAt(record, kind))) {
			if (!isRecord(measure)) throw new Error(`${path}.${kind}.${name} must be an object.`);
			for (const field of ['speech_rate_low', 'speech_rate_high']) {
				if (requireArray(measure, field, `${path}.${kind}.${name}`).length !== periods.length) {
					throw new Error(`${path}.${kind}.${name}.${field} must align with periods.`);
				}
			}
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

const validateNodeFrames: Validator = (record, path) => {
	// Two refusals, both substantive, and both about a figure that would be wrong
	// rather than absent.
	//
	// The composition is drawn as a share of the node's occurrences, so the frame
	// counts have to exhaust them. If they do not, every dot is drawn against a
	// denominator larger than the evidence behind it and the picture is quietly
	// flattened. 17 reconciles the classification against 03's count upstream;
	// this refuses a payload it cannot draw honestly rather than trusting that it
	// ran.
	const total = Number(record.occurrences);
	const rows = requireArray(recordAt(record, 'totals'), 'frames', `${path}.totals`);
	let counted = 0;
	for (const [index, row] of rows.entries()) {
		if (!isRecord(row)) throw new Error(`${path}.totals.frames[${index}] must be an object.`);
		counted += Number(row.occurrences ?? 0);
		// A share without its interval would be drawn as a dot with no whisker,
		// which is the one reading the figure exists to prevent.
		if (row.share !== null && !Number.isFinite(row.share_low)) {
			throw new Error(`${path}.totals.frames[${index}] has a share with no interval.`);
		}
	}
	if (counted !== total) {
		throw new Error(
			`${path}.totals.frames sum to ${counted} against ${total} occurrences of the node.`
		);
	}
	if (!requireArray(record, 'codebook', path).length) {
		throw new Error(`${path}.codebook is empty, so no frame on the figure can be explained.`);
	}
};

/** The three states the gold sample may honestly be in. Nothing else is one. */
const GOLD_STATES = new Set(['not_started', 'in_progress', 'complete']);

/** The two states a second opinion may honestly be in. Nothing else is one. */
const COMPARISON_STATES = new Set(['computed', 'none']);

/**
 * The five fields a second opinion is compared on, in the order `lib/usage.py`
 * writes them into a row.
 *
 * Declared here rather than in `usage.ts` because it is the artefact's own
 * vocabulary and this is the boundary that refuses a row outside it — and
 * because `usage.ts` already imports from this module, so one list can serve
 * both without the two files importing each other.
 */
export const COMPARED_FIELDS = [
	'verdict',
	'quotation',
	'concrete_case',
	'speaker_position',
	'function',
	'referent'
] as const;

const COMPARED = new Set<string>(COMPARED_FIELDS);

/**
 * The second opinion, refused on the two ways its own claim can be false.
 *
 * A whole section of the page appears under `computed` and nothing at all
 * appears under `none`, so a block that has the state wrong is not a wrong
 * number on screen — it is a section of the interface that either promises a
 * comparison it cannot show or hides one it has.
 */
const validateUsageComparison = (record: JsonRecord, path: string): void => {
	const comparison = recordAt(record, 'comparison');
	if (typeof comparison.state !== 'string' || !COMPARISON_STATES.has(comparison.state)) {
		throw new Error(
			`${path}.comparison.state is ${JSON.stringify(comparison.state)}; it must be one of ` +
				`${[...COMPARISON_STATES].join(', ')}, because the page draws a section under one of ` +
				`them and nothing under the other.`
		);
	}
	const compared = requireArray(comparison, 'fields', `${path}.comparison`);
	if (comparison.state === 'none' && (compared.length > 0 || Number(comparison.overlap) > 0)) {
		// A block saying no second opinion was run and reporting numbers anyway
		// would be numbers no surface ever prints, because nothing is drawn here.
		throw new Error(
			`${path}.comparison says no second opinion was run and reports ${compared.length} ` +
				`agreement rows over ${comparison.overlap} compared occurrences.`
		);
	}
	if (comparison.state === 'computed' && !String(comparison.model ?? '').trim()) {
		// The objection the published run already answers: a run nobody can
		// identify is a run nobody can repeat or reject. The apparatus prints this
		// identifier beside the published model's, as the thing it was compared to.
		throw new Error(`${path}.comparison claims a second opinion and does not name the model.`);
	}
	if (Number(comparison.contested_any) > Number(comparison.overlap)) {
		// A part larger than the whole, which is the objection the matrix's speaker_position
		// bands answer: the contested occurrences are a subset of the compared ones
		// and the page states the one as a share of the other.
		throw new Error(
			`${path}.comparison contests ${comparison.contested_any} of ${comparison.overlap} ` +
				`compared occurrences.`
		);
	}
	for (const [index, field] of compared.entries()) {
		const at = `${path}.comparison.fields[${index}]`;
		if (!isRecord(field)) throw new Error(`${at} must be an object.`);
		if (Number(field.contested) > Number(field.n)) {
			throw new Error(
				`${at} (${field.field}) contests ${field.contested} of ${field.n} compared occurrences.`
			);
		}
	}
};

/**
 * The experimental layer, refused on the four things it can get wrong quietly.
 *
 * This artefact is model output, which is exactly why the boundary is stricter
 * here rather than more forgiving: the interface's whole claim is that it
 * publishes what a model said and no more, and each of the refusals below is a
 * case where it would end up publishing something the model did not say.
 */
const validateUsage: Validator = (record, path) => {
	// A run nobody can identify is a run nobody can repeat or reject. The page
	// prints both of these as its own credentials, and `undefined` in a mono
	// span reads as a model identifier to anyone who does not know better.
	const model = recordAt(record, 'model');
	if (typeof model.id !== 'string' || typeof model.prompt_sha256 !== 'string') {
		throw new Error(`${path}.model must name the model it ran and the prompt it ran with.`);
	}

	const gold = recordAt(record, 'gold');
	if (typeof gold.state !== 'string' || !GOLD_STATES.has(gold.state)) {
		throw new Error(
			`${path}.gold.state is ${JSON.stringify(gold.state)}; it must be one of ` +
				`${[...GOLD_STATES].join(', ')}, because the page says which of those three it is.`
		);
	}

	const actors = new Set<string>();
	for (const [index, actor] of arrayAt(record, 'actors').entries()) {
		if (!isRecord(actor) || typeof actor.country_org !== 'string') {
			throw new Error(`${path}.actors[${index}] must name a speaker.`);
		}
		actors.add(actor.country_org);
	}
	const referents = new Set<string>();
	for (const [index, referent] of arrayAt(record, 'referents').entries()) {
		if (!isRecord(referent) || typeof referent.id !== 'string') {
			throw new Error(`${path}.referents[${index}] must carry an id.`);
		}
		referents.add(referent.id);
	}

	for (const [index, cell] of arrayAt(record, 'matrix').entries()) {
		if (!isRecord(cell)) throw new Error(`${path}.matrix[${index}] must be an object.`);
		// A cell naming a speaker or a referent that is not in the tables above is
		// a join failure upstream. Drawn anyway it would be a row or a column the
		// matrix has no heading for, and the figure would silently lose it.
		if (!actors.has(String(cell.actor))) {
			throw new Error(
				`${path}.matrix[${index}] names ${cell.actor}, who is not in the actor table.`
			);
		}
		if (!referents.has(String(cell.referent))) {
			throw new Error(
				`${path}.matrix[${index}] names the referent ${cell.referent}, which is not on the list.`
			);
		}
		const positions = requireRecord(cell, 'positions', `${path}.matrix[${index}]`);
		const total = Object.values(positions).reduce<number>(
			(sum, value) => sum + Number(value ?? 0),
			0
		);
		// Short is drawable and over is not: the speaker_position bands are parts of the
		// cell's own count, and a part larger than the whole is a bar that runs
		// past the number printed beside it.
		if (total > Number(cell.count)) {
			throw new Error(
				`${path}.matrix[${index}] (${cell.actor} × ${cell.referent}) divides ${cell.count} ` +
					`occurrences into ${total} positions.`
			);
		}
	}

	for (const [index, row] of arrayAt(record, 'position_by_actor').entries()) {
		if (!isRecord(row)) throw new Error(`${path}.position_by_actor[${index}] must be an object.`);
		if (!actors.has(String(row.actor))) {
			throw new Error(
				`${path}.position_by_actor[${index}] names ${row.actor}, who is not in the actor table.`
			);
		}
		// The same substantive check `validateCountries` makes: the figure ranks
		// exactly the rows that claim to be sufficient, so a sufficient row with
		// no share would be ranked at the top or the bottom by a null.
		if (row.sufficient === true && !Number.isFinite(row.share_rejects)) {
			throw new Error(
				`${path}.position_by_actor[${index}] (${row.actor}) claims to be sufficient without a share.`
			);
		}
	}

	// The chronology, held to what the other blocks are held to: the two joins it
	// makes, and the identifier the figure builds a link out of.
	const diffusion = recordAt(record, 'diffusion');
	const milestones = new Set(
		requireArray(diffusion, 'milestones', `${path}.diffusion`).map(String)
	);
	for (const [index, entry] of requireArray(
		diffusion,
		'referents',
		`${path}.diffusion`
	).entries()) {
		const at = `${path}.diffusion.referents[${index}]`;
		if (!isRecord(entry)) throw new Error(`${at} must be an object.`);
		// The same join failure the matrix is refused for. Drawn anyway it would be
		// a curve the picker has no name for.
		if (!referents.has(String(entry.id))) {
			throw new Error(`${at} names the referent ${entry.id}, which is not on the list.`);
		}
		for (const [position, event] of requireArray(entry, 'events', at).entries()) {
			const where = `${at}.events[${position}]`;
			if (!isRecord(event)) throw new Error(`${where} must be an object.`);
			if (!actors.has(String(event.actor))) {
				throw new Error(`${where} names ${event.actor}, who is not in the actor table.`);
			}
			// The milestones are the artefact's own list, so a fourth one is a series
			// this figure would draw nothing for and never mention.
			if (!milestones.has(String(event.milestone))) {
				throw new Error(
					`${where} is a ${event.milestone} event, which is not one of the milestones ` +
						`this run declares.`
				);
			}
			// The chronology's link into the record is built from this identifier
			// alone. Empty, it would offer a reader a speech that cannot exist rather
			// than no link at all.
			if (typeof event.id !== 'string' || !event.id) {
				throw new Error(`${where} carries no line id, so nothing can be read back from it.`);
			}
		}
	}

	validateUsageComparison(record, path);
};

/** The quotations behind the matrix, refused where they could not be quoted. */
const validateUsageOccurrences: Validator = (record, path) => {
	for (const [index, occurrence] of arrayAt(record, 'occurrences').entries()) {
		if (!isRecord(occurrence) || typeof occurrence.id !== 'string' || !occurrence.id) {
			throw new Error(
				`${path}.occurrences[${index}] carries no line id, so nothing can be quoted from it.`
			);
		}
		// The drill-down prints this span as the model's own evidence. A row that
		// says the span was found and hands over nothing would print an empty
		// quotation under a heading claiming the model verified it.
		if (occurrence.evidence_valid === true && !String(occurrence.evidence_quote ?? '').trim()) {
			throw new Error(
				`${path}.occurrences[${index}] (${occurrence.id}) claims a verified evidence span and ` +
					`carries no quotation.`
			);
		}
		// The second opinion, per row. The drill-down marks an occurrence with the
		// fields it names here and prints the other reading of exactly those, so a
		// name outside the five is a marking that reads back to nothing, and an
		// `alt` out of step with `contested` is either a disagreement with no
		// reading behind it or a reading no surface would ever show.
		const contested = requireArray(occurrence, 'contested', `${path}.occurrences[${index}]`).map(
			String
		);
		const unknown = contested.filter((field) => !COMPARED.has(field));
		if (unknown.length) {
			throw new Error(
				`${path}.occurrences[${index}] (${occurrence.id}) is contested on ${unknown.join(', ')}, ` +
					`which is not among the compared fields ${COMPARED_FIELDS.join(', ')}.`
			);
		}
		const alt = occurrence.alt;
		if (contested.length && !isRecord(alt)) {
			throw new Error(
				`${path}.occurrences[${index}] (${occurrence.id}) is contested on ${contested.join(', ')} ` +
					`and carries no second reading.`
			);
		}
		if (!contested.length && alt !== null) {
			throw new Error(
				`${path}.occurrences[${index}] (${occurrence.id}) is contested on nothing, so its second ` +
					`reading must be null and is ${alt === undefined ? 'absent' : 'a reading'}.`
			);
		}
		if (isRecord(alt)) {
			const silent = contested.filter((field) => typeof alt[field] !== 'string');
			if (silent.length) {
				throw new Error(
					`${path}.occurrences[${index}] (${occurrence.id}) is contested on ${silent.join(', ')} ` +
						`and its second reading says nothing there.`
				);
			}
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
 * 29 concordances and 9,464 speech files—and a reader who opens every term
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
	'usage/usage.json': {
		meta: 'object',
		model: 'object',
		prompt: 'string',
		referents: 'array',
		actors: 'array',
		minimum_occurrences: 'number',
		matrix: 'array',
		position_by_actor: 'array',
		diffusion: 'object',
		comparison: 'object',
		gold: 'object'
	},
	'usage/occurrences.json': { meta: 'object', occurrences: 'array' },
	'frames/frames.json': {
		meta: 'object',
		codebook: 'array',
		totals: 'object',
		morphology: 'object',
		by_year: 'object',
		slices: 'object',
		occurrences: 'number',
		minimum_occurrences: 'number'
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

/* The experimental layer, in two files rather than one: the summary is a few
   tens of kilobytes and every reader of the view needs it, while the annotated
   occurrences behind it are wanted only by a reader who opens a cell.
   The concordance splits its index from its lines for the same reason. */
export const usage = at<Usage>('usage/usage.json', validateUsage);
export const usageOccurrences = at<UsageOccurrences>(
	'usage/occurrences.json',
	validateUsageOccurrences
);

/* 17's composition of the node's occurrences. The per-occurrence assignments in
   `frames/occurrences.json` are not fetched: the figure is an aggregate, and a
   megabyte of rows nobody draws is a megabyte nobody should download. They stay
   in the payload for a reader who wants to check the table by hand. */
export const nodeFrames = at<NodeFrames>('frames/frames.json', validateNodeFrames);

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

/** `UNSC_2015_SPV.7481_spch0007#3` → the one-based occurrence ordinal `3`. */
export function occurrenceOf(lineId: string): number | null {
	const match = /#([1-9]\d*)$/.exec(lineId);
	return match ? Number(match[1]) : null;
}
