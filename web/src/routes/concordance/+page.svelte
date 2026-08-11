<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import Download from '@lucide/svelte/icons/download';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import X from '@lucide/svelte/icons/x';
	import { MONTH_PARAM, describeMonth, inMonth, readMonth } from '$lib/concordance';
	import { kwic, meetingOf, speechOf } from '$lib/data';
	import { filename, provenanceOf, saveCsv, toCsv } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import Figure from '$lib/Figure.svelte';
	import Icon from '$lib/Icon.svelte';
	import {
		MONTH_NAMES,
		bytes,
		count,
		isoDate,
		shortCountry,
		termLabel,
		unSearch
	} from '$lib/format';
	import { segments } from '$lib/highlight';
	import type { KwicFile, KwicLine } from '$lib/types';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	type Sort = 'date' | 'country' | 'agenda' | 'left' | 'right';

	/* A segmented control rather than a select: five short words, all visible at
	   once, because which sort is in force changes what the column of nodes
	   means and should never be one click out of sight. */
	const SORTS: { value: Sort; label: string; hint: string }[] = [
		{ value: 'date', label: 'Date', hint: 'Oldest first, then by speech identifier' },
		{ value: 'country', label: 'Speaker', hint: 'Alphabetical by speaker' },
		{ value: 'agenda', label: 'Agenda', hint: 'Alphabetical by agenda item' },
		{
			value: 'left',
			label: 'Left',
			hint: 'Alphabetical on the word before the match, read backwards'
		},
		{ value: 'right', label: 'Right', hint: 'Alphabetical on the word after the match' }
	];

	const PAGE = 60;

	let term = $state('genocide');
	/**
	 * What the reader is typing, and what the lines are actually filtered by.
	 *
	 * `filtered` re-filters and re-sorts every line of the term — 51,000 of them
	 * for `genocide`, and the left and right sorts are reversed-string
	 * comparisons over the whole set. Deriving that from the box directly did all
	 * of it per keystroke, and threw away every result but the last. `applied`
	 * lags the box by `SETTLE` milliseconds and everything downstream reads it:
	 * the filter, the highlight, the export and the URL, so what is on screen,
	 * what a reader downloads and what they can cite are one query rather than
	 * three at different ages. `applied()` below is a different thing: the list
	 * of every narrowing in force, written into the exported file.
	 *
	 * The other controls are deliberately not debounced. They are discrete —
	 * a country, a sort, a month — and a reader who picks one has finished
	 * choosing.
	 */
	let query = $state('');
	let searched = $state('');
	let group = $state('');
	let country = $state('');
	let agenda = $state('');
	/** One meeting symbol, so the reader can come back the way it sent you. */
	let spv = $state('');
	let from = $state(1992);
	let to = $state(2023);
	/* A month of the year, orthogonal to the year bounds above: `month = 6` with
	   from = to = 2014 is one square of the heatmap, and the same month with the
	   years left alone is one row of the calendar beside it. What the parameter
	   means, and what an unreadable one does, is `$lib/concordance`. */
	let month = $state<number | null>(null);
	let sort = $state<Sort>('date');
	let regex = $state(false);
	let urlReady = $state(false);
	let shown = $state(PAGE);
	let expanded = $state<string | null>(null);

	let file = $state<KwicFile | null>(null);
	let loading = $state(false);
	let failure = $state<string | null>(null);
	let retry = $state(0);

	onMount(() => {
		const params = page.url.searchParams;
		term = params.get('term') ?? 'genocide';
		query = searched = params.get('q') ?? '';
		group = params.get('group') ?? '';
		country = params.get('country') ?? '';
		agenda = params.get('agenda') ?? '';
		spv = params.get('spv') ?? '';
		from = Number(params.get('from') ?? 1992);
		to = Number(params.get('to') ?? 2023);
		month = readMonth(params.get(MONTH_PARAM));
		sort = (params.get('sort') as Sort) ?? 'date';
		regex = params.get('re') === '1';
		// The first replaceState must wait until SvelteKit has assigned its root.
		// Running it inside the initial mount callback reaches the client router
		// before that assignment is complete.
		void tick().then(() => {
			urlReady = true;
		});
	});

	/** Long enough to cover typing, short enough not to feel like a wait. */
	const SETTLE = 200;

	$effect(() => {
		const typed = query;
		if (typed === searched) return;
		const timer = setTimeout(() => {
			searched = typed;
		}, SETTLE);
		return () => clearTimeout(timer);
	});

	const entries = $derived([...data.index.terms].sort((a, b) => b.count - a.count));
	const entry = $derived(entries.find((e) => e.term === term));

	$effect(() => {
		if (!urlReady) return;
		const wanted = term;
		void retry;
		loading = true;
		failure = null;
		kwic(wanted)
			.then((loaded) => {
				if (wanted === term) file = loaded;
			})
			.catch((error: Error) => {
				if (wanted === term) failure = error.message;
			})
			.finally(() => {
				if (wanted === term) loading = false;
			});
	});

	/** Keep the URL in step, so any view of the concordance is citable. */
	$effect(() => {
		if (!urlReady) return;
		const next = new SvelteURLSearchParams();
		if (term !== 'genocide') next.set('term', term);
		if (searched) next.set('q', searched);
		if (regex) next.set('re', '1');
		if (group) next.set('group', group);
		if (country) next.set('country', country);
		if (agenda) next.set('agenda', agenda);
		if (spv) next.set('spv', spv);
		if (from !== 1992) next.set('from', String(from));
		if (to !== 2023) next.set('to', String(to));
		// Written from the parsed value, never from the raw parameter, so a URL
		// carrying `month=13` rewrites itself to one that means what it shows.
		if (month !== null) next.set(MONTH_PARAM, String(month));
		if (sort !== 'date') next.set('sort', sort);
		const search = next.toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	const lines = $derived(file?.lines ?? []);

	const groups = $derived([...new Set(lines.map((l) => l.group))].sort());
	const countries = $derived(
		[...new Set(lines.map((l) => l.country))].sort((a, b) =>
			shortCountry(a).localeCompare(shortCountry(b))
		)
	);
	const agendas = $derived([...new Set(lines.map((l) => l.agenda))].sort());

	const matcher = $derived.by(() => {
		if (!searched.trim()) return null;
		if (!regex) {
			const needle = searched.toLowerCase();
			return (l: KwicLine) => `${l.left} ${l.kw} ${l.right}`.toLowerCase().includes(needle);
		}
		try {
			const re = new RegExp(searched, 'i');
			return (l: KwicLine) => re.test(`${l.left} ${l.kw} ${l.right}`);
		} catch {
			return 'invalid' as const;
		}
	});

	const badRegex = $derived(matcher === 'invalid');

	const filtered = $derived.by(() => {
		const test = typeof matcher === 'function' ? matcher : null;
		const rows = lines.filter((l) => {
			const year = Number(l.date.slice(0, 4));
			if (year < from || year > to) return false;
			if (!inMonth(l.date, month)) return false;
			if (group && l.group !== group) return false;
			if (country && l.country !== country) return false;
			if (agenda && l.agenda !== agenda) return false;
			if (spv && l.spv !== spv) return false;
			return test ? test(l) : true;
		});
		const tail = (s: string) => [...s.toLowerCase().replace(/[^a-z ]/g, '')].reverse().join('');
		const by: Record<Sort, (a: KwicLine, b: KwicLine) => number> = {
			date: (a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id),
			country: (a, b) => shortCountry(a.country).localeCompare(shortCountry(b.country)),
			agenda: (a, b) => a.agenda.localeCompare(b.agenda),
			// Classic corpus-linguistic sorts: alphabetise the context, not the
			// keyword, and recurring patterns line up down the column.
			left: (a, b) => tail(a.left).localeCompare(tail(b.left)),
			right: (a, b) => a.right.toLowerCase().localeCompare(b.right.toLowerCase())
		};
		return [...rows].sort(by[sort]);
	});

	$effect(() => {
		// Any change to the filter resets the page window.
		void [term, searched, group, country, agenda, spv, from, to, month, sort];
		shown = PAGE;
	});

	function reset() {
		// Immediately, not after `SETTLE`: clearing every filter at once is not
		// typing, and a reader who asked for the whole term should get it now.
		query = searched = '';
		group = '';
		country = '';
		agenda = '';
		spv = '';
		from = 1992;
		to = 2023;
		month = null;
		sort = 'date';
		regex = false;
	}

	/**
	 * The concordance is the one export that may legitimately be a subset.
	 *
	 * docs/PLAN.md §7.5 forbids exporting "whatever happened to be visible",
	 * because a figure's top-N cut is a display decision the reader did not make.
	 * A concordance filter is the opposite: it *is* the reader's question, and
	 * returning 51,000 lines to someone who asked for Rwanda in 1994 answers a
	 * different one. So both are offered and each says which it is — the button
	 * under the results takes the filtered lines, the figure's own control takes
	 * every line for the term.
	 */
	function table(rows: KwicLine[], scope: string, filters: string[]): ExportRequest {
		return {
			title: `Keyword in context — ${termLabel(term)}`,
			columns: ['id', 'spv', 'date', 'country', 'group', 'agenda', 'keyword', 'sentence'],
			rows: rows.map((l) => [l.id, l.spv, l.date, l.country, l.group, l.agenda, l.kw, l.sent]),
			// The kwic payload is fetched per term rather than loaded with the page,
			// so its manifest is on `file` and not on `data`.
			provenance: provenanceOf(file?.meta ?? data.index.meta, `kwic/${term}.json`),
			filters,
			scope
		};
	}

	/** What the reader actually narrowed by, for the file's own record. */
	const applied = () =>
		[
			searched ? `search: ${searched}${regex ? ' (regex)' : ''}` : null,
			group ? `group: ${group}` : null,
			country ? `speaker: ${country}` : null,
			agenda ? `agenda: ${agenda}` : null,
			spv ? `meeting: ${spv}` : null,
			from !== 1992 || to !== 2023 ? `years: ${from}–${to}` : null,
			describeMonth(month),
			`sorted by: ${sort}`
		].filter((line): line is string => line !== null);

	function download() {
		saveCsv(
			toCsv(
				table(
					filtered,
					`the ${filtered.length} lines matching the filters below, of ${lines.length} for this term`,
					applied()
				)
			),
			filename(['unsc', term, 'concordance', 'filtered'], 'csv')
		);
	}
</script>

<svelte:head>
	<title>Concordance — Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>Concordance</h1>
		<p class="standfirst">
			Every occurrence of every term on the list, with 150 characters of searchable text either
			side. This is where the counts elsewhere on the site turn back into speech: each line opens to
			the full sentence, and from there to the speech it came from.
		</p>
	</header>

	<Figure
		title="Keyword in context"
		question="What was actually said, each of the {count(entry?.count ?? 0)} times?"
		source="08_kwic.py → kwic/{term}.json"
	>
		{#snippet controls()}
			<label>
				Term
				<select bind:value={term}>
					{#each entries as e (e.term)}
						<option value={e.term}>{termLabel(e.term)} ({count(e.count)})</option>
					{/each}
				</select>
			</label>
			<label>
				Search
				<input
					type="search"
					bind:value={query}
					placeholder="within the line…"
					class:bad={badRegex}
					aria-invalid={badRegex}
					aria-describedby={badRegex ? 'regex-error' : undefined}
				/>
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={regex} /> regex
			</label>
			<div class="sort">
				<span class="label" id="sort-label">Sort</span>
				<div class="segmented" role="group" aria-labelledby="sort-label">
					{#each SORTS as option (option.value)}
						<button
							type="button"
							title={option.hint}
							aria-pressed={sort === option.value}
							onclick={() => (sort = option.value)}>{option.label}</button
						>
					{/each}
				</div>
			</div>
		{/snippet}

		{#snippet reading()}
			<p>
				The <strong>bold centre</strong> is what the search pattern matched; corpus linguists call
				it the <em>node</em>. The columns either side hold the
				{data.index.meta.width as number} characters around it, with line breaks removed. Click any line
				to open the full sentence and the details needed to cite it.
			</p>
			<p>
				<strong>Sorting by left or right context</strong> is a standard technique in corpus
				linguistics, the study of language through large collections of text. It puts the words
				<em>around</em> the match into alphabetical order, so repeated turns of phrase stack up down the
				column and can be read as patterns rather than one at a time.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A concordance line is evidence that a word was used, not evidence of a position. &ldquo;We
				reject the claim that this is genocide&rdquo; and &ldquo;this is genocide&rdquo; each count
				as one occurrence. Reading the sentence is the least you should do; reading the speech is
				better, and one click away.
			</p>
			<p>
				The counts here match the totals elsewhere on this site exactly. The export refuses to run
				rather than hand over a concordance that disagrees with the figures drawn from it.
			</p>
		{/snippet}

		<div class="filters">
			<label>
				Speaker group
				<select bind:value={group}>
					<option value="">All</option>
					{#each groups as g (g)}<option value={g}>{g}</option>{/each}
				</select>
			</label>
			<label>
				Speaker
				<select bind:value={country}>
					<option value="">All</option>
					{#each countries as c (c)}<option value={c}>{shortCountry(c)}</option>{/each}
				</select>
			</label>
			<label>
				Agenda item
				<select bind:value={agenda}>
					<option value="">All</option>
					{#each agendas as a (a)}<option value={a}>{a}</option>{/each}
				</select>
			</label>
			<label>
				Years
				<input type="number" min="1992" max="2023" bind:value={from} />
				<span>&ndash;</span>
				<input type="number" min="1992" max="2023" bind:value={to} />
			</label>
			<!-- The month of the year, not a month of one year: with the years above
			     left alone this is every June in the corpus, which is the row the
			     pooled calendar draws. It is also the disclosure for the filter — a
			     URL asking for an impossible month reads as "All" here, and the
			     concordance never claims a month it is not showing. -->
			<label>
				Month
				<select bind:value={month}>
					<option value={null}>All</option>
					{#each MONTH_NAMES as name, index (name)}
						<option value={index + 1}>{name}</option>
					{/each}
				</select>
			</label>
			{#if spv}
				<button class="chip" onclick={() => (spv = '')}>
					<span class="symbol">{spv}</span>
					<Icon icon={X} />
					<span class="sr">Clear the meeting filter</span>
				</button>
			{/if}
			<button class="ghost" onclick={reset}>Reset</button>
		</div>

		<div class="status" aria-live="polite">
			{#if loading}
				<span>Loading {termLabel(term)} — {bytes(entry?.bytes ?? 0)}…</span>
			{:else if failure}
				<span class="error">{failure}</span>
				<button class="ghost" onclick={() => (retry += 1)}>Try again</button>
			{:else}
				<span>
					<strong>{count(filtered.length)}</strong> of {count(lines.length)} lines
					{#if filtered.length !== lines.length}after filtering{/if}
				</span>
				<button class="ghost" onclick={download} disabled={!filtered.length}>
					<Icon icon={Download} />
					Export {count(filtered.length)} to CSV
				</button>
			{/if}
			{#if badRegex}<span id="regex-error" class="error">Not a valid regular expression.</span>{/if}
		</div>

		<div class="columns" aria-hidden="true">
			<span>Record &middot; speaker</span>
			<span class="c-left">Left context</span>
			<span class="c-node">Match</span>
			<span>Right context</span>
		</div>

		<div class="kwic" role="list">
			{#each filtered.slice(0, shown) as line (line.id)}
				<div class="row" role="listitem">
					<button
						class="line"
						onclick={() => (expanded = expanded === line.id ? null : line.id)}
						aria-expanded={expanded === line.id}
					>
						<span class="meta">
							<span class="spv">{line.spv}</span>
							<span class="who">{shortCountry(line.country)}</span>
						</span>
						<span class="left"
							><span class="ltr"
								>{#each segments(line.left, searched, regex) as part, i (i)}{#if part.hit}<mark
											class="hit">{part.text}</mark
										>{:else}{part.text}{/if}{/each}</span
							></span
						>
						<span class="kw"
							><mark
								>{#each segments(line.kw, searched, regex) as part, i (i)}{#if part.hit}<mark
											class="hit">{part.text}</mark
										>{:else}{part.text}{/if}{/each}</mark
							></span
						>
						<span class="right"
							>{#each segments(line.right, searched, regex) as part, i (i)}{#if part.hit}<mark
										class="hit">{part.text}</mark
									>{:else}{part.text}{/if}{/each}</span
						>
					</button>

					{#if expanded === line.id}
						<div class="detail">
							<!-- Two layers, the same two as the line above: the node carries
							     the wash, the reader's query carries the rule under the word.
							     Segmented in that order so a query that matches the node is
							     drawn as both rather than losing one to the other. -->
							<blockquote>
								{#each segments(line.sent, line.kw) as part, i (i)}{#if part.hit}<mark
											>{#each segments(part.text, searched, regex) as bit, j (j)}{#if bit.hit}<mark
														class="hit">{bit.text}</mark
													>{:else}{bit.text}{/if}{/each}</mark
										>{:else}{#each segments(part.text, searched, regex) as bit, j (j)}{#if bit.hit}<mark
													class="hit">{bit.text}</mark
												>{:else}{bit.text}{/if}{/each}{/if}{/each}
							</blockquote>
							<dl>
								<div>
									<dt>Speaker</dt>
									<dd>
										{line.country}{#if line.iso3}<span class="iso"> {line.iso3}</span>{/if}
									</dd>
								</div>
								<div>
									<dt>Position</dt>
									<dd>{line.group} · {line.type}</dd>
								</div>
								<div>
									<dt>Date</dt>
									<dd>{isoDate(line.date)}</dd>
								</div>
								<div>
									<dt>Agenda item</dt>
									<dd>{line.agenda}</dd>
								</div>
								<div>
									<dt>Record</dt>
									<dd>
										<a class="symbol" href={unSearch(line.spv)}
											>{line.spv}<Icon icon={ExternalLink} /></a
										>
									</dd>
								</div>
							</dl>
							<p class="actions">
								<a
									class="button"
									href="{resolve('/reader/[meeting]', {
										meeting: meetingOf(line.id)
									})}?speech={speechOf(line.id)}&term={term}"
								>
									Read the whole speech<Icon icon={ArrowRight} />
								</a>
								<code class="id">{line.id}</code>
							</p>
						</div>
					{/if}
				</div>
			{/each}
		</div>

		{#if shown < filtered.length}
			<button class="more" onclick={() => (shown += PAGE * 4)}>
				Show {count(Math.min(PAGE * 4, filtered.length - shown))} more
			</button>
		{:else if filtered.length === 0 && !loading}
			<p class="empty">No line matches these filters.</p>
		{/if}
	</Figure>

	<section class="terms">
		<h2>What is available</h2>
		<p class="hint">
			{count(entries.reduce((a, e) => a + e.count, 0))} lines across {entries.length} terms, some of them
			single words and some short phrases. Each term is held in its own file, downloaded when you select
			it.
		</p>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
		<div class="table-scroll" role="region" aria-label="Available terms table" tabindex="0">
			<table>
				<thead>
					<tr>
						<th>Term</th>
						<th>Register</th>
						<th class="num">Lines</th>
						<th class="num">Speeches</th>
						<th class="num">File size</th>
						<th class="num">Median sentence length</th>
					</tr>
				</thead>
				<tbody>
					{#each entries as e (e.term)}
						<tr class:current={e.term === term}>
							<td
								><button class="link" onclick={() => (term = e.term)}>{termLabel(e.term)}</button
								></td
							>
							<td>{e.register}</td>
							<td class="num">{count(e.count)}</td>
							<td class="num">{count(e.speeches)}</td>
							<td class="num">{bytes(e.bytes)}</td>
							<td class="num">{e.sentence_median} chars</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
</article>

<style>
	.lede {
		max-width: var(--measure);
		margin-bottom: var(--sp-6);
	}

	.standfirst {
		font-size: var(--step-1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	label,
	.sort {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.sort .label {
		display: inline;
	}

	select,
	input {
		max-width: 16rem;
	}

	input[type='number'] {
		width: 5.5rem;
	}

	input.bad {
		border-color: var(--state-bad);
	}

	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-3) var(--sp-5);
		align-items: center;
		padding: var(--sp-3) 0;
	}

	/* The tally is a citation of the view itself: how much of the file the
	   filters have left, in the same face as every other number that could be
	   pasted somewhere. */
	.status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-4);
		padding: var(--sp-2) 0 var(--sp-3);
		border-bottom: var(--hair) solid var(--rule-strong);
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.status strong {
		color: var(--ink);
	}

	.error {
		color: var(--state-bad);
	}

	.ghost,
	.more,
	.link {
		display: inline-flex;
		align-items: center;
		gap: 0.4em;
		background: none;
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		cursor: pointer;
	}

	.ghost:hover,
	.more:hover {
		border-color: var(--blue);
		color: var(--blue);
	}

	.ghost:disabled {
		color: var(--ink-3);
		border-color: var(--rule);
		cursor: default;
	}

	.link {
		border: none;
		padding: 0;
		min-height: 0;
		color: var(--blue);
		text-decoration: underline;
		text-underline-offset: 0.18em;
	}

	/* An active filter that came in through the URL, and the way back out of it. */
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4em;
		background: var(--mark);
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2rem;
		color: var(--ink);
		cursor: pointer;
	}

	.chip:hover {
		border-color: var(--blue);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.more {
		display: flex;
		margin: var(--sp-4) auto 0;
		padding: var(--sp-2) var(--sp-5);
	}

	/* ---- the concordance proper -------------------------------------------
	   A true KWIC: one fixed axis down the middle of the page with the node on
	   it, the left context right-aligned against it and the right context
	   running away from it. Sorting on either context then makes recurring
	   grammatical frames stack up as shapes in the column. */

	.columns,
	.line {
		display: grid;
		grid-template-columns: 7.5rem minmax(0, 1fr) auto minmax(0, 1fr);
		gap: 0 var(--sp-3);
		align-items: baseline;
	}

	.columns {
		padding: 0 var(--sp-2) var(--sp-2);
		border-bottom: var(--hair) solid var(--rule-strong);
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	.c-left {
		text-align: right;
	}

	.c-node {
		text-align: center;
	}

	.kwic {
		font-family: var(--serif);
		font-size: var(--step--1);
		line-height: 1.9;
	}

	.row {
		border-bottom: var(--hair) solid var(--rule);
	}

	.row:nth-child(even) {
		background: var(--paper-sunk);
	}

	.line {
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		border-radius: 0;
		min-height: 0;
		padding: 0.12rem var(--sp-2);
		cursor: pointer;
		font-family: inherit;
		font-size: inherit;
		color: inherit;
	}

	/* Interaction is the accent's job, and a bar on the leading edge does not
	   compete with the striping that tells one line from the next. */
	.line:hover,
	.line[aria-expanded='true'] {
		box-shadow: inset 2px 0 0 var(--blue-flag);
	}

	.meta {
		display: flex;
		flex-direction: column;
		font-family: var(--mono);
		font-size: var(--step--2);
		line-height: 1.4;
		color: var(--ink-3);
		overflow: hidden;
	}

	.spv {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.who {
		color: var(--ink-2);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* `direction: rtl` truncates the left context at its far end rather than at
	   the node; the inner span puts the text itself back into logical order so
	   trailing punctuation does not migrate to the wrong side. */
	.left {
		text-align: right;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		direction: rtl;
		color: var(--ink-2);
	}

	.ltr {
		direction: ltr;
		unicode-bidi: embed;
	}

	.kw {
		text-align: center;
		white-space: nowrap;
	}

	.kw mark {
		font-weight: 600;
	}

	/* Two marks with two jobs. The node carries the wash, because it is what the
	   concordance was built around; the reader's own query carries a rule under
	   the word, so a search for the node itself reads as both at once instead of
	   styling the same characters twice. */
	mark.hit {
		background: none;
		box-shadow: inset 0 -2px 0 var(--blue-flag);
	}

	.right {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--ink-2);
	}

	@media (max-width: 60rem) {
		.columns {
			display: none;
		}

		.line {
			grid-template-columns: minmax(0, 1fr);
			gap: var(--sp-1);
			padding: var(--sp-2);
			line-height: 1.5;
		}

		.left,
		.right {
			white-space: normal;
			text-align: left;
			direction: ltr;
			overflow: visible;
		}

		.kw {
			text-align: left;
		}
	}

	.detail {
		padding: var(--sp-3) var(--sp-2) var(--sp-4) 8.25rem;
	}

	@media (max-width: 60rem) {
		.detail {
			padding-left: var(--sp-2);
		}
	}

	blockquote {
		margin: 0 0 var(--sp-3);
		padding-left: var(--sp-3);
		border-left: var(--hair) solid var(--rule-strong);
		font-family: var(--serif);
		font-size: var(--step-0);
		line-height: 1.55;
		max-width: var(--measure);
	}

	.detail dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: var(--sp-2) var(--sp-5);
		margin: 0 0 var(--sp-3);
	}

	.detail dt {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	.detail dd {
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.detail dd a {
		display: inline-flex;
		align-items: center;
		gap: 0.3em;
	}

	.iso {
		color: var(--ink-3);
		font-family: var(--mono);
		font-size: var(--step--2);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-4);
		margin: 0;
	}

	.button {
		display: inline-flex;
		align-items: center;
		gap: 0.4em;
		padding: var(--sp-2) var(--sp-3);
		border: var(--hair) solid var(--blue);
		color: var(--blue);
		text-decoration: none;
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.button:hover {
		background: var(--blue);
		color: var(--paper);
	}

	.button:hover :global(.icon) {
		transform: translateX(0.2rem);
	}

	.button :global(.icon) {
		transition: transform var(--dur) var(--ease);
	}

	.id {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.empty {
		text-align: center;
		color: var(--ink-3);
		padding: var(--sp-7) 0;
	}

	.terms {
		margin-top: var(--sp-7);
	}

	.terms h2 {
		font-size: var(--step-2);
	}

	.hint {
		max-width: var(--measure);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.table-scroll {
		max-width: 100%;
		overflow-x: auto;
	}

	tr.current td {
		background: var(--mark);
	}
</style>
