/**
 * The basket's contract, which is mostly about what it refuses to do.
 *
 * Three properties are worth more than the rest and are tested first: an
 * envelope this build cannot read is never overwritten, a limit refuses in
 * words rather than truncating, and an item exports what it recorded even
 * after the corpus behind it has moved. Each is a way of not destroying a
 * reader's work, which is the only thing local storage can do that no other
 * part of this site can.
 */

import { describe, expect, it } from 'vitest';
import {
	BASKET_COLUMNS,
	BASKET_VERSION,
	MAX_ITEMS,
	MAX_NOTE,
	addItem,
	basketCsv,
	basketFilename,
	basketJson,
	basketMarkdown,
	currencyOf,
	emptyBasket,
	holds,
	occurrenceItem,
	readBasket,
	removeItem,
	serializeBasket,
	setNote,
	speechItem
} from './basket';
import type { Basket, BasketItem, OccurrenceItem } from './basket';
import type { KwicLine, Meeting, Speech } from './types';

const EXPORTED = '2026-08-27T10:00:00Z';

const line = (over: Partial<KwicLine> = {}): KwicLine => ({
	id: 'UNSC_2014_SPV.7000_spch0001#1',
	spv: 'S/PV.7000',
	date: '2014-06-11',
	country: 'Rwanda',
	iso3: 'RWA',
	group: 'E10',
	type: 'Mentioned',
	agenda: 'Protection of civilians',
	start: 26,
	end: 34,
	left: 'We warned that ',
	kw: 'genocide',
	right: ' could occur.',
	sent: 'We warned that genocide could occur.',
	...over
});

const stamps = { lexiconVersion: 2, analysisHash: 'abc123' };

const item = (over: Partial<OccurrenceItem> = {}): OccurrenceItem => ({
	...occurrenceItem(line(), 'genocide', '2026-08-27T09:00:00Z', stamps),
	...over
});

const permalink = (entry: BasketItem) => `https://example.org/#${entry.id}`;

const filled = (...items: BasketItem[]): Basket => ({ version: BASKET_VERSION, items });

describe('reading what is in storage', () => {
	it('starts empty, and says nothing was wrong', () => {
		expect(readBasket(null)).toEqual({ basket: emptyBasket(), unreadable: null });
		expect(readBasket('')).toEqual({ basket: emptyBasket(), unreadable: null });
	});

	it('round-trips a basket it wrote', () => {
		const basket = filled(item());
		expect(readBasket(serializeBasket(basket)).basket).toEqual(basket);
	});

	// The property that matters: an unreadable value produces a working empty
	// basket AND a sentence, because starting empty in silence is what a wiped
	// basket looks like.
	it.each([
		['not json at all', 'not json at all'],
		['a bare array', '[]'],
		['a bare string', '"hello"'],
		['null', 'null'],
		['a future version', '{"version":99,"items":[]}'],
		['a past version', '{"version":0,"items":[]}'],
		['no version', '{"items":[]}']
	])('refuses %s without destroying it', (_reason, stored) => {
		const read = readBasket(stored);
		expect(read.basket).toEqual(emptyBasket());
		expect(read.unreadable).toBeTruthy();
		expect(read.unreadable).toContain('untouched');
	});

	it('names the version it found and the one it reads', () => {
		const read = readBasket('{"version":99,"items":[]}');
		expect(read.unreadable).toContain('99');
		expect(read.unreadable).toContain(String(BASKET_VERSION));
	});

	// A single malformed row must not cost the reader the rest of the basket.
	it('keeps the rows it can read and drops only the ones it cannot', () => {
		const stored = JSON.stringify({
			version: BASKET_VERSION,
			items: [item(), { kind: 'occurrence', note: 'no id' }, null, 'nonsense']
		});
		const read = readBasket(stored);
		expect(read.basket.items).toHaveLength(1);
		expect(read.unreadable).toBeNull();
	});

	it('reads a speech item back as a speech item', () => {
		const meeting = {
			basename: 'UNSC_2014_SPV.7000',
			spv: 'S/PV.7000',
			date: '2014-06-11',
			topic: 'Protection of civilians',
			agenda: 'Protection of civilians'
		} as Meeting;
		const speech = {
			id: 'UNSC_2014_SPV.7000_spch0001',
			country: 'Rwanda',
			speaker: 'Mr. Gasana',
			role: 'Permanent Representative'
		} as Speech;
		const entry = speechItem(meeting, speech, EXPORTED, stamps);
		const read = readBasket(serializeBasket(filled(entry)));
		expect(read.basket.items[0]).toEqual(entry);
	});
});

describe('changing a basket', () => {
	it('adds an item and reports no refusal', () => {
		const change = addItem(emptyBasket(), item());
		expect(change.basket.items).toHaveLength(1);
		expect(change.refused).toBeNull();
	});

	it('refuses a duplicate in words rather than adding it twice', () => {
		const change = addItem(filled(item()), item());
		expect(change.basket.items).toHaveLength(1);
		expect(change.refused).toBe('That is already in the basket.');
	});

	// Refuses rather than evicting: dropping the oldest item would delete a
	// note nobody asked to delete.
	it('refuses beyond its limit and keeps every item it holds', () => {
		const full = filled(
			...Array.from({ length: MAX_ITEMS }, (_, index) => item({ id: `occurrence#${index}` }))
		);
		const change = addItem(full, item({ id: 'one-too-many' }));
		expect(change.basket.items).toHaveLength(MAX_ITEMS);
		expect(change.refused).toContain(String(MAX_ITEMS));
		expect(holds(change.basket, 'one-too-many')).toBe(false);
	});

	it('writes a note', () => {
		const change = setNote(filled(item()), item().id, 'The denial reading.');
		expect(change.basket.items[0].note).toBe('The denial reading.');
		expect(change.refused).toBeNull();
	});

	// Truncation would silently alter what a reader wrote.
	it('refuses an over-long note rather than cutting it', () => {
		const long = 'x'.repeat(MAX_NOTE + 1);
		const change = setNote(filled(item()), item().id, long);
		expect(change.basket.items[0].note).toBe('');
		expect(change.refused).toContain(String(MAX_NOTE));
	});

	it('removes by id and leaves the others', () => {
		const basket = filled(item({ id: 'a#1' }), item({ id: 'b#1' }));
		expect(removeItem(basket, 'a#1').basket.items.map((entry) => entry.id)).toEqual(['b#1']);
	});
});

describe('snapshotting what a view already holds', () => {
	it('copies the sentence and its identifying context', () => {
		const entry = occurrenceItem(line(), 'genocide', EXPORTED, stamps);
		expect(entry.snapshot.sentence).toBe('We warned that genocide could occur.');
		expect(entry.snapshot.spv).toBe('S/PV.7000');
		expect(entry.snapshot.country).toBe('Rwanda');
		expect(entry.lexiconVersion).toBe(2);
		expect(entry.analysisHash).toBe('abc123');
	});

	// The KWIC file carries the delegation; the personal name lives on the
	// speech, so it is present only when the reader came from a loaded meeting.
	it('omits the personal speaker when no speech was supplied', () => {
		expect(occurrenceItem(line(), 'genocide', EXPORTED, stamps).snapshot.speaker).toBeUndefined();
	});

	it('takes the personal speaker from a speech when there is one', () => {
		const speech = { speaker: 'Mr. Gasana', role: 'Permanent Representative' } as Speech;
		const entry = occurrenceItem(line(), 'genocide', EXPORTED, stamps, speech);
		expect(entry.snapshot.speaker).toBe('Mr. Gasana');
		expect(entry.snapshot.role).toBe('Permanent Representative');
	});
});

describe('whether an item still matches the corpus on the site', () => {
	it('is current when the versions agree', () => {
		expect(currencyOf(item(), 2)).toBe('current');
	});

	it('is stale when they do not', () => {
		expect(currencyOf(item(), 3)).toBe('stale');
	});

	// "may have moved" and "has moved" are a caution and a false alarm; an
	// unknown version must never be reported as the second.
	it('is unknown rather than stale when either version is missing', () => {
		expect(currencyOf(item(), null)).toBe('unknown');
		expect(currencyOf(item({ lexiconVersion: null }), 2)).toBe('unknown');
		expect(currencyOf(item({ lexiconVersion: null }), null)).toBe('unknown');
	});
});

describe('exporting a basket', () => {
	const request = {
		basket: filled(item({ note: 'Denial, not warning.' })),
		exported: EXPORTED,
		currentLexicon: 2,
		permalink
	};

	it('leads with provenance, and says where the per-row stamps are', () => {
		const csv = basketCsv(request);
		expect(csv).toContain('# Genocide at the Security Council');
		expect(csv).toContain(`# exported: ${EXPORTED}`);
		expect(csv).toContain('# site lexicon version: 2');
		expect(csv).toContain('# licence: CC BY 4.0');
		expect(csv).toContain('each row carries the lexicon version and analytical hash');
	});

	it('writes one row per item under the declared columns', () => {
		const csv = basketCsv(request);
		const rows = csv.split('\r\n').filter((row) => row && !row.startsWith('#'));
		expect(rows[0]).toBe(BASKET_COLUMNS.join(','));
		expect(rows).toHaveLength(2);
		expect(rows[1]).toContain('UNSC_2014_SPV.7000_spch0001#1');
		expect(rows[1]).toContain('current');
		expect(rows[1]).toContain('https://example.org/');
	});

	// `csvField`'s rule, inherited deliberately: quote for the format's sake and
	// not otherwise, so numeric columns do not arrive in a spreadsheet as text.
	it('quotes only the fields the format requires it to', () => {
		const row = basketCsv(request)
			.split('\r\n')
			.find((line) => line.includes('spch0001#1'))!;
		expect(row).toContain('We warned that genocide could occur.,');
		expect(row).toContain('"Denial, not warning."');
	});

	it('records a stale row as stale, with the version it was taken under', () => {
		const csv = basketCsv({ ...request, currentLexicon: 3 });
		expect(csv).toContain('# site lexicon version: 3');
		const row = csv.split('\r\n').find((line) => line.includes('spch0001#1'));
		expect(row).toContain('stale');
		expect(row).toContain('2');
	});

	it('exports JSON that reads back as the envelope it saved', () => {
		const parsed = JSON.parse(basketJson(request));
		expect(parsed.version).toBe(BASKET_VERSION);
		expect(parsed.items).toHaveLength(1);
		expect(parsed.items[0].id).toBe('UNSC_2014_SPV.7000_spch0001#1');
		expect(parsed.items[0].currency).toBe('current');
		expect(parsed.licence).toBe('CC BY 4.0');
		expect(
			readBasket(JSON.stringify({ version: parsed.version, items: parsed.items })).basket.items
		).toHaveLength(1);
	});

	it('writes markdown that keeps the quotation a quotation', () => {
		const markdown = basketMarkdown(request);
		expect(markdown).toContain('> We warned that genocide could occur.');
		expect(markdown).toContain('Rwanda, UN Security Council, S/PV.7000 (2014-06-11).');
		expect(markdown).toContain('occurrence UNSC_2014_SPV.7000_spch0001#1.');
		expect(markdown).toContain('**Note.** Denial, not warning.');
	});

	it('says in the markdown when an item predates the current lexicon', () => {
		const markdown = basketMarkdown({ ...request, currentLexicon: 3 });
		expect(markdown).toContain('Recorded under lexicon version 2');
		expect(markdown).toContain('as recorded');
	});

	it('exports an empty basket without inventing rows', () => {
		const empty = { ...request, basket: emptyBasket() };
		expect(
			basketCsv(empty)
				.split('\r\n')
				.filter((row) => row && !row.startsWith('#'))
		).toEqual([BASKET_COLUMNS.join(',')]);
		expect(JSON.parse(basketJson(empty)).items).toEqual([]);
	});

	it('names the file for the day it was exported', () => {
		expect(basketFilename(EXPORTED, 'csv')).toBe('unsc-basket-2026-08-27.csv');
		expect(basketFilename(EXPORTED, 'md')).toBe('unsc-basket-2026-08-27.md');
	});
});
