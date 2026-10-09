import { describe, expect, it } from 'vitest';
import { OFFLINE_KEEP, overflow } from './offline';

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
