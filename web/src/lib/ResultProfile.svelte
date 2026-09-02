<!--
	What the current result set is made of, and how to narrow it further.

	This panel is apparatus, not evidence, and the distinction is the reason it
	is not a `Figure`. A figure on this site must declare a question, a reading,
	a caveat and a source, because it makes a claim about the Council. This makes
	no claim: it counts the lines a reader has already selected, so that the
	selection can be seen and adjusted. Give it the figure apparatus and it would
	read as a finding about who says the word most, which is precisely what a raw
	count cannot support.

	Hence one rule the copy holds to. Every number here is a count of concordance
	lines, and it says so, next to the two pages that carry rates. A year with
	many lines is partly a year the Council met more, and nothing on this panel
	is corrected for that.

	Everything the panel decides is decided in `concordance.ts` — the counts, the
	top-N cut and its remainder, and what a click does to the state. This file
	draws them.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { chronologyEscape, topFacet } from './concordance';
	import type { ConcordanceState, FacetDimension, FacetRow, ResultProfile } from './concordance';
	import { count, shortCountry, termLabel } from './format';
	import Icon from './Icon.svelte';

	interface Props {
		profile: ResultProfile;
		state: ConcordanceState;
		/** The corpus bounds, so an empty year is still drawn in its place. */
		firstYear: number;
		lastYear: number;
		onfacet: (dimension: FacetDimension, value: string) => void;
		onyear: (year: number) => void;
	}

	let { profile, state, firstYear, lastYear, onfacet, onyear }: Props = $props();

	/* Eight rows before the remainder: enough that the P5 and the busiest
	   delegations are all present at once, few enough that four columns of them
	   remain one glance rather than a page. */
	const TOP = 8;

	const COLUMNS: { dimension: FacetDimension; label: string }[] = [
		{ dimension: 'country', label: 'Speaker' },
		{ dimension: 'group', label: 'Speaker group' },
		{ dimension: 'participantType', label: 'Participant type' },
		{ dimension: 'agenda', label: 'Agenda item' }
	];

	const columns = $derived(
		COLUMNS.map((column) => ({
			...column,
			facet: topFacet(profile[column.dimension], TOP, state[column.dimension])
		}))
	);

	/* The full corpus range, not only the years that are present: a gap in the
	   middle of the strip is a fact about the term, and drawing only the years
	   with lines would silently close it. */
	const years = $derived(
		Array.from({ length: lastYear - firstYear + 1 }, (_, index) => {
			const year = firstYear + index;
			return { year, lines: profile.years.get(year) ?? 0 };
		})
	);

	const busiest = $derived(Math.max(1, ...years.map((entry) => entry.lines)));
	const oneYear = $derived(state.from === state.to ? state.from : null);
	const escape = $derived(chronologyEscape(state.term));

	const label = (dimension: FacetDimension, value: string) =>
		dimension === 'country' ? shortCountry(value) : value;

	const lines = (n: number) => `${count(n)} ${n === 1 ? 'line' : 'lines'}`;

	/*
	 * What the hover has to give back.
	 *
	 * A row name is one clipped line — "Maintenance ..." is an agenda item this
	 * column has no room for — and the bar behind the number carries a share
	 * with no figure beside it. The title restores both: the name in full, and
	 * the count as the fraction of the result set it actually is, in the same
	 * register as the rest of the panel, which counts lines and says so.
	 */
	const facetTip = (dimension: FacetDimension, row: FacetRow) =>
		`${label(dimension, row.value)} — ${count(row.count)} of ${lines(profile.total)} on screen`;

	/* An empty year has no button to hover: it is disabled, and a disabled
	   control suppresses the tooltip with the pointer events. The title sits on
	   the column instead, so a gap in the strip can still say which year it is. */
	const yearTip = (year: number, n: number) => `${year}: ${n === 0 ? 'no lines' : lines(n)}`;

	/* An empty year is not a control, and offering to narrow to it is a promise
	   the disabled button cannot keep. It names itself and its emptiness instead. */
	const yearLabel = (year: number, n: number, selected: boolean) =>
		n === 0 ? `${year}, no lines` : `${selected ? 'Release' : 'Narrow to'} ${year}, ${lines(n)}`;
</script>

<details class="profile" open>
	<summary><Icon icon={ChevronRight} />Profile of this result set</summary>

	<p class="hint">
		Counts of the <strong>{count(profile.total)}</strong> lines currently on screen — apparatus for
		narrowing them, not evidence of emphasis. A busy year is partly a year the Council met more, and
		nothing here is corrected for that; the rates are on
		<a href={resolve('/chronology')}>Chronology</a> and <a href={resolve('/actors')}>Actors</a>.
		Select a row to apply it, select it again to release it.
	</p>

	{#if profile.total === 0}
		<p class="empty">No lines match, so there is nothing to profile.</p>
	{:else}
		<section class="years">
			<h3>By year</h3>
			<ol class="strip" style:--columns={years.length}>
				{#each years as entry (entry.year)}
					<li title={yearTip(entry.year, entry.lines)}>
						<button
							type="button"
							class:nil={entry.lines === 0}
							aria-pressed={oneYear === entry.year}
							disabled={entry.lines === 0}
							aria-label={yearLabel(entry.year, entry.lines, oneYear === entry.year)}
							onclick={() => onyear(entry.year)}
						>
							<span class="bar" style:--height="{(entry.lines / busiest) * 100}%"></span>
						</button>
					</li>
				{/each}
			</ol>
			<div class="axis">
				<span>{firstYear}</span>
				<span class="peak">busiest year: {count(busiest)}</span>
				<span>{lastYear}</span>
			</div>
		</section>

		<div class="facets">
			{#each columns as column (column.dimension)}
				<section>
					<h3>{column.label}</h3>
					<ol>
						{#each column.facet.rows as row (row.value)}
							<li>
								<button
									type="button"
									aria-pressed={row.active}
									title={facetTip(column.dimension, row)}
									aria-label="{row.active ? 'Release' : 'Filter to'} {label(
										column.dimension,
										row.value
									)}, {lines(row.count)}"
									onclick={() => onfacet(column.dimension, row.value)}
								>
									<span class="name">{label(column.dimension, row.value)}</span>
									<span class="tally" style:--share="{(row.count / profile.total) * 100}%">
										<span class="fill"></span><span class="n">{count(row.count)}</span>
									</span>
								</button>
							</li>
						{/each}
					</ol>
					{#if column.facet.remainder}
						<p class="rest">
							and {count(column.facet.remainder.values)} more, holding {count(
								column.facet.remainder.count
							)}
							{column.facet.remainder.count === 1 ? 'line' : 'lines'}
						</p>
					{/if}
				</section>
			{/each}
		</div>
	{/if}

	<p class="escape">
		<a href="{resolve('/chronology')}?{escape.query}">
			Open the chronology of {termLabel(state.term)}<Icon icon={ArrowRight} />
		</a>
		<span class="scope">{escape.scope}</span>
	</p>
</details>

<style>
	.profile {
		border-top: 1px solid var(--rule);
		margin-block: var(--sp-4);
		padding-top: var(--sp-3);
	}

	summary {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 600;
		color: var(--ink-2);
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: var(--sp-1);
	}

	summary :global(svg) {
		transition: transform 120ms ease;
	}

	.profile[open] summary :global(svg) {
		transform: rotate(90deg);
	}

	.hint,
	.empty,
	.rest,
	.axis,
	.scope {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.hint {
		margin-block: var(--sp-3);
		max-width: 68ch;
		line-height: 1.5;
	}

	h3 {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-block: 0 var(--sp-2);
	}

	ol {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	/* One column per year of the corpus, so position on the strip is the date
	   and a year with no lines keeps its place rather than closing the gap. */
	.strip {
		display: grid;
		grid-template-columns: repeat(var(--columns), 1fr);
		gap: 1px;
		align-items: end;
		height: 3.5rem;
	}

	.strip button {
		display: flex;
		align-items: flex-end;
		width: 100%;
		height: 3.5rem;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}

	.strip button:disabled {
		cursor: default;
	}

	/* Monochrome on purpose. Colour on this site carries register and speaker
	   group; spending it on a navigation aid would make those readings ambiguous. */
	.bar {
		display: block;
		width: 100%;
		min-height: 1px;
		height: var(--height);
		background: var(--ink-3);
	}

	.strip button.nil .bar {
		background: var(--rule);
		height: 1px;
	}

	.strip button:hover:not(:disabled) .bar,
	.strip button[aria-pressed='true'] .bar {
		background: var(--blue);
	}

	.axis {
		display: flex;
		justify-content: space-between;
		margin-top: var(--sp-1);
	}

	.peak {
		font-family: var(--mono);
	}

	.facets {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
		gap: var(--sp-4);
		margin-top: var(--sp-4);
	}

	.facets button {
		display: grid;
		grid-template-columns: 1fr 6rem;
		gap: var(--sp-2);
		align-items: center;
		width: 100%;
		padding: 2px var(--sp-1);
		border: 0;
		background: none;
		text-align: left;
		cursor: pointer;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.facets button:hover {
		background: var(--paper-sunk);
		color: var(--ink);
	}

	.facets button[aria-pressed='true'] {
		color: var(--blue);
		font-weight: 600;
	}

	.name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* The bar sits behind the number rather than beside it: four columns of
	   these have no room for a third track, and the count is the thing being
	   compared. */
	.tally {
		position: relative;
		display: flex;
		justify-content: flex-end;
		align-items: center;
		padding-inline: var(--sp-1);
	}

	.fill {
		position: absolute;
		inset-block: 1px;
		inset-inline-end: 0;
		width: var(--share);
		background: var(--rule);
	}

	.facets button[aria-pressed='true'] .fill {
		background: color-mix(in oklab, var(--blue) 28%, transparent);
	}

	.n {
		position: relative;
		font-family: var(--mono);
		font-size: var(--step--2);
	}

	.rest {
		margin-block: var(--sp-2) 0;
		padding-inline: var(--sp-1);
	}

	.empty {
		margin-block: var(--sp-3);
	}

	.escape {
		margin-block: var(--sp-4) 0;
		padding-top: var(--sp-3);
		border-top: 1px solid var(--rule);
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-1) var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.escape a {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
	}

	@media (prefers-reduced-motion: reduce) {
		summary :global(svg) {
			transition: none;
		}
	}
</style>
