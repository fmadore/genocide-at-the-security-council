/**
 * A basket of occurrences, kept on the reader's own machine.
 *
 * Roadmap U5. The site's other state lives in the URL, because a URL is the
 * unit a scholar cites and hands to a collaborator. A basket is deliberately
 * the opposite kind of thing: a working collection, assembled over an
 * afternoon across a dozen terms, that nobody wants to reconstruct from a
 * hundred query strings. So it lives in `localStorage`, and everything that
 * follows from that choice is a constraint rather than a feature.
 *
 * **It is one device's private note, and says so.** No accounts, no
 * synchronisation, no backend — the roadmap forbids all three, and the export
 * is what moves work between machines and between people.
 *
 * **An item carries a copy of what it quotes.** The obvious design stores an
 * occurrence ID and re-fetches. That would make the basket unreadable offline,
 * where `static/data/` is excluded from the service worker on purpose, and it
 * would make an item meaningless the day a lexicon change renumbers the
 * occurrences it names. Every item therefore keeps a snapshot — the sentence,
 * the speaker, the record symbol, the date — plus the lexicon version and
 * analytical hash of the artefact it was taken from. The export then says what
 * each row was true of, and a rebuilt corpus makes items *stale*, not empty.
 *
 * **Nothing here silently destroys work.** An envelope this module cannot read
 * is left in storage untouched and reported to the interface; a cap refuses
 * loudly rather than truncating; there is no migration that guesses.
 *
 * The module is pure. Reading and writing storage, and the reactive state the
 * components bind to, live in `basket.svelte.ts`, which is the only file that
 * touches the browser.
 */

import { csvField, filename } from './export';
import type { KwicLine, Meeting, Speech } from './types';

/** The only envelope version this module will read. */
export const BASKET_VERSION = 1;

/** Where the envelope is kept. Namespaced, because an origin can be shared. */
export const BASKET_KEY = 'unsc-genocide:basket';

/**
 * How many items a basket holds before it refuses more.
 *
 * A limit exists because `localStorage` is a few megabytes per origin and a
 * snapshot is roughly a kilobyte; 200 is far inside that and far beyond a
 * working session. It refuses rather than evicting: dropping the oldest item
 * to make room would delete a reader's note without being asked.
 */
export const MAX_ITEMS = 200;

/** Long enough for a paragraph of argument, short enough to bound the file. */
export const MAX_NOTE = 2000;

/** What an occurrence looked like when it was put in the basket. */
export interface OccurrenceSnapshot {
	spv: string;
	date: string;
	country: string;
	group: string;
	type: string;
	agenda: string;
	keyword: string;
	sentence: string;
	/** The personal speaker, when the item was added from a loaded meeting. */
	speaker?: string;
	role?: string;
}

/** What a whole speech looked like when it was put in the basket. */
export interface SpeechSnapshot {
	spv: string;
	date: string;
	country: string;
	speaker: string;
	role: string;
	topic: string;
	agenda: string;
}

interface Common {
	/** The stable identifier: an occurrence ID, or a speech ID. */
	id: string;
	note: string;
	/** ISO 8601, supplied by the caller so this module stays pure. */
	added: string;
	/** The artefact's own version stamps, for staleness and for the export. */
	lexiconVersion: number | null;
	analysisHash: string | null;
}

export interface OccurrenceItem extends Common {
	kind: 'occurrence';
	/** The lexicon term whose file this line came from. */
	term: string;
	snapshot: OccurrenceSnapshot;
}

export interface SpeechItem extends Common {
	kind: 'speech';
	snapshot: SpeechSnapshot;
}

export type BasketItem = OccurrenceItem | SpeechItem;

export interface Basket {
	version: typeof BASKET_VERSION;
	items: BasketItem[];
}

export const emptyBasket = (): Basket => ({ version: BASKET_VERSION, items: [] });

/**
 * What came back from storage, and whether anything was found that could not
 * be read.
 *
 * The two are reported separately on purpose. An unreadable envelope must
 * produce a working empty basket *and* a sentence the interface can show,
 * because the alternative — starting empty in silence — looks exactly like a
 * basket that has been wiped.
 */
export interface BasketRead {
	basket: Basket;
	/** Null when the stored value was absent or valid. */
	unreadable: string | null;
}

const text = (value: unknown, fallback = ''): string =>
	typeof value === 'string' ? value : fallback;

const versionOf = (value: unknown): number | null =>
	typeof value === 'number' && Number.isFinite(value) ? value : null;

function readOccurrence(raw: Record<string, unknown>): OccurrenceItem | null {
	const id = text(raw.id);
	const snapshot = raw.snapshot;
	if (!id || typeof snapshot !== 'object' || snapshot === null) return null;
	const shot = snapshot as Record<string, unknown>;
	return {
		kind: 'occurrence',
		id,
		term: text(raw.term),
		note: text(raw.note),
		added: text(raw.added),
		lexiconVersion: versionOf(raw.lexiconVersion),
		analysisHash: typeof raw.analysisHash === 'string' ? raw.analysisHash : null,
		snapshot: {
			spv: text(shot.spv),
			date: text(shot.date),
			country: text(shot.country),
			group: text(shot.group),
			type: text(shot.type),
			agenda: text(shot.agenda),
			keyword: text(shot.keyword),
			sentence: text(shot.sentence),
			...(typeof shot.speaker === 'string' ? { speaker: shot.speaker } : {}),
			...(typeof shot.role === 'string' ? { role: shot.role } : {})
		}
	};
}

function readSpeech(raw: Record<string, unknown>): SpeechItem | null {
	const id = text(raw.id);
	const snapshot = raw.snapshot;
	if (!id || typeof snapshot !== 'object' || snapshot === null) return null;
	const shot = snapshot as Record<string, unknown>;
	return {
		kind: 'speech',
		id,
		note: text(raw.note),
		added: text(raw.added),
		lexiconVersion: versionOf(raw.lexiconVersion),
		analysisHash: typeof raw.analysisHash === 'string' ? raw.analysisHash : null,
		snapshot: {
			spv: text(shot.spv),
			date: text(shot.date),
			country: text(shot.country),
			speaker: text(shot.speaker),
			role: text(shot.role),
			topic: text(shot.topic),
			agenda: text(shot.agenda)
		}
	};
}

/**
 * Parse a stored envelope, refusing anything this version does not own.
 *
 * There is no migration and no coercion of a foreign version, because both
 * would mean guessing at the meaning of data written by code this build has
 * never seen. Refusing keeps the stored text intact for a build that does
 * understand it — the caller must not write until the reader has acted.
 */
export function readBasket(stored: string | null): BasketRead {
	if (stored === null || stored.trim() === '') return { basket: emptyBasket(), unreadable: null };

	let parsed: unknown;
	try {
		parsed = JSON.parse(stored);
	} catch {
		return {
			basket: emptyBasket(),
			unreadable:
				'Something is saved under this basket that is not readable as data. It has been left untouched.'
		};
	}

	if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
		return {
			basket: emptyBasket(),
			unreadable: 'The saved basket is not in the expected form. It has been left untouched.'
		};
	}

	const envelope = parsed as Record<string, unknown>;
	const version = versionOf(envelope.version);
	if (version !== BASKET_VERSION) {
		return {
			basket: emptyBasket(),
			unreadable:
				`This browser holds a basket saved as version ${version ?? 'unknown'}, and this ` +
				`version of the site reads version ${BASKET_VERSION}. It has been left untouched ` +
				`rather than converted or overwritten.`
		};
	}

	const rows = Array.isArray(envelope.items) ? envelope.items : [];
	const items: BasketItem[] = [];
	for (const row of rows) {
		if (typeof row !== 'object' || row === null) continue;
		const raw = row as Record<string, unknown>;
		const item = raw.kind === 'speech' ? readSpeech(raw) : readOccurrence(raw);
		if (item) items.push(item);
	}
	return { basket: { version: BASKET_VERSION, items }, unreadable: null };
}

/** The envelope as it goes to storage. */
export const serializeBasket = (basket: Basket): string => JSON.stringify(basket);

/**
 * The result of asking to change a basket.
 *
 * A refusal is a sentence, not a thrown error or a silent no-op: every limit
 * this module enforces has to be explicable at the moment it bites.
 */
export interface BasketChange {
	basket: Basket;
	refused: string | null;
}

const unchanged = (basket: Basket, refused: string): BasketChange => ({ basket, refused });

/** Whether this exact occurrence or speech is already held. */
export const holds = (basket: Basket, id: string): boolean =>
	basket.items.some((item) => item.id === id);

/** Add an item, refusing a duplicate or an overfull basket in words. */
export function addItem(basket: Basket, item: BasketItem): BasketChange {
	if (holds(basket, item.id)) {
		return unchanged(basket, 'That is already in the basket.');
	}
	if (basket.items.length >= MAX_ITEMS) {
		return unchanged(
			basket,
			`The basket holds ${MAX_ITEMS} items, which is its limit. Export what is there, ` +
				`then remove some — nothing is dropped to make room.`
		);
	}
	if (item.note.length > MAX_NOTE) {
		return unchanged(basket, `A note is limited to ${MAX_NOTE} characters.`);
	}
	return { basket: { ...basket, items: [...basket.items, item] }, refused: null };
}

export function removeItem(basket: Basket, id: string): BasketChange {
	return {
		basket: { ...basket, items: basket.items.filter((item) => item.id !== id) },
		refused: null
	};
}

/** Write a note, refusing over-long text rather than cutting it off mid-word. */
export function setNote(basket: Basket, id: string, note: string): BasketChange {
	if (note.length > MAX_NOTE) {
		return unchanged(
			basket,
			`A note is limited to ${MAX_NOTE} characters; this one is ${note.length}.`
		);
	}
	return {
		basket: {
			...basket,
			items: basket.items.map((item) => (item.id === id ? { ...item, note } : item))
		},
		refused: null
	};
}

export const clearBasket = (): Basket => emptyBasket();

/* --- Building items from what a view already holds ------------------------ */

/** Snapshot a concordance line. `added` is passed in so this stays pure. */
export function occurrenceItem(
	line: KwicLine,
	term: string,
	added: string,
	stamps: { lexiconVersion: number | null; analysisHash: string | null },
	speech?: Speech
): OccurrenceItem {
	return {
		kind: 'occurrence',
		id: line.id,
		term,
		note: '',
		added,
		lexiconVersion: stamps.lexiconVersion,
		analysisHash: stamps.analysisHash,
		snapshot: {
			spv: line.spv,
			date: line.date,
			country: line.country,
			group: line.group,
			type: line.type,
			agenda: line.agenda,
			keyword: line.kw,
			sentence: line.sent,
			// Only present when the reader supplied it: the concordance's KWIC file
			// carries the delegation, and the personal name lives on the speech.
			...(speech?.speaker ? { speaker: speech.speaker } : {}),
			...(speech?.role ? { role: speech.role } : {})
		}
	};
}

export function speechItem(
	meeting: Meeting,
	speech: Speech,
	added: string,
	stamps: { lexiconVersion: number | null; analysisHash: string | null }
): SpeechItem {
	return {
		kind: 'speech',
		id: speech.id,
		note: '',
		added,
		lexiconVersion: stamps.lexiconVersion,
		analysisHash: stamps.analysisHash,
		snapshot: {
			spv: meeting.spv,
			date: meeting.date,
			country: speech.country,
			speaker: speech.speaker ?? '',
			role: speech.role ?? '',
			topic: meeting.topic ?? '',
			agenda: meeting.agenda ?? ''
		}
	};
}

/* --- Staleness ------------------------------------------------------------ */

export type Currency = 'current' | 'stale' | 'unknown';

/**
 * Whether an item still describes the corpus the site is currently serving.
 *
 * Compared by lexicon version rather than by checking the occurrence still
 * exists. Existence would mean fetching up to twenty-two term files to answer
 * a question the version answers for the case that actually breaks items — a
 * lexicon change renumbers occurrences within a speech. An item whose version
 * is unknown is reported as unknown and never as stale: the difference between
 * "this may have moved" and "this has moved" is the difference between a
 * caution and a false alarm.
 */
export function currencyOf(item: BasketItem, current: number | null): Currency {
	if (item.lexiconVersion === null || current === null) return 'unknown';
	return item.lexiconVersion === current ? 'current' : 'stale';
}

/* --- Exports -------------------------------------------------------------- */

const SITE = 'Genocide at the Security Council';
const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';

/**
 * A basket export cannot use `ExportRequest`, and the reason is provenance.
 *
 * That type carries one `Provenance` block, because a figure comes from one
 * artefact. A basket is assembled across terms and, after a rebuild, possibly
 * across lexicon versions, so a single header block would have to name one of
 * them and would therefore be false about the rest. The version stamps travel
 * per row instead, and the header says that is where they are.
 */
function header(exported: string, currentLexicon: number | null): string[] {
	const lines = [
		SITE,
		'collection: a reader’s basket, assembled in one browser',
		`exported: ${exported}`,
		currentLexicon === null
			? 'site lexicon version: not known at export time'
			: `site lexicon version: ${currentLexicon}`,
		'provenance: each row carries the lexicon version and analytical hash of the artefact it was taken from',
		`licence: CC BY 4.0 — ${REPO}`
	];
	return lines;
}

export const BASKET_COLUMNS = [
	'id',
	'kind',
	'term',
	'spv',
	'date',
	'country',
	'speaker',
	'group',
	'participant_type',
	'agenda',
	'keyword',
	'sentence',
	'note',
	'added',
	'lexicon_version',
	'analysis_hash',
	'currency',
	'permalink'
];

/** The row a single item contributes, in `BASKET_COLUMNS` order. */
function row(
	item: BasketItem,
	current: number | null,
	permalink: (item: BasketItem) => string
): (string | number | null)[] {
	const shared = [item.id, item.kind];
	const tail = [
		item.note,
		item.added,
		item.lexiconVersion,
		item.analysisHash,
		currencyOf(item, current),
		permalink(item)
	];
	if (item.kind === 'occurrence') {
		const shot = item.snapshot;
		return [
			...shared,
			item.term,
			shot.spv,
			shot.date,
			shot.country,
			shot.speaker ?? '',
			shot.group,
			shot.type,
			shot.agenda,
			shot.keyword,
			shot.sentence,
			...tail
		];
	}
	const shot = item.snapshot;
	return [
		...shared,
		'',
		shot.spv,
		shot.date,
		shot.country,
		shot.speaker,
		'',
		'',
		shot.agenda || shot.topic,
		'',
		'',
		...tail
	];
}

export interface BasketExport {
	basket: Basket;
	/** ISO 8601 timestamp, supplied by the caller. */
	exported: string;
	/** The lexicon version the site is currently serving, when known. */
	currentLexicon: number | null;
	/** Absolute URL for one item, built by the caller that knows the origin. */
	permalink: (item: BasketItem) => string;
}

export function basketCsv(request: BasketExport): string {
	const comments = header(request.exported, request.currentLexicon).map((line) => `# ${line}`);
	const body = request.basket.items.map((item) =>
		row(item, request.currentLexicon, request.permalink).map(csvField).join(',')
	);
	return [...comments, BASKET_COLUMNS.map(csvField).join(','), ...body, ''].join('\r\n');
}

/** The envelope as saved, plus what was true of the site when it was exported. */
export function basketJson(request: BasketExport): string {
	return JSON.stringify(
		{
			site: SITE,
			licence: 'CC BY 4.0',
			repository: REPO,
			exported: request.exported,
			currentLexiconVersion: request.currentLexicon,
			version: request.basket.version,
			items: request.basket.items.map((item) => ({
				...item,
				currency: currencyOf(item, request.currentLexicon),
				permalink: request.permalink(item)
			}))
		},
		null,
		'\t'
	);
}

/**
 * The basket as prose, in the register `occurrenceQuotation` established.
 *
 * Markdown because it is the format that pastes into a manuscript draft with
 * the quotation still a quotation and the citation still beneath it.
 */
export function basketMarkdown(request: BasketExport): string {
	const lines = [
		`# ${SITE} — basket`,
		'',
		...header(request.exported, request.currentLexicon)
			.slice(1)
			.map((line) => `- ${line}`),
		''
	];
	for (const item of request.basket.items) {
		const shot = item.snapshot;
		const who =
			'speaker' in shot && shot.speaker ? `${shot.speaker} (${shot.country})` : shot.country;
		lines.push(`## ${who}, ${shot.spv} (${shot.date})`);
		lines.push('');
		if (item.kind === 'occurrence') {
			lines.push(`> ${item.snapshot.sentence.trim()}`);
			lines.push('');
			lines.push(
				`${who}, UN Security Council, ${shot.spv} (${shot.date}). ` +
					`${SITE}, occurrence ${item.id}. ${request.permalink(item)}`
			);
		} else {
			lines.push(
				`${who}, UN Security Council, ${shot.spv} (${shot.date}). ` +
					`${SITE}, speech ${item.id}. ${request.permalink(item)}`
			);
		}
		const currency = currencyOf(item, request.currentLexicon);
		if (currency !== 'current') {
			lines.push('');
			lines.push(
				currency === 'stale'
					? `*Recorded under lexicon version ${item.lexiconVersion}; the site now serves ` +
							`version ${request.currentLexicon}. The quoted text above is as recorded.*`
					: '*The lexicon version behind this item is not known; the quoted text above is as recorded.*'
			);
		}
		if (item.note.trim()) {
			lines.push('');
			lines.push(`**Note.** ${item.note.trim()}`);
		}
		lines.push('');
	}
	return lines.join('\n');
}

/** `unsc-basket-2026-08-27.csv`, from the export timestamp the caller supplied. */
export const basketFilename = (exported: string, extension: string): string =>
	filename(['unsc', 'basket', exported.slice(0, 10)], extension);
