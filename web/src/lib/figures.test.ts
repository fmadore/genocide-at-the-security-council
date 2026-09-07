import { describe, expect, it } from 'vitest';
import { figureId, slug, provenance } from './figures';

describe('figure ids', () => {
	it('slugs a title into an anchor', () => {
		expect(slug("The vocabulary's calendar")).toBe('the-vocabulary-s-calendar');
		expect(slug('Occurrences and share of speeches, 1992&ndash;2023')).toBe(
			'occurrences-and-share-of-speeches-1992-2023'
		);
	});

	it('lets a figure keep an id it already had', () => {
		expect(figureId({ title: 'Anything', id: 'speaker-keyness' })).toBe('speaker-keyness');
		expect(figureId({ title: 'Keyword in context' })).toBe('keyword-in-context');
	});
});

it('derives provenance from every contributing source', () => {
	expect(provenance('04_series.py → annual.json')).toBe('computed');
	expect(provenance('15_usage.py → usage.json')).toBe('model');
	expect(provenance('08_kwic.py; 15_usage.py')).toBe('mixed');
	expect(() => provenance('unrecorded source')).toThrow();
});
