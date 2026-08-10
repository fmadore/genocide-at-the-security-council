<script lang="ts">
	import { resolve } from '$app/paths';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import CountryMap from '$lib/CountryMap.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import SpeakerKeyness from '$lib/SpeakerKeyness.svelte';
	import Standing from '$lib/Standing.svelte';
	import { ambiguous, carries, occurrences, orderings, plan, points, scale } from '$lib/actors';
	import type { ActorRow, MapPoint, Ordering } from '$lib/actors';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, percent, shortCountry, termLabel } from '$lib/format';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
	const artefact = $derived(data.countries);

	let measure = $state('genocide');
	let period = $state('all');
	let order = $state<Ordering>('speech_rate');
	let selected = $state<string | null>(null);

	const measures = $derived(Object.keys(artefact.measures));
	const shared = $derived(ambiguous(artefact));
	const result = $derived(plan({ data: artefact, measure, period, order }));

	/* What this measure has a number for. `atrocity_core` is a union of five
	   overlapping terms, so 11 withholds its occurrence count rather than
	   double-counting a speech that uses two of them — and a withheld figure read
	   through `?? 0` is published as `0.00 per 100,000 words`. Everything below
	   that would print one is gated on this instead. */
	const has = $derived(carries(artefact.measures[measure]));
	const rankings = $derived(orderings(artefact.measures[measure]));

	/* `plan()` refuses an ordering the measure cannot support and says which one
	   it used; the select follows it, so the control never names a figure the
	   table is not in. */
	$effect(() => {
		if (!rankings.includes(order)) order = result.order;
	});

	/* Size stands for the figure the table is ranked by, so a large marker and a
	   high row are the same statement. Computed over what is on screen, which
	   makes a marker comparable within one view and not across two. */
	const drawn = $derived(points(result.rows, shared));
	const figure = (entry: ActorRow) =>
		result.order === 'token_rate'
			? (entry.row.token_rate ?? 0)
			: result.order === 'speeches'
				? entry.row.speeches
				: result.order === 'held'
					? entry.row.held
					: (entry.row.speech_rate ?? 0);
	const at = $derived(scale(drawn.map((point) => figure(point.speakers[0]))));
	const weight = (point: MapPoint) => at(figure(point.speakers[0]));

	const chosen = $derived(
		drawn.find((p) => p.speakers[0].speaker.country_org === selected) ?? null
	);

	/* Speakers the map cannot show at all: the UN Secretariat is among the
	   largest in the corpus and belongs on no globe. Stated rather than left for
	   a reader to notice that a table row has no marker. */
	const unmapped = $derived(result.rows.filter((entry) => !entry.speaker.mappable));

	const collisions = $derived(
		Object.entries(artefact.iso3_collisions).filter(([, holders]) => holders.length > 1)
	);

	/**
	 * The download: every speaker in the period, not the 133 that are drawn.
	 *
	 * The withheld rows go in with their nulls intact and a `sufficient` column
	 * beside them, so the file carries the minimum-sample gate rather than having
	 * been quietly filtered by it. A reader who wants only the drawable rows can
	 * filter on that column; a reader given only those rows cannot recover the
	 * 468 that were left out, or know that they were.
	 */
	function table(): ExportRequest {
		const speakers = new Map(artefact.countries.map((s) => [s.country_org, s]));
		const rows = artefact.measures[measure].rows
			.filter((row) => row.period === period)
			.map((row) => {
				const speaker = speakers.get(row.country_org);
				return [
					row.country_org,
					speaker?.entity_type ?? null,
					speaker?.iso3 ?? null,
					speaker?.un_regional_group ?? null,
					row.held,
					row.tokens,
					row.speeches,
					row.speech_rate,
					// Two columns a set measure has no figure for. Dropped rather
					// than written empty: a blank column reads as data that went
					// missing, and this one was never computed.
					...(has.occurrences ? [row.occurrences, row.token_rate] : []),
					row.sufficient,
					speaker?.mappable ?? null
				];
			});
		return {
			title: `Speakers by rate — ${termLabel(measure)}, ${result.period?.label ?? period}`,
			columns: [
				'country_org',
				'entity_type',
				'iso3',
				'un_regional_group',
				'speeches_held',
				'tokens',
				'term_bearing_speeches',
				'speech_rate',
				...(has.occurrences ? ['occurrences', `token_rate_per_${artefact.rate_per_tokens}`] : []),
				'sufficient',
				'mappable'
			],
			rows,
			provenance: provenanceOf(artefact.meta, 'countries/countries.json'),
			filters: [
				`measure: ${termLabel(measure)}`,
				`period: ${result.period?.label ?? period}`,
				`ranked by: ${label(result.order)}`,
				`minimum: ${artefact.minimum_speeches} speeches`,
				...(has.occurrences
					? []
					: [
							`occurrences and token rate: withheld — ${termLabel(measure)} is a union of ` +
								`overlapping terms and a sum would double-count`
						])
			],
			scope:
				`all ${rows.length} speakers in this period, including the ${result.withheld} ` +
				`below the ${artefact.minimum_speeches}-speech minimum whose rates are null`
		};
	}

	/** What a ranking is called. `title` capitalises it for a control; prose keeps it low. */
	const label = (o: Ordering, title = false) => {
		const text =
			o === 'speech_rate'
				? 'share of its speeches'
				: o === 'token_rate'
					? `per ${count(artefact.rate_per_tokens)} words`
					: o === 'speeches'
						? 'term-bearing speeches'
						: 'speeches delivered';
		return title ? text.charAt(0).toUpperCase() + text.slice(1) : text;
	};
</script>

<svelte:head>
	<title>Actors · Genocide at the Security Council</title>
	<meta
		name="description"
		content="Which delegations used genocide vocabulary, at what rate, and how many are heard from too rarely to say."
	/>
</svelte:head>

<article class="page">
	<header class="lede">
		<h1>Who said it</h1>
		<p class="standfirst">
			Every speaker with its own denominator: how much of what a delegation said at the Council
			carried the vocabulary, rather than how often it appears in the record. Of
			{count(artefact.countries.length)} speakers, {count(result.rows.length)} are heard from often enough
			to answer.
		</p>
	</header>

	<Figure
		title="Speakers by rate"
		question="Which delegations used the vocabulary most, as a share of their own speeches?"
		source="11_countries.py → countries/countries.json"
		note="Circle area is not proportional to the rate; radius is. Read the table."
		download={{ name: ['unsc', measure, period, 'speakers'], table }}
	>
		{#snippet controls()}
			<label>
				Measure
				<select bind:value={measure}>
					{#each measures as name (name)}<option value={name}>{termLabel(name)}</option>{/each}
				</select>
			</label>
			<label>
				Period
				<select bind:value={period}>
					{#each artefact.periods as p (p.key)}<option value={p.key}>{p.label}</option>{/each}
				</select>
			</label>
			<label>
				Ranked by
				<select bind:value={order}>
					{#each rankings as ranking (ranking)}
						<option value={ranking}>{label(ranking, true)}</option>
					{/each}
				</select>
			</label>
		{/snippet}

		{#snippet reading()}
			<p>
				One circle per delegation that cleared the minimum. Radius carries the same figure the table
				is ranked by; colour carries nothing. A heavier ring marks a point whose ISO3 code another
				speaker also holds.
			</p>
			<p>
				Click a circle to pick out its row, or a row to pick out its circle. Two ISO3 codes are held
				by more than one speaker, marked with an asterisk in the table; in every period here only
				one holder of each clears the minimum, so no marker on this map stands for more than one
				speaker. Markers are grouped by coordinate rather than drawn on top of each other, so that
				stays true if the corpus grows.
			</p>
		{/snippet}

		{#snippet caveat()}
			<p>{artefact.centroid_rule}</p>
			<p>
				{count(result.withheld)} speakers delivered fewer than {count(result.minimum)} speeches in this
				period and carry no rate. They are not ranked low; they are not ranked. {artefact.minimum_speeches_rule}
			</p>
			{#if !has.occurrences}
				<p>
					{termLabel(measure)} is a union of overlapping terms, so this measure counts
					<em>speeches that used any of them</em> and has no occurrence count: a speech saying both
					<em>genocide</em> and <em>war crimes</em> would be counted twice by a sum of its members.
					<code>11_countries.py</code> withholds the figure rather than computing a wrong one, so the
					per-word column and its ranking are absent here rather than shown as zero.
				</p>
			{/if}
		{/snippet}

		{#if result.refusal}
			<p class="refusal">
				{#if result.refusal === 'none-sufficient'}
					No speaker in this period cleared {count(result.minimum)} speeches, so there is nothing here
					that could be drawn honestly.
				{:else}
					This slice is not in the artefact.
				{/if}
			</p>
		{:else}
			<CountryMap
				points={drawn}
				{weight}
				{selected}
				onselect={(point) => (selected = point?.speakers[0].speaker.country_org ?? null)}
				describe={(point) => {
					const { speaker, row } = point.speakers[0];
					return {
						heading: shortCountry(speaker.country_org),
						lines: [
							`${percent(row.speech_rate ?? 0)} of ${count(row.held)} speeches`,
							// Both of these are figures a set measure does not have.
							...(has.occurrences
								? [
										`${decimal(row.token_rate ?? 0)} per ${count(artefact.rate_per_tokens)} words`,
										`${count(row.occurrences ?? 0)} occurrences · ${speaker.un_regional_group ?? speaker.entity_type}`
									]
								: [`${speaker.un_regional_group ?? speaker.entity_type}`]),
							...(point.speakers.length > 1
								? [`${point.speakers.length} speakers share this point`]
								: []),
							...(point.shared ? [`${speaker.iso3} is held by more than one speaker`] : [])
						]
					};
				}}
			/>
		{/if}
	</Figure>

	{#if chosen}
		<aside class="picked">
			<h2>{shortCountry(chosen.speakers[0].speaker.country_org)}</h2>
			{#if chosen.speakers.length > 1}
				<p class="stacked">
					This point carries {chosen.speakers.length} speakers, which share a centroid and an ISO3 code.
					They are separate rows with separate denominators and are not combined:
					{chosen.speakers.map((s) => s.speaker.country_org).join(', ')}.
				</p>
			{/if}
			<dl>
				{#each chosen.speakers as entry (entry.speaker.country_org)}
					{@const links = occurrences(artefact, measure, entry)}
					<div>
						<dt>{shortCountry(entry.speaker.country_org)}</dt>
						<dd>
							{percent(entry.row.speech_rate ?? 0)} of {count(entry.row.held)} speeches
							{#if has.occurrences}&middot; {count(entry.row.occurrences ?? 0)} occurrences{/if}
							&middot; {entry.speaker.first_year}&ndash;{entry.speaker.last_year}
						</dd>
						{#if links.length === 1}
							<dd class="read">
								<a class="more" href="{resolve('/concordance')}?{links[0].query}">
									Read the occurrences <Icon icon={ChevronRight} />
								</a>
							</dd>
						{:else if links.length > 1}
							<!-- The concordance shows one term. A single link for a set would
							     offer a fifth of the evidence as all of it, so the members are
							     listed and the reading is term by term. -->
							<dd class="read">
								<span>Read them one term at a time:</span>
								{#each links as link, index (link.term)}<a
										href="{resolve('/concordance')}?{link.query}">{termLabel(link.term)}</a
									>{#if index < links.length - 1}<span aria-hidden="true">
											&middot;
										</span>{/if}{/each}
							</dd>
						{/if}
					</div>
				{/each}
			</dl>
			<p class="scoped">
				Each link carries this speaker and {result.period?.label ?? period} into the concordance, so what
				opens is the evidence behind the rate above rather than the whole corpus.
			</p>
		</aside>
	{/if}

	<section class="table-wrap">
		<h2>The table behind the map</h2>
		<p class="prose">
			The same {count(result.rows.length)} rows, in the same order. This is the primary presentation:
			the map is an index into it, and a circle cannot be tabbed to or read aloud.
		</p>
		<div class="scroll">
			<table>
				<caption class="sr-only">
					Speakers ranked by {label(result.order)} for {termLabel(measure)}, {result.period?.label}
				</caption>
				<thead>
					<tr>
						<th scope="col">Speaker</th>
						<th scope="col">Group</th>
						<th scope="col" class="num">Speeches</th>
						<th scope="col" class="num">Term-bearing</th>
						<th scope="col" class="num">Share</th>
						{#if has.occurrences}
							<th scope="col" class="num">Per {count(artefact.rate_per_tokens)} words</th>
						{/if}
					</tr>
				</thead>
				<tbody>
					{#each result.rows as entry (entry.speaker.country_org)}
						<tr
							class:picked={entry.speaker.country_org === selected}
							class:unmapped={!entry.speaker.mappable}
						>
							<th scope="row">
								<button
									type="button"
									onclick={() =>
										(selected =
											selected === entry.speaker.country_org ? null : entry.speaker.country_org)}
								>
									{shortCountry(entry.speaker.country_org)}
								</button>
								{#if entry.speaker.iso3 && shared.has(entry.speaker.iso3)}
									<abbr title="This ISO3 code is held by more than one speaker in the corpus."
										>{entry.speaker.iso3}*</abbr
									>
								{/if}
							</th>
							<td>{entry.speaker.un_regional_group ?? entry.speaker.entity_type}</td>
							<td class="num">{count(entry.row.held)}</td>
							<td class="num">{count(entry.row.speeches)}</td>
							<td class="num">{percent(entry.row.speech_rate ?? 0)}</td>
							{#if has.occurrences}
								<td class="num">{decimal(entry.row.token_rate ?? 0)}</td>
							{/if}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	<!-- The same artefact, a different block, and a question the ranking above
	     cannot answer: not how often a delegation used the word, but what
	     position it held when it spoke at all. It reads `countries.json`'s
	     `standing` block and none of the measures beside it. -->
	<Standing data={artefact} />

	<!-- A second question over a second artefact, on the same page because it is
	     the same object: what a delegation said, rather than how often it said
	     one word. It reads `speaker_keyness.json` and nothing above it. -->
	<SpeakerKeyness data={data.keyness} />

	<section class="apparatus">
		<h2>What this table will not tell you</h2>
		<ul>
			<li>
				<strong>{count(result.withheld)} speakers are withheld, not ranked low.</strong>
				{artefact.minimum_speeches_rule}
			</li>
			{#if unmapped.length}
				<li>
					<strong>{count(unmapped.length)} of the ranked speakers are on no map.</strong>
					{unmapped
						.slice(0, 4)
						.map((entry) => entry.speaker.country_org)
						.join(', ')}{unmapped.length > 4 ? ', and others' : ''} are not states with a centroid. They
					are in the table and absent from the figure above, on purpose.
				</li>
			{/if}
			{#each collisions as [code, holders] (code)}
				<li>
					<strong>{code} is shared by {holders.length} speakers.</strong>
					{holders.join(', ')} carry the same code because a successor state's code is the only way to
					place a historical one at all. They are never merged: a combined denominator would belong to
					no state that ever spoke.
				</li>
			{/each}
			<li>
				<strong>A centroid is not where anyone spoke.</strong>
				{artefact.centroid_rule}
			</li>
		</ul>
	</section>
</article>

<style>
	.page {
		max-width: var(--page);
		margin: 0 auto;
		padding: var(--sp-7) var(--gutter) var(--sp-9);
	}

	.lede {
		max-width: var(--measure);
		margin-bottom: var(--sp-7);
	}

	h1 {
		font-family: var(--serif);
		font-size: var(--display);
		line-height: 1.05;
		margin: 0 0 var(--sp-4);
	}

	.standfirst {
		font-family: var(--serif);
		font-size: var(--step-1);
		color: var(--ink-2);
		margin: 0;
	}

	.refusal,
	.prose {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}

	.picked {
		margin: var(--sp-5) 0 0;
		padding: var(--sp-4) 0;
		border-top: var(--hair) solid var(--rule);
		border-bottom: var(--hair) solid var(--rule);
	}

	.picked h2 {
		font-family: var(--sans);
		font-size: var(--step-0);
		margin: 0 0 var(--sp-2);
	}

	.stacked {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}

	.picked dl {
		margin: 0;
	}

	.picked dt {
		font-family: var(--sans);
		font-weight: 600;
		font-size: var(--step--1);
	}

	.picked dd {
		margin: 0 0 var(--sp-2);
		font-family: var(--mono);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.more {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.picked dd.read {
		font-family: var(--sans);
		margin-bottom: var(--sp-3);
	}

	.picked dd.read span {
		color: var(--ink-3);
		margin-right: var(--sp-1);
	}

	.scoped {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
		margin: 0;
	}

	.table-wrap,
	.apparatus {
		margin-top: var(--sp-7);
	}

	h2 {
		font-family: var(--sans);
		font-size: var(--step-1);
		margin: 0 0 var(--sp-3);
	}

	.scroll {
		overflow-x: auto;
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
		color: var(--ink-3);
		font-weight: 600;
		border-bottom: var(--hair) solid var(--rule-strong);
	}

	.num {
		text-align: end;
		font-family: var(--mono);
		font-variant-numeric: tabular-nums;
	}

	tbody th {
		font-weight: 400;
	}

	tbody button {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: var(--blue);
		cursor: pointer;
		text-align: start;
	}

	tbody button:hover {
		color: var(--blue-mid);
	}

	tr.picked {
		background: var(--mark);
	}

	tr.unmapped th::after {
		content: ' (not mapped)';
		color: var(--ink-3);
		font-size: var(--step--2);
	}

	abbr {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
		text-decoration: none;
		margin-inline-start: var(--sp-1);
	}

	.apparatus ul {
		max-width: var(--measure);
		margin: 0;
		padding-inline-start: var(--sp-4);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.apparatus li {
		margin-bottom: var(--sp-3);
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
