<script lang="ts">
	/**
	 * An ECharts canvas that resizes with its container, follows the colour
	 * scheme, and tears itself down.
	 *
	 * Only the chart and component types used by the dashboard are registered;
	 * this keeps ECharts tree-shakeable while `init` remains browser-only.
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
	import { CanvasRenderer } from 'echarts/renderers';

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
		CanvasRenderer
	]);

	interface Props {
		option: EChartsOption;
		height?: string;
		/** Announced to screen readers in place of the canvas. */
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
		chart = init(element, undefined, { renderer: 'canvas' });
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
	<div bind:this={element} class="canvas"></div>
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

	.canvas {
		width: 100%;
		height: 100%;
	}

	.loading {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		margin: 0;
		color: var(--ink-faint);
		font-size: 0.875rem;
	}
</style>
