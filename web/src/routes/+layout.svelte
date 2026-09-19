<script lang="ts">
	import '../app.css';
	import textFace from '../fonts/HankenGrotesk-Variable.woff2?url';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import BackToTop from '$lib/BackToTop.svelte';
	import BasketDrawer from '$lib/BasketDrawer.svelte';
	import ScopeControl from '$lib/ScopeControl.svelte';
	import ThemeToggle from '$lib/ThemeToggle.svelte';
	import pageProvenance from '$lib/page-provenance.json';
	import { PROVENANCE_LABELS, type ProvenanceKind } from '$lib/figures';
	import { basket } from '$lib/basket.svelte';
	import type { Snippet } from 'svelte';
	import type { LayoutData } from './$types';

	let { children, data }: { children: Snippet; data: LayoutData } = $props();

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
		{ href: '/language', label: 'Words in context', blurb: 'The words it sits next to' },
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
		{
			href: '/semantic',
			label: 'Semantic map',
			blurb: 'Speech similarity in an experimental embedding map'
		},
		{ href: '/methods', label: 'Methods', blurb: 'How every number was made' }
	] as const;

	// Compare against what `resolve` produces rather than re-deriving the base
	// path by hand: the two would drift the moment the site moved to a domain root.
	const here = $derived(page.url.pathname.replace(/\/$/, ''));
	const isCurrent = (href: (typeof sections)[number]['href']) =>
		here === resolve(href).replace(/\/$/, '');
	const originOf = (href: string) => (pageProvenance as Record<string, ProvenanceKind>)[href];
	// The reader is reached from the concordance and has no nav entry of its own.
	const isReader = $derived(here.includes('/reader/'));

	/* The views that read the scope, and therefore the only ones that offer it.
	   R9 puts the control in the layout; a page that ignores it does not get to
	   show it, because a control that changes nothing teaches a reader that the
	   scope changes nothing. */
	const SCOPED = ['/chronology', '/actors', '/concordance'] as const;
	const isScoped = $derived(isReader || SCOPED.some((href) => isCurrent(href)));

	/* The masthead's height, published for whatever else has to stick under it.
	   It is measured rather than declared because the row wraps: seven sections,
	   a basket and a theme toggle are one line at 82rem and four at 375px, and a
	   contents band told the wrong number covers the page or floats over it. */
	let masthead = $state.raw<HTMLElement>();

	$effect(() => {
		if (!masthead) return;
		const observer = new ResizeObserver(([entry]) => {
			document.documentElement.style.setProperty(
				'--masthead-h',
				`${entry.target.getBoundingClientRect().height}px`
			);
		});
		observer.observe(masthead);
		return () => observer.disconnect();
	});

	/* Native fragment scrolling can precede the measured sticky bands and fonts.
	   Align once after layout settles, unless the reader has already intervened. */
	$effect(() => {
		const fragment = page.url.hash;
		void page.url.pathname;
		if (!fragment) return;
		let cancelled = false;
		const cancel = () => {
			cancelled = true;
		};
		const events = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;
		const clean = () => events.forEach((event) => window.removeEventListener(event, cancel));
		events.forEach((event) => window.addEventListener(event, cancel, { passive: true }));
		void document.fonts.ready.then(() =>
			requestAnimationFrame(() =>
				requestAnimationFrame(() => {
					clean();
					if (cancelled) return;
					let id: string;
					try {
						id = decodeURIComponent(fragment.slice(1));
					} catch {
						return;
					}
					document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: 'instant' });
				})
			)
		);
		return () => {
			cancelled = true;
			clean();
		};
	});
</script>

<svelte:head>
	<!-- The text face, preloaded here rather than in `app.html` because Vite
	     fingerprints it and only the module graph knows the emitted name. -->
	<link rel="preload" href={textFace} as="font" type="font/woff2" crossorigin="anonymous" />
</svelte:head>

<!-- The design's direction contract lives in `app.html`, as the first child of
     the body: Svelte strips template comments at compile time, and the
     contract has to survive the production build to be auditable. -->

<!-- The first point in the document, and what `BackToTop` links to. It is a
     marker of its own rather than the masthead, because the masthead is sticky:
     it is never out of view, so scrolling it into view moves nothing. Zero
     height and `tabindex="-1"`, so it takes the focus the jump brings without
     occupying space or entering the tab order — the next Tab from here offers
     the skip link, which is the right thing to be offered at the top. -->
<span id="top" tabindex="-1"></span>

<a class="skip" href="#main">Skip to content</a>

<header class="masthead" bind:this={masthead}>
	<div class="inner">
		<a class="wordmark" href={resolve('/')}>
			<strong><mark>Genocide</mark> at the Security Council</strong>
			<span class="symbol">1946&ndash;2024</span>
		</a>
		<nav aria-label="Sections">
			<ul>
				{#each sections as section (section.href)}
					<li>
						<a
							href={resolve(section.href)}
							title={`${section.blurb}${originOf(section.href) ? ` · ${PROVENANCE_LABELS[originOf(section.href)]}` : ''}`}
							aria-current={isCurrent(section.href) ? 'page' : undefined}
							class:active={isCurrent(section.href) ||
								(isReader && section.href === '/concordance')}
							>{section.label}{#if originOf(section.href)}<small
									class="nav-origin"
									data-provenance={originOf(section.href)}
									aria-hidden="true"
									>{originOf(section.href) === 'model'
										? 'Model'
										: originOf(section.href) === 'mixed'
											? 'Mixed'
											: 'Computed'}</small
								>{/if}</a
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

{#if isScoped}
	<ScopeControl index={data.scopeIndex} />
{/if}

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
			The transcripts are in English, including translations. The source does not reliably identify
			the language spoken. Results describe the English records and should be checked against the
			passages when interpreting a speaker's position.
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
	/* The provenance of a page, under its name: a square of the kind's colour
	   and the word in the quiet ink, so the row reads as a key and not as a
	   row of warnings. */
	.nav-origin {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--step--2);
		font-weight: 400;
		line-height: 1.2;
		color: var(--ink-3);
	}
	.nav-origin::before {
		content: '';
		width: 0.5rem;
		height: 0.5rem;
		flex: none;
		background: var(--ink-3);
	}
	.nav-origin[data-provenance='computed']::before {
		background: var(--state-ok);
	}
	.nav-origin[data-provenance='mixed']::before {
		background: var(--state-warn);
	}
	.nav-origin[data-provenance='model']::before {
		background: var(--state-bad);
	}
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
	   the page, under the heavy rule the body draws, not an object sitting on it. */
	.masthead {
		border-bottom: var(--hair) solid var(--ink);
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
		align-items: center;
		justify-content: space-between;
		gap: var(--sp-2) var(--sp-6);
		/* Never `min-height: var(--masthead-h)` here: that variable is written
		   FROM this element's measured height, and reading it back made the
		   masthead grow 69px every observer tick. */
		padding-top: var(--sp-2);
		padding-bottom: var(--sp-2);
	}

	/* The wordmark is the site's one gesture at its own scale: a marked word in
	   a line of running text. */
	.wordmark {
		text-decoration: none;
		color: inherit;
		display: flex;
		align-items: baseline;
		gap: var(--sp-3);
		padding: var(--sp-1) 0;
	}

	.wordmark strong {
		font-family: var(--sans);
		font-size: var(--step-0);
		font-weight: 700;
		letter-spacing: -0.01em;
	}

	.wordmark span {
		color: var(--ink-3);
		font-size: var(--step--1);
	}

	nav ul {
		display: flex;
		flex-wrap: wrap;
		align-items: stretch;
		gap: 0 var(--sp-5);
		list-style: none;
		margin: 0;
		padding: 0;
	}

	nav li {
		display: flex;
		align-items: center;
	}

	/* Every entry stands on the same 2rem box, badge or no badge: the review of
	   14 September 2026 measured the one unbadged link at 18.6px beside its
	   35px neighbours. */
	nav a {
		display: flex;
		flex-direction: column;
		justify-content: center;
		min-height: 2.5rem;
		text-decoration: none;
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 500;
		color: var(--ink-2);
	}

	nav a:hover {
		color: var(--ink);
	}

	/* Set as the nav links are, because it belongs to the same row of choices —
	   but a button, because it opens something rather than going somewhere. */
	.basket {
		font-family: var(--sans);
		font-size: var(--step--1);
		font-weight: 500;
		color: var(--ink-2);
		background: none;
		border: 0;
		min-height: 2.5rem;
		padding: 0;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: var(--sp-2);
	}

	.basket:hover {
		color: var(--ink);
		background: none;
	}

	.basket .n {
		font-variant-numeric: tabular-nums;
		font-size: var(--step--2);
		line-height: 1;
		color: var(--paper);
		background: var(--ink);
		padding: 0.2em 0.4em;
	}

	/* The current section carries the heavy rule, in ink: the same rule that
	   opens the page and each plate. An inset shadow rather than a border, so
	   nothing moves when it appears. */
	nav a.active {
		color: var(--ink);
		font-weight: 700;
		box-shadow: inset 0 calc(-1 * var(--heavy)) 0 var(--ink);
	}

	/* The rule is a shadow, and a forced-colour mode does not paint shadows: the
	   section a reader is on would lose its only mark. An underline says it
	   instead, thick and set low, and moves nothing — which is why the rule was
	   a shadow in the first place. */
	@media (forced-colors: active) {
		nav a.active {
			text-decoration: underline;
			text-decoration-thickness: var(--heavy);
			text-underline-offset: 0.5em;
		}
	}

	main {
		max-width: var(--page);
		margin: 0 auto;
		padding: var(--sp-5) var(--gutter) var(--sp-9);
	}

	footer {
		border-top: var(--heavy) solid var(--ink);
		padding: var(--sp-6) 0 var(--sp-8);
		font-family: var(--sans);
		font-size: var(--step--1);
		line-height: 1.5;
		color: var(--ink-2);
	}

	footer p {
		max-width: var(--measure);
	}

	footer .quiet {
		color: var(--ink-3);
	}
</style>
