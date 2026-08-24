import { describe, expect, it } from 'vitest';
import { occurrenceQuotation } from './citation';
import type { KwicLine } from './types';

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
