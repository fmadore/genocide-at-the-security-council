import { describe, expect, it } from 'vitest';
import { citationOf, occurrenceQuotation, toBibtex, toCslJson, toRis } from './citation';
import type { KwicLine, Speech } from './types';

const line: KwicLine = {
	id: 'UNSC_2014_SPV.7000_spch0001#1',
	spv: 'S/PV.7000',
	date: '2014-06-11',
	country: 'Rwanda',
	iso3: 'RWA',
	group: 'E10',
	type: 'state',
	agenda: 'Protection of civilians',
	start: 26,
	end: 34,
	left: 'We warned that ',
	kw: 'genocide',
	right: ' could occur.',
	sent: 'We warned that genocide could occur.'
};

describe('a plain occurrence quotation', () => {
	it('keeps the pipeline sentence verbatim and trims only surrounding space', () => {
		expect(
			occurrenceQuotation({ ...line, sent: '  We warned that genocide could occur.  ' }, 'URL')
		).toContain('“We warned that genocide could occur.”');
	});

	it('names the speaker, record, date, project, and stable occurrence', () => {
		const text = occurrenceQuotation(line, 'https://example.test/reader?occurrence=1');
		expect(text).toContain('Rwanda, UN Security Council, S/PV.7000 (2014-06-11).');
		expect(text).toContain(
			'Genocide at the Security Council, occurrence UNSC_2014_SPV.7000_spch0001#1.'
		);
	});

	it('ends with the occurrence permalink', () => {
		const url = 'https://example.test/reader?occurrence=UNSC_2014_SPV.7000_spch0001%231';
		expect(occurrenceQuotation(line, url).endsWith(url)).toBe(true);
	});
});

/**
 * The three machine formats, pinned two ways.
 *
 * Golden strings catch a field that silently changes shape; parsing the output
 * back catches a field that silently disappears, which a substring assertion
 * would not. RIS and BibTeX have no parser in this project and do not need
 * one in production — these two are fifteen lines each and live here, where
 * their only job is to prove the serializers are readable by something other
 * than themselves.
 */
const URL =
	'https://example.test/reader/UNSC_2014_SPV.7000?occurrence=UNSC_2014_SPV.7000_spch0001%231';
const ACCESSED = '2026-08-27';

const speech = { speaker: 'Mr. Gasana', role: 'Permanent Representative' } as Speech;

/** `TY  - GOVDOC` → `{TY: ['GOVDOC']}`; repeated tags accumulate. */
function parseRis(text: string): Record<string, string[]> {
	const fields: Record<string, string[]> = {};
	for (const row of text.split('\r\n')) {
		const match = /^([A-Z][A-Z0-9])\s{2}- ?(.*)$/.exec(row);
		if (!match) continue;
		(fields[match[1]] ??= []).push(match[2]);
	}
	return fields;
}

/** Undo what `bibtex()` did, so a round trip can be asserted against the source. */
const unTex = (value: string): string =>
	value.replace(/\\([#$%&_{}])/g, '$1').replace(/\\textbackslash\{\}/g, '\\');

/** `@misc{key, a = {b},}` → `{type, key, fields}`, with TeX escapes undone. */
function parseBibtex(text: string): { type: string; key: string; fields: Record<string, string> } {
	const head = /^@(\w+)\{([^,]+),/.exec(text);
	const fields: Record<string, string> = {};
	for (const row of text.split('\n').slice(1)) {
		const match = /^\t(\w+) = \{([\s\S]*)\},$/.exec(row);
		if (match) fields[match[1]] = unTex(match[2]);
	}
	return { type: head?.[1] ?? '', key: head?.[2] ?? '', fields };
}

describe('the record a citation is written from', () => {
	it('reads the meeting number off the symbol', () => {
		expect(citationOf(line, null, URL, ACCESSED).meeting).toBe(7000);
	});

	// A KWIC line names the delegation; the person lives on the speech, which
	// only the reader has loaded. Both must produce a valid citation.
	it('cites the delegation alone when no speech is loaded', () => {
		expect(citationOf(line, null, URL, ACCESSED).speaker).toBeNull();
	});

	it('adds the person when one is known', () => {
		expect(citationOf(line, speech, URL, ACCESSED).speaker).toBe('Mr. Gasana');
	});

	it('has no meeting number when the symbol carries none', () => {
		expect(citationOf({ ...line, spv: 'S/PV.unknown' }, null, URL, ACCESSED).meeting).toBeNull();
	});
});

describe('CSL-JSON', () => {
	const record = citationOf(line, speech, URL, ACCESSED);

	it('is exactly this', () => {
		expect(toCslJson(record)).toBe(
			[
				'[',
				'\t{',
				'\t\t"id": "UNSC_2014_SPV.7000_spch0001#1",',
				'\t\t"type": "speech",',
				'\t\t"author": [',
				'\t\t\t{',
				'\t\t\t\t"literal": "Mr. Gasana (Rwanda)"',
				'\t\t\t}',
				'\t\t],',
				'\t\t"title": "We warned that genocide could occur.",',
				'\t\t"container-title": "United Nations Security Council Official Records",',
				'\t\t"publisher": "United Nations",',
				'\t\t"number": "S/PV.7000",',
				'\t\t"event": "UN Security Council, 7000th meeting",',
				'\t\t"section": "Protection of civilians",',
				'\t\t"issued": {',
				'\t\t\t"date-parts": [',
				'\t\t\t\t[',
				'\t\t\t\t\t2014,',
				'\t\t\t\t\t6,',
				'\t\t\t\t\t11',
				'\t\t\t\t]',
				'\t\t\t]',
				'\t\t},',
				'\t\t"accessed": {',
				'\t\t\t"date-parts": [',
				'\t\t\t\t[',
				'\t\t\t\t\t2026,',
				'\t\t\t\t\t8,',
				'\t\t\t\t\t27',
				'\t\t\t\t]',
				'\t\t\t]',
				'\t\t},',
				`\t\t"URL": ${JSON.stringify(URL)},`,
				'\t\t"note": "Genocide at the Security Council, occurrence UNSC_2014_SPV.7000_spch0001#1"',
				'\t}',
				']'
			].join('\n')
		);
	});

	it('parses back with every field intact', () => {
		const [parsed] = JSON.parse(toCslJson(record));
		expect(parsed.id).toBe(record.id);
		expect(parsed.type).toBe('speech');
		expect(parsed.author[0].literal).toBe('Mr. Gasana (Rwanda)');
		expect(parsed.number).toBe('S/PV.7000');
		expect(parsed.issued['date-parts'][0]).toEqual([2014, 6, 11]);
		expect(parsed.accessed['date-parts'][0]).toEqual([2026, 8, 27]);
		expect(parsed.URL).toBe(URL);
		expect(parsed.note).toContain(record.id);
	});
});

describe('RIS', () => {
	const record = citationOf(line, null, URL, ACCESSED);
	const text = toRis(record);

	// The format requires both, and some importers reject a file without them.
	it('uses CRLF and terminates the record', () => {
		expect(text).toContain('\r\n');
		expect(text).not.toMatch(/[^\r]\n/);
		expect(text.trimEnd().endsWith('ER  -')).toBe(true);
	});

	it('parses back with every field intact', () => {
		const fields = parseRis(text);
		expect(fields.TY).toEqual(['GOVDOC']);
		expect(fields.AU).toEqual(['Rwanda']);
		expect(fields.TI).toEqual(['We warned that genocide could occur.']);
		expect(fields.T2).toEqual(['United Nations Security Council Official Records']);
		expect(fields.M1).toEqual(['S/PV.7000']);
		expect(fields.DA).toEqual(['2014/06/11']);
		expect(fields.PY).toEqual(['2014']);
		expect(fields.UR).toEqual([URL]);
		expect(fields.Y2).toEqual(['2026/08/27']);
		expect(fields.N1[0]).toContain('occurrence UNSC_2014_SPV.7000_spch0001#1');
	});
});

describe('BibTeX', () => {
	const record = citationOf(line, null, URL, ACCESSED);

	it('is exactly this', () => {
		expect(toBibtex(record)).toBe(
			[
				'@misc{UNSC-2014-SPV.7000-spch0001-1,',
				'\tauthor = {Rwanda},',
				'\ttitle = {We warned that genocide could occur.},',
				'\thowpublished = {United Nations Security Council Official Records, S/PV.7000},',
				'\torganization = {UN Security Council, 7000th meeting},',
				'\tyear = {2014},',
				'\tmonth = {jun},',
				'\tkeywords = {Protection of civilians},',
				// The percent-encoding and the underscores are escaped: an unescaped
				// `%` opens a TeX comment and would swallow the rest of the entry.
				'\turl = {https://example.test/reader/UNSC\\_2014\\_SPV.7000?occurrence=UNSC\\_2014\\_SPV.7000\\_spch0001\\%231},',
				'\turldate = {2026-08-27},',
				'\tnote = {Genocide at the Security Council, occurrence UNSC\\_2014\\_SPV.7000\\_spch0001\\#1},',
				'}',
				''
			].join('\n')
		);
	});

	it('leaves no bare TeX comment character anywhere in the entry', () => {
		expect(toBibtex(record)).not.toMatch(/(^|[^\\])%/);
	});

	it('parses back with every field intact', () => {
		const parsed = parseBibtex(toBibtex(record));
		expect(parsed.type).toBe('misc');
		expect(parsed.key).not.toMatch(/[^A-Za-z0-9:.-]/);
		expect(parsed.fields.author).toBe('Rwanda');
		expect(parsed.fields.year).toBe('2014');
		expect(parsed.fields.urldate).toBe('2026-08-27');
		expect(parsed.fields.url).toBe(URL);
	});
});

/**
 * The corpus holds apostrophes, accents and punctuation that each format reads
 * as syntax. A citation that breaks a `.bib` file is worse than no citation.
 */
describe('a record that is hostile to all three formats', () => {
	const nasty: KwicLine = {
		...line,
		id: 'UNSC_1994_SPV.3377_spch0012#4',
		spv: 'S/PV.3377',
		country: "Côte d'Ivoire",
		agenda: 'Rwanda {special} 100% & more_things',
		sent: 'He said “this is genocide”, and $50 was raised — 50% of it.'
	};
	const record = citationOf(nasty, null, URL, ACCESSED);

	it('keeps the text readable in CSL-JSON', () => {
		const [parsed] = JSON.parse(toCslJson(record));
		expect(parsed.author[0].literal).toBe("Côte d'Ivoire");
		expect(parsed.title).toBe('He said “this is genocide”, and $50 was raised — 50% of it.');
		expect(parsed.section).toBe('Rwanda {special} 100% & more_things');
	});

	it('keeps the text readable in RIS', () => {
		const fields = parseRis(toRis(record));
		expect(fields.AU).toEqual(["Côte d'Ivoire"]);
		expect(fields.TI).toEqual(['He said “this is genocide”, and $50 was raised — 50% of it.']);
	});

	// TeX's own characters must be escaped, and non-ASCII left alone: every
	// current engine reads UTF-8, and transliterating a delegation is worse.
	it('escapes what TeX would otherwise read as syntax', () => {
		const text = toBibtex(record);
		expect(text).toContain("author = {Côte d'Ivoire}");
		expect(text).toContain('\\$50');
		expect(text).toContain('50\\%');
		expect(text).toContain('\\{special\\}');
		expect(text).toContain('\\&');
		expect(text).toContain('more\\_things');
		// Braces are balanced, which is what makes the file parseable at all.
		const body = text.slice(text.indexOf('{'));
		expect([...body].filter((c) => c === '{').length).toBe(
			[...body].filter((c) => c === '}').length
		);
	});

	it('never emits a key BibTeX would refuse', () => {
		expect(parseBibtex(toBibtex(record)).key).toBe('UNSC-1994-SPV.3377-spch0012-4');
	});
});
