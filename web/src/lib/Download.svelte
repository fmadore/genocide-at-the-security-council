<script lang="ts">
	/**
	 * Take this figure away: the numbers as CSV, the picture as SVG or PNG.
	 *
	 * A renderer over `export.ts`, which holds every decision about what a file
	 * contains. This decides only when the work happens — on click, never on
	 * render, because building a CSV of the whole artefact for a figure nobody
	 * downloads is work done for no reader.
	 *
	 * Both image formats are offered rather than PNG alone. `Chart.svelte` picks
	 * the SVG renderer on the argument that these figures are the part of the
	 * site most likely to leave it — into a slide, a paper, a printout — and only
	 * SVG survives that at any size. Rasterising on the way out would throw away
	 * the property the renderer was chosen for, so PNG sits beside SVG for the
	 * places that will not take vector art, and both are built from one captioned
	 * document so the two cannot disagree.
	 */
	import Download from '@lucide/svelte/icons/download';
	import Icon from './Icon.svelte';
	import { captionSvg, filename, save, saveCsv, svgToPng, toCsv } from './export';
	import type { ExportRequest } from './export';
	import { palette } from './theme';

	export interface DownloadSpec {
		/** Parts of the filename, slugged by `export.ts`. */
		name: (string | number | null | undefined)[];
		/** Built on click. Must return the artefact's rows, not the drawing's. */
		table?: () => ExportRequest;
		/** The figure's live `<svg>`, for the image formats. Omit for a table. */
		chart?: () => SVGSVGElement | null;
	}

	let { spec }: { spec: DownloadSpec } = $props();

	let busy = $state<string | null>(null);
	let problem = $state<string | null>(null);

	async function run(what: string, work: () => void | Promise<void>) {
		busy = what;
		problem = null;
		try {
			await work();
		} catch (error) {
			// A failed download is silent otherwise: the file simply never appears,
			// and the reader is left unsure whether they missed the save dialog.
			problem = error instanceof Error ? error.message : 'The download failed.';
		} finally {
			busy = null;
		}
	}

	const csv = () =>
		run('csv', () => {
			const request = spec.table?.();
			if (!request) throw new Error('This figure has no table behind it.');
			saveCsv(toCsv(request), filename(spec.name, 'csv'));
		});

	/**
	 * The captioned document both image formats come from.
	 *
	 * Width and height are read off the live element rather than its attributes:
	 * the chart is sized by a ResizeObserver, so the attributes are whatever the
	 * last resize wrote, and a figure exported mid-layout would otherwise carry a
	 * stale box and letterbox itself.
	 */
	function picture() {
		const element = spec.chart?.();
		if (!element) throw new Error('The figure has not finished drawing yet.');
		const box = element.getBoundingClientRect();
		const width = Math.round(box.width) || Number(element.getAttribute('width')) || 900;
		const height = Math.round(box.height) || Number(element.getAttribute('height')) || 400;
		const request = spec.table?.();
		const colours = palette();
		return {
			width,
			height,
			markup: captionSvg({
				svg: new XMLSerializer().serializeToString(element),
				width,
				height,
				title: request?.title ?? 'Figure',
				filters: request?.filters,
				provenance:
					request?.provenance ??
					({ artifact: 'unknown', script: 'unknown', generated: 'unknown' } as never),
				colours: {
					ink: colours.ink,
					faint: colours.inkFaint,
					paper: colours.panel,
					rule: colours.ruleSoft
				}
			})
		};
	}

	const svg = () =>
		run('svg', () => {
			const { markup } = picture();
			save(new Blob([markup], { type: 'image/svg+xml;charset=utf-8' }), filename(spec.name, 'svg'));
		});

	const png = () =>
		run('png', async () => {
			const { markup, width, height } = picture();
			const caption = 120; // room the caption added; over-allocating only pads.
			save(await svgToPng(markup, width, height + caption), filename(spec.name, 'png'));
		});
</script>

<div class="download">
	<span class="label">Take it away</span>
	<div class="row">
		{#if spec.table}
			<button type="button" onclick={csv} disabled={busy !== null}>
				<Icon icon={Download} />
				{busy === 'csv' ? 'Building…' : 'CSV'}
			</button>
		{/if}
		{#if spec.chart}
			<button type="button" onclick={svg} disabled={busy !== null}>
				{busy === 'svg' ? 'Building…' : 'SVG'}
			</button>
			<button type="button" onclick={png} disabled={busy !== null}>
				{busy === 'png' ? 'Building…' : 'PNG'}
			</button>
		{/if}
	</div>
	{#if problem}
		<p class="problem" role="status">{problem}</p>
	{:else}
		<p class="hint">
			The CSV holds every row the artefact has, not only what is drawn, and every file names the
			script and lexicon version behind it.
		</p>
	{/if}
</div>

<style>
	.download {
		margin-top: var(--sp-4);
	}

	.label {
		display: block;
		font-family: var(--sans);
		font-size: var(--step--2);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: var(--sp-2);
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-2);
	}

	button {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
		font-family: var(--sans);
		font-size: var(--step--1);
		padding: var(--sp-1) var(--sp-3);
		background: none;
		border: var(--hair) solid var(--rule-strong);
		border-radius: 0;
		color: var(--blue);
		cursor: pointer;
	}

	button:hover:not(:disabled) {
		border-color: var(--blue-mid);
		color: var(--blue-mid);
	}

	button:disabled {
		color: var(--ink-3);
		cursor: default;
	}

	.hint,
	.problem {
		margin: var(--sp-2) 0 0;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
		line-height: 1.45;
	}

	.problem {
		color: var(--state-bad);
	}
</style>
