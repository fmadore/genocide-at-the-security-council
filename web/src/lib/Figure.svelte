<script lang="ts">
	/**
	 * The frame every visualisation on this site sits in.
	 *
	 * A chart without an account of itself is a decoration. Each figure states
	 * four things, and none of them is hidden behind a toggle:
	 *
	 *   question   what it is here to answer
	 *   reading    how to read the marks on it
	 *   caveat     what it does not show, or what would be wrong to conclude
	 *   source     the script and the file behind it, so any number can be traced
	 *
	 * The apparatus is set in the MARGIN, beside the evidence, the way a critical
	 * edition sets its notes — not queued underneath where it reads as boilerplate.
	 * Below 62rem the margin folds under the figure and keeps its rule.
	 *
	 * No panel, no border, no radius: a figure is separated from the page by a
	 * rule and by space, like everything else here.
	 */
	import type { Snippet } from 'svelte';
	import DownloadControls from './Download.svelte';
	import type { DownloadSpec } from './Download.svelte';

	interface Props {
		title: string;
		question: string;
		/** Script and artefact, e.g. "04_series.py → series/annual.json". */
		source: string;
		reading: Snippet;
		caveat?: Snippet;
		controls?: Snippet;
		/** Shown under the figure in mono: says the geometry is not the claim. */
		note?: string;
		/**
		 * CSV and image export, offered beside the source rather than over the
		 * figure. A figure with nothing exportable simply omits it — the control
		 * appears only where there is an artefact behind it to hand over.
		 */
		download?: DownloadSpec;
		children: Snippet;
	}

	let { title, question, source, reading, caveat, controls, note, download, children }: Props =
		$props();
</script>

<figure class="figure">
	<figcaption class="head">
		<h3>{title}</h3>
		<p class="question">{question}</p>
	</figcaption>

	{#if controls}
		<div class="controls">{@render controls()}</div>
	{/if}

	<div class="split">
		<div class="body">
			{@render children()}
			{#if note}
				<p class="note-line">{note}</p>
			{/if}
		</div>

		<aside class="apparatus">
			<div class="note">
				<span class="label lead">How to read this</span>
				<div class="prose">{@render reading()}</div>
			</div>
			{#if caveat}
				<div class="note">
					<span class="label">What it does not show</span>
					<div class="prose">{@render caveat()}</div>
				</div>
			{/if}
			<div class="note src">
				<span class="label">Source</span>
				<p class="symbol">{source}</p>
				{#if download}
					<DownloadControls spec={download} />
				{/if}
			</div>
		</aside>
	</div>
</figure>

<style>
	.figure {
		margin: 0 0 var(--sp-8);
		padding-top: var(--sp-5);
		border-top: var(--hair) solid var(--rule-strong);
	}

	.head {
		margin-bottom: var(--sp-4);
	}

	.head h3 {
		margin: 0 0 0.1em;
		font-size: var(--step-2);
	}

	.question {
		margin: 0;
		max-width: var(--measure);
		color: var(--ink-2);
		font-size: var(--step-0);
		line-height: 1.5;
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-3) var(--sp-5);
		align-items: end;
		padding: var(--sp-3) 0;
		margin-bottom: var(--sp-4);
		border-top: var(--hair) solid var(--rule);
		border-bottom: var(--hair) solid var(--rule);
	}

	.split {
		display: grid;
		gap: var(--sp-5);
	}

	@media (min-width: 62rem) {
		.split {
			grid-template-columns: minmax(0, 1fr) var(--measure-note);
			gap: var(--sp-6);
			align-items: start;
		}
	}

	.body {
		min-width: 0;
		overflow-x: auto;
	}

	.note-line {
		margin: var(--sp-2) 0 0;
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.apparatus {
		display: grid;
		gap: var(--sp-4);
		border-left: var(--hair) solid var(--rule-strong);
		padding-left: var(--sp-4);
	}

	@media (max-width: 61.999rem) {
		.apparatus {
			grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
		}
	}

	.label {
		display: block;
		font-family: var(--sans);
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: var(--sp-1);
	}

	/* The reading note is the one the reader needs first. */
	.lead {
		color: var(--blue);
	}

	.prose {
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	.prose :global(p) {
		margin: 0 0 0.5em;
	}

	.prose :global(p:last-child) {
		margin-bottom: 0;
	}

	.prose :global(strong) {
		color: var(--ink);
		font-weight: 600;
	}

	.prose :global(code) {
		font-family: var(--mono);
		font-size: 0.9em;
	}

	.src {
		border-top: var(--hair) solid var(--rule);
		padding-top: var(--sp-3);
	}

	.src .symbol {
		margin: 0;
		font-family: var(--mono);
		font-size: var(--step--2);
		line-height: 1.5;
		color: var(--ink-2);
		overflow-wrap: anywhere;
	}
</style>
