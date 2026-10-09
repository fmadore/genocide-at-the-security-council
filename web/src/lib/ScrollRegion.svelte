<script lang="ts">
	/**
	 * A box that scrolls on its own, for a table wider or taller than its column.
	 *
	 * A scrolling box with nothing focusable inside cannot be scrolled from the
	 * keyboard, so the box itself takes a tab stop; and a focusable element a
	 * screen reader lands on has to say what it is, so it is a named region.
	 * `label` is that name.
	 *
	 * `tall` caps the height too, for the long tables of the usage page, which
	 * would otherwise run on for screens beneath the figure they belong to.
	 */
	import type { Snippet } from 'svelte';

	let {
		label,
		tall = false,
		children
	}: { label: string; tall?: boolean; children: Snippet } = $props();
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex (A keyboard-focusable scroll region is intentional.) -->
<div class={tall ? 'scroll' : 'table-scroll'} role="region" aria-label={label} tabindex="0">
	{@render children()}
</div>

<style>
	.table-scroll {
		max-width: 100%;
		overflow-x: auto;
	}

	.scroll {
		overflow-x: auto;
		max-height: 32rem;
		overflow-y: auto;
	}
</style>
