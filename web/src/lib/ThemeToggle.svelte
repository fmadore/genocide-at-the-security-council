<script lang="ts">
	/**
	 * The one control that changes what the whole page looks like.
	 *
	 * It writes `data-theme` on the document element and remembers the choice in
	 * `localStorage`, which is exactly the pair `app.html`'s boot script reads
	 * before first paint — so a reload keeps the choice without a flash of the
	 * other theme.
	 *
	 * Nothing else has to be told. `app.css` hangs the dark tokens off the same
	 * attribute, and `colourScheme` in `$lib/theme` observes it, so the ECharts
	 * figures redraw themselves.
	 *
	 * The button names the theme it will switch *to*, which is also why the
	 * accessible name contains the visible word rather than replacing it.
	 */
	import Moon from '@lucide/svelte/icons/moon';
	import Sun from '@lucide/svelte/icons/sun';
	import Icon from '$lib/Icon.svelte';
	import { colourScheme } from '$lib/theme';

	const next = $derived($colourScheme === 'dark' ? 'light' : 'dark');

	function flip() {
		document.documentElement.dataset.theme = next;
		try {
			localStorage.setItem('theme', next);
		} catch {
			// Private mode: the theme still applies, it just will not survive a reload.
		}
	}
</script>

<button type="button" class="toggle" onclick={flip} aria-label="Switch to {next} theme">
	<Icon icon={next === 'dark' ? Moon : Sun} />
	{next}
</button>

<style>
	/* The same face as the Basket button it stands beside — one grotesk, sentence
	   case, no ground of its own — inside the hairline every chip on the site
	   carries. `capitalize` rather than an edited string: the visible word is the
	   theme's own name and belongs to the component's contract, not to its
	   styling. */
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
		min-height: 2rem;
		padding: 0 var(--sp-3);
		border: var(--hair) solid var(--ink);
		background: none;
		color: var(--ink-2);
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 500;
		text-transform: capitalize;
		/* Both words are four or five characters; reserving the wider one stops
		   the nav shifting under the pointer as the label changes. */
		min-width: 5.4rem;
		justify-content: center;
	}

	.toggle:hover {
		background: var(--paper-sunk);
		color: var(--ink);
	}
</style>
