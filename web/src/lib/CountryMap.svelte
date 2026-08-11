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
	 * **Two views over the same rows.** Circles are the default and are keyed on
	 * the speaker: `points()` groups coincident centroids into one marker that
	 * knows how many speakers it stands for, so nothing is ever merged by ISO3.
	 * The choropleth is keyed on ISO3 because a fill has to be — territory has a
	 * code, not a speaker — and everything that makes that safe is settled in
	 * `$lib/choropleth`, which refuses to fill a code two drawable speakers share
	 * rather than picking one of them. This file renders whichever view is asked
	 * for and decides neither.
	 *
	 * **In the circle view, size carries the rate and colour carries nothing.**
	 * One tone of ink for every marker, the accent for the selection because the
	 * accent is for interaction, and a heavier stroke where the ISO3 is shared.
	 * In the choropleth colour is the quantity, which is the trade the view
	 * exists to offer: area replaces radius, so a small state is hard to see and
	 * a large one is hard to ignore. Both views are the same table, and the table
	 * is under both of them.
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
	import { base } from '$app/paths';
	import { colours, colourScheme, mix, sequential, tone } from './theme';
	import { escapeHtml } from './format';
	import { withoutPolygon } from './choropleth';
	import type { ChoroplethPlan, Patch } from './choropleth';
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
		/** Which encoding is on screen. The rows behind them are identical. */
		view?: 'points' | 'choropleth';
		/**
		 * The choropleth's decisions, from `fills()`. Null in the circle view, and
		 * the boundary file is not fetched until it is not.
		 */
		fills?: ChoroplethPlan | null;
		/** What the hover box says over a patch. See `describe`; same argument. */
		explain?: (patch: Patch) => { heading: string; lines: string[] };
		/** Names the ramp in the key, e.g. "share of its speeches". */
		unit?: string;
		/** A value on the ramp, written the way the figure writes its numbers. */
		format?: (value: number) => string;
		/**
		 * The speakers the boundary file has no polygon for, reported once it has
		 * loaded. The page states the count; this component draws them as marks
		 * rather than losing them, and neither can say how many before the file is
		 * here to be asked.
		 */
		onmissing?: (patches: Patch[]) => void;
	}

	let {
		points,
		weight,
		selected,
		onselect,
		describe,
		height = '30rem',
		view = 'points',
		fills = null,
		explain,
		unit,
		format,
		onmissing
	}: Props = $props();

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
	/** The world, from `web/static/geo/countries.json`. */
	const WORLD = 'countries';
	const FILL = 'country-fill';
	const CONTESTED = 'country-contested';
	const PICKED = 'country-picked';
	/** Speakers whose code the boundary file has no polygon for. */
	const MARKS = 'unbounded';
	const MARK_LAYER = 'unbounded-marks';

	/**
	 * How far up the ramp a value of zero sits.
	 *
	 * Not at the bottom, which is the colour of the page. A delegation that
	 * cleared a hundred speeches and never said the word is a finding, and in the
	 * circle view it is a four-pixel floor that cannot vanish; here it has to be a
	 * fill a reader can see against an unfilled neighbour. The ramp is compressed
	 * into what is left, which costs a little contrast at the top and buys the
	 * distinction between *nothing* and *not in this figure*.
	 */
	const FLOOR = 0.15;

	/**
	 * The key's swatches, at even steps of the *value* rather than of the ramp.
	 *
	 * That makes it a correct lookup table whatever transform the ramp applies,
	 * and it puts the transform on screen: the colours change fast at the left and
	 * slowly at the right because that is what the square root does. The
	 * chronology's grid draws its key the same way, for the same reason.
	 */
	const STOPS = Array.from({ length: 10 }, (_, index) => tone((index + 0.5) / 10));

	let container: HTMLDivElement;
	let map: import('maplibre-gl').Map | null = null;
	let hover: import('maplibre-gl').Popup;
	let ready = $state(false);
	let failed = $state<string | null>(null);
	/** The basemap is taking long enough that the reader should be told where else to look. */
	let slow = $state(false);

	/**
	 * The boundaries, fetched once and only when a reader asks for them.
	 *
	 * 156 KB of polygons is not much beside the basemap's tiles, but it is a
	 * request nobody who stays on the default view ever needs, and the actor page
	 * already fetches two artefacts before it draws anything.
	 */
	let world = $state<FeatureCollection | null>(null);
	let worldFailed = $state<string | null>(null);
	let fetching = false;
	/** Set once the country layers are on the map, so the paint effects can run. */
	let layered = $state(false);

	/** The ISO3 codes the boundary file actually carries. */
	const bounded = $derived(
		new Set(
			(world?.features ?? [])
				.map((feature) => String(feature.properties?.iso3 ?? ''))
				.filter(Boolean)
		)
	);

	const unbounded = $derived(fills && world ? withoutPolygon(fills, bounded) : []);

	async function fetchWorld() {
		if (fetching || world) return;
		fetching = true;
		try {
			const response = await fetch(`${base}/geo/countries.json`);
			if (!response.ok) throw new Error(`${response.status}`);
			world = (await response.json()) as FeatureCollection;
		} catch (error) {
			worldFailed = error instanceof Error ? error.message : 'the file did not load';
		} finally {
			fetching = false;
		}
	}

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
	 * The colour one country is filled with, and the only place a patch state
	 * becomes ink.
	 *
	 * Three colours for three states, and the two that are not a value are not on
	 * the ramp at all: a withheld country is grey and a contested one is nearly
	 * ink, so neither can be misread as a quiet delegation. Grey rather than a
	 * hatch because MapLibre fills a polygon with an image or with a colour, and
	 * an image that fails to load leaves the polygon empty — which is the one
	 * appearance this state must never take.
	 */
	function patchColour(patch: Patch): string {
		if (patch.state === 'drawn') return sequential($colours)(FLOOR + (1 - FLOOR) * patch.tone);
		if (patch.state === 'withheld') return mix($colours.paper, $colours.inkFaint, 0.45);
		return mix($colours.paper, $colours.ink, 0.62);
	}

	/**
	 * Every patch's colour as one `match` on the ISO3 in the geometry.
	 *
	 * A code the slice does not carry falls through to fully transparent, so the
	 * basemap shows through and a state that never addressed the Council looks
	 * like what it is. That fallback is why the layer needs no filter and why a
	 * change of measure or period is a paint-property update rather than a
	 * re-upload of 166 polygons.
	 */
	function patchFill(plan: ChoroplethPlan | null): import('maplibre-gl').ExpressionSpecification {
		const arms = (plan?.patches ?? []).flatMap((patch) => [patch.iso3, patchColour(patch)]);
		if (!arms.length) return ['to-color', 'rgba(0,0,0,0)'];
		return [
			'match',
			['get', 'iso3'],
			...(arms as [string, string]),
			'rgba(0,0,0,0)'
		] as unknown as import('maplibre-gl').ExpressionSpecification;
	}

	/** The codes in one state, for a layer filter. */
	const codesIn = (plan: ChoroplethPlan | null, state: Patch['state']) =>
		(plan?.patches ?? []).filter((patch) => patch.state === state).map((patch) => patch.iso3);

	/** The marks for speakers with no polygon, as points. */
	function marks(): FeatureCollection {
		return {
			type: 'FeatureCollection',
			features: unbounded.map((patch) => ({
				type: 'Feature',
				geometry: { type: 'Point', coordinates: patch.lngLat as [number, number] },
				properties: { iso3: patch.iso3, key: patch.key ?? '' }
			}))
		};
	}

	/**
	 * Where the fills go in the basemap's own stack.
	 *
	 * Under the boundaries and the place names, which is the whole difference
	 * between a choropleth and a sheet of coloured paper laid over a map: the
	 * borders that separate two filled countries have to be the basemap's, drawn
	 * on top, or two neighbours at similar rates merge into one shape. The layer
	 * is found by name because CARTO's styles are documents we do not control —
	 * if the name ever changes, the first symbol layer is the fallback, and an
	 * appended fill is the worst case rather than a crash.
	 */
	function beneathBorders(layers: { id: string; type: string }[]): string | undefined {
		const boundary = layers.find((layer) => /boundar|border/i.test(layer.id));
		return (boundary ?? layers.find((layer) => layer.type === 'symbol'))?.id;
	}

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
		// nothing, which is a choice and not a misfire. Every layer that can be
		// pointed *at* has to be asked, and only the ones that exist: the country
		// layers arrive with the boundary file, and querying a layer MapLibre does
		// not have throws rather than returning nothing.
		instance.on('click', (event) => {
			const asked = [LAYER, FILL, MARK_LAYER].filter((id) => instance.getLayer(id));
			if (!instance.queryRenderedFeatures(event.point, { layers: asked }).length) {
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

	/**
	 * The world, added once, when a reader first asks for the filled view.
	 *
	 * Like `paint()` this runs exactly once and registers its handlers once; the
	 * theme swap carries these layers across rather than rebuilding them. Only
	 * the fill goes under the basemap's borders — the outlines and the marks are
	 * appended, because an outline that says *this is selected* or *this cannot
	 * be filled* is worth more on top of a place name than under it.
	 */
	function paintCountries(instance: import('maplibre-gl').Map, geometry: FeatureCollection) {
		instance.addSource(WORLD, { type: 'geojson', data: geometry });
		instance.addSource(MARKS, { type: 'geojson', data: marks() });

		instance.addLayer(
			{
				id: FILL,
				type: 'fill',
				source: WORLD,
				layout: { visibility: view === 'choropleth' ? 'visible' : 'none' },
				paint: { 'fill-color': patchFill(fills), 'fill-opacity': 0.82 }
			},
			beneathBorders(instance.getStyle().layers)
		);

		// A code more than one drawable speaker holds. Dashed, in ink, because it
		// is the one mark here that means *refused* rather than *measured*.
		instance.addLayer({
			id: CONTESTED,
			type: 'line',
			source: WORLD,
			layout: { visibility: view === 'choropleth' ? 'visible' : 'none' },
			filter: ['in', ['get', 'iso3'], ['literal', codesIn(fills, 'contested')]],
			paint: { 'line-color': $colours.ink, 'line-width': 1.6, 'line-dasharray': [2, 1.4] }
		});

		instance.addLayer({
			id: PICKED,
			type: 'line',
			source: WORLD,
			layout: { visibility: view === 'choropleth' ? 'visible' : 'none' },
			filter: ['in', ['get', 'iso3'], ['literal', []]],
			paint: { 'line-color': $colours.accent, 'line-width': 2 }
		});

		// The states Natural Earth's 1:110m sheet is too coarse to carry. A fixed
		// radius, so the mark says *here* and the colour says everything else; it
		// is the same colour the polygon would have been.
		instance.addLayer({
			id: MARK_LAYER,
			type: 'circle',
			source: MARKS,
			layout: { visibility: view === 'choropleth' ? 'visible' : 'none' },
			paint: {
				'circle-radius': 4,
				'circle-color': patchFill(fills),
				'circle-stroke-width': 1,
				'circle-stroke-color': $colours.inkFaint
			}
		});

		for (const id of [FILL, MARK_LAYER]) {
			instance.on('click', id, (event) => {
				const code = event.features?.[0]?.properties?.iso3;
				const patch = fills?.patches.find((one) => one.iso3 === code);
				// A contested patch has no single speaker to select, which is the
				// point of it. Clicking one selects nothing rather than one of two.
				onselect(
					(patch?.key && points.find((p) => p.speakers[0].speaker.country_org === patch.key)) ||
						null
				);
			});
			instance.on('mousemove', id, (event) => {
				const code = event.features?.[0]?.properties?.iso3;
				const patch = fills?.patches.find((one) => one.iso3 === code);
				if (!patch || !explain) return;
				instance.getCanvas().style.cursor = 'pointer';
				const { heading, lines } = explain(patch);
				hover
					// Anchored to the pointer, not to a feature: a country is an area
					// and has no one point, and a box pinned to a centroid would sit
					// off Alaska while the reader is over Florida.
					.setLngLat(event.lngLat)
					.setHTML(
						`<p class="hover-head">${escapeHtml(heading)}</p>` +
							lines.map((line) => `<p class="hover-line">${escapeHtml(line)}</p>`).join('')
					)
					.addTo(instance);
			});
			instance.on('mouseleave', id, () => {
				instance.getCanvas().style.cursor = '';
				hover.remove();
			});
		}

		layered = true;
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
					// MapLibre's default is a bare `240px`. In rem it follows the
					// type scale the lines inside it are set in, and it is stated
					// here rather than left implicit because the stylesheet below
					// has cancelled it once already.
					maxWidth: '17rem',
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

	/* The boundary file is a cost only the filled view pays, so it is fetched the
	   first time one is asked for and kept for the rest of the session. */
	$effect(() => {
		if (view === 'choropleth') void fetchWorld();
	});

	/* The country layers, added as soon as both the map and the file are here.
	   Either can arrive first: the file is a fetch and the basemap is a render
	   loop, and neither waits for the other. Both are read before the guards, so
	   that whichever arrives second still re-runs this — `&&` short-circuits, and
	   state a run never reaches is state that run never subscribed to. */
	$effect(() => {
		const geometry = world;
		const loaded = ready;
		if (!map || !loaded || !geometry || map.getSource(WORLD)) return;
		paintCountries(map, geometry);
	});

	/**
	 * Which encoding is on screen. Both stay on the map; a view is a change of
	 * visibility, so switching back does not re-upload anything.
	 *
	 * `layered` is read before the guards and not after, so that adding the
	 * country layers re-runs this. Behind the guards it would never be read on
	 * the pass where the map does not exist yet, would therefore not be a
	 * dependency, and the four layers would arrive hidden and stay hidden — which
	 * is exactly the order a reader produces by pressing *Filled* before the
	 * boundary file has loaded, and is the first thing anyone would try.
	 */
	$effect(() => {
		const showing = view;
		const added = layered;
		const loaded = ready;
		if (!map || !loaded || !added) return;
		const shown = (id: string, on: boolean) => {
			if (map?.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
		};
		shown(LAYER, showing === 'points');
		for (const id of [FILL, CONTESTED, PICKED, MARK_LAYER]) shown(id, showing === 'choropleth');
	});

	/**
	 * Everything about the fills that a slice, a selection or a theme can change.
	 *
	 * All of it is paint and filters over geometry that never changes, which is
	 * what makes a change of measure or period cost nothing but an expression.
	 * Like the circle effect above it re-applies on a theme change, and for the
	 * same reason: the layers are carried into the incoming style with the paint
	 * they had, so a fill left alone would keep the palette of the theme the
	 * reader has just left.
	 */
	$effect(() => {
		const plan = fills;
		const colour = patchFill(plan);
		const contested = codesIn(plan, 'contested');
		const picked = selected
			? (plan?.patches.find((patch) => patch.key === selected)?.iso3 ?? null)
			: null;
		const ink = $colours.ink;
		const accent = $colours.accent;
		const edge = $colours.inkFaint;
		const added = layered;
		const loaded = ready;
		if (!map || !loaded || !added || !map.getLayer(FILL)) return;
		map.setPaintProperty(FILL, 'fill-color', colour);
		map.setFilter(CONTESTED, ['in', ['get', 'iso3'], ['literal', contested]]);
		map.setPaintProperty(CONTESTED, 'line-color', ink);
		map.setFilter(PICKED, ['in', ['get', 'iso3'], ['literal', picked ? [picked] : []]]);
		map.setPaintProperty(PICKED, 'line-color', accent);
		map.setPaintProperty(MARK_LAYER, 'circle-color', colour);
		map.setPaintProperty(MARK_LAYER, 'circle-stroke-color', edge);
		(map.getSource(MARKS) as import('maplibre-gl').GeoJSONSource | undefined)?.setData(marks());
	});

	/* What the page has to say about the speakers no polygon could carry. It
	   cannot be known before the file has loaded, so it is reported rather than
	   asserted. */
	$effect(() => {
		const missing = unbounded;
		if (world) onmissing?.(missing);
	});

	/**
	 * A theme change swaps the basemap and keeps everything drawn over it.
	 *
	 * `transformStyle` hands us the incoming style before it is committed, so
	 * the sources and the layers move into it rather than being discarded with
	 * the old one and re-added afterwards. That removes the blank frame between
	 * the two styles, the `style.load` handler, and the duplicate event handlers
	 * it registered each time it ran.
	 *
	 * The fill has to be *inserted* rather than appended, because where it sits
	 * in the stack is what makes it a choropleth: appending it would put the
	 * country colours over the incoming style's borders and place names. Its
	 * position is found again in the new style rather than remembered from the
	 * old one — the two documents are different files and share no layer order.
	 */
	$effect(() => {
		const scheme = $colourScheme;
		if (!map || !ready) return;
		map.setStyle(STYLES[scheme], {
			transformStyle: (previous, next) => {
				if (!previous) return next;
				const sources = { ...next.sources };
				for (const id of [SOURCE, WORLD, MARKS]) {
					if (previous.sources[id]) sources[id] = previous.sources[id];
				}
				const mine = (id: string) => previous.layers.find((one) => one.id === id);
				const layers = [...next.layers];
				const under = mine(FILL);
				if (under) {
					const before = beneathBorders(layers);
					const at = before ? layers.findIndex((one) => one.id === before) : -1;
					layers.splice(at < 0 ? layers.length : at, 0, under);
				}
				// Appended, so the outlines, the marks and the circles stay above
				// the basemap's own layers.
				const over = [CONTESTED, PICKED, MARK_LAYER, LAYER]
					.map(mine)
					.filter((one) => one !== undefined);
				return { ...next, sources, layers: [...layers, ...over] };
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
	{:else if view === 'choropleth' && worldFailed}
		<p class="state" role="status">
			The boundaries did not load ({worldFailed}), so this is still the circles. They are the same
			rows, and so is the table below.
		</p>
	{:else if view === 'choropleth' && !layered}
		<p class="state" role="status">Loading the boundaries…</p>
	{/if}
</div>

<!-- The key. Beside the figure rather than inside it, because unlike the
     chronology's grid this drawing is a canvas and cannot be downloaded as an
     SVG that carries its own legend. Drawn only once there is something for it
     to be a key to: a legend over a map that failed to load explains nothing. -->
{#if view === 'choropleth' && fills && layered}
	<div class="key">
		<div class="ramp">
			<span class="cap">0</span>
			<span class="stops" aria-hidden="true">
				{#each STOPS as stop (stop)}
					<span class="swatch" style:background={sequential($colours)(FLOOR + (1 - FLOOR) * stop)}
					></span>
				{/each}
			</span>
			<span class="cap">{format ? format(fills.high) : fills.high}</span>
			{#if unit}<span class="unit">{unit}</span>{/if}
		</div>
		<p class="states">
			<span class="pair">
				<span class="swatch" style:background={mix($colours.paper, $colours.inkFaint, 0.45)}></span>
				below the minimum ({fills.withheld})
			</span>
			{#if fills.contested}
				<span class="pair">
					<span class="swatch" style:background={mix($colours.paper, $colours.ink, 0.62)}></span>
					shared code, not filled ({fills.contested})
				</span>
			{/if}
			{#if unbounded.length}
				<span class="pair">
					<span class="dot"></span>
					too small for a boundary at this scale ({unbounded.length})
				</span>
			{/if}
			<span class="pair">unfilled: not a speaker in this period</span>
		</p>
	</div>
{/if}

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

	/* The key sits under the frame and keeps the frame's rule as its own top
	   edge — one hairline between the drawing and what it means, not two. */
	.key {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--sp-2) var(--sp-5);
		padding: var(--sp-2) 0;
		font-family: var(--sans);
		font-size: var(--step--2);
		color: var(--ink-3);
		border-bottom: var(--hair) solid var(--rule);
	}

	.ramp,
	.states,
	.pair {
		display: flex;
		align-items: center;
		gap: var(--sp-2);
	}

	.states {
		flex-wrap: wrap;
		margin: 0;
		gap: var(--sp-2) var(--sp-4);
	}

	.stops {
		display: flex;
	}

	.swatch {
		display: inline-block;
		width: 1.1rem;
		height: 0.6rem;
		border: var(--hair) solid var(--rule);
	}

	.states .swatch {
		width: 0.9rem;
	}

	/* The mark for a state with no boundary, at the size it is drawn on the map. */
	.dot {
		display: inline-block;
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 50%;
		border: var(--hair) solid var(--ink-3);
		background: var(--paper-sunk);
	}

	.cap,
	.unit {
		font-family: var(--mono);
		font-variant-numeric: tabular-nums;
	}

	.unit {
		font-family: var(--sans);
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
		overflow-wrap: break-word;
	}

	/* Wrapping, not `nowrap`.

	   These lines used to be `white-space: nowrap`, which quietly cancelled the
	   popup's own `max-width`: MapLibre writes the cap onto the content element,
	   and a box whose text refuses to wrap simply grows past it. The longest
	   line here — a count, an occurrence total and a regional group name — came
	   out 402px wide against a declared cap of 240, so the box ran off the map at
	   its edges and off a phone at any position. Wrapping at spaces restores the
	   cap; `break-word` is the escape for a single token longer than the box,
	   which a speaker name can be. */
	:global(.speaker-hover .hover-line) {
		margin: 0;
		font-family: var(--mono);
		font-size: var(--step--2);
		color: var(--ink-2);
		overflow-wrap: break-word;
	}

	@media (prefers-reduced-motion: reduce) {
		.frame :global(.maplibregl-canvas) {
			transition: none;
		}
	}
</style>
