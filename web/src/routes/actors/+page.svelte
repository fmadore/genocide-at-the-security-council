<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import CountryMap from '$lib/CountryMap.svelte';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
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
		readActorState,
		scale
	} from '$lib/actors';
	import type { ActorRow, ActorView, MapPoint, Ordering } from '$lib/actors';
	import { fills } from '$lib/choropleth';
	import type { Patch } from '$lib/choropleth';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, entityType, percent, shortCountry, termLabel } from '$lib/format';
	import type { PageData } from './$types';
	import { onMount, tick } from 'svelte';

	let { data }: { data: PageData } = $props();
	const artefact = $derived(data.countries);

	let measure = $state('genocide');
	let period = $state('all');
	let order = $state<Ordering>('speech_rate');
	let selected = $state<string | null>(null);
	let urlReady = $state(false);
	/* Circles first, and on purpose. They key on the speaker and can carry the
	   four that are on no map at all; the fill keys on territory and cannot. */
	let view = $state<ActorView>('points');

	const measures = $derived(Object.keys(artefact.measures));
	const shared = $derived(ambiguous(artefact));
	const result = $derived(plan({ data: artefact, measure, period, order }));

	onMount(() => {
		const state = readActorState(page.url.searchParams, artefact);
		measure = state.measure;
		period = state.period;
		order = state.order;
		view = state.view;
		void tick().then(() => {
			urlReady = true;
		});
	});

	$effect(() => {
		if (!urlReady) return;
		const params = actorParams({ measure, period, order, view }, artefact);
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

	/* The same rows keyed on territory instead of on the speaker. `$lib/choropleth`
	   says what that costs and what it refuses to do about it; nothing here
	   decides anything the circles do not. */
	const painted = $derived(fills(result, shared, figure));
	/* Reported by the map once the boundary file is here, because nothing before
	   then knows which codes it carries. */
	let unbounded = $state<Patch[]>([]);

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

<svelte:head>
	<title>Actors — Genocide at the Security Council</title>
	<meta
		name="description"
		content="Which delegations used the vocabulary of genocide, at what rate, and how many spoke too rarely to tell."
	/>
</svelte:head>

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

	<Figure
		title="Speakers by rate"
		question="Which delegations used the vocabulary most, as a share of their own speeches?"
		source="11_countries.py → countries/countries.json"
		note={view === 'points'
			? 'The radius of a circle carries the rate, not its area. Read the table for the numbers.'
			: 'Area is territory, not evidence: a country is prominent here because it is large. Read the table.'}
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
			<div class="view">
				<span class="label" id="map-view">Map</span>
				<div class="segmented" role="group" aria-labelledby="map-view">
					<button
						type="button"
						title="One circle per delegation, sized by the ranked figure. Colour carries nothing."
						aria-pressed={view === 'points'}
						onclick={() => (view = 'points')}>Circles</button
					>
					<button
						type="button"
						title="Territory shaded by the ranked figure. A country code held by two speakers is left blank rather than shaded."
						aria-pressed={view === 'choropleth'}
						onclick={() => (view = 'choropleth')}>Filled</button
					>
				</div>
			</div>
		{/snippet}

		{#snippet reading()}
			{#if view === 'points'}
				<p>
					One circle per delegation that spoke often enough to be measured. The radius carries the
					same figure the table is ranked by; colour carries nothing. A heavier ring marks a
					delegation whose three-letter country code (ISO3) another speaker shares.
				</p>
			{:else}
				<p>
					Territory shaded by the same figure the table is ranked by, running up from zero rather
					than from the lowest country. Two delegations here spoke often enough to be measured and
					never used the word, and a scale that began at the lowest value would shade them as merely
					quiet. The shading follows the <strong>square root</strong> of the rate: the middle delegation
					runs at about a tenth of the highest, so shading in direct proportion would leave half the world
					the colour of the page. Grey means a delegation heard from too rarely for a rate; blank means
					a state that did not speak at all in this period.
				</p>
			{/if}
			<p>
				Click a {view === 'points' ? 'circle' : 'country'} to pick out its row in the table, or a row
				to pick out its
				{view === 'points' ? 'circle' : 'country'}. Two country codes are held by more than one
				speaker and are marked with an asterisk in the table; in every period shown, only one holder
				of each has spoken often enough to be measured, so nothing on this map stands for two
				delegations at once.
				{#if view === 'points'}
					Circles that would land on the same coordinates are grouped rather than stacked, so that
					stays true as the corpus grows.
				{:else}
					A code shared by two measurable speakers would be outlined and left blank rather than
					given one of their two numbers.
				{/if}
			</p>
		{/snippet}

		{#snippet caveat()}
			<p>{artefact.centroid_rule}</p>
			{#if view === 'choropleth'}
				<p>
					<strong>Shading a country claims more than a circle does.</strong> A marker over Kigali is
					a way of finding Rwanda in a list; a shaded outline is the country itself, and for the
					historical speakers here that outline belongs to a successor state. Yugoslavia would shade
					modern Serbia, Zaire modern Democratic Republic of the Congo. Area carries no evidence
					either: Russia and Canada draw the eye because they are large, and {count(
						unbounded.length
					)} delegations are too small to have an outline at this scale and are marked with a dot instead.
					The circles and the table are built on the speaker and carry none of this.
				</p>
			{/if}
			<p>
				{count(result.under.length)} speakers delivered fewer than {count(result.minimum)} speeches in
				this period and carry no rate. They are not ranked low; they are not ranked. {artefact.minimum_speeches_rule}
			</p>
			{#if !has.occurrences}
				<p>
					{termLabel(measure)} gathers several overlapping phrases at once, so it counts
					<em>speeches that used any of them</em> and has no total for occurrences: a speech saying
					both
					<em>genocide</em> and <em>war crimes</em> would be counted twice by adding the members
					together. <code>11_countries.py</code> withholds that figure rather than publishing a wrong
					one, which is why the per-word column and the ranking that uses it are missing here instead
					of showing zero.
				</p>
			{/if}
		{/snippet}

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
				{weight}
				{selected}
				{view}
				fills={painted}
				unit={label(result.order)}
				format={(value) =>
					result.order === 'speech_rate'
						? percent(value)
						: result.order === 'token_rate'
							? decimal(value)
							: count(value)}
				onmissing={(patches) => (unbounded = patches)}
				explain={(patch) => {
					const point = drawn.find((p) => p.speakers[0].speaker.country_org === patch.key);
					if (patch.state === 'drawn' && point) return describeSpeaker(point);
					return {
						heading: patch.holders.map(shortCountry).join(', ') || patch.iso3,
						lines:
							patch.state === 'contested'
								? [
										`${patch.holders.length} speakers hold ${patch.iso3}`,
										'not filled: no one rate belongs here'
									]
								: [`fewer than ${count(result.minimum)} speeches in this period`, 'no rate']
					};
				}}
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

	<section class="table-wrap">
		<h2>The table behind the map</h2>
		<p class="prose">
			The same {count(result.rows.length)} rows, in the same order. The table is the main presentation
			and the map is a way into it: a circle cannot be reached by keyboard or read aloud by a screen reader,
			and a row can.
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
						<th scope="col" class="num">Using the term</th>
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
	     one word. It reads `speaker_keyness.json` and nothing above it.

	     The id is the landing point for the chronology's link out to this figure,
	     which had been pointing at a fragment no element carried. It lives on the
	     wrapper rather than inside the component so that the component stays
	     placeable more than once on a page without minting a duplicate id. -->
	<div id="speaker-keyness">
		<SpeakerKeyness data={data.keyness} />
	</div>

	<section class="apparatus">
		<h2>What this table will not tell you</h2>
		<ul>
			<li>
				<strong>{count(result.under.length)} speakers have no rate at all.</strong>
				{artefact.minimum_speeches_rule}
			</li>
			{#if unmapped.length}
				<li>
					<strong>{count(unmapped.length)} of the ranked speakers appear on no map.</strong>
					{unmapped
						.slice(0, 4)
						.map((entry) => entry.speaker.country_org)
						.join(', ')}{unmapped.length > 4 ? ', and others' : ''} are not states and have no place on
					a globe. They are in the table and missing from the figure above, on purpose.
				</li>
			{/if}
			{#each collisions as [code, holders] (code)}
				<li>
					<strong>{code} is shared by {holders.length} speakers.</strong>
					{holders.join(', ')} carry the same country code, because using a successor state's code is
					the only way to place a historical state on a map at all. They are never merged: a combined
					total would belong to no state that ever spoke.
				</li>
			{/each}
			<li>
				<strong>A country's map position is not where anyone spoke.</strong>
				{artefact.centroid_rule}
			</li>
			<li>
				<strong>The shaded map is built on territory; the table is built on the speaker.</strong>
				Shading needs a country code, so it inherits everything a code cannot carry: a historical speaker
				appears inside its successor's borders, a large state draws the eye for being large, and {count(
					unbounded.length
				)} delegations have no outline at this scale and are marked with a dot. Where two measurable speakers
				share a code, the country is outlined and left blank rather than given one of their two rates.
				The circles and this table carry none of these problems.
			</li>
		</ul>
	</section>
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
	.view {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	.view .label {
		display: inline;
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
