/**
 * The dot plot that replaced the word cloud (review of 1 September 2026, §5.2).
 *
 * A cloud needed 200 words of caveat to say what it did not encode — size is
 * not area, long words look bigger, position and colour mean nothing. A dot
 * plot encodes three things and each is a length or an area a reader can
 * check: position is the log ratio, the dot's area is the frequency beside
 * the term, and the spread mark is how evenly the word is dispersed over the
 * speeches. The arithmetic lives here so it can be tested, and the component
 * only draws it.
 */
import type { Word } from './types';

export interface DotScale {
	/** The log ratio at the left edge: never above zero, so the zero rule is always drawn. */
	low: number;
	/** The log ratio at the right edge: never below zero. */
	high: number;
	/** Integer log ratios inside [low, high], for the axis ticks. */
	ticks: number[];
}

/** The range the track covers, padded so the outermost dot is not clipped. */
export function dotScale(rows: readonly Word[]): DotScale {
	const ratios = rows.map((row) => row.log_ratio);
	const low = Math.min(0, ...ratios) - 0.25;
	const high = Math.max(0, ...ratios) + 0.25;
	const ticks: number[] = [];
	for (let t = Math.ceil(low); t <= Math.floor(high); t += 1) ticks.push(t);
	return { low, high, ticks };
}

/** Where a log ratio sits on the track, 0 at the left edge and 1 at the right. */
export function dotPosition(logRatio: number, scale: DotScale): number {
	if (scale.high === scale.low) return 0.5;
	return Math.min(1, Math.max(0, (logRatio - scale.low) / (scale.high - scale.low)));
}

/**
 * The dot's radius: area proportional to the frequency beside the term.
 *
 * Square root, because area is what the eye compares, and a linear radius
 * would overstate a four-fold frequency as a sixteen-fold dot — the fault the
 * review found in the map's circles. Floored so a word at the minimum count
 * is still a mark a reader can hover.
 */
export function dotRadius(target: number, largest: number, floor = 3, cap = 11): number {
	if (largest <= 0 || target <= 0) return floor;
	return floor + (cap - floor) * Math.sqrt(Math.min(target, largest) / largest);
}

/**
 * The spread mark's fill, from DP: a full mark is a word spread as the text
 * is, an empty one a word confined to a corner of it. `1 - DP` so that "more
 * filled" reads as "more evenly spread", which is the reading a reader will
 * take from a filled bar whatever the legend says.
 */
export function spreadFill(dp: number): number {
	return Math.min(1, Math.max(0, 1 - dp));
}
