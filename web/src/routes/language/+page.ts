import { collocates, keyness, network, slicedCollocates } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({
	collocates: await collocates(fetch),
	sliced: await slicedCollocates(fetch),
	keyness: await keyness(fetch),
	network: await network(fetch)
});
