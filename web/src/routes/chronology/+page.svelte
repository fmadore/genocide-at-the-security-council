<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Heatmap from '$lib/Heatmap.svelte';
	import Icon from '$lib/Icon.svelte';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import {
		CALENDAR_COLUMNS,
		GRID_COLUMNS,
		calendar,
		calendarRows,
		grid as monthGrid,
		gridRows,
		measures as monthlyMeasures,
		monthLabel,
		units as monthlyUnits
	} from '$lib/heatmap';
	import type { Cell, Unit as GridUnit } from '$lib/heatmap';
	import { count, decimal, escapeHtml, isoDate, percent, termLabel } from '$lib/format';
	import {
		axisX,
		axisY,
		categorical,
		colourScheme,
		endLabel,
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
	const colours = $derived.by(() => {
		void $colourScheme;
		return palette();
	});

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

	/* Live chart handles, for the image half of the export. */
	let seriesFigure = $state<Chart | null>(null);
	let splitFigure = $state<Chart | null>(null);
	let gridFigure = $state<Heatmap | null>(null);

	/* --- The month resolution ---------------------------------------------
	   A third resolution rather than more of the same. A year always holds
	   thousands of speeches and a month need not, so this artefact is the one
	   that can withhold a figure — and the figure it feeds is the one where a
	   blank square would be read as a measurement. */
	let gridMeasure = $state('genocide');
	let gridUnit = $state<GridUnit>('speech_rate');

	const byMonth = $derived(data.month);
	const gridMeasures = $derived(Object.keys(monthlyMeasures(byMonth)));
	const gridUnits = $derived(monthlyUnits(monthlyMeasures(byMonth)[gridMeasure]));
	const heat = $derived(monthGrid({ data: byMonth, measure: gridMeasure, unit: gridUnit }));
	const column = $derived(calendar(byMonth, gridMeasure, heat.unit));

	/* `grid()` refuses a unit the measure cannot carry and says which one it
	   used; the select follows it, so the control never names a figure the grid
	   is not in. Same rule as the actor view's ranking. */
	$effect(() => {
		if (!gridUnits.includes(gridUnit)) gridUnit = heat.unit;
	});

	const showRate = (value: number | null) =>
		value === null ? '—' : heat.unit === 'speech_rate' ? percent(value) : decimal(value);

	const unitName = $derived(
		heat.unit === 'speech_rate' ? 'share of the month’s speeches' : 'per 100k words'
	);

	/** Every cell says which of the three things it is, rather than only a number. */
	const cellLabel = (cell: Cell) => {
		const where = monthLabel(cell.period);
		if (cell.state === 'unobserved') return `${where}: the Council held no speeches`;
		if (cell.state === 'withheld') {
			return (
				`${where}: ${count(cell.speeches)} of ${count(cell.held)} speeches — withheld, ` +
				`under the ${count(heat.minimum)}-speech minimum`
			);
		}
		return `${where}: ${showRate(cell.value)} — ${count(cell.speeches)} of ${count(cell.held)} speeches`;
	};

	const strongest = $derived(
		[...column.rows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0)).slice(0, 2)
	);

	/** Every measure and every month, including the 53 that carry no rate. */
	function monthTable(): ExportRequest {
		return {
			title: 'Does the vocabulary have a calendar?',
			columns: GRID_COLUMNS,
			rows: gridRows(byMonth),
			provenance: provenanceOf(byMonth.meta, 'series/monthly.json'),
			filters: [
				`drawn: ${termLabel(gridMeasure)}`,
				`unit: ${unitName}`,
				`minimum: ${byMonth.minimum_speeches} speeches per month`
			],
			scope:
				`all ${byMonth.periods.length} months for every measure the artefact holds, ` +
				`including the ${heat.withheld} below the ${byMonth.minimum_speeches}-speech ` +
				`minimum whose rates are null`
		};
	}

	/** The pooled months, one row per agenda item so the confound travels too. */
	function calendarTable(): ExportRequest {
		return {
			title: 'The same twelve months, pooled',
			columns: CALENDAR_COLUMNS,
			rows: calendarRows(byMonth),
			provenance: provenanceOf(byMonth.meta, 'series/monthly.json'),
			filters: [
				`drawn: ${termLabel(gridMeasure)}`,
				`unit: ${unitName}`,
				`control reading excludes: ${column.excludedYears.join(', ')}`
			],
			scope:
				'every calendar month for every measure, with the agenda items behind each ' +
				'one — a calendar table without them is the misleading half of this figure'
		};
	}

	/**
	 * The series download: every measure and all four units, long-form.
	 *
	 * Not the selected terms and not the chosen unit. A reader who picked one
	 * line out of thirty and downloaded it would have a file that agrees with
	 * their screen and with nothing else, and could not check the normalisation
	 * argument this figure exists to make without going back for the rest. The
	 * filter line records what was drawn; the file carries the artefact.
	 */
	function seriesTable(): ExportRequest {
		const rows: (string | number | null)[][] = [];
		for (const [name, measure] of Object.entries(allMeasures)) {
			periods.forEach((period, index) => {
				rows.push([
					period,
					name,
					measure.kind,
					measure.register ?? null,
					source.corpus.speeches[index],
					source.corpus.tokens[index],
					measure.speeches[index] ?? null,
					measure.speech_rate[index] ?? null,
					measure.occurrences?.[index] ?? null,
					measure.token_rate?.[index] ?? null
				]);
			});
		}
		return {
			title: 'The lexicon over time',
			columns: [
				'period',
				'measure',
				'kind',
				'register',
				'corpus_speeches',
				'corpus_tokens',
				'speeches',
				'speech_rate',
				'occurrences',
				'token_rate_per_100k'
			],
			rows,
			provenance: provenanceOf(
				source.meta,
				grain === 'year' ? 'series/annual.json' : 'series/quarterly.json'
			),
			filters: [
				`drawn: ${selected.map(label).join(', ')}`,
				`unit: ${UNITS.find((u) => u.id === unit)?.label ?? unit}`,
				`grain: ${grain}`,
				`events overlay: ${showEvents ? 'on' : 'off'}`
			],
			scope: `every measure in the artefact at ${grain} grain, in all four units`
		};
	}

	/** The two-rate models, one row per unit per measure. Sets are absent by design. */
	function breaksTable(): ExportRequest {
		const rows: (string | number | null)[][] = [];
		for (const [measure, units] of Object.entries(data.breaks.series)) {
			for (const [unitName, found] of Object.entries(units)) {
				for (const point of found) {
					rows.push([
						measure,
						unitName,
						point.label,
						point.index,
						point.before,
						point.after,
						point.ratio,
						point.gain,
						point.p_value,
						point.interval_start,
						point.interval_stop
					]);
				}
			}
		}
		return {
			title: 'Rate heterogeneity in the genocide series',
			columns: [
				'measure',
				'unit',
				'label',
				'index',
				'rate_before',
				'rate_after',
				'ratio',
				'gain',
				'p_value',
				'interval_start',
				'interval_stop'
			],
			rows,
			provenance: provenanceOf(data.breaks.meta, 'series/change_points.json'),
			filters: [
				`threshold: ${percent(data.breaks.inference.per_test_alpha)} after ${data.breaks.inference.correction}`,
				`simulations: ${data.breaks.inference.trials}`,
				`minimum segment: ${data.breaks.parameters.min_size} periods`
			],
			scope: 'every accepted partition, for every measure and unit the artefact holds'
		};
	}

	/** Every split the artefact holds, not the one on screen. */
	function splitsTable(): ExportRequest {
		const rows: (string | number | null)[][] = [];
		for (const [measure, splits] of Object.entries(data.splits.measures)) {
			for (const [splitName, block] of Object.entries(splits)) {
				for (const row of block.rows) {
					rows.push([
						measure,
						splitName,
						row.period,
						row.category,
						row.held,
						row.speeches,
						row.speech_rate,
						row.occurrences ?? null,
						row.token_rate ?? null
					]);
				}
			}
		}
		return {
			title: 'Who says it, and in what debate',
			columns: [
				'measure',
				'split',
				'period',
				'category',
				'held',
				'speeches',
				'speech_rate',
				'occurrences',
				'token_rate_per_100k'
			],
			rows,
			provenance: provenanceOf(data.splits.meta, 'series/breakdowns.json'),
			filters: [`split by: ${split}`, `unit: ${UNITS.find((u) => u.id === unit)?.label ?? unit}`],
			scope: 'every split and every measure the artefact holds'
		};
	}

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

	// A term with no register of its own is drawn in ink, not in the accent: the
	// accent belongs to what the reader can act on, never to a series.
	const colourOf = (name: string, p = colours) =>
		name.startsWith('register:')
			? registerColour(name.slice(9), p)
			: allMeasures[name]?.register
				? registerColour(allMeasures[name].register!, p)
				: p.ink;

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

	/* Name each line where it ends rather than in a legend — up to the point
	   where the labels would sit on top of each other. Past that a legend is the
	   lesser evil, which is the one case `theme.ts` keeps it for. */
	const LABELLABLE = 8;

	const main: EChartsOption = $derived.by(() => {
		const p = colours;
		const usable = selected.filter((n) => allMeasures[n] && !unavailable.includes(n));
		const named = usable.length <= LABELLABLE;
		return {
			textStyle,
			legend: named ? undefined : legend(p),
			grid: {
				...grid(named),
				top: named ? 12 : 34,
				bottom: showEvents && grain === 'year' ? 30 : 8
			},
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				// The reference dates are markLines, but a markLine's own tooltip never
				// fires while the chart tooltip is axis-triggered: hovering a rule gave
				// the year's values and nothing about the date the rule was there for.
				// So the axis tooltip carries them, and every year is hoverable rather
				// than a one-pixel line.
				formatter: (params) => {
					const rows = (Array.isArray(params) ? params : [params]) as {
						axisValue?: string;
						marker?: string;
						seriesName?: string;
						value?: unknown;
					}[];
					const year = rows[0]?.axisValue ?? '';
					const show = (v: unknown) =>
						v == null
							? '—'
							: isRate && unit === 'speech_rate'
								? percent(v as number)
								: decimal(v as number);
					const series = rows
						.map(
							(r) => `${r.marker ?? ''}${escapeHtml(r.seriesName ?? '')} <b>${show(r.value)}</b>`
						)
						.join('<br>');
					const events = byYearLookup.get(year) ?? [];
					const dates = events.length
						? '<hr style="opacity:.2">' +
							`<span style="opacity:.7">Reference ${events.length === 1 ? 'date' : 'dates'}</span><br>` +
							events.map((e) => `<b>${isoDate(e.date)}</b> ${escapeHtml(e.label)}`).join('<br>')
						: '';
					return `<b>${escapeHtml(year)}</b><br>${series}${dates}`;
				}
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
				endLabel: named ? endLabel(colourOf(name, p), label(name)) : undefined,
				emphasis: { focus: 'series' },
				// Silent: the rule is a mark, not a hover target. What it means is read
				// off the axis tooltip, which fires anywhere in the year's column.
				markLine:
					i === 0 && eventMarks.length
						? {
								silent: true,
								symbol: 'none',
								lineStyle: { color: p.inkFaint, width: 1, type: 'solid', opacity: 0.35 },
								label: { show: false },
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
		const p = colours;
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
				data: years.map((y) => {
					const row = block.rows.find(
						(candidate) => String(candidate.period) === y && candidate.category === category
					);
					return row ? { value: row.speech_rate, held: row.held } : null;
				}),
				connectNulls: false,
				symbol: 'none',
				lineStyle: { width: 2, color: ramp[i % ramp.length] },
				itemStyle: { color: ramp[i % ramp.length] },
				emphasis: { focus: 'series' }
			}))
		};
	});

	const genocideBreaks = $derived(data.breaks.series.genocide ?? {});
	const genocideInference = $derived(data.breaks.inference.series.genocide ?? {});

	function drillChronology(params: { name?: string; seriesName?: string }) {
		if (!params.name || !params.seriesName) return;
		const internal = Object.keys(allMeasures).find((name) => label(name) === params.seriesName);
		if (!internal || internal.startsWith('set:') || internal.startsWith('register:')) return;
		const year = params.name.slice(0, 4);
		void goto(`${resolve('/concordance')}?term=${internal}&from=${year}&to=${year}`);
	}
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
		download={{
			name: ['unsc', 'lexicon-over-time', grain],
			table: seriesTable,
			chart: () => seriesFigure?.svg() ?? null
		}}
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
					{data.overlay.events.length}
					<a href="#reference-dates">reference dates</a>; hover anywhere in such a year to read the
					date and what it marks, below that year's values. They annotate the chart and explain
					nothing in it &mdash; see the caveat below.{:else}Reference dates are hidden.{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>The two raw units measure the corpus, not the discourse.</strong> The Council held {count(
					source.corpus.speeches[0]
				)} speeches in {source.periods[0]} and
				{count(source.corpus.speeches[source.corpus.speeches.length - 1])} in
				{source.periods[source.periods.length - 1]}; any series not divided by that is mostly a
				picture of that growth.
			</p>
			<p>
				Sets (<em>atrocity core</em>, <em>Rome triad</em>) have no occurrence count of their own,
				because a speech using two of their members would be counted twice. They appear only in the
				two share-based units.
			</p>
		{/snippet}

		<Chart
			bind:this={seriesFigure}
			option={main}
			height="420px"
			description="Time series of selected lexicon terms in the chosen unit."
			onclick={drillChronology}
		/>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the plotted values as a table</summary>
			<table>
				<thead
					><tr
						><th>Period</th
						>{#each selected.filter((name) => !unavailable.includes(name)) as name (name)}<th
								class="num">{label(name)}</th
							>{/each}</tr
					></thead
				>
				<tbody>
					{#each periods as period, index (period)}
						<tr
							><td>{period}</td
							>{#each selected.filter((name) => !unavailable.includes(name)) as name (name)}<td
									class="num"
									>{unit === 'speech_rate'
										? percent(Number(allMeasures[name][unit]?.[index] ?? 0))
										: decimal(Number(allMeasures[name][unit]?.[index] ?? 0))}</td
								>{/each}</tr
						>
					{/each}
				</tbody>
			</table>
		</details>
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
		title="Does the vocabulary have a calendar?"
		question="At month resolution, are there times of year the Council reaches for this vocabulary more than others?"
		source="04_series.py → series/monthly.json"
		note="Colour is a rate, never a count. Twice as dark is not twice the rate — read the key. A hatched cell is withheld, not a zero."
		download={{
			name: ['unsc', 'month-grid', gridMeasure],
			table: monthTable,
			chart: () => gridFigure?.svg() ?? null
		}}
	>
		{#snippet controls()}
			<label>
				Measure
				<select bind:value={gridMeasure}>
					{#each gridMeasures as name (name)}<option value={name}>{termLabel(name)}</option>{/each}
				</select>
			</label>
			<label>
				Unit
				<select bind:value={gridUnit}>
					{#each gridUnits as u (u)}
						<option value={u}>{u === 'speech_rate' ? 'Share of speeches' : 'Per 100k words'}</option
						>
					{/each}
				</select>
			</label>
			<span class="unit-note">{count(heat.drawn)} of {count(heat.cells.length)} months drawn</span>
		{/snippet}

		{#snippet reading()}
			<p>
				One square per month, {byMonth.years[0]}–{byMonth.years[byMonth.years.length - 1]}, years
				down and months across. Colour runs from the page's own tone at nothing to the darkest at
				<strong>{showRate(heat.high)}</strong>, the strongest month in the grid. The ramp starts at
				zero rather than at the quietest month, so a month in which nobody said the word looks empty
				— which it was.
			</p>
			<p>
				<strong>The ramp is not proportional.</strong> These rates are skewed — the middle month is
				around
				{showRate(byMonth.corpus_speech_prevalence)} and the strongest is {showRate(heat.high)} — so a
				colour proportional to the value would leave half the grid indistinguishable from the page. The
				ramp is on the square root instead: the order of every cell is preserved and nothing is capped,
				but the key, not the darkness, is what a value should be read off.
			</p>
			<p>
				<strong>Hatched squares carry no rate.</strong>
				{count(heat.withheld)} of the {count(heat.cells.length)} months hold fewer than
				{count(heat.minimum)} speeches. They keep their counts in the table and the download; what they
				do not get is a colour, because a pale square would say "quiet" where the record says "barely
				sat".
			</p>
		{/snippet}
		{#snippet caveat()}
			{#if column.shared}
				<p>
					<strong>The bright months are largely a reporting calendar.</strong>
					{strongest.map((row) => row.name).join(' and ')} are the strongest months, and the largest agenda
					item behind the speeches in both is
					<em>{column.shared}</em>. The tribunals reported to the Council semi-annually, so what is
					most visible here is partly when the Council was scheduled to discuss this, not when it
					chose to. The table below the pooled figure gives the attribution month by month.
				</p>
			{/if}
			<p>
				{byMonth.minimum_speeches_rule}
			</p>
			<p>
				A month's vocabulary is the vocabulary of the debates held in it. That is the same confound
				the <a href="{resolve('/actors')}#speaker-keyness">per-speaker keyness</a> step spends its whole
				design controlling for, and nothing here controls for it.
			</p>
		{/snippet}

		{#if heat.refusal}
			<p class="empty">
				{#if heat.refusal === 'none-drawable'}
					No month in this corpus cleared {count(heat.minimum)} speeches, so there is nothing here that
					could be drawn honestly.
				{:else}
					This measure is not in the artefact.
				{/if}
			</p>
		{:else}
			<Heatmap
				bind:this={gridFigure}
				plan={heat}
				label={cellLabel}
				unit={unitName}
				format={showRate}
				description="Year by month grid of {termLabel(gridMeasure)}, {byMonth.years[0]}–{byMonth
					.years[byMonth.years.length - 1]}, as a {unitName}."
			/>
			<details class="data-table">
				<summary><Icon icon={ChevronRight} />View the grid as a table</summary>
				<p class="hint">
					A dash is a month with no published rate. Each year links to its lines in the concordance
					— the year, not the month: the concordance filters by year, so what opens is wider than
					any one square here.
				</p>
				<table>
					<thead>
						<tr>
							<th>Year</th>
							{#each heat.months as month (month)}
								<th class="num"
									>{monthLabel(`2000-${String(month).padStart(2, '0')}`).slice(0, 3)}</th
								>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each heat.years as year (year)}
							<tr>
								<td
									><a href="{resolve('/concordance')}?term={gridMeasure}&from={year}&to={year}"
										>{year}</a
									></td
								>
								{#each heat.months as month (month)}
									{@const cell = heat.cells.find((c) => c.year === year && c.month === month)}
									<td class="num" title={cell ? cellLabel(cell) : ''}>
										{cell && cell.state === 'drawn' ? showRate(cell.value) : '—'}
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</details>
		{/if}
	</Figure>

	<Figure
		title="The same twelve months, pooled"
		question="Across thirty-two years, which months of the year carry the vocabulary — and what was on the agenda in them?"
		source="04_series.py → series/monthly.json"
		note="A different denominator from any square in the grid above. The two do not share a scale."
		download={{ name: ['unsc', 'month-of-year', gridMeasure], table: calendarTable }}
	>
		{#snippet reading()}
			<p>
				Each row pools every {byMonth.years.length} instances of that month. The bar in the row's own
				background is the figure beside it, so there is no second rendering that could drift from the
				numbers.
			</p>
			<p>
				<strong>Without</strong> repeats the figure with {column.excludedYears.join(' and ')} dropped
				— the corpus's two largest years for this vocabulary. A calendar pattern that is really one spike
				seen through a monthly lens would not survive their removal.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>{byMonth.month_of_year.rule}</p>
			<p>{byMonth.month_of_year.agenda_rule}</p>
		{/snippet}

		{#if column.refusal}
			<p class="empty">This measure is not in the calendar block.</p>
		{:else}
			<table class="calendar">
				<thead>
					<tr>
						<th>Month</th>
						<th class="num">Speeches</th>
						<th class="num">Bearing</th>
						<th class="num">Rate</th>
						<th class="num">Without {column.excludedYears.join('/')}</th>
						<th>Largest item behind them</th>
					</tr>
				</thead>
				<tbody>
					{#each column.rows as row (row.month)}
						<tr style:--w="{(row.weight * 100).toFixed(1)}%">
							<th scope="row">{row.name}</th>
							<td class="num">{count(row.held)}</td>
							<td class="num">{count(row.speeches)}</td>
							<td class="num">{showRate(row.value)}</td>
							<td class="num soft">{showRate(row.without)}</td>
							<td class="item">
								{#if row.agenda.length}
									{row.agenda[0].item}
									<span class="soft"
										>{count(row.agenda[0].speeches)} · {percent(row.agenda[0].share)}</span
									>
								{:else}
									—
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</Figure>

	<Figure
		title="Rate heterogeneity in the genocide series"
		question="Where is the strongest denominator-aware two-rate contrast?"
		source="04_series.py → series/change_points.json"
		download={{ name: ['unsc', 'rate-heterogeneity'], table: breaksTable }}
	>
		{#snippet reading()}
			<p>
				Each row is a denominator-aware two-rate model of the same annual series. Speech prevalence
				uses a
				<strong>binomial</strong> likelihood; occurrences use a <strong>Poisson</strong> likelihood
				with annual token counts as exposure. The reported p-value is from
				{count(data.breaks.inference.trials)} no-change simulations that repeat the full breakpoint search.
			</p>
			<p>
				The acceptance threshold is {percent(data.breaks.inference.per_test_alpha)} after
				{data.breaks.inference.correction.toLowerCase()}. Confidence intervals describe the
				aggregated rate on each side of the selected partition.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>{data.breaks.inference.caveat}</p>
			<p>
				Minimum segment {data.breaks.parameters.min_size} periods, so a single anomalous year cannot be
				reported as a regime.
			</p>
		{/snippet}

		<table>
			<thead>
				<tr>
					<th>Unit</th>
					<th>Partition</th>
					<th class="num">Earlier</th>
					<th class="num">Later</th>
					<th class="num">Ratio</th>
					<th class="num">p</th>
				</tr>
			</thead>
			<tbody>
				{#each Object.entries(genocideInference) as [name, result] (name)}
					{#if !result || !result.accepted}
						<tr class="none">
							<td>{UNITS.find((u) => u.id === name)?.label ?? name}</td>
							<td colspan="5">constant annual rate not rejected after correction</td>
						</tr>
					{:else}
						<tr>
							<td>{UNITS.find((u) => u.id === name)?.label ?? name}</td>
							<td><strong>{result.label}</strong></td>
							<td class="num"
								>{name === 'speech_rate'
									? percent(result.before)
									: decimal(result.before * 100000)}</td
							>
							<td class="num"
								>{name === 'speech_rate'
									? percent(result.after)
									: decimal(result.after * 100000)}</td
							>
							<td
								class="num"
								class:up={(result.ratio ?? 0) > 1}
								class:down={(result.ratio ?? 1) < 1}
								>{result.ratio == null ? '—' : `${decimal(result.ratio)}×`}</td
							>
							<td class="num">{result.p_value.toFixed(4)}</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
		<details class="data-table">
			<summary><Icon icon={ChevronRight} />View the exploratory WBS diagnostics</summary>
			<p>{data.breaks.caveat}</p>
			<table>
				<thead><tr><th>Unit</th><th>Candidate</th><th class="num">Diagnostic p</th></tr></thead>
				<tbody
					>{#each Object.entries(genocideBreaks) as [name, breaks] (name)}{#each breaks as item (item.index)}<tr
								><td>{UNITS.find((unit) => unit.id === name)?.label ?? name}</td><td
									>{item.label}</td
								><td class="num">{item.p_value.toFixed(4)}</td></tr
							>{/each}{/each}</tbody
				>
			</table>
		</details>
	</Figure>

	<Figure
		title="Who says it, and in what debate"
		question="Is the rise or fall concentrated in one kind of speaker, or one part of the agenda?"
		source="04_series.py → series/breakdowns.json"
		download={{
			name: ['unsc', 'breakdowns', split],
			table: splitsTable,
			chart: () => splitFigure?.svg() ?? null
		}}
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
				Delivery language partly restates who is speaking. VTC records are shown as unknown rather
				than inferred English because their document format carries no language marker.
			</p>
		{/snippet}

		{#if splitChart}
			<Chart
				bind:this={splitFigure}
				option={splitChart}
				height="380px"
				description="Rate of genocide invocation per year, split by the chosen category."
			/>
		{:else}
			<p class="empty">Choose a split above to break the series apart.</p>
		{/if}
	</Figure>

	<section class="events" id="reference-dates">
		<h2>Reference dates</h2>
		<p class="hint">
			{data.overlay.events.length} hand-curated dates used to annotate the chart above. Each links to
			the primary institutional record used to verify its date and description. The overlay is context,
			not evidence that an event caused a change in Council language.
		</p>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
		<div class="table-scroll" role="region" aria-label="Reference dates table" tabindex="0">
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
							<td><a href={e.source_url}>{e.source}</a></td>
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

	label {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	label.check {
		gap: var(--sp-2);
	}

	select {
		max-width: 16rem;
	}

	.unit-note {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
		margin-left: auto;
	}

	.picker {
		margin: 0 0 var(--sp-7);
	}

	.picker h2 {
		font-size: var(--step-2);
	}

	.hint {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
		max-width: var(--measure);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-1);
	}

	/* A term chip is a control that names a series, so it carries the series'
	   colour on one edge and takes the ink of a control everywhere else. No
	   radius, and no filling a button with a data colour. */
	.chip {
		border: var(--hair) solid var(--rule-strong);
		border-left: 3px solid var(--chip);
		background: none;
		color: var(--ink-2);
		padding: var(--sp-1) var(--sp-3);
		min-height: 2rem;
		font-family: var(--sans);
		font-size: var(--step--2);
		cursor: pointer;
		line-height: 1.5;
	}

	.chip:hover {
		border-color: var(--ink-2);
		border-left-color: var(--chip);
		color: var(--ink);
	}

	.chip.on {
		background: var(--ink);
		border-color: var(--ink);
		border-left-color: var(--chip);
		color: var(--paper);
	}

	.warn {
		margin: calc(-1 * var(--sp-6)) 0 var(--sp-6);
		padding: var(--sp-2) var(--sp-3);
		border-left: 2px solid var(--reg-contentious);
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
	}

	.empty {
		color: var(--ink-3);
		font-size: var(--step--1);
		padding: var(--sp-6) 0;
		text-align: center;
	}

	/* The bar *is* the table. Length is drawn in the row's own background, so the
	   figure and the numbers are one element and there is no second rendering to
	   drift from the first — the same decision the per-speaker keyness view made.
	   A tint rather than the full colour, because text sits on top of it. */
	.calendar tbody tr {
		/* The zebra stripe `app.css` puts on every other row is switched off: the
		   bar is translucent, so a stripe behind it would draw the same length in
		   two different colours down the column. */
		background-color: transparent;
		background-image: linear-gradient(
			to right,
			color-mix(in oklab, var(--reg-accountability) 24%, transparent) 0 var(--w, 0%),
			transparent var(--w, 0%)
		);
	}

	.calendar tbody th {
		font-weight: 600;
		white-space: nowrap;
		text-transform: none;
		letter-spacing: 0;
		font-size: var(--step--1);
		color: var(--ink);
	}

	.calendar .item {
		font-size: var(--step--2);
	}

	.calendar .soft {
		color: var(--ink-3);
	}

	.calendar .item .soft {
		font-family: var(--mono);
		margin-inline-start: var(--sp-2);
	}

	/* Direction, not judgement: a ratio above one is not a bad thing, so these
	   are the semantic states rather than the register ramp. */
	.num.up {
		color: var(--state-bad);
	}

	.num.down {
		color: var(--state-ok);
	}

	tr.none td {
		color: var(--ink-3);
		font-style: italic;
	}

	.events {
		margin-top: var(--sp-6);
	}

	.events h2 {
		font-size: var(--step-2);
	}

	.table-scroll {
		max-width: 100%;
		overflow-x: auto;
	}

	.date {
		white-space: nowrap;
		font-family: var(--mono);
		font-variant-numeric: tabular-nums;
	}

	.note {
		color: var(--ink-3);
	}

	.kind {
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}
</style>
