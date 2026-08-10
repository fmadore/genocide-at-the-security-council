<script lang="ts">
	/**
	 * Back to the top of a long page.
	 *
	 * A renderer over `scroll.ts`, which holds every decision about when this is
	 * offered at all. This decides only how it looks and what a click does.
	 *
	 * It is a link to `#top` rather than a button. That is not a stylistic
	 * preference: an anchor moves keyboard focus as well as the viewport, so a
	 * reader who arrives at the top by this control carries on tabbing from the
	 * top rather than from wherever the bottom of the page left them. It is the
	 * same mechanism as the skip link, pointed the other way.
	 *
	 * `#top` is a zero-height marker in `+layout.svelte` and deliberately not the
	 * masthead, which is `position: sticky` and therefore never out of view — a
	 * browser asked to scroll it into view correctly does nothing at all.
	 *
	 * The click is not intercepted at all. An earlier version cancelled it to
	 * animate the scroll, and that is a worse control than it sounds: cancelling
	 * the default makes the platform's jump this component's responsibility, so
	 * anywhere `scrollTo` declines to animate — it is a no-op without a
	 * compositor — the reader clicks Top and stays where they are. Nothing here
	 * runs on click, so nothing on click can fail.
	 */
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import { page } from '$app/state';
	import Icon from './Icon.svelte';
	import { offersTop } from './scroll';

	let showing = $state(false);

	function measure() {
		showing = offersTop(
			{
				scrollY: window.scrollY,
				viewportHeight: window.innerHeight,
				documentHeight: document.documentElement.scrollHeight
			},
			showing
		);
	}

	$effect(() => {
		// Re-read on navigation as well as on scroll: SvelteKit returns to the top
		// of a new page, and a control left showing there would point at nothing.
		void page.url.pathname;
		measure();
		window.addEventListener('scroll', measure, { passive: true });
		window.addEventListener('resize', measure);
		return () => {
			window.removeEventListener('scroll', measure);
			window.removeEventListener('resize', measure);
		};
	});
</script>

<!-- `inert` rather than a `visibility` transition or a conditional block. The
     control is always in the DOM so it can fade, and `inert` is what states, in
     one attribute the browser enforces, that a faded-out control is not
     clickable, not focusable and not readable — none of which may depend on a
     transition having finished. -->
<a class="to-top no-print" class:on={showing} href="#top" inert={!showing}>
	<Icon icon={ArrowUp} />
	Top
</a>

<style>
	.to-top {
		position: fixed;
		right: var(--gutter);
		bottom: var(--sp-5);
		z-index: var(--z-masthead);

		display: inline-flex;
		align-items: center;
		gap: 0.35em;
		padding: 0.25rem 0.6rem;

		/* The ground colour and a hairline, like the masthead: the control is an
		   edge of the page, not a panel floating over it. No radius, no shadow. */
		background: var(--paper);
		border: var(--hair) solid var(--rule-strong);
		text-decoration: none;

		font-family: var(--mono);
		font-size: var(--step--2);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--blue);

		/* The fade is the only thing CSS is trusted with here; `inert` on the
		   element carries whether the control exists as far as clicks, focus and
		   assistive technology are concerned. */
		opacity: 0;
		transition: opacity var(--dur) var(--ease);
	}

	.to-top.on {
		opacity: 1;
	}

	.to-top:hover {
		border-color: var(--blue-mid);
		color: var(--blue-mid);
	}
</style>
