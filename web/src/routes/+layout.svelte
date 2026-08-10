<script lang="ts">
	import '../app.css';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const REPO = 'https://github.com/fmadore/un-security-council-debates';

	const sections = [
		{ href: '/', label: 'Overview', blurb: 'The question in fifteen seconds' },
		{
			href: '/chronology',
			label: 'Chronology',
			blurb: 'When the word was said, and when that changed'
		},
		{ href: '/language', label: 'Language', blurb: 'What it travels with' },
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

<a class="skip" href="#main">Skip to content</a>

<header class="masthead">
	<div class="inner">
		<a class="wordmark" href={resolve('/')}>
			<strong>Genocide at the Security Council</strong>
			<span>UN Security Council debates, 1992&ndash;2023</span>
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
			</ul>
		</nav>
	</div>
</header>

<main id="main">
	{@render children()}
</main>

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
	.skip {
		position: absolute;
		left: -9999px;
	}

	.skip:focus {
		left: 1rem;
		top: 1rem;
		z-index: 10;
		background: var(--panel);
		padding: 0.5rem 0.9rem;
		border: 1px solid var(--rule);
		border-radius: 4px;
	}

	.masthead {
		border-bottom: 1px solid var(--rule);
		background: var(--panel);
		position: sticky;
		top: 0;
		z-index: 5;
	}

	.inner {
		max-width: var(--wide);
		margin: 0 auto;
		padding: 0 1.5rem;
	}

	.masthead .inner {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem 2rem;
		padding-top: 0.7rem;
		padding-bottom: 0.7rem;
	}

	.wordmark {
		text-decoration: none;
		color: inherit;
		display: flex;
		flex-direction: column;
		line-height: 1.25;
	}

	.wordmark strong {
		font-family: var(--serif);
		font-size: 1.05rem;
		font-weight: 600;
	}

	.wordmark span {
		font-size: 0.75rem;
		color: var(--ink-faint);
	}

	nav ul {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 1.3rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	nav a {
		text-decoration: none;
		color: var(--ink-soft);
		font-size: 0.9rem;
		padding: 0.2rem 0;
		border-bottom: 2px solid transparent;
	}

	nav a:hover {
		color: var(--ink);
	}

	nav a.active {
		color: var(--ink);
		border-bottom-color: var(--accent);
	}

	main {
		max-width: var(--wide);
		margin: 0 auto;
		padding: 2.5rem 1.5rem 4rem;
	}

	footer {
		border-top: 1px solid var(--rule);
		padding: 2rem 0 3rem;
		font-size: 0.83rem;
		color: var(--ink-soft);
	}

	footer p {
		max-width: 46rem;
	}

	footer .quiet {
		color: var(--ink-faint);
	}
</style>
