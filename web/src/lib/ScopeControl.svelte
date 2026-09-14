<script lang="ts">
	/**
	 * The corpus scope, in the masthead, carried in the URL.
	 *
	 * It sits beside its own counts because a control that silently changes a
	 * population is a control that produces mistakes: a reader who moves from
	 * 4,133 speeches to 50,735 should read that in the control rather than infer
	 * it from a chart that grew.
	 *
	 * Radios rather than a select, for the same reason. Three options whose sizes
	 * differ by a factor of twelve are a comparison, and a closed select shows one
	 * of them at a time.
	 *
	 * It appears only on the views that obey it. Offering it on `/usage`, where
	 * nothing reads it, would be a promise the page does not keep.
	 */
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { count } from '$lib/format';
	import { DEFAULT_SCOPE, SCOPE_PARAM, readScope, withScope, type ScopeId } from '$lib/scope';
	import type { ScopeIndex } from '$lib/types';

	let { index }: { index: ScopeIndex } = $props();

	/* `url.searchParams` is unreadable while a page is prerendered, by design:
	   a static file cannot depend on a query string. The answer there is the
	   default, which is the guarantee R9 makes anyway — a URL carrying no scope
	   renders what the site rendered before R9 — and hydration applies the rest. */
	const current = $derived(browser ? readScope(page.url.searchParams) : DEFAULT_SCOPE);
	const chosen = $derived(index.scopes.find((scope) => scope.id === current) ?? index.scopes[0]);

	function choose(id: ScopeId) {
		const search = withScope(page.url.searchParams, id).toString();
		// A push rather than a replace: the scope is analytical state, and Back
		// should return a reader to the population they were reading.
		void goto(`${page.url.pathname}${search ? `?${search}` : ''}`, {
			keepFocus: true,
			noScroll: true
		});
	}
</script>

<!-- A named `section`, so the band between the masthead and the page is a
     landmark rather than content sitting outside every one of them. -->
<section class="band no-print" aria-label="Reading set">
	<div class="inner">
		<fieldset>
			<legend>Reading set</legend>
			<div class="options">
				{#each index.scopes as scope (scope.id)}
					<label class:on={scope.id === current}>
						<input
							type="radio"
							name={SCOPE_PARAM}
							value={scope.id}
							checked={scope.id === current}
							onchange={() => choose(scope.id)}
						/>
						<span class="name">{scope.label}</span>
						<span class="n">{count(scope.speeches)}</span>
					</label>
				{/each}
			</div>
		</fieldset>
		<p class="says">
			{chosen.definition}
			{count(chosen.meetings)} meetings. The set identifies speeches to explore. It does not filter every
			chart; each figure states which speeches its calculations use.
		</p>
	</div>
</section>

<style>
	.band {
		border-bottom: var(--hair) solid var(--rule);
		background: var(--paper);
	}

	.inner {
		max-width: var(--page);
		margin: 0 auto;
		padding: var(--sp-2) var(--gutter);
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-2) var(--sp-5);
	}

	/* The three sets as one segmented control: the legend is its name, each
	   option a cell, the chosen one filled with ink. The radios stay real
	   (keyboard, assistive technology, the form semantics) and are drawn by
	   their labels; the review of 14 September 2026 found the visible radio
	   floating above its label at 390px. */
	fieldset {
		border: 0;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-3);
	}

	legend {
		float: left;
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 600;
		color: var(--ink);
		padding: 0 var(--sp-2) 0 0;
	}

	.options {
		display: flex;
		border: var(--hair) solid var(--ink);
	}

	label {
		position: relative;
		display: inline-flex;
		align-items: baseline;
		gap: var(--sp-2);
		min-height: 2rem;
		padding: 0 var(--sp-3);
		border-left: var(--hair) solid var(--ink);
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 500;
		line-height: 2rem;
		color: var(--ink-2);
		background: var(--paper);
		cursor: pointer;
	}

	label:first-child {
		border-left: 0;
	}

	label:hover {
		background: var(--paper-sunk);
	}

	label.on,
	label.on:hover {
		color: var(--paper);
		background: var(--ink);
	}

	/* The input is the control; the label is its face. */
	label input {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		margin: 0;
		opacity: 0;
		cursor: pointer;
	}

	label:has(input:focus-visible) {
		outline: 2px solid var(--blue-flag);
		outline-offset: 2px;
	}

	.n {
		font-variant-numeric: tabular-nums;
		font-size: var(--step--2);
		font-weight: 400;
	}

	.says {
		margin: 0;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		max-width: var(--measure);
	}
</style>
