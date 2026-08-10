/**
 * Marking the search query inside a concordance line.
 *
 * The keyword itself is already distinguished — it is the node the concordance
 * was built around, and it is styled as such. What was missing is the reader's
 * own query: filtering 6,092 lines down to 37 tells you the term is in there
 * somewhere, and then leaves you to find it by eye in every snippet.
 *
 * Returned as segments rather than as HTML, so the caller renders them through
 * Svelte's ordinary text interpolation and no search string can ever become
 * markup. A concordance over a corpus of arbitrary text is exactly the place
 * where building highlight markup by hand would eventually go wrong.
 */

export interface Segment {
	text: string;
	/** True when this segment is part of what the reader searched for. */
	hit: boolean;
}

/**
 * A pathological pattern over a long line can match thousands of times. The cap
 * is far above any legible number of marks and exists only so a regex like `\b`
 * cannot turn one snippet into ten thousand DOM nodes.
 */
const MAX_HITS = 200;

/** Escape a literal query so it can be run through the same regex path. */
function literal(query: string): string {
	return query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Split `text` around every match of `query`.
 *
 * An empty query, an unmatched line, or a regex the reader is still halfway
 * through typing all return the text as a single unmarked segment — the line
 * stays readable while the pattern is invalid, rather than flickering or
 * vanishing.
 */
export function segments(text: string, query: string, useRegex = false): Segment[] {
	const whole = [{ text, hit: false }];
	if (!text || !query.trim()) return whole;

	let pattern: RegExp;
	try {
		pattern = new RegExp(useRegex ? query : literal(query), 'gi');
	} catch {
		return whole;
	}

	const out: Segment[] = [];
	let cursor = 0;
	let hits = 0;
	for (const match of text.matchAll(pattern)) {
		// A pattern that can match nothing (`a*`, `\b`) marks nothing. Skipping
		// keeps it from splitting the line into empty segments; `matchAll`
		// already guarantees it advances, so this cannot loop.
		if (!match[0]) continue;
		if (hits >= MAX_HITS) break;
		const start = match.index ?? 0;
		if (start > cursor) out.push({ text: text.slice(cursor, start), hit: false });
		out.push({ text: match[0], hit: true });
		cursor = start + match[0].length;
		hits += 1;
	}
	if (!out.length) return whole;
	if (cursor < text.length) out.push({ text: text.slice(cursor), hit: false });
	return out;
}
