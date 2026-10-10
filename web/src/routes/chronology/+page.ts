import {
	annual,
	breakdowns,
	changePoints,
	decomposition,
	events,
	monthly,
	optional,
	quarterly
} from '$lib/data';
import type { PageLoad } from './$types';

// Six independent files, requested together. Awaited one after another they
// cost six round trips for 748 kB that share no dependency on each other —
// `monthly` does not need `annual` to have arrived, and the reader waits for
// the sum of the latencies rather than the largest of them. Nothing here
// changes what is fetched; only how long the page takes to have it.
export const load: PageLoad = async ({ fetch }) => {
	const [year, quarter, month, splits, breaks, overlay, parts] = await Promise.all([
		annual(fetch),
		quarterly(fetch),
		monthly(fetch),
		breakdowns(fetch),
		changePoints(fetch),
		events(fetch),
		// Optional: a payload built before the decomposition existed still draws.
		// A decomposition that is present and refused is not the same fact, and
		// reaches the page as the refusal it is.
		optional(decomposition(fetch))
	]);
	return { year, quarter, month, splits, breaks, overlay, parts };
};
