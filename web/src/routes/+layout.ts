import { readBuild } from '$lib/build';
import { payloadManifest, scopeIndex } from '$lib/data';
import type { LayoutLoad } from './$types';

// Every page is a static file. The reader route opts out below, because
// prerendering it would mean generating 9,464 pages to show text that is
// already fetched as JSON.
export const prerender = true;
export const trailingSlash = 'always';

/**
 * The scope control and the three views that obey it need 54 kB — the counts,
 * the corpus by year and the corpus by speaker — not the 3 MB meeting index.
 * One artefact rather than three fetches: every consumer already has it here.
 *
 * The payload manifest comes with it, for the footer's build line: about two
 * kilobytes, requested beside the scopes rather than after them, and a page
 * whose payload has no manifest simply goes without the line.
 */
export const load: LayoutLoad = async ({ fetch }) => {
	const [index, manifest] = await Promise.all([scopeIndex(fetch), payloadManifest(fetch)]);
	return { scopeIndex: index, build: readBuild(manifest) };
};
