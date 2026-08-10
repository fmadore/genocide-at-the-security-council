/**
 * The decisions behind the per-speaker keyness view, kept out of the component.
 *
 * `docs/PLAN.md` §7 requires that the arithmetic a visual performs at render
 * time be tested, and this figure has more of it than most: what to draw, what
 * to refuse, how long a bar is, and which of two readings a reader is looking
 * at. All of it is here; the component renders what these functions return.
 *
 * **A withheld speaker is offered, and refused with its reason.** 12 withholds a
 * table for two different reasons — too few matched pairs, or coverage below
 * half a speaker's own speeches — and `pick()` carries which one back rather
 * than returning an empty list. The two are different objections: "we could not
 * compare enough of what this delegation said" and "what we compared is an
 * unrepresentative part of it". A view that showed one message for both would
 * tell a reader something untrue about the UN Secretariat, which is the case
 * that produced the second gate.
 *
 * **Self-reference is marked and never filtered.** Every delegation says its own
 * name constantly, so 148 of the 1,008 rows in the top eight of a published
 * table are a word from the speaker's own name. Hiding them would delete
 * evidence and quietly change the ranking; `bars()` marks them and leaves them
 * in place. The upstream rule is mechanical and misses demonyms outside the
 * name, so nothing here may treat an unmarked row as certified.
 *
 * **The two readings are never mixed on one scale.** The matched table and the
 * unmatched one have different controls and therefore different denominators,
 * and a bar length computed across both would invite a comparison neither
 * supports. `bars()` scales within the reading it is given, and `removed()`
 * exists so the *difference* between them can be stated as a number instead of
 * being read off two pictures.
 */

import type { Keyword, SpeakerKeyness, SpeakerKeynessRow } from './types';

/** Which control a table was computed against. */
export type Reading = 'matched' | 'unmatched';

export interface Bar {
	word: string;
	target: number;
	reference: number;
	g2: number;
	logRatio: number;
	selfReference: boolean;
	/** 0–1, the row's log ratio against the widest in the same reading. */
	weight: number;
	/**
	 * Where this word's log ratio landed across the artefact's draws, as the
	 * observed range. The range and not the percentiles, because the row prints
	 * one draw beside it and `p05` at ten draws can sit above the value it is
	 * printed next to.
	 */
	interval: { median: number; low: number; high: number } | null;
}

export interface Refusal {
	/** The artefact's own reasons, in its own vocabulary. */
	because: string[];
	pairs: number;
	held: number;
	coverage: number;
}

export interface KeynessPlan {
	speaker: SpeakerKeynessRow | null;
	rows: Bar[];
	reading: Reading;
	/** Set when the speaker exists but has no table to draw. */
	refusal: Refusal | null;
	/** Set when no such speaker is in the artefact at all. */
	missing: boolean;
}

/** Speakers with a table, most matched pairs first — the only drawable rows. */
export function published(data: SpeakerKeyness): SpeakerKeynessRow[] {
	return data.speakers.filter((row) => row.sufficient).sort((a, b) => b.pairs - a.pairs);
}

/**
 * Speakers that were paired and then withheld, weakest first.
 *
 * Returned as rows rather than as a count, unlike the actor view's 468. The
 * difference is that these were *considered*: each one has a coverage figure and
 * a named reason, and a reader who wants to know why Yemen is absent can be
 * shown the arithmetic. A speaker that never reached the minimum in speeches is
 * not here and is reported as a number, because there is nothing to show.
 */
export function withheld(data: SpeakerKeyness): SpeakerKeynessRow[] {
	return data.speakers.filter((row) => !row.sufficient).sort((a, b) => a.pairs - b.pairs);
}

/** Speakers never paired at all: below the minimum before the matching ran. */
export function neverPaired(data: SpeakerKeyness): number {
	return data.speakers_total - data.speakers_considered;
}

/**
 * The rows to draw for one speaker in one reading.
 *
 * `limit` cuts the table for the figure. It cuts the *drawing* only — the
 * download is built from the artefact, per §7.5's first constraint, so a file
 * is never a screenshot with commas in it.
 */
export function bars(speaker: SpeakerKeynessRow, reading: Reading, limit = 20): Bar[] {
	const source = reading === 'matched' ? speaker.keywords : speaker.keywords_unmatched;
	if (!source) return [];
	const intervals = new Map(
		(speaker.stability?.keyword_log_ratio ?? []).map((entry) => [entry.word, entry])
	);
	const kept = source.slice(0, limit);
	// The widest bar in this reading, never across both: the two tables have
	// different controls, so a shared scale would compare two denominators.
	const widest = Math.max(...kept.map((row) => Math.abs(row.log_ratio)), 1);
	return kept.map((row) => ({
		word: row.word,
		target: row.target,
		reference: row.reference,
		g2: row.g2,
		logRatio: row.log_ratio,
		selfReference: row.self_reference,
		weight: Math.min(Math.abs(row.log_ratio) / widest, 1),
		interval:
			reading === 'matched' && intervals.has(row.word)
				? {
						median: intervals.get(row.word)!.median,
						low: intervals.get(row.word)!.low,
						high: intervals.get(row.word)!.high
					}
				: null
	}));
}

/**
 * How far a speaker's top unmatched keywords fall once the occasion is held.
 *
 * The one number that says whether the matching did anything, and the reason
 * both readings are published. Null when either reading is missing, rather than
 * zero: "no change" and "not computed" are different claims.
 */
export function removed(speaker: SpeakerKeynessRow, top = 15): number | null {
	if (!speaker.keywords || !speaker.keywords_unmatched) return null;
	const matched = new Map(speaker.keywords.map((row) => [row.word, row.log_ratio]));
	const drops = speaker.keywords_unmatched
		.slice(0, top)
		// A word the matching drops out of the table entirely counts as zero: it no
		// longer distinguishes the speaker at all, which is the clearest case of
		// the control having done its work.
		.map((row) => row.log_ratio - (matched.get(row.word) ?? 0));
	if (!drops.length) return null;
	const sorted = [...drops].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** How many of the drawn rows are the speaker naming itself. */
export function selfReferenceShare(rows: Bar[]): { marked: number; of: number } {
	return { marked: rows.filter((row) => row.selfReference).length, of: rows.length };
}

/** Everything the figure needs for one speaker, including why it may draw nothing. */
export function pick(
	data: SpeakerKeyness,
	name: string | null,
	reading: Reading = 'matched',
	limit = 20
): KeynessPlan {
	const speaker = data.speakers.find((row) => row.country_org === name) ?? null;
	if (!speaker) {
		return { speaker: null, rows: [], reading, refusal: null, missing: name !== null };
	}
	if (!speaker.sufficient) {
		return {
			speaker,
			rows: [],
			reading,
			refusal: {
				because: speaker.withheld_because,
				pairs: speaker.pairs,
				held: speaker.held,
				coverage: speaker.coverage
			},
			missing: false
		};
	}
	return { speaker, rows: bars(speaker, reading, limit), reading, refusal: null, missing: false };
}

/**
 * The whole of a speaker's table, both readings, for the download.
 *
 * Every row the artefact holds rather than the twenty on screen, and a `reading`
 * column so the two cannot be mistaken for one table. `stability` travels with
 * the matched rows where it exists — a log ratio without the interval it moved
 * across is the figure this view is most likely to be quoted on.
 */
export function exportRows(speaker: SpeakerKeynessRow): (string | number | boolean | null)[][] {
	const intervals = new Map(
		(speaker.stability?.keyword_log_ratio ?? []).map((entry) => [entry.word, entry])
	);
	const emit = (reading: Reading, list: Keyword[] | null) =>
		(list ?? []).map((row) => {
			const interval = reading === 'matched' ? (intervals.get(row.word) ?? null) : null;
			return [
				speaker.country_org,
				reading,
				row.word,
				row.target,
				row.reference,
				row.g2,
				row.log_ratio,
				row.self_reference,
				interval?.low ?? null,
				interval?.median ?? null,
				interval?.high ?? null
			];
		});
	return [...emit('matched', speaker.keywords), ...emit('unmatched', speaker.keywords_unmatched)];
}

export const EXPORT_COLUMNS = [
	'country_org',
	'reading',
	'word',
	'target_occurrences',
	'reference_occurrences',
	'g2',
	'log_ratio',
	'self_reference',
	'log_ratio_low',
	'log_ratio_median',
	'log_ratio_high'
];
