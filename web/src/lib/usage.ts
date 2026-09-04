/**
 * What the usage view decides, kept out of the components that draw it.
 *
 * The view answers two questions that a count of the word `genocide` cannot:
 * which genocide a delegation means when it says the word, and what it is doing
 * with it. Both readings are a model's, and everything below is arranged so
 * that the interface can never claim more than the model said.
 *
 * **Three denominators, never one.** An occurrence is a match; an *eligible*
 * occurrence is one the model judged a real use of the word with a quotable
 * span behind it; an *assigned* occurrence is an eligible one it could place on
 * a concrete referent. The matrix counts assigned, the speaker_position profile counts
 * eligible, and `matrixPlan` reports the gap between all three rather than
 * closing it — a table whose columns sum to less than the corpus is the honest
 * shape here, and the disclosure line is what makes it readable.
 *
 * **A share below the minimum is not drawn, a count is.** The same rule
 * `actors.ts` follows, for the same reason and with the same partition on the
 * artefact's own `sufficient` flag: two occurrences out of two is not "100% of
 * this delegation's uses". But a *count* of two is a fact about the record, so
 * the cell is drawn under the count unit and hatched under the share unit. This
 * is the distinction `Standing.svelte` states in prose: a share of a known
 * total is a fact, a rate estimated from a handful is not.
 *
 * **Nothing is cut without saying so.** The row cap exists because a matrix
 * with a hundred rows is a picture nobody reads, and `MatrixDisclosure` carries
 * what the cap left out, how many occurrences went with it, how many speakers
 * the model placed nothing for, and how many referents on the list no drawn row
 * ever used. The interface prints those numbers; it does not have the option of
 * quietly showing forty rows as though they were all of them.
 *
 * **Meta referents are grouped, not ranked.** `genocide_convention_law` and
 * `genocide_in_general` are not genocides; they are ways of talking about the
 * category. Ranked by count they would sit among Rwanda and Srebrenica and read
 * as one more case, so they are moved to the end of the column order and the
 * figure draws a rule before them.
 *
 * **A second opinion is not a second measurement.** Where a comparison run
 * exists, a second model was given the byte-identical prompt and the same
 * occurrences, and the ones the two read differently are marked as *contested*.
 * That is a reading list, not an error report: agreement between two models
 * measures stability across instruments, never accuracy, and the human gold
 * sample remains the only calibration. Nothing below lets the second reading
 * into a count — the matrix, the speaker_position profile and the diffusion curve are
 * drawn from the published run alone, and `contestedList` and the contested
 * filter are the only places the other run appears at all.
 *
 * **A diffusion curve counts delegations, not states.** The last figure here
 * plots when each delegation first placed the word on a referent, first asserted
 * it and first refused it, cumulated over the corpus. It is a curve of *speech
 * in this record*: a delegation that never spoke cannot appear on it, and a flat
 * stretch is as often an empty Council calendar as a silence about the case. The
 * arithmetic below therefore ends at counting firsts and drawing them; the
 * sentence that says what the shape is not belongs to the figure's caveat.
 */

import { CONCORDANCE_DEFAULTS, readerQuery } from './concordance';
import { COMPARED_FIELDS, meetingOf } from './data';
import { decimal, percent, termLabel } from './format';
import { tone } from './theme';
import type {
	KwicLine,
	Position,
	PositionCounts,
	Usage,
	UsageActor,
	UsageAlternative,
	UsageClassRow,
	UsageComparison,
	UsageComparisonField,
	UsageDiffusionEvent,
	UsageGold,
	UsageMatrixCell,
	UsageMilestone,
	UsageOccurrence,
	UsageReferent
} from './types';

/**
 * The one lexicon term this layer annotates.
 *
 * `genocide` alone is the population annotated by this layer, and a link out
 * of this view has to name the term it is showing
 * rather than inherit whatever the concordance last had.
 */
export const USAGE_TERM = 'genocide';

/**
 * The seven positions, in the codebook's own order.
 *
 * Fixed rather than read off a payload, because it is the order the stacked bar
 * draws in: two delegations are comparable only if the same band is in the same
 * place in both, and an order derived from each row's own counts would move it.
 */
export const POSITIONS: readonly Position[] = [
	'asserts',
	'reports_without_position',
	'rejects',
	'conditional',
	'no_position',
	'unclear',
	'not_applicable'
];

const POSITION_LABELS: Record<Position, string> = {
	asserts: 'Asserts',
	reports_without_position: 'Reports without a position',
	rejects: 'Rejects',
	conditional: 'Conditional',
	no_position: 'No position (not a case)',
	unclear: 'Unclear',
	not_applicable: 'Not applicable'
};

/**
 * What `concrete_case` is called on screen.
 *
 * Annotation schema 3 splits the abstract-or-concrete decision out of the
 * position field, and a run coded against schema 2 answers it by derivation
 * from its own referent — so `unclear` here is a real reading and not a gap.
 */
const CASE_LABELS: Record<string, string> = {
	yes: 'A named case',
	no: 'No case (legal or abstract)',
	unclear: 'Unclear',
	not_applicable: 'Not applicable'
};

/** What a `concrete_case` value is called on screen. */
export const caseLabel = (value: string): string => CASE_LABELS[value] ?? termLabel(value);

/** What a speaker_position is called on screen. An unknown value degrades to readable words. */
export const positionLabel = (speaker_position: string): string =>
	POSITION_LABELS[speaker_position as Position] ?? termLabel(speaker_position);

/** Every speaker_position at zero. An absent key and a measured zero must not be confused. */
export const emptyPositions = (): PositionCounts =>
	Object.fromEntries(POSITIONS.map((speaker_position) => [speaker_position, 0])) as PositionCounts;

const sumPositions = (positions: PositionCounts): number =>
	POSITIONS.reduce((total, speaker_position) => total + (positions[speaker_position] ?? 0), 0);

/**
 * How many rows the matrix draws before it starts leaving speakers out.
 *
 * 197 of the 198 speakers in the run have something placed, and the tail is
 * long and thin: the seventieth delegation has 19 placed occurrences and the
 * hundredth has 12, so past that point a row is a handful of ones and the table
 * is a scroll rather than a comparison. Seventy is where the artefact's own
 * minimum falls — 68 delegations clear it — so the cut lands just below the
 * last delegation whose share is publishable at all rather than in the middle
 * of the comparison.
 *
 * That coincidence is not enforced here and must not be assumed: the minimum is
 * counted on eligible occurrences and the ordering is by placed ones, so a
 * later run could put a sufficient speaker below the line.
 * `MatrixDisclosure.hiddenSufficient` counts exactly that case so the interface
 * can say it happened instead of the figure quietly dropping a publishable row.
 */
export const ROW_CAP = 70;

/* -------------------------------------------------------------------------- *
 * The analytical state a URL carries
 * -------------------------------------------------------------------------- */

/** Occurrences, or those occurrences as a share of the row speaker's own total. */
export type UsageUnit = 'count' | 'share';

/** How the rows of the matrix are ordered. All three come from the artefact. */
export type UsageSort = 'assigned' | 'occurrences' | 'name';

export interface UsageState {
	/**
	 * The selected referent and speaker, or `''` for none.
	 *
	 * Empty strings rather than `undefined`, which is the concordance's idiom
	 * for the same thing: a filter that is not in force is a value that is not
	 * set, and one representation for that keeps `readUsageState` total.
	 */
	referent: string;
	actor: string;
	unit: UsageUnit;
	sort: UsageSort;
	/**
	 * Narrow the drill-down to the occurrences two models read differently.
	 *
	 * A filter on the quotations and on nothing else: the matrix, the speaker_position
	 * profile and the diffusion curve are drawn from the published run alone and
	 * a second opinion never redraws them.
	 */
	contested: boolean;
}

export const USAGE_DEFAULTS: UsageState = {
	referent: '',
	actor: '',
	// Counts first, and on purpose: they are facts about the record and are
	// published for every speaker, where a share is withheld under the minimum.
	unit: 'count',
	sort: 'assigned',
	contested: false
};

const SORTS = new Set<UsageSort>(['assigned', 'occurrences', 'name']);

/**
 * Parse and normalize the usage controls from a copied URL.
 *
 * A selection that names a speaker or a referent this artefact does not carry
 * is dropped rather than kept: it would open a drill-down that can never fill,
 * and the reader would have no way to tell a stale link from an empty cell.
 */
export function readUsageState(params: URLSearchParams, data: Usage): UsageState {
	const askedActor = params.get('actor');
	const askedReferent = params.get('referent');
	const askedSort = params.get('sort') as UsageSort | null;
	return {
		actor:
			askedActor && data.actors.some((actor) => actor.country_org === askedActor)
				? askedActor
				: USAGE_DEFAULTS.actor,
		referent:
			askedReferent && data.referents.some((referent) => referent.id === askedReferent)
				? askedReferent
				: USAGE_DEFAULTS.referent,
		unit: params.get('unit') === 'share' ? 'share' : USAGE_DEFAULTS.unit,
		sort: askedSort && SORTS.has(askedSort) ? askedSort : USAGE_DEFAULTS.sort,
		// Dropped on a build with no second opinion, for the reason a referent this
		// artefact does not carry is dropped: the control it belongs to is not on
		// the page, so the filter would narrow a list to nothing with nothing on
		// screen saying why.
		contested: params.get('contested') === '1' && data.comparison.state === 'computed'
	};
}

/** Serialize only what differs from the documented defaults. */
export function usageParams(state: UsageState): URLSearchParams {
	const params = new URLSearchParams();
	if (state.actor !== USAGE_DEFAULTS.actor) params.set('actor', state.actor);
	if (state.referent !== USAGE_DEFAULTS.referent) params.set('referent', state.referent);
	if (state.unit !== USAGE_DEFAULTS.unit) params.set('unit', state.unit);
	if (state.sort !== USAGE_DEFAULTS.sort) params.set('sort', state.sort);
	if (state.contested !== USAGE_DEFAULTS.contested) params.set('contested', '1');
	return params;
}

/**
 * Apply a selection, or release it when it is the one already in force.
 *
 * Toggling rather than only narrowing is what makes the matrix a control and
 * not a one-way street: the cell that opened a drill-down is the cell that
 * closes it, and a reader never has to hunt for the way back out. The same rule
 * `facetClick` follows in `concordance.ts`, and for the same reason.
 *
 * A heading passes an empty string for the axis it does not name, so selecting
 * a delegation on its own and selecting one cell are the same operation.
 */
export function selectUsage(state: UsageState, actor: string, referent: string): UsageState {
	const already = state.actor === actor && state.referent === referent;
	return already ? { ...state, actor: '', referent: '' } : { ...state, actor, referent };
}

/* -------------------------------------------------------------------------- *
 * The matrix
 * -------------------------------------------------------------------------- */

export type CellState = 'drawn' | 'withheld-share' | 'empty';

export interface MatrixCell {
	actor: string;
	referent: string;
	count: number;
	/** Of the row speaker's assigned occurrences. Null wherever it is withheld. */
	share: number | null;
	/**
	 * How many of this cell's occurrences a second instrument read differently.
	 *
	 * Zero where no comparison run was made, which is not agreement — the
	 * apparatus above the figure says which of the two it is. Where one was, a
	 * cell is a count of occurrences the two models placed here *and* of ones
	 * only this model did, and that proportion is the cell's own caveat.
	 */
	contested: number;
	contestedShare: number | null;
	positions: PositionCounts;
	/** 0–1 against the largest drawn cell. A length may use this. */
	weight: number;
	/** Where it sits on the colour ramp, which is not `weight`. Never a length. */
	tone: number;
	state: CellState;
	selected: boolean;
}

export interface MatrixRow {
	actor: UsageActor;
	cells: MatrixCell[];
	selected: boolean;
}

export interface MatrixColumn {
	referent: UsageReferent;
	/**
	 * Not a named case, and therefore grouped after the ones that are.
	 *
	 * Two kinds land here: the `meta` referents — the Convention, the legal
	 * definition, an institution's title, a warning about no case in particular
	 * — and `other`, which the codebook defines as a referent a coder could
	 * identify but the controlled list does not yet carry. None of them is a
	 * genocide, and ranked among Rwanda and Srebrenica by count each would read
	 * as one more of them.
	 */
	grouped: boolean;
	/** Occurrences in this column among the rows actually drawn. */
	drawn: number;
	selected: boolean;
}

/** What the figure has to say out loud about everything it is not showing. */
export interface MatrixDisclosure {
	/** Speakers with at least one assigned occurrence, before the cap. */
	speakers: number;
	/** Rows the cap left out, and the assigned occurrences they hold. */
	hiddenRows: number;
	hiddenOccurrences: number;
	/**
	 * Hidden rows whose share the artefact publishes. Normally zero.
	 *
	 * The cap is a flat number and sufficiency is counted on a different
	 * denominator, so the two can in principle disagree. If they ever do, the
	 * figure has cut a delegation it could have drawn a share for, and this is
	 * what lets the interface say so rather than let it pass.
	 */
	hiddenSufficient: number;
	/** Speakers the model placed nothing for. They have no row at all. */
	silent: number;
	/** Drawn rows whose shares are withheld for being under the minimum. */
	withheldRows: number;
	/** Eligible occurrences the model would not place on any referent. */
	unassigned: number;
	/** Occurrences that never became eligible: not a real use, or unquotable. */
	ineligible: number;
	/** Referents a column exists for that no drawn row uses. The columns are kept. */
	emptyColumns: number;
	/** Occurrences inside the cells actually drawn. */
	drawn: number;
}

export interface MatrixPlan {
	rows: MatrixRow[];
	columns: MatrixColumn[];
	/** Index of the first column that is not a named case, or -1 when every one is. */
	groupedFrom: number;
	unit: UsageUnit;
	sort: UsageSort;
	/** The top of the ramp, in the unit in force. The bottom is zero. */
	high: number;
	minimum: number;
	cap: number;
	disclosure: MatrixDisclosure;
	/** Why there is nothing to draw, when there is nothing to draw. */
	refusal: 'no-assignments' | null;
}

/**
 * The sparse matrix, indexed for lookup: speaker, then referent.
 *
 * Nested rather than keyed on the two joined into one string. A composite key
 * needs a separator that can occur in neither half, and both halves here are
 * corpus data — a delegation’s name and a referent identifier — so that
 * guarantee would be an assumption rather than a fact, and what it protects
 * against is two cells silently becoming one.
 */
function index(matrix: readonly UsageMatrixCell[]): Map<string, Map<string, UsageMatrixCell>> {
	const byActor = new Map<string, Map<string, UsageMatrixCell>>();
	for (const cell of matrix) {
		const own = byActor.get(cell.actor) ?? new Map<string, UsageMatrixCell>();
		own.set(cell.referent, cell);
		byActor.set(cell.actor, own);
	}
	return byActor;
}

function compareActors(sort: UsageSort) {
	return (a: UsageActor, b: UsageActor) => {
		// The name breaks every tie, so the order is total: a table that reorders
		// itself between renders is a table a reader cannot cite. `actors.ts`
		// states the same rule for the same reason.
		if (sort === 'name') return a.country_org.localeCompare(b.country_org);
		const left = sort === 'occurrences' ? a.occurrences : a.assigned;
		const right = sort === 'occurrences' ? b.occurrences : b.assigned;
		return right - left || a.country_org.localeCompare(b.country_org);
	};
}

/** A referent that names no case: the meta ones, and the uncontrolled `other`. */
const notACase = (referent: UsageReferent) =>
	referent.kind === 'meta' || referent.kind === 'reserved';

/**
 * The column order: by weight, with everything that is not a case moved last.
 *
 * **A case the run never used keeps its column.** The list was drawn up first
 * and the model then declined to use it, so an empty column is a finding about
 * these delegations rather than a gap, and the disclosure line counts it.
 * Dropping it would make the figure's own vocabulary depend on its results.
 *
 * **An abstention code is not a referent and gets no column.** `unclear` and
 * `not_applicable` are how the codebook lets a coder decline; an occurrence
 * carrying either is by definition not *assigned*, so those columns cannot ever
 * fill. Kept, they would be two permanently empty columns that the sentence
 * above would then describe wrongly — as cases nobody invoked. The third
 * reserved value, `other`, does carry occurrences and does keep a column: it is
 * a real referent that has not been given an identifier yet.
 *
 * **A retired referent keeps its column only while it has counts.** The list is
 * versioned so that a run made before a category was withdrawn stays readable,
 * and on such a run the column is full and belongs here. On a run made after the
 * withdrawal it is empty, and the sentence above would describe it wrongly: it
 * is not a case these delegations declined to invoke, it is a category the
 * instrument was never offered.
 */
export function orderReferents(referents: readonly UsageReferent[]): UsageReferent[] {
	const ranked = [...referents]
		.filter((referent) => referent.occurrences > 0 || referent.kind !== 'reserved')
		.filter((referent) => referent.occurrences > 0 || !referent.retired)
		.sort((a, b) => b.occurrences - a.occurrences || a.label.localeCompare(b.label));
	return [...ranked.filter((r) => !notACase(r)), ...ranked.filter(notACase)];
}

/**
 * Which speaker said the word about which genocide, and how much of that is a
 * number the interface may print.
 */
export function matrixPlan(data: Usage, state: UsageState): MatrixPlan {
	const { unit, sort } = state;
	const cells = index(data.matrix);

	const placed = data.actors.filter((actor) => actor.assigned > 0);
	const ordered = [...placed].sort(compareActors(sort));
	const shown = ordered.slice(0, ROW_CAP);
	const hidden = ordered.slice(ROW_CAP);

	const columns: MatrixColumn[] = orderReferents(data.referents).map((referent) => ({
		referent,
		grouped: notACase(referent),
		drawn: 0,
		selected: referent.id === state.referent
	}));

	const rows: MatrixRow[] = shown.map((actor) => {
		const own = cells.get(actor.country_org);
		return {
			actor,
			selected: actor.country_org === state.actor,
			cells: columns.map((column) => {
				const found = own?.get(column.referent.id);
				const count = found?.count ?? 0;
				const contested = found?.contested ?? 0;
				// Withheld on the artefact's own flag rather than on a comparison
				// recomputed here: 15 derived the threshold and applied it, and a
				// second implementation could only ever drift from the first.
				const share = actor.sufficient && actor.assigned > 0 ? count / actor.assigned : null;
				const cellState: CellState =
					count === 0 ? 'empty' : unit === 'share' && share === null ? 'withheld-share' : 'drawn';
				column.drawn += count;
				return {
					actor: actor.country_org,
					referent: column.referent.id,
					count,
					share,
					contested,
					contestedShare: count > 0 ? contested / count : null,
					positions: found?.positions ?? emptyPositions(),
					weight: 0,
					tone: 0,
					state: cellState,
					selected: actor.country_org === state.actor && column.referent.id === state.referent
				};
			})
		};
	});

	// The ramp runs from zero to the largest cell that may actually be drawn, so
	// a hatched cell can never set the top of a scale it is not on.
	const value = (cell: MatrixCell) => (unit === 'share' ? (cell.share ?? 0) : cell.count);
	let high = 0;
	for (const row of rows) {
		for (const cell of row.cells) {
			if (cell.state === 'drawn') high = Math.max(high, value(cell));
		}
	}
	for (const row of rows) {
		for (const cell of row.cells) {
			if (cell.state !== 'drawn' || high <= 0) continue;
			cell.weight = value(cell) / high;
			cell.tone = tone(cell.weight);
		}
	}

	const disclosure: MatrixDisclosure = {
		speakers: placed.length,
		hiddenRows: hidden.length,
		hiddenOccurrences: hidden.reduce((total, actor) => total + actor.assigned, 0),
		hiddenSufficient: hidden.filter((actor) => actor.sufficient).length,
		silent: data.actors.length - placed.length,
		withheldRows: shown.filter((actor) => !actor.sufficient).length,
		unassigned: data.actors.reduce((total, actor) => total + (actor.eligible - actor.assigned), 0),
		ineligible: data.actors.reduce(
			(total, actor) => total + (actor.occurrences - actor.eligible),
			0
		),
		emptyColumns: columns.filter((column) => column.drawn === 0).length,
		drawn: columns.reduce((total, column) => total + column.drawn, 0)
	};

	return {
		rows,
		columns,
		groupedFrom: columns.findIndex((column) => column.grouped),
		unit,
		sort,
		high,
		minimum: data.minimum_occurrences,
		cap: ROW_CAP,
		disclosure,
		refusal: rows.length ? null : 'no-assignments'
	};
}

/* -------------------------------------------------------------------------- *
 * Keyboard navigation across the matrix
 *
 * `Heatmap.svelte` refused a tab stop per cell on the grounds that a keyboard
 * reader given 384 of them has to pass through a year to leave, and left the
 * table under the figure as the navigable thing. Here the table *is* the
 * figure, so the same objection is answered the other way: every cell is a real
 * button, exactly one of them is in the tab order at a time, and the arrow keys
 * move between them. The whole matrix is one tab stop.
 *
 * The coordinate space includes the headings, because they are controls too: a
 * row heading selects a speaker on its own and a column heading selects a
 * referent on its own. Row -1 is the heading row, column -1 the heading column,
 * and (-1, -1) is the empty corner, which is not focusable — a move that would
 * land there does not move at all.
 * -------------------------------------------------------------------------- */

export interface Focus {
	row: number;
	column: number;
}

/** The keys the matrix intercepts. Everything else belongs to the browser. */
export const NAVIGATION_KEYS = new Set([
	'ArrowUp',
	'ArrowDown',
	'ArrowLeft',
	'ArrowRight',
	'Home',
	'End'
]);

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);

/** Where a key press moves the focus, given what the plan actually drew. */
export function stepFocus(plan: MatrixPlan, at: Focus, pressed: string): Focus {
	const lastRow = plan.rows.length - 1;
	const lastColumn = plan.columns.length - 1;
	const moved = { ...at };
	if (pressed === 'ArrowUp') moved.row -= 1;
	else if (pressed === 'ArrowDown') moved.row += 1;
	else if (pressed === 'ArrowLeft') moved.column -= 1;
	else if (pressed === 'ArrowRight') moved.column += 1;
	else if (pressed === 'Home') moved.column = -1;
	else if (pressed === 'End') moved.column = lastColumn;
	else return at;

	moved.row = clamp(moved.row, -1, lastRow);
	moved.column = clamp(moved.column, -1, lastColumn);
	// The corner carries nothing, so it is never focused. Refusing the move is
	// the predictable behaviour: the reader stays where they can see themselves.
	if (moved.row < 0 && moved.column < 0) return at;
	return moved;
}

/* -------------------------------------------------------------------------- *
 * The speaker_position profile
 * -------------------------------------------------------------------------- */

export interface PositionSegment {
	speaker_position: Position;
	count: number;
	share: number;
	/** Cumulative bounds as percentages, so a bar is one gradient and not five. */
	from: number;
	to: number;
}

export interface PositionProfile {
	actor: string;
	eligible: number;
	/** The seven positions summed: the bar's own denominator. */
	total: number;
	positions: PositionCounts;
	segments: PositionSegment[];
	shareRejects: number;
	/** The count behind the share, which is a fact at every denominator. */
	rejects: number;
	/** The 95% Wilson bounds, and how they are written. */
	low: number | null;
	high: number | null;
	intervalText: string;
	/** Whether the lower bound clears the corpus's own 1.7%. */
	separated: boolean;
}

export interface PositionRankingResult {
	/** Speakers whose share may be published, most rejecting first. */
	rows: PositionProfile[];
	/**
	 * Speakers under the minimum, unranked and counts only.
	 *
	 * Never sorted into the ranking and never given a share: naming near-misses
	 * beside a ranked table invites reading them as ranked, which is the same
	 * objection `actors.ts` makes about its own `under` list.
	 */
	withheld: { actor: string; eligible: number; positions: PositionCounts; total: number }[];
	minimum: number;
}

function segmentsOf(positions: PositionCounts, total: number): PositionSegment[] {
	const segments: PositionSegment[] = [];
	let cursor = 0;
	for (const speaker_position of POSITIONS) {
		const count = positions[speaker_position] ?? 0;
		if (count <= 0) continue;
		const share = total > 0 ? count / total : 0;
		const from = cursor * 100;
		cursor += share;
		segments.push({ speaker_position, count, share, from, to: cursor * 100 });
	}
	return segments;
}

/**
 * Who rejects the word — separated from the corpus first, and then not ranked.
 *
 * **The order is not the share.** The review of 1 September 2026 (§4.5, item 11)
 * found the old ordering to be a ranking of noise at its foot: the corpus rate
 * is 1.7%, so at the minimum of twenty occurrences a single rejection reads as
 * 5%, and a table sorted on that puts one draw above another draw from the same
 * urn. What can be ordered is the rows whose 95% interval clears the corpus
 * rate — Sudan's 19 in 43, Serbia's 15 in 45 — and those come first, ordered
 * among themselves by share. Everything else follows by count, with its
 * interval printed, and is not a ranking of anything.
 *
 * A speaker under the minimum is not sorted to the bottom; it is not sorted. A
 * null read through `?? 0` would put every rarely-heard delegation at the foot
 * of a ranking of rejection, which is a claim about them that nothing measured.
 */
export function positionRanking(data: Usage): PositionRankingResult {
	const rows: PositionProfile[] = [];
	const withheld: PositionRankingResult['withheld'] = [];

	for (const row of data.position_by_actor) {
		const positions = { ...emptyPositions(), ...row.positions };
		const total = sumPositions(positions);
		if (row.sufficient && row.share_rejects !== null && Number.isFinite(row.share_rejects)) {
			rows.push({
				actor: row.actor,
				eligible: row.eligible,
				total,
				positions,
				segments: segmentsOf(positions, total),
				shareRejects: row.share_rejects,
				rejects: positions.rejects ?? 0,
				low: row.share_low,
				high: row.share_high,
				intervalText:
					row.share_low === null || row.share_high === null
						? '—'
						: `${percent(row.share_low)}\u2013${percent(row.share_high)}`,
				separated: Boolean(row.separated)
			});
		} else {
			withheld.push({ actor: row.actor, eligible: row.eligible, positions, total });
		}
	}

	rows.sort(
		(a, b) =>
			Number(b.separated) - Number(a.separated) ||
			(a.separated ? b.shareRejects - a.shareRejects : b.rejects - a.rejects) ||
			a.actor.localeCompare(b.actor)
	);
	withheld.sort((a, b) => b.eligible - a.eligible || a.actor.localeCompare(b.actor));
	return { rows, withheld, minimum: data.minimum_occurrences };
}

/* -------------------------------------------------------------------------- *
 * Where two readings part
 *
 * A comparison run is a second model given the byte-identical prompt and the
 * same occurrences. A *contested* occurrence is one the two instruments read
 * differently: not an error found, but a passage worth a reader's attention.
 *
 * The governing sentence, which every surface that prints one of these numbers
 * carries: agreement between two models measures stability across instruments,
 * never accuracy — both can be wrong about a passage in the same way — and the
 * human gold sample remains the only calibration.
 * -------------------------------------------------------------------------- */

/** One field the two runs read differently, with both readings written out. */
export interface ContestedField {
	field: string;
	/** As the agreement tables name a field: `termLabel`, lower case. */
	label: string;
	/** What the published run read, in the vocabulary the page uses elsewhere. */
	published: string;
	/** What the second model read, in the same vocabulary. */
	second: string;
}

/**
 * How one compared field's value is written on screen.
 *
 * Not `termLabel` for all five: a speaker_position has a name the rest of the page already
 * uses, a referent has one only the artefact's own list carries, and `function`
 * is several labels pipe-joined. Written in one place so that a disagreement
 * reads in the same words as the label it disagrees with.
 */
function readingOf(field: string, value: string, referents: ReadonlyMap<string, string>): string {
	if (!value) return '—';
	if (field === 'speaker_position') return positionLabel(value);
	if (field === 'referent') return referents.get(value) ?? termLabel(value);
	if (field === 'function') {
		return value.split('|').filter(Boolean).map(termLabel).join(', ') || '—';
	}
	return termLabel(value);
}

/** The published run's five compared labels, keyed the way `contested` names them. */
const publishedLabels = (occurrence: UsageOccurrence): Record<string, string> => ({
	verdict: occurrence.verdict,
	quotation: occurrence.quotation,
	speaker_position: occurrence.speaker_position,
	function: occurrence.function ?? '',
	referent: occurrence.referent
});

/** The second reading's, or nothing at all where there is no second reading. */
const secondLabels = (alt: UsageAlternative | null): Record<string, string> =>
	alt
		? {
				verdict: alt.verdict,
				quotation: alt.quotation,
				speaker_position: alt.speaker_position,
				function: alt.function ?? '',
				referent: alt.referent
			}
		: {};

/** A name for a referent identifier, from the artefact's own controlled list. */
const referentNames = (referents: readonly UsageReferent[] = []): ReadonlyMap<string, string> =>
	new Map(referents.map((referent) => [referent.id, referent.label]));

/**
 * The fields one occurrence is contested on, both readings included.
 *
 * Ordered by `COMPARED_FIELDS` rather than by the artefact's array, so that two
 * occurrences contested on the same pair of fields list them in the same order —
 * the same reason `POSITIONS` is fixed rather than derived. A field the row names
 * and the second reading is silent on is dropped: the boundary refuses that
 * payload, and a row printing "speaker_position: asserts → —" would be an alternative
 * nobody proposed.
 */
function contestedFields(
	occurrence: UsageOccurrence,
	referents: ReadonlyMap<string, string>
): ContestedField[] {
	const named = new Set(occurrence.contested ?? []);
	if (!named.size) return [];
	const mine = publishedLabels(occurrence);
	const theirs = secondLabels(occurrence.alt);
	return COMPARED_FIELDS.filter((field) => named.has(field) && field in theirs).map((field) => ({
		field,
		label: termLabel(field),
		published: readingOf(field, mine[field] ?? '', referents),
		second: readingOf(field, theirs[field] ?? '', referents)
	}));
}

/* -------------------------------------------------------------------------- *
 * The quotations behind a cell
 * -------------------------------------------------------------------------- */

/** Query string for a route, without the leading `?`. The route is the caller's. */
export interface EvidenceLink {
	query: string;
}

export interface ReaderLink extends EvidenceLink {
	/** The meeting file the speech lives in — `/reader/[meeting]`'s parameter. */
	meeting: string;
}

export interface EvidenceRow {
	/** The KWIC line identifier, which is this project's locator for a use. */
	id: string;
	/** The annotation's own key, stable across runs of the model. */
	occurrenceId: string;
	date: string;
	spv: string;
	country: string;
	agenda: string;
	sentence: string;
	keyword: string;
	speaker_position: string;
	positionLabel: string;
	/** How the run answered `concrete_case`, or the empty string on a run without it. */
	caseLabel: string;
	/** The rhetorical functions, split out of the pipe-joined field. */
	functions: string[];
	confidence: string;
	referent: string;
	/**
	 * Annotation schema 3's fields, in reading order, and only the ones this run
	 * actually answered.
	 *
	 * A run coded against schema 2 answered none of them and gets an empty list,
	 * which is what the view is meant to show: not a row of blanks that reads as
	 * "no accused actor", but no row at all. `lib.llm.resolve_row` translates what
	 * schema 2 measured and refuses to guess what it did not.
	 */
	schemaFields: { label: string; value: string }[];
	evidenceQuote: string;
	evidenceValid: boolean;
	/** True when the model's span says something the sentence on screen does not. */
	quoteDiffers: boolean;
	/**
	 * The fields a second opinion read differently, with both readings.
	 *
	 * Empty in every build with no comparison run, which is the ordinary state —
	 * and empty, too, wherever the two runs agreed or the second never reached
	 * this occurrence. The row marks itself on this being non-empty and on
	 * nothing else.
	 */
	contested: ContestedField[];
	reader: ReaderLink;
	concordance: EvidenceLink;
}

/**
 * The schema-3 fields this occurrence actually carries, in reading order.
 *
 * Empty on a run coded against schema 2, which answered none of them: the six
 * were added on 2 September 2026 and a v1 run has no image of any of them. An
 * empty string is therefore "not asked" and never "nothing to report", and a
 * caller that rendered it as a value would publish six blanks as findings.
 */
export function schemaThreeFields(occurrence: UsageOccurrence): { label: string; value: string }[] {
	const declared: [string, string | undefined][] = [
		['Referent read from', occurrence.referent_source],
		['Accused', occurrence.accused_actor],
		['Victim group', occurrence.victim_group],
		['Speaker’s own State accused', occurrence.own_state_accused],
		['Salience', occurrence.salience],
		['Rationale', occurrence.rationale]
	];
	return declared
		.filter(([, value]) => Boolean(value && value.trim()))
		.map(([label, value]) => ({ label, value: termLabel(String(value)) }));
}

/**
 * What the drill-down needs beyond a speaker and a referent.
 *
 * An options object rather than two more positional arguments: the two are
 * about the second opinion and neither is a narrowing of the corpus, and a
 * caller passing `drillDown(rows, lines, '', '', true, referents)` would be
 * unreadable at the call site.
 */
export interface DrillOptions {
	/**
	 * Whether this build has a second opinion at all. Off unless it is said so.
	 *
	 * A marking on a row claims that another model read that passage differently,
	 * and on a build whose summary says no comparison run was made there is
	 * nothing behind the claim. The two artefacts are written by one script and do
	 * agree; the interface declines to depend on it, and defaults to claiming
	 * nothing rather than to claiming whatever the rows happen to carry.
	 */
	compared?: boolean;
	/** Keep only the occurrences two models read differently. */
	contestedOnly?: boolean;
	/** The controlled list, so a contested referent is named rather than identified. */
	referents?: readonly UsageReferent[];
}

const flatten = (value: string) => value.replace(/\s+/g, ' ').trim().toLowerCase();

/**
 * The way back into the record from a line identifier alone.
 *
 * Shared by the drill-down and the diffusion chronology because it is one
 * decision — which term the reader arrives on, and which occurrence is
 * highlighted — and two copies of it would be two answers to "what does this
 * link open".
 */
const readerLink = (lineId: string): ReaderLink => ({
	meeting: meetingOf(lineId),
	query: readerQuery({ ...CONCORDANCE_DEFAULTS, term: USAGE_TERM }, lineId)
});

/**
 * The way back into the concordance, which cannot name one line.
 *
 * The link lands on the delegation and the record the line came from — the
 * smallest set the concordance can express that certainly contains it. Both
 * halves are read off the concordance line rather than off the annotation, so
 * nothing here re-derives who said what or in which meeting.
 */
const concordanceLink = (line: KwicLine): EvidenceLink => ({
	query: new URLSearchParams({
		term: USAGE_TERM,
		country: line.country,
		spv: line.spv
	}).toString()
});

/**
 * The annotated occurrences behind one selection, joined to what can be quoted.
 *
 * The join is on the KWIC line identifier and it is the only one this artefact
 * offers: `occurrences.json` carries the labels and the model's evidence span,
 * and every displayable fact — the sentence, the date, the delegation, the
 * record symbol — comes from `kwic/genocide.json`. An annotation whose line is
 * not in the concordance file is dropped rather than shown with blanks: the
 * view's whole promise is that a label can be read back to a sentence.
 *
 * The speaker is the concordance line's, not a field of its own. Nothing here
 * re-derives who said what.
 *
 * **The contested filter is applied here and nowhere else.** One enumeration of
 * a selection's occurrences, narrowed by one more predicate: a second list built
 * beside this one would be a second answer to "which quotations are behind this
 * cell", and the two would drift the first time either was touched.
 */
export function drillDown(
	occurrences: readonly UsageOccurrence[],
	lines: readonly KwicLine[],
	actor = '',
	referent = '',
	options: DrillOptions = {}
): EvidenceRow[] {
	if (!actor && !referent) return [];
	const byId = new Map(lines.map((line) => [line.id, line]));
	const names = referentNames(options.referents);
	const rows: EvidenceRow[] = [];

	for (const occurrence of occurrences) {
		if (referent && occurrence.referent !== referent) continue;
		const line = byId.get(occurrence.id);
		if (!line) continue;
		if (actor && line.country !== actor) continue;
		const contested = options.compared ? contestedFields(occurrence, names) : [];
		if (options.contestedOnly && !contested.length) continue;

		const quote = occurrence.evidence_quote ?? '';
		rows.push({
			id: line.id,
			occurrenceId: occurrence.occurrence_id,
			date: line.date,
			spv: line.spv,
			country: line.country,
			agenda: line.agenda,
			sentence: line.sent,
			keyword: line.kw,
			speaker_position: occurrence.speaker_position,
			positionLabel: positionLabel(occurrence.speaker_position),
			caseLabel: occurrence.concrete_case ? caseLabel(occurrence.concrete_case) : '',
			// Pipe-joined without spaces, per the codebook. An empty field is no
			// functions rather than one called "".
			functions: (occurrence.function ?? '').split('|').filter(Boolean),
			confidence: occurrence.confidence,
			referent: occurrence.referent,
			schemaFields: schemaThreeFields(occurrence),
			evidenceQuote: quote,
			evidenceValid: occurrence.evidence_valid,
			quoteDiffers: Boolean(quote.trim()) && flatten(quote) !== flatten(line.sent),
			contested,
			reader: readerLink(line.id),
			concordance: concordanceLink(line)
		});
	}

	// Date first, identifier last, for the same reason every concordance sort
	// ends there: ties are the normal case, and a list that reorders itself
	// between renders is a list a reader cannot cite.
	return rows.sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
}

/* -------------------------------------------------------------------------- *
 * How a referent spread through the Council
 *
 * One referent at a time, and three curves over it: the delegations that have
 * placed the word on it at all, the ones that have asserted it, and the ones
 * that have refused the word for it. Each event is a *first* — the first time
 * that delegation did that thing about that genocide — so a curve only ever
 * rises, and its height is a count of delegations rather than of occurrences.
 *
 * Everything the drawing needs is computed here, coordinates included. The
 * component is a renderer: it holds the tokens and the shapes, and no arithmetic
 * that could disagree with the table underneath it.
 * -------------------------------------------------------------------------- */

/** The three firsts, in the order that settles a tie between them. */
export const MILESTONES: readonly UsageMilestone[] = ['mention', 'asserts', 'rejects'];

/**
 * Back to front, which is not the rank.
 *
 * Assertion is the reading the figure is for, so it is drawn last and sits on
 * top; refusal is the counter-curve and is drawn under it; the faint envelope of
 * every delegation that placed the word at all goes down first.
 */
const DRAW_ORDER: readonly UsageMilestone[] = ['mention', 'rejects', 'asserts'];

const MILESTONE_LABELS: Record<UsageMilestone, string> = {
	mention: 'Placed the word on it',
	asserts: 'Asserted it',
	rejects: 'Refused the word for it'
};

/** What a milestone is called on screen. An unknown value degrades to readable words. */
export const milestoneLabel = (milestone: string): string =>
	MILESTONE_LABELS[milestone as UsageMilestone] ?? termLabel(milestone);

/**
 * Where a milestone sits when a date and an identifier cannot separate two
 * events — which is the normal case, because one occurrence can be both a first
 * mention and a first assertion. An unlisted milestone sorts last rather than
 * first, so a fourth one added upstream cannot silently displace these three.
 */
export const milestoneRank = (milestone: string): number => {
	const rank = MILESTONES.indexOf(milestone as UsageMilestone);
	return rank < 0 ? MILESTONES.length : rank;
};

const WIDTH = 720;
const HEIGHT = 180;
/** Room a stroke and an event marker need at the edges of the box. */
const PAD = 5;

/**
 * The drawing's own coordinate space, and the only place its size is written.
 *
 * A viewBox rather than pixels: the component scales it to whatever width the
 * figure gets, uniformly, so nothing in it is stretched. The four edges are
 * given rather than derived, because a component that worked out where its own
 * baseline goes would be a second answer to a question this module has already
 * answered — and the one that drifts is always the one further from the data.
 */
export const DIFFUSION_BOX = {
	width: WIDTH,
	height: HEIGHT,
	left: PAD,
	right: WIDTH - PAD,
	top: PAD,
	bottom: HEIGHT - PAD
} as const;

const PLOT = { width: WIDTH - 2 * PAD, height: HEIGHT - 2 * PAD };

/** Box units a step needs to itself before a mark on it reads as one mark. */
const MARKER_ROOM = 8;

export interface DiffusionPoint {
	/** `YYYY-MM-DD`. */
	date: string;
	actor: string;
	speaker_position: string;
	positionLabel: string;
	/** The KWIC line identifier, which is this project's locator for a use. */
	id: string;
	/** Delegations that had crossed this milestone once this one had. Never falls. */
	value: number;
	x: number;
	y: number;
}

export interface DiffusionSeries {
	milestone: UsageMilestone;
	label: string;
	points: DiffusionPoint[];
	/** Delegations that ever crossed it: the height the curve ends at. */
	total: number;
	/** The step through those points, in `DIFFUSION_BOX` coordinates. */
	path: string;
	/**
	 * The radius of the mark on each step, or zero for no marks at all.
	 *
	 * A dozen delegations are a dozen events and each one is worth pointing at;
	 * a hundred and forty-six are a curve, and marks four units wide five units
	 * apart stop being marks and become a bead chain along a line that already
	 * shows the same thing. The threshold is the room a mark needs to read as
	 * one, so the figure draws them exactly while they can be told apart.
	 */
	marker: number;
	/**
	 * Whether the figure draws this curve.
	 *
	 * A milestone nothing crossed is not drawn: a flat line along the floor reads
	 * as a measured nothing rather than as an absence, and the totals beside the
	 * figure say it in words instead. `mention` has a second condition — it is
	 * dropped when it is the same curve as `asserts`, delegation for delegation
	 * and date for date, because two lines drawn on top of each other are one
	 * line with a legend that promises two readings.
	 */
	drawn: boolean;
}

/** A year on the time axis, positioned rather than spaced. */
export interface DiffusionTick {
	label: string;
	/** In `DIFFUSION_BOX` coordinates, for a rule inside the drawing. */
	x: number;
	/** The same position as a percentage, for a label in the markup around it. */
	percent: number;
	/**
	 * Which end of the label sits at that position.
	 *
	 * A centred label at 1% hangs off the left of the figure and one at 99% off
	 * the right, where it would push a scrollbar onto the figure body. The two
	 * outermost ticks are therefore anchored by their own edge instead.
	 */
	anchor: 'start' | 'middle' | 'end';
}

/** One entry of the referent picker. Only referents the block carries events for. */
export interface DiffusionOption {
	id: string;
	label: string;
	/** From `data.referents`: `case`, `historical`, `meta` or `reserved`. */
	kind: string;
	events: number;
	/** Distinct delegations with any event at all. */
	delegations: number;
}

/**
 * Why there is no curve: the run recorded no first for any referent at all, or
 * the referent the reader selected has none. Two different sentences, so the
 * figure can say which rather than going blank in one voice.
 */
export type DiffusionRefusal = 'no-diffusion' | 'no-events' | 'unstable-referent';

export interface DiffusionPlan {
	/** The referent in force, which is the selected one or the documented default. */
	referent: string;
	label: string;
	options: DiffusionOption[];
	/** All three milestones, drawn or not, so the totals can be stated in full. */
	series: DiffusionSeries[];
	/** The ones with a curve, back to front. */
	drawn: DiffusionSeries[];
	/**
	 * Delegations that ever crossed each milestone, drawn or not.
	 *
	 * Kept beside the series because a milestone the figure declines to draw is
	 * still a number the figure has to be able to state: "nobody refused the word
	 * for this one" is a finding, and it is one only prose can carry.
	 */
	totals: Record<UsageMilestone, number>;
	ticks: DiffusionTick[];
	/** The first and last dated event in the whole block, not in this referent's. */
	span: { from: string; to: string };
	/** The top of the vertical scale: the tallest drawn curve's final height. */
	high: number;
	/**
	 * How far this referent survives a second instrument, or null.
	 *
	 * Null where no comparison run was made, and where the published run placed
	 * the referent too rarely for the figure to be measured. Read with
	 * `refusal === 'unstable-referent'`, which is what it governs.
	 */
	reliability?: number | null;
	/** Events behind the drawn curves — the chronology's own length. */
	events: number;
	refusal: DiffusionRefusal | null;
}

/** A date as a number. `NaN` for anything unparseable, which is then not spanned. */
const stamp = (date: string): number => Date.parse(date);

const byDateThenId = (a: UsageDiffusionEvent, b: UsageDiffusionEvent) =>
	a.date.localeCompare(b.date) ||
	a.id.localeCompare(b.id) ||
	milestoneRank(a.milestone) - milestoneRank(b.milestone);

/**
 * The time axis, taken from every referent in the block rather than from the one
 * on screen.
 *
 * Switching referents then moves the curve along a fixed axis instead of
 * rescaling it: 1994 is in the same place in both pictures, which is the whole
 * point of being able to switch. A referent whose events span two years would
 * otherwise be drawn as wide as one that spans thirty.
 */
function spanOf(referents: readonly (readonly UsageDiffusionEvent[])[]) {
	let from = Number.POSITIVE_INFINITY;
	let to = Number.NEGATIVE_INFINITY;
	let fromDate = '';
	let toDate = '';
	for (const events of referents) {
		for (const event of events) {
			const at = stamp(event.date);
			if (!Number.isFinite(at)) continue;
			if (at < from) [from, fromDate] = [at, event.date];
			if (at > to) [to, toDate] = [at, event.date];
		}
	}
	return { from, to, fromDate, toDate };
}

/** Year steps that read as round numbers, smallest first. */
const TICK_STEPS = [1, 2, 5, 10, 20, 25, 50];
const MAX_TICKS = 7;

function ticksFor(from: number, to: number, x: (at: number) => number): DiffusionTick[] {
	if (!Number.isFinite(from) || !Number.isFinite(to)) return [];
	const first = new Date(from).getUTCFullYear();
	const last = new Date(to).getUTCFullYear();
	const widest = TICK_STEPS[TICK_STEPS.length - 1];
	const step = TICK_STEPS.find((size) => (last - first) / size <= MAX_TICKS) ?? widest;
	const ticks: DiffusionTick[] = [];
	for (let year = Math.ceil(first / step) * step; year <= last; year += step) {
		const at = stamp(`${year}-01-01`);
		// A January that falls before the first event or after the last is a rule
		// drawn outside the plot: the axis is the data's span, not the decade's.
		if (at < from || at > to) continue;
		const position = x(at);
		const percent = ((position - DIFFUSION_BOX.left) / PLOT.width) * 100;
		ticks.push({
			label: String(year),
			x: position,
			percent,
			anchor: percent < 6 ? 'start' : percent > 94 ? 'end' : 'middle'
		});
	}
	return ticks;
}

/** Two curves are the same curve when they step at the same moment for the same speaker. */
const sameCurve = (
	a: readonly { event: UsageDiffusionEvent }[],
	b: readonly { event: UsageDiffusionEvent }[]
) =>
	a.length === b.length &&
	a.every(
		({ event }, index) => event.actor === b[index].event.actor && event.date === b[index].event.date
	);

const noTotals = (): Record<UsageMilestone, number> =>
	Object.fromEntries(MILESTONES.map((milestone) => [milestone, 0])) as Record<
		UsageMilestone,
		number
	>;

const blank = (refusal: DiffusionRefusal, referent = '', label = ''): DiffusionPlan => ({
	referent,
	label,
	options: [],
	series: [],
	drawn: [],
	totals: noTotals(),
	ticks: [],
	span: { from: '', to: '' },
	high: 0,
	events: 0,
	refusal
});

/**
 * When each delegation first said it, first asserted it, first refused it.
 *
 * The selection is the page's one referent state, shared with the matrix: a
 * column heading and this figure's picker set the same value, so the two figures
 * are always showing the same genocide. With nothing selected the figure falls
 * back to the first *case* the block carries — a named genocide rather than the
 * Convention or the legal definition, which have a chronology but not one anyone
 * would call a diffusion.
 */
export function diffusionPlan(data: Usage, state: UsageState): DiffusionPlan {
	const known = new Map(data.referents.map((referent) => [referent.id, referent]));
	const nameOf = (id: string) => known.get(id)?.label ?? termLabel(id);

	// A referent the block carries and has no event for is the same nothing as a
	// referent it does not carry: it would be an option that refuses when picked.
	const carried = data.diffusion.referents.filter((entry) => entry.events.length > 0);
	if (!carried.length) return blank('no-diffusion');
	const reliability = referentReliability(data);

	const options: DiffusionOption[] = carried.map((entry) => ({
		id: entry.id,
		label: nameOf(entry.id),
		kind: known.get(entry.id)?.kind ?? '',
		events: entry.events.length,
		delegations: new Set(entry.events.map((event) => event.actor)).size
	}));

	const fallback = options.find((option) => option.kind === 'case') ?? options[0];
	const wanted = state.referent || fallback.id;
	const chosen = carried.find((entry) => entry.id === wanted);
	if (!chosen) {
		// A referent selected in the matrix that the chronology has nothing for.
		// Its option is appended anyway, so the picker still shows what is in force
		// rather than jumping to a referent nobody asked for.
		return {
			...blank('no-events', wanted, nameOf(wanted)),
			options: [
				...options,
				{
					id: wanted,
					label: nameOf(wanted),
					kind: known.get(wanted)?.kind ?? '',
					events: 0,
					delegations: 0
				}
			]
		};
	}

	const { from, to, fromDate, toDate } = spanOf(carried.map((entry) => entry.events));
	const width = to - from;
	// A block holding one dated event has no span to scale against; the step is
	// drawn down the middle rather than divided by zero.
	const x = (at: number) =>
		Number.isFinite(at) && width > 0
			? DIFFUSION_BOX.left + ((at - from) / width) * PLOT.width
			: DIFFUSION_BOX.left + PLOT.width / 2;

	// A chronology is a claim about dates, and a date here is the first
	// occurrence a label fell on. Where two instruments place a referent on the
	// same occurrences fewer than four times in five, the first of them is a
	// property of which model was asked; the curve is withheld and the reason is
	// the one the reader needs, not a blank figure.
	const reliable = reliability.get(chosen.id);
	if (
		data.comparison.state === 'computed' &&
		(reliable === null || reliable === undefined
			? reliability.has(chosen.id)
			: reliable < DIFFUSION_RELIABILITY)
	) {
		return {
			...blank('unstable-referent', chosen.id, nameOf(chosen.id)),
			options,
			reliability: reliable ?? null
		};
	}

	const ordered = [...chosen.events].sort(byDateThenId);
	const counted = MILESTONES.map((milestone) => {
		const seen = new Set<string>();
		const points = ordered
			.filter((event) => event.milestone === milestone)
			.map((event) => {
				// Distinct delegations rather than events. The artefact writes one
				// event per delegation and milestone, so the two agree — but a curve
				// that would climb twice for one delegation if it ever stopped
				// agreeing is a curve that says something the caption does not.
				seen.add(event.actor);
				return { event, value: seen.size };
			});
		return { milestone, points };
	});

	const assertions = counted.find((entry) => entry.milestone === 'asserts')?.points ?? [];
	const drawnMilestones = new Set(
		counted
			.filter(({ milestone, points }) => {
				if (!points.length) return false;
				if (milestone !== 'mention') return true;
				return !sameCurve(points, assertions);
			})
			.map((entry) => entry.milestone)
	);

	const high = Math.max(
		0,
		...counted
			.filter((entry) => drawnMilestones.has(entry.milestone))
			.map((entry) => entry.points.at(-1)?.value ?? 0)
	);
	const y = (value: number) =>
		DIFFUSION_BOX.top + (1 - (high > 0 ? value / high : 0)) * PLOT.height;

	const series: DiffusionSeries[] = counted.map(({ milestone, points }) => {
		const placed: DiffusionPoint[] = points.map(({ event, value }) => ({
			date: event.date,
			actor: event.actor,
			speaker_position: event.speaker_position,
			positionLabel: positionLabel(event.speaker_position),
			id: event.id,
			value,
			x: x(stamp(event.date)),
			y: y(value)
		}));
		const spacing = placed.length ? PLOT.width / placed.length : 0;
		return {
			milestone,
			label: milestoneLabel(milestone),
			points: placed,
			total: placed.at(-1)?.value ?? 0,
			path: stepPath(placed, y(0)),
			marker: spacing >= MARKER_ROOM ? (milestone === 'mention' ? 1.8 : 2.4) : 0,
			drawn: drawnMilestones.has(milestone)
		};
	});

	const drawn = DRAW_ORDER.flatMap((milestone) =>
		series.filter((entry) => entry.milestone === milestone && entry.drawn)
	);

	return {
		referent: chosen.id,
		label: nameOf(chosen.id),
		options,
		series,
		drawn,
		totals: Object.fromEntries(series.map((entry) => [entry.milestone, entry.total])) as Record<
			UsageMilestone,
			number
		>,
		ticks: ticksFor(from, to, x),
		span: { from: fromDate, to: toDate },
		high,
		events: drawn.reduce((total, entry) => total + entry.points.length, 0),
		// A referent with events and no curve is possible: a run that declared a
		// fourth milestone would put every event of it on a series this figure has
		// no reading for. It refuses in the same words rather than drawing an empty
		// pair of axes under a key with nothing in it.
		refusal: drawn.length ? null : 'no-events'
	};
}

/**
 * A cumulative count drawn as what it is: a floor, a jump at each event, and a
 * flat run to the right-hand edge.
 *
 * Steps rather than a straight line between events, because the quantity does
 * not pass through the values in between. Nothing joined 1997 through 2003 in
 * the gap between two delegations, and a sloped segment would draw exactly that.
 */
function stepPath(points: readonly DiffusionPoint[], floor: number): string {
	if (!points.length) return '';
	const round = (value: number) => value.toFixed(1);
	const parts = [`M ${round(DIFFUSION_BOX.left)},${round(floor)}`];
	for (const point of points) parts.push(`H ${round(point.x)}`, `V ${round(point.y)}`);
	parts.push(`H ${round(DIFFUSION_BOX.right)}`);
	return parts.join(' ');
}

/**
 * The chronology the curve summarises: one row per event, oldest first.
 *
 * **Two links, and only one of them is free.** `/reader` is addressed by the
 * line identifier alone, which every event carries, so that link is always
 * there. The concordance cannot be addressed without the record symbol, and the
 * symbol lives in `kwic/genocide.json` — a file this page fetches only when a
 * reader opens something. So the concordance link is null until the concordance
 * is loaded, rather than the whole table waiting on several megabytes nobody
 * asked for.
 *
 * **The rows are the drawn curves' own events.** A milestone the figure declines
 * to draw is one whose events are already in the table under another name — that
 * is the condition for dropping it — so listing them again would be the same
 * occurrence twice. The CSV beside the figure carries every event of every
 * referent regardless.
 */
export interface DiffusionRow {
	/** The KWIC line identifier. */
	id: string;
	date: string;
	actor: string;
	milestone: UsageMilestone;
	milestoneLabel: string;
	speaker_position: string;
	positionLabel: string;
	/** Which delegation this was to cross that milestone. 1 is the first. */
	ordinal: number;
	reader: ReaderLink;
	/** The record symbol, empty until the concordance for the term is loaded. */
	spv: string;
	/** Null for the same reason. Never a link built from the identifier alone. */
	concordance: EvidenceLink | null;
}

export function diffusionChronology(
	plan: DiffusionPlan,
	lines: readonly KwicLine[] = []
): DiffusionRow[] {
	const byId = new Map(lines.map((line) => [line.id, line]));
	const rows: DiffusionRow[] = plan.drawn.flatMap((series) =>
		series.points.map((point) => {
			const line = byId.get(point.id);
			return {
				id: point.id,
				date: point.date,
				actor: point.actor,
				milestone: series.milestone,
				milestoneLabel: series.label,
				speaker_position: point.speaker_position,
				positionLabel: point.positionLabel,
				ordinal: point.value,
				reader: readerLink(point.id),
				spv: line?.spv ?? '',
				concordance: line ? concordanceLink(line) : null
			};
		})
	);

	// The artefact's own order, rebuilt after the flattening: date first,
	// identifier next, and the milestone last, because one occurrence can be two
	// events and nothing else separates them.
	return rows.sort(
		(a, b) =>
			a.date.localeCompare(b.date) ||
			a.id.localeCompare(b.id) ||
			milestoneRank(a.milestone) - milestoneRank(b.milestone)
	);
}

/* -------------------------------------------------------------------------- *
 * The second opinion, as the apparatus states it
 * -------------------------------------------------------------------------- */

/** One row of the agreement table between the two runs, ready to be printed. */
export interface ComparisonFieldRow {
	field: string;
	label: string;
	/** Occurrences both runs reached. The same for every row of one comparison. */
	n: number;
	observed: number | null;
	/** The share as the page writes shares, or an em dash where it was not computed. */
	observedText: string;
	kappa: number | null;
	kappaText: string;
	/** True where kappa was suppressed rather than undefined. Different findings. */
	kappaWithheld: boolean;
	minorityShareText: string;
	pabak: number | null;
	pabakText: string;
	contested: number;
}

/**
 * Everything the standing apparatus prints about a second opinion.
 *
 * `computed` is the only condition any surface tests. Under `none` the block is
 * the artefact's own empty state — empty strings, zero counts, no rows — and
 * nothing at all is drawn from it: no section, no figure, no filter. That is the
 * ordinary case, and it is the one the live payload is in.
 */
export interface ComparisonApparatus {
	computed: boolean;
	state: UsageComparison['state'];
	/** The published run's model, named beside the other so the pair reads as a pair. */
	published: string;
	model: string;
	runId: string;
	runDate: string;
	reasoningEffort: string;
	/** Whether both runs were made from the same prompt, byte for byte. */
	samePrompt: boolean;
	annotated: number;
	/** The published run's own total: what `annotated` is a share of. */
	total: number;
	/** `annotated / total`, or null with nothing to divide by. Never `?? 0`. */
	coverage: number | null;
	/** Occurrences carrying a label from both runs. Every statistic is over these. */
	overlap: number;
	evidenceInvalid: number;
	abstained: number;
	abstention: UsageComparison['abstention'];
	fields: ComparisonFieldRow[];
	/** Per referent, how far the two instruments place the same occurrences there. */
	referents: UsageClassRow[];
	functionJaccard: number | null;
	functionJaccardText: string;
	/** Chance-corrected, where the mean overlap is not. Read this one. */
	functionAlphaText: string;
	/** Which `function` label the two readings part on. */
	functionLabels: {
		label: string;
		left: number;
		right: number;
		observedText: string;
		kappaText: string;
	}[];
	functionContested: number;
	contestedAny: number;
	/** `contested_any / overlap`, or null where nothing was compared. */
	contestedShare: number | null;
}

/** A statistic that could not be computed is an em dash, never a zero. */
const orDash = (value: number | null, write: (value: number) => string) =>
	value === null || !Number.isFinite(value) ? '—' : write(value);

/**
 * One field's agreement row, written once for the two tables that print it.
 *
 * The cross-model comparison and the retest carry the same statistics computed
 * by the same code upstream, and are meant to be read against each other; two
 * copies of this mapping would let the two tables come to disagree about how a
 * withheld kappa is written.
 */
const fieldRow = (row: UsageComparisonField): ComparisonFieldRow => ({
	field: row.field,
	label: termLabel(row.field),
	n: row.n,
	observed: row.observed,
	observedText: orDash(row.observed, percent),
	kappa: row.kappa,
	kappaText: orDash(row.kappa, decimal),
	kappaWithheld: Boolean(row.kappa_withheld),
	minorityShareText: orDash(row.minority_share, percent),
	pabak: row.pabak,
	pabakText: orDash(row.pabak, decimal),
	contested: row.contested
});

/**
 * What the apparatus says about the second opinion, in one call.
 *
 * Every number here is over the *overlap* — the occurrences both runs reached —
 * except the three that describe the comparison run itself, which are over all
 * of its rows. Both are stated, because a run that annotated half the corpus and
 * agreed on all of it is not the finding a run that annotated all of it and
 * agreed on half is.
 */
export function comparisonApparatus(data: Usage): ComparisonApparatus {
	const block = data.comparison;
	const total = data.model.occurrences_annotated;
	const abstention = block.abstention;
	return {
		computed: block.state === 'computed',
		state: block.state,
		published: data.model.id,
		model: block.model,
		runId: block.run_id,
		runDate: block.run_date,
		reasoningEffort: block.reasoning_effort,
		// Stated rather than assumed. 15 refuses a comparison made from other
		// instructions, and this is the page being able to say that it held.
		samePrompt: Boolean(block.prompt_sha256) && block.prompt_sha256 === data.model.prompt_sha256,
		annotated: block.occurrences_annotated,
		total,
		coverage: total > 0 ? block.occurrences_annotated / total : null,
		overlap: block.overlap,
		evidenceInvalid: block.evidence_invalid,
		abstained:
			abstention.verdict_uncertain + abstention.referent_unclear + abstention.position_unclear,
		abstention,
		fields: block.fields.map(fieldRow),
		referents: block.referents ?? [],
		functionJaccard: block.function_jaccard,
		functionJaccardText: orDash(block.function_jaccard, decimal),
		functionAlphaText: orDash(block.function_alpha_masi, decimal),
		functionLabels: (block.function_labels ?? []).map((row) => ({
			label: termLabel(row.label),
			left: row.left,
			right: row.right,
			observedText: orDash(row.observed, percent),
			kappaText: orDash(row.kappa, decimal)
		})),
		functionContested: block.function_contested,
		contestedAny: block.contested_any,
		contestedShare: block.overlap > 0 ? block.contested_any / block.overlap : null
	};
}

/* -------------------------------------------------------------------------- *
 * The noise floor, and what it makes the cross-model table mean
 * -------------------------------------------------------------------------- */

/**
 * Fields whose label is a property of the instrument as much as of the passage.
 *
 * The review of 1 September 2026 (§4.6) names two by hand and the run's own
 * numbers say why. `reports_without_position` has a cross-instrument F1 of 0.37:
 * 445 occurrences are `attributes` to one model and `asserts` to the other, the
 * largest single disagreement in the corpus, and the prompt gives no rule for
 * the boundary. `attributed_or_reported`, the quotation label the same
 * ambiguity drives, is Luna-only on 539 rows. A count of either is a count of
 * how one model read a boundary the codebook has not drawn, and every surface
 * that prints one says so.
 */
export const INSTRUMENT_DEPENDENT: ReadonlySet<string> = new Set([
	'reports_without_position',
	'attributed_or_reported'
]);

/** Whether a label's count is a property of the instrument as much as the corpus. */
export const isInstrumentDependent = (label: string): boolean => INSTRUMENT_DEPENDENT.has(label);

/**
 * Below this cross-instrument F1, a referent's diffusion chronology is withheld.
 *
 * A curve of first assertions and first refusals is a claim about *dates*, and a
 * date is the first occurrence a label fell on. Where two instruments place a
 * referent on the same occurrences three times in five — `drc_great_lakes` at
 * 0.61, `hypothetical_future` at 0.40 — the first of them is a property of which
 * model was asked, and the curve is a chronology of one model's habits.
 */
export const DIFFUSION_RELIABILITY = 0.8;

/** One row of the retest table: a model against another call of itself. */
export interface RetestRow {
	which: string;
	model: string;
	retestRunId: string;
	overlap: number;
	/** All five fields identical, as a share of the overlap. */
	identical: number;
	identicalShare: number | null;
	fields: ComparisonFieldRow[];
	functionJaccardText: string;
}

/**
 * Each model against another run of itself, ready to print beside the other table.
 *
 * The statistics are the ones the cross-model table carries, computed upstream
 * by the same code, so a reader can lay one over the other. What the comparison
 * says is the point: Luna writes all five fields identically on 69 of the 91
 * pilot occurrences, so about a quarter of its own labels move between two calls
 * of one instrument, and a cross-model disagreement of a fifth has to be read
 * against that and not against zero.
 */
export function retestRows(data: Usage): RetestRow[] {
	return (data.retest ?? []).map((entry) => ({
		which: entry.which,
		model: entry.model,
		retestRunId: entry.retest_run_id,
		overlap: entry.overlap,
		identical: entry.identical,
		identicalShare: entry.overlap > 0 ? entry.identical / entry.overlap : null,
		fields: entry.fields.map(fieldRow),
		functionJaccardText: orDash(entry.function_jaccard, decimal)
	}));
}

/**
 * How reliably each referent survives a second instrument, keyed by referent id.
 *
 * Null where the published run placed the referent fewer than twenty times: the
 * F1 was withheld upstream for the same reason every rate below that support is,
 * and a consumer must not read the absence as a low score. `diffusionPlan`
 * withholds on both — an unreliable referent and an unmeasurable one are both
 * referents whose chronology cannot be read as one.
 */
export function referentReliability(data: Usage): ReadonlyMap<string, number | null> {
	const out = new Map<string, number | null>();
	for (const row of data.comparison.referents ?? []) out.set(row.label, row.f1);
	return out;
}

/* -------------------------------------------------------------------------- *
 * The contested passages
 * -------------------------------------------------------------------------- */

/**
 * How many contested occurrences the reading list draws.
 *
 * A reading list is a list somebody reads: fifty passages is already an
 * afternoon, and the tail of a corpus-wide comparison is thousands. The cap is a
 * display decision like the matrix's, so it is disclosed in the same way — what
 * it left out is counted, and the CSV beside the figure carries every one.
 */
export const CONTESTED_CAP = 50;

export interface ContestedRow {
	/** The KWIC line identifier, which is this project's locator for a use. */
	id: string;
	occurrenceId: string;
	date: string;
	spv: string;
	/** The concordance line's speaker. Nothing here re-derives who said what. */
	actor: string;
	sentence: string;
	keyword: string;
	referent: string;
	referentLabel: string;
	/** The fields the two runs read differently, both readings written out. */
	contested: ContestedField[];
	/** How many they are: the count the list is ordered by. */
	fields: number;
	reader: ReaderLink;
	concordance: EvidenceLink;
}

/** What the reading list has to say out loud about everything it is not showing. */
export interface ContestedListing {
	rows: ContestedRow[];
	cap: number;
	/** Contested occurrences the run recorded, before the join and before the cap. */
	contested: number;
	/** Those a sentence could be found for: the list's own denominator. */
	quotable: number;
	/** Quotable rows the cap left out. They are in the CSV. */
	hidden: number;
	/** Contested occurrences whose line is not in the concordance file for the term. */
	unquotable: number;
	/** Compared occurrences, so the disclosure can state the one as a share of the other. */
	overlap: number;
	/** Why there is no list: no second opinion at all, or one that found no difference. */
	refusal: 'no-comparison' | 'no-contest' | null;
}

/**
 * Every occurrence the two runs read differently, most contested first.
 *
 * **Ordered by how much they disagree.** An occurrence the two models split on
 * three of five fields is a harder passage than one they split on the verdict
 * alone, and the reader with an afternoon should meet it first. Date and then
 * identifier settle every tie, so the order is total and the list is citable.
 *
 * **Joined to a sentence, or dropped and counted.** The same rule `drillDown`
 * follows: a reading list whose rows cannot be read back to the record is a list
 * of labels. What the join lost is reported rather than absorbed.
 *
 * **The published labels stay published.** Nothing here replaces a speaker_position or a
 * referent with the second model's; both readings are carried side by side, and
 * the matrix, the speaker_position profile and the diffusion curve are drawn from the
 * published run alone.
 */
export function contestedList(
	data: Usage,
	occurrences: readonly UsageOccurrence[],
	lines: readonly KwicLine[] = []
): ContestedListing {
	const blank: ContestedListing = {
		rows: [],
		cap: CONTESTED_CAP,
		contested: 0,
		quotable: 0,
		hidden: 0,
		unquotable: 0,
		overlap: data.comparison.overlap,
		refusal: 'no-comparison'
	};
	if (data.comparison.state !== 'computed') return blank;

	const names = referentNames(data.referents);
	const byId = new Map(lines.map((line) => [line.id, line]));
	const rows: ContestedRow[] = [];
	let contested = 0;
	let unquotable = 0;

	for (const occurrence of occurrences) {
		const fields = contestedFields(occurrence, names);
		if (!fields.length) continue;
		contested += 1;
		const line = byId.get(occurrence.id);
		if (!line) {
			unquotable += 1;
			continue;
		}
		rows.push({
			id: line.id,
			occurrenceId: occurrence.occurrence_id,
			date: line.date,
			spv: line.spv,
			actor: line.country,
			sentence: line.sent,
			keyword: line.kw,
			referent: occurrence.referent,
			referentLabel: names.get(occurrence.referent) ?? termLabel(occurrence.referent),
			contested: fields,
			fields: fields.length,
			reader: readerLink(line.id),
			concordance: concordanceLink(line)
		});
	}

	rows.sort(
		(a, b) => b.fields - a.fields || a.date.localeCompare(b.date) || a.id.localeCompare(b.id)
	);

	return {
		rows: rows.slice(0, CONTESTED_CAP),
		cap: CONTESTED_CAP,
		contested,
		quotable: rows.length,
		hidden: Math.max(0, rows.length - CONTESTED_CAP),
		unquotable,
		overlap: data.comparison.overlap,
		refusal: contested ? null : 'no-contest'
	};
}

/* -------------------------------------------------------------------------- *
 * The gold sample, and the exports
 * -------------------------------------------------------------------------- */

export interface GoldProgress {
	state: UsageGold['state'];
	sampleSize: number;
	uniqueOccurrences: number;
	/**
	 * Occurrences carrying at least one human verdict.
	 *
	 * The furthest-along coder's row count, never the sum of them: both coders
	 * code every sampled occurrence, so adding their totals would report 400
	 * coded rows out of a 200-row sample the first time the pair finished.
	 */
	coded: number;
	coders: number;
	doubleCoded: number;
	adjudicated: number;
	hasAgreement: boolean;
	hasModelScores: boolean;
	/** Whether the comparison run has been scored against the same human labels. */
	hasComparisonScores: boolean;
}

export function goldProgress(data: Usage): GoldProgress {
	const gold = data.gold;
	return {
		state: gold.state,
		sampleSize: gold.sample_size,
		uniqueOccurrences: gold.unique_occurrences,
		coded: gold.coders.reduce((most, coder) => Math.max(most, coder.rows), 0),
		coders: gold.coders.length,
		doubleCoded: gold.double_coded,
		adjudicated: gold.adjudicated,
		hasAgreement: gold.human_agreement.length > 0,
		hasModelScores: gold.model_vs_human.length > 0,
		hasComparisonScores: gold.model_vs_human_comparison.length > 0
	};
}

/**
 * The matrix as a file, in long form and at full width.
 *
 * One row per filled cell of the whole artefact, not per cell of the drawing:
 * the row cap and the ordering are display decisions the reader did not make,
 * and `export.ts` exists so that a download is never "whatever happened to be
 * visible". The speaker's three denominators travel with every row so that a
 * share can be recomputed — and so that its withholding is visible as a column
 * rather than as an absence.
 */
export const MATRIX_COLUMNS = [
	'country_org',
	'iso3',
	'group',
	'entity_type',
	'referent',
	'referent_label',
	'referent_kind',
	'count',
	'share_of_assigned',
	'occurrences',
	'eligible',
	'assigned',
	'sufficient',
	...POSITIONS.map((speaker_position) => `position_${speaker_position}`)
];

export function matrixExportRows(data: Usage): (string | number | boolean | null)[][] {
	const actors = new Map(data.actors.map((actor) => [actor.country_org, actor]));
	const referents = new Map(data.referents.map((referent) => [referent.id, referent]));
	return data.matrix.map((cell) => {
		const actor = actors.get(cell.actor);
		const referent = referents.get(cell.referent);
		const assigned = actor?.assigned ?? 0;
		return [
			cell.actor,
			actor?.iso3 ?? null,
			actor?.group ?? null,
			actor?.entity_type ?? null,
			cell.referent,
			referent?.label ?? null,
			referent?.kind ?? null,
			cell.count,
			// Null rather than a number wherever the interface withholds it, so
			// the file carries the gate instead of having been filtered by it.
			actor?.sufficient && assigned > 0 ? cell.count / assigned : null,
			actor?.occurrences ?? null,
			actor?.eligible ?? null,
			assigned,
			actor?.sufficient ?? null,
			...POSITIONS.map((speaker_position) => cell.positions[speaker_position] ?? 0)
		];
	});
}

/**
 * Every first, for every referent, in one long table.
 *
 * Not the referent on screen and not the curves that were drawn: the picker is a
 * display decision the reader did not make, and a milestone folded into another
 * for being identical to it is still an event the run recorded. The same rule
 * `matrixExportRows` follows — a download is never whatever happened to be
 * visible.
 */
export const DIFFUSION_COLUMNS = [
	'referent',
	'referent_label',
	'referent_kind',
	'date',
	'actor',
	'milestone',
	'speaker_position',
	'id'
];

export function diffusionExportRows(data: Usage): (string | number | boolean | null)[][] {
	const referents = new Map(data.referents.map((referent) => [referent.id, referent]));
	return data.diffusion.referents.flatMap((entry) => {
		const referent = referents.get(entry.id);
		return [...entry.events]
			.sort(byDateThenId)
			.map((event) => [
				entry.id,
				referent?.label ?? null,
				referent?.kind ?? null,
				event.date,
				event.actor,
				event.milestone,
				event.speaker_position,
				event.id
			]);
	});
}

/**
 * Every contested occurrence, both readings side by side, in one long table.
 *
 * Not the fifty the figure draws and not only the ones a sentence was found for:
 * the cap is a display decision the reader did not make, and an occurrence the
 * concordance file has no line for is still one the two runs read differently.
 * Those rows travel with a null date, speaker and record symbol rather than
 * being filtered out — the same null-honesty `matrixExportRows` gives a withheld
 * share, so the file carries the gap instead of having been cut by it.
 *
 * The labels are the artefact's own values, not the page's wording: a file is
 * read by a script, and `rejects` is what joins back to the run.
 */
export const CONTESTED_COLUMNS = [
	'id',
	'occurrence_id',
	'date',
	'actor',
	'spv',
	'referent_label',
	'contested_count',
	'contested_fields',
	...COMPARED_FIELDS.map((field) => `published_${field}`),
	...COMPARED_FIELDS.map((field) => `comparison_${field}`)
];

export function contestedExportRows(
	data: Usage,
	occurrences: readonly UsageOccurrence[],
	lines: readonly KwicLine[] = []
): (string | number | boolean | null)[][] {
	const names = referentNames(data.referents);
	const byId = new Map(lines.map((line) => [line.id, line]));
	const rows = occurrences
		.filter((occurrence) => (occurrence.contested ?? []).length > 0)
		.map((occurrence) => {
			const line = byId.get(occurrence.id);
			const mine = publishedLabels(occurrence);
			const theirs = secondLabels(occurrence.alt);
			// Ordered by `COMPARED_FIELDS` rather than by the row's own array, so
			// that two rows contested on the same fields read the same way.
			const named = new Set(occurrence.contested ?? []);
			const fields = COMPARED_FIELDS.filter((field) => named.has(field));
			return {
				date: line?.date ?? '',
				id: occurrence.id,
				row: [
					occurrence.id,
					occurrence.occurrence_id,
					line?.date ?? null,
					line?.country ?? null,
					line?.spv ?? null,
					names.get(occurrence.referent) ?? null,
					fields.length,
					// Pipe-joined without spaces, the artefact's own idiom for a field
					// carrying several values.
					fields.join('|'),
					...COMPARED_FIELDS.map((field) => mine[field] ?? null),
					...COMPARED_FIELDS.map((field) => theirs[field] ?? null)
				] as (string | number | boolean | null)[]
			};
		});
	// Chronological, and the identifier settles every tie: a file is a record to
	// cite from rather than the figure's ranking written down. A row with no line
	// has no date and sorts first, where its emptiness is visible.
	rows.sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
	return rows.map((entry) => entry.row);
}

export const POSITION_COLUMNS = [
	'country_org',
	'iso3',
	'group',
	'eligible',
	'sufficient',
	'share_rejects',
	...POSITIONS.map((speaker_position) => `position_${speaker_position}`)
];

/** Every speaker's speaker_position profile, including the ones whose share is withheld. */
export function positionExportRows(data: Usage): (string | number | boolean | null)[][] {
	const actors = new Map(data.actors.map((actor) => [actor.country_org, actor]));
	return data.position_by_actor.map((row) => {
		const actor = actors.get(row.actor);
		return [
			row.actor,
			actor?.iso3 ?? null,
			actor?.group ?? null,
			row.eligible,
			row.sufficient,
			row.share_rejects,
			...POSITIONS.map((speaker_position) => row.positions[speaker_position] ?? 0)
		];
	});
}
