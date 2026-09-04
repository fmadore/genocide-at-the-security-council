<!--
	The basket, as a dialog rather than a page.

	It is not a route on purpose. Every URL on this site determines what a
	reader sees, which is what makes one citable and worth sending to a
	colleague; a basket URL would be the single exception, naming a page whose
	contents live in one browser and are invisible to everyone else who opens
	the link. The reader route already sets the precedent for an interactive
	surface that is reached rather than listed.

	Everything drawn here comes from the snapshot stored with each item, so the
	dialog renders with no fetches at all — which is what makes it work offline,
	where `static/data/` is deliberately outside the service worker. The one
	network read is the KWIC index, used only to say whether an item predates
	the lexicon the site now serves, and its absence downgrades that to
	"version unknown" rather than to an error.
-->
<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Trash from '@lucide/svelte/icons/trash-2';
	import X from '@lucide/svelte/icons/x';
	import {
		basketCsv,
		basketFilename,
		basketJson,
		basketMarkdown,
		currencyOf,
		MAX_NOTE
	} from './basket';
	import type { BasketItem } from './basket';
	import { basket } from './basket.svelte';
	import { resolve } from '$app/paths';
	import { kwicIndex, meetingOf, speechOf } from './data';
	import { save, saveCsv } from './export';
	import { count, shortCountry } from './format';
	import Icon from './Icon.svelte';

	interface Props {
		open: boolean;
		onclose: () => void;
	}

	let { open = $bindable(), onclose }: Props = $props();

	let dialog = $state<HTMLDialogElement | null>(null);
	let lexicon = $state<number | null>(null);
	let confirming = $state(false);

	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) dialog.showModal();
		if (!open && dialog.open) dialog.close();
	});

	/* Read once, when the dialog is first opened, and never at mount: the layout
	   renders this component on every page, and a fetch at mount would make the
	   whole site depend on a file the service worker does not hold. */
	$effect(() => {
		if (!open || lexicon !== null) return;
		kwicIndex()
			.then((index) => {
				const version = index.meta.lexicon_version;
				lexicon = Number.isFinite(version) ? Number(version) : null;
			})
			.catch(() => {
				// Offline or unavailable. `currencyOf` reports "unknown", which is
				// the honest answer and not a failure worth a banner.
			});
	});

	const items = $derived(basket.items);

	const who = (item: BasketItem) => {
		const shot = item.snapshot;
		const speaker = 'speaker' in shot ? shot.speaker : undefined;
		return speaker ? `${speaker} (${shortCountry(shot.country)})` : shortCountry(shot.country);
	};

	/**
	 * Where an item points: the reader, at the exact occurrence.
	 *
	 * This is the link U3 built the stable occurrence IDs for — it opens the
	 * verbatim record scrolled to the sentence and marks it. A concordance
	 * search would only be a way of looking for it again. The origin comes from
	 * the window so an export made against a local copy does not hand out links
	 * to localhost from a machine that was reading the published site.
	 */
	function permalink(item: BasketItem): string {
		const origin = typeof window === 'undefined' ? '' : window.location.origin;
		const path = resolve('/reader/[meeting]', { meeting: meetingOf(item.id) });
		const params =
			item.kind === 'occurrence'
				? new URLSearchParams({
						term: item.term,
						speech: speechOf(item.id),
						occurrence: item.id
					})
				: new URLSearchParams({ speech: item.id });
		return `${origin}${path}?${params}`;
	}

	const request = () => ({
		basket: basket.basket,
		exported: new Date().toISOString(),
		currentLexicon: lexicon,
		permalink
	});

	function exportCsv() {
		const built = request();
		saveCsv(basketCsv(built), basketFilename(built.exported, 'csv'));
	}

	function exportJson() {
		const built = request();
		save(
			new Blob([basketJson(built)], { type: 'application/json;charset=utf-8' }),
			basketFilename(built.exported, 'json')
		);
	}

	function exportMarkdown() {
		const built = request();
		save(
			new Blob([basketMarkdown(built)], { type: 'text/markdown;charset=utf-8' }),
			basketFilename(built.exported, 'md')
		);
	}

	function close() {
		confirming = false;
		basket.settle();
		open = false;
		onclose();
	}
</script>

<dialog bind:this={dialog} onclose={close} aria-labelledby="basket-title">
	<div class="head">
		<h2 id="basket-title">Basket <span class="n">{count(basket.count)}</span></h2>
		<button type="button" class="ghost" onclick={close} aria-label="Close the basket">
			<Icon icon={X} />
		</button>
	</div>

	<p class="hint">
		Kept in this browser only — not an account, not synced, and not visible to anyone else. Export
		it to take it anywhere, including to another machine of your own.
	</p>

	{#if basket.problem}
		<p class="problem" role="alert">
			{basket.problem}
			{#if basket.blocked}
				<button type="button" class="ghost" onclick={() => basket.startOver()}>
					Start a new basket
				</button>
			{/if}
		</p>
	{/if}

	{#if items.length === 0}
		<p class="empty">
			Nothing here yet. Add an occurrence from the concordance or the reader, and it will keep the
			sentence, the speaker and the record it came from.
		</p>
	{:else}
		<ul>
			{#each items as item (item.id)}
				{@const currency = currencyOf(item, lexicon)}
				<li>
					<div class="meta">
						<span class="symbol">{item.snapshot.spv}</span>
						<span class="dot">·</span>
						<span>{who(item)}</span>
						<span class="dot">·</span>
						<span>{item.snapshot.date}</span>
						{#if currency !== 'current'}
							<span
								class="badge"
								title={currency === 'stale'
									? `Recorded under lexicon version ${item.lexiconVersion}; the site now serves version ${lexicon}. The text below is as recorded.`
									: 'The lexicon version behind this item is not known. The text below is as recorded.'}
							>
								{currency === 'stale' ? `lexicon v${item.lexiconVersion}` : 'version unknown'}
							</span>
						{/if}
					</div>

					{#if item.kind === 'occurrence'}
						<blockquote>{item.snapshot.sentence}</blockquote>
					{:else}
						<p class="whole">
							The whole speech{item.snapshot.agenda ? `, on ${item.snapshot.agenda}` : ''}.
						</p>
					{/if}

					<label class="note">
						<span class="sr-only">Note on {who(item)}, {item.snapshot.spv}</span>
						<textarea
							rows="2"
							maxlength={MAX_NOTE}
							placeholder="A note for yourself…"
							value={item.note}
							onchange={(event) => basket.note(item.id, event.currentTarget.value)}
						></textarea>
					</label>

					<div class="actions">
						<a href={permalink(item)}>
							{item.kind === 'occurrence' ? 'Open the occurrence' : 'Read the speech'}<Icon
								icon={ExternalLink}
							/>
						</a>
						<button
							type="button"
							class="ghost"
							onclick={() => basket.remove(item.id)}
							aria-label="Remove {who(item)}, {item.snapshot.spv} from the basket"
						>
							<Icon icon={Trash} />Remove
						</button>
					</div>
				</li>
			{/each}
		</ul>

		<div class="foot">
			<div class="exports">
				<span class="label">Export</span>
				<button type="button" class="ghost" onclick={exportCsv}>
					<Icon icon={Download} />CSV
				</button>
				<button type="button" class="ghost" onclick={exportJson}>
					<Icon icon={Download} />JSON
				</button>
				<button type="button" class="ghost" onclick={exportMarkdown}>
					<Icon icon={Download} />Markdown
				</button>
			</div>
			{#if confirming}
				<p class="confirm" role="alert">
					Empty the basket? The notes go with it, and nothing here is recoverable.
					<button
						type="button"
						class="ghost danger"
						onclick={() => {
							basket.clear();
							confirming = false;
						}}
					>
						Empty it
					</button>
					<button type="button" class="ghost" onclick={() => (confirming = false)}>Keep it</button>
				</p>
			{:else}
				<button type="button" class="ghost" onclick={() => (confirming = true)}>
					Empty the basket
				</button>
			{/if}
		</div>

		<p class="provenance">
			Every export carries the lexicon version and analytical hash each item was taken under, so a
			row stays traceable after the corpus is rebuilt.
		</p>
	{/if}
</dialog>

<style>
	dialog {
		width: min(48rem, calc(100vw - 2 * var(--sp-4)));
		max-height: min(80vh, 52rem);
		padding: var(--sp-5);
		border: var(--hair) solid var(--rule-strong);
		background: var(--paper);
		color: var(--ink);
		overflow-y: auto;
	}

	dialog::backdrop {
		background: color-mix(in oklab, var(--ink) 45%, transparent);
	}

	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--sp-4);
	}

	h2 {
		font-family: var(--serif);
		font-size: var(--step-2);
		margin: 0;
	}

	.n {
		font-family: var(--mono);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	.hint,
	.empty,
	.provenance,
	.problem {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
		line-height: 1.5;
		max-width: 62ch;
	}

	.hint {
		margin-block: var(--sp-2) var(--sp-4);
	}

	.problem {
		color: var(--ink-2);
		background: var(--paper-sunk);
		border-inline-start: 3px solid var(--rule-strong);
		padding: var(--sp-2) var(--sp-3);
		margin-block: var(--sp-3);
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	li {
		border-top: var(--hair) solid var(--rule);
		padding-block: var(--sp-4);
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
	}

	.symbol {
		font-family: var(--mono);
	}

	.dot {
		color: var(--rule-strong);
	}

	/* Not an error colour: an item recorded under an older lexicon is a fact
	   about provenance, and the text it holds is still exactly what was said. */
	.badge {
		font-family: var(--sans);
		font-size: var(--step--2);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink-3);
		border: var(--hair) solid var(--rule-strong);
		padding: 0 var(--sp-1);
	}

	blockquote {
		font-family: var(--serif);
		font-size: var(--step-0);
		line-height: 1.5;
		margin: var(--sp-2) 0 var(--sp-3);
		padding-inline-start: var(--sp-3);
		border-inline-start: 2px solid var(--rule-strong);
	}

	.whole {
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-2);
		margin: var(--sp-2) 0 var(--sp-3);
	}

	textarea {
		width: 100%;
		font-family: var(--sans);
		font-size: var(--step--1);
		padding: var(--sp-2);
		border: var(--hair) solid var(--rule);
		background: var(--paper-raised);
		color: var(--ink);
		resize: vertical;
	}

	.actions,
	.exports,
	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-4);
	}

	.actions {
		margin-top: var(--sp-2);
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	.actions a {
		display: inline-flex;
		align-items: center;
		gap: var(--sp-1);
	}

	.foot {
		justify-content: space-between;
		border-top: var(--hair) solid var(--rule-strong);
		padding-top: var(--sp-4);
		margin-top: var(--sp-2);
	}

	.label {
		font-family: var(--sans);
		font-size: var(--step--2);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-3);
	}

	.confirm {
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-2);
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2);
		margin: 0;
	}

	.danger {
		color: var(--reg-contentious, var(--ink));
		font-weight: 600;
	}

	.provenance {
		margin-top: var(--sp-3);
	}

	/* Each note needs a label naming the item it belongs to, because a screen
	   reader meets a column of identical text areas otherwise; on screen the
	   quotation directly above it is that label. Defined here rather than
	   globally, as `Standing.svelte` does. */
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	@media (max-width: 40rem) {
		dialog {
			padding: var(--sp-4);
		}
	}
</style>
