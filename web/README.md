# Dashboard

SvelteKit 2 / Svelte 5 (runes), ECharts 6, `adapter-static`. No backend and no database:
every view reads static JSON written by the pipeline.

```bash
npm ci
npm run dev      # http://localhost:5173/genocide-at-the-security-council/
npm run check    # svelte-check
npm run lint     # prettier + eslint
npm run build    # → build/
```

The app needs `static/data/`, which is gitignored and 483 MB. Build it with
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
the breakdown chart says a rate on twenty speeches swings on a single mention; the
keyness table says the unmatched column is not a result. Each of those is a wrong reading
that the figure would otherwise invite.

## Views

| Route               | What it is for                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `/`                 | The question in fifteen seconds: headline figures, the raw-versus-rate contrast, register shares                    |
| `/chronology`       | Every term and register over 32 years or 128 quarters, in four units, with change points and 35 reference dates     |
| `/language`         | Collocates as effect-size-against-significance, two speakers side by side, matched keyness, the co-occurrence graph |
| `/concordance`      | All 80,011 lines, filterable, with corpus-linguistic left/right context sorting and CSV export                      |
| `/reader/[meeting]` | The full verbatim record with matches highlighted by register                                                       |
| `/methods`          | How every number was made, and what is still unverified                                                             |

`/reader/[meeting]` is the only client-only route: prerendering it would mean generating
6,595 pages to display text that is already fetched as JSON. The static adapter's
`404.html` fallback serves it.

## Layout

```
src/
├── app.css              Design tokens. Charts read the palette from here too.
├── lib/
│   ├── types.ts         The shapes the pipeline writes — kept in step with scripts/ by hand
│   ├── data.ts          Fetch + cache, one function per artefact
│   ├── theme.ts         Palette read off the CSS custom properties; chart fragments
│   ├── format.ts        Numbers, country names, UN Digital Library links
│   ├── Chart.svelte     ECharts wrapper: lazy import, resize, dark-mode redraw, dispose
│   └── Figure.svelte    The explanation frame above
└── routes/              One directory per view
```

`base` is `/genocide-at-the-security-council` for project Pages. Override with `BASE_PATH=''`
to serve from a domain root. Internal links use `resolve()` rather than string-joining the
base, so a renamed route is a type error rather than a broken link.
