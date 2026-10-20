<script lang="ts">
	/**
	 * The frame profile: one row per construction, two marks and a whisker.
	 *
	 * An open dot is the frame's share of all the node's occurrences; a filled
	 * dot with a Wilson interval is its share in the slice the reader chose. The
	 * reading is the distance between them, and the whisker says whether that
	 * distance is worth reading. A row whose interval does not cover the corpus
	 * share is marked with a rule at the corpus dot rather than with a word:
	 * seventeen frames are on screen and nothing is corrected for that, so the
	 * mark is an invitation to look, not a claim of significance.
	 *
	 * Inline SVG rather than ECharts, as `DotPlot.svelte` is and for the same
	 * reasons: every row is reachable by keyboard, and the export is the drawing.
	 * Ink and greys only — the register hues mean "register" on this site and a
	 * frame is not one, and the accent belongs to what a reader can act on and
	 * may never stand for a datum.
	 */
	import { colours } from './theme';
	import { count, percent } from './format';
	import { frameLabel, outside, position, track } from './nodeframes';
	import type { FrameRow } from './nodeframes';

	interface Props {
		rows: FrameRow[];
		/** The slice on the filled dots, for the row's title. Empty for none. */
		slice: string;
		description: string;
	}

	let { rows, slice, description }: Props = $props();

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
	/* The label column narrows with the drawing, never below what the longest
	   function name needs at 12px. */
	const LABEL = $derived(WIDTH < 560 ? Math.max(120, Math.round(WIDTH * 0.4)) : 168);
	const TOP = 30;
	const RIGHT = 16;
	const trackWidth = $derived(WIDTH - LABEL - RIGHT);

	const scale = $derived(track(rows));
	const height = $derived(TOP + rows.length * ROW + 10);
	const x = (share: number) => LABEL + position(share, scale) * trackWidth;

	const label = frameLabel;

	/* Whole points on the axis. `percent` gives two decimals, which is right
	   beside a number a reader may quote and wrong on a tick they only read
	   against. */
	const tickLabel = (share: number) => `${Math.round(share * 100)}%`;

	const title = (row: FrameRow) =>
		`${label(row.frame)}: ${percent(row.overall)} of all occurrences ` +
		`(${count(row.overallOccurrences)})` +
		(row.share === null
			? slice
				? `; ${slice} withheld, ${count(row.occurrences)} occurrences`
				: ''
			: `; ${percent(row.share)} in ${slice} ` +
				`[${percent(row.low ?? 0)}, ${percent(row.high ?? 0)}], ` +
				`${count(row.occurrences)} occurrences`);
</script>

<!-- The frame is what is measured; measuring the drawing would be a loop. -->
<div class="frame" bind:this={frame}>
	<svg
		bind:this={element}
		viewBox="0 0 {WIDTH} {height}"
		width="100%"
		role="img"
		aria-label={description}
		style:font-family="var(--sans)"
		class="frames"
	>
		<g class="axis">
			{#each scale.ticks as tick (tick)}
				<line
					x1={x(tick)}
					x2={x(tick)}
					y1={TOP - 6}
					y2={height - 10}
					stroke={tick === 0 ? $colours.rule : $colours.ruleSoft}
					stroke-width={tick === 0 ? 1.2 : 0.8}
				/>
				<text x={x(tick)} y={TOP - 10} text-anchor="middle" font-size="10" fill={$colours.inkFaint}
					>{tickLabel(tick)}</text
				>
			{/each}
			<text x={LABEL} y={12} font-size="10" fill={$colours.inkFaint}
				>share of the word's occurrences</text
			>
		</g>
		{#each rows as row, index (row.frame)}
			{@const cy = TOP + index * ROW + ROW / 2}
			<g class="row">
				<title>{title(row)}</title>
				<text x={LABEL - 10} y={cy + 4} text-anchor="end" font-size="12" fill={$colours.ink}
					>{label(row.frame)}</text
				>
				{#if row.share !== null && row.low !== null && row.high !== null}
					<line
						x1={x(row.low)}
						x2={x(row.high)}
						y1={cy}
						y2={cy}
						stroke={$colours.rule}
						stroke-width="1.4"
					/>
					<line
						x1={x(row.low)}
						x2={x(row.low)}
						y1={cy - 4}
						y2={cy + 4}
						stroke={$colours.rule}
						stroke-width="1"
					/>
					<line
						x1={x(row.high)}
						x2={x(row.high)}
						y1={cy - 4}
						y2={cy + 4}
						stroke={$colours.rule}
						stroke-width="1"
					/>
				{/if}
				<!-- The corpus share: an open dot, and a taller rule through it where the
			     slice's interval does not reach it. -->
				{#if outside(row)}
					<line
						x1={x(row.overall)}
						x2={x(row.overall)}
						y1={cy - 8}
						y2={cy + 8}
						stroke={$colours.ink}
						stroke-width="1"
					/>
				{/if}
				<circle
					cx={x(row.overall)}
					{cy}
					r="4"
					fill={$colours.paper}
					stroke={$colours.inkFaint}
					stroke-width="1.2"
				/>
				{#if row.share !== null}
					<circle cx={x(row.share)} {cy} r="4.5" fill={$colours.ink} fill-opacity="0.85" />
				{/if}
			</g>
		{/each}
	</svg>
</div>

<style>
	.frames {
		display: block;
		max-width: 100%;
		height: auto;
	}
</style>
