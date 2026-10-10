/**
 * How the reader cuts a speech into plain and marked runs.
 *
 * The record is the full text with the lexicon's spans over it, and the reader
 * draws each span as a mark in its register. Which spans are drawn, how two
 * overlapping spans become one mark, which one mark is the occurrence the URL
 * names, and where the speaker line ends are decided here, so each of those
 * decisions can be tested without mounting the route.
 */

import { occurrenceOf, speechOf } from './data';
import type { Speech } from './types';

/** A run of the text: plain where `terms` is empty, marked otherwise. */
export interface Segment {
	text: string;
	/** Every term whose span covers this run. */
	terms: string[];
	/** Whether this run holds the one occurrence the URL names. */
	exact: boolean;
}

/** The occurrence the reader was sent to, and the term its ordinal counts in. */
export interface Selection {
	occurrence: string | null;
	term: string | null;
}

/**
 * The one span the URL names, if it belongs to this speech and to the term
 * on screen. An occurrence ordinal counts within one term's matches, so under
 * another term's highlighting, or all of them, it names nothing.
 */
export function exactSpan(
	speech: Speech,
	only: string | null,
	selection: Selection
): [number, number] | null {
	const { occurrence, term } = selection;
	if (!occurrence || !term || only !== term) return null;
	if (speech.id !== speechOf(occurrence)) return null;
	const ordinal = occurrenceOf(occurrence);
	return ordinal ? (speech.hits[term]?.[ordinal - 1] ?? null) : null;
}

/**
 * Split a speech into plain and highlighted runs, for one term or for all.
 *
 * Spans overlap by design — "genocide" sits inside "prevention of genocide" —
 * so overlapping ones are merged into a single run that names every term it
 * covers, rather than nesting marks or silently dropping one.
 */
export function segments(speech: Speech, only: string | null, selection: Selection): Segment[] {
	const selected = exactSpan(speech, only, selection);
	const marks = Object.entries(speech.hits)
		.filter(([term]) => !only || term === only)
		.flatMap(([term, spans]) =>
			spans.map(([s, e]) => ({
				s,
				e,
				term,
				exact: selected?.[0] === s && selected[1] === e
			}))
		)
		.sort((a, b) => a.s - b.s || b.e - a.e);

	const merged: { s: number; e: number; terms: Set<string>; exact: boolean }[] = [];
	for (const mark of marks) {
		const last = merged[merged.length - 1];
		if (last && mark.s < last.e) {
			last.e = Math.max(last.e, mark.e);
			last.terms.add(mark.term);
			last.exact ||= mark.exact;
		} else {
			merged.push({ s: mark.s, e: mark.e, terms: new Set([mark.term]), exact: mark.exact });
		}
	}

	const out: Segment[] = [];
	let cursor = 0;
	for (const block of merged) {
		if (block.s > cursor)
			out.push({ text: speech.text.slice(cursor, block.s), terms: [], exact: false });
		out.push({
			text: speech.text.slice(block.s, block.e),
			terms: [...block.terms],
			exact: block.exact
		});
		cursor = block.e;
	}
	if (cursor < speech.text.length)
		out.push({ text: speech.text.slice(cursor), terms: [], exact: false });
	return out;
}

/**
 * The runs a reader sees: all of them with the opening form of address shown,
 * and otherwise everything after `body_start`. The address is the
 * Secretariat's speaker line rather than anything the speaker said.
 */
export function visible(
	speech: Speech,
	only: string | null,
	selection: Selection,
	showAddress: boolean
): Segment[] {
	const all = segments(speech, only, selection);
	if (showAddress || speech.body_start === 0) return all;
	let dropped = 0;
	const out: Segment[] = [];
	for (const segment of all) {
		const end = dropped + segment.text.length;
		if (end <= speech.body_start) {
			dropped = end;
			continue;
		}
		const from = Math.max(0, speech.body_start - dropped);
		out.push({ ...segment, text: segment.text.slice(from) });
		dropped = end;
	}
	return out;
}
