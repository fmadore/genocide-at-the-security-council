/**
 * One thing a view fetches in the browser, and what a reader is told about it.
 *
 * The concordance's lines, the usage view's evidence, the reader's meeting
 * record and the semantic map are each fetched after the page has rendered,
 * and each needs the same three facts: what arrived, whether it is still on
 * its way, and the sentence to show when it failed. They also need the same
 * two rules. A request superseded by a newer one — a term changed while the
 * last term's file was in flight — must not land over it. And "Try again"
 * must ask for exactly what failed.
 */

export class Resource<T> {
	/** What the last request that finished delivered, or null. */
	value = $state.raw<T | null>(null);
	loading = $state(false);
	/** The sentence the last request failed with, or null. */
	failure = $state<string | null>(null);

	#attempt = 0;
	#controller: AbortController | null = null;
	#last: ((signal: AbortSignal) => Promise<T>) | null = null;

	/**
	 * `loading` may start true: a view whose request cannot start until the
	 * address has been read is still waiting for its data from the first paint,
	 * and saying otherwise would draw an empty result as though it were the
	 * answer.
	 */
	constructor(options: { loading?: boolean } = {}) {
		this.loading = options.loading ?? false;
	}

	/**
	 * Start a request, superseding and aborting any still in flight.
	 *
	 * `clear` empties the value at once, for a view that must not show the
	 * previous answer under a new question. Resolves with what arrived, or null
	 * when the request failed or was superseded, so a caller can act on the
	 * value once it is on screen.
	 */
	load(
		request: (signal: AbortSignal) => Promise<T>,
		options: { clear?: boolean } = {}
	): Promise<T | null> {
		this.#controller?.abort();
		const controller = new AbortController();
		this.#controller = controller;
		this.#last = request;
		const attempt = ++this.#attempt;
		const current = () => attempt === this.#attempt;
		this.loading = true;
		this.failure = null;
		if (options.clear) this.value = null;
		return request(controller.signal)
			.then((value) => {
				if (!current()) return null;
				this.value = value;
				return value;
			})
			.catch((error: unknown) => {
				if (current()) this.failure = error instanceof Error ? error.message : String(error);
				return null;
			})
			.finally(() => {
				if (current()) this.loading = false;
			});
	}

	/** Ask again for whatever was last asked for. */
	retry(): Promise<T | null> {
		return this.#last ? this.load(this.#last) : Promise.resolve(null);
	}

	/** Abort anything in flight and forget it: nothing is being asked for. */
	reset(): void {
		this.#controller?.abort();
		this.#controller = null;
		this.#attempt += 1;
		this.value = null;
		this.loading = false;
		this.failure = null;
	}

	/** Abort anything in flight, keeping what is shown; for a view being torn down. */
	abort(): void {
		this.#controller?.abort();
		this.#attempt += 1;
	}
}
