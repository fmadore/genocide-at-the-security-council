import type { HandleClientError } from '@sveltejs/kit';
import { DataError } from '$lib/data';

/**
 * What a reader is told when a page cannot be built in the browser.
 *
 * SvelteKit replaces the message of any error it did not raise itself with
 * "Internal Error", because an unexpected error may carry something private.
 * The refusals `$lib/data` writes are the opposite case: each one names the
 * file and the way out — no connection and not in the offline cache, not in
 * this release, or present and refused by the boundary — and is the only
 * thing on the page a reader offline can act on. Those pass through as they
 * were written. Anything else, a not-found route included, keeps SvelteKit's
 * own wording.
 */
export const handleError: HandleClientError = ({ error, message }) => ({
	message: error instanceof DataError ? error.message : message
});
