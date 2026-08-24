import { describe, expect, it } from 'vitest';
import type { AnnualSeries, BaseMeta, LexiconMeta, SpeakerKeyness } from './types';

const base: BaseMeta = {
	script: '12_speaker_keyness.py',
	generated: '2026-08-24T00:00:00Z'
};

const lexicon: LexiconMeta = {
	...base,
	script: '04_series.py',
	lexicon_version: 2
};

const speakerKeynessMeta: SpeakerKeyness['meta'] = base;
const annualSeriesMeta: AnnualSeries['meta'] = lexicon;

// The producer does not write this field for speaker keyness, so its metadata
// must remain usable without inventing one.
const noInventedLexiconVersion: SpeakerKeyness['meta'] = {
	script: '12_speaker_keyness.py',
	generated: '2026-08-24T00:00:00Z'
};

// @ts-expect-error A series cannot be typed without the lexicon that defines its measures.
const seriesWithoutLexicon: AnnualSeries['meta'] = base;

describe('artifact metadata types', () => {
	it('distinguish universal provenance from lexicon-dependent provenance', () => {
		expect(speakerKeynessMeta.lexicon_version).toBeUndefined();
		expect(noInventedLexiconVersion.lexicon_version).toBeUndefined();
		expect(annualSeriesMeta.lexicon_version).toBe(2);
		expect(seriesWithoutLexicon.lexicon_version).toBeUndefined();
	});
});
