import { annual, breakdowns, changePoints, events, monthly, quarterly } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({
	year: await annual(fetch),
	quarter: await quarterly(fetch),
	month: await monthly(fetch),
	splits: await breakdowns(fetch),
	breaks: await changePoints(fetch),
	overlay: await events(fetch)
});
