import { countries } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({
	countries: await countries(fetch)
});
