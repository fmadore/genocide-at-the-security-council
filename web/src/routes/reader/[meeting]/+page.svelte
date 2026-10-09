<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import {
		kwic,
		kwicIndex,
		meeting as loadMeeting,
		meetingOf,
		speechOf,
		usageOccurrences
	} from '$lib/data';
	import {
		concordanceQuery,
		occurrenceInResult,
		readConcordanceState,
		referentMap
	} from '$lib/concordance';
	import { USAGE_TERM } from '$lib/usage';
	import { visible } from '$lib/reader';
	import { Resource } from '$lib/resource.svelte';
	import { readScope, speechInScope } from '$lib/scope';
	import { occurrenceItem, speechItem } from '$lib/basket';
	import { basket } from '$lib/basket.svelte';
	import { citationOf, occurrenceQuotation, toBibtex, toCslJson, toRis } from '$lib/citation';
	import { filename, save } from '$lib/export';
	import {
		count,
		interpretedFrom,
		isoDate,
		meetingLabel,
		namedLanguage,
		shortCountry,
		termLabel,
		unSearch
	} from '$lib/format';
	import { SITE_NAME, type PageMetadata } from '$lib/seo';
	import type { KwicLine, Meeting, Speech } from '$lib/types';
	import { tick } from 'svelte';
	import { SvelteSet, SvelteURLSearchParams } from 'svelte/reactivity';

	const basename = $derived(page.params.meeting!);
	const wantedSpeech = $derived(page.url.searchParams.get('speech'));
	const wantedTerm = $derived(page.url.searchParams.get('term'));
	const wantedOccurrence = $derived(page.url.searchParams.get('occurrence'));

	/* The record is emptied whenever another meeting, speech or occurrence is
	   asked for, so the page never shows one meeting under another's address. */
	const meetingRecord = new Resource<Meeting>();
	const record = $derived(meetingRecord.value);
	const failure = $derived(meetingRecord.failure);
	let registers = $state<Record<string, string>>({});
	let open = new SvelteSet<string>();
	let showAddress = $state(false);
	let copyState = $state<'idle' | 'copied' | 'failed'>('idle');
	let quoteState = $state<'idle' | 'copied' | 'failed'>('idle');
	let selectedLine = $state<KwicLine | null>(null);
	let resultNavigation = $state<{
		position: number;
		total: number;
		previous: string | null;
		next: string | null;
	} | null>(null);

	$effect(() => {
		const wanted = basename;
		const speech = wantedSpeech;
		const occurrence = wantedOccurrence;
		copyState = 'idle';
		quoteState = 'idle';
		void meetingRecord
			.load(() => loadMeeting(wanted), { clear: true })
			.then(async (loaded) => {
				if (!loaded) return;
				const target = speech ?? loaded.speeches.find((s) => hasHits(s))?.id;
				open.clear();
				if (target) open.add(target);
				await tick();
				const exact = occurrence ? document.querySelector<HTMLElement>('[data-occurrence]') : null;
				(exact ?? document.getElementById(target ?? ''))?.scrollIntoView({ block: 'center' });
			});
	});

	$effect(() => {
		const occurrence = wantedOccurrence;
		const term = wantedTerm;
		const search = page.url.search;
		resultNavigation = null;
		selectedLine = null;
		if (!occurrence || !term) return;
		const state = readConcordanceState(new URLSearchParams(search));
		/* The referent filter reads the published run's placements, exactly as
		   the concordance does, and only for the term that run annotated.
		   Without them it keeps nothing, so previous and next would vanish while
		   the concordance the reader came from still listed the occurrence. */
		const referents =
			state.referent && term === USAGE_TERM
				? usageOccurrences()
						.then((file) => referentMap(file.occurrences))
						.catch(() => null)
				: Promise.resolve(null);
		Promise.all([kwic(term), referents])
			.then(([file, placements]) => {
				if (occurrence !== wantedOccurrence || search !== page.url.search) return;
				const found = occurrenceInResult(file.lines, state, occurrence, placements);
				selectedLine = found.line;
				resultNavigation = found.position;
			})
			.catch(() => {
				// Navigation is an enhancement. The meeting evidence remains usable if
				// the term-specific result file is unavailable to a direct permalink.
			});
	});

	$effect(() => {
		kwicIndex()
			.then((index) => {
				registers = Object.fromEntries(index.terms.map((t) => [t.term, t.register]));
			})
			.catch(() => {
				registers = {};
			});
	});

	const hasHits = (speech: Speech) => Object.keys(speech.hits).length > 0;

	/** A run of the record cut at its paragraph breaks, for the pause drawn between them. */
	const paragraphs = (text: string) => text.split('\n');

	// Writable derived: seeded from the URL the reader arrived on, then owned by
	// the select below.
	let filterTerm = $derived(wantedTerm);

	/* The occurrence the URL names, which `$lib/reader` marks as the exact one. */
	const selection = $derived({ occurrence: wantedOccurrence, term: wantedTerm });

	const termsHere = $derived(
		record ? [...new Set(record.speeches.flatMap((s) => Object.keys(s.hits)))].sort() : []
	);

	const totalHits = $derived(
		record
			? record.speeches.reduce(
					(sum, s) =>
						sum +
						Object.entries(s.hits)
							.filter(([t]) => !filterTerm || t === filterTerm)
							.reduce((n, [, spans]) => n + spans.length, 0),
					0
				)
			: 0
	);

	function toggle(id: string) {
		if (open.has(id)) open.delete(id);
		else open.add(id);
	}

	function openAll() {
		for (const speech of record?.speeches ?? []) open.add(speech.id);
	}

	async function copyOccurrenceLink() {
		try {
			await navigator.clipboard.writeText(page.url.href);
			copyState = 'copied';
		} catch {
			copyState = 'failed';
		}
	}

	async function copyQuotation() {
		if (!selectedLine) return;
		try {
			await navigator.clipboard.writeText(occurrenceQuotation(selectedLine, page.url.href));
			quoteState = 'copied';
		} catch {
			quoteState = 'failed';
		}
	}

	/**
	 * Keep the selected occurrence, enriched with what only the reader knows.
	 *
	 * The concordance can snapshot the delegation; this route has the meeting
	 * loaded, so it can add the personal speaker and their role. Same item
	 * shape either way — an item added here is simply better described.
	 */
	function keepOccurrence() {
		const line = selectedLine;
		if (!line || !record) return;
		const speech = record.speeches.find((entry) => entry.id === speechOf(line.id));
		const meta = record.meta;
		basket.add(
			occurrenceItem(
				line,
				filterTerm ?? termsHere[0] ?? '',
				new Date().toISOString(),
				{
					lexiconVersion: Number.isFinite(meta.lexicon_version)
						? Number(meta.lexicon_version)
						: null,
					analysisHash: typeof meta.analysis_hash === 'string' ? meta.analysis_hash : null
				},
				speech
			)
		);
	}

	/**
	 * Hand the selected occurrence to a reference manager.
	 *
	 * Built here rather than in the concordance because this route has the
	 * meeting loaded, so the citation can name the representative and not only
	 * the delegation. The accessed date is passed in rather than read inside the
	 * builders, which is what keeps their fixtures exact.
	 */
	function downloadCitation(format: 'json' | 'ris' | 'bib') {
		const line = selectedLine;
		if (!line || !record) return;
		const speech = record.speeches.find((entry) => entry.id === speechOf(line.id)) ?? null;
		const citation = citationOf(line, speech, page.url.href, new Date().toISOString().slice(0, 10));
		const [text, type] =
			format === 'json'
				? [toCslJson(citation), 'application/json']
				: format === 'ris'
					? [toRis(citation), 'application/x-research-info-systems']
					: [toBibtex(citation), 'application/x-bibtex'];
		save(
			new Blob([text], { type: `${type};charset=utf-8` }),
			filename(['unsc', 'citation', line.id], format)
		);
	}

	/** Keep a whole speech, for the argument that is not one sentence long. */
	function keepSpeech(speech: Speech) {
		if (!record) return;
		const meta = record.meta;
		basket.add(
			speechItem(record, speech, new Date().toISOString(), {
				lexiconVersion: Number.isFinite(meta.lexicon_version) ? Number(meta.lexicon_version) : null,
				analysisHash: typeof meta.analysis_hash === 'string' ? meta.analysis_hash : null
			})
		);
	}

	function occurrenceHref(id: string): string {
		const params = new SvelteURLSearchParams(page.url.searchParams);
		params.set('speech', speechOf(id));
		params.set('occurrence', id);
		return `${resolve('/reader/[meeting]', { meeting: meetingOf(id) })}?${params}`;
	}

	const preview = (speech: Speech) =>
		speech.text.slice(speech.body_start, speech.body_start + 180).replace(/\s+/g, ' ') + '…';

	// The register names the mark's rule; `app.css` owns what each one looks
	// like, so the drawing lives in one place rather than in an inline colour.
	const registerFor = (terms: string[]) => registers[terms[0]!] ?? 'core';

	/**
	 * The marginal apparatus: what is marked in this record, counted by register,
	 * and how much of it was spoken in another language before it was written
	 * down in this one.
	 *
	 * Ordered by the lexicon's own order rather than by size, so the same
	 * registers sit in the same places from one meeting to the next.
	 */
	const ORDER = ['core', 'legal', 'preventive', 'commemorative', 'contentious', 'accountability'];

	const marksHere = $derived.by(() => {
		const tally: Record<string, number> = {};
		for (const speech of record?.speeches ?? []) {
			for (const [term, spans] of Object.entries(speech.hits)) {
				if (filterTerm && term !== filterTerm) continue;
				const register = registers[term] ?? 'core';
				tally[register] = (tally[register] ?? 0) + spans.length;
			}
		}
		return ORDER.filter((r) => tally[r]).map((r) => ({ register: r, n: tally[r]! }));
	});

	/* --- The whole debate, under the reading set the masthead selected -------
	   R9 promotes this route from an escape hatch to a destination: the record
	   is already every speech in the meeting with each one's vocabulary marked,
	   and what it lacked was the debate's own shape — who sat in it, what each
	   delegation used, and which speeches the selected reading set holds.
	   Recomputed from the offsets already loaded rather than fetched: a second
	   artefact would be a second answer to a question this file can answer. */
	const scope = $derived(readScope(page.url.searchParams));

	/**
	 * The concordance the reader came from, as they left it.
	 *
	 * The link that brought them here carries the concordance's whole state —
	 * `readerQuery` writes it so the previous and next occurrence walk the same
	 * result set — and the way back used to throw it away: "Concordance" opened
	 * an unfiltered list of 51,000 lines to a reader who had narrowed to Rwanda
	 * in 1994 (review of 14 September 2026, still open on the 19th). The same
	 * state is read back out of this URL, with the reading set beside it, so the
	 * return trip lands on the list the reader left.
	 */
	const concordanceHref = $derived.by(() => {
		const search = concordanceQuery(page.url.searchParams).toString();
		return `${resolve('/concordance')}${search ? `?${search}` : ''}`;
	});
	const saysTheWord = $derived((record?.speeches ?? []).some((s) => 'genocide' in s.hits));
	const inScope = $derived(
		new Set(
			(record?.speeches ?? [])
				.filter((s) => speechInScope(s.hits, scope, saysTheWord))
				.map((s) => s.id)
		)
	);

	/* Ordered by how much of the record a delegation holds, so the debate reads
	   as a debate rather than as an alphabet. The silent ones stay in it. */
	const roll = $derived(
		[...(record?.delegations ?? [])].sort(
			(a, b) => b.speeches - a.speeches || a.country.localeCompare(b.country)
		)
	);

	/* The reader's toolbar sticks under the masthead, and on a phone it is
	   400px tall — select, checkbox, six buttons and a prev/next pair, wrapped
	   over five rows. Everything on this page that a link can aim at budgeted
	   `--masthead-h + --contents-h + 1rem` = 72px of sticky chrome for the
	   landing, so a deep link to an occurrence at 390px parked the marked word
	   7px behind the bar it was supposed to be under. The bar wraps, so its
	   height is measured rather than declared, exactly as the masthead's is. */
	let toolbar = $state.raw<HTMLElement>();

	$effect(() => {
		const element = toolbar;
		if (!element) {
			document.documentElement.style.setProperty('--toolbar-h', '0px');
			return;
		}
		const observer = new ResizeObserver(([entry]) => {
			// Only a bar that is actually stuck to the top costs a link any room.
			// Below 48rem it scrolls away with the page, and a landing that still
			// budgeted 400px for it would park the marked word at the foot of the
			// window with nothing under it to read.
			const stuck = getComputedStyle(entry!.target).position === 'sticky';
			document.documentElement.style.setProperty(
				'--toolbar-h',
				stuck ? `${entry!.target.getBoundingClientRect().height}px` : '0px'
			);
		});
		observer.observe(element);
		return () => {
			observer.disconnect();
			document.documentElement.style.setProperty('--toolbar-h', '0px');
		};
	});

	const interpreted = $derived(
		(record?.speeches ?? []).filter((s) => interpretedFrom(s.language)).length
	);
	const readerMetadata = $derived<PageMetadata>({
		path: `/reader/${encodeURIComponent(basename)}/`,
		title: record
			? `${record.spv} — ${record.topic} — ${SITE_NAME}`
			: `Meeting record — ${SITE_NAME}`,
		description: record
			? `Read ${record.spv}, ${record.topic}, with every matched occurrence highlighted in its full UN Security Council speech.`
			: 'Read a UN Security Council meeting record and its matched genocide-related vocabulary in full speech context.'
	});
</script>

<PageMeta meta={readerMetadata} />

{#if failure}
	<div class="notice">
		<h1>The meeting record could not be loaded</h1>
		<p>{failure}</p>
		<p><a href={concordanceHref}>Back to the concordance</a></p>
	</div>
{:else if !record}
	<p class="loading">Loading the meeting record…</p>
{:else}
	<article class="reader">
		<header>
			<p class="crumb">
				<a href={concordanceHref}>Concordance</a><Icon icon={ChevronRight} />meeting record
			</p>
			<div class="titling">
				<div>
					<!-- Rule 06: the symbol is the address, and it is the first thing
					     on the page because it is what a reader would cite. -->
					<p class="spv">{meetingLabel(record.spv)}</p>
					<h1>{record.topic}</h1>
					<p class="meta">
						{isoDate(record.date)} · {count(record.speeches.length)} speeches · agenda item
						<strong>{record.agenda}</strong>
						{#if record.region}({record.region}){/if}
					</p>
				</div>
				<p class="jump">
					<a href={unSearch(record.spv)}>UN Digital Library<Icon icon={ExternalLink} /></a>
					<a href="{resolve('/concordance')}?spv={encodeURIComponent(record.spv)}"
						>Concordance for this meeting</a
					>
				</p>
			</div>
		</header>

		<!-- The apparatus, under the header, as a full-width band on the twelve
		     column grid: the register legend is the key to every mark below it and
		     has to be readable before the record is. From 64rem it is the column
		     beside the record instead — the one width the record's measure leaves
		     unused, so no plate gives anything up for it. First in the source
		     either way, so it is read before the record. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex (From 64rem the notes are a column that scrolls on its own, and a keyboard has to be able to scroll it.) -->
		<aside class="apparatus grid" tabindex="0">
			<div class="note">
				<span class="label">Highlights in this record</span>
				{#if marksHere.length}
					<ul class="tally-list">
						{#each marksHere as entry (entry.register)}
							<li>
								<span class="swatch" data-register={entry.register}></span>
								<span class="name">{entry.register}</span>
								<span class="n">{count(entry.n)}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="prose">No term from the word list is highlighted under the current filter.</p>
				{/if}
			</div>

			<div class="note">
				<span class="label">The reading set here</span>
				<p class="prose">
					{count(inScope.size)} of {count(record.speeches.length)} speeches belong to the reading set
					selected at the top of the page. The full meeting remains available, including speeches outside
					that set.
				</p>
			</div>

			<div class="note">
				<span class="label">Affiliations, speech counts and terms</span>
				<ul class="roll">
					{#each roll as delegation (delegation.country)}
						<li>
							<span class="name">{shortCountry(delegation.country)}</span>
							<span class="n">{count(delegation.speeches)}</span>
							<span class="said"
								>{delegation.terms.length
									? delegation.terms.map(termLabel).join(', ')
									: 'no term on the list'}</span
							>
						</li>
					{/each}
				</ul>
			</div>

			<div class="note">
				<span class="label">Delivery language</span>
				<p class="prose">
					The record is in English. {#if interpreted > 0}{count(interpreted)}
						{interpreted === 1 ? 'speech carries' : 'speeches carry'} a non-English language label.{/if}
					The source does not identify the language each speech was delivered in, so a speech may reach
					this record through interpretation.
				</p>
			</div>

			<div class="note">
				<span class="label">The text</span>
				<p class="prose">
					The text comes from the published dataset of verbatim records. Scanning and text
					processing can introduce errors. Highlights identify the search matches used in the
					counts. Consult the UN Digital Library record when checking a quotation.
				</p>
			</div>

			<div class="note src">
				<span class="label">Source</span>
				<p class="symbol">09_export_speeches.py<br />→ speeches/{record.basename}.json.gz</p>
			</div>
		</aside>

		<div class="toolbar" bind:this={toolbar}>
			<label>
				Highlight
				<select bind:value={filterTerm}>
					<option value={null}>All {termsHere.length} terms present</option>
					{#each termsHere as t (t)}<option value={t}>{termLabel(t)}</option>{/each}
				</select>
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={showAddress} /> Show opening greetings
			</label>
			<span class="tally">{count(totalHits)} highlighted occurrences in this meeting</span>
			{#if wantedOccurrence}
				<span class="selected">Selected <span class="symbol">{wantedOccurrence}</span></span>
				<button class="ghost" onclick={copyOccurrenceLink}>
					{copyState === 'copied'
						? 'Occurrence link copied'
						: copyState === 'failed'
							? 'Could not copy link'
							: 'Copy occurrence link'}
				</button>
			{/if}
			{#if selectedLine}
				<button class="ghost" onclick={copyQuotation}>
					{quoteState === 'copied'
						? 'Quotation copied'
						: quoteState === 'failed'
							? 'Could not copy quotation'
							: 'Copy quotation + citation'}
				</button>
				<button class="ghost" disabled={basket.has(selectedLine.id)} onclick={keepOccurrence}>
					{basket.has(selectedLine.id) ? 'In the basket' : 'Add to basket'}
				</button>
				<span class="cites">
					<span class="label">Export citation</span>
					<button class="ghost" onclick={() => downloadCitation('json')}>CSL-JSON</button>
					<button class="ghost" onclick={() => downloadCitation('ris')}>RIS</button>
					<button class="ghost" onclick={() => downloadCitation('bib')}>BibTeX</button>
				</span>
			{/if}
			{#if resultNavigation}
				<nav class="result-nav" aria-label="Occurrences in the current concordance results">
					{#if resultNavigation.previous}
						<a href={occurrenceHref(resultNavigation.previous)}>Previous occurrence</a>
					{/if}
					<span class="position">{resultNavigation.position} of {resultNavigation.total}</span>
					{#if resultNavigation.next}
						<a href={occurrenceHref(resultNavigation.next)}>Next occurrence</a>
					{/if}
				</nav>
			{/if}
			<button class="ghost" onclick={openAll}>Open every speech</button>
		</div>

		<!-- The record itself, at the prose measure, under the apparatus band. -->
		<ol class="speeches">
			{#each record.speeches as speech (speech.id)}
				{@const hits = Object.entries(speech.hits).filter(([t]) => !filterTerm || t === filterTerm)}
				{@const marked = hits.reduce((n, [, spans]) => n + spans.length, 0)}
				<li id={speech.id} class:target={speech.id === wantedSpeech}>
					<!-- A heading round the button, the accordion pattern: 179 speeches
					     with no heading below the H1 left a screen-reader user no way
					     to skim the debate by speaker (review of 19 September 2026). -->
					<h2 class="speech-heading">
						<button
							class="head"
							onclick={() => toggle(speech.id)}
							aria-expanded={open.has(speech.id)}
						>
							<span class="n">{speech.n}</span>
							<span class="who">
								<strong>{speech.speaker ?? shortCountry(speech.country)}</strong>
								<span class="sub">
									{shortCountry(speech.country)}
									· {speech.group}
									{#if speech.role}· {speech.role}{/if}
									{#if namedLanguage(speech.language)}· spoke in {speech.language}{/if}
								</span>
							</span>
							<span class="tags">
								{#if inScope.has(speech.id)}
									<span class="set" title="In the selected reading set">in set</span>
								{/if}
								{#if marked}
									<span class="count">{marked}</span>
								{/if}
								<span class="chev" class:down={open.has(speech.id)}
									><Icon icon={ChevronRight} /></span
								>
							</span>
						</button>
					</h2>

					{#if open.has(speech.id)}
						<div class="text">
							{#each visible(speech, filterTerm, selection, showAddress) as segment, i (i)}
								{#if segment.terms.length}
									<mark
										class:occurrence={segment.exact}
										data-occurrence={segment.exact ? wantedOccurrence : undefined}
										data-register={registerFor(segment.terms)}
										title={segment.exact
											? `Selected occurrence ${wantedOccurrence}`
											: `${segment.terms.map(termLabel).join(', ')} · ${registerFor(segment.terms)}`}
										>{segment.text}</mark
									>
								{:else}{#each paragraphs(segment.text) as piece, k (k)}{#if k}<span class="pause"
											></span>{/if}{piece}{/each}{/if}
							{/each}
						</div>
						<p class="speech-meta">
							<span class="symbol">{speech.id}</span> · {count(speech.words)} words
							{#if Object.keys(speech.hits).length}
								· {Object.keys(speech.hits).map(termLabel).join(', ')}
							{/if}
							<button
								type="button"
								class="ghost keep"
								disabled={basket.has(speech.id)}
								onclick={() => keepSpeech(speech)}
							>
								{basket.has(speech.id) ? 'In the basket' : 'Add this speech to the basket'}
							</button>
						</p>
					{:else}
						<p class="preview">{preview(speech)}</p>
					{/if}
				</li>
			{/each}
		</ol>
	</article>
{/if}

<style>
	.notice,
	.loading {
		max-width: var(--measure);
		margin: var(--sp-7) auto;
		text-align: center;
		color: var(--ink-2);
	}

	.crumb {
		display: flex;
		align-items: center;
		gap: 0.25em;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		margin-bottom: var(--sp-3);
	}

	.titling {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: var(--sp-6);
		align-items: start;
		padding-bottom: var(--sp-4);
		border-bottom: var(--hair) solid var(--rule-strong);
	}

	@media (max-width: 44rem) {
		.titling {
			grid-template-columns: minmax(0, 1fr);
			gap: var(--sp-3);
		}
	}

	/* Rule 06: the citation that produced the page, in mono, above its title. */
	.spv {
		margin: 0;
		font-family: var(--mono);
		font-size: var(--step-2);
		letter-spacing: -0.01em;
		font-variant-numeric: tabular-nums;
		color: var(--ink);
	}

	header h1 {
		font-size: var(--step-3);
		margin: var(--sp-2) 0 0;
		max-width: 28ch;
	}

	.meta {
		margin: var(--sp-1) 0 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.jump {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: var(--sp-1);
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		text-align: right;
	}

	.jump a {
		display: inline-flex;
		align-items: center;
		gap: 0.3em;
	}

	@media (max-width: 44rem) {
		.jump {
			align-items: flex-start;
			text-align: left;
		}
	}

	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-3) var(--sp-5);
		align-items: center;
		padding: var(--sp-3) 0;
		margin-bottom: var(--sp-5);
		border-bottom: var(--hair) solid var(--rule-strong);
		position: sticky;
		/* The measured masthead height, not a number that was true of one
		   viewport: the masthead wraps, and a hard-coded 3.4rem left the bar
		   sliding under it at every width where it wrapped to two lines. */
		top: var(--masthead-h);
		background: var(--paper);
		z-index: 2;
	}

	/* Below 48rem the bar wraps to five rows and stands 400px tall on a 780px
	   window: stuck, it is 51% of the viewport, it follows the record down all
	   24,000px of it, and a deep link to an occurrence lands behind it. The
	   programme allows two sticky bands, the masthead and the contents; this is
	   a third, and it is the one that can afford to scroll away. The citation
	   cluster is not what a reader came for, and it is a screen away, not a
	   page. The measurement above publishes zero for a bar that is not stuck, so
	   nothing aiming at a speech budgets room the bar no longer occupies. */
	@media (max-width: 48rem) {
		.toolbar {
			position: static;
		}
	}

	label {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	select {
		max-width: 18rem;
	}

	.tally {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
		margin-left: auto;
	}

	.selected {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.result-nav {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.result-nav .position {
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
	}

	/* Three formats of one thing, so they are grouped under one label rather
	   than sitting in the toolbar as three unrelated buttons. */
	.cites {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	/* The apparatus voice, inline in the bar: `.label` in `app.css` now carries
	   the whole of it, so nothing is set here but the line it sits on. */
	.cites .label {
		display: inline;
	}

	/* Every chip on the site: one ink hairline, 2rem, no fill until it is
	   pressed. The register hues and the state colours never reach a control. */
	.ghost {
		display: inline-flex;
		align-items: center;
		background: var(--paper);
		border: var(--hair) solid var(--ink);
		padding: 0 var(--sp-3);
		min-height: 2rem;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink);
		cursor: pointer;
	}

	.ghost:hover {
		background: var(--paper-sunk);
	}

	.ghost:disabled {
		color: var(--ink-3);
		border-color: var(--rule);
		cursor: default;
	}

	/* The record is a column of prose, not a plate: with the apparatus lifted
	   out of the margin the list would otherwise run the full twelve columns and
	   fling every speaker's tags to the far edge. The 2.9rem is the number
	   column the speech text is already indented past. */
	.speeches {
		list-style: none;
		margin: 0;
		padding: 0;
		min-width: 0;
		max-width: calc(var(--measure) + 2.9rem);
	}

	/* Where a deep link parks a speech: under everything stuck to the top of the
	   window, and the same value as the occurrence anchor below, which used to
	   disagree with it by a whole rem. */
	.speeches li {
		border-bottom: var(--hair) solid var(--rule);
		padding-bottom: var(--sp-3);
		margin-bottom: var(--sp-3);
		scroll-margin-top: calc(
			var(--masthead-h) + var(--contents-h) + var(--toolbar-h, 0px) + var(--sp-4)
		);
	}

	/* The speech a link asked for, set on the sunk stripe rather than behind a
	   coloured bar: the record carries no rules on its leading edge. */
	.speeches li.target {
		background: var(--paper-sunk);
		padding-inline: var(--sp-3);
		margin-inline: calc(-1 * var(--sp-3));
	}

	/* The heading carries the button and no voice of its own: the speaker line
	   is set as it was, and the heading is what an outline of the page reads. */
	.speech-heading {
		margin: 0;
		font: inherit;
		letter-spacing: normal;
	}

	.head {
		display: grid;
		grid-template-columns: 2.2rem minmax(0, 1fr) auto;
		gap: var(--sp-3);
		align-items: baseline;
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		min-height: 0;
		padding: var(--sp-2) 0;
		cursor: pointer;
		font-family: inherit;
		color: inherit;
	}

	.head:hover .who strong {
		color: var(--blue);
	}

	.n {
		color: var(--ink-3);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums lining-nums;
	}

	/* The speaker line is apparatus, not text: it names who is talking, in the
	   apparatus voice, and the record below it carries the reading. */
	.who strong {
		display: block;
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 700;
	}

	.sub {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.tags {
		display: flex;
		align-items: center;
		gap: var(--sp-2);
	}

	/* Set as the occurrence count is, but hollow: it says which population a
	   speech is in, not how many times anything was said. */
	.set {
		border: var(--hair) solid var(--ink);
		color: var(--ink-2);
		padding: 0.05rem 0.4rem;
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	.count {
		background: var(--mark);
		color: var(--ink);
		padding: 0.05rem 0.4rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums lining-nums;
	}

	.chev {
		color: var(--ink-3);
		display: inline-flex;
		transition: transform var(--dur) var(--ease);
	}

	.chev.down {
		transform: rotate(90deg);
	}

	.preview {
		margin: 0 0 0 2.9rem;
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	/* The long-form reading role, the one surface on the site read at length:
	   the body face at a looser 1.68 leading, and a pause where the record
	   starts a new paragraph. The record marks a paragraph with a single line
	   break and never a blank line, so under `pre-wrap` a speech of thirteen
	   paragraphs read as ninety lines without a pause, in first-person testimony
	   about mass atrocity (review of 19 September 2026). The break is replaced
	   by a block of space rather than by a second line: a blank line is 1.68em,
	   which reads as a section, not a paragraph. */
	.text {
		margin: var(--sp-2) 0 var(--sp-3) 2.9rem;
		font-family: var(--sans);
		font-size: var(--step-0);
		line-height: 1.68;
		white-space: pre-wrap;
		max-width: var(--measure);
	}

	.pause {
		display: block;
		height: var(--sp-3);
	}

	/* The one occurrence a link asked for. Blue is the interaction layer and
	   this outline is the only thing on the page that answers a query. */
	.text mark.occurrence {
		outline: 2px solid var(--blue);
		outline-offset: 2px;
		scroll-margin-top: calc(
			var(--masthead-h) + var(--contents-h) + var(--toolbar-h, 0px) + var(--sp-4)
		);
	}

	.speech-meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-3);
		margin: 0 0 0 2.9rem;
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	/* ---- the apparatus ---------------------------------------------------- */

	/* A band under the header on the twelve-column grid, opened by a rule: the
	   same shape a plate's notes take in `Figure.svelte`, and for the same
	   reason — the notes belong under the thing they are about, at its width,
	   not in a margin cut out of it. */
	.apparatus {
		row-gap: var(--sp-5);
		margin-bottom: var(--sp-6);
		padding-top: var(--sp-3);
		border-top: var(--hair) solid var(--ink);
	}

	/* From 64rem the record and its notes stand side by side. The record keeps
	   its measure, which no width improves, and at 1440px that left 706px of
	   empty column beside it, all on one side (review of 19 September 2026).
	   The notes take that column and stay beside the record as it scrolls: the
	   register key is then next to the marks it explains for the whole of a
	   24,000px debate, rather than a screen above the first of them. They take
	   the space the prose cannot use, which is the opposite of the margin the
	   plates gave up: no figure is narrowed by them. */
	@media (min-width: 64rem) {
		.reader {
			display: grid;
			grid-template-columns: minmax(0, calc(var(--measure) + 2.9rem)) minmax(16rem, 1fr);
			grid-template-areas:
				'header header'
				'toolbar toolbar'
				'record notes';
			column-gap: var(--sp-7);
			align-items: start;
		}

		.reader > header {
			grid-area: header;
		}

		.toolbar {
			grid-area: toolbar;
		}

		.speeches {
			grid-area: record;
		}

		.apparatus {
			grid-area: notes;
			position: sticky;
			top: calc(var(--masthead-h) + var(--toolbar-h, 0px) + var(--sp-4));
			max-height: calc(100vh - var(--masthead-h) - var(--toolbar-h, 0px) - var(--sp-6));
			overflow-y: auto;
			scrollbar-width: thin;
			margin-bottom: 0;
		}

		.apparatus .note {
			grid-column: span 12;
		}
	}

	.note {
		grid-column: span 12;
	}

	@media (min-width: 48rem) {
		.note {
			grid-column: span 6;
		}
	}

	/* `.label` in `app.css` sets the apparatus voice; only the space under it
	   belongs to this page. */
	.note .label {
		margin-bottom: var(--sp-2);
	}

	.prose {
		margin: 0;
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	/* Capped rather than run to the full six columns: a count set against the far
	   edge of a 41rem cell has left its name behind. */
	.tally-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--sp-1);
		max-width: 22rem;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.tally-list li {
		display: grid;
		grid-template-columns: 0.625rem minmax(0, 1fr) auto;
		gap: var(--sp-2);
		align-items: center;
	}

	.tally-list .n {
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
	}

	/* Every delegation in the record, the silent ones included: a delegation's
	   silence is only legible against the debate it sat in. */
	.roll {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--1);
		max-width: 22rem;
		max-height: 22rem;
		overflow-y: auto;
	}

	.roll li {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		column-gap: var(--sp-2);
	}

	.roll .name {
		color: var(--ink-2);
	}

	.roll .n {
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums lining-nums;
		color: var(--ink-3);
	}

	.roll .said {
		grid-column: 1 / -1;
		color: var(--ink-3);
		font-size: var(--step--2);
	}

	/* The same six data colours the marks in the text carry. */
	.swatch {
		width: 0.625rem;
		height: 0.625rem;
		background: var(--ink);
	}

	.swatch[data-register='legal'] {
		background: var(--reg-legal);
	}
	.swatch[data-register='preventive'] {
		background: var(--reg-preventive);
	}
	.swatch[data-register='commemorative'] {
		background: var(--reg-commemorative);
	}
	.swatch[data-register='contentious'] {
		background: var(--reg-contentious);
	}
	.swatch[data-register='accountability'] {
		background: var(--reg-accountability);
	}

	/* One note among the others in the band: the band's own rule opens all six,
	   and a second rule over this one alone read as a footer inside a column. */
	.src .symbol {
		margin: 0;
		line-height: 1.5;
		color: var(--ink-2);
		overflow-wrap: anywhere;
	}
</style>
