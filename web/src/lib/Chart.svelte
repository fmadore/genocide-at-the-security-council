<script lang="ts">
	/**
	 * An ECharts figure that resizes with its container, follows the colour
	 * scheme, and tears itself down.
	 *
	 * Only the chart and component types used by the dashboard are registered;
	 * this keeps ECharts tree-shakeable while `init` remains browser-only.
	 *
	 * SVG, not canvas. These figures are the part of the site most likely to
	 * leave it — into a slide, a paper, a printout — and only SVG survives that
	 * at any size. It also means the text in a chart is real text: selectable,
	 * searchable, and rendered in the same faces as the page around it.
	 */
	import { BarChart, GraphChart, LineChart, ScatterChart } from 'echarts/charts';
	import {
		AriaComponent,
		DataZoomComponent,
		GridComponent,
		LegendComponent,
		MarkLineComponent,
		TooltipComponent
	} from 'echarts/components';
	import { init, use } from 'echarts/core';
	import { onMount } from 'svelte';
	import type { EChartsOption } from 'echarts';
	import type { EChartsType } from 'echarts/core';
	import { SVGRenderer } from 'echarts/renderers';

	use([
		BarChart,
		LineChart,
		ScatterChart,
		GraphChart,
		GridComponent,
		TooltipComponent,
		LegendComponent,
		DataZoomComponent,
		MarkLineComponent,
		AriaComponent,
		SVGRenderer
	]);

	interface Props {
		option: EChartsOption;
		height?: string;
		/** Announced to screen readers in place of the drawing. */
		description: string;
		onclick?: (params: {
			name?: string;
			seriesName?: string;
			value?: unknown;
			dataType?: string;
			data?: unknown;
		}) => void;
	}

	let { option, height = '340px', description, onclick }: Props = $props();

	let element: HTMLDivElement;
	let chart: EChartsType | undefined;
	let ready = $state(false);

	onMount(() => {
		chart = init(element, undefined, { renderer: 'svg' });
		chart.setOption({
			animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
			aria: { enabled: true, decal: { show: true } },
			...option
		});
		if (onclick) chart.on('click', (params) => onclick(params as never));
		const observer = new ResizeObserver(() => chart?.resize());
		observer.observe(element);
		ready = true;
		return () => {
			observer.disconnect();
			chart?.dispose();
		};
	});

	// `notMerge` so a series removed by a filter actually disappears rather than
	// lingering underneath the new one.
	$effect(() => {
		if (chart && ready) {
			chart.setOption(
				{
					animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
					aria: { enabled: true, decal: { show: true } },
					...option
				},
				{ notMerge: true }
			);
		}
	});
</script>

<figure class="chart" style:height role="img" aria-label={description}>
	<div bind:this={element} class="plot"></div>
	{#if !ready}
		<p class="loading">Drawing…</p>
	{/if}
</figure>

<style>
	.chart {
		margin: 0;
		position: relative;
		width: 100%;
	}

	.plot {
		width: 100%;
		height: 100%;
	}

	.loading {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}
</style>
