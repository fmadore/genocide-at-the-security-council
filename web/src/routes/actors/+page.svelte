<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Contents from '$lib/Contents.svelte';
	import CountryMap from '$lib/CountryMap.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import SpeakerKeyness from '$lib/SpeakerKeyness.svelte';
	import Standing from '$lib/Standing.svelte';
	import {
		actorParams,
		ambiguous,
		carries,
		occurrences,
		orderings,
		plan,
		points,
		readActorState
	} from '$lib/actors';
	import type { MapPoint, Ordering } from '$lib/actors';
	import type { CountryMeasureRow } from '$lib/types';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, entityType, percent, shortCountry, termLabel } from '$lib/format';
	import { PAGE_METADATA } from '$lib/seo';
	import type { PageData } from './$types';
	import { onMount, tick } from 'svelte';

	let { data }: { data: PageData } = $props();
	const artefact = $derived(data.countries);

	let measure = $state('genocide_qualification');
	let period = $state('all');
	let order = $state<Ordering>('speech_rate');
	let selected = $state<string | null>(null);
	let urlReady = $state(false);

	const measures = $derived(Object.keys(artefact.measures));
	const shared = $derived(ambiguous(artefact));
	const result = $derived(plan({ data: artefact, measure, period, order }));

	onMount(() => {
		const state = readActorState(page.url.searchParams, artefact);
		measure = state.measure;
		period = state.period;
		order = state.order;
		void tick().then(() => {
			urlReady = true;
		});
	});

	$effect(() => {
		if (!urlReady) return;
		const params = actorParams({ measure, period, order }, artefact);
		const search = params.toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	$effect(() => {
		void [measure, period];
		selected = null;
	});

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

	/* The dots locate; the table measures. Nothing about a marker follows the
	   ranked figure any more, so there is no scale to compute here. */
	const drawn = $derived(points(result.rows, shared));

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
					row.words,
					row.speeches,
					row.speech_rate,
					row.speech_rate_low,
					row.speech_rate_high,
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
				'words',
				'term_bearing_speeches',
				'speech_rate',
				'speech_rate_wilson95_low',
				'speech_rate_wilson95_high',
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
				`all ${rows.length} speakers in this period, including the ${result.under.length} ` +
				`below the ${artefact.minimum_speeches}-speech minimum whose rates are null`
		};
	}

	/**
	 * What the hover box says over a speaker.
	 *
	 * Named rather than written inline because both views ask for it: a circle
	 * hands over its point, and a filled country hands over the one drawable
	 * speaker at that ISO3. Two copies of this would be two hover boxes free to
	 * disagree about the same delegation.
	 */
	function describeSpeaker(point: MapPoint) {
		const { speaker, row } = point.speakers[0];
		return {
			heading: shortCountry(speaker.country_org),
			lines: [
				`${percent(row.speech_rate ?? 0)} of ${count(row.held)} speeches`,
				...(row.speech_rate_low != null && row.speech_rate_high != null
					? [`95% interval ${percent(row.speech_rate_low)}–${percent(row.speech_rate_high)}`]
					: []),
				// Both of these are figures a set measure does not have.
				...(has.occurrences
					? [
							`${decimal(row.token_rate ?? 0)} per ${count(artefact.rate_per_tokens)} words`,
							`${count(row.occurrences ?? 0)} occurrences · ${speaker.un_regional_group ?? entityType(speaker.entity_type)}`
						]
					: [`${speaker.un_regional_group ?? entityType(speaker.entity_type)}`]),
				...(point.speakers.length > 1
					? [`${point.speakers.length} speakers share this point`]
					: []),
				...(point.shared ? [`${speaker.iso3} is held by more than one speaker`] : [])
			]
		};
	}

	/* The whisker column is scaled to the widest upper bound on the page, so
	   every row's interval is drawn on one axis and the rows can be compared. */
	const whiskerScale = $derived(
		Math.max(...result.rows.map((entry) => entry.row.speech_rate_high ?? 0), 1e-6)
	);
	const whisker = (row: CountryMeasureRow) => {
		if (row.speech_rate == null || row.speech_rate_low == null || row.speech_rate_high == null) {
			return null;
		}
		const at = (value: number) => `${((value / whiskerScale) * 100).toFixed(2)}%`;
		return {
			low: at(row.speech_rate_low),
			high: at(row.speech_rate_high),
			point: at(row.speech_rate)
		};
	};

	/** What a ranking is called. `title` capitalises it for a control; prose keeps it low. */
	const label = (o: Ordering, title = false) => {
		const text =
			o === 'speech_rate'
				? 'share of its speeches'
				: o === 'token_rate'
					? `per ${count(artefact.rate_per_tokens)} words`
					: o === 'speeches'
						? 'speeches using the term'
						: 'speeches delivered';
		return title ? text.charAt(0).toUpperCase() + text.slice(1) : text;
	};
</script>

<PageMeta meta={PAGE_METADATA['/actors/']} />

<article>
	<header class="lede">
		<h1>Who said it</h1>
		<p class="standfirst">
			Each delegation measured against its own record: what share of its own speeches used this
			vocabulary, rather than how often it turns up in the corpus overall. Of
			{count(artefact.countries.length)} speakers, {count(result.rows.length)} spoke often enough for
			that share to mean anything.
		</p>
	</header>

	<Contents
		figures={[
			{ title: 'Speakers by rate' },
			{ title: 'Who held a seat when they spoke' },
			{ title: 'What a delegation says that the room does not' }
		]}
	/>

	<Figure
		title="Speakers by rate"
		question="Which delegations used the vocabulary most, as a share of their own speeches?"
		source="11_countries.py → countries/countries.json"
		note="Every dot is the same size: the map locates a delegation, the table carries its rate."
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
				Ranked by the figure you chose; each row's <strong>whisker</strong> is the 95% Wilson interval
				of its share. Click a row to pick a delegation out on the map, or a dot to pick its row. Dots
				are all one size: the map locates, the table measures. An asterisk marks a country code held by
				two speakers.
			</p>
		{/snippet}

		{#snippet caveat()}
			<p>
				{artefact.centroid_rule}
				{count(result.under.length)} speakers delivered fewer than
				{count(result.minimum)} speeches this period and carry no rate: they are not ranked low, they
				are not ranked.
				{#if !has.occurrences}<em>{termLabel(measure)}</em> gathers overlapping phrases, so it counts
					speeches using any of them and has no occurrence total.{/if}
			</p>
		{/snippet}
		{#snippet more()}
			<p>{artefact.minimum_speeches_rule}</p>
			{#if unmapped.length}
				<p>
					{count(unmapped.length)} of the ranked speakers appear on no map: {unmapped
						.slice(0, 4)
						.map((entry) => shortCountry(entry.speaker.country_org))
						.join(', ')}{unmapped.length > 4 ? ' and others' : ''} are not states and have no place on
					a globe. They are in the table on purpose.
				</p>
			{/if}
			{#each collisions as [code, holders] (code)}
				<p>
					{code} is shared by {holders.join(' and ')}: a successor state's code is the only way to
					place a historical state on a map. They are never merged; a combined total would belong to
					no state that ever spoke.
				</p>
			{/each}
		{/snippet}

		<section class="table-wrap">
			<h3 class="sr-only">Speakers, ranked</h3>
			<div class="scroll">
				<table>
					<caption class="sr-only">
						Speakers ranked by {label(result.order)} for {termLabel(measure)}, {result.period
							?.label}
					</caption>
					<thead>
						<tr>
							<th scope="col">Speaker</th>
							<th scope="col">Group</th>
							<th scope="col" class="num">Speeches</th>
							<th scope="col" class="num">Using the term</th>
							<th scope="col" class="num">Share</th>
							<th scope="col" class="whisker-head">95% interval</th>
							{#if has.occurrences}
								<th scope="col" class="num">Per {count(artefact.rate_per_tokens)} words</th>
							{/if}
						</tr>
					</thead>
					<tbody>
						{#each result.rows as entry (entry.speaker.country_org)}
							{@const w = whisker(entry.row)}
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
										<abbr
											title="This three-letter country code is held by more than one speaker in the corpus."
											>{entry.speaker.iso3}*</abbr
										>
									{/if}
								</th>
								<td>{entry.speaker.un_regional_group ?? entityType(entry.speaker.entity_type)}</td>
								<td class="num">{count(entry.row.held)}</td>
								<td class="num">{count(entry.row.speeches)}</td>
								<td class="num">{percent(entry.row.speech_rate ?? 0)}</td>
								<td class="whisker">
									{#if w}
										<span
											class="rail"
											style:--low={w.low}
											style:--high={w.high}
											style:--point={w.point}
											aria-hidden="true"
										></span>
										<span class="range"
											>{percent(entry.row.speech_rate_low ?? 0)}&ndash;{percent(
												entry.row.speech_rate_high ?? 0
											)}</span
										>
									{:else}
										<span class="nil">—</span>
									{/if}
								</td>
								{#if has.occurrences}
									<td class="num">{decimal(entry.row.token_rate ?? 0)}</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		{#if result.refusal}
			<p class="refusal">
				{#if result.refusal === 'none-sufficient'}
					No speaker in this period reached {count(result.minimum)} speeches, so there is nothing here
					that could be drawn honestly.
				{:else}
					This combination is not in the data.
				{/if}
			</p>
		{:else}
			<CountryMap
				points={drawn}
				{selected}
				onselect={(point) => (selected = point?.speakers[0].speaker.country_org ?? null)}
				describe={describeSpeaker}
			/>
		{/if}
	</Figure>

	{#if chosen}
		<aside class="picked">
			<h2>{shortCountry(chosen.speakers[0].speaker.country_org)}</h2>
			{#if chosen.speakers.length > 1}
				<p class="stacked">
					This point carries {chosen.speakers.length} speakers, which share both a map position and a
					country code. They stay separate rows, each measured against its own speeches:
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
							{#if entry.row.speech_rate_low != null && entry.row.speech_rate_high != null}
								<span class="interval"
									>(95% interval {percent(entry.row.speech_rate_low)}&ndash;{percent(
										entry.row.speech_rate_high
									)})</span
								>
							{/if}
							{#if has.occurrences}&middot; {count(entry.row.occurrences ?? 0)} occurrences{/if}
							&middot; {entry.speaker.first_year}&ndash;{entry.speaker.last_year}
						</dd>
						<dd class="read">
							<a
								class="more"
								href="{resolve('/usage')}?actor={encodeURIComponent(entry.speaker.country_org)}"
							>
								Which genocide it means by the word <Icon icon={ChevronRight} />
							</a>
							<span class="interval">model-derived, experimental</span>
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
								<span>Read them one word at a time:</span>
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
				Each link carries this speaker and {result.period?.label ?? period} through to the concordance,
				so what opens is the evidence behind the rate above rather than the whole corpus.
			</p>
		</aside>
	{/if}

	<!-- The same artefact, a different block, and a question the ranking above
	     cannot answer: not how often a delegation used the word, but what
	     position it held when it spoke at all. It reads `countries.json`'s
	     `standing` block and none of the measures beside it. -->
	<Standing data={artefact} />

	<!-- A second question over a second artefact, on the same page because it is
	     the same object: what a delegation said, rather than how often it said
	     one word. It reads `speaker_keyness.json` and nothing above it.

	     The id is the landing point for the chronology's link out to this figure,
	     which had been pointing at a fragment no element carried. It lives on the
	     wrapper rather than inside the component so that the component stays
	     placeable more than once on a page without minting a duplicate id. -->
	<div id="speaker-keyness">
		<SpeakerKeyness data={data.keyness} />
	</div>
</article>

<style>
	/* No page box here: `main` in `+layout.svelte` already sets the measure, the
	   gutter and the top padding for every route. Repeating them on this
	   article inset it by a second gutter and pushed its title 51px below every
	   other page's — the same heading, in a different place, on one route. */

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

	/* The view switch, in the figure's control bar beside the three selects. */

	.refusal {
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

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	/* The interval column: a rail the width of the cell, scaled to the widest
	   upper bound on the page, with the Wilson bounds as a bar and the rate
	   as a tick. Read left to right like the map's circles, and unlike them
	   it survives a screen reader, which gets the printed range. */
	.whisker-head {
		white-space: nowrap;
	}

	td.whisker {
		min-width: 9rem;
		white-space: nowrap;
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
		border-radius: 1px;
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

	.range,
	.interval {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}
</style>
