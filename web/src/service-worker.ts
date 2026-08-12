/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

// The offline layer. SvelteKit bundles and registers this file automatically in
// a production build and leaves it out of `vite dev`, so nothing here runs while
// developing — which is the only reason a cache this aggressive is safe to keep
// simple.
//
// **What it does not do.** It does not try to make the site work offline before
// it has been used. `web/static/data/` is 468 MB across 6,632 files — 6,595 of
// them one per meeting — and precaching that is not a heavy version of the right
// idea, it is the wrong idea: a reader who opens the Overview would spend their
// month's data on 6,594 meetings they will never read. `svelte.config.js` keeps
// that directory out of `$service-worker.files` so it cannot arrive here by
// accident, and the strategies below are chosen around the same fact.
//
// **The three strategies.**
//
// - *Precached on install*: `files`, minus the data payload — the icons, the
//   manifest, and the country polygons the actor map draws. About 170 KB, all of
//   it needed by a page that draws anything at all.
// - *Cache-first, filled as it is used*: `build`, the Vite output. Every name in
//   it is content-hashed, so a hit is never stale and cannot be. It is not
//   precached because two thirds of it is ECharts and MapLibre, and a reader who
//   stays on the Overview should not pay 2 MB for a chart engine they never see.
// - *Network-first, cache as fallback*: everything else — the prerendered pages
//   and the speech and series JSON. The record is the truth and it is small per
//   request; the cache is what is left when the network is gone.
//
// **Why nothing calls `skipWaiting()`.** A deployment changes the hashed names
// in `build`, so a tab left open on the old HTML would start asking a new
// service worker for chunks its cache no longer has. Letting the new worker wait
// for that tab to close costs nothing a reader notices and removes the failure
// entirely. It also means no "a new version is available" prompt, which is the
// second-most annoying thing a page can do after asking to be installed.

import { base, build, files, version } from '$service-worker';

const worker = self as unknown as ServiceWorkerGlobalScope;

// Keyed on the build, so a deployment starts clean and `activate` can drop every
// cache that is not this one.
const CACHE = `unsc-${version}`;

// The SPA shell adapter-static writes for routes that are not prerendered — the
// reader, which has 6,595 possible URLs and is a route rather than 6,595 pages.
// It belongs to no `$service-worker` array: `build` is Vite's output, `files` is
// `static/`, and this is the adapter's own. Hence the literal.
const FALLBACK = `${base}/404.html`;

// Served from the cache without asking the network first. `build` is safe here
// because its names are content-hashed, and `files` is safe because this whole
// cache is discarded on the next deployment. `FALLBACK` is deliberately not in
// this set: it is reached by name when a navigation fails, never by its own URL.
const CACHE_FIRST = new Set([...build, ...files]);

worker.addEventListener('install', (event) => {
	event.waitUntil(precache());
});

async function precache(): Promise<void> {
	const cache = await caches.open(CACHE);

	// Atomic on purpose. These are the handful of static files a drawing page
	// needs, they are always present, and a build where one is missing is a build
	// worth failing over — `verify-static.mjs` makes the same bet.
	await cache.addAll(files);

	// The shell is fetched and `put` rather than added, because a static host
	// answers a direct request for it with the status it exists to carry: both
	// `vite preview` and GitHub Pages reply 404, which is the correct answer to
	// "give me the not-found page". `addAll` rejects its whole batch on any
	// response that is not `ok`, so including this URL there failed the install
	// outright and left the site with no service worker at all. `put` accepts any
	// status but 206.
	//
	// Tolerated rather than folded into the install's result: without the shell
	// the site still works whenever the network does, and `respond` already
	// treats a shell it cannot find as one it cannot use.
	try {
		await cache.put(FALLBACK, await fetch(FALLBACK, { cache: 'reload' }));
	} catch {
		// Installed while offline, or served by a host that does not expose it.
	}
}

worker.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) {
				if (key !== CACHE) await caches.delete(key);
			}
			// Take over tabs that were loaded before any worker existed, so the
			// first visit is also the one that starts filling the cache.
			await worker.clients.claim();
		})()
	);
});

worker.addEventListener('fetch', (event) => {
	const { request } = event;

	if (request.method !== 'GET') return;

	// Chrome throws on a cross-origin `only-if-cached` request that reaches a
	// worker at all, and there is nothing useful to do with one.
	if (request.cache === 'only-if-cached' && request.mode !== 'same-origin') return;

	const url = new URL(request.url);
	if (url.origin !== worker.location.origin) return;

	event.respondWith(respond(request, url));
});

async function respond(request: Request, url: URL): Promise<Response> {
	const cache = await caches.open(CACHE);

	if (CACHE_FIRST.has(url.pathname)) {
		const hit = await cache.match(request);
		if (hit) return hit;

		const response = await fetch(request);
		if (response.ok) await cache.put(request, response.clone());
		return response;
	}

	try {
		const response = await fetch(request);

		// `ok` and not `status === 200` on purpose: on GitHub Pages every route
		// that is not prerendered is answered with the fallback shell under a 404,
		// and caching that under the reader's own URL would pin an error page to a
		// document that exists. The fallback is cached once, by name, above.
		if (response.ok && !response.headers.get('cache-control')?.includes('no-store')) {
			await cache.put(request, response.clone());
		}

		return response;
	} catch (error) {
		const hit = await cache.match(request);
		if (hit) return hit;

		// A page that was never visited is still a page this app can draw: the
		// shell boots, the router reads the URL, and the view says for itself what
		// it could not load. That is a better offline answer than the browser's.
		if (request.mode === 'navigate') {
			const shell = await cache.match(FALLBACK);
			if (shell) return shell;
		}

		throw error;
	}
}
