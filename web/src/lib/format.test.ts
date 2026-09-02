import { describe, expect, it } from 'vitest';
import { meetingBase, meetingLabel, unSearch } from './format';

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
