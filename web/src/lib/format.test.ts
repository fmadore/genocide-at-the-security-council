import { describe, expect, it } from 'vitest';
import {
	interpretedFrom,
	measureLabel,
	meetingBase,
	meetingLabel,
	namedLanguage,
	termLabel,
	unSearch
} from './format';

describe('meeting symbols', () => {
	it('prints a resumed sitting the way the record is titled', () => {
		expect(meetingLabel('S/PV.3745Resumption1')).toBe('S/PV.3745 (Resumption 1)');
		expect(meetingLabel('S/PV.7155')).toBe('S/PV.7155');
	});

	it('searches the Digital Library by the base symbol', () => {
		expect(meetingBase('S/PV.3745Resumption2')).toBe('S/PV.3745');
		expect(unSearch('S/PV.3745Resumption2')).toContain(encodeURIComponent('S/PV.3745'));
		expect(unSearch('S/PV.3745Resumption2')).not.toContain('Resumption');
	});
});

/** Measure identifiers are displayed consistently with term identifiers. */
describe('measure names', () => {
	it('names the derived measure rather than printing its key', () => {
		expect(measureLabel('genocide')).toBe('genocide');
	});

	it('falls back to the underscores stripped out, as the term label always did', () => {
		expect(measureLabel('crimes_against_humanity')).toBe(termLabel('crimes_against_humanity'));
		expect(measureLabel('genocide')).toBe('genocide');
	});
});

/**
 * The language field, which names a language on none of the corpus's speeches.
 *
 * Every speech carries `Unknown`. Read as "not English" it made the reader's
 * apparatus report a meeting held in English as one where every speech carried
 * a non-English label, and printed "spoke in Unknown" under every speaker.
 */
describe('the delivery-language field', () => {
	it('treats the corpus sentinel as an absent value, because that is what it is', () => {
		expect(namedLanguage('Unknown')).toBe(false);
		expect(namedLanguage('unknown')).toBe(false);
		expect(namedLanguage(null)).toBe(false);
		expect(namedLanguage(undefined)).toBe(false);
		expect(namedLanguage('')).toBe(false);
	});

	it('keeps a language the record actually names', () => {
		expect(namedLanguage('French')).toBe(true);
		expect(namedLanguage('English')).toBe(true);
	});

	it('counts as interpreted only a named language other than the record’s own', () => {
		expect(interpretedFrom('French')).toBe(true);
		expect(interpretedFrom('Spanish')).toBe(true);
		expect(interpretedFrom('English')).toBe(false);
		expect(interpretedFrom('english')).toBe(false);
		// The one that mattered: a sentinel is not a foreign language.
		expect(interpretedFrom('Unknown')).toBe(false);
		expect(interpretedFrom(null)).toBe(false);
	});
});
