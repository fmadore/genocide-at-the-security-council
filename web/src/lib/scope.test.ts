import { describe, expect, it } from 'vitest';
import { DEFAULT_SCOPE, readScope, withScope } from './scope';

describe('the corpus scope URL contract', () => {
	it('keeps an old URL on the word scope', () => {
		expect(readScope(new URLSearchParams())).toBe(DEFAULT_SCOPE);
	});

	it('falls back from an unknown scope without preserving it', () => {
		const params = new URLSearchParams('scope=everything&term=genocide');
		expect(readScope(params)).toBe('word');
		expect(withScope(params, readScope(params)).toString()).toBe('term=genocide');
	});

	it('carries a non-default scope without dropping page filters', () => {
		const params = withScope(new URLSearchParams('term=war_crimes&from=1992'), 'debate');
		expect(params.get('scope')).toBe('debate');
		expect(params.get('term')).toBe('war_crimes');
		expect(params.get('from')).toBe('1992');
	});

	it('removes the default from a previously scoped URL', () => {
		const params = withScope(new URLSearchParams('scope=vocabulary&series=genocide'), 'word');
		expect(params.toString()).toBe('series=genocide');
	});
});
