import { countries, speakerKeyness } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	// Two artefacts, both from 11 and 12, fetched together rather than in
	// sequence: they are independent files and the second is 1.4 MB.
	const [table, keyness] = await Promise.all([countries(fetch), speakerKeyness(fetch)]);
	return { countries: table, keyness };
};
