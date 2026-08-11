import { collocates, keyness, network, slicedCollocates } from '$lib/data';
import type { PageLoad } from './$types';

// Four artefacts from 05, all independent of each other. See
// `chronology/+page.ts` for why they are requested together.
export const load: PageLoad = async ({ fetch }) => {
	const [collocated, sliced, key, graph] = await Promise.all([
		collocates(fetch),
		slicedCollocates(fetch),
		keyness(fetch),
		network(fetch)
	]);
	return { collocates: collocated, sliced, keyness: key, network: graph };
};
