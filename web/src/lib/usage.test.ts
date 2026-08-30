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
	MATRIX_COLUMNS,
	NAVIGATION_KEYS,
	ROW_CAP,
	STANCES,
	STANCE_COLUMNS,
	USAGE_DEFAULTS,
	USAGE_TERM,
	drillDown,
	emptyStances,
	goldProgress,
	matrixExportRows,
	matrixPlan,
	orderReferents,
	readUsageState,
	selectUsage,
	stanceExportRows,
	stanceLabel,
	stanceRanking,
	stepFocus,
	usageParams
} from './usage';
import type { UsageState } from './usage';
import type {
	KwicLine,
	StanceCounts,
	Usage,
	UsageActor,
	UsageMatrixCell,
	UsageOccurrence,
	UsageReferent,
	UsageStanceRow
} from './types';

const meta = { script: '15_usage.py', generated: '2026-09-01T00:00:00Z' };

const model: Usage['model'] = {
	id: 'chatgpt-5.6-luna-2026-08-01',
	run_id: '2026-09-01-luna-v1',
	run_date: '2026-09-01',
	prompt_version: '1',
	prompt_sha256: 'a'.repeat(64),
	reasoning_effort: 'high',
	requests: 3273,
	occurrences_total: 6092,
	occurrences_annotated: 6092,
	parse_failures: 0,
	evidence_invalid: 0,
	abstention: { verdict_uncertain: 0, referent_unclear: 0, stance_unclear: 0 },
	tokens: { input: 0, output: 0 }
};

const gold: Usage['gold'] = {
	sample_size: 200,
	unique_occurrences: 197,
	coders: [],
	double_coded: 0,
	adjudicated: 0,
	human_agreement: [],
	model_vs_human: [],
	state: 'not_started'
};

const stances = (partial: Partial<StanceCounts> = {}): StanceCounts => ({
	...emptyStances(),
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
	kind: 'case',
	iso3: '',
	years: '',
	occurrences: 1,
	...extra
});

const cell = (
	actorName: string,
	referentId: string,
	count: number,
	partial: Partial<StanceCounts> = {}
): UsageMatrixCell => ({
	actor: actorName,
	referent: referentId,
	count,
	stances: stances(partial)
});

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
		cell('Alpha', 'rwanda_1994', 4, { asserts: 3, rejects_or_denies: 1 }),
		cell('Alpha', 'bosnia', 1, { asserts: 1 }),
		cell('Alpha', 'convention', 1, { neutral_legal_reference: 1 }),
		cell('Bravo', 'rwanda_1994', 1, { rejects_or_denies: 1 }),
		cell('Bravo', 'convention', 1, { neutral_legal_reference: 1 })
	],
	stance_by_actor: [
		{
			actor: 'Alpha',
			eligible: 8,
			sufficient: true,
			stances: stances({ asserts: 5, rejects_or_denies: 2, unclear: 1 }),
			share_rejects: 0.25
		},
		{
			actor: 'Bravo',
			eligible: 3,
			sufficient: false,
			stances: stances({ asserts: 3 }),
			share_rejects: null
		}
	],
	gold,
	...overrides
});

const state = (partial: Partial<UsageState> = {}): UsageState => ({
	...USAGE_DEFAULTS,
	...partial
});

describe('the stance vocabulary', () => {
	it('holds the codebook’s seven values in the codebook’s order', () => {
		// Fixed rather than derived: the stacked bar is only comparable between
		// delegations if the same band is in the same place in every one of them.
		expect(STANCES).toEqual([
			'asserts',
			'attributes_or_reports',
			'rejects_or_denies',
			'hypothetical_or_conditional',
			'neutral_legal_reference',
			'unclear',
			'not_applicable'
		]);
		expect(Object.keys(emptyStances())).toEqual([...STANCES]);
		expect(Object.values(emptyStances()).every((value) => value === 0)).toBe(true);
	});

	it('names a stance for a reader, and degrades a value it has never seen', () => {
		expect(stanceLabel('rejects_or_denies')).toBe('Rejects or denies');
		expect(stanceLabel('some_future_label')).toBe('some future label');
	});

	it('annotates exactly one term, and says which', () => {
		expect(USAGE_TERM).toBe('genocide');
	});
});

describe('usage URL state', () => {
	it('round-trips every analytical control', () => {
		const data = corpus();
		const wanted = state({
			actor: 'Alpha',
			referent: 'rwanda_1994',
			unit: 'share',
			sort: 'name'
		});
		expect(readUsageState(usageParams(wanted), data)).toEqual(wanted);
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
		expect(alpha.cells[2].stances).toEqual(emptyStances());
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
	it('ranks only the shares the artefact published, most rejecting first', () => {
		const rows: UsageStanceRow[] = [
			{
				actor: 'Alpha',
				eligible: 8,
				sufficient: true,
				stances: stances({ asserts: 5, rejects_or_denies: 2, unclear: 1 }),
				share_rejects: 0.25
			},
			{
				actor: 'Delta',
				eligible: 10,
				sufficient: true,
				stances: stances({ asserts: 5, rejects_or_denies: 5 }),
				share_rejects: 0.5
			},
			{
				actor: 'Bravo',
				eligible: 3,
				sufficient: false,
				stances: stances({ asserts: 3 }),
				share_rejects: null
			}
		];
		const result = stanceRanking(corpus({ stance_by_actor: rows }));
		expect(result.rows.map((row) => row.actor)).toEqual(['Delta', 'Alpha']);
		// Not ranked low; not ranked. A null read through `?? 0` would put every
		// rarely-heard delegation at the foot of a ranking of rejection.
		expect(result.withheld.map((row) => row.actor)).toEqual(['Bravo']);
		expect(result.withheld[0].total).toBe(3);
		expect(result.minimum).toBe(4);
	});

	it('withholds a row that claims to be sufficient and carries no share', () => {
		const result = stanceRanking(
			corpus({
				stance_by_actor: [
					{
						actor: 'Alpha',
						eligible: 9,
						sufficient: true,
						stances: stances({ asserts: 9 }),
						share_rejects: null
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
		const result = stanceRanking(corpus());
		const alpha = result.rows[0];
		expect(alpha.total).toBe(8);
		expect(alpha.segments.map((segment) => segment.stance)).toEqual([
			'asserts',
			'rejects_or_denies',
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
		stance: 'hypothetical_or_conditional',
		function: 'warning_or_prevention|accountability',
		referent: 'rwanda_1994',
		proposed_referent: '',
		confidence: 'high',
		evidence_quote: 'We warned that genocide could occur.',
		evidence_valid: true,
		...extra
	});

	const lines = [
		line('UNSC_2014_SPV.7000_spch0001#1'),
		line('UNSC_2015_SPV.7481_spch0007#1', {
			spv: 'S/PV.7481',
			date: '2015-07-08',
			country: 'France',
			group: 'P5',
			sent: 'The Council must call this genocide by its name.'
		})
	];

	it('shows nothing at all until something is selected', () => {
		expect(drillDown([annotation('UNSC_2014_SPV.7000_spch0001#1')], lines)).toEqual([]);
	});

	it('joins an annotation to the sentence it labels, on the line identifier alone', () => {
		const rows = drillDown(
			[annotation('UNSC_2014_SPV.7000_spch0001#1')],
			lines,
			'Rwanda',
			'rwanda_1994'
		);
		expect(rows).toHaveLength(1);
		expect(rows[0]).toMatchObject({
			country: 'Rwanda',
			spv: 'S/PV.7000',
			sentence: 'We warned that genocide could occur.',
			stanceLabel: 'Hypothetical or conditional',
			functions: ['warning_or_prevention', 'accountability'],
			quoteDiffers: false
		});
	});

	it('drops an annotation whose line is not in the concordance file', () => {
		// The view's whole promise is that a label reads back to a sentence. An
		// annotation with no line would be a row of labels under no quotation.
		expect(drillDown([annotation('UNSC_1999_SPV.4011_spch0003#2')], lines, 'Rwanda')).toEqual([]);
	});

	it('narrows on the speaker, on the referent, or on both', () => {
		const all = [
			annotation('UNSC_2014_SPV.7000_spch0001#1'),
			annotation('UNSC_2015_SPV.7481_spch0007#1', { referent: 'bosnia', stance: 'asserts' })
		];
		expect(drillDown(all, lines, 'France').map((row) => row.id)).toEqual([
			'UNSC_2015_SPV.7481_spch0007#1'
		]);
		expect(drillDown(all, lines, '', 'rwanda_1994').map((row) => row.id)).toEqual([
			'UNSC_2014_SPV.7000_spch0001#1'
		]);
		expect(drillDown(all, lines, 'France', 'rwanda_1994')).toEqual([]);
		expect(drillDown(all, lines, '', 'bosnia')).toHaveLength(1);
	});

	it('says when the model’s evidence span is not simply the sentence', () => {
		const [same] = drillDown(
			[
				annotation('UNSC_2014_SPV.7000_spch0001#1', {
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
				annotation('UNSC_2014_SPV.7000_spch0001#1', {
					evidence_quote: 'warned that genocide could occur'
				})
			],
			lines,
			'Rwanda'
		);
		expect(narrower.quoteDiffers).toBe(true);
	});

	it('carries a link into the record and a link back into the concordance', () => {
		const [row] = drillDown([annotation('UNSC_2014_SPV.7000_spch0001#1')], lines, 'Rwanda');
		expect(row.reader.meeting).toBe('UNSC_2014_SPV.7000');
		expect(row.reader.query).toBe(
			'term=genocide&speech=UNSC_2014_SPV.7000_spch0001&occurrence=UNSC_2014_SPV.7000_spch0001%231'
		);
		// The concordance cannot name one line, so the link lands on the smallest
		// set it can express that certainly contains it.
		expect(row.concordance.query).toBe('term=genocide&country=Rwanda&spv=S%2FPV.7000');
	});

	it('orders by date and settles every tie on the identifier', () => {
		const rows = drillDown(
			[
				annotation('UNSC_2015_SPV.7481_spch0007#1', { referent: 'bosnia' }),
				annotation('UNSC_2014_SPV.7000_spch0001#1')
			],
			lines,
			'',
			''
		);
		expect(rows).toEqual([]);
		const both = drillDown(
			[
				annotation('UNSC_2015_SPV.7481_spch0007#1', { referent: 'rwanda_1994' }),
				annotation('UNSC_2014_SPV.7000_spch0001#1')
			],
			lines,
			'',
			'rwanda_1994'
		);
		expect(both.map((row) => row.date)).toEqual(['2014-06-11', '2015-07-08']);
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
					human_agreement: [{ field: 'stance', observed: 0.83, kappa: 0.71, n: 40 }]
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
		expect(alpha?.[MATRIX_COLUMNS.indexOf('stance_asserts')]).toBe(3);
	});

	it('exports every stance profile, withheld shares included', () => {
		const rows = stanceExportRows(corpus());
		expect(rows.map((row) => row[0])).toEqual(['Alpha', 'Bravo']);
		expect(rows[0]).toHaveLength(STANCE_COLUMNS.length);
		expect(rows[1][STANCE_COLUMNS.indexOf('share_rejects')]).toBeNull();
		expect(rows[0][STANCE_COLUMNS.indexOf('stance_rejects_or_denies')]).toBe(2);
	});
});
