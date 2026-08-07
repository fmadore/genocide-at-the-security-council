<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { kwicIndex, meeting as loadMeeting } from '$lib/data';
	import { count, isoDate, shortCountry, termLabel, unSearch } from '$lib/format';
	import { registerColour } from '$lib/theme';
	import type { Meeting, Speech } from '$lib/types';
	import { tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';

	const basename = $derived(page.params.meeting!);
	const wantedSpeech = $derived(page.url.searchParams.get('speech'));
	const wantedTerm = $derived(page.url.searchParams.get('term'));

	let record = $state<Meeting | null>(null);
	let failure = $state<string | null>(null);
	let registers = $state<Record<string, string>>({});
	let open = new SvelteSet<string>();
	let showAddress = $state(false);

	$effect(() => {
		const wanted = basename;
		record = null;
		failure = null;
		loadMeeting(wanted)
			.then(async (loaded) => {
				if (wanted !== basename) return;
				record = loaded;
				const target = wantedSpeech ?? loaded.speeches.find((s) => hasHits(s))?.id;
				open.clear();
				if (target) open.add(target);
				await tick();
				document.getElementById(target ?? '')?.scrollIntoView({ block: 'center' });
			})
			.catch((error: Error) => {
				if (wanted === basename) failure = error.message;
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
	}

	/**
	 * Split a speech into plain and highlighted runs.
	 *
	 * Spans overlap by design — "genocide" sits inside "prevention of genocide" —
	 * so overlapping ones are merged into a single run that names every term it
	 * covers, rather than nesting marks or silently dropping one.
	 */
	function segments(speech: Speech, only: string | null): Segment[] {
		const marks = Object.entries(speech.hits)
			.filter(([term]) => !only || term === only)
			.flatMap(([term, spans]) => spans.map(([s, e]) => ({ s, e, term })))
			.sort((a, b) => a.s - b.s || b.e - a.e);

		const merged: { s: number; e: number; terms: Set<string> }[] = [];
		for (const mark of marks) {
			const last = merged[merged.length - 1];
			if (last && mark.s < last.e) {
				last.e = Math.max(last.e, mark.e);
				last.terms.add(mark.term);
			} else {
				merged.push({ s: mark.s, e: mark.e, terms: new Set([mark.term]) });
			}
		}

		const out: Segment[] = [];
		let cursor = 0;
		for (const block of merged) {
			if (block.s > cursor) out.push({ text: speech.text.slice(cursor, block.s), terms: [] });
			out.push({ text: speech.text.slice(block.s, block.e), terms: [...block.terms] });
			cursor = block.e;
		}
		if (cursor < speech.text.length) out.push({ text: speech.text.slice(cursor), terms: [] });
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

	const preview = (speech: Speech) =>
		speech.text.slice(speech.body_start, speech.body_start + 180).replace(/\s+/g, ' ') + '…';

	const colourFor = (terms: string[]) => registerColour(registers[terms[0]] ?? 'core');
</script>

<svelte:head>
	<title>{record ? `${record.spv} — ${record.topic}` : 'Reading…'}</title>
</svelte:head>

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
			<p class="crumb"><a href={resolve('/concordance')}>Concordance</a> → meeting record</p>
			<h1>{record.topic}</h1>
			<p class="meta">
				<a href={unSearch(record.spv)}>{record.spv}</a>
				· {isoDate(record.date)}
				· {count(record.speeches.length)} speeches · agenda item <strong>{record.agenda}</strong>
				({record.region})
			</p>
			<p class="note">
				Text as it appears in the verbatim record, digitised and OCR'd &mdash; occasional character
				errors are the source's, not a transcription made here. Highlights are drawn from offsets
				computed by the pipeline, so what is marked is exactly what was counted.
			</p>
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
				<input type="checkbox" bind:checked={showAddress} /> Show form of address
			</label>
			<span class="tally">{count(totalHits)} highlighted occurrences in this meeting</span>
			<button class="ghost" onclick={openAll}>Open every speech</button>
		</div>

		<ol class="speeches">
			{#each record.speeches as speech (speech.id)}
				{@const hits = Object.entries(speech.hits).filter(([t]) => !filterTerm || t === filterTerm)}
				{@const marked = hits.reduce((n, [, spans]) => n + spans.length, 0)}
				<li id={speech.id} class:target={speech.id === wantedSpeech}>
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
								{#if speech.language}· spoke in {speech.language}{/if}
							</span>
						</span>
						<span class="tags">
							{#if marked}
								<span class="count">{marked}</span>
							{/if}
							<span class="chev" class:down={open.has(speech.id)}>›</span>
						</span>
					</button>

					{#if open.has(speech.id)}
						<div class="text">
							{#each visible(speech) as segment, i (i)}
								{#if segment.terms.length}
									<mark
										style:--mark={colourFor(segment.terms)}
										title={segment.terms.map(termLabel).join(', ')}>{segment.text}</mark
									>
								{:else}{segment.text}{/if}
							{/each}
						</div>
						<p class="speech-meta">
							<code>{speech.id}</code> · {count(speech.tokens)} words
							{#if Object.keys(speech.hits).length}
								· {Object.keys(speech.hits).map(termLabel).join(', ')}
							{/if}
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
		max-width: 40rem;
		margin: 3rem auto;
		text-align: center;
		color: var(--ink-soft);
	}

	.reader {
		max-width: 52rem;
		margin: 0 auto;
	}

	.crumb {
		font-size: 0.8rem;
		color: var(--ink-faint);
		margin-bottom: 0.6rem;
	}

	header h1 {
		font-size: clamp(1.5rem, 1.2rem + 1.4vw, 2.1rem);
	}

	.meta {
		font-size: 0.9rem;
		color: var(--ink-soft);
		margin-bottom: 0.7rem;
	}

	.note {
		font-size: 0.82rem;
		color: var(--ink-faint);
		border-left: 2px solid var(--rule);
		padding-left: 0.8rem;
		max-width: 42rem;
	}

	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1.2rem;
		align-items: center;
		padding: 0.8rem 0;
		margin-bottom: 1rem;
		border-top: 1px solid var(--rule);
		border-bottom: 1px solid var(--rule);
		position: sticky;
		top: 3.6rem;
		background: var(--paper);
		z-index: 2;
	}

	label {
		font-size: 0.83rem;
		color: var(--ink-faint);
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
	}

	select {
		background: var(--panel);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.25rem 0.4rem;
		font-size: 0.85rem;
	}

	.tally {
		font-size: 0.8rem;
		color: var(--ink-faint);
		margin-left: auto;
	}

	.ghost {
		background: none;
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.2rem 0.6rem;
		font-size: 0.8rem;
		color: var(--ink-soft);
		cursor: pointer;
	}

	.ghost:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.speeches {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.speeches li {
		border-bottom: 1px solid var(--rule-soft);
		padding-bottom: 0.6rem;
		margin-bottom: 0.6rem;
		scroll-margin-top: 8rem;
	}

	.speeches li.target {
		border-left: 3px solid var(--accent);
		padding-left: 0.9rem;
		margin-left: -1.2rem;
	}

	.head {
		display: grid;
		grid-template-columns: 2.2rem 1fr auto;
		gap: 0.7rem;
		align-items: baseline;
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		padding: 0.4rem 0;
		cursor: pointer;
		color: inherit;
	}

	.head:hover .who strong {
		color: var(--accent);
	}

	.n {
		font-variant-numeric: tabular-nums;
		color: var(--ink-faint);
		font-size: 0.78rem;
	}

	.who strong {
		font-family: var(--serif);
		font-size: 1.02rem;
		display: block;
	}

	.sub {
		font-size: 0.78rem;
		color: var(--ink-faint);
	}

	.tags {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.count {
		background: var(--accent-soft);
		color: var(--accent);
		border-radius: 999px;
		padding: 0.05rem 0.45rem;
		font-size: 0.74rem;
		font-variant-numeric: tabular-nums;
	}

	.chev {
		color: var(--ink-faint);
		transition: transform 0.15s;
		display: inline-block;
	}

	.chev.down {
		transform: rotate(90deg);
	}

	.preview {
		margin: 0 0 0 2.9rem;
		font-size: 0.85rem;
		color: var(--ink-faint);
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.text {
		margin: 0.5rem 0 0.6rem 2.9rem;
		font-family: var(--serif);
		font-size: 1.02rem;
		line-height: 1.7;
		white-space: pre-wrap;
		max-width: var(--measure);
	}

	mark {
		background: color-mix(in srgb, var(--mark) 22%, transparent);
		color: inherit;
		border-bottom: 2px solid var(--mark);
		padding: 0 0.05em;
		border-radius: 2px;
	}

	.speech-meta {
		margin: 0 0 0 2.9rem;
		font-size: 0.75rem;
		color: var(--ink-faint);
	}

	.speech-meta code {
		background: none;
		padding: 0;
		font-size: 0.75rem;
	}
</style>
