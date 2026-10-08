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
	 * few hundred bytes of markup that prints. The download is a second drawing
	 * of the same rows with the colours resolved, in `$lib/multiples`.
	 */
	import { multiplesKey, multiplesPoints, multiplesSvg } from './multiples';
	import { FONT, palette } from './theme';

	interface Row {
		/** Shown at the left in ink, behind a square of the series' colour. */
		name: string;
		values: number[];
		/** Any CSS colour — normally `var(--reg-…)`. */
		colour: string;
		/** The one number the per-row scaling throws away. */
		summary: string;
		/**
		 * The register the colour stands for, named in the key above the rows.
		 * Without it a reader was told that colour groups related terms and was
		 * never told which group a colour was (review of 19 September 2026).
		 */
		register?: string;
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

	const ticks = $derived(events.map((e) => ({ x: x(e.index, periods.length), title: e.title })));
	const axis = $derived({
		first: periods[0],
		last: periods[periods.length - 1],
		mid: periods[Math.floor(periods.length / 2)]
	});
	const key = $derived(multiplesKey(rows));
	const ticksLabel = $derived(eventsLabel ?? `${ticks.length} reference dates`);

	/**
	 * A `var(--…)` resolved against the document, for the file.
	 *
	 * Custom properties compute with their own `var()` references substituted,
	 * so `--reg-core`, declared as `var(--ink)`, reads back as the ink itself.
	 */
	function literal(colour: string, style: CSSStyleDeclaration, fallback: string): string {
		const name = /^var\((--[\w-]+)\)$/.exec(colour.trim())?.[1];
		return name ? style.getPropertyValue(name).trim() || fallback : colour;
	}

	/**
	 * The figure as a file, for `Download.svelte`'s two image formats.
	 *
	 * Built fresh on every call rather than read off the page: the page's copy
	 * colours itself with the theme's custom properties, which a file opened
	 * anywhere else does not have. Detached, so its size is read from its own
	 * `width` and `height`, which is the path `Download.svelte` already takes
	 * for an element with no box.
	 */
	export function svg(): SVGSVGElement | null {
		if (typeof document === 'undefined' || !rows.length) return null;
		const style = getComputedStyle(document.documentElement);
		const p = palette();
		const resolved = rows.map((row) => ({ ...row, colour: literal(row.colour, style, p.ink) }));
		const markup = multiplesSvg({
			rows: resolved,
			periods,
			key: multiplesKey(resolved).map((entry) => ({
				label: entry.register,
				colour: entry.colour
			})),
			ticks: events,
			ticksLabel,
			colours: { ink: p.ink, faint: p.inkFaint, rule: p.ruleSoft },
			fontFamily: FONT
		});
		const parsed = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement;
		return parsed instanceof SVGSVGElement ? parsed : null;
	}
</script>

<!-- The key names each colour in words, a square before each word, so the
     words stay ink: the colour is the register the term sits on, and a reader
     told that colour groups related terms is owed the name of each group. -->
{#if key.length}
	<p class="key">
		{#each key as entry (entry.register)}
			<span class="entry"
				><span class="swatch" style:background={entry.colour}></span>{entry.register}</span
			>
		{/each}
	</p>
{/if}
<div class="multiples" role="img" aria-label={description}>
	{#each rows as row (row.name)}
		<div class="row">
			<div class="name">
				<span class="swatch" style:background={row.colour}></span>{row.name}
			</div>
			<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">
				<polyline
					points={multiplesPoints(row.values, W, H)}
					fill="none"
					stroke={row.colour}
					stroke-width="1.6"
					stroke-linejoin="round"
					vector-effect="non-scaling-stroke"
				/>
			</svg>
			<div class="summary">{row.summary}</div>
		</div>
	{/each}

	{#if ticks.length}
		<div class="row events">
			<div class="label">{ticksLabel}</div>
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
				<div class="scale">
					<span>{axis.first}</span><span>{axis.mid}</span><span>{axis.last}</span>
				</div>
			</div>
			<div></div>
		</div>
	{/if}
</div>

<style>
	.multiples {
		border-top: var(--hair) solid var(--ink);
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
		border-bottom-color: var(--ink);
	}

	.name {
		display: flex;
		align-items: baseline;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 600;
		color: var(--ink);
	}

	/* The site's one way of stating a colour key: a 0.625rem square before the
	   words. Painted by background, which a forced-colour mode drops; the
	   register then survives as the word in the key and in the table. */
	.swatch {
		width: 0.625rem;
		height: 0.625rem;
		flex: none;
	}

	.key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-1) var(--sp-4);
		margin: 0 0 var(--sp-2);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.entry {
		display: inline-flex;
		align-items: baseline;
		gap: var(--sp-2);
	}

	svg {
		width: 100%;
		height: 34px;
		display: block;
	}

	/* The grotesk, not the typewriter. These are a percentage and three years;
	   the mono on this site belongs to a meeting symbol, a script name or a
	   path, and the same percentages in this plate's own table were already set
	   in the text face — one plate, one number, two faces. The tabular figures
	   the `symbol` class used to bring are restored here, where they are what
	   was actually wanted. */
	.summary {
		text-align: right;
		color: var(--ink-3);
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums lining-nums;
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
		font-size: var(--step--1);
		font-weight: 600;
		color: var(--ink-3);
	}

	.scale {
		display: flex;
		justify-content: space-between;
		color: var(--ink-3);
		margin-top: var(--sp-1);
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums lining-nums;
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
