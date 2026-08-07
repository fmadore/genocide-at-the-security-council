import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// Project Pages are served from a subpath. Override with BASE_PATH='' to serve
// from a domain root, or to preview the build locally.
const base = process.env.BASE_PATH ?? '/un-security-council-debates';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// `fallback` makes the reader an SPA route. Prerendering it would mean
		// generating 6,595 pages to display text that is already fetched as JSON.
		adapter: adapter({ fallback: '404.html', strict: false }),
		paths: { base },
		prerender: { handleHttpError: 'warn' }
	}
};
