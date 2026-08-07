<script lang="ts">
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import { count, decimal, isoDate, percent, termLabel } from '$lib/format';
	import {
		axisX,
		axisY,
		categorical,
		grid,
		legend,
		palette,
		registerColour,
		textStyle,
		tooltip
	} from '$lib/theme';
	import type { CouncilEvent, Measure } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import { SvelteMap } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	type Unit = 'speech_rate' | 'token_rate' | 'occurrences' | 'speeches';

	const UNITS: { id: Unit; label: string; note: string }[] = [
		{
			id: 'speech_rate',
			label: 'Share of speeches',
			note: 'speeches containing the term ÷ speeches held'
		},
		{
			id: 'token_rate',
			label: 'Per 100k words',
			note: 'occurrences ÷ words spoken × 100,000'
		},
		{ id: 'occurrences', label: 'Occurrences', note: 'raw count — a measure of corpus growth' },
		{ id: 'speeches', label: 'Speeches', note: 'raw count — a measure of corpus growth' }
	];

	let unit = $state<Unit>('speech_rate');
	let grain = $state<'year' | 'quarter'>('year');
	let selected = $state<string[]>(['genocide']);
	let showEvents = $state(true);
	let split = $state<string>('none');

	const source = $derived(grain === 'year' ? data.year : data.quarter);
	const periods = $derived(source.periods.map(String));

	const allMeasures = $derived<Record<string, Measure & { kind: string }>>({
		...Object.fromEntries(
			Object.entries(source.terms).map(([k, v]) => [k, { ...v, kind: 'term' }])
		),
		...Object.fromEntries(
			Object.entries(source.registers).map(([k, v]) => [
				`register:${k}`,
				{ ...v, kind: 'register' }
			])
		),
		...Object.fromEntries(
			Object.entries(source.sets).map(([k, v]) => [`set:${k}`, { ...v, kind: 'set' }])
		)
	});

	const isRate = $derived(unit === 'speech_rate' || unit === 'token_rate');
	const unavailable = $derived(
		selected.filter(
			(name) => (unit === 'token_rate' || unit === 'occurrences') && !allMeasures[name]?.occurrences
		)
	);

	const label = (name: string) =>
		name.startsWith('register:')
			? `${termLabel(name.slice(9))} (register)`
			: name.startsWith('set:')
				? `${termLabel(name.slice(4))} (set)`
				: termLabel(name);

	const colourOf = (name: string, p = palette()) =>
		name.startsWith('register:')
			? registerColour(name.slice(9), p)
			: allMeasures[name]?.register
				? registerColour(allMeasures[name].register!, p)
				: p.accent;

	function toggle(name: string) {
		selected = selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name];
	}

	/* Events are annotations on the year axis. At quarterly grain they would be
	   a forest, so they are offered only where they are legible. */
	const eventMarks = $derived.by(() => {
		if (!showEvents || grain !== 'year') return [];
		const byYear = new SvelteMap<string, CouncilEvent[]>();
		for (const e of data.overlay.events) {
			const key = String(e.year);
			byYear.set(key, [...(byYear.get(key) ?? []), e]);
		}
		return [...byYear.entries()];
	});

	const byYearLookup = $derived(new SvelteMap(eventMarks));

	const main: EChartsOption = $derived.by(() => {
		const p = palette();
		const usable = selected.filter((n) => allMeasures[n] && !unavailable.includes(n));
		return {
			textStyle,
			legend: legend(p),
			grid: { ...grid(), top: 34, bottom: showEvents && grain === 'year' ? 30 : 8 },
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				valueFormatter: (v) =>
					v == null
						? '—'
						: isRate && unit === 'speech_rate'
							? percent(v as number)
							: decimal(v as number)
			},
			xAxis: { ...axisX(p), type: 'category', data: periods },
			yAxis: {
				...axisY(p),
				type: 'value',
				axisLabel: {
					color: p.inkFaint,
					fontSize: 12,
					formatter: (v: number) => (unit === 'speech_rate' ? `${(v * 100).toFixed(1)}%` : count(v))
				}
			},
			dataZoom: [
				{ type: 'inside', throttle: 50 },
				{
					type: 'slider',
					height: 18,
					bottom: 0,
					borderColor: p.rule,
					fillerColor: p.accent + '22',
					handleStyle: { color: p.accent },
					textStyle: { color: p.inkFaint, fontSize: 11 }
				}
			],
			series: usable.map((name, i) => ({
				name: label(name),
				type: 'line',
				data: allMeasures[name][unit] ?? [],
				symbol: 'circle',
				symbolSize: grain === 'year' ? 5 : 0,
				lineStyle: { width: 2.2, color: colourOf(name, p) },
				itemStyle: { color: colourOf(name, p) },
				emphasis: { focus: 'series' },
				markLine:
					i === 0 && eventMarks.length
						? {
								silent: false,
								symbol: 'none',
								lineStyle: { color: p.inkFaint, width: 1, type: 'solid', opacity: 0.35 },
								label: { show: false },
								tooltip: {
									formatter: (params) =>
										(byYearLookup.get(String((params as { name?: string }).name)) ?? [])
											.map((e) => `<b>${isoDate(e.date)}</b><br>${e.label}`)
											.join('<hr style="opacity:.2">')
								},
								data: eventMarks.map(([year]) => ({ xAxis: year, name: year }))
							}
						: undefined
			}))
		};
	});

	/* One measure split by a categorical column — every line its own denominator. */
	const SPLITS = [
		{ id: 'none', label: 'No split' },
		{ id: 'speaker_group', label: 'Speaker group' },
		{ id: 'entity_type', label: 'Entity type' },
		{ id: 'agenda_item1', label: 'Region of agenda item' },
		{ id: 'agenda_item_manual', label: 'Agenda item' },
		{ id: 'delivery_language', label: 'Delivery language' }
	];

	const splitChart: EChartsOption | null = $derived.by(() => {
		if (split === 'none') return null;
		const block = data.splits.measures.genocide?.[split];
		if (!block) return null;
		const p = palette();
		const ramp = categorical(p);
		const years = [...new Set(block.rows.map((r) => String(r.period)))].sort();
		return {
			textStyle,
			grid: grid(),
			legend: legend(p),
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				valueFormatter: (v) => (v == null ? '—' : percent(v as number))
			},
			xAxis: { ...axisX(p), type: 'category', data: years },
			yAxis: {
				...axisY(p),
				type: 'value',
				axisLabel: {
					color: p.inkFaint,
					fontSize: 12,
					formatter: (v: number) => `${(v * 100).toFixed(0)}%`
				}
			},
			series: block.categories.map((category, i) => ({
				name: category,
				type: 'line',
				data: years.map(
					(y) =>
						block.rows.find((r) => String(r.period) === y && r.category === category)
							?.speech_rate ?? null
				),
				connectNulls: true,
				symbol: 'none',
				lineStyle: { width: 2, color: ramp[i % ramp.length] },
				itemStyle: { color: ramp[i % ramp.length] },
				emphasis: { focus: 'series' }
			}))
		};
	});

	const genocideBreaks = $derived(data.breaks.series.genocide ?? {});
</script>

<svelte:head>
	<title>Chronology — Genocide at the Security Council</title>
</svelte:head>

<article>
	<header class="lede">
		<h1>Chronology</h1>
		<p class="standfirst">
			Every term in the lexicon over {periods.length}
			{grain === 'year' ? 'years' : 'quarters'}, in whichever unit you ask for. The unit is the
			argument: the same data reads as a rise or as flat depending on what it is divided by, and
			both readings are available here on purpose.
		</p>
	</header>

	<Figure
		title="The lexicon over time"
		question="When was each term said, and does the answer survive being normalised?"
		source="04_series.py → series/annual.json, series/quarterly.json, series/events.json"
	>
		{#snippet controls()}
			<label>
				Unit
				<select bind:value={unit}>
					{#each UNITS as u (u.id)}<option value={u.id}>{u.label}</option>{/each}
				</select>
			</label>
			<label>
				Grain
				<select bind:value={grain}>
					<option value="year">Year</option>
					<option value="quarter">Quarter</option>
				</select>
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={showEvents} disabled={grain !== 'year'} />
				Reference dates
			</label>
			<span class="unit-note">{UNITS.find((u) => u.id === unit)?.note}</span>
		{/snippet}

		{#snippet reading()}
			<p>
				Pick terms below the chart. Drag the bar under the axis to zoom a period; scroll on the plot
				to do the same. Colour follows the term's <strong>register</strong>, so terms from the same
				discursive family share a hue.
			</p>
			<p>
				{#if showEvents && grain === 'year'}Faint vertical rules mark years carrying one of the
					{data.overlay.events.length} reference dates &mdash; hover a rule to read them.{:else}Reference
					dates are hidden.{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>The two raw units measure the corpus, not the discourse.</strong> The Council held {count(
					data.year.corpus.speeches[0]
				)} speeches in {periods[0]} and
				{count(data.year.corpus.speeches[data.year.corpus.speeches.length - 1])} in
				{periods[periods.length - 1]}; any series not divided by that is mostly a picture of that
				growth.
			</p>
			<p>
				Sets (<em>atrocity core</em>, <em>Rome triad</em>) have no occurrence count of their own,
				because a speech using two of their members would be counted twice. They appear only in the
				two share-based units.
			</p>
		{/snippet}

		<Chart
			option={main}
			height="420px"
			description="Time series of selected lexicon terms in the chosen unit."
		/>
	</Figure>

	{#if unavailable.length}
		<p class="warn">
			{unavailable.map(label).join(', ')} cannot be shown in this unit &mdash; a set has no occurrence
			count of its own. Switch to a share-based unit.
		</p>
	{/if}

	<section class="picker">
		<h2>Terms</h2>
		<p class="hint">
			Grouped by register. <strong>Sets</strong> are unions of terms; <strong>registers</strong>
			are every term in a discursive family at once.
		</p>
		<div class="chips">
			{#each Object.keys(allMeasures) as name (name)}
				<button
					class="chip"
					class:on={selected.includes(name)}
					style:--chip={colourOf(name)}
					onclick={() => toggle(name)}
					aria-pressed={selected.includes(name)}
				>
					{label(name)}
				</button>
			{/each}
		</div>
	</section>

	<Figure
		title="Change points in the genocide series"
		question="Where does the series actually shift, rather than merely look as though it does?"
		source="04_series.py → series/change_points.json"
	>
		{#snippet reading()}
			<p>
				Each row is one unit of the same series. A <strong>break</strong> is a point where splitting
				the series most reduces its residual variance, and where fewer than
				{percent(data.breaks.parameters.alpha)}
				of {count(data.breaks.parameters.trials)} random reorderings of the same values do as well.
			</p>
			<p>
				The method scans every sub-interval, not only the series as a whole, so a rise that subsides
				again is found at both its edges rather than missed entirely.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>{data.breaks.caveat}</p>
			<p>
				Minimum segment {data.breaks.parameters.min_size} periods, so a single anomalous year cannot be
				reported as a regime.
			</p>
		{/snippet}

		<table>
			<thead>
				<tr>
					<th>Unit</th>
					<th>Break</th>
					<th class="num">Before</th>
					<th class="num">After</th>
					<th class="num">Ratio</th>
					<th class="num">p</th>
				</tr>
			</thead>
			<tbody>
				{#each Object.entries(genocideBreaks) as [name, breaks] (name)}
					{#if breaks.length === 0}
						<tr class="none">
							<td>{UNITS.find((u) => u.id === name)?.label ?? name}</td>
							<td colspan="5">no significant break in {periods.length} years</td>
						</tr>
					{:else}
						{#each breaks as b (b.label)}
							<tr>
								<td>{UNITS.find((u) => u.id === name)?.label ?? name}</td>
								<td><strong>{b.label}</strong></td>
								<td class="num">{decimal(b.before)}</td>
								<td class="num">{decimal(b.after)}</td>
								<td class="num" class:up={b.ratio > 1} class:down={b.ratio < 1}>
									{decimal(b.ratio)}&times;
								</td>
								<td class="num">{b.p_value.toFixed(4)}</td>
							</tr>
						{/each}
					{/if}
				{/each}
			</tbody>
		</table>
	</Figure>

	<Figure
		title="Who says it, and in what debate"
		question="Is the rise or fall concentrated in one kind of speaker, or one part of the agenda?"
		source="04_series.py → series/breakdowns.json"
	>
		{#snippet controls()}
			<label>
				Split by
				<select bind:value={split}>
					{#each SPLITS as s (s.id)}<option value={s.id}>{s.label}</option>{/each}
				</select>
			</label>
		{/snippet}
		{#snippet reading()}
			<p>
				Each line is one category's own rate: speeches in that category containing
				<code>genocid*</code>, divided by speeches in that category. Every line therefore has its
				own denominator, and a small category is not penalised for being small.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>A rate says nothing about how much evidence is behind it.</strong> A category with twenty
				speeches in a year can swing between 0% and 25% on a single mention. Lines break where a category
				held no speeches at all that year.
			</p>
			<p>
				Delivery language is very nearly a restatement of who is speaking &mdash; essentially every
				Russian-language speech is Russia's &mdash; so read that split as a speaker effect wearing a
				linguistic label.
			</p>
		{/snippet}

		{#if splitChart}
			<Chart
				option={splitChart}
				height="380px"
				description="Rate of genocide invocation per year, split by the chosen category."
			/>
		{:else}
			<p class="empty">Choose a split above to break the series apart.</p>
		{/if}
	</Figure>

	<section class="events">
		<h2>Reference dates</h2>
		<p class="hint">
			{data.overlay.events.length} hand-curated dates used to annotate the chart above. They are
			<strong>drafted and not yet verified against primary records</strong> &mdash; see Methods.
		</p>
		<table>
			<thead>
				<tr><th>Date</th><th>Event</th><th>Kind</th><th>Source</th></tr>
			</thead>
			<tbody>
				{#each data.overlay.events as e (e.date + e.label)}
					<tr>
						<td class="date">{isoDate(e.date)}</td>
						<td
							>{e.label}{#if e.note}<span class="note"> — {e.note}</span>{/if}</td
						>
						<td><span class="kind">{e.kind}</span></td>
						<td><code class="sym">{e.source || '—'}</code></td>
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

	label.check {
		gap: 0.35rem;
	}

	select {
		background: var(--panel);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0.25rem 0.4rem;
		font-size: 0.85rem;
	}

	.unit-note {
		font-size: 0.78rem;
		color: var(--ink-faint);
		font-style: italic;
		margin-left: auto;
	}

	.picker {
		margin: 0 0 3rem;
	}

	.picker h2 {
		font-size: 1.05rem;
	}

	.hint {
		font-size: 0.85rem;
		color: var(--ink-soft);
		max-width: 46rem;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}

	.chip {
		border: 1px solid var(--rule);
		background: var(--panel);
		color: var(--ink-soft);
		border-radius: 999px;
		padding: 0.22rem 0.7rem;
		font-size: 0.8rem;
		cursor: pointer;
		line-height: 1.5;
	}

	.chip:hover {
		border-color: var(--chip);
		color: var(--ink);
	}

	.chip.on {
		background: var(--chip);
		border-color: var(--chip);
		color: var(--panel);
	}

	.warn {
		margin: -2rem 0 2.5rem;
		padding: 0.6rem 0.9rem;
		border-left: 3px solid var(--accent);
		background: var(--accent-soft);
		font-size: 0.87rem;
	}

	.empty {
		color: var(--ink-faint);
		font-size: 0.9rem;
		padding: 2rem 0;
		text-align: center;
	}

	.num.up {
		color: var(--negative);
	}

	.num.down {
		color: var(--positive);
	}

	tr.none td {
		color: var(--ink-faint);
		font-style: italic;
	}

	.events {
		margin-top: 1rem;
	}

	.events h2 {
		font-size: 1.05rem;
	}

	.date {
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.note {
		color: var(--ink-faint);
	}

	.kind {
		font-size: 0.72rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink-faint);
	}

	.sym {
		background: none;
		padding: 0;
		font-size: 0.78rem;
		color: var(--ink-faint);
	}
</style>
