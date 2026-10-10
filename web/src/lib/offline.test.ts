import { describe, expect, it } from 'vitest';
import { unreachable } from './data';
import { OFFLINE_KEEP, offlineCeilings, overflow } from './offline';

const root = '/site/data/';

describe('the offline cache ceiling', () => {
	it('drops the oldest files of a family past its ceiling', () => {
		const families = [{ matches: (path: string) => path.startsWith('speeches/'), keep: 2 }];
		const cached = [
			`${root}speeches/A.json.gz`,
			`${root}speeches/B.json.gz`,
			`${root}series/annual.json`,
			`${root}speeches/C.json.gz`
		];
		expect(overflow(cached, root, families)).toEqual([`${root}speeches/A.json.gz`]);
	});

	it('keeps everything while a family is within its ceiling', () => {
		const cached = Array.from({ length: 6 }, (_, index) => `${root}kwic/term-${index}.json`);
		expect(overflow(cached, root)).toEqual([]);
	});

	it('bounds the concordances and never counts their index among them', () => {
		const kwic = OFFLINE_KEEP.find((family) => family.matches('kwic/genocide.json'))!;
		const cached = [
			`${root}kwic/index.json`,
			...Array.from({ length: kwic.keep + 2 }, (_, index) => `${root}kwic/term-${index}.json`)
		];
		expect(overflow(cached, root)).toEqual([`${root}kwic/term-0.json`, `${root}kwic/term-1.json`]);
	});

	it('leaves the fixed artefacts, the pages and anything outside the data root alone', () => {
		const cached = [
			`${root}series/annual.json`,
			`${root}usage/occurrences.json`,
			`${root}semantic/map.json`,
			'/site/concordance/',
			'/site/_app/immutable/chunks/echarts.js',
			'/elsewhere/data/speeches/A.json.gz'
		];
		expect(overflow(cached, root)).toEqual([]);
	});

	it('names every ceiling in the sentence a reader offline is shown', () => {
		// The sentence is built from the ceilings, so a change to one changes the
		// copy with it: "pages already visited stay available offline" was true
		// until the meeting files got a ceiling, and nothing said so.
		expect(OFFLINE_KEEP.every((family) => family.noun)).toBe(true);
		expect(offlineCeilings()).toBe(
			'100 meeting records, 6 concordance terms and 32 related-speech files'
		);
		expect(offlineCeilings([{ matches: () => true, keep: 3, noun: 'things' }])).toBe('3 things');
		expect(unreachable('speeches/SC07000-01.json.gz')).toContain(
			'the cache keeps only the 100 meeting records, 6 concordance terms and 32 ' +
				'related-speech files opened most recently.'
		);
	});

	it('bounds every family that grows with the reading', () => {
		for (const path of [
			'kwic/genocide.json',
			'speeches/SC07000-01.json.gz',
			'semantic/neighbours/20.json'
		]) {
			expect(
				OFFLINE_KEEP.some((family) => family.matches(path)),
				path
			).toBe(true);
		}
	});
});
