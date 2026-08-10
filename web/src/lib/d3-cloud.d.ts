/**
 * Types for the part of `d3-cloud` this project uses, and no more.
 *
 * `@types/d3-cloud` exists, but it depends on `@types/d3@^3` — the typings for
 * the whole of d3 version 3 — which is a large and long-dead dependency to take
 * on for one builder. What is declared here is exactly what `wordcloud.ts`
 * calls. Nothing else is described, because a plausible-looking type for a
 * method nobody has run is worse than no type at all.
 *
 * `d3-cloud` computes positions; this project renders them. That division is
 * why the layout can be a proven one and every word can still be an anchor.
 */
declare module 'd3-cloud' {
	/** The slice of the canvas API the layout uses to measure and mask glyphs. */
	export interface CloudCanvas {
		width: number;
		height: number;
		getContext(kind: '2d', options?: { willReadFrequently?: boolean }): unknown;
	}

	/**
	 * A word handed to the layout. `x`, `y`, `rotate` and `size` are written
	 * back by `start()`, so they are present before it runs and meaningful
	 * after.
	 */
	export interface CloudWord {
		text: string;
		size: number;
		x: number;
		y: number;
		rotate: number;
	}

	/** A corner of the box the placed words occupy, in layout coordinates. */
	export interface CloudCorner {
		x: number;
		y: number;
	}

	export interface Cloud<T extends CloudWord> {
		size(dimensions: [number, number]): Cloud<T>;
		words(words: T[]): Cloud<T>;
		padding(padding: number): Cloud<T>;
		font(font: string): Cloud<T>;
		fontWeight(weight: string): Cloud<T>;
		fontSize(size: (word: T, index: number) => number): Cloud<T>;
		rotate(rotate: (word: T, index: number) => number): Cloud<T>;
		/** The source of placement randomness. Seed it, or the cloud reshuffles. */
		random(source: () => number): Cloud<T>;
		canvas(source: () => CloudCanvas): Cloud<T>;
		/** `words` holds only what was placed; anything that did not fit is absent. */
		on(type: 'end', listener: (words: T[], bounds?: [CloudCorner, CloudCorner]) => void): Cloud<T>;
		start(): Cloud<T>;
		stop(): Cloud<T>;
	}

	export type CloudFactory = <T extends CloudWord>() => Cloud<T>;

	const cloud: CloudFactory;
	export default cloud;
}
