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
	/**
	 * The instance, as a raw signal.
	 *
	 * `$state.raw` rather than `$state` because this is a class instance and not
	 * a value to be observed field by field, and rather than a plain `let`
	 * because the effect below must genuinely depend on it. Written as a plain
	 * variable it did not: the effect only re-ran because `ready` happened to be
	 * set in the same flush, which made the order of two effect declarations
	 * load-bearing without saying so anywhere.
	 */
	let chart = $state.raw<EChartsType | undefined>(undefined);
	let ready = $state(false);

	/**
	 * The figure's live `<svg>`, for export.
	 *
	 * Read from the DOM rather than through `getDataURL`, which returns a raster
	 * only under the canvas renderer and a data URL that would have to be
	 * unwrapped under this one. The element is what `export.ts` wants anyway: it
	 * serialises the markup and measures the box the observer last laid out.
	 */
	export function svg(): SVGSVGElement | null {
		return element?.querySelector('svg') ?? null;
	}

	export function resize(): void {
		requestAnimationFrame(() => chart?.resize());
	}

	/**
	 * The two settings every figure on this site carries, around the option the
	 * route built.
	 *
	 * Written once. Held in two places — the mount and the update — they were
	 * two copies of a decision about motion and assistive technology that a
	 * later edit could change in one and not the other.
	 */
	function framed(built: EChartsOption): EChartsOption {
		return {
			animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
			aria: { enabled: true, decal: { show: true } },
			...built
		};
	}

	// Creates the instance and wires it up. It deliberately draws nothing: the
	// effect below owns every `setOption`, including the first.
	onMount(() => {
		const instance = init(element, undefined, { renderer: 'svg' });
		if (onclick) instance.on('click', (params) => onclick(params as never));
		/**
		 * Resize on the next frame, not inside the callback.
		 *
		 * Resizing synchronously is what produces "ResizeObserver loop completed
		 * with undelivered notifications": the redraw changes layout, the observer
		 * sees the change, and the browser gives up part-way through the cycle. It
		 * has not been seen here — the plot is a fixed-height box — but the guard
		 * is one frame's delay, and it also collapses a drag along the window edge
		 * into one redraw per frame instead of one per event, where each redraw is
		 * a whole SVG tree.
		 */
		let frame = 0;
		const observer = new ResizeObserver(() => {
			if (frame) return;
			frame = requestAnimationFrame(() => {
				frame = 0;
				instance.resize();
			});
		});
		observer.observe(element);
		chart = instance;
		return () => {
			observer.disconnect();
			if (frame) cancelAnimationFrame(frame);
			instance.dispose();
		};
	});

	/**
	 * Every draw, first and subsequent.
	 *
	 * It used to be the second: the mount drew the figure and then this effect
	 * ran and drew it again, because setting `ready` inside the mount was itself
	 * the change that woke it. Every chart on the site was therefore built,
	 * discarded and rebuilt before a reader saw it — and under `notMerge` that is
	 * a whole SVG tree each time, plus a restarted layout on the network graph,
	 * which settles by simulation rather than by measurement.
	 *
	 * `notMerge` so a series removed by a filter actually disappears rather than
	 * lingering underneath the new one.
	 */
	$effect(() => {
		if (!chart) return;
		chart.setOption(framed(option), { notMerge: true });
		ready = true;
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
