/**
 * Keeping a route's controls and its address in step.
 *
 * Every view whose controls change a reading writes them into the URL, so a
 * copied address restores the same measures, filters and comparisons. Each
 * did it the same way: read the query into the controls when the page mounts,
 * wait a tick, then rewrite the address whenever a control moves. This is
 * that pattern once.
 *
 * The tick is not decoration. The first `replaceState` has to wait until
 * SvelteKit has assigned its root; called inside the initial mount callback it
 * reaches the client router before that assignment is complete.
 *
 * Call it during component initialisation, where a route would have called
 * `onMount` and `$effect` itself: it registers both, in that order.
 */

import { pushState, replaceState } from '$app/navigation';
import { page } from '$app/state';
import { onMount, tick } from 'svelte';
import type { HistoryStep } from './concordance';

export interface UrlStateOptions {
	/** Put the state the address carries into the controls. Runs once, on mount. */
	read: (params: URLSearchParams) => void;
	/**
	 * The query the controls stand for now. Read inside an effect, so every
	 * control it touches is followed.
	 */
	write: () => URLSearchParams;
	/** Anything that has to wait for the state `read` applied, run before the first write. */
	settle?: () => void;
	/**
	 * Push, replace or leave the history alone for a new query. Without it
	 * every change replaces the entry it is on.
	 */
	step?: (next: URLSearchParams) => HistoryStep;
	/**
	 * Read the address again on Back and Forward. Only a route that pushes
	 * entries needs it: its entries are shallow, so SvelteKit restores
	 * `page.state` and leaves `page.url` where the last real navigation put it,
	 * and the address bar is the only thing that knows which entry the reader
	 * has stepped back to.
	 */
	restore?: (search: string) => void;
}

export function urlState(options: UrlStateOptions): { readonly ready: boolean } {
	let ready = $state(false);

	onMount(() => {
		options.read(page.url.searchParams);
		void tick().then(() => {
			options.settle?.();
			ready = true;
		});
		const { restore } = options;
		if (!restore) return;
		const back = () => restore(location.search);
		window.addEventListener('popstate', back);
		return () => window.removeEventListener('popstate', back);
	});

	$effect(() => {
		if (!ready) return;
		const next = options.write();
		const step = options.step ? options.step(next) : 'replace';
		if (step === 'none') return;
		const search = next.toString();
		const url = `${page.url.pathname}${search ? `?${search}` : ''}`;
		if (step === 'push') pushState(url, page.state);
		else replaceState(url, page.state);
	});

	return {
		get ready() {
			return ready;
		}
	};
}
