<script lang="ts">
	/**
	 * Who held a seat when they spoke.
	 *
	 * A renderer over `$lib/standing`, which settles what is drawn and why. The
	 * one drawing decision here is the one §3 forced: **the bar is the table**.
	 * Each row's composition is painted in the row's own background as a
	 * multi-stop gradient, so the figure and the numbers are a single element and
	 * there is no second rendering that could drift from the first — the same
	 * decision the per-speaker keyness view made, for the same reason.
	 *
	 * One hue per position, and five of them rather than a seated family and an
	 * unseated one. "Not seated" covers three different situations — a state that
	 * was not on the Council, the Secretariat which never can be, and an invited
	 * speaker — and a shared colour would say they were the same thing, which is
	 * exactly what the artefact's `seated_rule` refuses. What groups the two
	 * seated positions instead is *structure*: they are listed first, so the
	 * seated share is always the left-hand part of a row, which is the quantity
	 * printed beside it. `--blue` appears nowhere: it belongs to what a reader can
	 * act on, never to a datum.
	 *
	 * There is no minimum here, and the interface says so rather than leaving the
	 * absence to be noticed. Every other figure over this artefact withholds a
	 * rate below 100 speeches; a share of a speaker's own known speeches is a fact
	 * about the record rather than an estimate from a sample, so it is published
	 * at every denominator.
	 */
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, percent, shortCountry } from '$lib/format';
	import { EXPORT_COLUMNS, exemplar, exportRows, plan } from '$lib/standing';
	import type { Category, Ordering, Segment } from '$lib/standing';
	import type { Countries } from '$lib/types';

	let { data }: { data: Countries } = $props();

	let period = $state('all');
	let category = $state<Category | 'all'>('changed');
	let order = $state<Ordering>('held');

	const result = $derived(plan({ data, period, category, order }));
	const named = $derived(exemplar(result.rows));

	const CATEGORIES: { id: Category | 'all'; label: string; hint: string }[] = [
		{ id: 'changed', label: 'Spoke from both', hint: 'seated in some years, not in others' },
		{ id: 'always', label: 'Always seated', hint: 'every speech from a seat' },
		{ id: 'never', label: 'Never seated', hint: 'no speech from a seat' },
		{ id: 'all', label: 'Every speaker', hint: 'all three records at once' }
	];

	/* The gradient. One `linear-gradient` with hard stops rather than five nested
	   elements: a band is a range of the row, not a box inside it. */
	const bands = (segments: Segment[]) =>
		segments
			.map(
				(band) => `var(--band-${slug(band.group)}) ${band.from.toFixed(3)}% ${band.to.toFixed(3)}%`
			)
			.join(', ');

	const slug = (group: string) => group.toLowerCase().replace(/[^a-z0-9]+/g, '-');

	const describe = (entry: (typeof result.rows)[number]) =>
		entry.segments
			.map((band) => `${band.group}: ${count(band.count)} (${percent(band.share)})`)
			.join(', ');

	function table(): ExportRequest {
		return {
			title: 'Who held a seat when they spoke',
			columns: EXPORT_COLUMNS(result.groups),
			rows: exportRows(data),
			provenance: provenanceOf(data.meta, 'countries/countries.json'),
			filters: [
				`period: ${result.period?.label ?? period}`,
				`showing: ${CATEGORIES.find((c) => c.id === category)?.label ?? category}`,
				`ordered by: ${order === 'held' ? 'speeches delivered' : order === 'name' ? 'name' : 'seated share'}`
			],
			scope:
				'every speaker in every period, with all five group counts — a file carrying ' +
				'only the seated total would erase the difference between a state that was not ' +
				'on the Council, the Secretariat, and an invited speaker'
		};
	}
</script>

<Figure
	title="Who held a seat when they spoke"
	question="Was a delegation speaking as a member of the Council, or from outside it?"
	source="11_countries.py → countries/countries.json"
	note="A row is a mixture, not a single label. Width is the share of that speaker's own speeches."
	download={{ name: ['unsc', 'standing', period, String(category)], table }}
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
			<select bind:value={category}>
				{#each CATEGORIES as c (c.id)}<option value={c.id}>{c.label}</option>{/each}
			</select>
		</label>
		<label>
			Ordered by
			<select bind:value={order}>
				<option value="held">Speeches delivered</option>
				<option value="seated_share">Share from a seat</option>
				<option value="name">Name</option>
			</select>
		</label>
		<span class="hint-inline">{CATEGORIES.find((c) => c.id === category)?.hint}</span>
	{/snippet}

	{#snippet reading()}
		<p>
			Each row is one speaker's own speeches, divided up by the position it held when it gave them.
			The two <strong>seated</strong> bands are the UN Charter's two kinds of Council membership: the
			five permanent members and the ten elected ones. The three unseated bands are kept apart because
			they are not the same thing as each other.
		</p>
		<p>
			Of {count(result.counts.changed + result.counts.always + result.counts.never)} speakers in this
			period,
			<strong>{count(result.counts.changed)}</strong>
			spoke both from a seat and from outside one, {count(result.counts.always)} only ever from a seat,
			and {count(result.counts.never)} never from one.
			{#if named}
				{shortCountry(named.row.country_org)} is the clearest case: {count(named.row.held)} speeches,
				{percent(named.row.seated_share ?? 0)} of them from a seat.
			{/if}
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>{data.standing.membership_rule}</p>
		<p>
			<strong>There is no minimum sample here</strong>, unlike every rate on this page. {data
				.standing.seated_rule}
		</p>
		<p>
			A whole-corpus row is not the sum of the period rows, and the two should not be read side by
			side: a speaker can hold a seat for a decade and still count as a non-member across the corpus
			as a whole.
		</p>
	{/snippet}

	{#if result.refusal}
		<p class="refusal">
			{#if result.refusal === 'none-in-category'}
				No speaker in this period has that record.
			{:else}
				This combination is not in the data.
			{/if}
		</p>
	{:else}
		<div class="key">
			{#each result.groups as group (group)}
				<span class="swatch" style:--band="var(--band-{slug(group)})">
					<i></i>{group}{#if result.seatedGroups.has(group)}<abbr
							title="Holds a seat on the Council">seat</abbr
						>{/if}
				</span>
			{/each}
		</div>

		<div class="scroll">
			<table>
				<caption class="sr-only">
					Speakers by the positions they held when speaking, {result.period?.label}
				</caption>
				<thead>
					<tr>
						<th scope="col">Speaker</th>
						<th scope="col" class="num">Speeches</th>
						<th scope="col" class="num">From a seat</th>
						{#each result.groups as group (group)}
							<th scope="col" class="num">{group}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each result.rows as entry (entry.row.country_org)}
						<tr class="band" style:--bands="linear-gradient(to right, {bands(entry.segments)})">
							<th scope="row" title={describe(entry)}>{shortCountry(entry.row.country_org)}</th>
							<td class="num">{count(entry.row.held)}</td>
							<td class="num">{percent(entry.row.seated_share ?? 0)}</td>
							{#each result.groups as group (group)}
								<td class="num" class:nil={!entry.row.groups[group]}
									>{count(entry.row.groups[group] ?? 0)}</td
								>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<details class="data-table">
		<summary><Icon icon={ChevronRight} />What the five positions mean</summary>
		<p class="prose">{data.standing.seated_rule}</p>
	</details>
</Figure>

<style>
	/* One hue per position, tinted toward the page so the numbers can be read on
	   top of them. Five distinct hues rather than two families, because "not
	   seated" covers three different situations and a shared colour would say
	   they were one.

	   What groups the two seated positions is structure, not hue: the artefact
	   lists them first, so the seated share is always the left-hand part of a
	   row — which is the quantity beside it. `--blue` is absent on purpose. */
	.key,
	table {
		--tint: 32%;
		--band-p5: color-mix(in oklab, var(--ink) var(--tint), transparent);
		--band-e10: color-mix(in oklab, var(--reg-accountability) var(--tint), transparent);
		--band-non-member-state: color-mix(in oklab, var(--reg-legal) var(--tint), transparent);
		--band-un: color-mix(in oklab, var(--reg-commemorative) var(--tint), transparent);
		--band-non-state: color-mix(in oklab, var(--reg-preventive) var(--tint), transparent);
	}

	.key {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-2) var(--sp-4);
		margin-bottom: var(--sp-3);
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
	}

	.swatch {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
	}

	.swatch i {
		width: 1.4rem;
		height: 0.55rem;
		background: var(--band);
		display: inline-block;
	}

	.swatch abbr {
		font-size: var(--step--2);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3);
		text-decoration: none;
		margin-inline-start: var(--sp-1);
	}

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

	thead th {
		position: sticky;
		top: 0;
		background: var(--paper);
		z-index: 1;
	}

	/* The composition, painted behind the row it describes. The gradient sits on
	   the row itself rather than in an overlay element: a `tr::after` is not laid
	   out reliably in table layout, and the bands are a range of the row rather
	   than a box inside it.

	   The zebra striping every other table on this site gets is switched off
	   here, and that is not a preference. `app.css` alternates a background
	   colour down the rows; these bands are 32% opaque, so the stripe shows
	   through and the same position is drawn in two different colours down the
	   column. Decoration and data cannot share one channel. */
	tbody tr.band {
		background-color: transparent;
		background-image: var(--bands);
	}

	tbody th {
		font-weight: 400;
		white-space: nowrap;
		/* The global `th` is an uppercased faint label, which is right for a column
		   heading and wrong for a speaker's name. */
		text-transform: none;
		letter-spacing: 0;
		font-size: var(--step--1);
		color: var(--ink);
	}

	.nil {
		color: var(--ink-3);
		opacity: 0.55;
	}

	.refusal,
	.prose {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}

	.hint-inline {
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
