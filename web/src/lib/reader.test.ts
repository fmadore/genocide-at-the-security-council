import { describe, expect, it } from 'vitest';
import { exactSpan, segments, visible, type Selection } from './reader';
import type { Speech } from './types';

// The speaker line is the first 15 characters; "prevention of genocide" is 31–53.
const text = 'Mr. President: We call for the prevention of genocide now.';

const speech = (over: Partial<Speech> = {}): Speech =>
	({
		id: 'SC07000-01-001',
		body_start: 15,
		text,
		hits: {
			genocide: [[45, 53]],
			prevention_of_genocide: [[31, 53]]
		},
		...over
	}) as Speech;

const none: Selection = { occurrence: null, term: null };
const joined = (parts: { text: string }[]) => parts.map((part) => part.text).join('');

describe('the span the URL names', () => {
	const selected: Selection = { occurrence: 'SC07000-01-001#1', term: 'genocide' };

	it('is the ordinal’s span under its own term', () => {
		expect(exactSpan(speech(), 'genocide', selected)).toEqual([45, 53]);
	});

	it('names nothing under another term, under all terms, or in another speech', () => {
		expect(exactSpan(speech(), 'prevention_of_genocide', selected)).toBeNull();
		expect(exactSpan(speech(), null, selected)).toBeNull();
		expect(exactSpan(speech({ id: 'SC07000-01-002' }), 'genocide', selected)).toBeNull();
	});

	it('names nothing for an ordinal past the speech’s matches or without one', () => {
		expect(
			exactSpan(speech(), 'genocide', { occurrence: 'SC07000-01-001#2', term: 'genocide' })
		).toBeNull();
		expect(
			exactSpan(speech(), 'genocide', { occurrence: 'SC07000-01-001', term: 'genocide' })
		).toBeNull();
	});
});

describe('cutting a speech into runs', () => {
	it('merges overlapping spans into one mark that names every term it covers', () => {
		const runs = segments(speech(), null, none);
		expect(runs.map((run) => run.terms)).toEqual([[], ['prevention_of_genocide', 'genocide'], []]);
		expect(runs[1]?.text).toBe('prevention of genocide');
		expect(joined(runs)).toBe(text);
	});

	it('marks only the chosen term when one is chosen', () => {
		const runs = segments(speech(), 'genocide', none);
		expect(runs.filter((run) => run.terms.length).map((run) => run.text)).toEqual(['genocide']);
	});

	it('marks the run holding the named occurrence as the exact one', () => {
		const runs = segments(speech(), 'genocide', {
			occurrence: 'SC07000-01-001#1',
			term: 'genocide'
		});
		expect(runs.filter((run) => run.exact).map((run) => run.text)).toEqual(['genocide']);
	});

	it('returns the whole text as one run when nothing is marked', () => {
		expect(segments(speech({ hits: {} }), null, none)).toEqual([{ text, terms: [], exact: false }]);
	});
});

describe('what the reader shows', () => {
	it('drops the speaker line unless it is asked for', () => {
		expect(joined(visible(speech(), null, none, false))).toBe(text.slice(15));
		expect(joined(visible(speech(), null, none, true))).toBe(text);
	});

	it('cuts a mark that straddles the speaker line rather than losing it', () => {
		const runs = visible(speech({ hits: { president: [[4, 20]] } }), null, none, false);
		expect(runs[0]).toEqual({ text: 'We ca', terms: ['president'], exact: false });
	});

	it('shows everything for a speech with no speaker line', () => {
		expect(joined(visible(speech({ body_start: 0 }), null, none, false))).toBe(text);
	});
});
