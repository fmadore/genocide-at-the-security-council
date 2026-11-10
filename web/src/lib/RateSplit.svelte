<script lang="ts">
	/**
	 * The two-rate split, drawn: for each unit, the earlier and later rates as
	 * steps over the whole span with their 95% intervals as bands, the year the
	 * search chose, and each year's own rate as a faint dot underneath, so a
	 * gradual rise that the step summarises is there to be seen. A split that
	 * does not clear the corrected threshold is drawn dashed and in faint ink,
	 * never as a finding. Decisions are in `#lib/ratesplit`.
	 *
	 * Drawn with the palette's literal colours so the exported SVG is the one on
	 * screen in either theme.
	 */
	import { colours, FONT } from '#lib/theme.js';
	import {
		annualPoints,
		formatLevel,
		formatRate,
		isStep,
		rateCeiling,
		rateSteps,
		valueTicks,
		verdict,
		yearTicks
	} from '#lib/ratesplit.js';
	import type { RateStep } from '#lib/ratesplit.js';
	import type { AnnualSeries, ChangePoints } from '#lib/types.js';

	let { breaks, annual }: { breaks: ChangePoints; annual: AnnualSeries | null } = $props();

	const rows = $derived(rateSteps(breaks, annual?.periods ?? []));
	const steps = $derived(rows.filter(isStep));

	let width = $state(0);
	let element = $state<SVGSVGElement | null>(null);
	const W = $derived(Math.max(280, width || 960));
	const narrow = $derived(W < 560);

	const PANEL = 168;
	const HEAD = 26;
	const LEFT = 46;
	const RIGHT = 10;
	const BOTTOM = 24;
	const plotHeight = PANEL - HEAD - BOTTOM;
	const H = $derived(Math.max(1, steps.length) * PANEL);

	/** The drawing, for the plate's SVG and PNG downloads. */
	export function svg(): SVGSVGElement | null {
		return steps.length ? element : null;
	}

	const p = $derived($colours);

	function panel(step: RateStep, index: number) {
		const points = annualPoints(annual, step.unit);
		const ceiling = rateCeiling(
			step,
			points.map((point) => point.value)
		);
		const top = index * PANEL + HEAD;
		const x = (year: number) =>
			LEFT + ((year - step.start) / (step.end - step.start || 1)) * (W - LEFT - RIGHT);
		const y = (value: number) => top + plotHeight - (value / ceiling) * plotHeight;
		return { points, ceiling, top, x, y, ticks: valueTicks(ceiling) };
	}

	const axisLabel = (step: RateStep, value: number) =>
		step.unit === 'speech_rate' ? `${Number((value * 100).toPrecision(3))}%` : String(value);
</script>

{#if rows.length}
	<div class="ratesplit">
		{#if steps.length}
			<div class="plot" bind:clientWidth={width}>
				<svg
					bind:this={element}
					xmlns="http://www.w3.org/2000/svg"
					width={W}
					height={H}
					viewBox="0 0 {W} {H}"
					font-family={FONT}
					role="img"
					aria-label={steps
						.map(
							(step) =>
								`${step.label}: ${formatRate(step.unit, step.before.value)} before ${step.split}, ` +
								`${formatRate(step.unit, step.after.value)} from ${step.split}. ${verdict(step)}`
						)
						.join(' ')}
				>
					{#each steps as step, index (step.unit)}
						{@const g = panel(step, index)}
						{@const strong = step.accepted}
						{@const stroke = strong ? p.ink : p.inkFaint}
						{@const dash = strong ? undefined : '6 4'}
						{@const bottom = g.top + plotHeight}
						<g>
							<text x="0" y={index * PANEL + 14} font-size="13" font-weight="600" fill={p.ink}
								>{step.label}</text
							>
							<!-- value grid -->
							{#each g.ticks as value (value)}
								<line
									x1={LEFT}
									x2={W - RIGHT}
									y1={g.y(value)}
									y2={g.y(value)}
									stroke={value === 0 ? p.ink : p.ruleSoft}
								/>
								<text
									x={LEFT - 6}
									y={g.y(value) + 4}
									font-size="11"
									text-anchor="end"
									fill={p.inkSoft}>{axisLabel(step, value)}</text
								>
							{/each}
							<!-- years -->
							{#each yearTicks(step.start, step.end, narrow ? 20 : 10) as year (year)}
								<text
									x={g.x(year)}
									y={bottom + 16}
									font-size="11"
									text-anchor="middle"
									fill={p.inkSoft}>{year}</text
								>
								<line x1={g.x(year)} x2={g.x(year)} y1={bottom} y2={bottom + 4} stroke={p.ink} />
							{/each}
							<!-- each year's own rate, faint; a withheld year is left undrawn -->
							{#each g.points as point (point.year)}
								{#if point.value !== null && point.value <= g.ceiling}
									<circle
										cx={g.x(point.year + 0.5)}
										cy={g.y(point.value)}
										r="2"
										fill={p.inkFaint}
										fill-opacity="0.6"
									/>
								{/if}
							{/each}
							<!-- 95% intervals of the two rates -->
							<rect
								x={g.x(step.start)}
								width={g.x(step.split) - g.x(step.start)}
								y={g.y(step.before.high)}
								height={Math.max(1, g.y(step.before.low) - g.y(step.before.high))}
								fill={p.ink}
								fill-opacity={strong ? 0.16 : 0.07}
							/>
							<rect
								x={g.x(step.split)}
								width={g.x(step.end) - g.x(step.split)}
								y={g.y(step.after.high)}
								height={Math.max(1, g.y(step.after.low) - g.y(step.after.high))}
								fill={p.ink}
								fill-opacity={strong ? 0.16 : 0.07}
							/>
							<!-- the split year -->
							<line
								x1={g.x(step.split)}
								x2={g.x(step.split)}
								y1={g.top - 4}
								y2={bottom}
								stroke={p.inkFaint}
								stroke-dasharray="3 3"
							/>
							<text
								x={g.x(step.split) - 5}
								y={g.top + 6}
								font-size="11"
								font-weight="600"
								text-anchor="end"
								fill={p.inkSoft}>split {step.split}</text
							>
							<!-- the two rates as one step -->
							<path
								d="M{g.x(step.start)},{g.y(step.before.value)} H{g.x(step.split)} V{g.y(
									step.after.value
								)} H{g.x(step.end)}"
								fill="none"
								{stroke}
								stroke-width="2.5"
								stroke-dasharray={dash}
							/>
							<text
								x={g.x(step.start) + 6}
								y={g.y(step.before.high) - 6}
								font-size="12"
								font-weight="600"
								fill={stroke}
								stroke={p.paper}
								stroke-width="3"
								paint-order="stroke">{formatLevel(step.unit, step.before)}</text
							>
							<text
								x={g.x(step.end) - 6}
								y={g.y(step.after.high) - 6}
								font-size="12"
								font-weight="600"
								text-anchor="end"
								fill={stroke}
								stroke={p.paper}
								stroke-width="3"
								paint-order="stroke">{formatLevel(step.unit, step.after)}</text
							>
						</g>
					{/each}
				</svg>
			</div>
		{/if}
		<ul class="verdicts">
			{#each rows as row (row.unit)}
				<li>
					<span class="unit">{row.label}.</span>
					{#if isStep(row)}
						{verdict(row)}
						{#if !row.accepted}Drawn dashed: a best split, not a finding.{/if}
					{:else}
						No split improves on one steady rate.
					{/if}
				</li>
			{/each}
		</ul>
		<p class="warning">
			Steps are the two rates, bands their 95% intervals, dots each year's own rate. A best split
			always exists, and a gradual rise also produces one; the intervals assume the split fell where
			the search put it.
		</p>
	</div>
{/if}

<style>
	.ratesplit {
		margin-bottom: var(--sp-5);
	}

	.plot {
		width: 100%;
		min-width: 0;
	}

	svg {
		display: block;
	}

	.verdicts {
		margin: var(--sp-3) 0 0;
		padding: 0;
		list-style: none;
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.verdicts li {
		margin-bottom: var(--sp-1);
	}

	.unit {
		font-weight: 600;
		color: var(--ink);
	}

	.warning {
		margin: var(--sp-2) 0 0;
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}
</style>
