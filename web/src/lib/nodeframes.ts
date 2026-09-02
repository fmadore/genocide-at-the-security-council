/**
 * The frame profile: what the word is doing, and how that differs in a slice.
 *
 * The figure is a dot plot with two marks per row. An open dot is the frame's
 * share of all 6,092 occurrences of the node; a filled dot with a Wilson whisker
 * is its share in whichever slice the reader has chosen — an eight-year block, a
 * speaker group. The reading is the distance between them, and the whisker says
 * whether that distance is worth reading at all.
 *
 * Two dots and an interval rather than seventeen lines over thirty-two years:
 * a composition of eighteen categories drawn as a time series is eighteen
 * overlapping lines, and the only question a reader can answer from it is which
 * one is on top. The annual series is in the artefact and in the download for
 * anyone who wants it.
 *
 * Every share and every bound is computed by `lib/series.py::wilson_interval`
 * in the pipeline and shipped. Nothing here recomputes one: what lives here is
 * the arithmetic of the drawing — which rows, in what order, at what scale,
 * and where a mark sits on the track.
 */
import type { FrameEntry, FrameShare, FrameSlice, NodeFrames } from './types';

/** The residue's name in the artefact. It is a row like any other, and drawn. */
export const UNFRAMED = 'unframed';

export interface FrameRow {
	frame: string;
	/** The gloss from the codebook, or the residue's own sentence. */
	gloss: string;
	/** Share over every occurrence of the node. Never withheld: n is 6,092. */
	overall: number;
	overallOccurrences: number;
	/** Share within the chosen slice, and its Wilson bounds. Null when withheld. */
	share: number | null;
	low: number | null;
	high: number | null;
	occurrences: number;
	/** Slice minus overall, in points. Null wherever the share is. */
	shift: number | null;
}

/** What the residue's row says where a codebook gloss would be. */
export const RESIDUE_GLOSS =
	'No pattern in the codebook reached this occurrence. Its share is not constant over ' +
	'time, so a frame that gained share may have gained it from here.';

const glossOf = (codebook: FrameEntry[], frame: string): string =>
	codebook.find((entry) => entry.frame === frame)?.gloss ?? RESIDUE_GLOSS;

/**
 * The facets the artefact offers, in the order the control lists them.
 *
 * Read off the payload rather than hard-coded, so a facet added upstream appears
 * without an edit here; the labels are this file's, because `speaker_group` is
 * a column name and not a thing to print.
 */
export const FACET_LABELS: Record<string, string> = {
	period: 'Period',
	speaker_group: 'Speaker group'
};

export const facets = (data: NodeFrames): string[] => Object.keys(data.slices);

export const facetLabel = (facet: string): string => FACET_LABELS[facet] ?? facet;

/** The members of one facet, largest first, as the artefact ordered them. */
export const members = (data: NodeFrames, facet: string): FrameSlice[] => data.slices[facet] ?? [];

/** One member by name, or the largest when the name is not in the facet. */
export function member(data: NodeFrames, facet: string, name: string): FrameSlice | null {
	const rows = members(data, facet);
	return rows.find((row) => row.member === name) ?? rows[0] ?? null;
}

/**
 * The rows of the figure, ranked by overall share, largest first.
 *
 * Ranked by the *corpus* share and not by the slice's, so the rows do not
 * reshuffle when the reader moves the control: the figure is a comparison, and
 * a comparison whose baseline reorders under it is a different figure each time.
 * `unframed` is ranked with the rest rather than pinned to the bottom — it is
 * the second-largest category, and moving it out of the ranking would be the
 * hiding this artefact refuses.
 */
export function profile(data: NodeFrames, slice: FrameSlice | null): FrameRow[] {
	const total = data.occurrences;
	const inSlice = new Map((slice?.frames ?? []).map((row) => [row.frame, row]));
	return data.totals.frames
		.map((row: FrameShare): FrameRow => {
			const here = inSlice.get(row.frame);
			const overall = total > 0 ? row.occurrences / total : 0;
			const share = here?.share ?? null;
			return {
				frame: row.frame,
				gloss: glossOf(data.codebook, row.frame),
				overall,
				overallOccurrences: row.occurrences,
				share,
				low: here?.share_low ?? null,
				high: here?.share_high ?? null,
				occurrences: here?.occurrences ?? 0,
				shift: share === null ? null : share - overall
			};
		})
		.sort((a, b) => b.overall - a.overall || a.frame.localeCompare(b.frame));
}

export interface Track {
	/** Always zero: a share has a floor, and hiding it would exaggerate every gap. */
	low: number;
	high: number;
	/** Round shares inside the track, for the axis. */
	ticks: number[];
}

/**
 * The share axis: zero to a round figure above the largest mark drawn.
 *
 * Anchored at zero because these are shares of a whole, and a bar or a dot read
 * against a floating baseline overstates every difference — the objection §5.2
 * makes to the map's circles, in one dimension. The top is the next multiple of
 * five points above the widest interval on screen, so the whiskers are not
 * clipped and the scale does not jump by a pixel when the control moves.
 */
export function track(rows: FrameRow[], step = 0.05): Track {
	const marks = rows.flatMap((row) => [row.overall, row.share ?? 0, row.high ?? 0]);
	const highest = Math.max(step, ...marks);
	// Rounded off the floating-point residue: `Math.ceil(0.28 / 0.05) * 0.05` is
	// 0.30000000000000004, and that reaches the axis label and the download.
	const high = Number((Math.ceil(highest / step) * step).toFixed(4));
	const ticks: number[] = [];
	for (let tick = 0; tick <= high + 1e-9; tick += step) ticks.push(Number(tick.toFixed(4)));
	return { low: 0, high, ticks };
}

/** Where a share sits on the track: 0 at the left edge, 1 at the right. */
export function position(share: number, scale: Track): number {
	if (scale.high === scale.low) return 0;
	return Math.min(1, Math.max(0, (share - scale.low) / (scale.high - scale.low)));
}

/**
 * Whether a slice's row differs from the corpus by more than its own interval.
 *
 * The weakest defensible statement about a difference, and the only one this
 * figure is entitled to make: the corpus share falls outside the slice's Wilson
 * interval. It is not a test — seventeen frames are on screen and nothing is
 * corrected — so the component marks these rows rather than labelling them
 * significant, and the caveat says so.
 */
export function outside(row: FrameRow): boolean {
	if (row.low === null || row.high === null) return false;
	return row.overall < row.low || row.overall > row.high;
}

/** The rows a reader would want first: the largest shifts, marked, largest first. */
export function movers(rows: FrameRow[], limit = 3): FrameRow[] {
	return rows
		.filter((row) => outside(row) && row.shift !== null)
		.sort((a, b) => Math.abs(b.shift ?? 0) - Math.abs(a.shift ?? 0))
		.slice(0, limit);
}

/**
 * The morphological split, as rows a table can draw.
 *
 * The forms are folded into their categories here rather than in the pipeline,
 * which publishes both: the artefact's job is to record every surface form it
 * saw, including the one OCR spelling, and the figure's job is to say that the
 * node is four different words.
 */
export interface FormRow {
	category: string;
	occurrences: number;
	share: number;
	forms: string[];
}

export function morphology(data: NodeFrames): FormRow[] {
	const total = data.occurrences;
	return data.morphology.categories
		.map((row) => ({
			category: row.category,
			occurrences: row.occurrences,
			share: total > 0 ? row.occurrences / total : 0,
			forms: data.morphology.forms
				.filter((form) => form.category === row.category && form.occurrences > 0)
				.map((form) => form.form)
		}))
		.filter((row) => row.occurrences > 0);
}
