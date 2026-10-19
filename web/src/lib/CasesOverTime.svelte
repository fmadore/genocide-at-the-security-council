<script lang="ts">
	/**
	 * Cases over time: which situations the word is applied to, year by year,
	 * and how much of its use is applied to none.
	 *
	 * A renderer over `#lib/timeline`, which decides what is stacked and when a
	 * share is withheld. Two panels on one year axis, so a reader can line up a
	 * change in the cases with a change in the no-case share without a second
	 * scale on the same plot. A bar opens that case in that year in the
	 * concordance.
	 */
	import type { BarSeriesOption, EChartsOption, LineSeriesOption } from 'echarts';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Chart from '#lib/Chart.svelte';
	import Figure from '#lib/Figure.svelte';
	import { provenanceOf } from '#lib/export.js';
	import type { ExportRequest } from '#lib/export.js';
	import { count, percent } from '#lib/format.js';
	import { axisX, axisY, categoricalData, colours, textStyle, tooltip } from '#lib/theme.js';
	import {
		OTHER_CASES,
		TIMELINE_COLUMNS,
		timelineExportRows,
		timelineLink,
		timelinePlan
	} from '#lib/timeline.js';
	import type { Usage } from '#lib/types.js';

	let { data, status }: { data: Usage; status: string | null } = $props();

	const plan = $derived(timelinePlan(data));
	let chart = $state<Chart | null>(null);

	const option: EChartsOption = $derived.by(() => {
		const p = $colours;
		const fills = categoricalData(p);
		const labels = plan.years.map(String);
		return {
			textStyle,
			// No hatch: on this site a hatch means a withheld value (see the overview).
			aria: { enabled: true, decal: { show: false } },
			legend: {
				type: 'scroll',
				top: 0,
				icon: 'rect',
				itemWidth: 10,
				itemHeight: 10,
				itemGap: 14,
				textStyle: { color: p.inkSoft, fontSize: 12 },
				data: plan.series.map((s) => s.label)
			},
			grid: [
				{
					left: 2,
					right: 16,
					top: 44,
					height: '56%',
					outerBoundsMode: 'same',
					outerBoundsContain: 'axisLabel'
				},
				{
					left: 2,
					right: 16,
					top: '76%',
					bottom: 4,
					outerBoundsMode: 'same',
					outerBoundsContain: 'axisLabel'
				}
			],
			tooltip: {
				...tooltip(p),
				trigger: 'axis',
				axisPointer: { type: 'shadow' },
				// One box for the whole year, whichever panel is hovered: the named
				// cases, what the pooled remainder holds, and the no-case share with
				// the count it is a share of.
				formatter: (params: unknown) => {
					const [first] = params as { dataIndex: number }[];
					const at = first?.dataIndex ?? 0;
					const lines = plan.series
						.filter((s) => s.counts[at])
						.map((s) =>
							s.id === OTHER_CASES
								? `Other cases: ${count(s.counts[at]!)} (${plan.pooled[at]!.map((o) => `${o.label} ${count(o.count)}`).join(', ')})`
								: `${s.label}: ${count(s.counts[at]!)}`
						);
					const share = plan.noCaseShare[at];
					const noCase =
						share === null || share === undefined
							? `Applied to no case: ${count(plan.noCase[at] ?? 0)} of ${count(plan.eligible[at] ?? 0)} (share withheld)`
							: `Applied to no case: ${percent(share)} of ${count(plan.eligible[at] ?? 0)}`;
					return [`<strong>${plan.years[at]}</strong>`, ...lines, noCase].join('<br>');
				}
			},
			axisPointer: { link: [{ xAxisIndex: 'all' }] },
			xAxis: [
				{ ...axisX(p), type: 'category', data: labels, gridIndex: 0, axisLabel: { show: false } },
				{ ...axisX(p), type: 'category', data: labels, gridIndex: 1 }
			],
			yAxis: [
				{
					...axisY(p),
					type: 'value',
					gridIndex: 0,
					name: 'occurrences applied to a case',
					nameTextStyle: { color: p.inkFaint, fontSize: 11, align: 'left' }
				},
				{
					...axisY(p),
					type: 'value',
					gridIndex: 1,
					min: 0,
					max: 1,
					splitNumber: 2,
					name: 'share applied to no case',
					nameTextStyle: { color: p.inkFaint, fontSize: 11, align: 'left' },
					axisLabel: { ...axisY(p).axisLabel, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }
				}
			],
			series: [
				...plan.series.map((s, at): BarSeriesOption => ({
					name: s.label,
					type: 'bar',
					stack: 'cases',
					xAxisIndex: 0,
					yAxisIndex: 0,
					data: s.counts,
					barMaxWidth: 14,
					itemStyle: { color: fills[at % fills.length] },
					tooltip: { valueFormatter: (v) => count(v as number) }
				})),
				{
					name: 'Applied to no case',
					type: 'line',
					xAxisIndex: 1,
					yAxisIndex: 1,
					data: plan.noCaseShare,
					connectNulls: false,
					showSymbol: false,
					lineStyle: { color: p.ink, width: 1.5 },
					itemStyle: { color: p.ink },
					tooltip: { valueFormatter: (v) => (v == null ? '—' : percent(v as number)) }
				} satisfies LineSeriesOption
			]
		};
	});

	function open(params: { seriesName?: string; name?: string }) {
		const series = plan.series.find((s) => s.label === params.seriesName);
		const year = Number(params.name);
		if (!series || !Number.isInteger(year)) return;
		const query = timelineLink(series.id, year);
		if (query) void goto(`${resolve('/concordance')}?${query}`);
	}

	const busiest = $derived.by(() => {
		let best = { year: 0, total: 0 };
		plan.years.forEach((year, at) => {
			const total = plan.series.reduce((sum, s) => sum + s.counts[at]!, 0);
			if (total > best.total) best = { year, total };
		});
		return best;
	});

	function table(): ExportRequest {
		return {
			title: 'Cases over time',
			columns: TIMELINE_COLUMNS,
			rows: timelineExportRows(data),
			provenance: provenanceOf(data.meta, 'usage/usage.json'),
			status,
			filters: [
				`stacked: the ${plan.series.length - 1} leading cases and the rest pooled`,
				`share withheld below ${data.minimum_occurrences} occurrences in a year`
			],
			scope:
				'every year and every referent the run assigned, including the no-case categories ' +
				'the chart shows only as a share'
		};
	}
</script>

<Figure
	title="Cases over time"
	question="Which situations is the word applied to in each year, and how often to none?"
	source="15_usage.py → usage/usage.json"
	note="Bars count occurrences the model applied to a case; the line below is a share of all of them."
	download={{
		name: ['unsc', 'usage', 'cases-over-time'],
		table,
		chart: () => chart?.svg() ?? null
	}}
>
	{#snippet reading()}
		<p>
			Each bar stacks one year's occurrences by the case the model assigned, the leading cases in
			their own colour and the rest pooled. The line below is the share the model applied to no
			case: the Convention, a tribunal's or an office's name, a general formula. Select a bar to
			read that case in that year.
		</p>
	{/snippet}
	{#snippet caveat()}
		<p>
			These are a model's labels, not yet checked against a human reading. Before 1992 a year holds
			few occurrences, so one wrong label moves it; the share is withheld below {count(
				data.minimum_occurrences
			)} occurrences.
		</p>
	{/snippet}
	{#snippet more()}
		{#if busiest.total}<p>
				The busiest year for cases is {busiest.year}, with {count(busiest.total)} occurrences.
			</p>{/if}
		<p>
			Historical referents such as the Holocaust are stacked with the cases, because a speaker
			applies the word to them as to a situation. A case the controlled list does not hold yet joins
			the pooled remainder.
		</p>
	{/snippet}

	{#if plan.refusal}
		<p class="refusal">The published run carries no dated occurrences to lay on a timeline.</p>
	{:else}
		<Chart
			bind:this={chart}
			{option}
			height="460px"
			description="Stacked bars of occurrences per year by case, and a line of the share applied to no case."
			onclick={open}
		/>
	{/if}
</Figure>

<style>
	.refusal {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}
</style>
