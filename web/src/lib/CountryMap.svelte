<script lang="ts">
	/**
	 * The speaker map: MapLibre GL, and a renderer over `actors.ts`.
	 *
	 * It decides nothing. Which speakers exist, which may be drawn, where they
	 * sit and how large their marker is are all settled in `actors.ts`, where
	 * they are tested; this file turns that into circles and clicks.
	 *
	 * **What the map is for.** `docs/PLAN.md` §7.3 permits centroids as
	 * navigation and forbids them as location: every speech in this corpus was
	 * delivered in the Security Council chamber, so a marker over Kigali is a way
	 * to find Rwanda in a list of 133, not a claim about where anyone stood. The
	 * artefact carries that sentence in `centroid_rule` and the view prints it —
	 * the string, not a paraphrase, so the two cannot drift.
	 *
	 * **Why circles and not a choropleth.** Filling territory would key the
	 * drawing on ISO3, and two codes are shared: COD by the DRC and Zaire, SRB by
	 * Serbia, Serbia and Montenegro and Yugoslavia. A fill keyed on the code
	 * paints one row over another with nothing on screen to say it happened.
	 * Circles are keyed on the speaker, and where several share a centroid
	 * `points()` returns one marker that knows how many it stands for.
	 *
	 * **Size, not colour, carries the rate.** Colour is one tone of ink for every
	 * marker, the accent marks the selection because the accent is for
	 * interaction, and a heavier stroke marks a point whose ISO3 is shared. None
	 * of the three encodes a quantity, which keeps the figure inside §7's rule
	 * that colour may not carry what the table cannot support.
	 *
	 * **The map is not the accessible path to this data.** A canvas of circles
	 * cannot be tabbed through or read aloud; the ranked table beside it holds the
	 * same rows in the same order and is the primary presentation.
	 *
	 * That does *not* license hiding this subtree from assistive technology. It
	 * was `aria-hidden` at first, which is a worse bug than the one it was trying
	 * to fix: MapLibre puts real zoom buttons inside the container, and
	 * `aria-hidden` over a focusable control produces exactly the trap the
	 * attribute exists to prevent — a keyboard user tabs to a button no screen
	 * reader will name. The container is labelled instead, saying what it is and
	 * where the data actually lives, and the buttons keep their own labels.
	 */
	import { onMount, untrack } from 'svelte';
	import { colours, colourScheme } from './theme';
	import { escapeHtml } from './format';
	import type { MapPoint } from './actors';
	import type { FeatureCollection } from 'geojson';
	import 'maplibre-gl/dist/maplibre-gl.css';
	/**
	 * MapLibre's worker, bundled by us and handed over explicitly.
	 *
	 * v6 finds its own worker at runtime — `new URL('./maplibre-gl-worker.mjs',
	 * import.meta.url)` — which resolves against whatever chunk the library ends
	 * up inside. Rollup cannot see a runtime URL as a dependency, so it emits no
	 * worker at all, and on GitHub Pages the request falls through to `404.html`:
	 * "Loading worker … was blocked because of a disallowed MIME type
	 * ('text/html')". It works in dev only because Vite serves node_modules.
	 *
	 * `?worker&url` makes Vite bundle the worker *and* the
	 * `./maplibre-gl-shared.mjs` it imports into one hashed asset, and hands back
	 * a base-path-aware URL. `setWorkerUrl` then points the library at it instead
	 * of at its own guess. A plain `?url` would not do: it copies the entry
	 * verbatim and the sibling import would 404 in its place.
	 */
	import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

	interface Props {
		points: MapPoint[];
		/** 0-to-1 position in the drawn range, per point, for the radius. */
		weight: (point: MapPoint) => number;
		selected: string | null;
		onselect: (point: MapPoint | null) => void;
		/**
		 * What the hover box says: a heading and its lines, per point.
		 *
		 * The page supplies it rather than this component building it, because the
		 * wording depends on which figure is being ranked by and on the artefact's
		 * units — knowledge that lives with the route, not with the renderer.
		 */
		describe: (point: MapPoint) => { heading: string; lines: string[] };
		height?: string;
	}

	let { points, weight, selected, onselect, describe, height = '30rem' }: Props = $props();

	/**
	 * Keyless vector styles from CARTO, one per theme. Verified live on
	 * 10 August 2026. They carry their own OpenStreetMap and CARTO attribution in
	 * the style document, which MapLibre renders — do not suppress the control.
	 */
	const STYLES = {
		light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
		dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
	} as const;

	const SOURCE = 'speakers';
	const LAYER = 'speaker-circles';

	let container: HTMLDivElement;
	let map: import('maplibre-gl').Map | null = null;
	let hover: import('maplibre-gl').Popup;
	let ready = $state(false);
	let failed = $state<string | null>(null);
	/** The basemap is taking long enough that the reader should be told where else to look. */
	let slow = $state(false);

	/** One feature per drawable point. `id` is the speaker key, never the ISO3. */
	function collection(): FeatureCollection {
		return {
			type: 'FeatureCollection',
			features: points.map((point) => ({
				type: 'Feature',
				geometry: { type: 'Point', coordinates: point.lngLat },
				properties: {
					key: point.speakers[0].speaker.country_org,
					weight: weight(point),
					shared: point.shared ? 1 : 0,
					stacked: point.speakers.length
				}
			}))
		};
	}

	/**
	 * The circle colours, from the same `palette()` every other figure reads.
	 *
	 * This file used to call `getComputedStyle` itself and carry `#1b5fa8` and
	 * `#3d444c` as its own fallbacks — a third and fourth copy of two values
	 * `theme.ts` already resolves, in the file whose opening sentence is that
	 * there should be one definition of the palette and not two that drift.
	 */
	const fill = (key: string | null): import('maplibre-gl').ExpressionSpecification => [
		'case',
		['==', ['get', 'key'], key ?? ' '],
		$colours.accent,
		$colours.inkSoft
	];

	/**
	 * The speakers, added once.
	 *
	 * This used to run again on every `style.load`, because `setStyle` discarded
	 * the source and the layer with the old style and they had to be put back.
	 * It also put the handlers below back, every time, on top of the ones already
	 * there: three theme toggles left four click handlers on the same layer.
	 * `transformStyle` carries the source and layer into the incoming style
	 * instead, so this runs exactly once and the guards it needed are gone.
	 */
	function paint(instance: import('maplibre-gl').Map) {
		instance.addSource(SOURCE, { type: 'geojson', data: collection() });
		instance.addLayer({
			id: LAYER,
			type: 'circle',
			source: SOURCE,
			paint: {
				// Radius is linear in the position within the drawn range, with a
				// floor: a speaker at the bottom of the range is still a speaker,
				// and a zero-radius circle is an omission the reader cannot see.
				'circle-radius': ['+', 4, ['*', 16, ['get', 'weight']]],
				'circle-color': fill(selected),
				'circle-opacity': 0.62,
				'circle-stroke-width': ['case', ['==', ['get', 'shared'], 1], 2, 1],
				'circle-stroke-color': $colours.paper,
				'circle-stroke-opacity': 0.9
			}
		});

		instance.on('click', LAYER, (event) => {
			const key = event.features?.[0]?.properties?.key;
			onselect(points.find((p) => p.speakers[0].speaker.country_org === key) ?? null);
		});
		// A click on the basemap clears the selection: the reader has pointed at
		// nothing, which is a choice and not a misfire.
		instance.on('click', (event) => {
			if (!instance.queryRenderedFeatures(event.point, { layers: [LAYER] }).length) {
				onselect(null);
			}
		});
		/**
		 * The hover box.
		 *
		 * `mousemove` rather than `mouseenter`, so moving between two circles that
		 * overlap moves the box instead of leaving it on the first one. The
		 * coordinates come from the feature, not the pointer, so the box is
		 * anchored to the marker and does not jitter under the cursor.
		 *
		 * It is a convenience, not the accessible path: hovering is not something
		 * a keyboard offers, which is why the same figures are in the table.
		 */
		instance.on('mousemove', LAYER, (event) => {
			const feature = event.features?.[0];
			const key = feature?.properties?.key;
			const point = points.find((p) => p.speakers[0].speaker.country_org === key);
			if (!point) return;
			instance.getCanvas().style.cursor = 'pointer';
			const { heading, lines } = describe(point);
			hover
				.setLngLat(point.lngLat)
				.setHTML(
					`<p class="hover-head">${escapeHtml(heading)}</p>` +
						lines.map((line) => `<p class="hover-line">${escapeHtml(line)}</p>`).join('')
				)
				.addTo(instance);
		});
		instance.on('mouseleave', LAYER, () => {
			instance.getCanvas().style.cursor = '';
			hover.remove();
		});
	}

	onMount(() => {
		let dead = false;
		/**
		 * A basemap that never arrives must stop claiming to be arriving.
		 *
		 * MapLibre drives `load` from its render loop, and a render loop is
		 * `requestAnimationFrame`, which browsers do not run for a page that is
		 * not visible. A reader who opens this view in a background tab, or whose
		 * network drops the tiles, would otherwise sit on "Loading the basemap…"
		 * for as long as the tab is open, with no hint that the same 133 rows are
		 * already complete a screen further down. After this long, say so.
		 */
		const patience = window.setTimeout(() => {
			if (!dead && !ready) slow = true;
		}, 6000);

		// Dynamic: maplibre-gl touches `window` at module scope, and every route
		// on this site is prerendered to static HTML by adapter-static.
		import('maplibre-gl')
			.then(({ Map, NavigationControl, Popup, setWorkerUrl }) => {
				if (dead) return;
				setWorkerUrl(workerUrl);
				// No close button and no close-on-click: it follows the pointer and
				// leaves with it, so a control to dismiss it would never be used.
				hover = new Popup({
					closeButton: false,
					closeOnClick: false,
					offset: 14,
					className: 'speaker-hover'
				});
				const instance = new Map({
					container,
					style: STYLES[untrack(() => $colourScheme)],
					center: [10, 20],
					zoom: 1.1,
					// The projection is a rendering choice, and a globe would make
					// the marker sizes this figure relies on vary with latitude.
					attributionControl: { compact: true },
					// Nothing here rewards tilting, and a tilted map makes two
					// circles of equal radius look unequal.
					pitchWithRotate: false,
					dragRotate: false,
					touchZoomRotate: true
				});
				instance.addControl(new NavigationControl({ showCompass: false }), 'top-right');
				instance.on('load', () => {
					if (dead) return;
					paint(instance);
					ready = true;
					slow = false;
				});
				// Tiles, glyphs and the style document all report here. Left
				// unhandled, a basemap that 404s or a CORS refusal is a silent
				// blank rectangle — MapLibre logs to the console and carries on.
				instance.on('error', (event) => {
					if (!dead && !ready) failed = event.error?.message ?? 'The basemap did not load.';
				});
				map = instance;
			})
			.catch((error: unknown) => {
				failed = error instanceof Error ? error.message : 'The map library failed to load.';
			});

		return () => {
			dead = true;
			window.clearTimeout(patience);
			hover?.remove();
			map?.remove();
			map = null;
		};
	});

	// Points, selection and theme each redraw without rebuilding the map.
	$effect(() => {
		const data = collection();
		if (map && ready) {
			(map.getSource(SOURCE) as import('maplibre-gl').GeoJSONSource | undefined)?.setData(data);
		}
	});

	/**
	 * Everything about the circles that a colour can change.
	 *
	 * Selection and theme both land here, and both have to: the layer carried
	 * across a style swap keeps the paint it was created with, so a stroke left
	 * un-updated would stay the previous theme's paper colour under the new
	 * basemap.
	 */
	$effect(() => {
		const circle = fill(selected);
		const stroke = $colours.paper;
		if (!map || !ready || !map.getLayer(LAYER)) return;
		map.setPaintProperty(LAYER, 'circle-color', circle);
		map.setPaintProperty(LAYER, 'circle-stroke-color', stroke);
	});

	/**
	 * A theme change swaps the basemap and keeps the speakers.
	 *
	 * `transformStyle` hands us the incoming style before it is committed, so
	 * the source and the layer move into it rather than being discarded with the
	 * old one and re-added afterwards. That removes the blank frame between the
	 * two styles, the `style.load` handler, and the duplicate event handlers it
	 * registered each time it ran.
	 */
	$effect(() => {
		const scheme = $colourScheme;
		if (!map || !ready) return;
		map.setStyle(STYLES[scheme], {
			transformStyle: (previous, next) => {
				if (!previous) return next;
				const source = previous.sources[SOURCE];
				const layer = previous.layers.find((one) => one.id === LAYER);
				return {
					...next,
					sources: source ? { ...next.sources, [SOURCE]: source } : next.sources,
					// Appended, so the circles stay above the basemap's own layers.
					layers: layer ? [...next.layers, layer] : next.layers
				};
			}
		});
	});
</script>

<div class="frame" style:height>
	<div
		class="canvas"
		bind:this={container}
		role="group"
		aria-label="Locator map of the ranked speakers. The ranked table below carries the same rows in the same order."
	></div>
	{#if failed}
		<p class="state" role="status">
			The map did not load ({failed}). Every speaker it would show is in the table below, which is
			the same data in the same order.
		</p>
	{:else if !ready}
		<p class="state" role="status">
			{#if slow}
				The basemap has not loaded. Every speaker it would show is in the table below, which is the
				same data in the same order — the map is only an index into it.
			{:else}
				Loading the basemap…
			{/if}
		</p>
	{/if}
</div>

<style>
	.frame {
		position: relative;
		border-top: var(--hair) solid var(--rule);
		border-bottom: var(--hair) solid var(--rule);
		background: var(--paper-sunk);
	}

	.canvas {
		width: 100%;
		height: 100%;
	}

	.state {
		position: absolute;
		inset-inline: 0;
		top: 50%;
		margin: 0;
		transform: translateY(-50%);
		padding: 0 var(--sp-5);
		text-align: center;
		font-family: var(--sans);
		font-size: var(--step--1);
		color: var(--ink-3);
	}

	/* The basemap's own chrome, brought into the page's palette. No radius and
	   no shadow: nothing on this site is framed. */
	.frame :global(.maplibregl-ctrl-group) {
		border-radius: 0;
		box-shadow: none;
		border: var(--hair) solid var(--rule);
		background: var(--paper-raised);
	}

	.frame :global(.maplibregl-ctrl-group button + button) {
		border-top: var(--hair) solid var(--rule);
	}

	.frame :global(.maplibregl-ctrl-attrib) {
		background: color-mix(in srgb, var(--paper) 82%, transparent);
		font-family: var(--sans);
		font-size: var(--step--2);
	}

	.frame :global(.maplibregl-ctrl-attrib a) {
		color: var(--ink-3);
	}

	/* The hover box, in the page's palette. Square, hairline, no shadow — the
	   same treatment the ECharts tooltips get in `theme.ts`. */
	:global(.speaker-hover .maplibregl-popup-content) {
		background: var(--paper-raised);
		border: var(--hair) solid var(--rule-strong);
		border-radius: 0;
		box-shadow: none;
		padding: var(--sp-2) var(--sp-3);
		font-family: var(--sans);
	}

	:global(.speaker-hover .maplibregl-popup-tip) {
		display: none;
	}

	:global(.speaker-hover .hover-head) {
		margin: 0 0 var(--sp-1);
		font-size: var(--step--1);
		font-weight: 600;
		color: var(--ink);
	}

	:global(.speaker-hover .hover-line) {
		margin: 0;
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-2);
		white-space: nowrap;
	}

	@media (prefers-reduced-motion: reduce) {
		.frame :global(.maplibregl-canvas) {
			transition: none;
		}
	}
</style>
