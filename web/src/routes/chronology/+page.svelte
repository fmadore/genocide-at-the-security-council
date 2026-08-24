<script lang="ts">
	import { goto, replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Chart from '$lib/Chart.svelte';
	import Figure from '$lib/Figure.svelte';
	import Heatmap from '$lib/Heatmap.svelte';
	import Icon from '$lib/Icon.svelte';
	import PageMeta from '$lib/PageMeta.svelte';
	import {
		chronologyParams,
		readChronologyState,
		splitEvidenceQuery,
		type ChronologyChoices,
		type ChronologyUnit as Unit
	} from '$lib/chronology';
	import { provenanceOf } from '$lib/export';
	import type { ExportRequest } from '$lib/export';
	import {
		CALENDAR_COLUMNS,
		GRID_COLUMNS,
		calendar,
		calendarRows,
		evidence,
		grid as monthGrid,
		gridRows,
		measures as monthlyMeasures,
		pooledEvidence,
		termsOf,
		units as monthlyUnits
	} from '$lib/heatmap';
	import type { CalendarRow, Cell, Unit as GridUnit } from '$lib/heatmap';
	import { count, decimal, escapeHtml, isoDate, monthLabel, percent, termLabel } from '$lib/format';
	import { PAGE_METADATA } from '$lib/seo';
	import {
		axisX,
		axisY,
		categorical,
		colours,
		endLabel,
		grid,
		legend,
		registerColour,
		textStyle,
		tooltip
	} from '$lib/theme';
	import type { BreakdownRow, CouncilEvent, Measure } from '$lib/types';
	import type { EChartsOption } from 'echarts';
	import { onMount, tick } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const UNITS: { id: Unit; label: string; note: string }[] = [
		{
			id: 'speech_rate',
			label: 'Share of speeches',
			note: 'speeches using the term ÷ speeches held'
		},
		{
			id: 'token_rate',
			label: 'Per 100k words',
			note: 'occurrences ÷ words spoken × 100,000'
		},
		{
			id: 'occurrences',
			label: 'Occurrences',
			note: 'raw count — tracks how much the Council spoke'
		},
		{ id: 'speeches', label: 'Speeches', note: 'raw count — tracks how much the Council spoke' }
	];

	let unit = $state<Unit>('speech_rate');
	let grain = $state<'year' | 'quarter'>('year');
	let selected = $state<string[]>(['genocide']);
	let showEvents = $state(true);
	let split = $state<string>('none');
	let urlReady = $state(false);

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

	/* --- Opening the evidence behind a square ------------------------------
	   This figure shipped linking each *year*, because the concordance filtered
	   by year and a square could not open itself. It can now, and the rule for
	   when it may is one line: the concordance is a file per term, so a measure
	   that resolves to several declines rather than offering one member's lines
	   as the square's evidence. 384 cells cannot each carry five links, and the
	   note under the table says which case a reader is in. */
	const gridTerms = $derived(termsOf(byMonth, gridMeasure));
	const linkable = $derived(gridTerms.length === 1);
	const cellLink = (cell: Cell) =>
		linkable ? (evidence(byMonth, gridMeasure, cell)[0] ?? null) : null;
	const rowLink = (row: CalendarRow) =>
		linkable ? (pooledEvidence(byMonth, gridMeasure, row)[0] ?? null) : null;

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
			title: 'The word list over time',
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
			title: 'Testing for a change in the rate',
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
	const colourOf = (name: string, p = $colours) =>
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
		const p = $colours;
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
		{ id: 'entity_type', label: 'Kind of speaker' },
		{ id: 'participanttype', label: 'Participant type' },
		{ id: 'agenda_item1', label: 'Region of agenda item' },
		{ id: 'agenda_item_manual', label: 'Agenda item' },
		{ id: 'delivery_language', label: 'Delivery language' }
	];

	const seriesNames = (source: typeof data.year) => [
		...Object.keys(source.terms),
		...Object.keys(source.registers).map((name) => `register:${name}`),
		...Object.keys(source.sets).map((name) => `set:${name}`)
	];
	const urlChoices: ChronologyChoices = $derived.by(() => ({
		series: { year: seriesNames(data.year), quarter: seriesNames(data.quarter) },
		calendar: Object.fromEntries(
			Object.entries(monthlyMeasures(data.month)).map(([name, measure]) => [
				name,
				monthlyUnits(measure)
			])
		),
		splits: SPLITS.map(({ id }) => id)
	}));

	onMount(() => {
		const state = readChronologyState(page.url.searchParams, urlChoices);
		unit = state.unit;
		grain = state.grain;
		selected = state.series;
		gridMeasure = state.calendarMeasure;
		gridUnit = state.calendarUnit;
		split = state.split;
		void tick().then(() => {
			urlReady = true;
		});
	});

	$effect(() => {
		if (!urlReady) return;
		const params = chronologyParams(
			{
				unit,
				grain,
				series: selected,
				calendarMeasure: gridMeasure,
				calendarUnit: gridUnit,
				split
			},
			urlChoices
		);
		const search = params.toString();
		replaceState(`${page.url.pathname}${search ? `?${search}` : ''}`, page.state);
	});

	const splitBlock = $derived(
		split === 'none' ? null : (data.splits.measures.genocide?.[split] ?? null)
	);

	const splitChart: EChartsOption | null = $derived.by(() => {
		const block = splitBlock;
		if (!block) return null;
		const p = $colours;
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

	function splitHref(row: BreakdownRow): string | null {
		const link = splitEvidenceQuery('genocide', split, row.category, row.period);
		return link ? `${resolve('/concordance')}?${link.query}` : null;
	}

	function drillSplit(params: { name?: string; seriesName?: string }) {
		if (!params.name || !params.seriesName) return;
		const link = splitEvidenceQuery('genocide', split, params.seriesName, params.name);
		if (link) void goto(`${resolve('/concordance')}?${link.query}`);
	}

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

<PageMeta meta={PAGE_METADATA['/chronology/']} />

<article>
	<header class="lede">
		<h1>Chronology</h1>
		<p class="standfirst">
			Every term on the list over {periods.length}
			{grain === 'year' ? 'years' : 'quarters'}, counted however you ask for it. The choice of unit
			is itself an argument: the same numbers look like a steep rise or like a flat line depending
			on what they are divided by, and both readings are offered here on purpose.
		</p>
	</header>

	<Figure
		title="The word list over time"
		question="When was each term said, and does the answer hold up once you allow for how much the Council spoke?"
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
				Pick terms from the list below the chart. Drag the bar under the axis to zoom in on a
				stretch of years, or scroll on the plot itself. Colour follows the term's
				<strong>register</strong> &mdash; the family of vocabulary it belongs to &mdash; so terms that
				do similar work in a speech share a hue.
			</p>
			<p>
				{#if showEvents && grain === 'year'}Faint vertical lines mark the years carrying one of the
					{data.overlay.events.length}
					<a href="#reference-dates">reference dates</a>. Hover anywhere inside such a year to read
					the date and what it marks, listed below that year's values. They are there for context
					and explain nothing in the chart &mdash; see the note below.{:else}Reference dates are
					hidden.{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>The two raw counts measure the Council's output, not its language.</strong> The
				Council held {count(source.corpus.speeches[0])} speeches in {source.periods[0]} and
				{count(source.corpus.speeches[source.corpus.speeches.length - 1])} in
				{source.periods[source.periods.length - 1]}. A line that is not divided by that is mostly a
				picture of the growth.
			</p>
			<p>
				Sets of terms (<em>atrocity core</em>, <em>Rome triad</em>) have no occurrence count of
				their own, because a speech using two members of the set would be counted twice. They are
				available only in the two share-based units.
			</p>
		{/snippet}

		<Chart
			bind:this={seriesFigure}
			option={main}
			height="420px"
			description="Line chart of the selected terms over time, in the chosen unit."
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
			{unavailable.map(label).join(', ')} cannot be shown in this unit, because a set of terms has no
			occurrence count of its own. Switch to a share-based unit to see it.
		</p>
	{/if}

	<section class="picker">
		<h2>Terms</h2>
		<p class="hint">
			Grouped by register. A <strong>set</strong> counts several terms together; a
			<strong>register</strong> counts every term in one family of vocabulary at once.
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
		question="Month by month, are there times of year when the Council reaches for this vocabulary more than others?"
		source="04_series.py → series/monthly.json"
		note="Shading always carries a rate, never a count. Twice as dark is not twice the rate — read the key. A hatched square has no rate; it is not a zero."
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
				One square per month, {byMonth.years[0]}–{byMonth.years[byMonth.years.length - 1]}, with
				years running down and months across. The shading runs from the colour of the page at zero
				to the darkest tone at <strong>{showRate(heat.high)}</strong>, the strongest month in the
				grid. It starts at zero rather than at the quietest month, so a month in which nobody said
				the word looks empty, which is what it was.
			</p>
			<p>
				<strong>The shading is deliberately not proportional.</strong> A handful of months sit far
				above the rest: the middle month runs at about
				{showRate(byMonth.corpus_speech_prevalence)} and the strongest at {showRate(heat.high)}.
				Shading in direct proportion would leave half the grid indistinguishable from the page, so
				it follows the square root of the rate instead. Every square keeps its place in the order
				and nothing is cut off at the top, but the number should be read off the key rather than
				guessed from the darkness.
			</p>
			<p>
				<strong>Hatched squares carry no rate.</strong>
				{count(heat.withheld)} of the {count(heat.cells.length)} months hold fewer than
				{count(heat.minimum)} speeches. Their counts stay in the table and in the download; what they
				do not get is a shade. The note opposite says why.
			</p>
		{/snippet}
		{#snippet caveat()}
			{#if column.shared}
				<p>
					<strong>The darkest months largely follow a reporting timetable.</strong>
					{strongest.map((row) => row.name).join(' and ')} are the strongest months, and the agenda item
					behind most of the speeches in both is
					<em>{column.shared}</em>. The international tribunals reported to the Council twice a
					year, so what stands out here is partly when the Council was scheduled to discuss the
					subject rather than when it chose to. The table under the pooled figure below names the
					agenda item behind each month.
				</p>
			{/if}
			<p>
				{byMonth.minimum_speeches_rule}
			</p>
			<p>
				A month's vocabulary is the vocabulary of whatever debates were held in it. That is the same
				problem the
				<a href="{resolve('/actors')}#speaker-keyness">speaker-by-speaker comparison</a> on the Actors
				page is designed around, and nothing in this figure corrects for it.
			</p>
		{/snippet}

		{#if heat.refusal}
			<p class="empty">
				{#if heat.refusal === 'none-drawable'}
					No month in this corpus reached {count(heat.minimum)} speeches, so there is nothing here that
					could be drawn honestly.
				{:else}
					This measure is not in the data.
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
					A dash marks a month with no published rate.
					{#if linkable}
						Every number opens that month's lines in the concordance, that month alone rather than
						the year around it. Months with no rate link too: the minimum applies to the rate, and
						the lines beneath it are the record itself rather than an estimate drawn from it.
					{:else}
						The numbers do not link here. The concordance shows one term at a time, and
						<em>{termLabel(gridMeasure)}</em>
						gathers {gridTerms.length} of them ({gridTerms.map(termLabel).join(', ')}). Select one
						of those above to open a month's lines.
					{/if}
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
								<!-- No longer a link: the year was what this table could offer when a
								     square could not open itself, and offering both would leave a
								     reader one click from the wider answer for no reason. -->
								<td>{year}</td>
								{#each heat.months as month (month)}
									{@const cell = heat.cells.find((c) => c.year === year && c.month === month)}
									{@const link = cell ? cellLink(cell) : null}
									<td class="num" title={cell ? cellLabel(cell) : ''}>
										{#if cell && link}
											<a href="{resolve('/concordance')}?{link.query}"
												>{cell.state === 'drawn' ? showRate(cell.value) : '—'}</a
											>
										{:else}
											{cell && cell.state === 'drawn' ? showRate(cell.value) : '—'}
										{/if}
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
		note="These rows are measured against a different total from any square in the grid above, so the two figures do not share a scale."
		download={{ name: ['unsc', 'month-of-year', gridMeasure], table: calendarTable }}
	>
		{#snippet reading()}
			<p>
				Each row gathers all {byMonth.years.length} instances of that month across the corpus. The bar
				behind a row is drawn from the number printed beside it, so the two cannot drift apart.
			</p>
			<p>
				<strong>Without</strong> repeats the figure with {column.excludedYears.join(' and ')} removed.
				Those are the corpus's two largest years for this vocabulary, and a seasonal pattern that is really
				one spike seen through a monthly lens would not survive their removal.
			</p>
			<p>
				{#if linkable}
					Each month opens every instance of it in the concordance: all {byMonth.years.length} Junes rather
					than one of them, which is what the row is measured against.
				{:else}
					The months do not link here. <em>{termLabel(gridMeasure)}</em> gathers {gridTerms.length} terms,
					and the concordance shows one at a time.
				{/if}
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>{byMonth.month_of_year.rule}</p>
			<p>{byMonth.month_of_year.agenda_rule}</p>
		{/snippet}

		{#if column.refusal}
			<p class="empty">This measure has no pooled-month figures.</p>
		{:else}
			<table class="calendar">
				<thead>
					<tr>
						<th>Month</th>
						<th class="num">Speeches</th>
						<th class="num">Using the term</th>
						<th class="num">Rate</th>
						<th class="num">Without {column.excludedYears.join('/')}</th>
						<th>Largest agenda item behind them</th>
					</tr>
				</thead>
				<tbody>
					{#each column.rows as row (row.month)}
						{@const link = rowLink(row)}
						<tr style:--w="{(row.weight * 100).toFixed(1)}%">
							<!-- Every year's June, which is what this row pools — so the link
							     carries the month and no year bound at all. -->
							<th scope="row">
								{#if link}<a href="{resolve('/concordance')}?{link.query}">{row.name}</a
									>{:else}{row.name}{/if}
							</th>
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
		title="Testing for a change in the rate"
		question="Is the genocide series better described by one steady rate, or by two?"
		source="04_series.py → series/change_points.json"
		download={{ name: ['unsc', 'rate-change'], table: breaksTable }}
	>
		{#snippet reading()}
			<p>
				Each row asks the same question of the same annual series in a different unit: split the
				years at the best possible point, and is the difference between the two halves larger than
				chance would produce? The share of speeches is modelled as a series of coin flips; the count
				of occurrences is modelled against the number of words spoken each year, so a talkative year
				is expected to contain more of everything.
			</p>
			<p>
				The p-value comes from {count(data.breaks.inference.trials)} simulated series in which the rate
				never changes and the whole search is repeated from scratch. A result counts only below
				{percent(data.breaks.inference.per_test_alpha)}, a threshold already tightened to allow for
				several tests being run at once ({data.breaks.inference.correction}). The intervals describe
				the combined rate on either side of the split.
			</p>
		{/snippet}
		{#snippet caveat()}
			<p>{data.breaks.inference.caveat}</p>
			<p>
				Each side of a split must cover at least {data.breaks.parameters.min_size} periods, so a single
				unusual year cannot be reported as a lasting change.
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
							<td colspan="5">no change detected; one steady rate survives the test</td>
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
			<summary><Icon icon={ChevronRight} />View the second, exploratory change-point method</summary
			>
			<p>{data.breaks.caveat}</p>
			<table>
				<thead><tr><th>Unit</th><th>Candidate year</th><th class="num">Diagnostic p</th></tr></thead
				>
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
				Each line is one category measured against itself: speeches in that category using
				<code>genocid*</code>, divided by all speeches in that category. Every line is therefore
				scaled to its own output, and a category that spoke rarely is not pushed down the chart for
				having spoken rarely.
			</p>
			{#if split === 'participanttype'}
				<p>
					Participant type is the role recorded for the speech in the source corpus. Each plotted
					point links to the matching concordance lines for that role and year.
				</p>
			{/if}
		{/snippet}
		{#snippet caveat()}
			<p>
				<strong>A rate says nothing about how much evidence is behind it.</strong> A category with twenty
				speeches in a year can swing between 0% and 25% on a single mention. A line breaks where the category
				held no speeches at all that year.
			</p>
			<p>
				Delivery language partly restates who is speaking. Speeches given by video link are shown as
				unknown rather than assumed to be English, because that document format carries no marker of
				the language either way.
			</p>
			<p>
				An em dash in the evidence column means the concordance artifact does not carry that split,
				not that the category has no speeches. Speaker group, participant type and agenda item do
				carry exact evidence links.
			</p>
		{/snippet}

		{#if splitChart}
			<Chart
				bind:this={splitFigure}
				option={splitChart}
				height="380px"
				description="Share of speeches using genocide per year, one line per category of the chosen split."
				onclick={drillSplit}
			/>
			<details class="data-table">
				<summary><Icon icon={ChevronRight} />View denominators and evidence</summary>
				<table>
					<thead>
						<tr>
							<th>Period</th><th>Category</th><th class="num">Speeches held</th><th class="num"
								>Using genocide</th
							><th class="num">Share</th><th>Evidence</th>
						</tr>
					</thead>
					<tbody>
						{#each splitBlock?.rows ?? [] as row (row.period + row.category)}
							{@const href = splitHref(row)}
							<tr>
								<td>{row.period}</td><td>{row.category}</td><td class="num">{count(row.held)}</td
								><td class="num">{count(row.speeches)}</td><td class="num"
									>{percent(row.speech_rate)}</td
								><td
									>{#if href}<a {href}>Read lines</a>{:else}—{/if}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</details>
		{:else}
			<p class="empty">Choose a split above to break the series apart.</p>
		{/if}
	</Figure>

	<section class="events" id="reference-dates">
		<h2>Reference dates</h2>
		<p class="hint">
			{data.overlay.events.length} dates, selected by hand, used to mark the chart above. Each links to
			the official record used to verify its date and description. They are there for context; a date
			falling near a change in the chart is not evidence that it produced the change.
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

	/* Reads on after the controls rather than being flung to the right edge.
	   `margin-left: auto` put up to 1,000px between this and the control whose
	   state it reports, and when the bar wrapped it stranded the note alone on a
	   second line, still hard right — furthest from everything it describes. */
	.unit-note {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
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
