import { kwicIndex } from '$lib/data';
import type { PageLoad } from './$types';

// Only the index is loaded up front. The lines themselves are up to 10 MB per
// term, so they are fetched in the browser when a term is chosen.
export const load: PageLoad = async ({ fetch }) => ({ index: await kwicIndex(fetch) });
