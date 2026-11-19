import { countries } from '#lib/data.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	// One artefact up front. `countries/speaker_keyness.json` (2.3 MB) is fetched
	// in the browser once the page is drawn, for the last plate only: loaded
	// here it was inlined into the prerendered HTML, which the service worker
	// refetches on every visit (audit of 19 November 2026).
	return { countries: await countries(fetch) };
};
