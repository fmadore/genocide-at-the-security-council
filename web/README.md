# Dashboard

SvelteKit 2 / Svelte 5 (runes), ECharts 6, MapLibre 6, `adapter-static`. No backend and no
database: every view reads static JSON written by the pipeline.

```bash
npm ci
npm run dev      # http://localhost:5173/genocide-at-the-security-council/
npm run check    # svelte-check
npm run lint     # prettier + eslint
npm test         # vitest — unit tests over the modules the views compute with
npm run test:e2e # Playwright — Chromium journeys over tiny fixtures
npm run test:e2e:sw # Playwright — built-site reader recovery while offline
npm run build    # → build/, then verify-static.mjs checks every public route arrived
```

The app needs `static/data/`, which is gitignored and 491 MB. Build it with
`scripts/09_export_speeches.py` then `scripts/export_web.py`. Without it, every page fails
with a message saying so rather than rendering empty.

The browser suite uses the committed files under `e2e/fixtures/`, selected only when
Playwright starts its local server with `E2E_FIXTURES=1`; it never reads or copies the
production payload. Install Chromium once with `npx playwright install chromium`. The CI
job installs Chromium and runs the suite after the unit, formatting, lint, and type gates.
Fixture-server tests block service workers so request interception can exercise the visible
failure-and-retry path deterministically; production service-worker/offline coverage is a
separate remaining roadmap journey.

## Every figure explains itself

This is the one rule the whole application is arranged around, and
[`src/lib/Figure.svelte`](src/lib/Figure.svelte) enforces it structurally: a chart cannot
be placed on a page without supplying four things.

| Prop       | What it must say                                                           |
| ---------- | -------------------------------------------------------------------------- |
| `question` | What this figure is here to answer, in one sentence                        |
| `reading`  | How to read the marks — which axis, what colour encodes, what a click does |
| `caveat`   | What it does **not** show, or what would be wrong to conclude from it      |
| `source`   | The script and the file behind it, so any number can be traced back        |

`caveat` is the one that earns its place. The 2014 chart says a share of speeches is not a
measure of intensity; the register chart says its lines overlap and must not be stacked;
the month grid says its brightest cells are the tribunal reporting calendar; the keyness
table says the unmatched column is not a result. Each of those is a wrong reading that the
figure would otherwise invite.

Beside the source, every figure offers what it is made of: the artefact's numbers as CSV
with their provenance, and the picture as SVG or PNG with its filters drawn into the image.
The decisions live in [`src/lib/export.ts`](src/lib/export.ts); the button does the work on
click and decides nothing. Newly generated artefacts and their exports include an
`analysis_hash` that stays stable when only the generation timestamp or Git working-tree
state changes, but changes with the analytical content or declared configuration.

## Views

| Route               | What it is for                                                                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                 | The question in fifteen seconds: headline figures, the raw-versus-rate contrast, register shares                                                                    |
| `/chronology`       | Every term and register over 32 years or 128 quarters in four units, with change points, participant-type breakdowns and 35 reference dates, plus the monthly views |
| `/language`         | Collocates as effect-size-against-significance, the same table as a cloud, two speakers side by side, matched keyness, the co-occurrence graph                      |
| `/actors`           | 601 speakers against their own denominators: the ranking, the locator map, the membership composition and the per-speaker matched keyness                           |
| `/concordance`      | All 79,569 lines, filterable by term, speaker, participant type, agenda, meeting, year and month, with context sorting and CSV export                               |
| `/reader/[meeting]` | The full verbatim record with matches highlighted by register                                                                                                       |
| `/methods`          | How every number was made, and what is still unverified                                                                                                             |

Controls that change an analytical reading are reflected in the URL on Chronology, Actors,
Language and Concordance. A copied address therefore restores the same measures, periods,
comparisons and filters. Hover, chart zoom, map-row focus and other transient presentation
state stay local to the browser session.

`/reader/[meeting]` is the only client-only route: prerendering it would mean generating
6,595 pages to display text that is already fetched as JSON. The static adapter's
`404.html` fallback serves it.

## Installable, and it never asks

The site is a PWA: [`static/manifest.webmanifest`](static/manifest.webmanifest) plus
[`src/service-worker.ts`](src/service-worker.ts). Nothing prompts anyone to install it. A
listener in `app.html` cancels Chromium's `beforeinstallprompt`, which is the event that
produces the install banner, and no custom button replaces it — a reader who wants an app
knows where their browser keeps Install, and the entry stays there either way.

**The manifest carries no comments, so its decisions are here.** Every URL in it is
relative — `"start_url": "./"`, `"./icon-192.png"` — because manifest URLs resolve against
the manifest's own address, so the file needs no knowledge of `base` and keeps working
under `BASE_PATH=''`. There is deliberately no `id`: an `id` resolves against the _origin_
rather than the path, so any relative value would resolve to `fmadore.github.io/` and be
shared with every other project hosted there. Omitted, it defaults to the resolved
`start_url`, which is this project's subpath and nobody else's. `display_override` asks for
`minimal-ui` before falling back to `standalone`, because a site whose own claim is that it
is citable should keep the address of the thing being cited on screen.

**The service worker is built around one number: `static/data/` is 468 MB across 6,632
files.** Precaching it — the default shape of a service worker, and what `$service-worker`
would hand over unfiltered — would spend a reader's data on 6,594 meetings they will never
open. So `svelte.config.js` filters that directory out of `serviceWorker.files`, and the
three strategies follow from the same fact:

| What                                  | Strategy                         | Why                                                                                                 |
| ------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| Icons, manifest, `geo/countries.json` | Precached on install             | ~170 KB, and any page that draws needs it                                                           |
| `_app/immutable/**`                   | Cache-first, filled as used      | Content-hashed, so a hit is never stale; not precached, as two thirds of it is ECharts and MapLibre |
| Pages and `data/**`                   | Network-first, cache as fallback | The record is the truth; the cache is what is left when the network is gone                         |

A navigation that fails and has no cached page falls back to the `404.html` shell, so the
router still boots and each view says for itself what it could not load. That shell is
cached with `put` rather than `add` on purpose: a static host answers a direct request for
it with a 404 — the status it exists to carry — and `addAll` rejects its whole batch on any
response that is not `ok`, which failed the install outright and left the site with no
worker at all. Nothing calls `skipWaiting()`, so a new deployment takes over on the next
full load rather than pulling chunks out from under an open tab, and no "new version
available" prompt is needed to manage that.

Rebuild the icons with `python tools/build_icons.py`; they are committed, like
`static/geo/countries.json`, and are cut from the University of Bayreuth mark.

## Layout

```
src/
├── app.css              Design tokens. Charts read the palette from here too.
├── app.html             Theme resolved before first paint; the install prompt cancelled
├── service-worker.ts    The offline layer. Never precaches the 468 MB data payload.
├── lib/
│   ├── types.ts         The shapes the pipeline writes — checked against tests/contract/
│   ├── data.ts          Fetch, cache and refuse: one shape per artefact, one function each
│   ├── theme.ts         Palette read off the CSS custom properties; chart fragments
│   ├── format.ts        Numbers, country names, UN Digital Library links
│   ├── export.ts        CSV with provenance, SVG/PNG with the filters in the image
│   ├── Chart.svelte     ECharts wrapper: lazy import, resize, dark-mode redraw, dispose
│   ├── CountryMap.svelte  MapLibre locator: circles keyed on the speaker, never on ISO3
│   ├── Heatmap.svelte   The year × month grid, drawn as SVG from `heatmap.ts`
│   └── Figure.svelte    The explanation frame above
└── routes/              One directory per view
```

**What a component may decide is nothing.** Every filter, gate, scale and ordering a view
performs at render time lives in a plain module beside it — `actors.ts`, `concordance.ts`,
`heatmap.ts`, `keyness.ts`, `standing.ts`, `wordcloud.ts`, `highlight.ts`, `scroll.ts` —
each with a `.test.ts` next to it, because logic reachable only by mounting a component is
logic nobody will test twice. `docs/PLAN.md` §7 states the rule; the colocated unit suite
holds it.

`data.ts` is where the pipeline is met and, when necessary, refused. `REQUIRED` names every
key each artefact must carry and of what kind, `json()` enforces that before any validator
runs, and the validators hold only what is substantive: a corpus series that does not line
up with its own periods, a month grid that is not rectangular, membership bands that do not
sum to their own denominator, a chronology event with no link to its primary record. A
failed request is evicted from the cache, which is the only reason the concordance's retry
can succeed. `contract.test.ts` checks the other direction — that every field the dashboard
fetches for, and the kind it fetches it as, is one the pipeline actually writes.

`base` is `/genocide-at-the-security-council` for project Pages. Override with `BASE_PATH=''`
to serve from a domain root. Internal links use `resolve()` rather than string-joining the
base, so a renamed route is a type error rather than a broken link.
