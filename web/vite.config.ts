import { readdirSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Project Pages are served from a subpath. Override with BASE_PATH='' to serve
// from a domain root, or to preview the build locally.
const base = basePath(process.env.BASE_PATH ?? '/genocide-at-the-security-council');
const fixtureMode = process.env.E2E_FIXTURES === '1';
// Browser tests serve a tiny committed payload through the real routes.
// Production and ordinary development continue to use `static/`.
const assets = fixtureMode ? 'e2e/fixtures' : 'static';

/**
 * What the service worker precaches on install, as URLs under `base`.
 *
 * Everything in the assets directory except the dashboard payload in `data/` —
 * one file per meeting record, 9,464 of them, which would otherwise be fetched
 * on a reader's first visit for the sake of meetings they did not ask for. The
 * data is served network-first and cached as it is read instead; see the
 * service worker. `og.png` is left out for a smaller reason: it exists for link
 * scrapers, which do not run service workers, so precaching it is 54 KB spent
 * on nobody. Both stay reachable; this list governs precaching, not access.
 *
 * SvelteKit 2 took this as `serviceWorker.files`. SvelteKit 3 removed that
 * option, and the `assets` its `$app/manifest` offers instead lists every
 * static file, so importing it would write all of `data/` into
 * `service-worker.js` itself. The list is made here and handed to the worker
 * as the constant `__PRECACHE__`, beside `__BASE__`, which `$service-worker`
 * also supplied.
 */
function precache(directory: string): string[] {
	return readdirSync(directory, { recursive: true, withFileTypes: true })
		.filter((entry) => entry.isFile())
		.map((entry) => relative(directory, join(entry.parentPath, entry.name)).split(sep).join('/'))
		.filter((path) => !path.startsWith('data/') && path !== 'og.png' && !path.endsWith('.DS_Store'))
		.sort()
		.map((path) => `${base}/${path}`);
}

/** SvelteKit 3 types `paths.base` as empty or rooted; say so before it does. */
function basePath(value: string): '' | `/${string}` {
	if (value === '' || value.startsWith('/')) return value as '' | `/${string}`;
	throw new Error(`BASE_PATH must be empty or start with "/", not "${value}"`);
}

export default defineConfig(({ command }) => ({
	plugins: [
		sveltekit({
			preprocess: vitePreprocess(),
			files: { assets },
			// `fallback` makes the reader an SPA route. Prerendering it would mean
			// generating 9,464 document pages to display text already fetched as JSON.
			adapter: adapter({ fallback: '404.html', strict: true }),
			// Absolute paths, as SvelteKit 2 rendered them. SvelteKit 3 renders
			// `resolve()` and `asset()` relative to the page when this is true (the
			// default), and hydration keeps what was rendered, so links such as a
			// chronology value's way into the concordance read `../concordance?...`.
			// The base is fixed at build time, so portable HTML buys nothing here.
			paths: { base, relative: false },
			prerender: {
				// A fixture build needs only the routes its browser tests visit. Normal
				// releases retain SvelteKit's all-route discovery.
				crawl: !fixtureMode,
				entries: fixtureMode
					? ['/', '/chronology', '/concordance', '/actors', '/usage', '/language', '/methods']
					: ['*'],
				handleHttpError: fixtureMode ? 'warn' : 'fail',
				handleUnseenRoutes: fixtureMode ? 'ignore' : 'fail'
			},
			// SvelteKit 3 polls for a new deployment every hour by default, to set
			// `updated.current`. Nothing here reads it, and the service worker already
			// handles a deployment without prompting anyone (see its comment on
			// `skipWaiting`), so the polling would be requests for nothing.
			version: { pollInterval: 0 },
			// The service worker runs in a built site only: its own comment explains
			// that its cache is safe to keep simple because nothing of it runs while
			// developing. SvelteKit 3 registers it under `vite dev` as well, and there
			// it cannot receive the constants it is built with (Vite supplies `define`
			// in development through a module only pages load).
			serviceWorker: { register: command === 'build' }
		})
	],
	environments: {
		// ECharts is the only heavy dependency; keeping it in its own chunk means
		// a page that shows no chart does not pay for it. Set on the browser build
		// alone: SvelteKit 3 builds the service worker as an environment of this
		// configuration too, as a single file, and the setting failed that build.
		// A `codeSplitting` group rather than `manualChunks`, which Rolldown ignores
		// once SvelteKit sets groups of its own; Vite merges the two lists.
		client: {
			build: {
				rolldownOptions: {
					output: {
						codeSplitting: { groups: [{ name: 'echarts', test: /echarts|zrender/ }] }
					}
				}
			}
		},
		// For the service worker; see `precache` above.
		serviceWorker: {
			define: {
				__BASE__: JSON.stringify(base),
				__PRECACHE__: JSON.stringify(precache(assets))
			}
		}
	},
	ssr: {
		// Lucide ships uncompiled `.svelte` behind its `./icons/*` entries. Node's
		// ESM loader has no opinion about that extension, so the icons have to be
		// bundled for SSR rather than required at runtime.
		noExternal: ['@lucide/svelte']
	}
}));
