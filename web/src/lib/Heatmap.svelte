<script lang="ts">
	/**
	 * A year x month grid drawn in SVG, from the table it depicts.
	 *
	 * This component decides nothing. Which cells may be drawn, what the top of
	 * the ramp is, and why 53 of them carry no number is settled in `$lib/heatmap`
	 * by the same call that feeds the table below the figure.
	 *
	 * Three things about the drawing itself.
	 *
	 * **A withheld cell is hatched, not left blank.** White is the colour a zero
	 * has. The hatch is drawn in the same hairline as the rules elsewhere on the
	 * site, so a month the Council barely sat in reads as *absent evidence* at a
	 * glance and as its own sentence on hover — and it survives being printed in
	 * greyscale, which a paler fill would not.
	 *
	 * **Every cell keeps its outline.** A drawn cell at a rate of zero is nearly
	 * the colour of the page, which is the right encoding for a month in which
	 * nobody said the word; the outline is what keeps it a cell rather than a
	 * hole, and what stops it being confused with the hatch beside it.
	 *
	 * **Fills are attributes, not classes.** The exported SVG carries none of this
	 * site's stylesheet, so a ramp expressed in CSS would leave a downloaded
	 * figure black. The colours are resolved from the design tokens through
	 * `palette()` and written inline, which also means the grid follows the
	 * light/dark switch instead of ignoring it.
	 *
	 * The grid is one image rather than 384 focusable elements: a keyboard reader
	 * given a tab stop per cell would have to pass through a year of them to
	 * leave. What is navigable is the table under the figure, which carries the
	 * same numbers and the links.
	 */
	import { colours, sequential, FONT, MONO } from '$lib/theme';
	import { tone } from '$lib/heatmap';
	import type { Cell, HeatmapPlan } from '$lib/heatmap';

	interface Props {
		plan: HeatmapPlan;
		/** The cell's own numbers, as a hover title and for the table's benefit. */
		label: (cell: Cell) => string;
		/** Names the ramp, e.g. "share of the month's speeches". */
		unit: string;
		/** A value on the ramp, written the way the figure writes its numbers. */
		format: (value: number) => string;
		/** Announced in place of the drawing. */
		description: string;
	}

	let { plan, label, unit, format, description }: Props = $props();

	const ramp = $derived(sequential($colours));

	const captionId = $props.id();
	const hatchId = `hatch-${captionId}`;

	/* Geometry in user units; the SVG scales to its column through the viewBox. */
	const GUTTER = 44;
	const HEADER = 18;
	const CELL_W = 42;
	const CELL_H = 15;
	const GAP = 1.5;
	const LEGEND = 40;

	const width = $derived(GUTTER + plan.months.length * (CELL_W + GAP));
	const rows = $derived(plan.years.length);
	const height = $derived(HEADER + rows * (CELL_H + GAP) + LEGEND);

	const x = (month: number) => GUTTER + (month - 1) * (CELL_W + GAP);
	const y = $derived((year: number) => HEADER + plan.years.indexOf(year) * (CELL_H + GAP));

	const initial = (month: number) =>
		['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'][month - 1] ?? '';

	/* Ten stops rather than a gradient element: a `<linearGradient>` referenced by
	   id survives serialisation but not every SVG consumer, and the legend is a
	   key rather than a figure. */
	const STOPS = 10;

	let element = $state<SVGSVGElement | null>(null);

	/** The live element, for `Download.svelte`. The same one that is on screen. */
	export function svg(): SVGSVGElement | null {
		return element;
	}
</script>

<svg
	bind:this={element}
	class="grid"
	{width}
	{height}
	viewBox="0 0 {width} {height}"
	role="img"
	aria-labelledby={captionId}
>
	<title id={captionId}>{description}</title>
	<defs>
		<pattern
			id={hatchId}
			width="4"
			height="4"
			patternUnits="userSpaceOnUse"
			patternTransform="rotate(45)"
		>
			<line x1="0" y1="0" x2="0" y2="4" stroke={$colours.rule} stroke-width="1.4" />
		</pattern>
	</defs>

	{#each plan.months as month (month)}
		<text
			x={x(month) + CELL_W / 2}
			y={HEADER - 6}
			text-anchor="middle"
			font-family={FONT}
			font-size="9"
			fill={$colours.inkFaint}>{initial(month)}</text
		>
	{/each}

	{#each plan.years as year (year)}
		<text
			x={GUTTER - 8}
			y={y(year) + CELL_H - 4}
			text-anchor="end"
			font-family={MONO}
			font-size="9"
			fill={$colours.inkFaint}>{year}</text
		>
	{/each}

	{#each plan.cells as cell (cell.period)}
		<rect
			x={x(cell.month)}
			y={y(cell.year)}
			width={CELL_W}
			height={CELL_H}
			fill={cell.state === 'drawn' ? ramp(cell.tone) : `url(#${hatchId})`}
			stroke={$colours.ruleSoft}
			stroke-width="0.75"
		>
			<title>{label(cell)}</title>
		</rect>
	{/each}

	<!-- The key. Inside the picture rather than beside it, so a downloaded file
	     still says what its colours mean. -->
	<!-- Swatches at even steps of the *value*, so the key is a correct lookup
	     table whatever transform the ramp applies. That the colours change fast
	     at the left and slowly at the right is the transform, visible. -->
	{#snippet key(left: number, base: number)}
		{#each Array.from({ length: STOPS }, (_, i) => i) as index (index)}
			<rect
				x={left + index * 14}
				y={base}
				width="14"
				height="9"
				fill={ramp(tone((index + 0.5) / STOPS))}
				stroke={$colours.ruleSoft}
				stroke-width="0.5"
			/>
		{/each}
		<text x={left} y={base + 20} font-family={FONT} font-size="8.5" fill={$colours.inkFaint}>0</text
		>
		<text
			x={left + (STOPS * 14) / 2}
			y={base + 20}
			text-anchor="middle"
			font-family={FONT}
			font-size="8.5"
			fill={$colours.inkFaint}>{format(plan.high / 2)}</text
		>
		<text
			x={left + STOPS * 14}
			y={base + 20}
			text-anchor="end"
			font-family={FONT}
			font-size="8.5"
			fill={$colours.inkFaint}>{format(plan.high)}</text
		>
		<text
			x={left + STOPS * 14 + 14}
			y={base + 8}
			font-family={FONT}
			font-size="9"
			fill={$colours.inkFaint}>{unit}</text
		>
	{/snippet}

	{@render key(GUTTER, HEADER + rows * (CELL_H + GAP) + 12)}

	<rect
		x={width - 108}
		y={HEADER + rows * (CELL_H + GAP) + 12}
		width="14"
		height="9"
		fill="url(#{hatchId})"
		stroke={$colours.ruleSoft}
		stroke-width="0.5"
	/>
	<text
		x={width - 90}
		y={HEADER + rows * (CELL_H + GAP) + 20}
		font-family={FONT}
		font-size="9"
		fill={$colours.inkFaint}>withheld ({plan.withheld})</text
	>
</svg>

<style>
	.grid {
		width: 100%;
		max-width: 46rem;
		height: auto;
		display: block;
	}
</style>
