/**
 * Citing an occurrence, in prose and in the three formats reference managers read.
 *
 * Roadmap U3 deferred these formats until two conditions were met: that the
 * speech metadata is sufficient, and that round-trip fixtures are defined.
 * Both are settled here, and the first is worth stating plainly because the
 * honest answer is *sufficient, with one substitution*.
 *
 * **What the corpus gives.** The delegation or organisation, the S/PV symbol,
 * the meeting date, the agenda item, the verbatim sentence, a stable
 * occurrence identifier, and — when a meeting file is loaded, as it is in the
 * reader — the personal speaker and their role.
 *
 * **What it does not.** Paragraph or page locators of the official record, and
 * a stable URL for the record itself: the interface links the UN Digital
 * Library by *search*, which is a way of finding the document and not an
 * identifier for it. So a citation built here uses this project's own stable
 * occurrence ID as its locator and its permalink as its URL, and never dresses
 * a search link up as a document URI. A reader who needs the official
 * pagination has the symbol and the date, which is what one asks the library
 * with.
 *
 * **The clock is a parameter.** `accessed` is passed in rather than read from
 * `Date` inside, which is what lets the fixtures below pin exact strings.
 */

import type { KwicLine, Speech } from './types';

/** A quotation plus enough plain-text context to trace it without special software. */
export function occurrenceQuotation(line: KwicLine, permalink: string): string {
	return [
		`“${line.sent.trim()}”`,
		'',
		`${line.country}, UN Security Council, ${line.spv} (${line.date}). ` +
			`Genocide at the Security Council, occurrence ${line.id}. ${permalink}`
	].join('\n');
}

const PROJECT = 'Genocide at the Security Council';
const CONTAINER = 'United Nations Security Council Official Records';

/** One occurrence, reduced to the fields every citation format needs. */
export interface CitationRecord {
	/** The stable occurrence ID; this project's locator. */
	id: string;
	/** The delegation or organisation that holds the floor. */
	body: string;
	/** The person speaking for it, when the meeting is loaded. */
	speaker: string | null;
	role: string | null;
	/** `S/PV.7000`. */
	symbol: string;
	/** The meeting's ordinal, read off the symbol, or null if it is not there. */
	meeting: number | null;
	/** ISO `YYYY-MM-DD`. */
	date: string;
	agenda: string;
	sentence: string;
	url: string;
	/** ISO `YYYY-MM-DD`, supplied by the caller. */
	accessed: string;
}

const ordinal = (value: number): string => {
	const tens = value % 100;
	if (tens >= 11 && tens <= 13) return `${value}th`;
	return `${value}${['th', 'st', 'nd', 'rd'][value % 10] ?? 'th'}`;
};

/**
 * Build the record a citation is written from.
 *
 * The speech is optional because the concordance does not hold one: a KWIC
 * line names the delegation, and the personal speaker lives on the speech the
 * reader loads. A citation to "France" is correct and complete; one that can
 * also name the representative is simply fuller.
 */
export function citationOf(
	line: KwicLine,
	speech: Speech | null,
	url: string,
	accessed: string
): CitationRecord {
	const number = Number(/(\d+)\s*$/.exec(line.spv)?.[1]);
	return {
		id: line.id,
		body: line.country,
		speaker: speech?.speaker ?? null,
		role: speech?.role ?? null,
		symbol: line.spv,
		meeting: Number.isFinite(number) ? number : null,
		date: line.date,
		agenda: line.agenda,
		sentence: line.sent.trim(),
		url,
		accessed
	};
}

/** `2014-06-11` → `[2014, 6, 11]`, dropping any part the date does not have. */
const dateParts = (date: string): number[] =>
	date
		.split('-')
		.map(Number)
		.filter((part) => Number.isFinite(part));

/** How the author reads: the person and their delegation, or the delegation. */
const author = (record: CitationRecord): string =>
	record.speaker ? `${record.speaker} (${record.body})` : record.body;

/** The meeting as an event name, when the symbol carried an ordinal. */
const event = (record: CitationRecord): string =>
	record.meeting === null
		? 'UN Security Council'
		: `UN Security Council, ${ordinal(record.meeting)} meeting`;

const note = (record: CitationRecord): string => `${PROJECT}, occurrence ${record.id}`;

/**
 * CSL-JSON, as `type: "speech"`.
 *
 * A verbatim record of a statement is a delivered speech, and CSL has that
 * type. `bill` and `legal_case` describe instruments the Council adopts rather
 * than what a delegation said; `document` would lose the speech act. The
 * symbol goes in `number`, which is where a reader of the official records
 * looks for it, and the agenda item in `section`.
 */
export function toCslJson(record: CitationRecord): string {
	return JSON.stringify(
		[
			{
				id: record.id,
				type: 'speech',
				author: [{ literal: author(record) }],
				title: record.sentence,
				'container-title': CONTAINER,
				publisher: 'United Nations',
				number: record.symbol,
				event: event(record),
				...(record.agenda ? { section: record.agenda } : {}),
				issued: { 'date-parts': [dateParts(record.date)] },
				accessed: { 'date-parts': [dateParts(record.accessed)] },
				URL: record.url,
				note: note(record)
			}
		],
		null,
		'\t'
	);
}

/**
 * RIS, as `GOVDOC`.
 *
 * RIS has no speech type; a UN verbatim record is a government document, which
 * is the type reference managers map to the right shape. Lines are CRLF and
 * the record ends on `ER  -`, both of which the format requires and some
 * importers enforce.
 */
export function toRis(record: CitationRecord): string {
	const rows: [string, string][] = [
		['TY', 'GOVDOC'],
		['AU', author(record)],
		['TI', record.sentence],
		['T2', CONTAINER],
		['PB', 'United Nations'],
		['M1', record.symbol],
		['DA', record.date.replace(/-/g, '/')],
		['PY', record.date.slice(0, 4)]
	];
	if (record.agenda) rows.push(['KW', record.agenda]);
	rows.push(['UR', record.url]);
	rows.push(['Y2', record.accessed.replace(/-/g, '/')]);
	rows.push(['N1', note(record)]);
	return [...rows.map(([tag, value]) => `${tag}  - ${value}`), 'ER  - ', ''].join('\r\n');
}

/**
 * Escape for a BibTeX field.
 *
 * Braces and backslashes would otherwise open groups or commands, and the five
 * characters after them are TeX's own. Non-ASCII is left as UTF-8: every
 * current engine reads it, and transliterating a delegation's name would be a
 * worse error than assuming biber.
 *
 * **The URL is escaped too, and must be.** A percent-encoded permalink — and
 * these are percent-encoded, because an occurrence ID contains `#` — carries
 * `%`, which opens a comment in TeX and would silently swallow the rest of the
 * line and the entry with it. Underscores in the identifier are the same kind
 * of hazard. An escaped URL is what a style prints; an unescaped one is what
 * breaks the file.
 */
const bibtex = (value: string): string =>
	value
		.replace(/\\/g, '\\textbackslash{}')
		.replace(/([{}])/g, '\\$1')
		.replace(/([#$%&_])/g, '\\$1');

/** A key a `.bib` file will accept: letters, digits and colons survive. */
const bibKey = (id: string): string => id.replace(/[^A-Za-z0-9:.-]+/g, '-').replace(/^-+|-+$/g, '');

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

/**
 * BibTeX, as `@misc`.
 *
 * `@misc` rather than a document type BibTeX does not have: `howpublished`
 * then carries the container and the symbol together, which is how UN records
 * are cited in practice and what a bibliography style will print unaltered.
 */
export function toBibtex(record: CitationRecord): string {
	const month = MONTHS[Number(record.date.slice(5, 7)) - 1];
	const fields: [string, string][] = [
		['author', bibtex(author(record))],
		['title', bibtex(record.sentence)],
		['howpublished', bibtex(`${CONTAINER}, ${record.symbol}`)],
		['organization', bibtex(event(record))],
		['year', record.date.slice(0, 4)]
	];
	if (month) fields.push(['month', month]);
	if (record.agenda) fields.push(['keywords', bibtex(record.agenda)]);
	fields.push(['url', bibtex(record.url)]);
	fields.push(['urldate', record.accessed]);
	fields.push(['note', bibtex(note(record))]);
	return [
		`@misc{${bibKey(record.id)},`,
		...fields.map(([name, value]) => `\t${name} = {${value}},`),
		'}',
		''
	].join('\n');
}
