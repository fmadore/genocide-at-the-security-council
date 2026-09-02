/**
 * What the filled map decides, tested apart from how it is drawn.
 *
 * `docs/PLAN.md` §7.3 refused a choropleth for one reason: a fill is keyed on
 * ISO3 and two codes in this corpus are shared, so a fill keyed on the code
 * paints one speaker's rate over another's silently. The view exists now
 * because that is preventable, and the prevention is a function rather than a
 * sentence in a caveat — so it is tested here, including the branch the present
 * corpus never reaches.
 *
 * Four things can go wrong in ways that look right on screen, and all four are
 * checked: a shared code filled with one holder's number, a below-minimum
 * speaker painted the colour of a state that never spoke, a ramp anchored on the
 * smallest country so a silent delegation looks merely quiet, and a micro-state
 * dropped out of the figure because Natural Earth has no polygon for it.
 */

import { describe, expect, it } from 'vitest';
import { plan } from './actors';
import type { ActorPlan, ActorRow } from './actors';
import { fills, withoutPolygon } from './choropleth';
import { tone } from './theme';
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
	speech_rate_low: 0.034,
	speech_rate_high: 0.073,
	sufficient: true,
	occurrences: 60,
	token_rate: 12,
	...extra
});

const corpus = (
	speakers: Speaker[],
	rows: CountryMeasureRow[],
	collisions: Record<string, string[]> = {}
): Countries => ({
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
	// A different question over the same artefact, exercised in
	// `standing.test.ts`; it is here only because the payload carries it.
	standing: {
		groups: ['P5', 'E10', 'Non-member state', 'UN', 'Non-state'],
		seated_groups: ['P5', 'E10'],
		seated_rule: 'P5 and E10 are the Charter’s two kinds of membership.',
		membership_rule: 'Membership is a property of a speech, not of a country.',
		rows: []
	},
	measures: { genocide: { kind: 'terms', tier: 'core', register: 'core', rows } }
});

/** The rate, which is what the actor page ranks by unless asked otherwise. */
const rate = (entry: ActorRow) => entry.row.speech_rate ?? 0;

const planned = (data: Countries): ActorPlan => plan({ data, measure: 'genocide', period: 'all' });

const at = (result: ReturnType<typeof fills>, iso3: string) =>
	result.patches.find((patch) => patch.iso3 === iso3);

describe('fills', () => {
	it('refuses to fill a code two drawable speakers hold', () => {
		// The branch the present corpus never reaches: of the two shared codes,
		// only one holder each ever clears the minimum. The day that changes, the
		// map must say so rather than paint one rate over the other.
		const data = corpus(
			[
				speaker('Yugoslavia', { iso3: 'SRB' }),
				speaker('Serbia', { iso3: 'SRB' }),
				speaker('Kenya', { iso3: 'KEN' })
			],
			[
				row('Yugoslavia', { speech_rate: 0.2 }),
				row('Serbia', { speech_rate: 0.04 }),
				row('Kenya', { speech_rate: 0.08 })
			],
			{ SRB: ['Serbia', 'Yugoslavia'] }
		);
		const result = fills(planned(data), new Set(['SRB']), rate);

		const srb = at(result, 'SRB');
		expect(srb?.state).toBe('contested');
		expect(srb?.value).toBeNull();
		// No key means no selection: choosing one of the two would be the failure
		// this state exists to refuse, committed in the interaction layer instead.
		expect(srb?.key).toBeNull();
		expect(srb?.holders).toHaveLength(2);
		expect(result.contested).toBe(1);

		// And the contested rate never reaches the range: 0.2 is the largest
		// number in the slice and is not the top of the ramp.
		expect(result.high).toBeCloseTo(0.08);
	});

	it('marks a code as shared even when only one holder is drawable', () => {
		const data = corpus(
			[speaker('Zaire', { iso3: 'COD' }), speaker('Congo', { iso3: 'COD' })],
			[
				row('Zaire', { held: 40, speech_rate: null, sufficient: false }),
				row('Congo', { speech_rate: 0.06 })
			],
			{ COD: ['Congo', 'Zaire'] }
		);
		const result = fills(planned(data), new Set(['COD']), rate);

		const cod = at(result, 'COD');
		expect(cod?.state).toBe('drawn');
		expect(cod?.key).toBe('Congo');
		// Both holders travel with the patch, so the hover box can name the one
		// whose rate is not being shown.
		expect(cod?.holders).toEqual(['Congo', 'Zaire']);
		expect(cod?.shared).toBe(true);
	});

	it('separates a withheld speaker from one that never spoke', () => {
		const data = corpus(
			[speaker('Alpha'), speaker('Bravo')],
			[row('Alpha'), row('Bravo', { held: 40, speech_rate: null, sufficient: false })]
		);
		const result = fills(planned(data), new Set(), rate);

		expect(at(result, 'BRA')?.state).toBe('withheld');
		expect(at(result, 'BRA')?.value).toBeNull();
		expect(result.withheld).toBe(1);
		// A state that is not in the corpus at all has no patch, so the renderer
		// has nothing to fill it with. That is the distinction: absence of a patch
		// is absence of a speaker, and it can never be confused with a grey one.
		expect(at(result, 'ZZZ')).toBeUndefined();
	});

	it('anchors the ramp at zero, not at the quietest country', () => {
		const data = corpus(
			[speaker('Alpha'), speaker('Bravo'), speaker('Charlie')],
			[
				row('Alpha', { speech_rate: 0 }),
				row('Bravo', { speech_rate: 0.05 }),
				row('Charlie', { speech_rate: 0.1 })
			]
		);
		const result = fills(planned(data), new Set(), rate);

		expect(result.high).toBeCloseTo(0.1);
		// A delegation that cleared the minimum and never used the word sits at
		// the bottom of the ramp. Anchored on the smallest observed value it would
		// have sat there too — but so would a country at 0.049, which is the
		// failure: the floor has to mean zero.
		expect(at(result, 'ALP')?.tone).toBe(0);
		expect(at(result, 'BRA')?.tone).toBeCloseTo(tone(0.5));
		expect(at(result, 'CHA')?.tone).toBe(1);
	});

	it('leaves every patch at the floor when nothing distinguishes them', () => {
		const data = corpus([speaker('Alpha')], [row('Alpha', { speech_rate: 0 })]);
		const result = fills(planned(data), new Set(), rate);
		expect(result.high).toBe(0);
		expect(at(result, 'ALP')?.tone).toBe(0);
	});

	it('draws no speaker the artefact says is not mappable', () => {
		// The UN Secretariat is among the largest speakers in the corpus and
		// belongs on no globe. `mappable` is read rather than inferred from the
		// presence of a code, so it is excluded on purpose.
		const data = corpus(
			[speaker('Alpha'), speaker('Secretariat', { mappable: false, entity_type: 'un' })],
			[row('Alpha'), row('Secretariat')]
		);
		const result = fills(planned(data), new Set(), rate);
		expect(result.patches).toHaveLength(1);
		expect(at(result, 'SEC')).toBeUndefined();
	});

	it('carries the centroid as longitude first, whatever the artefact writes', () => {
		// `config/entities.csv` records `lat, lon` because that reads naturally to
		// a person; MapLibre wants the other order. Flipping it in one place is
		// the point, and the test is here because nothing on screen would look
		// wrong — a country would simply be marked in the wrong ocean.
		const data = corpus([speaker('Alpha', { centroid: [-1.5, 30.5] })], [row('Alpha')]);
		const result = fills(planned(data), new Set(), rate);
		expect(at(result, 'ALP')?.lngLat).toEqual([30.5, -1.5]);
	});

	it('orders patches by code so the paint expression is stable', () => {
		const data = corpus(
			[speaker('Zulu'), speaker('Alpha'), speaker('Mike')],
			[row('Zulu'), row('Alpha'), row('Mike')]
		);
		const codes = fills(planned(data), new Set(), rate).patches.map((patch) => patch.iso3);
		expect(codes).toEqual([...codes].sort());
	});
});

describe('withoutPolygon', () => {
	it('keeps the speakers the boundary file cannot draw', () => {
		// Natural Earth's 1:110m sheet omits states below a size threshold, and
		// seven drawable speakers in this corpus are among them. Losing them
		// silently would be a figure that claims to hold every ranked row.
		const data = corpus(
			[speaker('Malta', { iso3: 'MLT' }), speaker('Kenya', { iso3: 'KEN' })],
			[row('Malta'), row('Kenya')]
		);
		const result = fills(planned(data), new Set(), rate);
		const missing = withoutPolygon(result, new Set(['KEN']));
		expect(missing.map((patch) => patch.iso3)).toEqual(['MLT']);
	});

	it('will not place a speaker that has no centroid', () => {
		// Unreachable — `mappable` requires a centroid — and a speaker drawn at
		// 0°N 0°E is a worse failure than one absent from a figure whose table
		// holds every row.
		const data = corpus([speaker('Alpha', { centroid: null })], [row('Alpha')]);
		const result = fills(planned(data), new Set(), rate);
		expect(withoutPolygon(result, new Set()).map((patch) => patch.iso3)).toEqual([]);
	});
});
