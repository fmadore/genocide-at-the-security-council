<script lang="ts">
	/**
	 * An ECharts canvas that resizes with its container, follows the colour
	 * scheme, and tears itself down.
	 *
	 * ECharts is imported dynamically so a page with no chart on it does not
	 * download 1 MB of charting library, and so the module never runs during
	 * prerendering, where there is no DOM.
	 */
	import { onMount } from 'svelte';
	import type { ECharts, EChartsOption } from 'echarts';

	interface Props {
		option: EChartsOption;
		height?: string;
		/** Announced to screen readers in place of the canvas. */
		description: string;
		onclick?: (params: { name?: string; seriesName?: string; value?: unknown }) => void;
	}

	let { option, height = '340px', description, onclick }: Props = $props();

	let element: HTMLDivElement;
	let chart: ECharts | undefined;
	let ready = $state(false);

	onMount(() => {
		let disposed = false;
		let observer: ResizeObserver | undefined;
		const scheme = window.matchMedia('(prefers-color-scheme: dark)');

		const redraw = () => {
			// The palette is read from CSS at build time of the option object, so
			// a scheme change has to rebuild it from the caller's side; disposing
			// and recreating is the honest way to pick up new custom properties.
			chart?.dispose();
			chart = undefined;
			void start();
		};

		async function start() {
			const echarts = await import('echarts');
			if (disposed || !element) return;
			chart = echarts.init(element, undefined, { renderer: 'canvas' });
			chart.setOption(option);
			if (onclick) chart.on('click', (params) => onclick(params as never));
			observer = new ResizeObserver(() => chart?.resize());
			observer.observe(element);
			ready = true;
		}

		void start();
		scheme.addEventListener('change', redraw);

		return () => {
			disposed = true;
			observer?.disconnect();
			scheme.removeEventListener('change', redraw);
			chart?.dispose();
		};
	});

	// `notMerge` so a series removed by a filter actually disappears rather than
	// lingering underneath the new one.
	$effect(() => {
		if (chart && ready) chart.setOption(option, { notMerge: true });
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
