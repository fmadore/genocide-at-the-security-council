<script lang="ts">
	/**
	 * The collocate profile as a dot plot: one row per word, ranked as the
	 * artefact ranks them, position by log ratio, area by frequency beside the
	 * term, and a spread mark for dispersion. Inline SVG rather than ECharts so
	 * every word is a link a keyboard can reach, and so the export is the
	 * drawing itself.
	 */
	import { colours } from './theme';
	import { dotPosition, dotRadius, dotScale, spreadFill } from './dotplot';
	import { count, decimal, signed } from './format';
	import type { Word } from './types';

	interface Props {
		rows: Word[];
		term: string;
		href: (word: Word) => string;
		description: string;
	}

	let { rows, term, href, description }: Props = $props();

	let element = $state<SVGSVGElement | null>(null);
	export function svg(): SVGSVGElement | null {
		return element;
	}

	/* Built to the width it is given, as the calendar is: a fixed 720-unit
	   drawing left to a viewBox shrank to 0.41 of itself on a 390px phone and
	   set its words at under 5px. Below 720 the drawing is made at the column's
	   width, so the type stays at the size it is written at; above it the
	   drawing is as it always was. */
	const WIDEST = 720;
	let frame = $state<HTMLDivElement | null>(null);
	let available = $state(WIDEST);
	$effect(() => {
		const node = frame;
		if (!node) return;
		// Read once now, so the first frame is drawn at the right width rather
		// than at 720 and redrawn when the observer first reports.
		if (node.clientWidth > 0) available = node.clientWidth;
		const observer = new ResizeObserver(([entry]) => {
			const measured = Math.round(entry!.contentRect.width);
			if (measured > 0) available = measured;
		});
		observer.observe(node);
		return () => observer.disconnect();
	});
	const WIDTH = $derived(Math.max(260, Math.min(WIDEST, available)));
	const ROW = 22;
	/* The word column narrows with the drawing, never below what a long word
	   at 12px needs. */
	const LABEL = $derived(WIDTH < 560 ? Math.max(104, Math.round(WIDTH * 0.34)) : 150);
	const SPREAD = 28;
	const TOP = 28;
	const track = $derived(WIDTH - LABEL - SPREAD - 24);

	const scale = $derived(dotScale(rows));
	const largest = $derived(Math.max(1, ...rows.map((row) => row.target)));
	const height = $derived(TOP + rows.length * ROW + 8);
	/* A rule at every whole log ratio, a figure on as many as fit: on a narrow
	   track the figures ran into each other, so only every second (or fifth)
	   is written, and 0 always is. */
	const labelEvery = $derived.by(() => {
		const step = track / Math.max(1, scale.high - scale.low);
		return [1, 2, 5, 10].find((every) => every * step >= 28) ?? 10;
	});
	const x = (ratio: number) => LABEL + dotPosition(ratio, scale) * track;

	const title = (word: Word) =>
		`${word.word}: ${count(word.target)} near ${term}, log ratio ${signed(word.log_ratio)}` +
		(word.log_dice == null ? '' : `, logDice ${decimal(word.log_dice)}`) +
		`, ${count(word.documents)} speeches` +
		(word.meetings == null ? '' : ` / ${count(word.meetings)} meetings`) +
		`, DP ${decimal(word.dp)}`;
</script>

<!-- The frame is what is measured; measuring the drawing would be a loop. -->
<div class="frame" bind:this={frame}>
	<svg
		bind:this={element}
		viewBox="0 0 {WIDTH} {height}"
		width="100%"
		role="group"
		aria-label={description}
		style:font-family="var(--sans)"
		class="dotplot"
	>
		<g class="axis">
			{#each scale.ticks as tick (tick)}
				<line
					x1={x(tick)}
					x2={x(tick)}
					y1={TOP - 6}
					y2={height - 8}
					stroke={tick === 0 ? $colours.rule : $colours.ruleSoft}
					stroke-width={tick === 0 ? 1.2 : 0.8}
				/>
				{#if tick % labelEvery === 0}
					<text
						x={x(tick)}
						y={TOP - 10}
						text-anchor="middle"
						font-size="10"
						fill={$colours.inkFaint}>{tick === 0 ? '0' : signed(tick)}</text
					>
				{/if}
			{/each}
			<text x={LABEL} y={10} font-size="10" fill={$colours.inkFaint}>log ratio</text>
			<text x={WIDTH - 24} y={10} font-size="10" fill={$colours.inkFaint} text-anchor="end"
				>spread</text
			>
		</g>
		{#each rows as word, index (word.word)}
			{@const cy = TOP + index * ROW + ROW / 2}
			<g class="row">
				<title>{title(word)}</title>
				<a href={href(word)}>
					<text x={LABEL - 10} y={cy + 4} text-anchor="end" font-size="12" fill={$colours.ink}
						>{word.word}</text
					>
				</a>
				<line
					x1={x(0)}
					x2={x(word.log_ratio)}
					y1={cy}
					y2={cy}
					stroke={$colours.ruleSoft}
					stroke-width="1"
				/>
				<circle
					cx={x(word.log_ratio)}
					{cy}
					r={dotRadius(word.target, largest)}
					fill={$colours.ink}
					fill-opacity="0.82"
				/>
				<rect
					x={WIDTH - 24 - SPREAD}
					y={cy - 5}
					width={SPREAD}
					height="10"
					fill="none"
					stroke={$colours.rule}
					stroke-width="0.8"
				/>
				<rect
					x={WIDTH - 24 - SPREAD}
					y={cy - 5}
					width={SPREAD * spreadFill(word.dp)}
					height="10"
					fill={$colours.inkFaint}
				/>
			</g>
		{/each}
	</svg>
</div>

<style>
	.dotplot {
		display: block;
		max-width: 100%;
		height: auto;
	}

	.dotplot a:focus-visible text,
	.dotplot a:hover text {
		fill: var(--blue);
		text-decoration: underline;
	}
</style>
