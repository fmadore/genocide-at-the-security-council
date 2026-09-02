<script lang="ts">
	/**
	 * The figures on this page, as a list of anchors.
	 *
	 * Declared by the page rather than collected from the figures at run time,
	 * so the list is in the prerendered HTML and a reader with scripts off, or a
	 * crawler, gets it too. The ids come from `figures.ts`, which is also what
	 * `Figure.svelte` derives its own `id` from.
	 */
	import { figureId } from './figures';
	import type { FigureEntry } from './figures';

	let { figures }: { figures: FigureEntry[] } = $props();
</script>

<nav class="contents" aria-label="Figures on this page">
	<span class="label">On this page</span>
	<ol>
		{#each figures as figure (figureId(figure))}
			<li><a href="#{figureId(figure)}">{figure.title}</a></li>
		{/each}
	</ol>
</nav>

<style>
	.contents {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-2) var(--sp-4);
		margin: 0 0 var(--sp-6);
		padding: var(--sp-3) 0;
		border-top: var(--hair) solid var(--rule);
		border-bottom: var(--hair) solid var(--rule);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.label {
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	ol {
		display: flex;
		flex-wrap: wrap;
		gap: var(--sp-1) var(--sp-4);
		margin: 0;
		padding: 0;
		list-style: none;
		counter-reset: figure;
	}

	li {
		counter-increment: figure;
	}

	li::before {
		content: counter(figure) ' ';
		font-family: var(--mono);
		color: var(--ink-3);
	}

	a {
		color: var(--ink-2);
	}
</style>
