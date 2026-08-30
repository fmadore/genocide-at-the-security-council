<script lang="ts">
	/**
	 * Which genocide each delegation means, drawn as the table it is.
	 *
	 * This component decides nothing. Which speakers are rows, which referents
	 * are columns and in what order, which cells may be shaded and which are
	 * hatched because their denominator is too small, and where a key press moves
	 * the focus, are all settled in `$lib/usage` by the same call that feeds the
	 * download beside the figure.
	 *
	 * Three things about the drawing itself.
	 *
	 * **The table is the figure.** Not a picture with a table under it: the same
	 * decision `Standing.svelte` and `SpeakerKeyness.svelte` made, and for the
	 * same reason — one element carrying both the number and the shading cannot
	 * drift from a second rendering of itself, and every cell is then reachable,
	 * readable aloud, and selectable without a parallel affordance.
	 *
	 * **The whole matrix is one tab stop.** `Heatmap.svelte` refused a tab stop
	 * per cell because a keyboard reader given 384 of them has to pass a year of
	 * squares to leave, and left its table underneath as the navigable thing.
	 * Here the table *is* the figure, so the objection is answered the other way:
	 * every cell is a real button, exactly one is in the tab order at a time, and
	 * the arrow keys move between them. The headings are in that same grid,
	 * because they are controls too — a row heading selects a delegation on its
	 * own, a column heading a referent on its own.
	 *
	 * **The fill is capped well short of the token.** Shading runs to 32% of the
	 * amber, the ceiling `Standing.svelte` uses, because the number sits on top of
	 * it and has to stay readable against the fill in both themes. The colour is a
	 * second cue here, not the only one — which is what lets it be quiet.
	 */
	import { tone } from './theme';
	import { NAVIGATION_KEYS, stepFocus } from './usage';
	import type { Focus, MatrixCell, MatrixPlan } from './usage';
	import type { UsageActor, UsageReferent } from './types';

	interface Props {
		plan: MatrixPlan;
		/** The full sentence a cell makes, for its tooltip and its screen reader. */
		label: (cell: MatrixCell, actor: UsageActor, referent: UsageReferent) => string;
		/** A value in the unit in force, written the way the figure writes its numbers. */
		format: (value: number) => string;
		/** How a speaker is named in a row heading. */
		name: (actor: UsageActor) => string;
		/** Names the ramp, e.g. "occurrences" or "share of the delegation's own". */
		unit: string;
		/** Announced in place of the table. */
		description: string;
		/** Both empty releases the selection; the caller decides what that means. */
		onselect: (actor: string, referent: string) => void;
	}

	let { plan, label, format, name, unit, description, onselect }: Props = $props();

	let grid = $state<HTMLTableElement | null>(null);
	let wanted = $state<Focus>({ row: 0, column: 0 });

	/* Clamped against what the plan actually drew rather than stored clamped: a
	   change of ordering or of unit rebuilds the plan, and a stored coordinate
	   past its end would leave no button in the tab order at all — which is a
	   grid a keyboard cannot enter. Row -1 is the heading row, column -1 the
	   heading column. */
	const at = $derived<Focus>({
		row: Math.min(Math.max(wanted.row, -1), plan.rows.length - 1),
		column: Math.min(Math.max(wanted.column, -1), plan.columns.length - 1)
	});

	const isAt = (row: number, column: number) => at.row === row && at.column === column;

	function move(event: KeyboardEvent) {
		if (!NAVIGATION_KEYS.has(event.key)) return;
		// Claimed whether or not the focus moves: at the edge of the grid the
		// alternative is the page scrolling out from under the reader's cursor.
		event.preventDefault();
		const next = stepFocus(plan, at, event.key);
		wanted = next;
		grid
			?.querySelector<HTMLElement>(`[data-row='${next.row}'][data-col='${next.column}']`)
			?.focus();
	}

	/** A click positions the roving index too, so Tab returns where the eye is. */
	function pick(row: number, column: number, actor: string, referent: string) {
		wanted = { row, column };
		onselect(actor, referent);
	}

	/* Which of the cell's two figures is on screen. The plan settled the unit;
	   this only reads it, so the key and the cells cannot show different ones. */
	const value = (cell: MatrixCell) => (plan.unit === 'share' ? (cell.share ?? 0) : cell.count);
	const fill = (weight: number) => `${(weight * 32).toFixed(1)}%`;

	/* Ten stops of the same ramp the cells use, as the key. Small, and inside the
	   figure rather than beside it. Swatches at even steps of the *value*, so the
	   key stays a correct lookup table under the ramp's transform. */
	const STOPS = 10;
	const stops = Array.from({ length: STOPS }, (_, index) => (index + 0.5) / STOPS);
</script>

<div class="key">
	<span class="label">{unit}</span>
	<span class="ramp">
		<span class="zero">0</span>
		{#each stops as stop (stop)}
			<i style:--fill={fill(tone(stop))}></i>
		{/each}
		<span class="top">{plan.high > 0 ? format(plan.high) : ''}</span>
	</span>
	{#if plan.unit === 'share' && plan.disclosure.withheldRows}
		<span class="swatch">
			<i class="hatched"></i>share withheld ({plan.disclosure.withheldRows})
		</span>
	{/if}
	<span class="swatch"><i class="none"></i>never on this referent</span>
</div>

<div class="scroll">
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions (The grid owns the arrow keys on behalf of the buttons inside it; everything focusable here is a button.) -->
	<table bind:this={grid} onkeydown={move}>
		<caption class="sr-only">{description}</caption>
		<thead>
			<tr>
				<th class="corner" scope="col"><span class="sr-only">Delegation</span></th>
				{#each plan.columns as column, c (column.referent.id)}
					<th scope="col" class:grouped={column.grouped} class:rule={c === plan.groupedFrom}>
						<button
							type="button"
							class="head"
							data-row="-1"
							data-col={c}
							tabindex={isAt(-1, c) ? 0 : -1}
							aria-pressed={column.selected}
							title="{column.referent.label}{column.referent.years
								? ` (${column.referent.years})`
								: ''} — {column.drawn} occurrences in this table"
							onclick={() => pick(-1, c, '', column.referent.id)}
						>
							{column.referent.label}
						</button>
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each plan.rows as row, r (row.actor.country_org)}
				<tr class:selected={row.selected}>
					<th scope="row" class="who">
						<button
							type="button"
							class="head"
							data-row={r}
							data-col="-1"
							tabindex={isAt(r, -1) ? 0 : -1}
							aria-pressed={row.selected}
							title="{row.actor.country_org} — {row.actor.assigned} placed occurrences of {row.actor
								.eligible} eligible{row.actor.sufficient ? '' : '; shares withheld'}"
							onclick={() => pick(r, -1, row.actor.country_org, '')}
						>
							{name(row.actor)}
							<span class="n">{row.actor.assigned}</span>
						</button>
					</th>
					{#each row.cells as cell, c (cell.referent)}
						<td class:rule={c === plan.groupedFrom}>
							<button
								type="button"
								class="cell"
								data-row={r}
								data-col={c}
								data-state={cell.state}
								style:--fill={fill(cell.tone)}
								tabindex={isAt(r, c) ? 0 : -1}
								aria-pressed={cell.selected}
								class:selected={cell.selected}
								title={label(cell, row.actor, plan.columns[c].referent)}
								aria-label={label(cell, row.actor, plan.columns[c].referent)}
								onclick={() => pick(r, c, cell.actor, cell.referent)}
							>
								<span aria-hidden="true">{cell.state === 'drawn' ? format(value(cell)) : ''}</span>
							</button>
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<p class="hint">
	One tab stop for the whole table: the arrow keys move between cells and out into the headings,
	Home and End run to the ends of a row.
</p>

<style>
	/* ---- the key ---------------------------------------------------------- */

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

	.key .label {
		display: inline;
	}

	.ramp,
	.swatch {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
	}

	.ramp i,
	.swatch i {
		width: 1.1rem;
		height: 0.6rem;
		display: inline-block;
		border: var(--hair) solid var(--rule);
	}

	.ramp i {
		background: color-mix(in oklab, var(--reg-accountability) var(--fill), transparent);
	}

	.zero,
	.top {
		font-family: var(--mono);
		color: var(--ink-3);
	}

	/* The same hatch the month grid uses, for the same distinction: a withheld
	   figure is absent evidence, and white is the colour a measured zero has. */
	.hatched {
		background: repeating-linear-gradient(45deg, transparent 0 3px, var(--rule-strong) 3px 4px);
	}

	.none {
		background: none;
	}

	/* ---- the matrix -------------------------------------------------------- */

	/* Inside the figure, never the page: the body of `Figure.svelte` already
	   scrolls on its own axis, and a table that pushed the article sideways would
	   take the margin notes with it. */
	.scroll {
		overflow-x: auto;
		max-height: 34rem;
		overflow-y: auto;
	}

	table {
		border-collapse: collapse;
		width: auto;
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	th,
	td {
		padding: 0;
		border: 0;
		white-space: nowrap;
	}

	thead th {
		/* Vertical, because twenty-eight referent names set horizontally is a
		   table five screens wide. Rotated bottom-to-top, which is the direction a
		   reader tilts their head for. */
		height: 9rem;
		vertical-align: bottom;
		background: var(--paper);
		position: sticky;
		top: 0;
		z-index: 2;
	}

	thead th.corner {
		left: 0;
		z-index: 3;
		width: 11rem;
	}

	.head {
		background: none;
		border: 0;
		border-radius: 0;
		min-height: 0;
		padding: var(--sp-1);
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 400;
		letter-spacing: 0;
		text-transform: none;
		color: var(--ink-2);
		cursor: pointer;
		text-align: start;
	}

	thead .head {
		writing-mode: vertical-rl;
		rotate: 180deg;
		max-height: 8.5rem;
		overflow: hidden;
		text-overflow: ellipsis;
		width: 100%;
	}

	th.grouped .head {
		color: var(--ink-3);
		font-style: italic;
	}

	.head:hover,
	.head[aria-pressed='true'] {
		color: var(--ink);
		background: var(--mark);
	}

	tbody th.who {
		position: sticky;
		left: 0;
		z-index: 1;
		background: var(--paper);
		border-right: var(--hair) solid var(--rule-strong);
		text-transform: none;
		letter-spacing: 0;
		font-weight: 400;
		font-size: var(--step--2);
	}

	tbody th.who .head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--sp-2);
		width: 11rem;
		overflow: hidden;
	}

	.n {
		font-family: var(--mono);
		font-variant-numeric: tabular-nums;
		color: var(--ink-3);
	}

	tr.selected th.who {
		background: var(--mark);
	}

	/* The rule that separates the cases from the ways of talking about the
	   category. A hairline, like every other division on this site. */
	.rule {
		border-left: var(--hair) solid var(--rule-strong);
	}

	.cell {
		display: block;
		width: 2.6rem;
		height: 1.5rem;
		padding: 0;
		border: var(--hair) solid var(--rule);
		border-radius: 0;
		min-height: 0;
		background: none;
		font-family: var(--mono);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums;
		line-height: 1.4;
		text-align: center;
		color: var(--ink);
		cursor: pointer;
	}

	/* Amber, the ramp `theme.ts` builds for every magnitude on this site, capped
	   at the tint the numbers stay readable on in both themes. */
	.cell[data-state='drawn'] {
		background: color-mix(in oklab, var(--reg-accountability) var(--fill), transparent);
	}

	.cell[data-state='withheld-share'] {
		background: repeating-linear-gradient(45deg, transparent 0 3px, var(--rule-strong) 3px 4px);
	}

	.cell:hover {
		border-color: var(--blue);
	}

	/* Interaction is the accent's job, and an inset ring does not move the cell
	   or the ones beside it. */
	.cell.selected {
		box-shadow: inset 0 0 0 2px var(--blue-flag);
	}

	.hint {
		margin: var(--sp-2) 0 0;
		font-family: var(--mono);
		font-size: var(--step--2);
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
