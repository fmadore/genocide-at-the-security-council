import { describe, expect, it } from 'vitest';
import { segments } from './highlight';

const marked = (text: string, query: string, regex = false) =>
	segments(text, query, regex)
		.filter((part) => part.hit)
		.map((part) => part.text);

const rebuilt = (text: string, query: string, regex = false) =>
	segments(text, query, regex)
		.map((part) => part.text)
		.join('');

describe('marking the query in a concordance line', () => {
	it('never loses or reorders a character of the line', () => {
		// The segments are rendered in order and nothing else is. If they did not
		// rejoin to the original, the reader would be shown an edited quotation.
		const line = 'the tribunal convicts those responsible for genocide in Rwanda';
		for (const query of ['convicts', 'the', 'zzz', '', 'Rwanda']) {
			expect(rebuilt(line, query)).toBe(line);
		}
	});

	it('marks every occurrence, not only the first', () => {
		expect(marked('crimes against humanity and other crimes', 'crimes')).toEqual([
			'crimes',
			'crimes'
		]);
	});

	it('matches without regard to case but marks the text as written', () => {
		// The Council writes Genocide and genocide; a reader searching one wants
		// both, and wants to see which one the record actually used.
		expect(marked('Genocide, genocide, GENOCIDE', 'genocide')).toEqual([
			'Genocide',
			'genocide',
			'GENOCIDE'
		]);
	});

	it('treats a literal query as literal', () => {
		// Without escaping, a reader searching for `r.p` would match `rap`,
		// `rip` and `r.p` alike and never learn why.
		expect(marked('the r.p and the rap', 'r.p')).toEqual(['r.p']);
		expect(marked('cost $1.5m', '$1.5m')).toEqual(['$1.5m']);
	});

	it('honours a regular expression when the reader asked for one', () => {
		expect(marked('convicts, convicted, conviction', 'convict(s|ed)', true)).toEqual([
			'convicts',
			'convicted'
		]);
	});

	it('leaves the line whole while a regex is still half-typed', () => {
		// The search box filters as you type, so `convict(` exists for as long as
		// it takes to reach the closing bracket.
		const line = 'the tribunal convicts';
		expect(segments(line, 'convict(', true)).toEqual([{ text: line, hit: false }]);
	});

	it('marks nothing for a pattern that matches nothing at all', () => {
		// `a*` matches an empty string at every position. Marking those would
		// split the line into empty segments and highlight none of it.
		const line = 'genocide in Srebrenica';
		expect(segments(line, 'x*', true)).toEqual([{ text: line, hit: false }]);
		expect(rebuilt(line, '\\b', true)).toBe(line);
	});

	it('marks a hit that runs to the end of the line', () => {
		expect(segments('crimes against humanity', 'humanity')).toEqual([
			{ text: 'crimes against ', hit: false },
			{ text: 'humanity', hit: true }
		]);
	});

	it('marks a hit that starts at the very beginning', () => {
		expect(segments('genocide was the word', 'genocide')).toEqual([
			{ text: 'genocide', hit: true },
			{ text: ' was the word', hit: false }
		]);
	});

	it('returns an empty query as one unmarked segment', () => {
		expect(segments('anything at all', '   ')).toEqual([{ text: 'anything at all', hit: false }]);
	});

	it('caps a pathological pattern rather than building a node per character', () => {
		const line = 'genocide '.repeat(400);
		const parts = segments(line, '.', true);
		expect(parts.filter((part) => part.hit).length).toBeLessThanOrEqual(200);
		// Capped, but never truncated: what is not marked is still shown.
		expect(rebuilt(line, '.', true)).toBe(line);
	});
});
