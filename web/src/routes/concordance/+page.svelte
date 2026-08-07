<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { kwic, meetingOf, speechOf } from '$lib/data';
	import Figure from '$lib/Figure.svelte';
	import { bytes, count, isoDate, shortCountry, termLabel, unSearch } from '$lib/format';
	import type { KwicFile, KwicLine } from '$lib/types';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	type Sort = 'date' | 'country' | 'agenda' | 'left' | 'right';

	const PAGE = 60;

	const params = page.url.searchParams;
	let term = $state(params.get('term') ?? 'genocide');
	let query = $state(params.get('q') ?? '');
	let group = $state(params.get('group') ?? '');
	let country = $state(params.get('country') ?? '');
	let agenda = $state(params.get('agenda') ?? '');
	let from = $state(Number(params.get('from') ?? 1992));
	let to = $state(Number(params.get('to') ?? 2023));
	let sort = $state<Sort>((params.get('sort') as Sort) ?? 'date');
	let regex = $state(params.get('re') === '1');
	let shown = $state(PAGE);
	let expanded = $state<string | null>(null);

	let file = $state<KwicFile | null>(null);
	let loading = $state(false);
	let failure = $state<string | null>(null);

	const entries = $derived([...data.index.terms].sort((a, b) => b.count - a.count));
	const entry = $derived(entries.find((e) => e.term === term));

	$effect(() => {
		const wanted = term;
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
		const next = new SvelteURLSearchParams();
		if (term !== 'genocide') next.set('term', term);
		if (query) next.set('q', query);
		if (regex) next.set('re', '1');
		if (group) next.set('group', group);
		if (country) next.set('country', country);
		if (agenda) next.set('agenda', agenda);
		if (from !== 1992) next.set('from', String(from));
		if (to !== 2023) next.set('to', String(to));
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
		if (!query.trim()) return null;
		if (!regex) {
			const needle = query.toLowerCase();
			return (l: KwicLine) => `${l.left} ${l.kw} ${l.right}`.toLowerCase().includes(needle);
		}
		try {
			const re = new RegExp(query, 'i');
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
			if (group && l.group !== group) return false;
			if (country && l.country !== country) return false;
			if (agenda && l.agenda !== agenda) return false;
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
		void [term, query, group, country, agenda, from, to, sort];
		shown = PAGE;
	});

	function reset() {
		query = '';
		group = '';
		country = '';
		agenda = '';
		from = 1992;
		to = 2023;
		sort = 'date';
	}

	function toCsv(rows: KwicLine[]): string {
		const escape = (v: string) => `"${String(v).replace(/"/g, '""')}"`;
		const head = ['id', 'spv', 'date', 'country', 'group', 'agenda', 'keyword', 'sentence'];
		const body = rows.map((l) =>
			[l.id, l.spv, l.date, l.country, l.group, l.agenda, l.kw, l.sent].map(escape).join(',')
		);
		return [head.join(','), ...body].join('\n');
	}

	function download() {
		const blob = new Blob([toCsv(filtered)], { type: 'text/csv;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `unsc-${term}-concordance.csv`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:head>
	<title>Concordance — Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>Concordance</h1>
		<p class="standfirst">
			Every occurrence of every lexicon term, with the words either side of it. This is where an
			aggregate stops being an aggregate: each line opens to its full sentence, and from there to
			the speech it came from.
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
				/>
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={regex} /> regex
			</label>
			<label>
				Sort
				<select bind:value={sort}>
					<option value="date">Date</option>
					<option value="country">Speaker</option>
					<option value="agenda">Agenda item</option>
					<option value="left">Left context (reversed)</option>
					<option value="right">Right context</option>
				</select>
			</label>
		{/snippet}

		{#snippet reading()}
			<p>
				The <strong>bold centre</strong> is what the pattern matched; the columns either side are
				the {data.index.meta.width as number} characters around it, with line breaks flattened. Click
				any line to open the full sentence and the metadata for citing it.
			</p>
			<p>
				<strong>Sorting by left or right context</strong> is the classic corpus-linguistic move: it
				alphabetises the words <em>around</em> the keyword, so recurring constructions line up down the
				column and become visible as patterns rather than as instances.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				A concordance line is evidence of a word, not of a position. &ldquo;We reject the claim that
				this is genocide&rdquo; and &ldquo;this is genocide&rdquo; are one occurrence each. Reading
				the sentence is the minimum; reading the speech is better, and one click away.
			</p>
			<p>
				Counts here match the totals elsewhere on this site exactly &mdash; the export fails rather
				than ship a concordance that disagrees with its own aggregates.
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
			<button class="ghost" onclick={reset}>Reset</button>
		</div>

		<div class="status">
			{#if loading}
				<span>Loading {termLabel(term)} — {bytes(entry?.bytes ?? 0)}…</span>
			{:else if failure}
				<span class="error">{failure}</span>
			{:else}
				<span>
					<strong>{count(filtered.length)}</strong> of {count(lines.length)} lines
					{#if filtered.length !== lines.length}after filtering{/if}
				</span>
				<button class="ghost" onclick={download} disabled={!filtered.length}>
					Export {count(filtered.length)} to CSV
				</button>
			{/if}
			{#if badRegex}<span class="error">Not a valid regular expression.</span>{/if}
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
							<span class="year">{line.date.slice(0, 4)}</span>
							<span class="who">{shortCountry(line.country)}</span>
						</span>
						<span class="left">{line.left}</span>
						<span class="kw">{line.kw}</span>
						<span class="right">{line.right}</span>
					</button>

					{#if expanded === line.id}
						<div class="detail">
							<blockquote>{line.sent}</blockquote>
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
									<dd><a href={unSearch(line.spv)}>{line.spv}</a></dd>
								</div>
							</dl>
							<p class="actions">
								<a
									class="button"
									href="{resolve('/reader/[meeting]', {
										meeting: meetingOf(line.id)
									})}?speech={speechOf(line.id)}&term={term}"
								>
									Read the whole speech
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
			{count(entries.reduce((a, e) => a + e.count, 0))} lines across {entries.length} terms. Each term
			is a separate file, fetched when you choose it.
		</p>
		<table>
			<thead>
				<tr>
					<th>Term</th>
					<th>Register</th>
					<th class="num">Lines</th>
					<th class="num">Speeches</th>
					<th class="num">Size</th>
					<th class="num">Median sentence</th>
				</tr>
			</thead>
			<tbody>
				{#each entries as e (e.term)}
					<tr class:current={e.term === term}>
						<td
							><button class="link" onclick={() => (term = e.term)}>{termLabel(e.term)}</button></td
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
	</section>
</article>

<style>
	.lede {
		max-width: 46rem;
		margin-bottom: 2rem;
	}

	.standfirst {
		font-size: 1.08rem;
		color: var(--ink-soft);
	}

	label {
		font-size: 0.83rem;
		color: var(--ink-faint);
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
	}

	select,
	input {
		background: var(--panel);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.25rem 0.4rem;
		font-size: 0.85rem;
		max-width: 16rem;
	}

	input[type='number'] {
		width: 5rem;
	}

	input.bad {
		border-color: var(--negative);
	}

	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1.2rem;
		align-items: center;
		padding: 0.8rem 0;
	}

	.status {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem;
		padding: 0.5rem 0 0.9rem;
		border-bottom: 1px solid var(--rule);
		font-size: 0.85rem;
		color: var(--ink-soft);
	}

	.error {
		color: var(--negative);
	}

	.ghost,
	.more,
	.link {
		background: none;
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.2rem 0.6rem;
		font-size: 0.8rem;
		color: var(--ink-soft);
		cursor: pointer;
	}

	.ghost:hover,
	.more:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.link {
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: underline;
		text-underline-offset: 0.15em;
	}

	.more {
		display: block;
		margin: 1rem auto 0;
		padding: 0.4rem 1.1rem;
	}

	.kwic {
		font-size: 0.85rem;
	}

	.row {
		border-bottom: 1px solid var(--rule-soft);
	}

	.line {
		display: grid;
		grid-template-columns: 9.5rem 1fr auto 1fr;
		gap: 0 0.5rem;
		align-items: baseline;
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		padding: 0.32rem 0.2rem;
		cursor: pointer;
		font-size: inherit;
		color: inherit;
	}

	.line:hover {
		background: var(--rule-soft);
	}

	.meta {
		display: flex;
		gap: 0.45rem;
		color: var(--ink-faint);
		font-size: 0.76rem;
		overflow: hidden;
		white-space: nowrap;
	}

	.year {
		font-variant-numeric: tabular-nums;
	}

	.who {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.left {
		text-align: right;
		white-space: nowrap;
		overflow: hidden;
		direction: rtl;
		color: var(--ink-soft);
	}

	.kw {
		font-weight: 600;
		color: var(--accent);
		white-space: nowrap;
	}

	.right {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--ink-soft);
	}

	@media (max-width: 60rem) {
		.line {
			grid-template-columns: 1fr;
			gap: 0.15rem;
			padding: 0.6rem 0.2rem;
		}

		.left,
		.right {
			white-space: normal;
			text-align: left;
			direction: ltr;
			overflow: visible;
		}

		.kw {
			display: inline;
		}
	}

	.detail {
		padding: 0.6rem 0.2rem 1rem 10rem;
	}

	@media (max-width: 60rem) {
		.detail {
			padding-left: 0.2rem;
		}
	}

	blockquote {
		margin: 0 0 0.8rem;
		padding-left: 0.9rem;
		border-left: 3px solid var(--accent);
		font-family: var(--serif);
		font-size: 1rem;
		line-height: 1.55;
	}

	.detail dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: 0.5rem 1.2rem;
		margin: 0 0 0.8rem;
	}

	.detail dt {
		font-size: 0.7rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--ink-faint);
	}

	.detail dd {
		margin: 0;
		font-size: 0.85rem;
	}

	.iso {
		color: var(--ink-faint);
		font-family: var(--mono);
		font-size: 0.75rem;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.9rem;
		margin: 0;
	}

	.button {
		display: inline-block;
		padding: 0.3rem 0.8rem;
		border: 1px solid var(--accent);
		border-radius: 4px;
		color: var(--accent);
		text-decoration: none;
		font-size: 0.83rem;
	}

	.button:hover {
		background: var(--accent);
		color: var(--panel);
	}

	.id {
		background: none;
		padding: 0;
		font-size: 0.72rem;
		color: var(--ink-faint);
	}

	.empty {
		text-align: center;
		color: var(--ink-faint);
		padding: 2.5rem 0;
	}

	.terms h2 {
		font-size: 1.05rem;
	}

	.hint {
		font-size: 0.85rem;
		color: var(--ink-soft);
	}

	tr.current td {
		background: var(--accent-soft);
	}
</style>
