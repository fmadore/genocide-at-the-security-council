/**
 * The decisions behind the word cloud, kept out of the component that draws it.
 *
 * A cloud is a rendering of a collocate table, not a separate artefact, so
 * everything that could make the two disagree lives here where it can be
 * tested: which rows are shown, why rows are withheld, and what size stands
 * for. `WordCloud.svelte` is a renderer over the result and decides nothing.
 *
 * Two rules are worth stating because they are the reason this file exists.
 *
 * One selection feeds both views. `plan()` chooses the rows once; the table
 * lists them and `sizeWords()` attaches a size to the same array in the same
 * order for the cloud. There is no second path by which a cloud could come to
 * show a different population from the table beneath it.
 *
 * A slice below the artefact's declared minimum is refused, not substituted.
 * The refusal carries both the threshold and the count so the interface can
 * say which slice was asked for and why it is not drawn. Quietly falling back
 * to the whole corpus would answer a question the reader did not ask.
 */

import type { CloudCanvas, CloudFactory, CloudWord } from 'd3-cloud';
import type { CollocateBlock, Word } from './types';

/** Padding around each word, in pixels, passed to the layout. */
const PADDING = 2;

/** Mean advance of a semibold sans glyph, as a share of the em. */
const ADVANCE = 0.62;

/** Line box of a word, as a share of the em. */
const INK = 1.15;

/**
 * How much of its box a word cloud actually fills. Used only to choose a box
 * tall enough that the packer is not forced to discard words for want of room;
 * the drawn height comes from where the words landed, not from here.
 */
const PACKING = 0.42;

/** The largest and smallest type a frame can carry, in pixels. */
export interface TypeBand {
	smallest: number;
	largest: number;
}

export interface SizedWord {
	word: Word;
	/** Font size in pixels. Linear in log ratio, and never zero or negative. */
	size: number;
	/**
	 * Where this word sits in the drawn slice's log-ratio range, 0 to 1.
	 *
	 * The renderer mixes its fill between two theme colours by this figure, so
	 * colour carries the same quantity the size does and introduces no second
	 * claim — `docs/PLAN.md` §7 forbids colour encoding anything the underlying
	 * table does not support. One flat fill for forty words was the alternative,
	 * and it read as a wall rather than as a ranking.
	 */
	tone: number;
}

/**
 * Why nothing is drawn. `speeches` and `minimum` are both carried because the
 * interface has to name the slice's size *and* the threshold it fell under —
 * a message with only one of them cannot be checked by a reader.
 */
export interface Refusal {
	kind: 'missing' | 'below-minimum' | 'no-rows';
	/** Speeches behind the slice, where there is a slice. */
	speeches: number | null;
	/** The minimum the artefact declares. */
	minimum: number | null;
	/** The frequency floor in force, where that is what emptied the table. */
	floor: number | null;
}

export interface CloudRequest {
	/** The block asked for. `undefined` when the facet holds no such member. */
	block: CollocateBlock | undefined;
	/**
	 * The minimum speeches the artefact declares for a slice, or `null` for the
	 * whole corpus, which is not a slice and has no minimum to fall under.
	 */
	minimumSpeeches: number | null;
	/** Rows drawn, at most. */
	limit: number;
	/** Words occurring fewer times than this near the node are not drawn. */
	floor: number;
}

export interface CloudPlan {
	/** The rows drawn, and the rows listed. One array, so the two agree. */
	rows: Word[];
	/** Rows the artefact holds for this slice, before any filter. */
	available: number;
	/** Rows removed by the frequency floor. */
	filtered: number;
	/** Rows removed by the limit, after the floor. Stated, never silent. */
	truncated: number;
	refusal: Refusal | null;
}

/**
 * The type band a frame of this width can carry.
 *
 * The largest size is tied to the width so that a long word in a narrow column
 * cannot decide the scale for everything else, and the smallest is a fixed
 * share of it so the range stays legible rather than collapsing to a single
 * size on a phone.
 */
export function typeBand(frameWidth: number): TypeBand {
	const largest = Math.min(54, Math.max(20, frameWidth / 11));
	return { smallest: Math.max(11, largest * 0.34), largest };
}

const nothing = (refusal: Refusal, available: number): CloudPlan => ({
	rows: [],
	available,
	filtered: 0,
	truncated: 0,
	refusal
});

/**
 * Choose the rows the figure shows, or say why it shows none.
 *
 * Note that a refusal empties `rows`, so the table under the cloud is gated by
 * the same decision the cloud is. A withheld slice is withheld in both, which
 * is the point of there being one function.
 */
export function plan(request: CloudRequest): CloudPlan {
	const { block, minimumSpeeches, limit, floor } = request;

	if (!block) {
		return nothing({ kind: 'missing', speeches: null, minimum: minimumSpeeches, floor: null }, 0);
	}

	// The gate, before anything is counted. A slice below the declared minimum
	// is not drawn, and the whole corpus is not put in its place.
	if (minimumSpeeches !== null && (block.speeches ?? 0) < minimumSpeeches) {
		return nothing(
			{
				kind: 'below-minimum',
				speeches: block.speeches ?? 0,
				minimum: minimumSpeeches,
				floor: null
			},
			block.collocates.length
		);
	}

	const available = block.collocates.length;
	const kept = block.collocates.filter((word) => word.target >= floor);
	const rows = kept.slice(0, Math.max(0, limit));

	if (rows.length === 0) {
		return nothing(
			{ kind: 'no-rows', speeches: block.speeches ?? null, minimum: null, floor },
			available
		);
	}

	return {
		rows,
		available,
		filtered: available - kept.length,
		truncated: kept.length - rows.length,
		refusal: null
	};
}

/** The mapping from log ratio to pixels, so the figure can state it. */
export interface SizeScale {
	low: number;
	high: number;
	smallest: number;
	largest: number;
}

/**
 * Attach a size to each chosen row.
 *
 * Size is linear in log ratio across what is on screen: the largest word in
 * view holds the largest log ratio in view. That makes a cloud comparable
 * within itself and not across two, which the figure says. The order of the
 * rows is preserved untouched — this function selects nothing and drops
 * nothing, so a cloud cannot come to hold a different set from its table.
 */
export function sizeWords(rows: Word[], band: TypeBand): { words: SizedWord[]; scale: SizeScale } {
	if (rows.length === 0) {
		return {
			words: [],
			scale: { low: 0, high: 0, smallest: band.smallest, largest: band.largest }
		};
	}
	const ratios = rows.map((word) => word.log_ratio);
	const low = Math.min(...ratios);
	const high = Math.max(...ratios);
	// A slice of one word, or a slice whose words all share a log ratio, has no
	// range to map. Both are drawn at the middle of the band rather than at zero:
	// there is nothing to compare, and nothing to hide either.
	const flat = high - low < 1e-9;
	const middle = (band.smallest + band.largest) / 2;
	const words = rows.map((word) => {
		// One position in the range drives both size and colour, so the two can
		// never disagree about which word is the stronger collocate.
		const at = flat ? 0.5 : (word.log_ratio - low) / (high - low);
		return {
			word,
			size: flat ? middle : band.smallest + at * (band.largest - band.smallest),
			tone: at
		};
	});
	return { words, scale: { low, high, smallest: band.smallest, largest: band.largest } };
}

/**
 * A deterministic source of randomness, from a string that names what is drawn.
 *
 * `d3-cloud` starts every word at a random point and walks the spiral in a
 * random direction. Left on `Math.random` the same table would draw a different
 * cloud on every render, which is a decoration rather than a depiction. FNV-1a
 * into mulberry32: small, and identical in every runtime, which is the only
 * property wanted here.
 */
export function seededRandom(seed: string): () => number {
	let hash = 2166136261;
	for (let index = 0; index < seed.length; index += 1) {
		hash ^= seed.charCodeAt(index);
		hash = Math.imul(hash, 16777619);
	}
	let state = hash >>> 0;
	return () => {
		state = (state + 0x6d2b79f5) >>> 0;
		let t = state;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/**
 * The box the layout packs into.
 *
 * Width is rounded down to a multiple of 32 because `d3-cloud` keeps its
 * collision board 32 pixels to the integer and loses the remainder. Height is
 * whichever is larger of the nominal height and enough room for the ink, so
 * that asking for a hundred words does not silently discard sixty of them.
 */
export function layoutBox(words: SizedWord[], frameWidth: number, nominalHeight: number) {
	const width = Math.max(32, Math.floor(frameWidth / 32) * 32);
	let area = 0;
	for (const item of words) {
		const wide = item.size * item.word.word.length * ADVANCE + 2 * PADDING;
		const tall = item.size * INK + 2 * PADDING;
		area += wide * tall;
	}
	const height = Math.round(Math.min(1400, Math.max(nominalHeight, area / (PACKING * width))));
	return { width, height };
}

export interface Placement {
	word: Word;
	size: number;
	x: number;
	y: number;
	/** Carried through from `SizedWord`, so the fill and the size agree. */
	tone: number;
}

export interface Drawing {
	/** Placed words, in the artefact's order rather than the packer's. */
	placed: Placement[];
	/** Words the packer could not seat. Named in the figure, never dropped. */
	refused: string[];
	/** `viewBox`, tight around the ink. */
	view: string;
	width: number;
	height: number;
}

export interface LayoutRequest {
	words: SizedWord[];
	frameWidth: number;
	nominalHeight: number;
	/** Names what is drawn. The same name always draws the same picture. */
	seed: string;
	font: string;
	fontWeight: string;
}

interface Item extends CloudWord {
	row: Word;
	px: number;
}

function collect(
	words: SizedWord[],
	placed: Item[],
	bounds: [{ x: number; y: number }, { x: number; y: number }] | undefined,
	width: number,
	height: number
): Drawing {
	const at = new Map(placed.map((item) => [item.text, item]));
	const drawn: Placement[] = [];
	const refused: string[] = [];
	for (const item of words) {
		const seat = at.get(item.word.word);
		if (seat)
			drawn.push({ word: item.word, size: seat.size, x: seat.x, y: seat.y, tone: item.tone });
		else refused.push(item.word.word);
	}
	if (!bounds || drawn.length === 0) {
		return {
			placed: [],
			refused: words.map((item) => item.word.word),
			view: '0 0 1 1',
			width: 1,
			height: 1
		};
	}
	// `d3-cloud` reports bounds in the layout's own frame but returns each word
	// centred on the box, so the two are one half-box apart.
	const left = bounds[0].x - (width >> 1);
	const top = bounds[0].y - (height >> 1);
	const boxWidth = Math.max(1, bounds[1].x - bounds[0].x);
	const boxHeight = Math.max(1, bounds[1].y - bounds[0].y);
	return {
		placed: drawn,
		refused,
		view: `${left} ${top} ${boxWidth} ${boxHeight}`,
		width: boxWidth,
		height: boxHeight
	};
}

/**
 * Run the layout. Positions only: the caller draws the words.
 *
 * The canvas factory is a parameter rather than a call to `document` so that
 * this function has no opinion about where it runs — the component hands it a
 * real canvas, a test hands it a stub, and neither has to be the browser.
 */
export function layoutCloud(
	factory: CloudFactory,
	request: LayoutRequest,
	canvas: () => CloudCanvas
): { done: Promise<Drawing | null>; stop: () => void } {
	const { width, height } = layoutBox(request.words, request.frameWidth, request.nominalHeight);
	const items: Item[] = request.words.map((item) => ({
		text: item.word.word,
		row: item.word,
		px: Math.max(1, Math.round(item.size)),
		size: 0,
		x: 0,
		y: 0,
		rotate: 0
	}));

	let settle: (value: Drawing | null) => void = () => {};
	const done = new Promise<Drawing | null>((resolve) => {
		settle = resolve;
	});
	let over = false;

	const layout = factory<Item>()
		.canvas(canvas)
		.size([width, height])
		.words(items)
		.padding(PADDING)
		.font(request.font)
		.fontWeight(request.fontWeight)
		.fontSize((item) => item.px)
		// Rotation costs legibility and buys nothing in a research figure, and a
		// word turned on its side is a harder link to hit.
		.rotate(() => 0)
		.random(seededRandom(request.seed))
		.on('end', (drawn, bounds) => {
			if (over) return;
			over = true;
			settle(collect(request.words, drawn, bounds, width, height));
		});

	layout.start();

	return {
		done,
		/**
		 * Abandon a layout still in progress. `d3-cloud` is given no time budget,
		 * so it normally finishes inside `start()` above and this is a no-op that
		 * leaves the finished drawing alone. It exists for the case where it does
		 * not: a half-placed cloud must not resolve into a view that has already
		 * moved to another slice.
		 */
		stop: () => {
			if (over) return;
			over = true;
			layout.stop();
			settle(null);
		}
	};
}
