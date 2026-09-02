import { collocates, keyness, network, nodeFrames, slicedCollocates } from '$lib/data';
import type { PageLoad } from './$types';

// Four artefacts from 05 and one from 17, all independent of each other. See
// `chronology/+page.ts` for why they are requested together.
export const load: PageLoad = async ({ fetch }) => {
	const [collocated, sliced, key, graph, frames] = await Promise.all([
		collocates(fetch),
		slicedCollocates(fetch),
		keyness(fetch),
		network(fetch),
		nodeFrames(fetch)
	]);
	return { collocates: collocated, sliced, keyness: key, network: graph, frames };
};
