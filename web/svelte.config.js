import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// Project Pages are served from a subpath. Override with BASE_PATH='' to serve
// from a domain root, or to preview the build locally.
const base = process.env.BASE_PATH ?? '/genocide-at-the-security-council';
const fixtureMode = process.env.E2E_FIXTURES === '1';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// Browser tests serve a tiny committed payload through the real routes.
		// Production and ordinary development continue to use `static/`.
		files: fixtureMode ? { assets: 'e2e/fixtures' } : undefined,
		// `fallback` makes the reader an SPA route. Prerendering it would mean
		// generating 6,595 document pages to display text already fetched as JSON.
		adapter: adapter({ fallback: '404.html', strict: true }),
		paths: { base },
		prerender: {
			// A fixture build needs only the routes its browser tests visit. Normal
			// releases retain SvelteKit's all-route discovery.
			crawl: !fixtureMode,
			entries: fixtureMode ? ['/concordance', '/actors'] : ['*'],
			handleHttpError: fixtureMode ? 'warn' : 'fail',
			handleUnseenRoutes: fixtureMode ? 'ignore' : 'fail'
		},
		serviceWorker: {
			// What `$service-worker.files` is allowed to contain, and therefore what
			// `src/service-worker.ts` precaches on install. The default is everything
			// in `static/` bar `.DS_Store`, which here would be 468 MB across 6,632
			// files — the whole dashboard payload, fetched on a reader's first visit
			// for the sake of 6,595 meetings they did not ask for. The data is served
			// network-first and cached as it is read instead; see the service worker.
			//
			// `og.png` is excluded for a smaller reason: it exists for link scrapers,
			// which do not run service workers, so precaching it is 54 KB spent on
			// nobody. Both stay reachable — this list governs precaching, not access.
			files: (path) => !path.startsWith('data/') && path !== 'og.png'
		}
	}
};
