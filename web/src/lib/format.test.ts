import { describe, expect, it } from 'vitest';
import { measureLabel, meetingBase, meetingLabel, termLabel, unSearch } from './format';

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

/**
 * A measure's name, where the configuration key is not one.
 *
 * `genocide_qualification` is an arithmetic instruction rather than a word, and
 * three views open on it. The table is the one place the name is decided; every
 * term that is a word still reaches a reader through the fallback, so a lexicon
 * addition needs no entry here.
 */
describe('measure names', () => {
	it('names the derived measure rather than printing its key', () => {
		expect(measureLabel('genocide_qualification')).toBe('genocide (excluding génocidaires)');
	});

	it('falls back to the underscores stripped out, as the term label always did', () => {
		expect(measureLabel('crimes_against_humanity')).toBe(termLabel('crimes_against_humanity'));
		expect(measureLabel('genocide')).toBe('genocide');
	});
});
