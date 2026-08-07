import { annual, changePoints, keyness, kwicIndex } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({
	series: await annual(fetch),
	breaks: await changePoints(fetch),
	keyness: await keyness(fetch),
	kwic: await kwicIndex(fetch)
});
