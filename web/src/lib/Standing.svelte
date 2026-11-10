<script lang="ts">
	/**
	 * Who held a seat when they spoke.
	 *
	 * A renderer over `#lib/standing`, which settles what is drawn and why. The
	 * one drawing decision here is that the bar lives in the table: each row's
	 * composition is a multi-stop gradient in a cell of that row, so the figure
	 * and the numbers are one table and there is no second rendering that could
	 * drift from the first. It used to be painted behind the whole row, which put
	 * counts on the bands of other columns.
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
	import Figure from '#lib/Figure.svelte';
	import Icon from '#lib/Icon.svelte';
	import { provenanceOf } from '#lib/export.js';
	import type { ExportRequest } from '#lib/export.js';
	import { count, percent, shortCountry } from '#lib/format.js';
	import { EXPORT_COLUMNS, exemplar, exportRows, plan } from '#lib/standing.js';
	import type { Category, Ordering, Segment } from '#lib/standing.js';
	import type { Countries } from '#lib/types.js';
	import { categoricalData, colours } from '#lib/theme.js';

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

	/* One fill per position: the eight fills DESIGN.md gives a categorical split
	   that is not a register, alternating dark and light so neighbouring bands
	   differ in lightness as well as hue in both themes. They were five weights
	   of ink at 6–55% painted behind the whole row: the three lightest could not
	   be told apart, the two lightest vanished in dark, and a count could sit on
	   another column's band (review of 10 November 2026). */
	const fills = $derived.by(() => {
		const ramp = categoricalData($colours);
		return new Map(result.groups.map((group, i) => [group, ramp[i % ramp.length]!]));
	});

	/* The gradient. One `linear-gradient` with hard stops rather than five nested
	   elements: a band is a range of the bar, not a box inside it. */
	const bands = (segments: Segment[]) =>
		segments
			.map(
				(band) =>
					`${fills.get(band.group) ?? 'transparent'} ${band.from.toFixed(3)}% ${band.to.toFixed(3)}%`
			)
			.join(', ');

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
	note="Band width shows the share of an affiliation's speeches delivered in each membership category."
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
			Each row divides an affiliation's speeches by its status when speaking. Band width shows the
			share in each category; numbers give speech counts. P5 means permanent members; E10 means
			elected members. {count(result.counts.changed)} affiliations spoke both as members and as non-members.
			{#if named}{shortCountry(named.row.country_org)} delivered {percent(
					named.row.seated_share ?? 0
				)} of its {count(named.row.held)} speeches as a Council member.{/if}
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			Status is attached to each speech, so an affiliation can appear in several categories over
			time. These descriptive shares are displayed even for small speech totals. Membership does not
			measure influence, and non-member states, UN speakers and non-state participants have
			different roles.
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
				<span class="swatch" style:--band={fills.get(group)}>
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
						<th scope="col" class="composition">Composition</th>
						{#each result.groups as group (group)}
							<th scope="col" class="num"
								><span class="swatch" style:--band={fills.get(group)}><i></i>{group}</span></th
							>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each result.rows as entry (entry.row.country_org)}
						<tr>
							<th scope="row" title={describe(entry)}>{shortCountry(entry.row.country_org)}</th>
							<td class="num">{count(entry.row.held)}</td>
							<td class="num">{percent(entry.row.seated_share ?? 0)}</td>
							<td class="composition" title={describe(entry)}>
								<span
									class="bar"
									aria-hidden="true"
									style:--bands="linear-gradient(to right, {bands(entry.segments)})"
								></span>
							</td>
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
		<p class="prose">
			Permanent and elected members held Council seats when speaking. Non-member states addressed
			the Council without holding a seat. UN speakers and non-state participants form separate
			categories. The source labels elected members E10; the Council had six elected seats before
			its expansion in 1965.
		</p>
	</details>
</Figure>

<style>
	/* One fill per position, set in the script from the theme. Five distinct
	   fills rather than two families, because "not seated" covers three
	   different situations and a shared colour would say they were one.

	   What groups the two seated positions is structure, not hue: the artefact
	   lists them first, so the seated share is always the left-hand part of a
	   row — which is the quantity beside it. `--blue` is absent on purpose. */
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

	/* The site's colour key: a 0.625rem square before the words. */
	.swatch i {
		width: 0.625rem;
		height: 0.625rem;
		background: var(--band);
		display: inline-block;
		flex: none;
	}

	/* Sentence case at the key's own size: the tracked capitals this carried are
	   gone, and what separates it from the position's name is weight and the
	   quieter ink, not a second typographic register. */
	.swatch abbr {
		font-size: var(--step--2);
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

	/* The bar has a cell of its own, as the pooled months' does, so every count
	   sits on the page's ground and not on some other column's band — and the
	   zebra stripe, which used to show through 32%-opaque bands and draw one
	   position in two colours, can stay on: the bar's fills are opaque. */
	.composition {
		min-width: 8rem;
		width: 20%;
	}

	.bar {
		display: block;
		height: var(--sp-3);
		background-image: var(--bands);
	}

	thead .swatch {
		justify-content: flex-end;
	}

	tbody th {
		/* The global `th` is a bold column heading, which is right at the head of
		   a column and wrong on a speaker's name. */
		font-weight: 400;
		white-space: nowrap;
		font-size: var(--step--1);
		color: var(--ink);
	}

	/* Faint ink at full strength: at 55% opacity a zero fell under 3:1 and
	   vanished in dark. */
	.nil {
		color: var(--ink-3);
	}

	.refusal,
	.prose {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}

	/* The one family: the typewriter face is the citation's, and this is a gloss
	   on the control beside it. */
	.hint-inline {
		font-family: var(--sans);
		font-size: var(--step--1);
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
