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
 * a concrete referent. The matrix counts assigned, the stance profile counts
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
 * **A diffusion curve counts delegations, not states.** The last figure here
 * plots when each delegation first placed the word on a referent, first asserted
 * it and first refused it, cumulated over the corpus. It is a curve of *speech
 * in this record*: a delegation that never spoke cannot appear on it, and a flat
 * stretch is as often an empty Council calendar as a silence about the case. The
 * arithmetic below therefore ends at counting firsts and drawing them; the
 * sentence that says what the shape is not belongs to the figure's caveat.
 */

import { CONCORDANCE_DEFAULTS, readerQuery } from './concordance';
import { meetingOf } from './data';
import { termLabel } from './format';
import { tone } from './theme';
import type {
	KwicLine,
	Stance,
	StanceCounts,
	Usage,
	UsageActor,
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
 * `genocide` alone: 6,092 occurrences across 3,273 speeches was the run that
 * was made, and a link out of this view has to name the term it is showing
 * rather than inherit whatever the concordance last had.
 */
export const USAGE_TERM = 'genocide';

/**
 * The seven stances, in the codebook's own order.
 *
 * Fixed rather than read off a payload, because it is the order the stacked bar
 * draws in: two delegations are comparable only if the same band is in the same
 * place in both, and an order derived from each row's own counts would move it.
 */
export const STANCES: readonly Stance[] = [
	'asserts',
	'attributes_or_reports',
	'rejects_or_denies',
	'hypothetical_or_conditional',
	'neutral_legal_reference',
	'unclear',
	'not_applicable'
];

const STANCE_LABELS: Record<Stance, string> = {
	asserts: 'Asserts',
	attributes_or_reports: 'Attributes or reports',
	rejects_or_denies: 'Rejects or denies',
	hypothetical_or_conditional: 'Hypothetical or conditional',
	neutral_legal_reference: 'Neutral legal reference',
	unclear: 'Unclear',
	not_applicable: 'Not applicable'
};

/** What a stance is called on screen. An unknown value degrades to readable words. */
export const stanceLabel = (stance: string): string =>
	STANCE_LABELS[stance as Stance] ?? termLabel(stance);

/** Every stance at zero. An absent key and a measured zero must not be confused. */
export const emptyStances = (): StanceCounts =>
	Object.fromEntries(STANCES.map((stance) => [stance, 0])) as StanceCounts;

const sumStances = (stances: StanceCounts): number =>
	STANCES.reduce((total, stance) => total + (stances[stance] ?? 0), 0);

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
}

export const USAGE_DEFAULTS: UsageState = {
	referent: '',
	actor: '',
	// Counts first, and on purpose: they are facts about the record and are
	// published for every speaker, where a share is withheld under the minimum.
	unit: 'count',
	sort: 'assigned'
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
		sort: askedSort && SORTS.has(askedSort) ? askedSort : USAGE_DEFAULTS.sort
	};
}

/** Serialize only what differs from the documented defaults. */
export function usageParams(state: UsageState): URLSearchParams {
	const params = new URLSearchParams();
	if (state.actor !== USAGE_DEFAULTS.actor) params.set('actor', state.actor);
	if (state.referent !== USAGE_DEFAULTS.referent) params.set('referent', state.referent);
	if (state.unit !== USAGE_DEFAULTS.unit) params.set('unit', state.unit);
	if (state.sort !== USAGE_DEFAULTS.sort) params.set('sort', state.sort);
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
	stances: StanceCounts;
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
 */
export function orderReferents(referents: readonly UsageReferent[]): UsageReferent[] {
	const ranked = [...referents]
		.filter((referent) => referent.occurrences > 0 || referent.kind !== 'reserved')
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
					stances: found?.stances ?? emptyStances(),
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
 * The stance profile
 * -------------------------------------------------------------------------- */

export interface StanceSegment {
	stance: Stance;
	count: number;
	share: number;
	/** Cumulative bounds as percentages, so a bar is one gradient and not five. */
	from: number;
	to: number;
}

export interface StanceProfile {
	actor: string;
	eligible: number;
	/** The seven stances summed: the bar's own denominator. */
	total: number;
	stances: StanceCounts;
	segments: StanceSegment[];
	shareRejects: number;
}

export interface StanceRankingResult {
	/** Speakers whose share may be published, most rejecting first. */
	rows: StanceProfile[];
	/**
	 * Speakers under the minimum, unranked and counts only.
	 *
	 * Never sorted into the ranking and never given a share: naming near-misses
	 * beside a ranked table invites reading them as ranked, which is the same
	 * objection `actors.ts` makes about its own `under` list.
	 */
	withheld: { actor: string; eligible: number; stances: StanceCounts; total: number }[];
	minimum: number;
}

function segmentsOf(stances: StanceCounts, total: number): StanceSegment[] {
	const segments: StanceSegment[] = [];
	let cursor = 0;
	for (const stance of STANCES) {
		const count = stances[stance] ?? 0;
		if (count <= 0) continue;
		const share = total > 0 ? count / total : 0;
		const from = cursor * 100;
		cursor += share;
		segments.push({ stance, count, share, from, to: cursor * 100 });
	}
	return segments;
}

/**
 * Who rejects the word, ranked — and who is not ranked at all.
 *
 * The ordering is the artefact's `share_rejects`, which is null wherever the
 * speaker is under the minimum. Those rows are not sorted to the bottom; they
 * are not sorted. A null read through `?? 0` would put every rarely-heard
 * delegation at the foot of a ranking of rejection, which is a claim about them
 * that nothing measured.
 */
export function stanceRanking(data: Usage): StanceRankingResult {
	const rows: StanceProfile[] = [];
	const withheld: StanceRankingResult['withheld'] = [];

	for (const row of data.stance_by_actor) {
		const stances = { ...emptyStances(), ...row.stances };
		const total = sumStances(stances);
		if (row.sufficient && row.share_rejects !== null && Number.isFinite(row.share_rejects)) {
			rows.push({
				actor: row.actor,
				eligible: row.eligible,
				total,
				stances,
				segments: segmentsOf(stances, total),
				shareRejects: row.share_rejects
			});
		} else {
			withheld.push({ actor: row.actor, eligible: row.eligible, stances, total });
		}
	}

	rows.sort((a, b) => b.shareRejects - a.shareRejects || a.actor.localeCompare(b.actor));
	withheld.sort((a, b) => b.eligible - a.eligible || a.actor.localeCompare(b.actor));
	return { rows, withheld, minimum: data.minimum_occurrences };
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
	stance: string;
	stanceLabel: string;
	/** The rhetorical functions, split out of the pipe-joined field. */
	functions: string[];
	confidence: string;
	referent: string;
	evidenceQuote: string;
	evidenceValid: boolean;
	/** True when the model's span says something the sentence on screen does not. */
	quoteDiffers: boolean;
	reader: ReaderLink;
	concordance: EvidenceLink;
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
 */
export function drillDown(
	occurrences: readonly UsageOccurrence[],
	lines: readonly KwicLine[],
	actor = '',
	referent = ''
): EvidenceRow[] {
	if (!actor && !referent) return [];
	const byId = new Map(lines.map((line) => [line.id, line]));
	const rows: EvidenceRow[] = [];

	for (const occurrence of occurrences) {
		if (referent && occurrence.referent !== referent) continue;
		const line = byId.get(occurrence.id);
		if (!line) continue;
		if (actor && line.country !== actor) continue;

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
			stance: occurrence.stance,
			stanceLabel: stanceLabel(occurrence.stance),
			// Pipe-joined without spaces, per the codebook. An empty field is no
			// functions rather than one called "".
			functions: (occurrence.function ?? '').split('|').filter(Boolean),
			confidence: occurrence.confidence,
			referent: occurrence.referent,
			evidenceQuote: quote,
			evidenceValid: occurrence.evidence_valid,
			quoteDiffers: Boolean(quote.trim()) && flatten(quote) !== flatten(line.sent),
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
export const MILESTONES: readonly UsageMilestone[] = ['mention', 'asserts', 'rejects_or_denies'];

/**
 * Back to front, which is not the rank.
 *
 * Assertion is the reading the figure is for, so it is drawn last and sits on
 * top; refusal is the counter-curve and is drawn under it; the faint envelope of
 * every delegation that placed the word at all goes down first.
 */
const DRAW_ORDER: readonly UsageMilestone[] = ['mention', 'rejects_or_denies', 'asserts'];

const MILESTONE_LABELS: Record<UsageMilestone, string> = {
	mention: 'Placed the word on it',
	asserts: 'Asserted it',
	rejects_or_denies: 'Refused the word for it'
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
	stance: string;
	stanceLabel: string;
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
export type DiffusionRefusal = 'no-diffusion' | 'no-events';

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
			stance: event.stance,
			stanceLabel: stanceLabel(event.stance),
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
	stance: string;
	stanceLabel: string;
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
				stance: point.stance,
				stanceLabel: point.stanceLabel,
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
		hasModelScores: gold.model_vs_human.length > 0
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
	...STANCES.map((stance) => `stance_${stance}`)
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
			...STANCES.map((stance) => cell.stances[stance] ?? 0)
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
	'stance',
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
				event.stance,
				event.id
			]);
	});
}

export const STANCE_COLUMNS = [
	'country_org',
	'iso3',
	'group',
	'eligible',
	'sufficient',
	'share_rejects',
	...STANCES.map((stance) => `stance_${stance}`)
];

/** Every speaker's stance profile, including the ones whose share is withheld. */
export function stanceExportRows(data: Usage): (string | number | boolean | null)[][] {
	const actors = new Map(data.actors.map((actor) => [actor.country_org, actor]));
	return data.stance_by_actor.map((row) => {
		const actor = actors.get(row.actor);
		return [
			row.actor,
			actor?.iso3 ?? null,
			actor?.group ?? null,
			row.eligible,
			row.sufficient,
			row.share_rejects,
			...STANCES.map((stance) => row.stances[stance] ?? 0)
		];
	});
}
