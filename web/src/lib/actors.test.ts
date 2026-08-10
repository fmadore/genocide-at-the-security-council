/**
 * What the actor view decides, tested apart from how it is drawn.
 *
 * `docs/PLAN.md` §7.3 names the three ways this view can be wrong while looking
 * right: a sub-minimum slice drawn as though it were a rate, two speakers
 * collapsed because they share an ISO3, and a centroid read as the place a
 * diplomat spoke from. The first two are arithmetic and are tested here. The
 * third is a sentence in the interface, and `actors.svelte.test` has no way to
 * check that a reader read it — what is checked instead is that the artefact's
 * own `centroid_rule` is what gets shown, rather than a paraphrase that could
 * drift from it.
 */

import { describe, expect, it } from 'vitest';
import { ambiguous, plan, points, scale } from './actors';
import type { Countries, CountryMeasureRow, Speaker } from './types';

const meta = { script: '11_countries.py', generated: '2026-08-10T00:00:00Z', lexicon_version: 4 };

const speaker = (name: string, extra: Partial<Speaker> = {}): Speaker => ({
	country_org: name,
	entity_type: 'state',
	iso3: name.slice(0, 3).toUpperCase(),
	un_regional_group: 'African Group',
	centroid: [10, 20],
	mappable: true,
	speeches: 500,
	first_year: 1992,
	last_year: 2023,
	...extra
});

const row = (name: string, extra: Partial<CountryMeasureRow> = {}): CountryMeasureRow => ({
	country_org: name,
	period: 'all',
	held: 500,
	tokens: 500_000,
	speeches: 25,
	speech_rate: 0.05,
	sufficient: true,
	occurrences: 60,
	token_rate: 12,
	...extra
});

const corpus = (speakers: Speaker[], rows: CountryMeasureRow[], collisions = {}): Countries => ({
	meta,
	minimum_speeches: 100,
	minimum_speeches_rule: 'withheld below 100 speeches',
	rate_per_tokens: 100_000,
	centroid_rule: 'Country centroids are navigation aids.',
	iso3_collisions: collisions,
	periods: [
		{
			key: 'all',
			label: '1992-2023',
			first_year: 1992,
			last_year: 2023,
			speeches: 106_302,
			tokens: 66_392_703,
			speakers: speakers.length,
			speakers_at_minimum: rows.filter((r) => r.sufficient).length,
			speeches_at_minimum: 103_038
		}
	],
	countries: speakers,
	measures: { genocide: { kind: 'terms', tier: 'core', register: 'core', rows } }
});

describe('the minimum-sample gate', () => {
	it('draws only the slices the artefact called sufficient', () => {
		const data = corpus(
			[speaker('Alpha'), speaker('Bravo'), speaker('Charlie')],
			[
				row('Alpha'),
				row('Bravo', { held: 40, speeches: 0, speech_rate: null, sufficient: false }),
				row('Charlie', { speech_rate: 0.09 })
			]
		);
		const result = plan({ data, measure: 'genocide', period: 'all' });
		expect(result.rows.map((entry) => entry.speaker.country_org)).toEqual(['Charlie', 'Alpha']);
		expect(result.withheld).toBe(1);
		expect(result.minimum).toBe(100);
	});

	it('reports a withheld count rather than ranking the near misses', () => {
		const data = corpus(
			[speaker('Alpha'), speaker('Bravo')],
			[
				row('Alpha', { held: 99, speech_rate: null, sufficient: false }),
				row('Bravo', { held: 12, speech_rate: null, sufficient: false })
			]
		);
		const result = plan({ data, measure: 'genocide', period: 'all' });
		expect(result.rows).toEqual([]);
		expect(result.withheld).toBe(2);
		expect(result.refusal).toBe('none-sufficient');
	});

	it('does not recompute the threshold it was handed', () => {
		// `held` is under the minimum but the artefact says sufficient. The
		// artefact wrote the rates and is the authority; a second implementation
		// of the rule here could only drift from the one that made the data.
		const data = corpus([speaker('Alpha')], [row('Alpha', { held: 4 })]);
		expect(plan({ data, measure: 'genocide', period: 'all' }).rows).toHaveLength(1);
	});
});

describe('refusals', () => {
	it('names a measure that is not in the artefact', () => {
		const data = corpus([speaker('Alpha')], [row('Alpha')]);
		expect(plan({ data, measure: 'nope', period: 'all' }).refusal).toBe('no-measure');
	});

	it('names a period that is not in the artefact', () => {
		const data = corpus([speaker('Alpha')], [row('Alpha')]);
		expect(plan({ data, measure: 'genocide', period: '1970s' }).refusal).toBe('no-period');
	});

	it('drops a measure row whose speaker the country table does not list', () => {
		const data = corpus([speaker('Alpha')], [row('Alpha'), row('Ghost')]);
		const result = plan({ data, measure: 'genocide', period: 'all' });
		expect(result.rows).toHaveLength(1);
	});
});

describe('ordering', () => {
	it('ranks by the figure asked for, not always by rate', () => {
		const data = corpus(
			[speaker('Alpha'), speaker('Bravo')],
			[
				row('Alpha', { speech_rate: 0.9, speeches: 2 }),
				row('Bravo', { speech_rate: 0.1, speeches: 400 })
			]
		);
		const byRate = plan({ data, measure: 'genocide', period: 'all', order: 'speech_rate' });
		const byCount = plan({ data, measure: 'genocide', period: 'all', order: 'speeches' });
		expect(byRate.rows[0].speaker.country_org).toBe('Alpha');
		expect(byCount.rows[0].speaker.country_org).toBe('Bravo');
	});

	it('breaks ties by name so a table does not reorder between renders', () => {
		const data = corpus(
			[speaker('Zulu'), speaker('Alpha')],
			[row('Zulu', { speech_rate: 0.5 }), row('Alpha', { speech_rate: 0.5 })]
		);
		const order = () =>
			plan({ data, measure: 'genocide', period: 'all' }).rows.map((e) => e.speaker.country_org);
		expect(order()).toEqual(['Alpha', 'Zulu']);
		expect(order()).toEqual(order());
	});
});

describe('ISO3 collisions', () => {
	const collisions = { SRB: ['Serbia', 'Serbia And Montenegro', 'Yugoslavia'], COD: ['DRC'] };

	it('counts a code as ambiguous only when more than one speaker holds it', () => {
		const data = corpus([], [], collisions);
		expect(ambiguous(data)).toEqual(new Set(['SRB']));
	});

	it('never merges two speakers that share a code', () => {
		const data = corpus(
			[
				speaker('Serbia', { iso3: 'SRB', centroid: [44, 21] }),
				speaker('Yugoslavia', { iso3: 'SRB', centroid: [44, 21] })
			],
			[row('Serbia'), row('Yugoslavia')],
			collisions
		);
		const result = plan({ data, measure: 'genocide', period: 'all' });
		expect(result.rows).toHaveLength(2);
		// One marker, because the centroid is one place — but it stands for two
		// rows and knows it, which is what lets the interface say so.
		const drawn = points(result.rows, ambiguous(data));
		expect(drawn).toHaveLength(1);
		expect(drawn[0].speakers).toHaveLength(2);
		expect(drawn[0].shared).toBe(true);
	});

	it('leaves an unshared code unflagged', () => {
		const data = corpus([speaker('Kenya', { iso3: 'KEN' })], [row('Kenya')], collisions);
		const drawn = points(plan({ data, measure: 'genocide', period: 'all' }).rows, ambiguous(data));
		expect(drawn[0].shared).toBe(false);
	});
});

describe('what may be drawn on a map', () => {
	it('reads the mappable flag rather than inferring from coordinates', () => {
		// The UN Secretariat is among the largest speakers in the corpus and
		// belongs on no globe. Give it coordinates anyway: a truthiness test on
		// `centroid` would put it on the map, and the flag is what stops that.
		const data = corpus(
			[
				speaker('Kenya'),
				speaker('United Nations', {
					entity_type: 'un',
					mappable: false,
					centroid: [40, -73],
					iso3: null
				})
			],
			[row('Kenya'), row('United Nations')]
		);
		const drawn = points(plan({ data, measure: 'genocide', period: 'all' }).rows, new Set());
		expect(drawn).toHaveLength(1);
		expect(drawn[0].speakers[0].speaker.country_org).toBe('Kenya');
	});

	it('flips the artefact latitude/longitude into MapLibre order', () => {
		// `entities.csv` records lat,lon; MapLibre wants lon,lat. Afghanistan is
		// north and east of the origin, so a flip that went the wrong way would
		// put it in the Indian Ocean.
		const data = corpus(
			[speaker('Afghanistan', { centroid: [34.134, 66.5922] })],
			[row('Afghanistan')]
		);
		const drawn = points(plan({ data, measure: 'genocide', period: 'all' }).rows, new Set());
		expect(drawn[0].lngLat).toEqual([66.5922, 34.134]);
	});

	it('draws nothing for a speaker with no centroid', () => {
		const data = corpus(
			[speaker('Nowhere', { centroid: null, mappable: false })],
			[row('Nowhere')]
		);
		expect(points(plan({ data, measure: 'genocide', period: 'all' }).rows, new Set())).toEqual([]);
	});
});

describe('the marker scale', () => {
	it('spans the drawn range', () => {
		const at = scale([1, 5, 9]);
		expect(at(1)).toBe(0);
		expect(at(9)).toBe(1);
		expect(at(5)).toBeCloseTo(0.5);
	});

	it('puts a flat range in the middle rather than at nothing', () => {
		expect(scale([3, 3, 3])(3)).toBe(0.5);
		expect(scale([])(0)).toBe(0.5);
	});
});
