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
	import { colours, sequential, tone, FONT } from '$lib/theme';
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

	/**
	 * Geometry measured, not scaled.
	 *
	 * The grid used to be drawn at a fixed 1,220 user units and left to a
	 * `viewBox` to fit whatever column it landed in. On a desk that scaled up
	 * and was fine. On a phone it scaled to 342px — a factor of 0.28 — and took
	 * every label down with it: the year, the month initial and the key all
	 * rendered at **2.52 CSS pixels**, and a cell at 26.9 by 4.5. The figure was
	 * not small there, it was unreadable, and the only legible form of it was a
	 * table inside a closed disclosure that does not say so.
	 *
	 * So the cell width follows the column instead of the column following the
	 * cell. The drawing is built to the width it will be given, which keeps the
	 * scale at 1 and lets the type be stated in the size it is actually read at
	 * — the same 12px the rest of the site's chart labels use, where this drew
	 * 9 and rendered 2.5. The cell keeps its height: 79 rows at 16 is a
	 * 1,400px column of months, and that is a scroll, not a wall.
	 */
	const HEADER = 18;
	const CELL_H = 16;
	const GAP = 2;
	/** The size the drawing is built at before anything has been measured. */
	const ASSUMED = 1220;

	let frame = $state<HTMLDivElement | null>(null);
	let available = $state(ASSUMED);

	$effect(() => {
		const node = frame;
		if (!node) return;
		const observer = new ResizeObserver(([entry]) => {
			const measured = Math.round(entry.contentRect.width);
			// A zero arrives while the plate is still collapsed, and building the
			// grid to it would divide the cell into nothing.
			if (measured > 0) available = measured;
		});
		observer.observe(node);
		return () => observer.disconnect();
	});

	/* Room for a four-digit year at 12px, and no more than that. */
	const GUTTER = $derived(available < 520 ? 38 : 44);
	/* Wide enough for a month initial at 12px, narrow enough that twelve of them
	   fit a 320px window without the drawing being scaled down again; capped so
	   the calendar does not become a field of stripes on a desk. */
	const CELL_W = $derived(
		Math.max(17, Math.min(96, Math.floor((available - GUTTER) / plan.months.length) - GAP))
	);

	const width = $derived(GUTTER + plan.months.length * (CELL_W + GAP));
	const rows = $derived(plan.years.length);
	/* The key carries four things: the ramp, what it measures, and the two
	   refusals. The refusals always take a row of their own — pinned to the
	   right of a wide drawing they sat under the floating back-to-top control —
	   and below about 420 units the unit label drops to a row of its own too. */
	const stacked = $derived(width < 420);
	const LEGEND = $derived(stacked ? 92 : 80);
	const height = $derived(HEADER + rows * (CELL_H + GAP) + LEGEND);

	const x = $derived((month: number) => GUTTER + (month - 1) * (CELL_W + GAP));
	const y = $derived((year: number) => HEADER + plan.years.indexOf(year) * (CELL_H + GAP));

	const initial = (month: number) =>
		['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'][month - 1] ?? '';

	/* Ten stops rather than a gradient element: a `<linearGradient>` referenced by
	   id survives serialisation but not every SVG consumer, and the legend is a
	   key rather than a figure. */
	const STOPS = 10;
	/** One swatch of the ramp; ten of them make the key. */
	const SWATCH = 16;
	/** The mark at the centre of a month the Council did not speak in. */
	const DOT = 4;

	const fillOf = (cell: Cell) => (cell.state === 'drawn' ? ramp(cell.tone) : $colours.paper);

	let element = $state<SVGSVGElement | null>(null);

	/** The live element, for `Download.svelte`. The same one that is on screen. */
	export function svg(): SVGSVGElement | null {
		return element;
	}
</script>

<!-- The frame is what is measured. Measuring the drawing itself would be a
     loop: its width is built from the width it is given. -->
<div class="frame" bind:this={frame}>
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
				font-size="12"
				fill={$colours.inkFaint}>{initial(month)}</text
			>
		{/each}

		{#each plan.years as year (year)}
			<text
				x={GUTTER - 8}
				y={y(year) + CELL_H - 4}
				text-anchor="end"
				font-family={FONT}
				font-size="12"
				fill={$colours.inkFaint}>{year}</text
			>
		{/each}

		{#each plan.cells as cell (cell.period)}
			<rect
				x={x(cell.month)}
				y={y(cell.year)}
				width={CELL_W}
				height={CELL_H}
				fill={cell.state === 'withheld' ? `url(#${hatchId})` : fillOf(cell)}
				stroke={$colours.ruleSoft}
				stroke-width="0.75"
			>
				<title>{label(cell)}</title>
			</rect>
			<!-- A month in which the Council held no speeches at all. An empty
			     cell with a mark at its centre, because the two things it must not
			     be confused with are a hatched cell (a rate we decline to publish)
			     and a pale drawn cell (a rate that is nearly zero). A mark is
			     neither, and it survives greyscale and print as a hue would not. -->
			{#if cell.state === 'unobserved'}
				<rect
					x={x(cell.month) + CELL_W / 2 - DOT / 2}
					y={y(cell.year) + CELL_H / 2 - DOT / 2}
					width={DOT}
					height={DOT}
					fill={$colours.inkFaint}
					pointer-events="none"
				/>
			{/if}
		{/each}

		<!-- The key. Inside the picture rather than beside it, so a downloaded file
	     still says what its colours mean. -->
		<!-- Swatches at even steps of the *value*, so the key is a correct lookup
	     table whatever transform the ramp applies. That the colours change fast
	     at the left and slowly at the right is the transform, visible. -->
		{#snippet key(left: number, base: number)}
			{#each Array.from({ length: STOPS }, (_, i) => i) as index (index)}
				<rect
					x={left + index * SWATCH}
					y={base}
					width={SWATCH}
					height="10"
					fill={ramp(tone((index + 0.5) / STOPS))}
					stroke={$colours.ruleSoft}
					stroke-width="0.5"
				/>
			{/each}
			<text x={left} y={base + 23} font-family={FONT} font-size="11" fill={$colours.inkFaint}
				>0</text
			>
			<text
				x={left + (STOPS * SWATCH) / 2}
				y={base + 23}
				text-anchor="middle"
				font-family={FONT}
				font-size="11"
				fill={$colours.inkFaint}>{format(plan.high / 2)}</text
			>
			<text
				x={left + STOPS * SWATCH}
				y={base + 23}
				text-anchor="end"
				font-family={FONT}
				font-size="11"
				fill={$colours.inkFaint}>{format(plan.high)}</text
			>
			<!-- Beside the ramp where there is room for it, under the ramp where
		     there is not. -->
			<text
				x={stacked ? left : left + STOPS * SWATCH + 14}
				y={stacked ? base + 42 : base + 9}
				font-family={FONT}
				font-size="12"
				fill={$colours.inkFaint}>{unit}</text
			>

			<!-- Two refusals, two keys, on a row of their own. The hatch is a rate
		     this figure declines to publish; the mark is a month in which the
		     Council said nothing at all. They were drawn alike and counted as
		     one, and the count named only the first of them. -->
			{@const refusals = stacked ? base + 58 : base + 46}
			<rect
				x={left}
				y={refusals}
				width={SWATCH}
				height="10"
				fill="url(#{hatchId})"
				stroke={$colours.ruleSoft}
				stroke-width="0.5"
			/>
			<text
				x={left + SWATCH + 6}
				y={refusals + 9}
				font-family={FONT}
				font-size="12"
				fill={$colours.inkFaint}>no rate ({plan.withheld})</text
			>

			<rect
				x={left + 150}
				y={refusals}
				width={SWATCH}
				height="10"
				fill={$colours.paper}
				stroke={$colours.ruleSoft}
				stroke-width="0.5"
			/>
			<rect
				x={left + 150 + SWATCH / 2 - DOT / 2}
				y={refusals + 5 - DOT / 2}
				width={DOT}
				height={DOT}
				fill={$colours.inkFaint}
			/>
			<text
				x={left + 150 + SWATCH + 6}
				y={refusals + 9}
				font-family={FONT}
				font-size="12"
				fill={$colours.inkFaint}>no sitting ({plan.unobserved})</text
			>
		{/snippet}

		{@render key(GUTTER, HEADER + rows * (CELL_H + GAP) + 12)}
	</svg>
</div>

<style>
	/* The calendar takes every column the plate has: the review of 14 September
	   2026 found a 46rem cap here leaving it 59% of its own width. */
	.frame {
		width: 100%;
	}

	.grid {
		width: 100%;
		height: auto;
		display: block;
	}
</style>
