import { annual, changePoints, events } from '$lib/data';
import type { PageLoad } from './$types';

// Together rather than in sequence: three independent files, and this is the
// route a reader arrives on. See `chronology/+page.ts` for the same reasoning
// at six.
export const load: PageLoad = async ({ fetch }) => {
	const [series, breaks, overlay] = await Promise.all([
		annual(fetch),
		changePoints(fetch),
		events(fetch)
	]);
	return { series, breaks, overlay };
};
