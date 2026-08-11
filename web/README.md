# Dashboard

SvelteKit 2 / Svelte 5 (runes), ECharts 6, MapLibre 6, `adapter-static`. No backend and no
database: every view reads static JSON written by the pipeline.

```bash
npm ci
npm run dev      # http://localhost:5173/genocide-at-the-security-council/
npm run check    # svelte-check
npm run lint     # prettier + eslint
npm test         # vitest — 252 tests over the modules the views compute with
npm run build    # → build/, then verify-static.mjs checks every public route arrived
```

The app needs `static/data/`, which is gitignored and 491 MB. Build it with
`scripts/09_export_speeches.py` then `scripts/export_web.py`. Without it, every page fails
with a message saying so rather than rendering empty.

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
click and decides nothing.

## Views

| Route               | What it is for                                                                                                                                                          |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                 | The question in fifteen seconds: headline figures, the raw-versus-rate contrast, register shares                                                                        |
| `/chronology`       | Every term and register over 32 years or 128 quarters in four units, with change points and 35 reference dates, plus the year × month grid and the twelve months pooled |
| `/language`         | Collocates as effect-size-against-significance, the same table as a cloud, two speakers side by side, matched keyness, the co-occurrence graph                          |
| `/actors`           | 601 speakers against their own denominators: the ranking, the locator map, the membership composition and the per-speaker matched keyness                               |
| `/concordance`      | All 79,569 lines, filterable by term, speaker, agenda, meeting, year and month, with corpus-linguistic left/right context sorting and CSV export                        |
| `/reader/[meeting]` | The full verbatim record with matches highlighted by register                                                                                                           |
| `/methods`          | How every number was made, and what is still unverified                                                                                                                 |

`/reader/[meeting]` is the only client-only route: prerendering it would mean generating
6,595 pages to display text that is already fetched as JSON. The static adapter's
`404.html` fallback serves it.

## Layout

```
src/
├── app.css              Design tokens. Charts read the palette from here too.
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
logic nobody will test twice. `docs/PLAN.md` §7 states the rule; the 252 tests are what
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
