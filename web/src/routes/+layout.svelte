<script lang="ts">
	import '../app.css';
	import serifRoman from '../fonts/SourceSerif4Variable-Roman.woff2?url';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import BackToTop from '$lib/BackToTop.svelte';
	import ThemeToggle from '$lib/ThemeToggle.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';

	const sections = [
		{ href: '/', label: 'Overview', blurb: 'The question in fifteen seconds' },
		{
			href: '/chronology',
			label: 'Chronology',
			blurb: 'When the word was said, and when that changed'
		},
		{ href: '/language', label: 'Language', blurb: 'What it travels with' },
		{ href: '/actors', label: 'Actors', blurb: 'Who said it, against their own denominator' },
		{ href: '/concordance', label: 'Concordance', blurb: 'Every occurrence, in context' },
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
				<li class="no-print"><ThemeToggle /></li>
			</ul>
		</nav>
	</div>
</header>

<main id="main">
	{@render children()}
</main>

<BackToTop />

<footer>
	<div class="inner">
		<p>
			Built from the <a href="https://doi.org/10.7910/DVN/KGVSYH">UN Security Council Debates</a>
			corpus (Schoenfeld, Eckhard, Patz, van Meegdenburg &amp; Pires, v6.1, CC0). Every figure on this
			site is produced by a versioned script from a single parquet file; see
			<a href={resolve('/methods')}>Methods</a>.
		</p>
		<p class="quiet">
			The corpus is English-only by construction. At least 40.2% of speeches are explicit
			translations; missing in-person markers are classified as inferred English under the record
			convention, while VTC delivery language remains unknown. Nothing here measures what was said
			in the room &mdash; it measures what the English verbatim record says was said.
		</p>
		<p class="quiet">
			By <a href="https://orcid.org/0000-0003-0959-2092">Frédérick Madore</a> (University of
			Bayreuth). Code
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
