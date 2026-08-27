/**
 * The basket's one piece of browser state.
 *
 * This site keeps analytical state in the URL and has, until now, allowed
 * exactly one module-level store: the theme. The basket is the second, and the
 * exception is drawn on the same line. Theme and basket are both **the
 * reader's own**, persistent across routes, and analytically inert — nothing
 * either of them holds changes what a figure measures. State that *does*
 * change a reading stays in the URL, where it can be cited, and adding a
 * basket parameter to a query string would be the real mistake: it would put
 * device-local scratch work into the one thing on this site that is supposed
 * to mean the same for everybody who opens it.
 *
 * Everything that decides anything lives in `basket.ts` and is tested there.
 * This file holds the rune, the two storage calls, and the failure they can
 * produce.
 */

import { browser } from '$app/environment';
import {
	BASKET_KEY,
	addItem,
	emptyBasket,
	holds,
	readBasket,
	removeItem,
	serializeBasket,
	setNote
} from './basket';
import type { Basket, BasketItem } from './basket';

/**
 * Storage that never throws.
 *
 * `localStorage` is not merely absent during prerender: reading it throws
 * outright in a browser configured to block site data, and writing throws on
 * quota. Both are conditions this site should survive with the basket working
 * for the length of the session, so every access is guarded and the failure
 * becomes a sentence rather than a broken page.
 */
function load(): string | null {
	if (!browser) return null;
	try {
		return localStorage.getItem(BASKET_KEY);
	} catch {
		return null;
	}
}

class BasketStore {
	#basket = $state<Basket>(emptyBasket());

	/** A sentence about the last refusal or storage failure, or null. */
	#problem = $state<string | null>(null);

	/**
	 * True once a stored envelope this build cannot read has been found.
	 *
	 * While it is true nothing is written, so the unreadable value survives for
	 * a build that understands it. The reader clears the flag by choosing to
	 * start a new basket, which is the only path that overwrites.
	 */
	#blocked = $state(false);

	#loaded = false;

	/**
	 * Read storage once, from an effect rather than from a getter.
	 *
	 * The lazy version of this — load on first read of `count` — mutates state
	 * while a template is being evaluated, which Svelte 5 refuses outright. It
	 * also could not be right: the server renders an empty basket, so a client
	 * that filled itself during the first read would contradict the markup it
	 * was hydrating. The layout calls this from an effect, which runs after the
	 * first paint, and the count arrives a frame later.
	 */
	hydrate(): void {
		if (this.#loaded || !browser) return;
		this.#loaded = true;
		const read = readBasket(load());
		this.#basket = read.basket;
		if (read.unreadable) {
			this.#problem = read.unreadable;
			this.#blocked = true;
		}
	}

	#persist(): void {
		if (!browser || this.#blocked) return;
		try {
			localStorage.setItem(BASKET_KEY, serializeBasket(this.#basket));
		} catch {
			this.#problem =
				'This browser would not save the basket — its storage may be full or blocked. ' +
				'What is here still works for this visit; export it before closing the tab.';
		}
	}

	#apply(change: { basket: Basket; refused: string | null }): boolean {
		this.#problem = change.refused;
		if (change.refused) return false;
		this.#basket = change.basket;
		this.#persist();
		return true;
	}

	get items(): BasketItem[] {
		return this.#basket.items;
	}

	get count(): number {
		return this.#basket.items.length;
	}

	get problem(): string | null {
		return this.#problem;
	}

	get blocked(): boolean {
		return this.#blocked;
	}

	get basket(): Basket {
		return this.#basket;
	}

	has(id: string): boolean {
		return holds(this.#basket, id);
	}

	add(item: BasketItem): boolean {
		return this.#apply(addItem(this.#basket, item));
	}

	remove(id: string): void {
		this.#apply(removeItem(this.#basket, id));
	}

	note(id: string, note: string): boolean {
		return this.#apply(setNote(this.#basket, id, note));
	}

	clear(): void {
		this.#basket = emptyBasket();
		this.#persist();
		this.#problem = null;
	}

	/**
	 * Abandon an unreadable stored basket and start a new one.
	 *
	 * The only operation that overwrites a value this build could not parse, and
	 * it exists so the choice is the reader's rather than the code's.
	 */
	startOver(): void {
		this.#blocked = false;
		this.#problem = null;
		this.#basket = emptyBasket();
		this.#persist();
	}

	/** Dismiss a refusal once it has been read. */
	settle(): void {
		if (!this.#blocked) this.#problem = null;
	}
}

export const basket = new BasketStore();
