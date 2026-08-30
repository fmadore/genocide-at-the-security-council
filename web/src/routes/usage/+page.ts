import { usage } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	// One artefact up front, and deliberately one. `usage/occurrences.json`
	// carries an annotation for every occurrence in the corpus and
	// `kwic/genocide.json` is several megabytes; neither is needed until a
	// reader opens a cell, so both are fetched in the browser at the first
	// drill-down — the same division the concordance makes between its index and
	// the lines of one term.
	const [summary] = await Promise.all([usage(fetch)]);
	return { usage: summary };
};
