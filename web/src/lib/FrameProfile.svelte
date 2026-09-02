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
	 * Greys and the accent only — the register hues mean "register" on this site
	 * and a frame is not one.
	 */
	import { colours } from './theme';
	import { count, percent } from './format';
	import { outside, position, track } from './nodeframes';
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

	const ROW = 22;
	const LABEL = 168;
	const WIDTH = 720;
	const TOP = 30;
	const RIGHT = 16;
	const trackWidth = WIDTH - LABEL - RIGHT;

	const scale = $derived(track(rows));
	const height = $derived(TOP + rows.length * ROW + 10);
	const x = (share: number) => LABEL + position(share, scale) * trackWidth;

	const label = (frame: string) => frame.replaceAll('_', ' ');

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
					stroke={$colours.accent}
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

<style>
	.frames {
		display: block;
		max-width: 100%;
		height: auto;
	}
</style>
