import { scopeIndex } from '$lib/data';
import type { LayoutLoad } from './$types';

// Every page is a static file. The reader route opts out below, because
// prerendering it would mean generating 9,464 pages to show text that is
// already fetched as JSON.
export const prerender = true;
export const trailingSlash = 'always';

/** The global scope control needs 1 kB of counts, not the 3 MB meeting index. */
export const load: LayoutLoad = async ({ fetch }) => ({ scopeIndex: await scopeIndex(fetch) });
