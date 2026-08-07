<script lang="ts">
	/**
	 * The frame every visualisation on this site sits in.
	 *
	 * A chart without an account of itself is a decoration. Each figure therefore
	 * states four things, and none of them is hidden behind a toggle:
	 *
	 *   question   what it is here to answer
	 *   reading    how to read the marks on it
	 *   caveat     what it does not show, or what would be wrong to conclude
	 *   source     the script and the file behind it, so any number can be traced
	 *
	 * `caveat` is optional only in the sense that some figures genuinely have
	 * none. Most do.
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		question: string;
		source: string;
		reading: Snippet;
		caveat?: Snippet;
		controls?: Snippet;
		children: Snippet;
	}

	let { title, question, source, reading, caveat, controls, children }: Props = $props();
</script>

<figure class="figure">
	<figcaption class="head">
		<h3>{title}</h3>
		<p class="question">{question}</p>
	</figcaption>

	{#if controls}
		<div class="controls">{@render controls()}</div>
	{/if}

	<div class="body">{@render children()}</div>

	<div class="notes">
		<div class="note">
			<span class="label">How to read this</span>
			<div class="prose">{@render reading()}</div>
		</div>
		{#if caveat}
			<div class="note quiet">
				<span class="label">What it does not show</span>
				<div class="prose">{@render caveat()}</div>
			</div>
		{/if}
	</div>

	<p class="source"><span>Source</span> <code>{source}</code></p>
</figure>

<style>
	.figure {
		margin: 0 0 3.5rem;
		background: var(--panel);
		border: 1px solid var(--rule);
		border-radius: 6px;
		padding: 1.4rem 1.5rem 1rem;
	}

	.head {
		margin-bottom: 1rem;
	}

	.head h3 {
		margin: 0 0 0.15em;
	}

	.question {
		margin: 0;
		color: var(--ink-soft);
		font-size: 0.95rem;
		max-width: 52rem;
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1.2rem;
		align-items: center;
		padding: 0.7rem 0;
		margin-bottom: 0.6rem;
		border-top: 1px solid var(--rule-soft);
		border-bottom: 1px solid var(--rule-soft);
	}

	.body {
		overflow-x: auto;
	}

	.notes {
		display: grid;
		gap: 0.9rem;
		margin-top: 1.2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--rule-soft);
	}

	@media (min-width: 56rem) {
		.notes {
			grid-template-columns: 1fr 1fr;
			gap: 1.8rem;
		}
	}

	.note {
		border-left: 2px solid var(--accent);
		padding-left: 0.85rem;
	}

	.note.quiet {
		border-left-color: var(--rule);
	}

	.label {
		display: block;
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--ink-faint);
		margin-bottom: 0.25rem;
	}

	.prose {
		font-size: 0.9rem;
		line-height: 1.55;
		color: var(--ink-soft);
	}

	.prose :global(p) {
		margin: 0 0 0.5em;
	}

	.prose :global(p:last-child) {
		margin-bottom: 0;
	}

	.prose :global(strong) {
		color: var(--ink);
	}

	.source {
		margin: 1rem 0 0;
		font-size: 0.75rem;
		color: var(--ink-faint);
	}

	.source span {
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.source code {
		background: none;
		padding: 0;
		font-size: 0.75rem;
	}
</style>
