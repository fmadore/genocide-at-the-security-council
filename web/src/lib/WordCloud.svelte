<script lang="ts">
	/**
	 * A word cloud drawn in SVG, from the table it depicts.
	 *
	 * This component decides nothing. Which rows are shown and why any are
	 * withheld is settled in `$lib/wordcloud` by the same call that feeds the
	 * table, and the positions come from `d3-cloud`. What is left here is the
	 * drawing, and three choices about how it is drawn.
	 *
	 * It is SVG rather than canvas. Every word is an `<a>` carrying its own row
	 * of numbers, so the cloud is navigable by keyboard, readable by a screen
	 * reader, and each word leads to the lines behind it. A canvas cloud is a
	 * picture of a table that cannot be got back to.
	 *
	 * `d3-cloud` is loaded on mount rather than imported. It measures glyphs on
	 * a canvas, and this site is prerendered by adapter-static, so it must never
	 * run on the server; loading it here keeps it out of the server bundle as
	 * well as out of the server's way.
	 *
	 * Colour comes from the custom properties in `app.css` rather than from
	 * `palette()`. The fills are `var(--ink)` and `var(--accent)`, so the cloud
	 * follows the light/dark switch without being laid out again — and colour
	 * therefore encodes nothing, which is deliberate. Size is the only quantity
	 * here, and it is the log ratio.
	 */
	import { onMount } from 'svelte';
	import { FONT } from '$lib/theme';
	import { layoutCloud, sizeWords, typeBand } from '$lib/wordcloud';
	import type { Drawing } from '$lib/wordcloud';
	import type { CloudFactory } from 'd3-cloud';
	import type { Word } from '$lib/types';

	interface Props {
		/** The chosen rows, in the artefact's own order. */
		words: Word[];
		/** Where a word leads: the lines behind it. */
		href: (word: Word) => string;
		/** The word's own numbers — hover title and accessible name. */
		label: (word: Word) => string;
		/** Announced in place of the drawing. */
		description: string;
		/** Names what is drawn, so the same selection always draws alike. */
		seed: string;
		/** The height the cloud aims at; it grows if the words need the room. */
		height?: number;
	}

	let { words, href, label, description, seed, height = 360 }: Props = $props();

	/** Measurement and drawing must agree, so both take their weight from here. */
	const WEIGHT = '600';
	const captionId = $props.id();

	let frame: HTMLDivElement;
	let frameWidth = $state(0);
	let factory = $state<CloudFactory | null>(null);
	let drawing = $state<Drawing | null>(null);

	onMount(() => {
		let live = true;
		void import('d3-cloud').then((module) => {
			if (live) factory = module.default;
		});
		// Measured here as well as observed. A ResizeObserver only delivers as part
		// of a rendering step, so waiting for its first callback means a frame of
		// "Drawing…" in the common case and nothing at all in a document that is
		// laid out but never painted.
		frameWidth = Math.round(frame.clientWidth);
		const observer = new ResizeObserver((entries) => {
			// Rounded, so a fractional resize does not lay the cloud out again for
			// a change nobody can see.
			const measured = Math.round(entries[0].contentRect.width);
			if (measured !== frameWidth) frameWidth = measured;
		});
		observer.observe(frame);
		return () => {
			live = false;
			observer.disconnect();
		};
	});

	const sized = $derived(sizeWords(words, typeBand(frameWidth)));

	$effect(() => {
		const build = factory;
		const items = sized.words;
		const width = frameWidth;
		const box = height;
		const key = seed;
		if (!build || items.length === 0 || width <= 0) {
			drawing = null;
			return;
		}
		let live = true;
		const run = layoutCloud(
			build,
			{
				words: items,
				frameWidth: width,
				nominalHeight: box,
				seed: key,
				font: FONT,
				fontWeight: WEIGHT
			},
			() => document.createElement('canvas')
		);
		void run.done.then((result) => {
			if (live && result) drawing = result;
		});
		// A layout belonging to the previous selection must not paint over the one
		// the reader has just asked for, whether it has finished or not.
		return () => {
			live = false;
			run.stop();
		};
	});
</script>

<div class="frame" bind:this={frame}>
	{#if drawing && drawing.placed.length > 0}
		<svg
			class="cloud"
			width={drawing.width}
			height={drawing.height}
			viewBox={drawing.view}
			aria-labelledby={captionId}
			style:font-family={FONT}
			style:font-weight={WEIGHT}
		>
			<title id={captionId}>{description}</title>
			{#each drawing.placed as item (item.word.word)}
				<a href={href(item.word)}>
					<title>{label(item.word)}</title>
					<text
						x={item.x}
						y={item.y}
						font-size={item.size}
						text-anchor="middle"
						style:--tone="{Math.round(item.tone * 100)}%">{item.word.word}</text
					>
				</a>
			{/each}
		</svg>
	{:else}
		<p class="waiting">Drawing&hellip;</p>
	{/if}
</div>

{#if drawing && drawing.refused.length > 0}
	<p class="refused">
		For want of room rather than want of evidence, not drawn at this width:
		<em>{drawing.refused.join(', ')}</em>. The table below still carries every row.
	</p>
{/if}

<style>
	.frame {
		width: 100%;
		display: flex;
		justify-content: center;
		min-height: 8rem;
	}

	.cloud {
		max-width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}

	.cloud a {
		text-decoration: none;
	}

	/* Fill runs from the body colour for the weakest collocate drawn to the
	   accent for the strongest, mixed by `--tone` — the same position in the
	   log-ratio range that set the type size. Both ends are theme variables, so
	   the light/dark switch needs no relayout, and both are already legible
	   against the page, so no mix of them can fall below the contrast either
	   end has. `oklab` because mixing in sRGB drives the midpoint muddy. */
	.cloud text {
		fill: color-mix(in oklab, var(--accent) var(--tone, 0%), var(--ink));
		transition: fill 0.12s ease;
	}

	.cloud a:hover text,
	.cloud a:focus-visible text {
		fill: var(--accent);
		text-decoration: underline;
	}

	.cloud a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.cloud text {
			transition: none;
		}
	}

	.waiting {
		margin: auto;
		color: var(--ink-faint);
		font-size: 0.875rem;
	}

	.refused {
		margin: 0.6rem 0 0;
		font-size: 0.78rem;
		color: var(--ink-faint);
	}
</style>
