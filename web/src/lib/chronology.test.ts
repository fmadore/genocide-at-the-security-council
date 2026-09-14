import { describe, expect, it } from 'vitest';
import {
	chronologyParams,
	readChronologyState,
	splitEvidenceQuery,
	termStrokes,
	type ChronologyChoices,
	type ChronologyState
} from './chronology';
import type { Palette } from './theme';

const choices: ChronologyChoices = {
	series: {
		year: ['genocide', 'war_crimes', 'massacre', 'ethnic_cleansing'],
		quarter: ['genocide', 'war_crimes', 'massacre', 'ethnic_cleansing']
	},
	calendar: {
		genocide: ['speech_rate', 'token_rate'],
		// A measure the calendar can only draw as a share. Nothing in the
		// artefact withholds an occurrence count today; the reader may still ask
		// for a unit a measure is not in, and the state has to normalise it.
		war_crimes: ['speech_rate']
	},
	splits: ['none', 'speaker_group', 'delivery_language']
};

describe('the headline the chronology opens on', () => {
	/* Prefer the full word family while preserving explicit archived selections. */
	const withDerived: ChronologyChoices = {
		series: {
			year: ['genocide', 'term_subset', 'war_crimes'],
			quarter: ['genocide', 'term_subset', 'war_crimes']
		},
		calendar: {
			genocide: ['speech_rate'],
			term_subset: ['speech_rate', 'token_rate']
		},
		splits: ['none']
	};
	const withAtrocityComparison: ChronologyChoices = {
		...withDerived,
		series: {
			year: ['genocide', 'ethnic_cleansing', 'crimes_against_humanity', 'war_crimes'],
			quarter: ['genocide', 'ethnic_cleansing', 'crimes_against_humanity', 'war_crimes']
		}
	};

	it('opens on the full word family when both measures are available', () => {
		const state = readChronologyState(new URLSearchParams(''), withDerived);
		expect(state.series).toEqual(['genocide']);
		expect(state.calendarMeasure).toBe('genocide');
	});

	it('opens the R8 comparison as four explicit terms when all are available', () => {
		const state = readChronologyState(new URLSearchParams(''), withAtrocityComparison);
		expect(state.series).toEqual([
			'genocide',
			'ethnic_cleansing',
			'crimes_against_humanity',
			'war_crimes'
		]);
	});

	it('falls back to the raw term when the artefact has no derived measure', () => {
		const state = readChronologyState(new URLSearchParams(''), choices);
		expect(state.series).toEqual(['genocide']);
		expect(state.calendarMeasure).toBe('genocide');
	});

	it('still lets a reader select the explicit alternative measure', () => {
		const state = readChronologyState(new URLSearchParams('series=term_subset'), withDerived);
		expect(state.series).toEqual(['term_subset']);
	});
});

describe('chronology URL state', () => {
	it('round-trips every analytical control, including ordered multi-series state', () => {
		const state: ChronologyState = {
			unit: 'token_rate',
			grain: 'quarter',
			series: ['war_crimes', 'genocide'],
			calendarMeasure: 'war_crimes',
			calendarUnit: 'speech_rate',
			split: 'delivery_language'
		};
		expect(readChronologyState(chronologyParams(state, choices), choices)).toEqual(state);
	});

	it('preserves an intentionally empty series selection', () => {
		const state = readChronologyState(new URLSearchParams('series='), choices);
		expect(state.series).toEqual([]);
		expect(chronologyParams(state, choices).toString()).toBe('series=');
	});

	it('uses the selected grain when its available series differ', () => {
		const divergent: ChronologyChoices = {
			...choices,
			series: { ...choices.series, quarter: ['responsibility'] }
		};
		const state = readChronologyState(new URLSearchParams('grain=quarter'), divergent);
		expect(state.series).toEqual(['responsibility']);
		expect(chronologyParams(state, divergent).toString()).toBe('grain=quarter');
	});

	it('normalizes unknown and unsupported controls to visible defaults', () => {
		const state = readChronologyState(
			new URLSearchParams(
				'unit=ratio&grain=month&series=unknown&calendar=war_crimes&calendarUnit=token_rate&split=region'
			),
			choices
		);
		expect(state).toEqual({
			unit: 'speech_rate',
			grain: 'year',
			series: ['genocide'],
			calendarMeasure: 'war_crimes',
			calendarUnit: 'speech_rate',
			split: 'none'
		});
	});
});

describe('chronology breakdown evidence', () => {
	it('links participant type to its exact concordance category and year', () => {
		const link = splitEvidenceQuery('genocide', 'participanttype', 'Mentioned', 2014)!;
		const params = new URLSearchParams(link.query);
		expect(params.get('term')).toBe('genocide');
		expect(params.get('type')).toBe('Mentioned');
		expect(params.get('from')).toBe('2014');
		expect(params.get('to')).toBe('2014');
		expect(link.scope).toBe('Mentioned in 2014');
	});

	it('refuses a split whose category is absent from KWIC', () => {
		expect(splitEvidenceQuery('genocide', 'delivery_language', 'French', 2014)).toBeNull();
	});
});

describe('interval bands', () => {
	it('draws a floor at the lower bound and a strip of the interval height', async () => {
		const { intervalBand } = await import('./chronology');
		const [floor, strip] = intervalBand('genocide', '#123456', [0.01, 0.02], [0.03, 0.05]);
		expect(floor.data).toEqual([0.01, 0.02]);
		const heights = strip.data as number[];
		expect(heights[0]).toBeCloseTo(0.02, 12);
		expect(heights[1]).toBeCloseTo(0.03, 12);
		expect(strip.areaStyle).toEqual({ color: '#123456', opacity: 0.14 });
		expect(floor.stack).toBe(strip.stack);
		expect(floor.tooltip?.show).toBe(false);
		expect(floor.silent).toBe(true);
	});

	it('leaves a gap where a bound is withheld rather than guessing', async () => {
		const { intervalBand } = await import('./chronology');
		const [floor, strip] = intervalBand('g', '#000', [0.01, null, 0.02], [0.03, 0.04, null]);
		expect(floor.data).toEqual([0.01, null, null]);
		const heights = strip.data as (number | null)[];
		expect(heights[0]).toBeCloseTo(0.02, 12);
		expect(heights.slice(1)).toEqual([null, null]);
	});

	it('never draws a negative strip', async () => {
		const { intervalBand } = await import('./chronology');
		const [, strip] = intervalBand('g', '#000', [0.05], [0.04]);
		expect(strip.data).toEqual([0]);
	});

	it('tells a band from the line it belongs to', async () => {
		const { isIntervalBand, bandOwner, BAND_SUFFIX } = await import('./chronology');
		expect(isIntervalBand(`Genocide${BAND_SUFFIX}`)).toBe(true);
		expect(isIntervalBand('Genocide')).toBe(false);
		expect(isIntervalBand(undefined)).toBe(false);
		expect(bandOwner(`Genocide${BAND_SUFFIX}`)).toBe('Genocide');
		expect(bandOwner('Genocide')).toBe('Genocide');
	});
});

/* The nine legal terms were the bug: one register hue, nine identical teal
   lines, told apart only by their end labels. The stroke ladder has to keep the
   hue (a register is a shelf, and the hue says which shelf) while making the
   lines on one shelf tellable apart, with the dash carrying as much of that as
   the colour does. */
describe('term strokes', () => {
	const p: Palette = {
		ink: '#111111',
		inkSoft: '#3d444c',
		inkFaint: '#626a74',
		paper: '#ffffff',
		panel: '#fbfbf8',
		rule: '#b7bcaf',
		ruleSoft: '#d6d9cf',
		accent: '#1b5fa8',
		positive: '#4a6b2e',
		negative: '#98333a',
		registers: {
			core: '#111111',
			legal: '#2c7069',
			preventive: '#5c7a3a'
		}
	};

	const LEGAL = [
		'genocidal_acts',
		'ethnic_cleansing',
		'crimes_against_humanity',
		'war_crimes',
		'grave_breaches',
		'atrocity_crimes',
		'mass_atrocities',
		'extermination',
		'persecution'
	];
	const registers: Record<string, string> = {
		genocide: 'core',
		genocidaires: 'core',
		prevention: 'preventive',
		...Object.fromEntries(LEGAL.map((name) => [name, 'legal']))
	};
	const registerOf = (name: string) => registers[name];

	it('keeps the headline term in full ink, solid, and the heavier weight', () => {
		const strokes = termStrokes(['genocide', ...LEGAL], registerOf, p);
		expect(strokes.get('genocide')).toEqual({ color: p.ink, dash: 'solid', width: 2 });
	});

	it('gives every term of a register a stroke of its own', () => {
		const strokes = termStrokes(LEGAL, registerOf, p);
		const drawn = LEGAL.map((name) => strokes.get(name)!);
		expect(drawn).toHaveLength(9);
		expect(new Set(drawn.map((s) => `${s.color} ${s.dash}`)).size).toBe(9);
	});

	it('never leaves colour as the only thing separating two lines', () => {
		const strokes = termStrokes(LEGAL, registerOf, p);
		const drawn = LEGAL.map((name) => strokes.get(name)!);
		// Three lightness steps of the one hue, each crossed with the three
		// dashes: any two lines sharing a colour are drawn in different dashes.
		expect(new Set(drawn.map((s) => s.color)).size).toBe(3);
		for (const [i, a] of drawn.entries()) {
			for (const b of drawn.slice(i + 1)) {
				if (a.color === b.color) expect(a.dash).not.toBe(b.dash);
			}
		}
		expect(new Set(drawn.map((s) => s.dash))).toEqual(new Set(['solid', 'dashed', 'dotted']));
	});

	it('keeps the register hue as the family: the first step is the hue itself', () => {
		const strokes = termStrokes(LEGAL, registerOf, p);
		expect(strokes.get(LEGAL[0])!.color).toBe(p.registers.legal);
		expect(termStrokes(['prevention'], registerOf, p).get('prevention')!.color).toBe(
			p.registers.preventive
		);
	});

	it('steps by position in the register, not by position in the list', () => {
		// A preventive term sitting between two legal ones must not push the
		// second legal term onto a different rung.
		const woven = termStrokes([LEGAL[0], 'prevention', LEGAL[1]], registerOf, p);
		const plain = termStrokes([LEGAL[0], LEGAL[1]], registerOf, p);
		expect(woven.get(LEGAL[1])).toEqual(plain.get(LEGAL[1]));
	});

	it('draws a term the same way on every call, so an export matches the screen', () => {
		const names = ['genocide', 'genocidaires', ...LEGAL, 'prevention'];
		const once = termStrokes(names, registerOf, p);
		const twice = termStrokes(names, registerOf, p);
		for (const name of names) expect(twice.get(name)).toEqual(once.get(name));
	});

	it('draws a term with no register of its own in ink, never in the accent', () => {
		const stroke = termStrokes(['unfiled'], () => undefined, p).get('unfiled')!;
		expect(stroke.color).toBe(p.ink);
		expect(stroke.color).not.toBe(p.accent);
	});
});
