/**
 * What the usage view decides, tested apart from how it is drawn.
 *
 * Four things here can be wrong while looking entirely right on screen, and all
 * four are pinned below: a share published for a speaker heard from three
 * times; a meta referent ranked among the cases as though it were one; a row
 * cap that silently turns a hundred delegations into forty; and a drill-down
 * that shows an annotation it cannot quote. The fifth — that these are a
 * model's labels and not measurements — is a sentence in the interface, and the
 * only thing a unit test can hold is that the sentence has numbers behind it.
 */

import { describe, expect, it } from 'vitest';
import {
	CONTESTED_CAP,
	CONTESTED_COLUMNS,
	DIFFUSION_BOX,
	DIFFUSION_COLUMNS,
	MATRIX_COLUMNS,
	MILESTONES,
	NAVIGATION_KEYS,
	ROW_CAP,
	POSITIONS,
	POSITION_COLUMNS,
	USAGE_DEFAULTS,
	USAGE_TERM,
	comparisonApparatus,
	contestedExportRows,
	contestedList,
	diffusionChronology,
	diffusionExportRows,
	diffusionPlan,
	drillDown,
	emptyPositions,
	goldProgress,
	isInstrumentDependent,
	matrixExportRows,
	matrixPlan,
	milestoneLabel,
	milestoneRank,
	orderReferents,
	readUsageState,
	retestRows,
	selectUsage,
	positionExportRows,
	positionLabel,
	positionRanking,
	stepFocus,
	usageParams
} from './usage';
import type { UsageState } from './usage';
import type {
	KwicLine,
	PositionCounts,
	Usage,
	UsageActor,
	UsageAlternative,
	UsageDiffusion,
	UsageDiffusionEvent,
	UsageMatrixCell,
	UsageMilestone,
	UsageOccurrence,
	UsageReferent,
	UsagePositionRow
} from './types';

const meta = { script: '15_usage.py', generated: '2026-09-01T00:00:00Z' };

const model: Usage['model'] = {
	id: 'chatgpt-5.6-luna-2026-08-01',
	run_id: '2026-09-01-luna-v1',
	run_date: '2026-09-01',
	prompt_version: '1',
	referents_version: '1',
	prompt_sha256: 'a'.repeat(64),
	reasoning_effort: 'high',
	requests: 3273,
	requests_recounted: true,
	occurrences_total: 6092,
	occurrences_annotated: 6092,
	parse_failures: 0,
	evidence_invalid: 0,
	abstention: { verdict_uncertain: 0, referent_unclear: 0, position_unclear: 0 },
	tokens: { input: 0, output: 0 }
};

const gold: Usage['gold'] = {
	sample_size: 200,
	unique_occurrences: 197,
	coders: [],
	double_coded: 0,
	adjudicated: 0,
	frames: [],
	human_agreement: [],
	human_function: { n: 0, jaccard: null, alpha_masi: null, labels: [] },
	model_vs_human: [],
	model_vs_human_comparison: [],
	state: 'not_started'
};

/** The block every build without a second opinion carries: the ordinary state. */
const noComparison: Usage['comparison'] = {
	state: 'none',
	run_id: '',
	model: '',
	run_date: '',
	reasoning_effort: '',
	prompt_sha256: '',
	occurrences_annotated: 0,
	overlap: 0,
	evidence_invalid: 0,
	abstention: { verdict_uncertain: 0, referent_unclear: 0, position_unclear: 0 },
	fields: [],
	referents: [],
	function_jaccard: null,
	function_alpha_masi: null,
	function_labels: [],
	function_contested: 0,
	contested_any: 0
};

/** One compared field, with the three statistics 15 now writes beside kappa. */
const field = (
	name: string,
	observed: number,
	kappa: number | null,
	contested: number,
	extra: Partial<Usage['comparison']['fields'][number]> = {}
): Usage['comparison']['fields'][number] => ({
	field: name,
	n: 5800,
	observed,
	kappa,
	kappa_withheld: kappa === null,
	minority_share: kappa === null ? 0.001 : 0.4,
	pabak: 2 * observed - 1,
	contested,
	...extra
});

/** A second model over the same occurrences, agreeing on some of them. */
const comparison = (overrides: Partial<Usage['comparison']> = {}): Usage['comparison'] => ({
	...noComparison,
	state: 'computed',
	run_id: '2026-09-06-gemini-v1',
	model: 'gemini-3-pro-2026-07-15',
	run_date: '2026-09-06',
	reasoning_effort: 'medium',
	// The same prompt, byte for byte: a comparison of other instructions is an
	// answer to another question, and 15 refuses to publish one.
	prompt_sha256: model.prompt_sha256,
	occurrences_annotated: 6000,
	overlap: 5800,
	evidence_invalid: 4,
	abstention: { verdict_uncertain: 3, referent_unclear: 11, position_unclear: 7 },
	fields: [
		field('verdict', 0.99, null, 58),
		field('quotation', 0.94, 0.81, 348),
		field('speaker_position', 0.86, 0.74, 812),
		field('referent', 0.91, 0.88, 522)
	],
	function_jaccard: 0.72,
	function_contested: 1204,
	contested_any: 1800,
	...overrides
});

const positions = (partial: Partial<PositionCounts> = {}): PositionCounts => ({
	...emptyPositions(),
	...partial
});

const actor = (name: string, extra: Partial<UsageActor> = {}): UsageActor => ({
	country_org: name,
	iso3: name.slice(0, 3).toUpperCase(),
	group: 'E10',
	entity_type: 'state',
	occurrences: 10,
	eligible: 8,
	assigned: 6,
	sufficient: true,
	...extra
});

const referent = (id: string, extra: Partial<UsageReferent> = {}): UsageReferent => ({
	id,
	label: id,
	description: `${id} definition`,
	kind: 'case',
	iso3: '',
	years: '',
	since: 1,
	retired_in: null,
	occurrences: 1,
	retired: false,
	superseded_by: '',
	...extra
});

const cell = (
	actorName: string,
	referentId: string,
	count: number,
	partial: Partial<PositionCounts> = {},
	contested = 0
): UsageMatrixCell => ({
	actor: actorName,
	referent: referentId,
	count,
	contested,
	positions: positions(partial)
});

const moment = (
	date: string,
	actorName: string,
	milestone: UsageMilestone,
	speaker_position: string,
	id: string
): UsageDiffusionEvent => ({ date, actor: actorName, milestone, speaker_position, id });

/**
 * A chronology whose shape is the one the figure has to get right: a meta
 * referent first in the block, so a default that took the first entry would show
 * the Convention rather than a genocide; a delegation whose first placed use is
 * already an assertion, and another whose first is a refusal and who asserts six
 * years later; and one referent's events spanning the whole axis while the
 * other's sit inside it.
 */
const diffusion: UsageDiffusion = {
	milestones: ['mention', 'asserts', 'rejects'],
	referents: [
		{
			id: 'convention',
			events: [moment('1996-02-02', 'Alpha', 'mention', 'no_position', 'SC03600-01-001#1')]
		},
		{
			id: 'rwanda_1994',
			events: [
				moment('1994-04-21', 'Alpha', 'mention', 'asserts', 'SC03368-01-005#1'),
				moment('1994-04-21', 'Alpha', 'asserts', 'asserts', 'SC03368-01-005#1'),
				moment('1998-06-01', 'Bravo', 'mention', 'rejects', 'SC03888-01-002#1'),
				moment('1998-06-01', 'Bravo', 'rejects', 'rejects', 'SC03888-01-002#1'),
				moment('2004-04-07', 'Bravo', 'asserts', 'asserts', 'SC04940-01-011#1')
			]
		}
	]
};

const corpus = (overrides: Partial<Usage> = {}): Usage => ({
	meta,
	model,
	prompt: 'Read the occurrence and say what it refers to.',
	referents: [
		referent('rwanda_1994', { occurrences: 5, iso3: 'RWA', years: '1994' }),
		referent('convention', { kind: 'meta', occurrences: 2 }),
		referent('bosnia', { occurrences: 1 }),
		referent('holocaust', { kind: 'historical', occurrences: 0 })
	],
	actors: [
		actor('Alpha'),
		actor('Bravo', { occurrences: 4, eligible: 3, assigned: 2, sufficient: false }),
		actor('Charlie', { occurrences: 2, eligible: 1, assigned: 0, sufficient: false })
	],
	minimum_occurrences: 4,
	matrix: [
		cell('Alpha', 'rwanda_1994', 4, { asserts: 3, rejects: 1 }),
		cell('Alpha', 'bosnia', 1, { asserts: 1 }),
		cell('Alpha', 'convention', 1, { no_position: 1 }),
		cell('Bravo', 'rwanda_1994', 1, { rejects: 1 }),
		cell('Bravo', 'convention', 1, { no_position: 1 })
	],
	position_by_actor: [
		{
			actor: 'Alpha',
			eligible: 8,
			sufficient: true,
			positions: positions({ asserts: 5, rejects: 2, unclear: 1 }),
			share_rejects: 0.25,
			share_low: null,
			share_high: null,
			separated: false
		},
		{
			actor: 'Bravo',
			eligible: 3,
			sufficient: false,
			positions: positions({ asserts: 3 }),
			share_rejects: null,
			share_low: null,
			share_high: null,
			separated: false
		}
	],
	diffusion,
	comparison: noComparison,
	retest: [],
	gold,
	...overrides
});

const state = (partial: Partial<UsageState> = {}): UsageState => ({
	...USAGE_DEFAULTS,
	...partial
});

describe('the speaker_position vocabulary', () => {
	it('holds the codebook’s seven values in the codebook’s order', () => {
		// Fixed rather than derived: the stacked bar is only comparable between
		// delegations if the same band is in the same place in every one of them.
		expect(POSITIONS).toEqual([
			'asserts',
			'reports_without_position',
			'rejects',
			'conditional',
			'no_position',
			'unclear',
			'not_applicable'
		]);
		expect(Object.keys(emptyPositions())).toEqual([...POSITIONS]);
		expect(Object.values(emptyPositions()).every((value) => value === 0)).toBe(true);
	});

	it('names a speaker_position for a reader, and degrades a value it has never seen', () => {
		expect(positionLabel('rejects')).toBe('Rejects');
		expect(positionLabel('some_future_label')).toBe('some future label');
	});

	it('annotates exactly one term, and says which', () => {
		expect(USAGE_TERM).toBe('genocide');
	});
});

describe('usage URL state', () => {
	it('round-trips every analytical control', () => {
		const data = corpus({ comparison: comparison() });
		const wanted = state({
			actor: 'Alpha',
			referent: 'rwanda_1994',
			unit: 'share',
			sort: 'name',
			contested: true
		});
		expect(readUsageState(usageParams(wanted), data)).toEqual(wanted);
		expect(usageParams(wanted).get('contested')).toBe('1');
	});

	it('drops a contested filter on a build that has no second opinion', () => {
		// The same rule a referent this artefact does not carry is dropped under:
		// the control is not on the page, so the filter would narrow the list to
		// nothing with nothing on screen saying why.
		expect(readUsageState(new URLSearchParams('actor=Alpha&contested=1'), corpus())).toMatchObject({
			actor: 'Alpha',
			contested: false
		});
		expect(
			readUsageState(
				new URLSearchParams('actor=Alpha&contested=1'),
				corpus({ comparison: comparison() })
			).contested
		).toBe(true);
		// Only `1` turns it on, and only `true` is written back.
		expect(
			readUsageState(new URLSearchParams('contested=yes'), corpus({ comparison: comparison() }))
				.contested
		).toBe(false);
		expect(usageParams(state({ contested: false })).toString()).toBe('');
	});

	it('writes nothing for a view that is already the default', () => {
		expect(usageParams(USAGE_DEFAULTS).toString()).toBe('');
	});

	it('drops a selection this artefact cannot fill, and unreadable controls', () => {
		const data = corpus();
		// A stale link naming a delegation that is no longer in the payload would
		// open a drill-down that can never fill, and a reader would have no way to
		// tell that from an empty cell.
		const read = readUsageState(
			new URLSearchParams('actor=Atlantis&referent=narnia&unit=furlongs&sort=vibes'),
			data
		);
		expect(read).toEqual(USAGE_DEFAULTS);
		expect(usageParams(read).toString()).toBe('');
	});
});

describe('picking a cell, a row or a column', () => {
	it('selects a pairing, an axis on its own, and releases what is already in force', () => {
		const start = state();
		expect(selectUsage(start, 'Alpha', 'bosnia')).toMatchObject({
			actor: 'Alpha',
			referent: 'bosnia'
		});
		// A row heading names one axis and clears the other, so a delegation and
		// one of its cells are the same operation with different arguments.
		expect(selectUsage(state({ actor: 'Alpha', referent: 'bosnia' }), 'Alpha', '')).toMatchObject({
			actor: 'Alpha',
			referent: ''
		});
		// The cell that opened the drill-down closes it.
		expect(
			selectUsage(state({ actor: 'Alpha', referent: 'bosnia' }), 'Alpha', 'bosnia')
		).toMatchObject({ actor: '', referent: '' });
	});

	it('leaves the unit and the ordering alone', () => {
		const picked = selectUsage(state({ unit: 'share', sort: 'name' }), 'Alpha', 'bosnia');
		expect(picked.unit).toBe('share');
		expect(picked.sort).toBe('name');
	});
});

describe('the column order', () => {
	it('ranks the cases by weight and groups the meta referents after them', () => {
		const data = corpus();
		// `convention` outranks `bosnia` on count and still comes last: it is not
		// a genocide but a way of talking about the category, and ranked among the
		// cases it would read as one more of them.
		expect(orderReferents(data.referents).map((r) => r.id)).toEqual([
			'rwanda_1994',
			'bosnia',
			'holocaust',
			'convention'
		]);
	});

	it('keeps a retired referent only while a run still has counts under it', () => {
		// The list is versioned so an older run stays readable: on that run the
		// column is full and belongs here. On a run made after the withdrawal it is
		// empty, and the empty-column sentence would call it a case the delegations
		// declined to invoke rather than one the instrument was never offered.
		const withCounts = orderReferents([
			referent('rwanda', { occurrences: 5 }),
			referent('rwanda_1994', { occurrences: 3, retired: true, superseded_by: 'rwanda' })
		]);
		expect(withCounts.map((r) => r.id)).toEqual(['rwanda', 'rwanda_1994']);

		const withoutCounts = orderReferents([
			referent('rwanda', { occurrences: 5 }),
			referent('rwanda_1994', { occurrences: 0, retired: true, superseded_by: 'rwanda' }),
			referent('holocaust', { occurrences: 0 })
		]);
		expect(withoutCounts.map((r) => r.id)).toEqual(['rwanda', 'holocaust']);
	});

	it('keeps a referent nothing was assigned to, rather than hiding it', () => {
		const plan = matrixPlan(corpus(), state());
		expect(plan.columns.map((column) => column.referent.id)).toContain('holocaust');
		expect(plan.columns.find((column) => column.referent.id === 'holocaust')?.drawn).toBe(0);
		expect(plan.disclosure.emptyColumns).toBe(1);
	});

	it('gives an abstention code no column, and the uncontrolled referent one', () => {
		const data = corpus({
			referents: [
				referent('rwanda_1994', { occurrences: 5 }),
				referent('other', { kind: 'reserved', occurrences: 3 }),
				referent('unclear', { kind: 'reserved', occurrences: 0 }),
				referent('not_applicable', { kind: 'reserved', occurrences: 0 }),
				referent('convention', { kind: 'meta', occurrences: 2 })
			],
			matrix: [cell('Alpha', 'rwanda_1994', 4, { asserts: 4 })]
		});
		// `unclear` and `not_applicable` are how the codebook lets a coder decline;
		// an occurrence carrying either is by definition not assigned, so those
		// columns could never fill and would be described wrongly by the empty-
		// column disclosure — as cases the list offered and nobody invoked.
		expect(orderReferents(data.referents).map((r) => r.id)).toEqual([
			'rwanda_1994',
			'other',
			'convention'
		]);
		const plan = matrixPlan(data, state());
		expect(plan.columns.map((column) => column.referent.id)).not.toContain('unclear');
		// `other` names a real referent that has no identifier yet, so it keeps a
		// column — grouped away from the cases, because it is not one of them.
		expect(plan.groupedFrom).toBe(1);
		expect(plan.columns.map((column) => column.grouped)).toEqual([false, true, true]);
	});
});

describe('the matrix', () => {
	it('draws a row per speaker with something assigned, ranked, and no others', () => {
		const plan = matrixPlan(corpus(), state());
		expect(plan.rows.map((row) => row.actor.country_org)).toEqual(['Alpha', 'Bravo']);
		expect(plan.disclosure.speakers).toBe(2);
		// Charlie has an eligible occurrence and no referent for it, so it is not a
		// row at all. Reported rather than dropped.
		expect(plan.disclosure.silent).toBe(1);
		expect(plan.refusal).toBeNull();
		expect(plan.groupedFrom).toBe(3);
	});

	it('re-ranks on the ordering asked for, and breaks every tie on the name', () => {
		const data = corpus({
			actors: [
				actor('Bravo', { occurrences: 40, assigned: 2 }),
				actor('Alpha', { occurrences: 40, assigned: 2 }),
				actor('Charlie', { occurrences: 1, assigned: 9 })
			]
		});
		expect(
			matrixPlan(data, state({ sort: 'occurrences' })).rows.map((row) => row.actor.country_org)
		).toEqual(['Alpha', 'Bravo', 'Charlie']);
		expect(
			matrixPlan(data, state({ sort: 'assigned' })).rows.map((row) => row.actor.country_org)
		).toEqual(['Charlie', 'Alpha', 'Bravo']);
		expect(
			matrixPlan(data, state({ sort: 'name' })).rows.map((row) => row.actor.country_org)
		).toEqual(['Alpha', 'Bravo', 'Charlie']);
	});

	it('counts a sparse payload’s missing cells as empty rather than as zero data', () => {
		const plan = matrixPlan(corpus(), state());
		const alpha = plan.rows[0];
		expect(alpha.cells.map((c) => c.count)).toEqual([4, 1, 0, 1]);
		expect(alpha.cells.map((c) => c.state)).toEqual(['drawn', 'drawn', 'empty', 'drawn']);
		expect(alpha.cells[2].positions).toEqual(emptyPositions());
	});

	it('publishes a count for every speaker and a share only above the minimum', () => {
		const counted = matrixPlan(corpus(), state({ unit: 'count' }));
		const shared = matrixPlan(corpus(), state({ unit: 'share' }));
		const bravoCounted = counted.rows[1].cells[0];
		const bravoShared = shared.rows[1].cells[0];
		// A count of one is a fact about the record; one out of two is not "50% of
		// this delegation's uses". The same cell is drawn under one unit and
		// hatched under the other.
		expect(bravoCounted.state).toBe('drawn');
		expect(bravoShared.state).toBe('withheld-share');
		expect(bravoShared.share).toBeNull();
		expect(counted.disclosure.withheldRows).toBe(1);
		expect(counted.rows[0].cells[0].share).toBeCloseTo(4 / 6, 12);
	});

	it('runs the ramp from zero to the largest cell that may actually be drawn', () => {
		const counted = matrixPlan(corpus(), state({ unit: 'count' }));
		expect(counted.high).toBe(4);
		expect(counted.rows[0].cells[0].weight).toBe(1);
		expect(counted.rows[0].cells[0].tone).toBe(1);
		expect(counted.rows[0].cells[2].tone).toBe(0);

		const shared = matrixPlan(corpus(), state({ unit: 'share' }));
		// A hatched cell must never set the top of a scale it is not on: Bravo's
		// withheld 1-of-2 would otherwise be the highest share in the figure.
		expect(shared.high).toBeCloseTo(4 / 6, 12);
		expect(shared.rows[1].cells[0].weight).toBe(0);
	});

	it('marks the selected pair, its row and its column, and nothing when nothing is selected', () => {
		const selected = matrixPlan(corpus(), state({ actor: 'Alpha', referent: 'bosnia' }));
		expect(selected.rows.filter((row) => row.selected).map((row) => row.actor.country_org)).toEqual(
			['Alpha']
		);
		expect(
			selected.columns.filter((column) => column.selected).map((column) => column.referent.id)
		).toEqual(['bosnia']);
		expect(selected.rows.flatMap((row) => row.cells).filter((c) => c.selected).length).toBe(1);

		const none = matrixPlan(corpus(), state());
		expect(none.rows.flatMap((row) => row.cells).some((c) => c.selected)).toBe(false);
		expect(none.rows.some((row) => row.selected)).toBe(false);
	});

	it('caps the rows and hands the interface what the cap cost', () => {
		const many = Array.from({ length: ROW_CAP + 5 }, (_, index) =>
			actor(`Speaker ${String(index).padStart(3, '0')}`, {
				assigned: 100 - index,
				// The tail is the part the cap is for: below the minimum, and so
				// carrying no share the figure could have published anyway.
				sufficient: index < ROW_CAP
			})
		);
		const plan = matrixPlan(corpus({ actors: many, matrix: [] }), state());
		expect(plan.rows).toHaveLength(ROW_CAP);
		expect(plan.cap).toBe(ROW_CAP);
		// A cut that does not say it is a cut is the display decision the exports
		// refuse, and the objection holds on screen.
		expect(plan.disclosure.hiddenRows).toBe(5);
		expect(plan.disclosure.hiddenOccurrences).toBe(
			many.slice(ROW_CAP).reduce((total, row) => total + row.assigned, 0)
		);
		expect(plan.disclosure.hiddenSufficient).toBe(0);
	});

	it('counts a publishable share the cap cut, so the figure can never drop one quietly', () => {
		// The cap is a flat number and sufficiency is counted on a different
		// denominator, so the two can disagree. When they do, the interface has to
		// be able to say so rather than let the row disappear.
		const many = Array.from({ length: ROW_CAP + 2 }, (_, index) =>
			actor(`Speaker ${String(index).padStart(3, '0')}`, {
				assigned: 100 - index,
				sufficient: index !== ROW_CAP - 1
			})
		);
		const plan = matrixPlan(corpus({ actors: many, matrix: [] }), state());
		expect(plan.disclosure.hiddenSufficient).toBe(2);
	});

	it('reports the three denominators the figure does not draw', () => {
		const plan = matrixPlan(corpus(), state());
		// eligible but unplaced: (8-6) + (3-2) + (1-0)
		expect(plan.disclosure.unassigned).toBe(4);
		// never eligible: (10-8) + (4-3) + (2-1)
		expect(plan.disclosure.ineligible).toBe(4);
		// everything inside a drawn row's cells
		expect(plan.disclosure.drawn).toBe(8);
	});

	it('refuses in words when the model placed nothing at all', () => {
		const plan = matrixPlan(
			corpus({ actors: [actor('Alpha', { assigned: 0 })], matrix: [] }),
			state()
		);
		expect(plan.rows).toEqual([]);
		expect(plan.refusal).toBe('no-assignments');
		expect(plan.high).toBe(0);
	});
});

describe('moving through the matrix from the keyboard', () => {
	const plan = matrixPlan(corpus(), state());

	it('intercepts the six keys a grid owns and no others', () => {
		expect([...NAVIGATION_KEYS].sort()).toEqual([
			'ArrowDown',
			'ArrowLeft',
			'ArrowRight',
			'ArrowUp',
			'End',
			'Home'
		]);
		const at = { row: 0, column: 0 };
		expect(stepFocus(plan, at, 'Enter')).toBe(at);
	});

	it('steps between cells and out into the headings', () => {
		expect(stepFocus(plan, { row: 1, column: 2 }, 'ArrowUp')).toEqual({ row: 0, column: 2 });
		expect(stepFocus(plan, { row: 0, column: 2 }, 'ArrowUp')).toEqual({ row: -1, column: 2 });
		expect(stepFocus(plan, { row: 0, column: 0 }, 'ArrowLeft')).toEqual({ row: 0, column: -1 });
		expect(stepFocus(plan, { row: 0, column: 0 }, 'End')).toEqual({ row: 0, column: 3 });
		expect(stepFocus(plan, { row: 0, column: 3 }, 'Home')).toEqual({ row: 0, column: -1 });
	});

	it('stops at the edges rather than wrapping, and never lands on the corner', () => {
		expect(stepFocus(plan, { row: -1, column: 0 }, 'ArrowUp')).toEqual({ row: -1, column: 0 });
		expect(stepFocus(plan, { row: 1, column: 3 }, 'ArrowDown')).toEqual({ row: 1, column: 3 });
		expect(stepFocus(plan, { row: 1, column: 3 }, 'ArrowRight')).toEqual({ row: 1, column: 3 });
		// The corner heading carries nothing, so a move that would land there is
		// refused: the reader stays where they can still see themselves.
		const corner = { row: -1, column: 0 };
		expect(stepFocus(plan, corner, 'ArrowLeft')).toBe(corner);
		const edge = { row: 0, column: -1 };
		expect(stepFocus(plan, edge, 'ArrowUp')).toBe(edge);
	});
});

describe('who rejects the word', () => {
	it('orders only the shares the artefact published, and leaves out the rest', () => {
		const rows: UsagePositionRow[] = [
			{
				actor: 'Alpha',
				eligible: 8,
				sufficient: true,
				positions: positions({ asserts: 5, rejects: 2, unclear: 1 }),
				share_rejects: 0.25,
				share_low: null,
				share_high: null,
				separated: false
			},
			{
				actor: 'Delta',
				eligible: 10,
				sufficient: true,
				positions: positions({ asserts: 5, rejects: 5 }),
				share_rejects: 0.5,
				share_low: null,
				share_high: null,
				separated: false
			},
			{
				actor: 'Bravo',
				eligible: 3,
				sufficient: false,
				positions: positions({ asserts: 3 }),
				share_rejects: null,
				share_low: null,
				share_high: null,
				separated: false
			}
		];
		const result = positionRanking(corpus({ position_by_actor: rows }));
		// Neither clears the corpus rate, so the two are ordered by rejection
		// count and the order is not a claim that one rejects more than the other.
		expect(result.rows.map((row) => row.actor)).toEqual(['Delta', 'Alpha']);
		// Not ranked low; not ranked. A null read through `?? 0` would put every
		// rarely-heard delegation at the foot of a ranking of rejection.
		expect(result.withheld.map((row) => row.actor)).toEqual(['Bravo']);
		expect(result.withheld[0].total).toBe(3);
		expect(result.minimum).toBe(4);
	});

	it('withholds a row that claims to be sufficient and carries no share', () => {
		const result = positionRanking(
			corpus({
				position_by_actor: [
					{
						actor: 'Alpha',
						eligible: 9,
						sufficient: true,
						positions: positions({ asserts: 9 }),
						share_rejects: null,
						share_low: null,
						share_high: null,
						separated: false
					}
				]
			})
		);
		// The fetch boundary refuses such a payload, so this never arrives — but a
		// figure that would rank it by a null if it did is a figure one edit away
		// from doing so.
		expect(result.rows).toEqual([]);
		expect(result.withheld.map((row) => row.actor)).toEqual(['Alpha']);
	});

	it('lays the bands out in one pass of cumulative bounds, zeros omitted', () => {
		const result = positionRanking(corpus());
		const alpha = result.rows[0];
		expect(alpha.total).toBe(8);
		expect(alpha.segments.map((segment) => segment.speaker_position)).toEqual([
			'asserts',
			'rejects',
			'unclear'
		]);
		expect(alpha.segments[0]).toMatchObject({ count: 5, from: 0 });
		expect(alpha.segments[0].to).toBeCloseTo(62.5, 10);
		expect(alpha.segments[1].from).toBeCloseTo(62.5, 10);
		expect(alpha.segments[2].to).toBeCloseTo(100, 10);
	});
});

describe('the quotations behind a cell', () => {
	const line = (id: string, extra: Partial<KwicLine> = {}): KwicLine => ({
		id,
		spv: 'S/PV.7000',
		date: '2014-06-11',
		country: 'Rwanda',
		iso3: 'RWA',
		group: 'E10',
		type: 'Mentioned',
		agenda: 'Protection of civilians',
		start: 0,
		end: 8,
		left: 'We warned that ',
		kw: 'genocide',
		right: ' could occur.',
		sent: 'We warned that genocide could occur.',
		...extra
	});

	const annotation = (id: string, extra: Partial<UsageOccurrence> = {}): UsageOccurrence => ({
		id,
		occurrence_id: 'f'.repeat(64),
		verdict: 'true_positive',
		quotation: 'not_quoted',
		concrete_case: 'yes',
		speaker_position: 'conditional',
		function: 'warning_or_prevention|accountability',
		referent: 'rwanda_1994',
		proposed_referent: '',
		// A run coded against annotation schema 2 answers none of the six fields
		// schema 3 added, and this is what that looks like on a row.
		referent_source: '',
		accused_actor: '',
		victim_group: '',
		own_state_accused: '',
		salience: '',
		rationale: '',
		confidence: 'high',
		evidence_quote: 'We warned that genocide could occur.',
		evidence_valid: true,
		contested: [],
		alt: null,
		...extra
	});

	const lines = [
		line('SC07000-01-001#1'),
		line('SC07481-01-007#1', {
			spv: 'S/PV.7481',
			date: '2015-07-08',
			country: 'France',
			group: 'P5',
			sent: 'The Council must call this genocide by its name.'
		})
	];

	it('shows nothing at all until something is selected', () => {
		expect(drillDown([annotation('SC07000-01-001#1')], lines)).toEqual([]);
	});

	it('joins an annotation to the sentence it labels, on the line identifier alone', () => {
		const rows = drillDown([annotation('SC07000-01-001#1')], lines, 'Rwanda', 'rwanda_1994');
		expect(rows).toHaveLength(1);
		expect(rows[0]).toMatchObject({
			country: 'Rwanda',
			spv: 'S/PV.7000',
			sentence: 'We warned that genocide could occur.',
			positionLabel: 'Conditional',
			functions: ['warning_or_prevention', 'accountability'],
			quoteDiffers: false
		});
	});

	it('drops an annotation whose line is not in the concordance file', () => {
		// The view's whole promise is that a label reads back to a sentence. An
		// annotation with no line would be a row of labels under no quotation.
		expect(drillDown([annotation('SC04011-01-003#2')], lines, 'Rwanda')).toEqual([]);
	});

	it('narrows on the speaker, on the referent, or on both', () => {
		const all = [
			annotation('SC07000-01-001#1'),
			annotation('SC07481-01-007#1', {
				referent: 'bosnia',
				speaker_position: 'asserts'
			})
		];
		expect(drillDown(all, lines, 'France').map((row) => row.id)).toEqual(['SC07481-01-007#1']);
		expect(drillDown(all, lines, '', 'rwanda_1994').map((row) => row.id)).toEqual([
			'SC07000-01-001#1'
		]);
		expect(drillDown(all, lines, 'France', 'rwanda_1994')).toEqual([]);
		expect(drillDown(all, lines, '', 'bosnia')).toHaveLength(1);
	});

	it('says when the model’s evidence span is not simply the sentence', () => {
		const [same] = drillDown(
			[
				annotation('SC07000-01-001#1', {
					evidence_quote: '  we WARNED that genocide could occur. '
				})
			],
			lines,
			'Rwanda'
		);
		// Whitespace and case are not a difference worth printing the span twice for.
		expect(same.quoteDiffers).toBe(false);

		const [narrower] = drillDown(
			[
				annotation('SC07000-01-001#1', {
					evidence_quote: 'warned that genocide could occur'
				})
			],
			lines,
			'Rwanda'
		);
		expect(narrower.quoteDiffers).toBe(true);
	});

	it('carries a link into the record and a link back into the concordance', () => {
		const [row] = drillDown([annotation('SC07000-01-001#1')], lines, 'Rwanda');
		expect(row.reader.meeting).toBe('SC07000-01');
		expect(row.reader.query).toBe(
			'term=genocide&speech=SC07000-01-001&occurrence=SC07000-01-001%231'
		);
		// The concordance cannot name one line, so the link lands on the smallest
		// set it can express that certainly contains it.
		expect(row.concordance.query).toBe('term=genocide&country=Rwanda&spv=S%2FPV.7000');
	});

	it('carries both readings of a contested occurrence, and none where the two agreed', () => {
		const rows = drillDown(
			[
				annotation('SC07000-01-001#1', {
					contested: ['referent', 'speaker_position'],
					alt: {
						verdict: 'true_positive',
						quotation: 'not_quoted',
						speaker_position: 'rejects',
						function: 'warning_or_prevention|accountability',
						referent: 'bosnia'
					}
				}),
				annotation('SC07481-01-007#1', { referent: 'rwanda_1994' })
			],
			lines,
			'',
			'rwanda_1994',
			{ compared: true, referents: [referent('bosnia', { label: 'Bosnia and Srebrenica' })] }
		);
		// Listed in the artefact's own field order rather than the row's, so two
		// occurrences contested on the same pair read the same way.
		expect(rows[0].contested.map((entry) => entry.field)).toEqual(['speaker_position', 'referent']);
		expect(rows[0].contested[0]).toMatchObject({
			label: 'speaker position',
			published: 'Conditional',
			second: 'Rejects'
		});
		// A referent is named from the controlled list, not printed as its id.
		expect(rows[0].contested[1].second).toBe('Bosnia and Srebrenica');
		expect(rows[1].contested).toEqual([]);
	});

	it('names a contested referent by its identifier when the list is not to hand', () => {
		const [row] = drillDown(
			[
				annotation('SC07000-01-001#1', {
					contested: ['referent'],
					alt: {
						verdict: 'true_positive',
						quotation: 'not_quoted',
						speaker_position: 'conditional',
						function: 'warning_or_prevention|accountability',
						referent: 'genocide_convention_law'
					}
				})
			],
			lines,
			'Rwanda',
			'',
			{ compared: true }
		);
		// Degraded to readable words rather than blank: the drill-down is fed two
		// artefacts and the controlled list is in neither of them.
		expect(row.contested[0].second).toBe('genocide convention law');
	});

	it('narrows to the contested occurrences without a second enumeration of them', () => {
		const all = [
			annotation('SC07000-01-001#1'),
			annotation('SC07481-01-007#1', {
				referent: 'rwanda_1994',
				contested: ['speaker_position'],
				alt: {
					verdict: 'true_positive',
					quotation: 'not_quoted',
					speaker_position: 'asserts',
					function: 'warning_or_prevention|accountability',
					referent: 'rwanda_1994'
				}
			})
		];
		// Nothing is marked on a build that says no second opinion was made, whatever
		// the rows happen to carry: the claim would have nothing behind it.
		expect(drillDown(all, lines, '', 'rwanda_1994')[1].contested).toEqual([]);
		expect(drillDown(all, lines, '', 'rwanda_1994', { compared: true })).toHaveLength(2);
		const only = drillDown(all, lines, '', 'rwanda_1994', { compared: true, contestedOnly: true });
		expect(only.map((row) => row.id)).toEqual(['SC07481-01-007#1']);
		// The filter narrows the same list rather than building another: everything
		// a row carries is what it carried unfiltered.
		expect(only[0].sentence).toBe('The Council must call this genocide by its name.');
		expect(drillDown(all, lines, 'Rwanda', '', { compared: true, contestedOnly: true })).toEqual(
			[]
		);
	});

	it('orders by date and settles every tie on the identifier', () => {
		const rows = drillDown(
			[annotation('SC07481-01-007#1', { referent: 'bosnia' }), annotation('SC07000-01-001#1')],
			lines,
			'',
			''
		);
		expect(rows).toEqual([]);
		const both = drillDown(
			[annotation('SC07481-01-007#1', { referent: 'rwanda_1994' }), annotation('SC07000-01-001#1')],
			lines,
			'',
			'rwanda_1994'
		);
		expect(both.map((row) => row.date)).toEqual(['2014-06-11', '2015-07-08']);
	});
});

describe('the milestones a diffusion curve counts', () => {
	it('holds three firsts, in the order that settles a tie between two of them', () => {
		expect(MILESTONES).toEqual(['mention', 'asserts', 'rejects']);
		expect(milestoneRank('mention')).toBeLessThan(milestoneRank('asserts'));
		// A fourth milestone added upstream sorts last rather than displacing these.
		expect(milestoneRank('first_referral')).toBe(MILESTONES.length);
		expect(milestoneLabel('rejects')).toBe('Refused the word for it');
		expect(milestoneLabel('some_future_first')).toBe('some future first');
	});
});

describe('how a referent spread through the Council', () => {
	const only = (events: UsageDiffusionEvent[], id = 'rwanda_1994'): Usage =>
		corpus({ diffusion: { milestones: [...MILESTONES], referents: [{ id, events }] } });

	it('refuses an empty chronology, and one whose referents carry no events', () => {
		expect(
			diffusionPlan(corpus({ diffusion: { milestones: [...MILESTONES], referents: [] } }), state())
				.refusal
		).toBe('no-diffusion');
		// A referent carried with an empty list is the same nothing: kept as an
		// option it would refuse the moment a reader picked it.
		expect(diffusionPlan(only([], 'bosnia'), state()).refusal).toBe('no-diffusion');
		expect(diffusionPlan(only([], 'bosnia'), state()).options).toEqual([]);
	});

	it('defaults to the first named case rather than to the first entry in the block', () => {
		const plan = diffusionPlan(corpus(), state());
		// `convention` comes first in the block and is not a genocide: a chronology
		// of the Convention is a real thing and not a diffusion of anything.
		expect(plan.referent).toBe('rwanda_1994');
		expect(plan.options.map((option) => option.id)).toEqual(['convention', 'rwanda_1994']);
		expect(plan.options[1]).toMatchObject({ kind: 'case', events: 5, delegations: 2 });
		expect(plan.refusal).toBeNull();
	});

	it('follows the selection the matrix sets, and says when it has nothing for it', () => {
		expect(diffusionPlan(corpus(), state({ referent: 'convention' })).referent).toBe('convention');

		const missing = diffusionPlan(corpus(), state({ referent: 'bosnia' }));
		expect(missing.refusal).toBe('no-events');
		expect(missing.referent).toBe('bosnia');
		expect(missing.drawn).toEqual([]);
		// The picker still carries what is in force. Dropping it would leave the
		// control showing a referent nobody selected while the figure refused.
		expect(missing.options.map((option) => option.id)).toEqual([
			'convention',
			'rwanda_1994',
			'bosnia'
		]);
		expect(missing.options.at(-1)).toMatchObject({ events: 0, delegations: 0 });
	});

	it('refuses a referent whose events are all on a milestone it cannot draw', () => {
		// A run declaring a fourth milestone would put every event of it on a
		// series this figure has no reading for. Empty axes under a key with
		// nothing in it would be the one outcome that says nothing at all.
		const later = only([
			{
				date: '1994-04-21',
				actor: 'Alpha',
				milestone: 'first_referral' as UsageMilestone,
				speaker_position: 'asserts',
				id: 'SC03368-01-005#1'
			}
		]);
		const plan = diffusionPlan(later, state());
		expect(plan.drawn).toEqual([]);
		expect(plan.refusal).toBe('no-events');
	});

	it('counts each delegation once, at its first, and never falls', () => {
		const plan = diffusionPlan(corpus(), state({ referent: 'rwanda_1994' }));
		const asserts = plan.series.find((series) => series.milestone === 'asserts');
		expect(asserts?.points.map((point) => [point.actor, point.value])).toEqual([
			['Alpha', 1],
			['Bravo', 2]
		]);
		expect(plan.totals).toEqual({ mention: 2, asserts: 2, rejects: 1 });
		expect(plan.high).toBe(2);
		expect(plan.events).toBe(5);
	});

	it('draws nothing for a milestone nobody crossed, and says the zero in a number', () => {
		const plan = diffusionPlan(corpus(), state({ referent: 'convention' }));
		// A flat line along the floor reads as a measured nothing rather than as
		// an absence, so the count goes in the prose and not on the drawing.
		expect(plan.drawn.map((series) => series.milestone)).toEqual(['mention']);
		expect(plan.series.map((series) => series.drawn)).toEqual([true, false, false]);
		expect(plan.totals.asserts).toBe(0);
		expect(plan.series[1].path).toBe('');
	});

	it('marks every step while the steps can be told apart, and none once they cannot', () => {
		const sparse = diffusionPlan(corpus(), state({ referent: 'rwanda_1994' }));
		expect(sparse.series.every((series) => series.marker > 0)).toBe(true);

		const crowded = only(
			Array.from({ length: 120 }, (_, index) =>
				moment(
					`${1994 + Math.floor(index / 12)}-01-${String((index % 12) + 1).padStart(2, '0')}`,
					`Speaker ${index}`,
					'asserts',
					'asserts',
					`SC04100-01-${String(index).padStart(3, '0')}#1`
				)
			)
		);
		// A hundred and twenty marks four units wide five units apart are a bead
		// chain along a line that already shows the same thing.
		const asserts = diffusionPlan(crowded, state()).series.find(
			(series) => series.milestone === 'asserts'
		);
		expect(asserts?.points).toHaveLength(120);
		expect(asserts?.marker).toBe(0);
	});

	it('draws the assertion curve last, over the counter-curve and the envelope', () => {
		const plan = diffusionPlan(corpus(), state({ referent: 'rwanda_1994' }));
		expect(plan.drawn.map((series) => series.milestone)).toEqual(['mention', 'rejects', 'asserts']);
	});

	it('drops the envelope when it is the assertion curve drawn a second time', () => {
		const folded = only([
			moment('1994-04-21', 'Alpha', 'mention', 'asserts', 'SC03368-01-005#1'),
			moment('1994-04-21', 'Alpha', 'asserts', 'asserts', 'SC03368-01-005#1')
		]);
		const plan = diffusionPlan(folded, state());
		expect(plan.drawn.map((series) => series.milestone)).toEqual(['asserts']);
		// Dropped from the drawing, kept in the totals: it is still a fact about
		// the record that one delegation placed the word here.
		expect(plan.totals.mention).toBe(1);
	});

	it('lays the steps out on a time axis every referent in the block shares', () => {
		const plan = diffusionPlan(corpus(), state({ referent: 'rwanda_1994' }));
		expect(plan.span).toEqual({ from: '1994-04-21', to: '2004-04-07' });
		const asserts = plan.series.find((series) => series.milestone === 'asserts');
		expect(asserts?.points[0].x).toBeCloseTo(DIFFUSION_BOX.left, 6);
		expect(asserts?.points[1].x).toBeCloseTo(DIFFUSION_BOX.right, 6);
		expect(asserts?.points[1].y).toBeCloseTo(DIFFUSION_BOX.top, 6);
		expect(asserts?.points[0].y).toBeCloseTo((DIFFUSION_BOX.top + DIFFUSION_BOX.bottom) / 2, 6);
		// A floor, a jump at each event, and a flat run to the right-hand edge.
		// Nothing joined between two delegations, and no sloped segment says it did.
		expect(asserts?.path).toBe('M 5.0,175.0 H 5.0 V 90.0 H 715.0 V 5.0 H 715.0');

		// The Convention's single event sits inside that span rather than at the
		// left edge of a span of its own, so switching referents moves the curve
		// along a fixed axis instead of rescaling it.
		const convention = diffusionPlan(corpus(), state({ referent: 'convention' }));
		expect(convention.span).toEqual(plan.span);
		const at = convention.series[0].points[0].x;
		expect(at).toBeGreaterThan(DIFFUSION_BOX.left);
		expect(at).toBeLessThan(DIFFUSION_BOX.right);
	});

	it('puts round years on that axis and anchors the ones at its ends', () => {
		const plan = diffusionPlan(corpus(), state());
		expect(plan.ticks.map((tick) => tick.label)).toEqual(['1996', '1998', '2000', '2002', '2004']);
		// 1994 is on the axis and its January is not: the span is the data's, so a
		// rule outside it would be a year the figure does not cover.
		expect(plan.ticks.every((tick) => tick.x >= DIFFUSION_BOX.left)).toBe(true);
		expect(plan.ticks[0].anchor).toBe('middle');
		// The last one all but touches the right edge, where a centred label would
		// hang off the figure and push a scrollbar onto its body.
		expect(plan.ticks.at(-1)?.anchor).toBe('end');
	});

	it('draws a block holding one dated event down the middle rather than dividing by zero', () => {
		const single = only([moment('1994-04-21', 'Alpha', 'asserts', 'asserts', 'SC03368-01-005#1')]);
		const plan = diffusionPlan(single, state());
		expect(plan.ticks).toEqual([]);
		expect(plan.series[1].points[0].x).toBeCloseTo(
			(DIFFUSION_BOX.left + DIFFUSION_BOX.right) / 2,
			6
		);
	});
});

describe('the chronology the curve summarises', () => {
	const record = (id: string, extra: Partial<KwicLine> = {}): KwicLine => ({
		id,
		spv: 'S/PV.3368',
		date: '1994-04-21',
		country: 'Rwanda',
		iso3: 'RWA',
		group: 'E10',
		type: 'Mentioned',
		agenda: 'The situation concerning Rwanda',
		start: 0,
		end: 8,
		left: '',
		kw: 'genocide',
		right: '',
		sent: 'What is happening is genocide.',
		...extra
	});

	const plan = () => diffusionPlan(corpus(), state({ referent: 'rwanda_1994' }));

	it('lists every step of every drawn curve, oldest first, milestone last', () => {
		const rows = diffusionChronology(plan());
		expect(rows.map((row) => [row.date, row.actor, row.milestone])).toEqual([
			['1994-04-21', 'Alpha', 'mention'],
			['1994-04-21', 'Alpha', 'asserts'],
			['1998-06-01', 'Bravo', 'mention'],
			['1998-06-01', 'Bravo', 'rejects'],
			['2004-04-07', 'Bravo', 'asserts']
		]);
		// One occurrence can be two firsts, and the date and the identifier cannot
		// separate them; the rank can.
		expect(rows[0].id).toBe(rows[1].id);
		expect(rows.map((row) => row.ordinal)).toEqual([1, 1, 2, 1, 2]);
		expect(rows[3].positionLabel).toBe('Rejects');
	});

	it('omits a milestone the figure folded away, whose events are already listed', () => {
		const folded = corpus({
			diffusion: {
				milestones: [...MILESTONES],
				referents: [
					{
						id: 'rwanda_1994',
						events: [
							moment('1994-04-21', 'Alpha', 'mention', 'asserts', 'SC03368-01-005#1'),
							moment('1994-04-21', 'Alpha', 'asserts', 'asserts', 'SC03368-01-005#1')
						]
					}
				]
			}
		});
		expect(diffusionChronology(diffusionPlan(folded, state())).map((row) => row.milestone)).toEqual(
			['asserts']
		);
	});

	it('links into the record from the identifier alone, and into the concordance only with a line', () => {
		const [first] = diffusionChronology(plan());
		expect(first.reader.meeting).toBe('SC03368-01');
		expect(first.reader.query).toBe(
			'term=genocide&speech=SC03368-01-005&occurrence=SC03368-01-005%231'
		);
		// The concordance cannot be addressed without a record symbol, and the
		// symbol lives in a file this page fetches only on demand. A null rather
		// than a link built out of the identifier, which would be a guess.
		expect(first.concordance).toBeNull();
		expect(first.spv).toBe('');

		const joined = diffusionChronology(plan(), [record('SC03368-01-005#1')]);
		expect(joined[0].spv).toBe('S/PV.3368');
		expect(joined[0].concordance?.query).toBe('term=genocide&country=Rwanda&spv=S%2FPV.3368');
		// A row whose line is not in the file keeps its reader link and loses only
		// the concordance one: the chronology is not a list of quotations.
		expect(joined.at(-1)?.concordance).toBeNull();
		expect(joined).toHaveLength(5);
	});
});

describe('the second opinion, as the apparatus states it', () => {
	it('says nothing at all where no comparison run was made', () => {
		const apparatus = comparisonApparatus(corpus());
		expect(apparatus).toMatchObject({ computed: false, state: 'none', model: '', overlap: 0 });
		// The empty block is the ordinary state, and the whole section is drawn on
		// `computed` alone. Nothing here is a measured zero.
		expect(apparatus.fields).toEqual([]);
		expect(apparatus.contestedShare).toBeNull();
		expect(apparatus.functionJaccardText).toBe('—');
	});

	it('names both runs, the overlap they were compared over, and both denominators', () => {
		const apparatus = comparisonApparatus(corpus({ comparison: comparison() }));
		expect(apparatus).toMatchObject({
			computed: true,
			published: 'chatgpt-5.6-luna-2026-08-01',
			model: 'gemini-3-pro-2026-07-15',
			runId: '2026-09-06-gemini-v1',
			overlap: 5800,
			contestedAny: 1800,
			samePrompt: true
		});
		// A run that annotated half the corpus and agreed on all of it is not the
		// finding a run that annotated all of it and agreed on half is, so both
		// shares are stated rather than one.
		expect(apparatus.coverage).toBeCloseTo(6000 / 6092, 12);
		expect(apparatus.contestedShare).toBeCloseTo(1800 / 5800, 12);
		expect(apparatus.abstained).toBe(21);
	});

	it('writes a statistic that could not be computed as a dash, never as a zero', () => {
		const apparatus = comparisonApparatus(corpus({ comparison: comparison() }));
		expect(apparatus.fields.map((row) => row.field)).toEqual([
			'verdict',
			'quotation',
			'speaker_position',
			'referent'
		]);
		// With every row in one category there is no chance agreement to correct
		// for, and 0.00 would read as two runs agreeing by luck alone.
		expect(apparatus.fields[0]).toMatchObject({
			label: 'verdict',
			kappa: null,
			kappaText: '—',
			observedText: '99.00%'
		});
		expect(apparatus.fields[2].kappaText).toBe('0.74');
		expect(apparatus.functionJaccardText).toBe('0.72');
	});

	it('says when the two runs were not made from the same prompt', () => {
		// 15 refuses to publish a comparison made from other instructions, so this
		// should never arrive — but the page states it rather than assuming it.
		const apparatus = comparisonApparatus(
			corpus({ comparison: comparison({ prompt_sha256: 'b'.repeat(64) }) })
		);
		expect(apparatus.samePrompt).toBe(false);
	});
});

describe('the contested passages', () => {
	const record = (id: string, extra: Partial<KwicLine> = {}): KwicLine => ({
		id,
		spv: 'S/PV.7000',
		date: '2014-06-11',
		country: 'Rwanda',
		iso3: 'RWA',
		group: 'E10',
		type: 'Mentioned',
		agenda: 'Protection of civilians',
		start: 0,
		end: 8,
		left: '',
		kw: 'genocide',
		right: '',
		sent: 'We warned that genocide could occur.',
		...extra
	});

	const coded = (
		id: string,
		contested: string[],
		alt: UsageOccurrence['alt'] = null,
		extra: Partial<UsageOccurrence> = {}
	): UsageOccurrence => ({
		id,
		occurrence_id: id,
		verdict: 'true_positive',
		quotation: 'not_quoted',
		concrete_case: 'yes',
		speaker_position: 'asserts',
		function: 'accusation_or_qualification',
		referent: 'rwanda_1994',
		proposed_referent: '',
		referent_source: 'passage',
		accused_actor: '',
		victim_group: '',
		own_state_accused: 'no',
		salience: 'substantive',
		rationale: 'The speaker applies the word in their own voice.',
		confidence: 'high',
		evidence_quote: 'genocide',
		evidence_valid: true,
		contested,
		alt,
		...extra
	});

	const other = (overrides: Partial<UsageAlternative> = {}): UsageAlternative => ({
		verdict: 'true_positive',
		quotation: 'not_quoted',
		speaker_position: 'asserts',
		function: 'accusation_or_qualification',
		referent: 'rwanda_1994',
		...overrides
	});

	const data = corpus({ comparison: comparison({ overlap: 4, contested_any: 2 }) });

	const three = coded(
		'SC07481-01-007#1',
		['speaker_position', 'function', 'referent'],
		other({ speaker_position: 'rejects', function: 'accountability', referent: 'bosnia' })
	);
	const one = coded(
		'SC07000-01-001#1',
		['speaker_position'],
		other({ speaker_position: 'reports_without_position' })
	);
	const agreed = coded('SC07000-01-001#2', []);
	const unquotable = coded('SC04011-01-003#2', ['verdict'], other({ verdict: 'false_positive' }));

	const files = [
		record('SC07000-01-001#1'),
		record('SC07000-01-001#2'),
		record('SC07481-01-007#1', {
			spv: 'S/PV.7481',
			date: '2015-07-08',
			country: 'France',
			group: 'P5',
			sent: 'The Council must call this genocide by its name.'
		})
	];

	it('refuses in words on a build with no second opinion, whatever the rows carry', () => {
		const listing = contestedList(corpus(), [three, one], files);
		expect(listing.refusal).toBe('no-comparison');
		expect(listing.rows).toEqual([]);
	});

	it('says so when a comparison was made and found no difference', () => {
		const listing = contestedList(data, [agreed], files);
		expect(listing.refusal).toBe('no-contest');
		expect(listing.contested).toBe(0);
	});

	it('ranks by how much the two runs disagree, not by date', () => {
		const listing = contestedList(data, [one, agreed, three], files);
		// Three fields apart in 2015 comes before one field apart in 2014: the
		// reader with an afternoon should meet the hardest passage first.
		expect(listing.rows.map((row) => [row.actor, row.fields])).toEqual([
			['France', 3],
			['Rwanda', 1]
		]);
		expect(listing.rows[0].contested.map((entry) => entry.field)).toEqual([
			'speaker_position',
			'function',
			'referent'
		]);
		expect(listing.rows[0].contested[0]).toMatchObject({
			published: 'Asserts',
			second: 'Rejects'
		});
		// The published labels stay published: nothing here is replaced.
		expect(listing.rows[0].referent).toBe('rwanda_1994');
		expect(listing.rows[0].sentence).toBe('The Council must call this genocide by its name.');
		expect(listing.rows[0].reader.meeting).toBe('SC07481-01');
		expect(listing.rows[0].concordance.query).toBe('term=genocide&country=France&spv=S%2FPV.7481');
	});

	it('drops a contested occurrence it cannot quote, and counts what it dropped', () => {
		const listing = contestedList(data, [one, unquotable], files);
		expect(listing.rows.map((row) => row.id)).toEqual(['SC07000-01-001#1']);
		expect(listing.contested).toBe(2);
		expect(listing.quotable).toBe(1);
		expect(listing.unquotable).toBe(1);
		expect(listing.overlap).toBe(4);
		expect(listing.refusal).toBeNull();
	});

	it('caps the list and hands the interface what the cap cost', () => {
		const many = Array.from({ length: CONTESTED_CAP + 7 }, (_, index) =>
			coded(`SC07000-01-${String(index).padStart(3, '0')}#1`, ['speaker_position'], other())
		);
		const rows = many.map((occurrence) => record(occurrence.id));
		const listing = contestedList(data, many, rows);
		expect(listing.rows).toHaveLength(CONTESTED_CAP);
		expect(listing.cap).toBe(CONTESTED_CAP);
		// A cut that does not say it is a cut is the display decision the exports
		// refuse, and the objection holds on screen.
		expect(listing.hidden).toBe(7);
		expect(listing.quotable).toBe(CONTESTED_CAP + 7);
	});

	it('exports every contested occurrence, the cap and the join included', () => {
		const rows = contestedExportRows(data, [one, agreed, three, unquotable], files);
		expect(rows).toHaveLength(3);
		expect(rows[0]).toHaveLength(CONTESTED_COLUMNS.length);
		// Chronological, with the unjoinable row first because it has no date —
		// carried with nulls rather than filtered out, so the file holds the gap.
		expect(rows.map((row) => row[CONTESTED_COLUMNS.indexOf('id')])).toEqual([
			'SC04011-01-003#2',
			'SC07000-01-001#1',
			'SC07481-01-007#1'
		]);
		expect(rows[0][CONTESTED_COLUMNS.indexOf('date')]).toBeNull();
		expect(rows[0][CONTESTED_COLUMNS.indexOf('actor')]).toBeNull();
		// The artefact's own values, not the page's wording: a file is read by a
		// script, and `rejects` is what joins back to the run.
		const last = rows[2];
		expect(last[CONTESTED_COLUMNS.indexOf('contested_fields')]).toBe(
			'speaker_position|function|referent'
		);
		expect(last[CONTESTED_COLUMNS.indexOf('contested_count')]).toBe(3);
		expect(last[CONTESTED_COLUMNS.indexOf('published_speaker_position')]).toBe('asserts');
		expect(last[CONTESTED_COLUMNS.indexOf('comparison_speaker_position')]).toBe('rejects');
		expect(last[CONTESTED_COLUMNS.indexOf('comparison_referent')]).toBe('bosnia');
	});
});

describe('the gold sample’s own state', () => {
	it('reports an untouched sample as untouched rather than as a measured zero', () => {
		const progress = goldProgress(corpus());
		expect(progress).toMatchObject({
			state: 'not_started',
			sampleSize: 200,
			coded: 0,
			coders: 0,
			hasAgreement: false,
			hasModelScores: false
		});
	});

	it('counts the furthest-along coder rather than adding the two together', () => {
		const progress = goldProgress(
			corpus({
				gold: {
					...gold,
					state: 'in_progress',
					coders: [
						{ coder: 'FM', rows: 58 },
						{ coder: 'JG', rows: 40 }
					],
					double_coded: 40,
					human_agreement: [
						{
							field: 'speaker_position',
							observed: 0.83,
							kappa: 0.71,
							kappa_withheld: false,
							minority_share: 0.4,
							pabak: 0.66,
							n: 40
						}
					]
				}
			})
		);
		// Both coders code every sampled occurrence, so summing their totals would
		// report 400 rows coded out of a 200-row sample.
		expect(progress.coded).toBe(58);
		expect(progress.coders).toBe(2);
		expect(progress.doubleCoded).toBe(40);
		expect(progress.hasAgreement).toBe(true);
		expect(progress.hasModelScores).toBe(false);
	});
});

describe('what leaves in a file', () => {
	it('exports every cell the artefact holds, not the rows the figure drew', () => {
		const data = corpus();
		const rows = matrixExportRows(data);
		expect(rows).toHaveLength(data.matrix.length);
		expect(rows[0]).toHaveLength(MATRIX_COLUMNS.length);
		const bravo = rows.find((row) => row[0] === 'Bravo' && row[4] === 'rwanda_1994');
		// The withheld share travels as a null beside a `sufficient` column, so the
		// file carries the gate rather than having been filtered by it.
		expect(bravo?.[MATRIX_COLUMNS.indexOf('share_of_assigned')]).toBeNull();
		expect(bravo?.[MATRIX_COLUMNS.indexOf('sufficient')]).toBe(false);
		const alpha = rows.find((row) => row[0] === 'Alpha' && row[4] === 'rwanda_1994');
		expect(alpha?.[MATRIX_COLUMNS.indexOf('share_of_assigned')]).toBeCloseTo(4 / 6, 12);
		expect(alpha?.[MATRIX_COLUMNS.indexOf('position_asserts')]).toBe(3);
	});

	it('exports every first of every referent, not the one the picker was showing', () => {
		const rows = diffusionExportRows(corpus());
		expect(rows).toHaveLength(6);
		expect(rows[0]).toHaveLength(DIFFUSION_COLUMNS.length);
		expect(rows[0][DIFFUSION_COLUMNS.indexOf('referent')]).toBe('convention');
		expect(rows[0][DIFFUSION_COLUMNS.indexOf('referent_kind')]).toBe('meta');
		// An envelope the figure folds away is still an event the run recorded.
		const milestone = DIFFUSION_COLUMNS.indexOf('milestone');
		expect(rows.filter((row) => row[milestone] === 'mention')).toHaveLength(3);
		expect(
			diffusionExportRows(corpus({ diffusion: { milestones: [...MILESTONES], referents: [] } }))
		).toEqual([]);
	});

	it('exports every speaker_position profile, withheld shares included', () => {
		const rows = positionExportRows(corpus());
		expect(rows.map((row) => row[0])).toEqual(['Alpha', 'Bravo']);
		expect(rows[0]).toHaveLength(POSITION_COLUMNS.length);
		expect(rows[1][POSITION_COLUMNS.indexOf('share_rejects')]).toBeNull();
		expect(rows[0][POSITION_COLUMNS.indexOf('position_rejects')]).toBe(2);
	});
});

describe('what a second instrument does to the figures', () => {
	it('carries a contested count and share into every drawn cell', () => {
		const plan = matrixPlan(
			corpus({
				matrix: [
					cell('Alpha', 'rwanda_1994', 4, { asserts: 4 }, 1),
					cell('Alpha', 'bosnia', 2, { asserts: 2 }, 0)
				],
				comparison: comparison()
			}),
			USAGE_DEFAULTS
		);
		const cells = plan.rows[0].cells;
		const rwanda = cells.find((entry) => entry.referent === 'rwanda_1994');
		const bosnia = cells.find((entry) => entry.referent === 'bosnia');
		expect(rwanda?.contested).toBe(1);
		expect(rwanda?.contestedShare).toBe(0.25);
		expect(bosnia?.contestedShare).toBe(0);
		// An empty cell has no share to state rather than a zero one.
		const empty = cells.find((entry) => entry.count === 0);
		expect(empty?.contestedShare ?? null).toBeNull();
	});

	it('publishes PABAK beside a withheld kappa and says which it was', () => {
		const apparatus = comparisonApparatus(corpus({ comparison: comparison() }));
		const verdict = apparatus.fields.find((row) => row.field === 'verdict');
		const speaker_position = apparatus.fields.find((row) => row.field === 'speaker_position');
		expect(verdict?.kappaText).toBe('—');
		expect(verdict?.kappaWithheld).toBe(true);
		// 2 * 0.99 - 1 = 0.98, the prevalence-adjusted figure the fixture carries.
		expect(verdict?.pabakText).toBe('0.98');
		// A field with information in both margins keeps its kappa and is not
		// reported as withheld, which is a different finding from undefined.
		expect(speaker_position?.kappaWithheld).toBe(false);
		expect(speaker_position?.kappaText).toBe('0.74');
	});

	it('reads the multi-label field through alpha as well as through overlap', () => {
		const apparatus = comparisonApparatus(
			corpus({
				comparison: comparison({
					function_alpha_masi: 0.61,
					function_labels: [
						{ label: 'accountability', left: 10, right: 12, observed: 0.9, kappa: 0.78 },
						{ label: 'commemoration', left: 4, right: 4, observed: 1, kappa: null }
					]
				})
			})
		);
		expect(apparatus.functionJaccardText).toBe('0.72');
		expect(apparatus.functionAlphaText).toBe('0.61');
		expect(apparatus.functionLabels.map((row) => row.kappaText)).toEqual(['0.78', '—']);
	});

	it('names the two labels whose count is partly a property of the instrument', () => {
		expect(isInstrumentDependent('reports_without_position')).toBe(true);
		expect(isInstrumentDependent('attributed_or_reported')).toBe(true);
		expect(isInstrumentDependent('asserts')).toBe(false);
		expect(isInstrumentDependent('rejects')).toBe(false);
	});

	it('lays each model against another call of itself', () => {
		const rows = retestRows(
			corpus({
				comparison: comparison(),
				retest: [
					{
						which: 'published',
						model: model.id,
						run_id: model.run_id,
						retest_run_id: '2026-08-30-luna-pilot',
						overlap: 91,
						fields: [field('speaker_position', 0.945, 0.885, 5)],
						function_jaccard: 0.886,
						identical: 69
					}
				]
			})
		);
		expect(rows).toHaveLength(1);
		expect(rows[0].retestRunId).toBe('2026-08-30-luna-pilot');
		// 69 of 91: about a quarter of one model's own labels move between two
		// calls, which is what the cross-model column has to be read against.
		expect(rows[0].identicalShare).toBeCloseTo(69 / 91, 6);
		expect(rows[0].fields[0].observedText).toBe('94.50%');
		expect(retestRows(corpus({}))).toEqual([]);
	});

	it('withholds a chronology for a referent the two instruments read differently', () => {
		const unstable = corpus({
			comparison: comparison({
				referents: [
					{
						label: 'rwanda_1994',
						precision: 0.6,
						recall: 0.62,
						f1: 0.61,
						support: 120,
						predicted: 118,
						correct: 72,
						measurable: true
					}
				]
			})
		});
		const plan = diffusionPlan(unstable, { ...USAGE_DEFAULTS, referent: 'rwanda_1994' });
		expect(plan.refusal).toBe('unstable-referent');
		expect(plan.reliability).toBe(0.61);
		// The picker still offers every referent, so the reader can move on.
		expect(plan.options.length).toBeGreaterThan(0);
	});

	it('draws a chronology where the two instruments hold together', () => {
		const stable = corpus({
			comparison: comparison({
				referents: [
					{
						label: 'rwanda_1994',
						precision: 0.94,
						recall: 0.95,
						f1: 0.945,
						support: 120,
						predicted: 121,
						correct: 114,
						measurable: true
					}
				]
			})
		});
		const plan = diffusionPlan(stable, { ...USAGE_DEFAULTS, referent: 'rwanda_1994' });
		expect(plan.refusal).toBeNull();
	});

	it('draws every chronology where no second instrument was asked', () => {
		// The withholding is a statement about two readings. With one reading
		// there is nothing to withhold on, and a blank figure would say the
		// opposite of what the empty comparison block means.
		const plan = diffusionPlan(corpus({}), { ...USAGE_DEFAULTS, referent: 'rwanda_1994' });
		expect(plan.refusal).toBeNull();
	});
});

describe('who rejects the word, ordered by what can be ordered', () => {
	const rows: UsagePositionRow[] = [
		{
			actor: 'Sudan',
			eligible: 43,
			sufficient: true,
			positions: positions({ asserts: 24, rejects: 19 }),
			share_rejects: 0.441,
			share_low: 0.304,
			share_high: 0.589,
			separated: true
		},
		{
			actor: 'Kenya',
			eligible: 24,
			sufficient: true,
			positions: positions({ asserts: 23, rejects: 1 }),
			share_rejects: 0.042,
			share_low: 0.007,
			share_high: 0.202,
			separated: false
		},
		{
			actor: 'China',
			eligible: 29,
			sufficient: true,
			positions: positions({ asserts: 27, rejects: 2 }),
			share_rejects: 0.069,
			share_low: 0.019,
			share_high: 0.222,
			separated: false
		}
	];

	it('puts the separated rows first and does not rank the rest by share', () => {
		const result = positionRanking(corpus({ position_by_actor: rows, minimum_occurrences: 20 }));
		// Sudan clears the corpus rate. China's 6.9% is higher than Kenya's 4.2%
		// and both intervals cover 1.7%, so the two are ordered by count and the
		// order is not a claim that one rejects more often than the other.
		expect(result.rows.map((row) => row.actor)).toEqual(['Sudan', 'China', 'Kenya']);
		expect(result.rows.map((row) => row.separated)).toEqual([true, false, false]);
		expect(result.rows[0].rejects).toBe(19);
		expect(result.rows[0].intervalText).toBe('30.40%–58.90%');
	});

	it('writes a dash where the artefact recorded no interval', () => {
		const result = positionRanking(
			corpus({
				minimum_occurrences: 20,
				position_by_actor: [{ ...rows[0], share_low: null, share_high: null, separated: false }]
			})
		);
		expect(result.rows[0].intervalText).toBe('—');
	});
});
