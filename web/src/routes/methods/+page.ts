import { annual, changePoints, keyness, kwicIndex } from '$lib/data';
import type { PageLoad } from './$types';

// Four artefacts from three different steps, read here only for the version
// identifiers and counts the page prints. See `chronology/+page.ts` for why
// they are requested together rather than in sequence.
export const load: PageLoad = async ({ fetch }) => {
	const [series, breaks, key, kwic] = await Promise.all([
		annual(fetch),
		changePoints(fetch),
		keyness(fetch),
		kwicIndex(fetch)
	]);
	return { series, breaks, keyness: key, kwic };
};
