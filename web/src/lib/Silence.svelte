<script lang="ts">
	/**
	 * Who stays silent when others say it.
	 *
	 * A renderer over `#lib/silence`, which settles what is ranked and why. The
	 * table is the figure: each row's 95% interval is drawn in its own cell on
	 * one scale for the whole table, with the room's average as a dashed line,
	 * so a delegation far from the room reads as far from the line.
	 */
	import { resolve } from '$app/paths';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Figure from '#lib/Figure.svelte';
	import Icon from '#lib/Icon.svelte';
	import { provenanceOf } from '#lib/export.js';
	import type { ExportRequest } from '#lib/export.js';
	import { count, entityType, percent, shortCountry } from '#lib/format.js';
	import { EXPORT_COLUMNS, exportRows, plan } from '#lib/silence.js';
	import type { Ordering, SilenceEntry } from '#lib/silence.js';
	import type { Countries } from '#lib/types.js';

	let { data }: { data: Countries } = $props();

	let period = $state('all');
	let order = $state<Ordering>('quietest');
	let who = $state<'states' | 'all'>('states');

	const result = $derived(plan({ data, period, order, states: who === 'states' }));
	const room = $derived(result.summary?.room_share ?? null);

	const ORDERS: { id: Ordering; label: string }[] = [
		{ id: 'quietest', label: 'Quietest first' },
		{ id: 'loudest', label: 'Most outspoken first' },
		{ id: 'exposed', label: 'Meetings exposed' },
		{ id: 'name', label: 'Name' }
	];

	/* One axis for every row: the widest upper bound in the selection. */
	const scale = $derived(
		Math.max(...result.rows.map((e) => e.row.share_high ?? 0), room ?? 0, 1e-6)
	);
	const at = (value: number) => `${((value / scale) * 100).toFixed(2)}%`;

	/* The delegation's own uses in the period: what it said when it did join in. */
	function uses(entry: SilenceEntry): string | null {
		if (entry.row.joined < 1 || !result.period) return null;
		const params = new URLSearchParams({
			term: data.silence.measure,
			country: entry.row.country_org,
			from: String(result.period.first_year),
			to: String(result.period.last_year)
		});
		return `${resolve('/concordance')}?${params.toString()}`;
	}

	function table(): ExportRequest {
		return {
			title: 'Who stays silent when others say it',
			columns: EXPORT_COLUMNS,
			rows: exportRows(data),
			provenance: provenanceOf(data.meta, 'countries/countries.json'),
			filters: [
				`period: ${result.period?.label ?? period}`,
				`showing: ${who === 'states' ? 'states only' : 'every speaker'}`,
				`ordered by: ${ORDERS.find((o) => o.id === order)?.label ?? order}`,
				`minimum: ${data.silence.minimum_meetings} exposed meetings`
			],
			scope:
				'every speaker exposed at least once, in every period, including those below the ' +
				`${data.silence.minimum_meetings}-meeting minimum whose shares are null`
		};
	}
</script>

<Figure
	title="Who stays silent when others say it"
	question="When another speaker has just used the word, does a delegation use it too, or stay silent?"
	source="11_countries.py → countries/countries.json"
	note="Shares are of a delegation's own exposed meetings, never of all its speeches."
	download={{ name: ['unsc', 'silence', period, who], table }}
>
	{#snippet controls()}
		<label>
			Period
			<select bind:value={period}>
				{#each data.periods as p (p.key)}<option value={p.key}>{p.label}</option>{/each}
			</select>
		</label>
		<label>
			Showing
			<select bind:value={who}>
				<option value="states">States</option>
				<option value="all">Every speaker</option>
			</select>
		</label>
		<label>
			Ordered by
			<select bind:value={order}>
				{#each ORDERS as o (o.id)}<option value={o.id}>{o.label}</option>{/each}
			</select>
		</label>
	{/snippet}

	{#snippet reading()}
		<p>
			A meeting counts when the delegation took the floor and another speaker used the word. The
			share is the part of those meetings in which it used the word too. The bar is the 95%
			interval, the tick the share, the dashed line the room's average{#if room !== null}, {percent(
					room
				)}{/if}. A name opens its own uses.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			Not using the word is a fact about the record, not about intent. For other languages the word
			is the UN translator's, and a delegation may have spoken to another point. {count(
				result.withheld
			)} speakers with fewer than {count(result.minimum)} such meetings are not ranked.
		</p>
	{/snippet}
	{#snippet more()}
		<p>
			Procedural turns by the presidency are left out on both sides: they read agenda titles aloud,
			and some titles contain the word. A meeting in which a delegation was the only one to use the
			word does not count for it, because nobody else had made the word available.
		</p>
		{#if result.summary}<p>
				In this period {count(result.summary.meetings)} meetings carried the word in a substantive speech.
				Speakers joined in {count(result.summary.joined)} of {count(result.summary.exposed)} exposed attendances.
			</p>{/if}
	{/snippet}

	{#if result.refusal}
		<p class="refusal">
			{#if result.refusal === 'none-sufficient'}
				No speaker reached {count(result.minimum)} exposed meetings in this period. Select a longer period.
			{:else}
				This combination is not in the data.
			{/if}
		</p>
	{:else}
		<div class="scroll">
			<table>
				<caption class="sr-only">
					Speakers by the share of their exposed meetings in which they used the word, {result
						.period?.label}
				</caption>
				<thead>
					<tr>
						<th scope="col">Speaker</th>
						<th scope="col">Group</th>
						<th scope="col" class="num">Exposed meetings</th>
						<th scope="col" class="num">Used the word</th>
						<th scope="col" class="num">Share</th>
						<th scope="col">95% interval</th>
					</tr>
				</thead>
				<tbody>
					{#each result.rows as entry (entry.row.country_org)}
						{@const link = uses(entry)}
						<tr>
							<th scope="row">
								{#if link}<a href={link}>{shortCountry(entry.row.country_org)}</a
									>{:else}{shortCountry(entry.row.country_org)}{/if}
							</th>
							<td
								>{entry.speaker?.un_regional_group ??
									(entry.speaker ? entityType(entry.speaker.entity_type) : '—')}</td
							>
							<td class="num">{count(entry.row.exposed)}</td>
							<td class="num">{count(entry.row.joined)}</td>
							<td class="num">{percent(entry.row.share ?? 0)}</td>
							<td class="whisker">
								<span
									class="rail"
									style:--low={at(entry.row.share_low ?? 0)}
									style:--high={at(entry.row.share_high ?? 0)}
									style:--point={at(entry.row.share ?? 0)}
									style:--room={at(room ?? 0)}
									class:has-room={room !== null}
									aria-hidden="true"
								></span>
								<span class="range"
									>{percent(entry.row.share_low ?? 0)}&ndash;{percent(
										entry.row.share_high ?? 0
									)}</span
								>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<details class="data-table">
		<summary><Icon icon={ChevronRight} />The rule, as the artefact states it</summary>
		<p class="prose">{data.silence.rule}</p>
	</details>
</Figure>

<style>
	.scroll {
		overflow-x: auto;
		max-height: 32rem;
		overflow-y: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	th,
	td {
		text-align: start;
		padding: var(--sp-2) var(--sp-3) var(--sp-2) 0;
		border-bottom: var(--hair) solid var(--rule);
		white-space: nowrap;
	}

	thead th {
		position: sticky;
		top: 0;
		background: var(--paper);
		z-index: 1;
		color: var(--ink);
		font-weight: 600;
		border-bottom: var(--hair) solid var(--rule-strong);
	}

	tbody th {
		font-weight: 400;
	}

	.num {
		text-align: end;
		font-variant-numeric: tabular-nums lining-nums;
	}

	/* The interval column, drawn as on "Speakers by rate": the Wilson bounds as
	   a bar, the share as a tick, and here the room's average as a dashed line on
	   the same scale. */
	td.whisker {
		min-width: 9rem;
	}

	.rail {
		position: relative;
		display: inline-block;
		vertical-align: middle;
		width: 4.5rem;
		height: 0.75rem;
		margin-inline-end: 0.5rem;
		background: linear-gradient(
			to right,
			transparent var(--low),
			var(--rule) var(--low),
			var(--rule) var(--high),
			transparent var(--high)
		);
	}

	.rail::after {
		content: '';
		position: absolute;
		top: -0.15rem;
		bottom: -0.15rem;
		left: var(--point);
		width: 2px;
		margin-left: -1px;
		background: var(--ink);
	}

	.rail.has-room::before {
		content: '';
		position: absolute;
		top: -0.3rem;
		bottom: -0.3rem;
		left: var(--room);
		border-left: 1px dashed var(--ink-3);
	}

	.range {
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
	}

	.refusal,
	.prose {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
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
