import { annual, changePoints, events } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({
	series: await annual(fetch),
	breaks: await changePoints(fetch),
	overlay: await events(fetch)
});
