<script lang="ts">
	/**
	 * How a referent spread through the Council, drawn as the step it is.
	 *
	 * This component decides nothing. Which referent is on screen, which curves
	 * are worth their ink, where every step falls and what the years on the axis
	 * are, are all settled in `$lib/usage` by the same call that fills the
	 * chronology underneath and the CSV beside it.
	 *
	 * Three things about the drawing itself.
	 *
	 * **Steps, never a slope.** A cumulative count does not pass through the
	 * values between two events: nothing joined the curve in the eight years
	 * between one delegation and the next, and a line drawn diagonally across that
	 * gap says it did. The rise is vertical and the wait is flat.
	 *
	 * **Plain SVG, so the colour is the theme's.** The same choice
	 * `SmallMultiples.svelte` made and for the same reason: the strokes are CSS
	 * custom properties, so the theme switch needs no redraw, and the whole figure
	 * is a few hundred bytes of markup that prints. The three curves are told
	 * apart by weight and dash as well as by hue — assertion solid and coloured,
	 * refusal dashed in ink, the envelope a faint hairline — because a reader who
	 * cannot separate two hues still has to be able to separate two readings.
	 *
	 * **The table underneath is the accessible figure.** The plot carries one
	 * label describing what it shows, as every chart on this site does; the
	 * chronology beneath it is the same events as text, in order, with a way into
	 * the record for each. Nothing here is reachable by keyboard because nothing
	 * here is a control — the picker above the figure is.
	 */
	import { DIFFUSION_BOX } from './usage';
	import type { DiffusionPlan, DiffusionPoint, DiffusionSeries } from './usage';

	interface Props {
		plan: DiffusionPlan;
		/** The full sentence one event makes, for its tooltip. */
		label: (point: DiffusionPoint, series: DiffusionSeries) => string;
		/** Announced in place of the drawing. */
		description: string;
	}

	let { plan, label, description }: Props = $props();
</script>

<div class="key">
	{#each plan.drawn as series (series.milestone)}
		<span class="swatch" data-milestone={series.milestone}>
			<i></i>{series.label}<span class="n">{series.total}</span>
		</span>
	{/each}
</div>

<div class="plot" role="img" aria-label={description}>
	<span class="high symbol">{plan.high}</span>
	<span class="zero symbol">0</span>

	<!-- Hidden from assistive technology, as `SmallMultiples.svelte` hides its
	     own: the label on the box around it is the one description of the
	     drawing, and an unlabelled `<svg>` is a second image in the tree. -->
	<svg viewBox="0 0 {DIFFUSION_BOX.width} {DIFFUSION_BOX.height}" aria-hidden="true">
		{#each plan.ticks as tick (tick.label)}
			<line
				class="grid"
				x1={tick.x}
				x2={tick.x}
				y1={DIFFUSION_BOX.top}
				y2={DIFFUSION_BOX.bottom}
				vector-effect="non-scaling-stroke"
			/>
		{/each}
		<line
			class="base"
			x1={DIFFUSION_BOX.left}
			x2={DIFFUSION_BOX.right}
			y1={DIFFUSION_BOX.bottom}
			y2={DIFFUSION_BOX.bottom}
			vector-effect="non-scaling-stroke"
		/>

		{#each plan.drawn as series (series.milestone)}
			<path
				class="curve"
				data-milestone={series.milestone}
				d={series.path}
				fill="none"
				stroke-linejoin="miter"
				vector-effect="non-scaling-stroke"
			/>
		{/each}

		<!-- The steps themselves, one mark per delegation, after every curve so
		     that no line is drawn over a mark it belongs to. A curve with more
		     steps than it has room for is drawn without them; the plan decides. -->
		{#each plan.drawn as series (series.milestone)}
			{#if series.marker}
				{#each series.points as point (point.id)}
					<circle
						class="step"
						data-milestone={series.milestone}
						cx={point.x}
						cy={point.y}
						r={series.marker}
					>
						<title>{label(point, series)}</title>
					</circle>
				{/each}
			{/if}
		{/each}
	</svg>

	<div class="ticks symbol">
		{#each plan.ticks as tick (tick.label)}
			<span style:left="{tick.percent}%" data-anchor={tick.anchor}>{tick.label}</span>
		{/each}
	</div>
</div>

<style>
	/* ---- the key ----------------------------------------------------------- */

	.key {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-5);
		margin-bottom: var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
	}

	.swatch {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	/* The swatch is the stroke it stands for, dash and weight included, rather
	   than a filled block that would make three different lines look alike. */
	.swatch i {
		width: 1.6rem;
		border-top: 2px solid var(--ink-3);
	}

	.swatch .n {
		font-family: var(--mono);
		font-variant-numeric: tabular-nums;
		color: var(--ink-3);
	}

	/* ---- the plot ---------------------------------------------------------- */

	.plot {
		position: relative;
		padding-left: 2.4rem;
	}

	svg {
		width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}

	.grid {
		stroke: var(--rule);
		stroke-width: 1;
	}

	.base {
		stroke: var(--rule-strong);
		stroke-width: 1;
	}

	/* Three readings, told apart by weight and dash before hue. Assertion is the
	   question the figure is for and carries the data colour; refusal is the
	   counter-curve, in ink and dashed so it reads as the answer to the first;
	   the envelope of everyone who placed the word at all is a hairline, because
	   it is context rather than a finding. `--blue` appears nowhere: it belongs
	   to what a reader can act on, never to a datum. */
	.curve[data-milestone='asserts'],
	.swatch[data-milestone='asserts'] i {
		stroke: var(--reg-contentious);
		border-top-color: var(--reg-contentious);
		stroke-width: 2;
	}

	.curve[data-milestone='rejects_or_denies'],
	.swatch[data-milestone='rejects_or_denies'] i {
		stroke: var(--ink);
		border-top-color: var(--ink);
		border-top-style: dashed;
		stroke-width: 1.4;
		stroke-dasharray: 5 3;
	}

	.curve[data-milestone='mention'],
	.swatch[data-milestone='mention'] i {
		stroke: var(--ink-3);
		border-top-color: var(--ink-3);
		border-top-width: 1px;
		stroke-width: 1;
	}

	.step[data-milestone='asserts'] {
		fill: var(--reg-contentious);
	}

	.step[data-milestone='rejects_or_denies'] {
		fill: var(--ink);
	}

	.step[data-milestone='mention'] {
		fill: var(--ink-3);
	}

	/* The two ends of the vertical scale, printed rather than drawn as an axis:
	   the count is what the reader needs, and a second ruled edge is chrome. */
	.high,
	.zero {
		position: absolute;
		left: 0;
		width: 2.1rem;
		text-align: right;
		font-family: var(--mono);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums;
		color: var(--ink-3);
	}

	.high {
		top: 0;
	}

	.zero {
		bottom: 1.4rem;
	}

	.ticks {
		position: relative;
		height: 1.4rem;
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.ticks span {
		position: absolute;
		top: var(--sp-1);
		transform: translateX(-50%);
		white-space: nowrap;
	}

	/* A centred label at either end hangs off the figure, and on the right it
	   would push a scrollbar onto the figure body. The plan says which. */
	.ticks span[data-anchor='start'] {
		transform: none;
	}

	.ticks span[data-anchor='end'] {
		transform: translateX(-100%);
	}
</style>
