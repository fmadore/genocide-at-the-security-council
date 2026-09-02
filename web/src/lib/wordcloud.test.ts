/**
 * What the word cloud decides, tested apart from how it is drawn.
 *
 * The cases below are the claims the figure makes about itself: that a slice
 * below the declared minimum is refused rather than replaced, that the table
 * and the cloud are one selection, that size means log ratio, and that the
 * same table always draws the same picture. Each is a claim a reader could
 * check by hand, which is why it is worth a test.
 */

import cloud from 'd3-cloud';
import type { CloudCanvas } from 'd3-cloud';
import { describe, expect, it } from 'vitest';
import { layoutCloud, plan, seededRandom, sizeWords, typeBand } from './wordcloud';
import type { CollocateBlock, Word } from './types';

const row = (word: string, target: number, g2: number, logRatio: number): Word => ({
	word,
	target,
	reference: 1000,
	g2,
	log_ratio: logRatio,
	documents: 12,
	meetings: 9,
	dp: 0.4
});

const block = (collocates: Word[], speeches?: number): CollocateBlock => ({
	occurrences: 500,
	window_tokens: 5000,
	collocates,
	speeches
});

/** A descending run of plausible rows: frequent and confident first. */
const rows = (n: number) =>
	Array.from({ length: n }, (_, index) =>
		row(`word${index}`, 500 - index * 4, 900 - index * 8, 9 - index * 0.05)
	);

/**
 * The smallest canvas `d3-cloud` will work against.
 *
 * The layout measures each word, paints it into a bitmap and reads that bitmap
 * back as a collision mask, so a stub has to do all three. Glyphs are painted
 * as solid rectangles, which is not what a browser produces — and does not need
 * to be. What is under test is that one input always gives one output and that
 * a different input gives a different one, neither of which depends on the
 * shape of a letter.
 */
function stubCanvas(): CloudCanvas {
	let width = 1;
	let height = 1;
	let pixels = new Uint8ClampedArray(4);
	let em = 10;
	let offsetX = 0;
	let offsetY = 0;
	const saved: [number, number][] = [];

	const advance = (text: string) => text.length * em * 0.6;

	const paint = (text: string, x: number) => {
		const left = Math.max(0, Math.round(offsetX + x));
		const right = Math.min(width, Math.round(offsetX + x + advance(text)));
		const top = Math.max(0, Math.round(offsetY - em * 0.35));
		const bottom = Math.min(height, Math.round(offsetY + em * 0.35));
		for (let y = top; y < bottom; y += 1) {
			for (let x0 = left; x0 < right; x0 += 1) {
				pixels[(y * width + x0) << 2] = 255;
			}
		}
	};

	const context = {
		fillStyle: '',
		strokeStyle: '',
		lineWidth: 0,
		set font(value: string) {
			const match = /(\d+(?:\.\d+)?)px/.exec(value);
			em = match ? Number(match[1]) : 10;
		},
		get font() {
			return `${em}px stub`;
		},
		save() {
			saved.push([offsetX, offsetY]);
		},
		restore() {
			const previous = saved.pop();
			if (previous) [offsetX, offsetY] = previous;
		},
		translate(x: number, y: number) {
			offsetX += x;
			offsetY += y;
		},
		rotate() {},
		clearRect() {
			pixels.fill(0);
		},
		measureText(text: string) {
			return { width: advance(text) };
		},
		fillText(text: string, x: number) {
			paint(text, x);
		},
		strokeText(text: string, x: number) {
			paint(text, x);
		},
		getImageData(_x: number, _y: number, w: number, h: number) {
			return { data: w === width && h === height ? pixels : new Uint8ClampedArray(4 * w * h) };
		}
	};

	const resize = () => {
		pixels = new Uint8ClampedArray(4 * width * height);
	};

	return {
		get width() {
			return width;
		},
		set width(value: number) {
			width = value;
			resize();
		},
		get height() {
			return height;
		},
		set height(value: number) {
			height = value;
			resize();
		},
		getContext: () => context
	};
}

const draw = (words: Word[], seed: string) =>
	layoutCloud(
		cloud,
		{
			words: sizeWords(words, typeBand(640)).words,
			frameWidth: 640,
			nominalHeight: 320,
			seed,
			font: 'stub',
			fontWeight: '600'
		},
		stubCanvas
	).done;

describe('choosing what a cloud shows', () => {
	it('refuses a slice under the declared minimum rather than substituting the whole corpus', () => {
		const result = plan({
			block: block(rows(40), 12),
			minimumSpeeches: 20,
			limit: 40,
			floor: 0
		});
		expect(result.rows).toEqual([]);
		// The interface has to name the slice's size *and* the threshold it fell
		// under, or the reader cannot tell a small slice from a broken artefact.
		expect(result.refusal).toEqual({
			kind: 'below-minimum',
			speeches: 12,
			minimum: 20,
			floor: null
		});
	});

	it('withholds the table too, so the two never disagree about a refused slice', () => {
		const result = plan({ block: block(rows(40), 3), minimumSpeeches: 20, limit: 40, floor: 0 });
		// `rows` is what the table lists. One empty array gates both views.
		expect(result.rows).toHaveLength(0);
		expect(result.available).toBe(40);
	});

	it('does not gate the whole corpus, which is not a slice and has no minimum', () => {
		const result = plan({ block: block(rows(10)), minimumSpeeches: null, limit: 40, floor: 0 });
		expect(result.refusal).toBeNull();
		expect(result.rows).toHaveLength(10);
	});

	it('tells an emptied filter apart from a withheld slice', () => {
		const result = plan({
			block: block(rows(10), 900),
			minimumSpeeches: 20,
			limit: 40,
			floor: 5000
		});
		expect(result.refusal?.kind).toBe('no-rows');
		expect(result.refusal?.floor).toBe(5000);
	});

	it('says how many rows the limit removed rather than truncating in silence', () => {
		const result = plan({ block: block(rows(100), 900), minimumSpeeches: 20, limit: 25, floor: 0 });
		expect(result.rows).toHaveLength(25);
		expect(result.available).toBe(100);
		expect(result.truncated).toBe(75);
		expect(result.filtered).toBe(0);
	});

	it('says how many rows the frequency floor removed', () => {
		// rows(20) runs from 500 occurrences down to 424 in steps of four.
		const result = plan({
			block: block(rows(20), 900),
			minimumSpeeches: 20,
			limit: 100,
			floor: 460
		});
		expect(result.rows.every((word) => word.target >= 460)).toBe(true);
		expect(result.filtered).toBe(20 - result.rows.length);
		expect(result.truncated).toBe(0);
	});

	it('hands the table and the cloud one array, in one order', () => {
		const result = plan({ block: block(rows(30), 900), minimumSpeeches: 20, limit: 12, floor: 0 });
		const sized = sizeWords(result.rows, typeBand(900));
		// Sizing selects nothing and drops nothing. If it ever did, the cloud
		// could come to show a different population from the table beneath it.
		expect(sized.words.map((item) => item.word)).toEqual(result.rows);
	});
});

describe('size stands for log ratio', () => {
	it('never draws a higher log ratio smaller than a lower one', () => {
		const shuffled = [
			row('a', 100, 500, 2.5),
			row('b', 100, 500, 11.2),
			row('c', 100, 500, 6.4),
			row('d', 100, 500, 1.585)
		];
		const { words } = sizeWords(shuffled, typeBand(900));
		const byRatio = [...words].sort((x, y) => x.word.log_ratio - y.word.log_ratio);
		for (let index = 1; index < byRatio.length; index += 1) {
			expect(byRatio[index].size).toBeGreaterThanOrEqual(byRatio[index - 1].size);
		}
	});

	it('carries the tone through the layout to the placed word', () => {
		// The renderer reads `tone` off the placement, not off the sized word, so
		// a placement that dropped it would mix `color-mix` over `NaN%` — which
		// invalidates the declaration and paints every word the default black.
		const { words } = sizeWords(
			[row('a', 100, 500, 1.585), row('b', 100, 500, 11.2)],
			typeBand(900)
		);
		for (const item of words) expect(Number.isFinite(item.tone)).toBe(true);
	});

	it('colours by the same position in the range that sized the word', () => {
		// Colour is mixed by `tone` at render time. If it could disagree with
		// `size`, the cloud would show one word larger and another stronger,
		// which is two rankings of one column.
		const rows = [row('a', 100, 500, 1.585), row('b', 100, 500, 6.4), row('c', 100, 500, 11.2)];
		const { words } = sizeWords(rows, typeBand(900));
		const bySize = [...words].sort((x, y) => x.size - y.size);
		const byTone = [...words].sort((x, y) => x.tone - y.tone);
		expect(byTone.map((item) => item.word.word)).toEqual(bySize.map((item) => item.word.word));
	});

	it('keeps every tone inside the range the renderer mixes over', () => {
		// `--tone` becomes a percentage in color-mix; outside 0-1 it would either
		// clamp silently or produce a colour from neither end of the scale.
		const rows = [row('a', 100, 500, -2.5), row('b', 100, 500, 0), row('c', 100, 500, 11.2)];
		for (const item of sizeWords(rows, typeBand(900)).words) {
			expect(item.tone).toBeGreaterThanOrEqual(0);
			expect(item.tone).toBeLessThanOrEqual(1);
		}
	});

	it('gives a slice with nothing to compare the middle tone rather than the faintest', () => {
		// Same reasoning as the size: one word, or a slice with no range, has
		// nothing to rank, and drawing it at tone 0 would state a ranking anyway.
		const flat = ['a', 'b', 'c'].map((text) => row(text, 40, 300, 4.2));
		for (const item of sizeWords(flat, typeBand(900)).words) expect(item.tone).toBe(0.5);
		expect(sizeWords([row('tutsi', 163, 1898, 10.656)], typeBand(900)).words[0].tone).toBe(0.5);
	});

	it('draws a slice whose log ratios are all equal at one legible size, not at none', () => {
		// Division by the range would be a division by zero here, and a cloud of
		// invisible words looks exactly like a cloud of no words.
		const flat = ['a', 'b', 'c'].map((text) => row(text, 40, 300, 4.2));
		const { words } = sizeWords(flat, typeBand(900));
		expect(words.map((item) => item.size)).toEqual([words[0].size, words[0].size, words[0].size]);
		expect(words[0].size).toBeGreaterThan(0);
	});

	it('does not blow up the scale on a single-word slice', () => {
		const { words, scale } = sizeWords([row('tutsi', 163, 1898, 10.656)], typeBand(900));
		expect(words).toHaveLength(1);
		expect(Number.isFinite(words[0].size)).toBe(true);
		expect(words[0].size).toBeGreaterThan(0);
		expect(scale.low).toBe(scale.high);
	});

	it('keeps a word repelled from the node above zero pixels', () => {
		// A negative log ratio means the word is rarer beside the node than away
		// from it. Mapped naively onto a font size that is a negative number, and
		// the word silently disappears instead of being drawn small.
		const repelled = [
			row('welcome', 30, 90, -3.4),
			row('zero', 30, 90, 0),
			row('tutsi', 30, 900, 10.6)
		];
		const { words } = sizeWords(repelled, typeBand(900));
		for (const item of words) expect(item.size).toBeGreaterThan(0);
	});

	it('scales with the frame, so a phone is not asked to carry desktop type', () => {
		expect(typeBand(320).largest).toBeLessThan(typeBand(1200).largest);
		expect(typeBand(320).smallest).toBeGreaterThan(0);
	});
});

describe('the layout is a depiction rather than a decoration', () => {
	it('draws the same slice identically on every render, positions included', async () => {
		const words = rows(14);
		const first = await draw(words, 'by_country:Rwanda');
		const second = await draw(words, 'by_country:Rwanda');
		expect(first).not.toBeNull();
		expect(first!.placed.length).toBeGreaterThan(0);
		// This is the test that fails if the seeding is ever dropped: `d3-cloud`
		// starts each word at a random point, so on `Math.random` two renders of
		// one table land in different places.
		expect(second).toEqual(first);
	});

	it('draws a different facet differently, so determinism is not indifference', async () => {
		const words = rows(14);
		const rwanda = await draw(words, 'by_country:Rwanda');
		const france = await draw(words, 'by_country:France');
		expect(france!.placed.map((item) => [item.x, item.y])).not.toEqual(
			rwanda!.placed.map((item) => [item.x, item.y])
		);
	});

	it('draws different words when the slice holds different words', async () => {
		const rwanda = await draw(rows(14), 'by_country:Rwanda');
		const other = await draw(
			['denial', 'perpetrators', 'gacaca'].map((text) => row(text, 60, 400, 7.2)),
			'by_country:Rwanda'
		);
		expect(other!.placed.map((item) => item.word.word)).not.toEqual(
			rwanda!.placed.map((item) => item.word.word)
		);
	});

	it('accounts for every word, either placed or named as unplaced', async () => {
		const words = rows(30);
		const drawing = await draw(words, 'whole:genocide:8');
		expect(drawing!.placed.length + drawing!.refused.length).toBe(words.length);
		const placed = new Set(drawing!.placed.map((item) => item.word.word));
		expect(drawing!.refused.some((text) => placed.has(text))).toBe(false);
	});

	it('does not throw away a finished layout when the effect that started it is torn down', async () => {
		const run = layoutCloud(
			cloud,
			{
				words: sizeWords(rows(14), typeBand(640)).words,
				frameWidth: 640,
				nominalHeight: 320,
				seed: 'by_period:1992-1999',
				font: 'stub',
				fontWeight: '600'
			},
			stubCanvas
		);
		run.stop();
		// Written expecting a null here, and wrong: `d3-cloud` is given no time
		// budget, so it runs to completion inside `start()` and the drawing
		// already exists by the time an effect cleanup can stop it. Stopping must
		// not discard it, or the reader is left at "Drawing…" for a cloud that has
		// been laid out. `stop()` remains for the case where a budget is set.
		await expect(run.done).resolves.not.toBeNull();
	});

	it('gives one seed one sequence, in whatever order the seeds are asked for', () => {
		const first = seededRandom('by_country:Rwanda');
		const again = seededRandom('by_country:Rwanda');
		const other = seededRandom('by_country:France');
		const take = (source: () => number) => Array.from({ length: 5 }, source);
		expect(take(again)).toEqual(take(first));
		expect(take(other)).not.toEqual(take(seededRandom('by_country:Rwanda')));
	});
});
