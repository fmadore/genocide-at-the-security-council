<script lang="ts">
	import { onMount } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { base, resolve } from '$app/paths';
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import type { EChartsOption } from 'echarts';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import SearchSelect from '$lib/SearchSelect.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import { PAGE_METADATA } from '$lib/seo';
	import {
		validateMap,
		validateNeighbours,
		semanticExport,
		type SemanticMap,
		type Point
	} from '$lib/semantic';
	let map = $state.raw<SemanticMap>();
	let status = $state('Loading the semantic map…');
	let related = $state<[string, number][]>([]);
	let neighbourStatus = $state('');
	let query = $state('');
	const params = $derived(new URLSearchParams(query));
	const colour = $derived(
		params.get('colour') === 'agenda'
			? 'agenda'
			: params.get('colour') === 'year'
				? 'year'
				: 'country'
	);
	const country = $derived(params.get('country') ?? '');
	const agenda = $derived(params.get('agenda') ?? '');
	const year = $derived(params.get('year') ?? '');
	const all = $derived(params.get('corpus') === 'all');
	const selected = $derived(params.get('speech') ?? '');
	const positions = $derived(new Map(map?.points.map((p, i) => [p[0], i]) ?? []));
	const rows = $derived(
		map?.points.filter(
			(p) =>
				(all || p[6]) &&
				(!country || map!.countries[p[4]] === country) &&
				(!agenda || map!.agendas[p[5]] === agenda) &&
				(!year || String(p[3]) === year)
		) ?? []
	);
	const offset = $derived(
		Math.min(
			Math.max(0, Math.floor(Number(params.get('p')) || 0)),
			Math.max(0, Math.ceil(rows.length / 20) - 1)
		)
	);
	const visible = $derived(rows.slice(offset * 20, offset * 20 + 20));
	const selectedPoint = $derived(map?.points[positions.get(selected) ?? -1]);
	const selectionVisible = $derived(rows.some((p) => p[0] === selected));
	const bounds = $derived.by(() => {
		const box = [Infinity, -Infinity, Infinity, -Infinity];
		for (const p of map?.points ?? []) {
			box[0] = Math.min(box[0], p[1]);
			box[1] = Math.max(box[1], p[1]);
			box[2] = Math.min(box[2], p[2]);
			box[3] = Math.max(box[3], p[2]);
		}
		return box.every(Number.isFinite) ? box : [0, 1, 0, 1];
	});
	const palette = [
		'#2c7069',
		'#6b5b95',
		'#a63d40',
		'#b07817',
		'#8e3f77',
		'#5c7a3a',
		'#347c97',
		'#97613b',
		'#73797e'
	];
	function category(p: Point) {
		return colour === 'year'
			? String(Math.floor(p[3] / 10) * 10) + 's'
			: colour === 'agenda'
				? map!.agendas[p[5]]
				: map!.countries[p[4]];
	}
	const categories = $derived.by(() => {
		const counts = new SvelteMap<string, number>();
		// Keep colour meanings fixed when affiliation, agenda and year filters change.
		for (const point of map?.points ?? []) {
			if (!all && !point[6]) continue;
			const key = category(point);
			counts.set(key, (counts.get(key) ?? 0) + 1);
		}
		return [...counts]
			.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
			.slice(0, 8)
			.map(([key]) => key);
	});
	const groups = $derived.by(() => {
		const grouped: Point[][] = Array.from({ length: categories.length + 1 }, () => []);
		for (const p of rows) {
			const index = categories.indexOf(category(p));
			grouped[index < 0 ? categories.length : index].push(p);
		}
		return [...categories, 'Other']
			.map((name, index) => ({
				name,
				rows: grouped[index],
				color: index === categories.length ? palette[8] : palette[index]
			}))
			.filter((group) => group.rows.length);
	});
	const scatter = $derived(
		groups.map((group) => ({
			type: 'scatter' as const,
			name: group.name,
			symbolSize: 5,
			progressive: 5000,
			itemStyle: { color: group.color, opacity: 0.65 },
			data: group.rows.map((p) => [p[1], p[2], p[0]])
		}))
	);
	const option: EChartsOption = $derived({
		animation: false,
		color: palette,
		tooltip: { show: false },
		grid: { left: 12, right: 12, top: 12, bottom: 25 },
		xAxis: { type: 'value', show: false, min: bounds[0], max: bounds[1] },
		yAxis: { type: 'value', show: false, min: bounds[2], max: bounds[3] },
		dataZoom: [
			{ type: 'inside', xAxisIndex: 0 },
			{ type: 'inside', yAxisIndex: 0 },
			{ type: 'slider', xAxisIndex: 0, height: 14 }
		],
		series: [
			...scatter,
			{
				type: 'scatter',
				name: 'Selected speech',
				symbol: 'diamond',
				symbolSize: 15,
				z: 10,
				itemStyle: { color: '#14171a', borderColor: '#fbfbf8', borderWidth: 2 },
				data:
					selectedPoint && selectionVisible
						? [[selectedPoint[1], selectedPoint[2], selectedPoint[0]]]
						: []
			}
		]
	});
	function update(key: string, value: string) {
		const url = new URL(window.location.href);
		if (value) url.searchParams.set(key, value);
		else url.searchParams.delete(key);
		if (key !== 'p' && key !== 'speech') url.searchParams.delete('p');
		replaceState(url, page.state);
		query = url.search;
	}
	function href(id: string) {
		return `${resolve('/reader/[meeting]', { meeting: id.split('-').slice(0, 2).join('-') })}?speech=${encodeURIComponent(id)}`;
	}
	onMount(() => {
		const restore = () => {
			query = window.location.search;
		};
		restore();
		window.addEventListener('popstate', restore);
		const controller = new AbortController();
		fetch(`${base}/data/semantic/map.json`, { signal: controller.signal })
			.then(async (response) => {
				if (response.status === 404) {
					status =
						'The full-corpus embedding run has not been published yet. The map will appear after its checks pass.';
					return;
				}
				if (!response.ok) throw new Error('Could not load the semantic map. Reload to retry.');
				const data = await response.json();
				if (data.status === 'pending') {
					status =
						'The full-corpus embedding run has not been published yet. The map will appear after its checks pass.';
					return;
				}
				map = validateMap(data);
				status = '';
			})
			.catch((error) => {
				if (!controller.signal.aborted) status = error.message;
			});
		return () => {
			controller.abort();
			window.removeEventListener('popstate', restore);
		};
	});
	$effect(() => {
		const speech = selected;
		const position = positions.get(speech);
		const known = new Set(positions.keys());
		related = [];
		if (position === undefined) {
			neighbourStatus = '';
			return;
		}
		const controller = new AbortController();
		neighbourStatus = 'Loading related speeches…';
		fetch(`${base}/data/semantic/neighbours/${position % 256}.json`, { signal: controller.signal })
			.then(async (response) => {
				if (!response.ok)
					throw new Error('Related speeches could not be loaded. Reload the page to retry.');
				const result = await response.json();
				if (controller.signal.aborted) return;
				related = validateNeighbours(result, speech, known);
				neighbourStatus = '';
			})
			.catch((error) => {
				if (!controller.signal.aborted) neighbourStatus = error.message;
			});
		return () => controller.abort();
	});
</script>

<PageMeta meta={PAGE_METADATA['/semantic/']} />
<article>
	<h1>Speeches in semantic space</h1>
	<p class="standfirst">
		Explore which speeches resemble one another in wording and meaning, then read the evidence.
	</p>
	<Figure
		title="Semantic map"
		question="Which speeches does the embedding model place near one another?"
		source="06_embed.py + 21_semantic_map.py → semantic/map.json"
		download={map
			? {
					name: ['semantic-map'],
					table: () =>
						semanticExport(map!, rows, [
							`corpus: ${all ? 'all' : 'mentions genocide'}`,
							`affiliation: ${country || 'all'}`,
							`agenda: ${agenda || 'all'}`,
							`year: ${year || 'all'}`,
							`colour: ${colour}`
						])
				}
			: undefined}
	>
		{#snippet reading()}Each point is one speech. Colour shows its source affiliation, dataset
			agenda category or decade. Filter the fixed map, select a point, or use the table to open a
			speech.{/snippet}
		{#snippet caveat()}This projection compresses many dimensions into two. Nearby points can be
			misleading; related speeches use original-vector similarity. Neither distance nor colour
			measures diplomatic agreement or influence.{/snippet}
		{#if status}<p role="status">{status}</p>{/if}
		{#if map}
			<div class="filters">
				<label
					>Colour by <select
						value={colour}
						onchange={(e) => update('colour', e.currentTarget.value)}
						><option value="country">Affiliation</option><option value="agenda"
							>Meeting agenda</option
						><option value="year">Decade</option></select
					></label
				>
				<label
					>Speeches <select
						value={all ? 'all' : ''}
						onchange={(e) => update('corpus', e.currentTarget.value)}
						><option value="">Mentioning genocide</option><option value="all">Full corpus</option
						></select
					></label
				>
				<SearchSelect
					label="Affiliation"
					options={map.countries.map((s) => ({ value: s, label: s }))}
					value={country}
					onchange={(v) => update('country', v)}
				/>
				<SearchSelect
					label="Meeting agenda"
					options={map.agendas.map((s) => ({ value: s, label: s }))}
					value={agenda}
					onchange={(v) => update('agenda', v)}
				/>
				<label
					>Year <select value={year} onchange={(e) => update('year', e.currentTarget.value)}
						><option value="">All years</option
						>{#each [...new Set(map.points.map((p) => p[3]))].sort() as y (y)}<option
								value={String(y)}>{y}</option
							>{/each}</select
					></label
				>
			</div>
			<p aria-live="polite">
				{rows.length.toLocaleString()} speeches shown. Colours stay fixed while filtering; groups outside
				the eight largest share grey. The selected speech is a black diamond.
			</p>
			<ul class="legend">
				{#each groups as group (group.name)}<li>
						<span style:background={group.color}></span>{group.name} ({group.rows.length.toLocaleString()})
					</li>{/each}
			</ul>
			{#if rows.length}<Chart
					{option}
					renderer="canvas"
					preserveZoom
					height="min(65vh, 640px)"
					description="Interactive semantic speech map; the following table provides keyboard access to every plotted speech."
					onclick={(event) => {
						const value = event.value;
						if (Array.isArray(value) && typeof value[2] === 'string') update('speech', value[2]);
					}}
				/>{:else}<p>No speeches match these filters.</p>{/if}
			<p class="diagnostic">
				On a {map.meta.evaluation.points.toLocaleString()}-speech diagnostic sample, {(
					100 * map.meta.evaluation.neighbours_lost_share
				).toFixed(1)}% of neighbours within that sample were lost in the projection. Approximate
				retrieval recall at 10: {(100 * map.meta.evaluation.ann_recall_at_10).toFixed(1)}%. Model: {map
					.meta.model_repo}.
			</p>
			{#if selectedPoint}
				<aside aria-label="Selected speech">
					<h3>{map.countries[selectedPoint[4]]} · {selectedPoint[3]}</h3>
					{#if !selectionVisible}<p>This selection is outside the current filters.</p>{/if}
					<p>
						{map.agendas[selectedPoint[5]]} · <a href={href(selected)}>Read speech {selected}</a>
					</p>
					<h4>Related speeches in the full corpus</h4>
					{#if neighbourStatus}<p role="status">{neighbourStatus}</p>{/if}
					<ol>
						{#each related as [id, score] (id)}{@const p = map.points[positions.get(id)!]}
							<li>
								<a href={href(id)}>{map.countries[p[4]]} · {p[3]} · {id}</a> — cosine {score.toFixed(
									3
								)}
							</li>{/each}
					</ol>
				</aside>
			{/if}
			<div class="table-wrap">
				<table>
					<caption
						>Plotted speeches · page {offset + 1} of {Math.max(
							1,
							Math.ceil(rows.length / 20)
						)}</caption
					><thead><tr><th>Speech</th><th>Affiliation</th><th>Year</th><th>Agenda</th></tr></thead
					><tbody
						>{#each visible as p (p[0])}<tr
								><td
									><button onclick={() => update('speech', p[0])} aria-pressed={selected === p[0]}
										>{p[0]}</button
									></td
								><td>{map.countries[p[4]]}</td><td>{p[3]}</td><td>{map.agendas[p[5]]}</td></tr
							>{/each}</tbody
					>
				</table>
			</div>
			<nav aria-label="Speech table pages">
				<button disabled={offset === 0} onclick={() => update('p', String(offset - 1))}
					>Previous</button
				><button
					disabled={(offset + 1) * 20 >= rows.length}
					onclick={() => update('p', String(offset + 1))}>Next</button
				>
			</nav>
		{/if}
	</Figure>
</article>

<style>
	.standfirst {
		max-width: var(--measure);
		font-size: var(--step-1);
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		gap: var(--sp-3);
	}
	label {
		display: grid;
		gap: var(--sp-1);
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-2) var(--sp-3);
		padding: 0;
		list-style: none;
		font-size: var(--step--1);
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.legend span {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		flex: 0 0 auto;
	}
	.diagnostic {
		color: var(--ink-2);
		font-size: var(--step--1);
	}
	aside {
		border-block: 1px solid var(--rule);
		padding-block: var(--sp-3);
		margin-block: var(--sp-4);
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		min-width: 38rem;
		text-align: left;
	}
	th,
	td {
		padding: 0.5rem;
		vertical-align: top;
	}
	nav {
		display: flex;
		gap: var(--sp-3);
		margin-top: var(--sp-3);
	}
</style>
