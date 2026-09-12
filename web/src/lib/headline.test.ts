import { describe, expect, it } from 'vitest';
import { HEADLINE, headlineMeasure } from './headline';

describe('the measure a view opens on', () => {
	it('uses the full word family even when the optional exclusion is available', () => {
		expect(headlineMeasure(['war_crimes', 'genocide', 'genocide_qualification'])).toBe('genocide');
	});

	it('falls back to the raw term on an artefact cut before lexicon v4', () => {
		/* The e2e fixtures are such an artefact. The home page crashed on them
		   once, reading the derived key directly, and the CI journey that exports
		   the headline figure caught it. */
		expect(headlineMeasure(['genocide', 'war_crimes'])).toBe('genocide');
	});

	it('does not select the retired exclusion', () => {
		expect(headlineMeasure(['genocide_qualification'])).toBeUndefined();
	});

	it('is undefined, not the first thing that sorts, when neither is there', () => {
		expect(headlineMeasure(['war_crimes'])).toBeUndefined();
		expect(headlineMeasure([])).toBeUndefined();
	});

	it('prefers the full word family whatever order the artefact lists them in', () => {
		expect(headlineMeasure(new Set(['genocide_qualification', 'genocide']))).toBe(HEADLINE[0]);
	});
});
