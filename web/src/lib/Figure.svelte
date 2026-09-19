<script lang="ts">
	/**
	 * The plate every visualisation on this site sits in.
	 *
	 * A chart without an account of itself is a decoration. Each figure states
	 * four things, and none of them is hidden behind a toggle:
	 *
	 *   question   what it is here to answer            (≤ 20 words)
	 *   reading    how to read the marks on it           (≤ 60 words)
	 *   caveat     the one wrong reading it invites      (≤ 50 words)
	 *   source     the script and the file behind it, so any number can be traced
	 *
	 * The budgets are enforced by `scripts/word-budget.mjs` on `npm run lint`,
	 * after the review of 1 September 2026 counted 5,200 words of apparatus
	 * over twenty figures and found most of it was method repeated, marks
	 * restated or engineering narrated. What a reader might still want — a
	 * withholding rule in full, a second-order caveat — goes in `more`, a
	 * disclosure capped at 150 words; method goes to Methods behind an anchor.
	 *
	 * The plate runs the full width of the page: the evidence gets every column.
	 * The notes sit UNDER it, side by side, the way a programme's plate carries
	 * its caption beneath the picture — not in a margin that took a third of the
	 * width and left blank paper under a short note (the review of 14 September
	 * 2026 measured the figure body at 67% of the page and the heatmap at 59%).
	 * Everything the reader must hold *while looking* is still one glance away:
	 * the reading note is the first thing under the marks.
	 *
	 * No panel, no border, no radius: a plate is opened by a heavy rule and
	 * numbered in document order, and separated from the next by space.
	 */
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';
	import DownloadControls from './Download.svelte';
	import type { DownloadSpec } from './Download.svelte';
	import { figureId, provenance, PROVENANCE_LABELS } from './figures';
	import { resolve } from '$app/paths';

	interface Props {
		title: string;
		/** The anchor; defaults to a slug of the title, which `Contents.svelte` also derives. */
		id?: string;
		question: string;
		/** Script and artefact, e.g. "04_series.py → series/annual.json". */
		source: string;
		reading: Snippet;
		caveat?: Snippet;
		/** Overflow the budget refused: opened on demand, never in the way. */
		more?: Snippet;
		controls?: Snippet;
		/** Shown under the figure in the quiet ink: says the geometry is not the claim. */
		note?: string;
		/**
		 * CSV and image export, offered beside the source rather than over the
		 * figure. A figure with nothing exportable simply omits it — the control
		 * appears only where there is an artefact behind it to hand over.
		 */
		download?: DownloadSpec;
		/** Opt in only where the figure materially benefits from the full viewport. */
		fullscreen?: boolean;
		/** Chart and map wrappers use this to resize after both layout transitions. */
		onfullscreenchange?: (expanded: boolean) => void;
		children: Snippet;
	}

	let {
		title,
		id,
		question,
		source,
		reading,
		caveat,
		more,
		controls,
		note,
		download,
		fullscreen = false,
		onfullscreenchange,
		children
	}: Props = $props();

	let element: HTMLElement;
	const origin = $derived(provenance(source));
	let trigger = $state.raw<HTMLButtonElement>();
	let expanded = $state(false);
	let native = false;
	let oldOverflow = '';

	function afterLayout(open: boolean) {
		requestAnimationFrame(() => requestAnimationFrame(() => onfullscreenchange?.(open)));
	}

	function lockPage() {
		oldOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
	}

	function unlockPage() {
		document.body.style.overflow = oldOverflow;
	}

	function setExpanded(open: boolean, usesNative = false) {
		if (expanded === open) return;
		expanded = open;
		native = open && usesNative;
		if (open) lockPage();
		else unlockPage();
		afterLayout(open);
		if (!open) requestAnimationFrame(() => trigger?.focus());
	}

	async function toggleFullscreen() {
		if (expanded) {
			if (native && document.fullscreenElement) await document.exitFullscreen();
			else setExpanded(false);
			return;
		}
		try {
			if (element.requestFullscreen) {
				await element.requestFullscreen();
				setExpanded(true, true);
				return;
			}
		} catch {
			// Denied requests and iOS Safari use the same fixed fallback.
		}
		setExpanded(true);
	}

	function keepFocus(event: KeyboardEvent) {
		if (!expanded || event.key !== 'Tab') return;
		const focusable = [
			...element.querySelectorAll<HTMLElement>(
				'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
			)
		].filter((item) => item.offsetParent !== null);
		if (!focusable.length) return;
		const first = focusable[0];
		const last = focusable.at(-1)!;
		if (event.shiftKey && document.activeElement === first) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && document.activeElement === last) {
			event.preventDefault();
			first.focus();
		}
	}

	onMount(() => {
		const fullscreenChanged = () => {
			if (native && document.fullscreenElement !== element) setExpanded(false);
		};
		const keyboard = (event: KeyboardEvent) => {
			if (event.key === 'Escape' && expanded && !native) setExpanded(false);
			else keepFocus(event);
		};
		document.addEventListener('fullscreenchange', fullscreenChanged);
		window.addEventListener('keydown', keyboard);
		return () => {
			document.removeEventListener('fullscreenchange', fullscreenChanged);
			window.removeEventListener('keydown', keyboard);
			if (expanded) unlockPage();
		};
	});
</script>

<!-- `tabindex="-1"` for the same reason `#top` in the layout carries it: a
     fragment link moves the viewport, but only a focusable target moves the
     focus with it, and a reader who reaches the last figure from the contents
     must carry on tabbing from that figure rather than from the first one. -->
<figure
	bind:this={element}
	class="figure"
	class:fullscreen-open={expanded}
	id={figureId({ title, id })}
	tabindex="-1"
>
	<figcaption class="head">
		<!-- The plate number is printed from a CSS counter so it always agrees
		     with document order and with the contents band, which counts the
		     same figures. Hidden from assistive technology: the heading is the
		     name, and "Plate 3" read before every title is noise. -->
		<span class="plate-no" aria-hidden="true"></span>
		<div class="title-row">
			<h2><a class="anchor" href="#{figureId({ title, id })}">{title}</a></h2>
			{#if fullscreen}
				<button
					bind:this={trigger}
					type="button"
					class="fullscreen-toggle"
					onclick={toggleFullscreen}
					aria-pressed={expanded}
					aria-label={expanded ? `Exit full screen: ${title}` : `View full screen: ${title}`}
				>
					<svg viewBox="0 0 24 24" aria-hidden="true">
						{#if expanded}
							<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
						{:else}
							<path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" />
						{/if}
					</svg>
					<span>{expanded ? 'Close full screen' : 'Full screen'}</span>
				</button>
			{/if}
		</div>
		<p class="question">{question}</p>
		<a class="provenance" data-provenance={origin} href={`${resolve('/methods')}#provenance`}>
			{PROVENANCE_LABELS[origin]}
		</a>
	</figcaption>

	{#if controls}
		<div class="controls">{@render controls()}</div>
	{/if}

	<div class="body">
		{@render children()}
		{#if note}
			<p class="note-line">{note}</p>
		{/if}
	</div>

	<!-- The notes, under the plate, on the grid: the reading note and the
	     caveat take six columns each, and the overflow disclosure runs under
	     both. The class name `apparatus` is the contract the tests and the
	     reader page share. -->
	<aside class="apparatus grid">
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
		{#if more}
			<details class="more">
				<summary><span class="label">More on this figure</span></summary>
				<div class="prose">{@render more()}</div>
			</details>
		{/if}
	</aside>

	<!-- Provenance and the downloads run the full width under the notes: not a
	     reading note but where the numbers came from and how to take them away. -->
	<footer class="src">
		<span class="label">Source</span>
		<p class="symbol">{source}</p>
		{#if download}
			<DownloadControls spec={download} />
		{/if}
	</footer>
</figure>

<style>
	.figure {
		counter-increment: plate;
		margin: 0 0 var(--sp-9);
		padding-top: var(--sp-3);
		border-top: var(--heavy) solid var(--ink);
	}

	.head {
		margin-bottom: var(--sp-4);
	}

	/* "Plate 3", in the apparatus voice, on its own line above the title: the
	   address a reader keys or cites. */
	.plate-no::before {
		content: 'Plate ' counter(plate);
		display: block;
		font-size: var(--step--1);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		color: var(--ink-3);
		margin-bottom: var(--sp-2);
	}

	.head h2 {
		margin: 0 0 0.15em;
		font-size: var(--step-3);
		max-width: 40rem;
	}

	.title-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--sp-4);
	}

	.fullscreen-toggle {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: var(--sp-2);
		min-height: 2rem;
		padding: 0 var(--sp-3);
		font-size: var(--step--1);
		font-weight: 500;
		line-height: 1;
		color: var(--ink);
		background: var(--paper);
		border: var(--hair) solid var(--ink);
	}

	.fullscreen-toggle:hover {
		background: var(--paper-sunk);
	}

	.fullscreen-toggle svg {
		width: 1rem;
		height: 1rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.75;
		stroke-linecap: square;
	}

	.figure:fullscreen,
	.figure.fullscreen-open {
		box-sizing: border-box;
		width: 100vw;
		height: 100vh;
		margin: 0;
		padding: clamp(1rem, 3vw, 3rem);
		overflow: auto;
		overscroll-behavior: contain;
		background: var(--paper);
		border-top: 0;
	}

	/* Fixed fallback for browsers without element.requestFullscreen, notably
	   iOS Safari. The native selector above and this class share one layout. */
	.figure.fullscreen-open:not(:fullscreen) {
		position: fixed;
		inset: 0;
		z-index: 1000;
	}

	@media (prefers-reduced-motion: no-preference) {
		.figure.fullscreen-open {
			animation: fullscreen-in var(--dur) var(--ease);
		}
	}

	@keyframes fullscreen-in {
		from {
			opacity: 0.7;
			clip-path: inset(2rem);
		}
	}

	/* The title is its own anchor: a heading a reader can copy a link from,
	   without a chain icon the type does not need. */
	.anchor {
		color: inherit;
		text-decoration: none;
	}

	.anchor:hover,
	.anchor:focus-visible {
		text-decoration: underline;
		text-decoration-thickness: 2px;
		text-underline-offset: 0.12em;
	}

	.question {
		margin: 0;
		max-width: var(--measure);
		color: var(--ink-2);
		font-size: var(--step-0);
		line-height: 1.5;
	}

	.provenance {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		margin-block: var(--sp-2) 0;
		font-size: var(--step--1);
		font-weight: 500;
		color: var(--ink);
		text-decoration: none;
	}

	.provenance:hover {
		text-decoration: underline;
	}

	/* The provenance kind is a square of its colour before the words, so the
	   words stay ink and the colour stays a key rather than a warning. */
	.provenance::before {
		content: '';
		width: 0.625rem;
		height: 0.625rem;
		flex: none;
		background: var(--ink);
	}

	.provenance[data-provenance='computed']::before {
		background: var(--state-ok);
	}
	.provenance[data-provenance='mixed']::before {
		background: var(--state-warn);
	}
	.provenance[data-provenance='model']::before {
		background: var(--state-bad);
	}

	/* Centred, not bottom-aligned. The bar mixes a label beside a select, a
	   segmented button group and a mono readout, and they are not the same
	   height; one centre line is the only alignment that survives that. */
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-3) var(--sp-5);
		align-items: center;
		padding: var(--sp-3) 0;
		margin-bottom: var(--sp-4);
		border-top: var(--hair) solid var(--ink);
		border-bottom: var(--hair) solid var(--rule);
	}

	/* A flex item refuses to shrink below the width of its content, and a
	   control here is usually a label wrapped around a select as wide as its
	   longest option. Wrapping to the next line does not help when one item is
	   already wider than the line; without this the bar carries the page
	   sideways.

	   `:global` because the bar's contents are a snippet the calling page
	   declares: they carry that page's scope, not this one's, so a scoped child
	   selector here would match nothing at all. */
	.controls > :global(*) {
		min-width: 0;
		max-width: 100%;
	}

	.body {
		min-width: 0;
		overflow-x: auto;
	}

	/* Running text, so the text face: the typewriter is for citations only. */
	.note-line {
		margin: var(--sp-2) 0 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.apparatus {
		row-gap: var(--sp-4);
		margin-top: var(--sp-5);
		padding-top: var(--sp-3);
		border-top: var(--hair) solid var(--ink);
	}

	.note {
		grid-column: span 12;
	}

	.more {
		grid-column: span 12;
	}

	@media (min-width: 48rem) {
		.note {
			grid-column: span 6;
		}
	}

	@media (min-width: 64rem) {
		.note {
			grid-column: span 5;
		}

		.note + .note {
			grid-column: 7 / span 5;
		}
	}

	.more summary {
		cursor: pointer;
		list-style: none;
		width: fit-content;
	}

	.more summary::-webkit-details-marker {
		display: none;
	}

	.more summary .label {
		display: inline;
		color: var(--blue);
	}

	.more summary:hover .label {
		color: var(--ink);
	}

	.more summary .label::before {
		content: '+ ';
	}

	.more[open] summary .label::before {
		content: '− ';
	}

	.more .prose {
		margin-top: var(--sp-2);
		max-width: var(--measure);
	}

	.label {
		margin-bottom: var(--sp-1);
	}

	/* The reading note is the one the reader needs first. */
	.lead {
		color: var(--ink);
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
		font-size: 0.92em;
	}

	/* A strip under the whole plate: label, artefact path, then the downloads,
	   on one line where there is room for one. */
	.src {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-4);
		margin-top: var(--sp-4);
		padding-top: var(--sp-3);
		border-top: var(--hair) solid var(--rule);
	}

	.src .label {
		margin-bottom: 0;
	}

	.src .symbol {
		margin: 0;
		font-family: var(--mono);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
		overflow-wrap: anywhere;
	}

	@media print {
		.figure {
			border-top-width: 2px;
		}
	}
</style>
