<script lang="ts">
	/**
	 * The figures on this page, as a band of anchors that stays put.
	 *
	 * Declared by the page rather than collected from the figures at run time,
	 * so the list is in the prerendered HTML and a reader with scripts off, or a
	 * crawler, gets it too. The ids come from `figures.ts`, which is also what
	 * `Figure.svelte` derives its own `id` from.
	 *
	 * R14: it used to scroll away with everything else, which helped the reader
	 * who had not started and nobody else. It now sticks under the masthead and
	 * marks where the reader is, so the last figure of a view 2,000 lines long is
	 * one key away from the first. The mark is `aria-current="location"` — the
	 * token for a place within a set of places — set in weight and in a rule as
	 * well as in colour, because a reader who cannot see the colour is exactly
	 * the reader this control was added for.
	 *
	 * One row on every viewport, scrolling sideways where it does not fit rather
	 * than becoming a second thing on a narrow screen. A sidebar has no room at
	 * 375px and a disclosure would hide the position it exists to show; a running
	 * head is what a long printed work uses, and it costs one line of height.
	 */
	import { page } from '$app/state';
	import { figureId } from './figures';
	import type { FigureEntry } from './figures';
	import { currentFigure } from './contents';

	let { figures }: { figures: FigureEntry[] } = $props();

	let band = $state.raw<HTMLElement>();
	let strip = $state.raw<HTMLElement>();
	let current = $state<string | null>(null);

	const ids = $derived(figures.map(figureId));

	/**
	 * Where the marked entry has to be, and the band's own height, both read from
	 * the layout rather than assumed.
	 *
	 * The reading line is `scroll-padding-top` — by definition the place a jump
	 * to an anchor parks a figure, and therefore the only line on which the mark
	 * and the jump can agree. The band's own bottom edge stands in for it before
	 * the first measurement has told the stylesheet how tall the band is.
	 */
	function measure() {
		if (!band) return;
		const padding = Number.parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop);
		const tops = ids
			.map((id) => ({ id, element: document.getElementById(id) }))
			.filter((entry) => entry.element)
			.map((entry) => ({
				id: entry.id,
				top: entry.element!.getBoundingClientRect().top + window.scrollY
			}));
		current = currentFigure(tops, {
			scrollY: window.scrollY,
			viewportHeight: window.innerHeight,
			documentHeight: document.documentElement.scrollHeight,
			obstructed: Number.isFinite(padding) ? padding : band.getBoundingClientRect().bottom
		});
		// What an anchor jump has to clear, published for `scroll-padding-top`:
		// two sticky bands, and only this one knows how tall the second is.
		document.documentElement.style.setProperty('--contents-h', `${band.offsetHeight}px`);
	}

	/**
	 * Keep the marked entry in view along the band's own axis, and only that
	 * axis. `scrollIntoView` would be shorter and would also be entitled to
	 * scroll the page, which is the one thing a reader who is scrolling must not
	 * have taken away from them.
	 */
	function follow() {
		if (!strip || !current) return;
		const link = strip.querySelector<HTMLElement>(`[data-figure="${CSS.escape(current)}"]`);
		if (!link) return;
		// Measured against the strip's own box rather than through `offsetLeft`,
		// whose origin is the sticky `nav` — a positioned ancestor — and therefore
		// counts the band's padding and its label as part of the entry's position.
		// A little slack either side, so a marked entry flush against an edge does
		// not read as the end of the list.
		const peek = 16;
		const item = (link.parentElement ?? link).getBoundingClientRect();
		const box = strip.getBoundingClientRect();
		const before = item.left - box.left;
		const after = item.right - box.right;
		if (before >= 0 && after <= 0) return;
		const wanted = strip.scrollLeft + (before < 0 ? before - peek : after + peek);
		strip.scrollTo({
			// Clamped here rather than left to the browser: a smooth scroll asked
			// for a position past the end settles short of it, which leaves the
			// last entry — the one a reader is most often jumping to — half drawn.
			left: Math.max(0, Math.min(wanted, strip.scrollWidth - strip.clientWidth)),
			behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
		});
	}

	$effect(() => {
		// Re-read on navigation as well: SvelteKit returns to the top of a new
		// page, and a mark left behind would point into the page before it.
		void page.url.pathname;
		let frame = 0;
		const update = () => {
			if (frame) return;
			// One measurement a frame. A scroll event fires far more often than
			// that, and each one reads the box of every figure on the page.
			frame = requestAnimationFrame(() => {
				frame = 0;
				measure();
			});
		};
		// The first one now rather than next frame: a page restored part-way down,
		// or opened in a tab that is not painting, would otherwise mark nothing.
		measure();
		window.addEventListener('scroll', update, { passive: true });
		window.addEventListener('resize', update);
		return () => {
			window.removeEventListener('scroll', update);
			window.removeEventListener('resize', update);
			if (frame) cancelAnimationFrame(frame);
			document.documentElement.style.removeProperty('--contents-h');
		};
	});

	/* After the mark has been drawn, not while it is being worked out: the marked
	   entry is set in a heavier weight and is therefore wider than it was a moment
	   ago, and a strip measured before that reflow scrolls a few pixels short. */
	$effect(() => {
		void current;
		follow();
	});
</script>

<nav class="contents" aria-label="Figures on this page" bind:this={band}>
	<span class="label">On this page</span>
	<ol bind:this={strip}>
		{#each figures as figure (figureId(figure))}
			<li>
				<a
					href="#{figureId(figure)}"
					data-figure={figureId(figure)}
					aria-current={figureId(figure) === current ? 'location' : undefined}>{figure.title}</a
				>
			</li>
		{/each}
	</ol>
</nav>

<style>
	/* The band spans the gutter as well as the column, so the page passes under
	   it rather than beside it. */
	.contents {
		position: sticky;
		top: var(--masthead-h);
		z-index: var(--z-contents);
		display: flex;
		align-items: baseline;
		gap: var(--sp-2) var(--sp-4);
		margin: 0 calc(-1 * var(--gutter)) var(--sp-6);
		padding: var(--sp-2) var(--gutter);
		background: var(--paper);
		border-top: var(--hair) solid var(--rule);
		border-bottom: var(--hair) solid var(--rule);
		font-family: var(--sans);
		font-size: var(--step--1);
	}

	.label {
		flex: none;
		font-size: var(--step--2);
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	/* On a narrow screen the label took two fifths of the line and said what the
	   `nav`'s own accessible name already says. The entries get the width. */
	@media (max-width: 48rem) {
		.label {
			display: none;
		}
	}

	ol {
		display: flex;
		flex-wrap: nowrap;
		gap: var(--sp-4);
		min-width: 0;
		margin: 0;
		padding: 0;
		overflow-x: auto;
		scrollbar-width: thin;
		list-style: none;
		counter-reset: figure;
	}

	li {
		flex: none;
		counter-increment: figure;
		white-space: nowrap;
	}

	li::before {
		content: counter(figure) ' ';
		font-family: var(--mono);
		color: var(--ink-3);
	}

	a {
		color: var(--ink-2);
		text-decoration: none;
		padding-bottom: 0.15rem;
	}

	a:hover {
		color: var(--ink);
		text-decoration: underline;
	}

	/* Weight and a rule, not colour: the same idiom the masthead uses for the
	   section a reader is on. An inset shadow adds nothing to the line's height,
	   so the band does not change size as the mark moves. */
	a[aria-current='location'] {
		color: var(--ink);
		font-weight: 600;
		box-shadow: inset 0 -2px 0 var(--blue-flag);
	}

	@media print {
		.contents {
			position: static;
			margin-inline: 0;
			padding-inline: 0;
		}

		ol {
			flex-wrap: wrap;
			overflow-x: visible;
		}
	}
</style>
