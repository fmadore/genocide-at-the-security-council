<script lang="ts">
	/**
	 * Six overlapping lines, drawn instead as six rows on a shared axis.
	 *
	 * A legend is a lookup table the reader has to hold in their head while
	 * looking somewhere else, and six lines crossing each other is a picture of
	 * the crossing rather than of any one series. Here each series has its own
	 * band, is named in place, and ends in its own number.
	 *
	 * Every row is scaled to its own maximum, so the shapes are comparable and
	 * the levels are not. That is a real trade and the caller is expected to say
	 * so in the figure's caveat; the number at the right of each row is there to
	 * give back the level the scaling took away.
	 *
	 * Plain SVG rather than a chart library: colour comes from the CSS custom
	 * properties, so the theme switch needs no redraw, and the whole thing is a
	 * few hundred bytes of markup that prints.
	 */
	interface Row {
		/** Shown at the left, in the series' own colour. */
		name: string;
		values: number[];
		/** Any CSS colour — normally `var(--reg-…)`. */
		colour: string;
		/** The one number the per-row scaling throws away. */
		summary: string;
	}

	/** A period carrying one or more reference dates, and what they were. */
	interface Tick {
		index: number;
		/** Read on hover and by a screen reader, e.g. "1994 — 6 April: …". */
		title: string;
	}

	interface Props {
		rows: Row[];
		/** One label per value, used for the axis ends and the accessible name. */
		periods: (string | number)[];
		/** Periods carrying a reference date, drawn as ticks on the shared axis. */
		events?: Tick[];
		/** Names what the ticks are, e.g. "35 reference dates". */
		eventsLabel?: string;
		/** Announced in place of the drawing. */
		description: string;
	}

	let { rows, periods, events = [], eventsLabel, description }: Props = $props();

	const W = 600;
	const H = 34;

	/** x of the i-th of n points, edge to edge. */
	const x = (i: number, n: number) => (n < 2 ? 0 : (i / (n - 1)) * W);

	function path(values: number[]): string {
		const top = Math.max(...values, 0);
		// A flat-zero row would divide by zero; draw it on the floor instead.
		const scale = top > 0 ? top : 1;
		return values
			.map(
				(v, i) => `${x(i, values.length).toFixed(1)},${(H - (v / scale) * (H - 4) - 2).toFixed(1)}`
			)
			.join(' ');
	}

	const ticks = $derived(events.map((e) => ({ x: x(e.index, periods.length), title: e.title })));
	const axis = $derived({
		first: periods[0],
		last: periods[periods.length - 1],
		mid: periods[Math.floor(periods.length / 2)]
	});
</script>

<div class="multiples" role="img" aria-label={description}>
	{#each rows as row (row.name)}
		<div class="row">
			<div class="name" style:color={row.colour}>{row.name}</div>
			<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">
				<polyline
					points={path(row.values)}
					fill="none"
					stroke={row.colour}
					stroke-width="1.6"
					stroke-linejoin="round"
					vector-effect="non-scaling-stroke"
				/>
			</svg>
			<div class="summary symbol">{row.summary}</div>
		</div>
	{/each}

	{#if ticks.length}
		<div class="row events">
			<div class="label">{eventsLabel ?? `${ticks.length} reference dates`}</div>
			<div class="rail">
				<svg viewBox="0 0 {W} 14" preserveAspectRatio="none">
					{#each ticks as tick, i (i)}
						<!-- The hairline is what you see; the transparent line behind it is
						     what you can actually hit with a pointer. -->
						<g class="tick">
							<title>{tick.title}</title>
							<line
								x1={tick.x}
								y1="0"
								x2={tick.x}
								y2="14"
								stroke="transparent"
								stroke-width="8"
								vector-effect="non-scaling-stroke"
							/>
							<line
								x1={tick.x}
								y1="0"
								x2={tick.x}
								y2="14"
								stroke="currentColor"
								stroke-width="1"
								vector-effect="non-scaling-stroke"
							/>
						</g>
					{/each}
				</svg>
				<div class="scale symbol">
					<span>{axis.first}</span><span>{axis.mid}</span><span>{axis.last}</span>
				</div>
			</div>
			<div></div>
		</div>
	{/if}
</div>

<style>
	.multiples {
		border-top: var(--hair) solid var(--rule-strong);
	}

	.row {
		display: grid;
		grid-template-columns: 9rem minmax(0, 1fr) 4.5rem;
		align-items: center;
		gap: var(--sp-4);
		padding: var(--sp-2) 0;
		border-bottom: var(--hair) solid var(--rule);
	}

	.row:last-of-type {
		border-bottom-color: var(--rule-strong);
	}

	.name {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 600;
	}

	svg {
		width: 100%;
		height: 34px;
		display: block;
	}

	.summary {
		text-align: right;
		color: var(--ink-3);
	}

	/* The reference dates are an annotation on the shared axis, not a series. */
	.events {
		border-bottom: 0;
		align-items: start;
		color: var(--ink-3);
	}

	.events svg {
		height: 14px;
	}

	.tick:hover {
		color: var(--ink);
	}

	.events .label {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	.scale {
		display: flex;
		justify-content: space-between;
		color: var(--ink-3);
		margin-top: var(--sp-1);
	}

	@media (max-width: 40rem) {
		.row {
			grid-template-columns: minmax(0, 1fr) 4.5rem;
			gap: var(--sp-2);
		}

		.name,
		.events .label {
			grid-column: 1 / -1;
		}
	}
</style>
