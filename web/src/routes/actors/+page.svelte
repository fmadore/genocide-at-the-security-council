<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { base, resolve } from '$app/paths';
	import { browser } from '$app/environment';
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
		readActorState,
		widening
	} from '$lib/actors';
	import type { MapPoint, Ordering } from '$lib/actors';
	import type { CountryMeasureRow } from '$lib/types';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import { count, decimal, entityType, measureLabel, percent, shortCountry } from '$lib/format';
	import {
		DEFAULT_SCOPE,
		SCOPE_IDS,
		rankedDelegations,
		readScope,
		scopeOf,
		withScope
	} from '$lib/scope';
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
	let countryMap = $state<CountryMap | null>(null);

	const measures = $derived(Object.keys(artefact.measures));
	const shared = $derived(ambiguous(artefact));
	/* The published measure is a subtraction and no concordance enumerates one,
	   so a link resolves to the term it subtracts from — which holds the spans
	   the measure removes as well as the ones it counts. The aside says so. */
	const wider = $derived(widening(artefact, measure));
	const result = $derived(plan({ data: artefact, measure, period, order }));
	const pageSize = 20;
	let rankingPage = $state(1);
	let speakerSearch = $state('');
	const matchingRows = $derived(
		result.rows.filter((entry) =>
			shortCountry(entry.speaker.country_org)
				.toLocaleLowerCase()
				.includes(speakerSearch.trim().toLocaleLowerCase())
		)
	);
	const pageCount = $derived(Math.max(1, Math.ceil(matchingRows.length / pageSize)));
	const visibleRows = $derived(
		matchingRows.slice((rankingPage - 1) * pageSize, rankingPage * pageSize)
	);
	$effect(() => {
		void [measure, period, order, speakerSearch];
		rankingPage = 1;
	});
	$effect(() => {
		if (!selected) return;
		const index = matchingRows.findIndex((entry) => entry.speaker.country_org === selected);
		if (index >= 0) rankingPage = Math.floor(index / pageSize) + 1;
	});

	onMount(() => {
		const state = readActorState(page.url.searchParams, artefact);
		measure = state.measure;
		period = state.period;
		order = state.order;
		speakerSearch = page.url.searchParams.get('q') ?? '';
		const requestedPage = Number(page.url.searchParams.get('page') ?? 1);
		void tick().then(() => {
			rankingPage = Number.isSafeInteger(requestedPage)
				? Math.max(1, Math.min(pageCount, requestedPage))
				: 1;
			urlReady = true;
		});
	});

	$effect(() => {
		if (!urlReady) return;
		/* The scope is layout state and the page owns everything else in the
		   query, so it is merged back in here: a page that rebuilt its own URL
		   from its own controls would silently drop the reader's reading set on
		   the next keystroke. */
		const params = withScope(actorParams({ measure, period, order }, artefact), scope);
		if (speakerSearch) params.set('q', speakerSearch);
		if (rankingPage > 1) params.set('page', String(rankingPage));
		const search = params.toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	$effect(() => {
		void [measure, period];
		selected = null;
	});

	/* What this measure has a number for. Every measure carries an occurrence
	   count since lexicon v5 removed the unions, but the gate stays: `11` may
	   withhold a figure rather than compute a wrong one, and a withheld figure
	   read through `?? 0` is published as `0.00 per 100,000 words`. Everything
	   below that would print one is gated on this instead. */
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
		drawn.find((p) => p.speakers.some((entry) => entry.speaker.country_org === selected)) ?? null
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
					// Two columns a withholding measure has no figure for. Dropped
					// rather than written empty: a blank column reads as data that
					// went missing, and this one was never computed.
					...(has.occurrences ? [row.occurrences, row.token_rate] : []),
					row.sufficient,
					speaker?.mappable ?? null
				];
			});
		return {
			title: `Speakers by rate — ${measureLabel(measure)}, ${result.period?.label ?? period}`,
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
				`measure: ${measureLabel(measure)}`,
				`period: ${result.period?.label ?? period}`,
				`ranked by: ${label(result.order)}`,
				`minimum: ${artefact.minimum_speeches} speeches`,
				...(has.occurrences
					? []
					: [
							`occurrences and token rate: withheld — ${measureLabel(measure)} is published ` +
								`without an occurrence count`
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
				// Both of these are figures a withholding measure does not have.
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

	/* --- The reading set the masthead selected -----------------------------
	   Who is in it, measured against their own record. The rate below is the
	   share of a delegation's *own* speeches, so the reading set changes the
	   numerator and never the base — which is what lets the debate scope ask
	   who sat in those meetings without inflating anybody's rate. */
	/* `url.searchParams` is unreadable while a page is prerendered, by design:
	   a static file cannot depend on a query string. The answer there is the
	   default, which is the guarantee R9 makes anyway — a URL carrying no scope
	   renders what the site rendered before R9 — and hydration applies the rest. */
	const scope = $derived(browser ? readScope(page.url.searchParams) : DEFAULT_SCOPE);
	const chosenScope = $derived(scopeOf(data.scopeIndex, scope));
	const RANKED = 20;
	const inScope = $derived(
		rankedDelegations(data.scopeIndex, scope, artefact.minimum_speeches, RANKED)
	);

	function scopeTable(): ExportRequest {
		return {
			title: 'The reading set, by delegation',
			columns: ['country_org', 'speeches_held', ...SCOPE_IDS.map((id) => `speeches_${id}`)],
			rows: data.scopeIndex.delegations.map((row) => [
				row.country_org,
				row.held,
				...SCOPE_IDS.map((id) => row.scopes[id])
			]),
			provenance: provenanceOf(data.scopeIndex.meta, 'scopes.json'),
			filters: [`drawn: ${chosenScope.label}`, `ranked: top ${RANKED}`],
			scope:
				`every speaker the three reading sets hold, including the ` +
				`${count(artefact.minimum_speeches)}-speech minimum's withheld rows, which the figure does not rank`
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
			{ title: 'The reading set, by delegation' },
			{ title: 'Speakers by rate' },
			{ title: 'Who held a seat when they spoke' },
			{ title: 'What a delegation says that the room does not' }
		]}
	/>

	<Figure
		title="The reading set, by delegation"
		question="Inside the selected reading set, who spoke, and how much of their own record is it?"
		source="09_export_speeches.py → scopes.json"
		note="Share is of a delegation's own speeches in the whole corpus, never of the reading set."
		download={{ name: ['unsc', 'reading-set', 'delegations', scope], table: scopeTable }}
	>
		{#snippet reading()}
			<p>
				<strong>{chosenScope.label}</strong>: {count(chosenScope.speeches)} speeches in
				{count(chosenScope.meetings)} meetings. The {RANKED} delegations whose own record it covers most.
				Change the set in the masthead.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				Under <em>the debate</em> a delegation is counted for every speech it made in a meeting where
				someone said the word, whether or not it said anything. That is the point of the set, and it is
				not a measure of what the delegation said.
			</p>
		{/snippet}
		{#snippet more()}
			<p>
				<a href={`${base}/data/actor_year/actor_year.csv`} download
					>Download annual speaker counts and rates</a
				>. Each affiliation keeps its own annual denominator. Rates below 125 speeches are withheld;
				the CSV retains counts and labels its Wilson intervals.
			</p>
			<p>{artefact.minimum_speeches_rule}</p>
		{/snippet}

		<section class="table-wrap">
			<h3 class="sr-only">The reading set, by delegation</h3>
			<div class="scroll">
				<table>
					<caption class="sr-only"
						>Delegations ranked by the share of their own speeches that {chosenScope.label.toLowerCase()}
						holds</caption
					>
					<thead>
						<tr>
							<th scope="col">Speaker</th>
							<th scope="col" class="num">Speeches</th>
							<th scope="col" class="num">In the set</th>
							<th scope="col" class="num">Share</th>
						</tr>
					</thead>
					<tbody>
						{#each inScope as row (row.country_org)}
							<tr>
								<th scope="row">{shortCountry(row.country_org)}</th>
								<td class="num">{count(row.held)}</td>
								<td class="num">{count(row.speeches)}</td>
								<td class="num">{row.share === null ? '—' : percent(row.share)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	</Figure>

	<Figure
		fullscreen
		onfullscreenchange={() => countryMap?.resize()}
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
					{#each measures as name (name)}<option value={name}>{measureLabel(name)}</option>{/each}
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
				of its share. Click a row to pick a delegation out on the map, or a dot to pick its row. An asterisk
				marks a country code held by two speakers.
			</p>
			<!-- The measure is a subtraction, and its name is now a name rather than
			     the key: the arithmetic has to be somewhere a reader meets it. The
			     size is read off the artefact's own rows, never written here, and is
			     stated only where the payload carries both measures. -->
			{#if wider}
				<p>
					<em>{measureLabel(measure)}</em> is <em>{measureLabel(wider.term)}</em> less
					<em>{wider.subtracted.map(measureLabel).join(' and ')}</em
					>{#if wider.occurrences !== null}, which removes {count(wider.occurrences)} occurrences{/if}.
					<a href="{resolve('/methods')}#derived-measure">Method: the subtraction &rarr;</a>
				</p>
			{/if}
		{/snippet}

		{#snippet caveat()}
			<p>
				{artefact.centroid_rule}
				{count(result.under.length)} speakers delivered fewer than
				{count(result.minimum)} speeches this period and carry no rate: they are not ranked low, they
				are not ranked.
				{#if !has.occurrences}<em>{measureLabel(measure)}</em> is published without an occurrence total,
					so the rate here is a share of speeches and nothing else.{/if}
			</p>
		{/snippet}
		{#snippet more()}
			<!-- The rule governs a denominator, so it cannot differ between measures;
			     `11_countries.py` refuses a payload where it does. Said here because a
			     reader who changes the measure and sees the same speakers withheld is
			     owed the reason, and because the alternative would look like a finding. -->
			<p>
				{artefact.minimum_speeches_rule} It is about how much a delegation spoke, not what it said, so
				the same speakers are withheld whichever measure is selected.
			</p>
			{#if wider}
				<p>
					A delegation calling the ex-FAR <em>génocidaires</em> names who did it rather than asking
					the Council to call the event a genocide, so the actor label is counted on its own and
					taken out{#if wider.speeches !== null}, along with the {count(wider.speeches)} speeches whose
						only match it was{/if}. Select <em>{measureLabel(wider.term)}</em> above to read the word
					in every form.
				</p>
			{/if}
			{#if unmapped.length}
				<p>
					{count(unmapped.length)} of the ranked speakers appear on no map: {unmapped
						.slice(0, 4)
						.map((entry) => shortCountry(entry.speaker.country_org))
						.join(', ')}{unmapped.length > 4 ? ' and others' : ''} have no map position under the source
					classification and geography lookup. They remain in the table.
				</p>
			{/if}
			{#each collisions as [code, holders] (code)}
				<p>
					{code} is shared by {holders.join(' and ')}. Different source labels can share a geography
					lookup, including a successor location for a historical state. Their speech counts and
					denominators remain separate.
				</p>
			{/each}
		{/snippet}

		<section class="table-wrap">
			<h3 class="sr-only">Speakers, ranked</h3>
			{#if unmapped.length}
				<details class="map-coverage">
					<summary>Why {unmapped.length} ranked speakers are not mapped</summary>
					<p>
						The map uses source state flags and reviewed locations. Missing locations do not remove
						a speaker from the ranking.
					</p>
					<ul>
						{#each unmapped as entry (entry.speaker.country_org)}
							<li>
								{shortCountry(entry.speaker.country_org)} — {entry.speaker.entity_type === 'state'
									? 'no reviewed geographic match'
									: 'not classified as a state in the source flags'}.
							</li>
						{/each}
					</ul>
				</details>
			{/if}
			<label>Find a ranked speaker <input type="search" bind:value={speakerSearch} /></label>
			<nav class="ranking-pages" aria-label="Speaker ranking pages">
				<button type="button" disabled={rankingPage === 1} onclick={() => rankingPage--}
					>Previous</button
				>
				<span role="status"
					>{matchingRows.length ? (rankingPage - 1) * pageSize + 1 : 0}–{Math.min(
						rankingPage * pageSize,
						matchingRows.length
					)} of {matchingRows.length} speakers · Page {rankingPage} of {pageCount}</span
				>
				<button type="button" disabled={rankingPage >= pageCount} onclick={() => rankingPage++}
					>Next</button
				>
			</nav>
			{#if !matchingRows.length}<p>No ranked speakers match this search.</p>{/if}
			<div class="scroll">
				<table>
					<caption class="sr-only">
						Speakers ranked by {label(result.order)} for {measureLabel(measure)}, {result.period
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
						{#each visibleRows as entry (entry.speaker.country_org)}
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
				bind:this={countryMap}
				points={drawn}
				selected={chosen?.speakers[0].speaker.country_org ?? null}
				onselect={(point) => {
					speakerSearch = '';
					selected = point?.speakers[0].speaker.country_org ?? null;
				}}
				describe={describeSpeaker}
			/>
		{/if}
	</Figure>

	{#if chosen}
		<aside class="picked">
			<h2>{shortCountry(selected ?? chosen.speakers[0].speaker.country_org)}</h2>
			{#if chosen.speakers.length > 1}
				<p class="stacked">
					This point carries {chosen.speakers.length} speakers, which share both a map position and a
					country code. They stay separate rows, each measured against its own speeches:
					{chosen.speakers.map((s) => s.speaker.country_org).join(', ')}.
				</p>
			{/if}
			<dl>
				{#each chosen.speakers as entry (entry.speaker.country_org)}
					{@const link = occurrences(artefact, measure, entry)}
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
						{#if link}
							<dd class="read">
								<a class="more" href="{resolve('/concordance')}?{link.query}">
									Read the occurrences <Icon icon={ChevronRight} />
								</a>
							</dd>
						{/if}
					</div>
				{/each}
			</dl>
			<p class="scoped">
				Each link carries this speaker and {result.period?.label ?? period} through to the concordance,
				so what opens is the evidence behind the rate above rather than the whole corpus.
				{#if wider}
					The lines are <em>{measureLabel(wider.term)}</em>'s: this measure subtracts
					<em>{wider.subtracted.map(measureLabel).join(' and ')}</em> from it, and only a lexicon term
					has a concordance, so they hold the occurrences the rate leaves out as well as those it counts.
				{/if}
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
	.table-wrap > label,
	.map-coverage {
		font-family: var(--sans);
		font-size: var(--step--1);
	}
	.map-coverage {
		margin-bottom: var(--sp-3);
	}
	.ranking-pages {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 1rem;
		margin-block: 1rem;
		font-family: var(--sans);
		font-size: var(--step--1);
	}
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
