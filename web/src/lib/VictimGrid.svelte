<script lang="ts">
	/**
	 * A count grid for the victim figures: rows down the side, columns across,
	 * each cell tinted on the amber ramp the usage matrix uses.
	 *
	 * A table rather than a chart, as the matrix is: the numbers are the figure,
	 * a screen reader reads it as the table it is, and every cell keeps its count
	 * in print. `#lib/victims` decides the rows, the columns and the cap; this
	 * component only draws them. The rows that name no particular people sit
	 * under a rule, so they are never read as one more people in the ranking.
	 */
	import ScrollRegion from '#lib/ScrollRegion.svelte';
	import { count } from '#lib/format.js';
	import { tone } from '#lib/theme.js';
	import type { GridPlan } from '#lib/victims.js';

	interface Props {
		plan: GridPlan;
		/** Names the rows, for the corner and a screen reader. */
		rowName: string;
		/** Names the ramp, e.g. "occurrences". */
		unit: string;
		/** Announced in place of the table. */
		description: string;
		/** Column headings stand on end when there are many and they are long. */
		upright?: boolean;
	}

	let { plan, rowName, unit, description, upright = false }: Props = $props();

	const fill = (value: number) =>
		plan.high > 0 && value > 0 ? `${(tone(value / plan.high) * 32).toFixed(1)}%` : '0%';
</script>

<ScrollRegion label={description} tall>
	<table class:upright>
		<caption class="sr-only">{description}</caption>
		<thead>
			<tr>
				<th class="corner" scope="col">{rowName}</th>
				{#each plan.columns as column (column.key)}
					<th scope="col" title={column.label}><span>{column.label}</span></th>
				{/each}
				<th scope="col" class="total">All</th>
			</tr>
		</thead>
		<tbody>
			{#each plan.rows as row, r (row.key)}
				<tr class:rule={r === plan.ruleAt}>
					<th scope="row" class:loose={row.unspecified}>{row.label}</th>
					{#each row.cells as value, c (plan.columns[c]!.key)}
						<td
							class:drawn={value > 0}
							style:--fill={fill(value)}
							title="{row.label}, {plan.columns[c]!.label}: {count(value)} {unit}"
							>{value > 0 ? count(value) : ''}</td
						>
					{/each}
					<td class="total">{count(row.total)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</ScrollRegion>

<style>
	/* The full width of the plate, as every figure on the site takes it: the
	   count columns share what the row names leave. */
	table {
		width: 100%;
		border-collapse: collapse;
		font-family: var(--sans);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums lining-nums;
	}

	th,
	td {
		padding: 0;
		font-weight: 400;
	}

	thead th {
		position: sticky;
		top: 0;
		z-index: 1;
		background: var(--paper);
		padding: 0 0 var(--sp-1);
		vertical-align: bottom;
		color: var(--ink-2);
		text-align: center;
	}

	/* Long column names stand on end, read bottom to top, as the matrix's do. */
	table.upright thead th:not(.corner, .total) span {
		display: inline-block;
		writing-mode: vertical-rl;
		transform: rotate(180deg);
		max-height: 13rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		text-align: left;
	}

	.corner {
		left: 0;
		z-index: 2;
		text-align: left;
		color: var(--ink-3);
	}

	tbody th {
		position: sticky;
		left: 0;
		z-index: 1;
		min-width: 12rem;
		max-width: 16rem;
		padding: 0 var(--sp-2) 0 0;
		background: var(--paper);
		text-align: left;
		color: var(--ink);
	}

	/* The groups that name no particular people: the same row, in quieter ink. */
	tbody th.loose {
		color: var(--ink-3);
		font-style: italic;
	}

	tr.rule > * {
		border-top: var(--hair) solid var(--ink);
		padding-top: var(--sp-1);
	}

	td {
		min-width: 2.8rem;
		height: 1.5rem;
		border: var(--hair) solid var(--rule);
		text-align: center;
		color: var(--ink);
	}

	td.drawn {
		background: color-mix(in oklab, var(--reg-accountability) var(--fill), transparent);
	}

	td.total,
	th.total {
		border: none;
		padding-left: var(--sp-2);
		text-align: right;
		color: var(--ink-3);
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
</style>
