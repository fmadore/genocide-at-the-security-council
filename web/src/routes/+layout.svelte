<script lang="ts">
	import '../app.css';
	import serifRoman from '../fonts/SourceSerif4Variable-Roman.woff2?url';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import BackToTop from '$lib/BackToTop.svelte';
	import BasketDrawer from '$lib/BasketDrawer.svelte';
	import ThemeToggle from '$lib/ThemeToggle.svelte';
	import { basket } from '$lib/basket.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	/* The basket lives in the masthead rather than on a route of its own: it is
	   filled from the concordance and the reader and read from anywhere, and a
	   URL for it would be the one URL on this site whose contents depend on
	   which browser opens it. */
	let basketOpen = $state(false);

	/* Read from storage after the first paint, not during it: the server renders
	   an empty basket, and filling it while the markup is being evaluated is both
	   a hydration mismatch and a state mutation Svelte refuses. */
	$effect(() => {
		basket.hydrate();
	});

	const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';

	const sections = [
		{ href: '/', label: 'Overview', blurb: 'The question, and the headline numbers' },
		{
			href: '/chronology',
			label: 'Chronology',
			blurb: 'When the word was said, and when that changed'
		},
		{ href: '/language', label: 'Language', blurb: 'The words it sits next to' },
		{
			href: '/actors',
			label: 'Actors',
			blurb: 'Who said it, as a share of their own speeches'
		},
		{ href: '/concordance', label: 'Concordance', blurb: 'Every occurrence, with its context' },
		{
			href: '/usage',
			label: 'Usage',
			blurb: 'Which genocide each speaker meant, read by a model — experimental'
		},
		{ href: '/methods', label: 'Methods', blurb: 'How every number was made' }
	] as const;

	// Compare against what `resolve` produces rather than re-deriving the base
	// path by hand: the two would drift the moment the site moved to a domain root.
	const here = $derived(page.url.pathname.replace(/\/$/, ''));
	const isCurrent = (href: (typeof sections)[number]['href']) =>
		here === resolve(href).replace(/\/$/, '');
	// The reader is reached from the concordance and has no nav entry of its own.
	const isReader = $derived(here.includes('/reader/'));
</script>

<svelte:head>
	<!-- The text face, preloaded here rather than in `app.html` because Vite
	     fingerprints it and only the module graph knows the emitted name. -->
	<link rel="preload" href={serifRoman} as="font" type="font/woff2" crossorigin="anonymous" />
</svelte:head>

<!-- The first point in the document, and what `BackToTop` links to. It is a
     marker of its own rather than the masthead, because the masthead is sticky:
     it is never out of view, so scrolling it into view moves nothing. Zero
     height and `tabindex="-1"`, so it takes the focus the jump brings without
     occupying space or entering the tab order — the next Tab from here offers
     the skip link, which is the right thing to be offered at the top. -->
<span id="top" tabindex="-1"></span>

<a class="skip" href="#main">Skip to content</a>

<header class="masthead">
	<div class="inner">
		<a class="wordmark" href={resolve('/')}>
			<strong><mark>Genocide</mark> at the Security Council</strong>
			<span class="symbol">1992&ndash;2023</span>
		</a>
		<nav aria-label="Sections">
			<ul>
				{#each sections as section (section.href)}
					<li>
						<a
							href={resolve(section.href)}
							title={section.blurb}
							aria-current={isCurrent(section.href) ? 'page' : undefined}
							class:active={isCurrent(section.href) ||
								(isReader && section.href === '/concordance')}>{section.label}</a
						>
					</li>
				{/each}
				<li class="no-print">
					<button type="button" class="basket" onclick={() => (basketOpen = true)}>
						Basket{#if basket.count}<span class="n">{basket.count}</span>{/if}
					</button>
				</li>
				<li class="no-print"><ThemeToggle /></li>
			</ul>
		</nav>
	</div>
</header>

<BasketDrawer bind:open={basketOpen} onclose={() => (basketOpen = false)} />

<main id="main">
	{@render children()}
	<BackToTop />
</main>

<footer>
	<div class="inner">
		<p>
			Built from <a href="https://doi.org/10.7910/DVN/CKPTRB">The UNSC Meetings and Speeches</a>
			(Sakamoto &amp; Matsuoka, v5.0, CC0). Every figure on this site is produced by a versioned script
			from a single data file; see
			<a href={resolve('/methods')}>Methods</a>.
		</p>
		<p class="quiet">
			The distributed transcripts are in English. The source does not retain a reliable marker of
			the language actually spoken, so delivery language remains unknown rather than inferred.
			Everything here measures the English verbatim record rather than the room it was written from.
		</p>
		<p class="quiet">
			By <a href="https://www.frederickmadore.com/">Frédérick Madore</a> (University of Bayreuth).
			Code
			<a href="{REPO}/blob/main/LICENSE">MIT</a>; the figures and tables on this site
			<a href="{REPO}/blob/main/LICENSE-DATA.md">CC BY 4.0</a>. Speech text quoted from the record
			remains CC0.
		</p>
	</div>
</footer>

<style>
	#top {
		display: block;
		height: 0;
	}

	.skip {
		position: absolute;
		left: -9999px;
	}

	.skip:focus {
		left: var(--sp-4);
		top: var(--sp-4);
		z-index: var(--z-popover);
		background: var(--paper);
		border: var(--hair) solid var(--rule-strong);
		padding: var(--sp-2) var(--sp-3);
	}

	/* A rule and the ground colour, not a panel. The masthead is the top edge of
	   the page, not an object sitting on it. */
	.masthead {
		border-bottom: var(--hair) solid var(--rule-strong);
		background: var(--paper);
		position: sticky;
		top: 0;
		z-index: var(--z-masthead);
	}

	.inner {
		max-width: var(--page);
		margin: 0 auto;
		padding: 0 var(--gutter);
	}

	.masthead .inner {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--sp-2) var(--sp-6);
		padding-top: var(--sp-3);
		padding-bottom: var(--sp-3);
	}

	/* The wordmark is the site's one gesture at its own scale: a marked word in
	   a line of running text. */
	.wordmark {
		text-decoration: none;
		color: inherit;
		display: flex;
		align-items: baseline;
		gap: var(--sp-3);
	}

	.wordmark strong {
		font-family: var(--serif);
		font-size: var(--step-0);
		font-weight: 600;
		letter-spacing: -0.01em;
	}

	.wordmark span {
		color: var(--ink-3);
		font-size: var(--step--2);
	}

	nav ul {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-2) var(--sp-5);
		list-style: none;
		margin: 0;
		padding: 0;
	}

	nav a {
		text-decoration: none;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		padding-bottom: 0.15rem;
	}

	nav a:hover {
		color: var(--ink);
	}

	/* Set as the nav links are, because it belongs to the same row of choices —
	   but a button, because it opens something rather than going somewhere. */
	.basket {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
		background: none;
		border: 0;
		padding: 0 0 0.15rem;
		cursor: pointer;
		display: inline-flex;
		align-items: baseline;
		gap: var(--sp-1);
	}

	.basket:hover {
		color: var(--ink);
	}

	.basket .n {
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink);
		border: var(--hair) solid var(--rule-strong);
		padding: 0 0.3em;
	}

	/* An inset shadow rather than a border: it sits inside the box without
	   adding to the line's height, so nothing moves when it appears. */
	nav a.active {
		color: var(--ink);
		font-weight: 600;
		box-shadow: inset 0 -2px 0 var(--blue-flag);
	}

	main {
		max-width: var(--page);
		margin: 0 auto;
		padding: var(--sp-7) var(--gutter) var(--sp-9);
	}

	footer {
		border-top: var(--hair) solid var(--rule-strong);
		padding: var(--sp-6) 0 var(--sp-7);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.55;
		color: var(--ink-2);
	}

	footer p {
		max-width: 46rem;
	}

	footer .quiet {
		color: var(--ink-3);
	}
</style>
