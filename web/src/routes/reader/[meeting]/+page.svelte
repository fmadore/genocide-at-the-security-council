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
		occurrenceOf,
		speechOf
	} from '$lib/data';
	import { filterConcordance, readConcordanceState } from '$lib/concordance';
	import { occurrenceItem, speechItem } from '$lib/basket';
	import { basket } from '$lib/basket.svelte';
	import { occurrenceQuotation } from '$lib/citation';
	import { count, isoDate, shortCountry, termLabel, unSearch } from '$lib/format';
	import { SITE_NAME, type PageMetadata } from '$lib/seo';
	import type { KwicLine, Meeting, Speech } from '$lib/types';
	import { tick } from 'svelte';
	import { SvelteSet, SvelteURLSearchParams } from 'svelte/reactivity';

	const basename = $derived(page.params.meeting!);
	const wantedSpeech = $derived(page.url.searchParams.get('speech'));
	const wantedTerm = $derived(page.url.searchParams.get('term'));
	const wantedOccurrence = $derived(page.url.searchParams.get('occurrence'));

	let record = $state<Meeting | null>(null);
	let failure = $state<string | null>(null);
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
		record = null;
		failure = null;
		copyState = 'idle';
		quoteState = 'idle';
		loadMeeting(wanted)
			.then(async (loaded) => {
				if (wanted !== basename) return;
				record = loaded;
				const target = speech ?? loaded.speeches.find((s) => hasHits(s))?.id;
				open.clear();
				if (target) open.add(target);
				await tick();
				const exact = occurrence ? document.querySelector<HTMLElement>('[data-occurrence]') : null;
				(exact ?? document.getElementById(target ?? ''))?.scrollIntoView({ block: 'center' });
			})
			.catch((error: Error) => {
				if (wanted === basename) failure = error.message;
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
		kwic(term)
			.then((file) => {
				if (occurrence !== wantedOccurrence || search !== page.url.search) return;
				const ordered = filterConcordance(file.lines, state).lines;
				const index = ordered.findIndex((line) => line.id === occurrence);
				if (index < 0) return;
				selectedLine = ordered[index];
				resultNavigation = {
					position: index + 1,
					total: ordered.length,
					previous: ordered[index - 1]?.id ?? null,
					next: ordered[index + 1]?.id ?? null
				};
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

	interface Segment {
		text: string;
		terms: string[];
		exact: boolean;
	}

	/** The one KWIC span named in the URL, if it belongs to this speech and term. */
	function exactSpan(speech: Speech, only: string | null): [number, number] | null {
		if (!wantedOccurrence || !wantedTerm || only !== wantedTerm) return null;
		if (speech.id !== speechOf(wantedOccurrence)) return null;
		const ordinal = occurrenceOf(wantedOccurrence);
		return ordinal ? (speech.hits[wantedTerm]?.[ordinal - 1] ?? null) : null;
	}

	/**
	 * Split a speech into plain and highlighted runs.
	 *
	 * Spans overlap by design — "genocide" sits inside "prevention of genocide" —
	 * so overlapping ones are merged into a single run that names every term it
	 * covers, rather than nesting marks or silently dropping one.
	 */
	function segments(speech: Speech, only: string | null): Segment[] {
		const selected = exactSpan(speech, only);
		const marks = Object.entries(speech.hits)
			.filter(([term]) => !only || term === only)
			.flatMap(([term, spans]) =>
				spans.map(([s, e]) => ({
					s,
					e,
					term,
					exact: selected?.[0] === s && selected[1] === e
				}))
			)
			.sort((a, b) => a.s - b.s || b.e - a.e);

		const merged: { s: number; e: number; terms: Set<string>; exact: boolean }[] = [];
		for (const mark of marks) {
			const last = merged[merged.length - 1];
			if (last && mark.s < last.e) {
				last.e = Math.max(last.e, mark.e);
				last.terms.add(mark.term);
				last.exact ||= mark.exact;
			} else {
				merged.push({ s: mark.s, e: mark.e, terms: new Set([mark.term]), exact: mark.exact });
			}
		}

		const out: Segment[] = [];
		let cursor = 0;
		for (const block of merged) {
			if (block.s > cursor)
				out.push({ text: speech.text.slice(cursor, block.s), terms: [], exact: false });
			out.push({
				text: speech.text.slice(block.s, block.e),
				terms: [...block.terms],
				exact: block.exact
			});
			cursor = block.e;
		}
		if (cursor < speech.text.length)
			out.push({ text: speech.text.slice(cursor), terms: [], exact: false });
		return out;
	}

	function visible(speech: Speech): Segment[] {
		const all = segments(speech, filterTerm);
		if (showAddress || speech.body_start === 0) return all;
		// Drop the opening form of address, which is the Secretariat's speaker
		// line rather than anything the speaker said.
		let dropped = 0;
		const out: Segment[] = [];
		for (const segment of all) {
			const end = dropped + segment.text.length;
			if (end <= speech.body_start) {
				dropped = end;
				continue;
			}
			const from = Math.max(0, speech.body_start - dropped);
			out.push({ ...segment, text: segment.text.slice(from) });
			dropped = end;
		}
		return out;
	}

	// Writable derived: seeded from the URL the reader arrived on, then owned by
	// the select below.
	let filterTerm = $derived(wantedTerm);

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
	const registerFor = (terms: string[]) => registers[terms[0]] ?? 'core';

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
		return ORDER.filter((r) => tally[r]).map((r) => ({ register: r, n: tally[r] }));
	});

	const interpreted = $derived(
		(record?.speeches ?? []).filter((s) => s.language && s.language.toLowerCase() !== 'english')
			.length
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
		<h1>That meeting is not here</h1>
		<p>{failure}</p>
		<p><a href={resolve('/concordance')}>Back to the concordance</a></p>
	</div>
{:else if !record}
	<p class="loading">Loading the meeting record…</p>
{:else}
	<article class="reader">
		<header>
			<p class="crumb">
				<a href={resolve('/concordance')}>Concordance</a><Icon icon={ChevronRight} />meeting record
			</p>
			<div class="titling">
				<div>
					<!-- Rule 06: the symbol is the address, and it is the first thing
					     on the page because it is what a reader would cite. -->
					<p class="spv">{record.spv}</p>
					<h1>{record.topic}</h1>
					<p class="meta">
						{isoDate(record.date)} · {count(record.speeches.length)} speeches · agenda item
						<strong>{record.agenda}</strong>
						({record.region})
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

		<div class="toolbar">
			<label>
				Highlight
				<select bind:value={filterTerm}>
					<option value={null}>All {termsHere.length} terms present</option>
					{#each termsHere as t (t)}<option value={t}>{termLabel(t)}</option>{/each}
				</select>
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={showAddress} /> Show the opening form of address
			</label>
			<span class="tally">{count(totalHits)} highlighted occurrences in this meeting</span>
			{#if wantedOccurrence}
				<span class="selected symbol">Selected {wantedOccurrence}</span>
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
			{/if}
			{#if resultNavigation}
				<nav class="result-nav" aria-label="Occurrences in the current concordance results">
					{#if resultNavigation.previous}
						<a href={occurrenceHref(resultNavigation.previous)}>Previous occurrence</a>
					{/if}
					<span class="symbol">{resultNavigation.position} of {resultNavigation.total}</span>
					{#if resultNavigation.next}
						<a href={occurrenceHref(resultNavigation.next)}>Next occurrence</a>
					{/if}
				</nav>
			{/if}
			<button class="ghost" onclick={openAll}>Open every speech</button>
		</div>

		<!-- The document, and its apparatus in the margin beside it. -->
		<div class="split">
			<ol class="speeches">
				{#each record.speeches as speech (speech.id)}
					{@const hits = Object.entries(speech.hits).filter(
						([t]) => !filterTerm || t === filterTerm
					)}
					{@const marked = hits.reduce((n, [, spans]) => n + spans.length, 0)}
					<li id={speech.id} class:target={speech.id === wantedSpeech}>
						<button
							class="head"
							onclick={() => toggle(speech.id)}
							aria-expanded={open.has(speech.id)}
						>
							<span class="n symbol">{speech.n}</span>
							<span class="who">
								<strong>{speech.speaker ?? shortCountry(speech.country)}</strong>
								<span class="sub">
									{shortCountry(speech.country)}
									· {speech.group}
									{#if speech.role}· {speech.role}{/if}
									{#if speech.language}· spoke in {speech.language}{/if}
								</span>
							</span>
							<span class="tags">
								{#if marked}
									<span class="count">{marked}</span>
								{/if}
								<span class="chev" class:down={open.has(speech.id)}
									><Icon icon={ChevronRight} /></span
								>
							</span>
						</button>

						{#if open.has(speech.id)}
							<div class="text">
								{#each visible(speech) as segment, i (i)}
									{#if segment.terms.length}
										<mark
											class:occurrence={segment.exact}
											data-occurrence={segment.exact ? wantedOccurrence : undefined}
											data-register={registerFor(segment.terms)}
											title={segment.exact
												? `Selected occurrence ${wantedOccurrence}`
												: segment.terms.map(termLabel).join(', ')}>{segment.text}</mark
										>
									{:else}{segment.text}{/if}
								{/each}
							</div>
							<p class="speech-meta symbol">
								{speech.id} · {count(speech.tokens)} words
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

			<aside class="apparatus">
				<div class="note">
					<span class="label">Highlights in this record</span>
					{#if marksHere.length}
						<ul class="tally-list">
							{#each marksHere as entry (entry.register)}
								<li>
									<span class="swatch" data-register={entry.register}></span>
									<span class="name">{entry.register}</span>
									<span class="symbol">{count(entry.n)}</span>
								</li>
							{/each}
						</ul>
					{:else}
						<p class="prose">No term from the word list is highlighted under the current filter.</p>
					{/if}
				</div>

				<div class="note">
					<span class="label">Delivery language</span>
					<p class="prose">
						{#if interpreted === 0}
							No speech in this record is marked as having been delivered in a language other than
							English.
						{:else if interpreted === record.speeches.length}
							Every speech in this record was delivered in a language other than English.
						{:else}
							{count(interpreted)} of {count(record.speeches.length)} speeches were delivered in a language
							other than English.
						{/if}
						The record itself is in English throughout.
					</p>
				</div>

				<div class="note">
					<span class="label">The text</span>
					<p class="prose">
						As it appears in the verbatim record, scanned and read by character-recognition
						software. The occasional wrong letter comes from that process rather than from any
						re-typing here. The highlights use the positions the pipeline recorded, so what is
						marked is exactly what was counted.
					</p>
				</div>

				<div class="note src">
					<span class="label">Source</span>
					<p class="symbol">09_export_speeches.py<br />→ speeches/{record.basename}.json</p>
				</div>
			</aside>
		</div>
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
		top: 3.4rem;
		background: var(--paper);
		z-index: 2;
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
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
		margin-left: auto;
	}

	.selected {
		font-size: var(--step--2);
		color: var(--ink-2);
	}

	.result-nav {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	.ghost {
		background: none;
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		cursor: pointer;
	}

	.ghost:hover {
		border-color: var(--blue);
		color: var(--blue);
	}

	/* The document, and beside it the apparatus. Below 62rem the margin folds
	   under the record and keeps its rule, exactly as it does in a figure. */
	.split {
		display: grid;
		gap: var(--sp-6);
	}

	@media (min-width: 62rem) {
		.split {
			grid-template-columns: minmax(0, 1fr) var(--measure-note);
			align-items: start;
		}
	}

	.speeches {
		list-style: none;
		margin: 0;
		padding: 0;
		min-width: 0;
	}

	.speeches li {
		border-bottom: var(--hair) solid var(--rule);
		padding-bottom: var(--sp-3);
		margin-bottom: var(--sp-3);
		scroll-margin-top: 8rem;
	}

	.speeches li.target {
		box-shadow: inset 2px 0 0 var(--blue-flag);
		padding-left: var(--sp-3);
		margin-left: calc(-1 * var(--sp-4));
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
	}

	/* The speaker line is apparatus, not text: it names who is talking, in the
	   voice the sidenotes use, so the record itself stays the only serif. */
	.who strong {
		display: block;
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 700;
		letter-spacing: 0.02em;
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

	.count {
		background: var(--mark);
		color: var(--ink);
		padding: 0.05rem 0.4rem;
		font-family: var(--mono);
		font-size: var(--step--2);
		font-variant-numeric: tabular-nums;
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

	.text {
		margin: var(--sp-2) 0 var(--sp-3) 2.9rem;
		font-family: var(--serif);
		font-size: var(--step-0);
		line-height: 1.68;
		white-space: pre-wrap;
		max-width: var(--measure);
	}

	.text mark.occurrence {
		outline: 2px solid var(--blue);
		outline-offset: 2px;
		scroll-margin-top: 9rem;
	}

	.speech-meta {
		margin: 0 0 0 2.9rem;
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	/* ---- the apparatus ---------------------------------------------------- */

	.apparatus {
		display: grid;
		gap: var(--sp-4);
		border-left: var(--hair) solid var(--rule-strong);
		padding-left: var(--sp-4);
	}

	@media (min-width: 62rem) {
		.apparatus {
			position: sticky;
			top: 7rem;
		}
	}

	@media (max-width: 61.999rem) {
		.apparatus {
			grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
		}
	}

	.label {
		display: block;
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: var(--sp-2);
	}

	.prose {
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	.tally-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--sp-1);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.tally-list li {
		display: grid;
		grid-template-columns: 0.7rem minmax(0, 1fr) auto;
		gap: var(--sp-2);
		align-items: center;
	}

	.tally-list .symbol {
		color: var(--ink-3);
	}

	/* The same six data colours the marks in the text carry. */
	.swatch {
		width: 0.7rem;
		height: 0.7rem;
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

	.src {
		border-top: var(--hair) solid var(--rule);
		padding-top: var(--sp-3);
	}

	.src .symbol {
		margin: 0;
		line-height: 1.5;
		color: var(--ink-2);
		overflow-wrap: anywhere;
	}
</style>
