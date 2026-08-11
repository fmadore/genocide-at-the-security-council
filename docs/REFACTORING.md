# Refactoring roadmap

Code health, kept separate from [`PLAN.md`](PLAN.md) on purpose. That file records what
would have to be true before a *claim* may be published; this one records what is known to
be wrong with the *code* that produces the claims. Neither is a substitute for the other: a
figure can be perfectly refactored and still uncited, and an honest figure can sit behind a
function nobody can safely change.

Status: 11 August 2026. Everything below was found in a full read of the repository against
a green baseline — 594 pytest, `ruff`, `prettier`, `eslint`, `svelte-check` on 4,090 files,
233 vitest — so nothing here is a failing test. It is all live code that works.

The rule for this file is the rule for the rest of the repository: say what is wrong, say
why it matters, and say what would tell you it was fixed. An item with no third part is a
preference, and preferences do not belong on a backlog.

---

## Done

Recorded so the backlog has a baseline rather than starting mid-sentence.

**The load waterfalls.** Four route loaders awaited independent artefacts one after
another; `chronology` cost six round trips for 748 kB that share no dependency on each
other. All four now request them together. `actors/+page.ts` already did this, and its
comment already said why — the pattern existed and four routes had not followed it.

**The double draw.** `Chart.svelte` drew every figure twice on mount: `onMount` called
`setOption`, and setting `ready` in the same flush woke an effect that called it again
under `notMerge`. A whole SVG tree built, discarded and rebuilt before a reader saw it,
plus a restarted simulation on the network graph. One effect now owns every draw, and the
instance is a `$state.raw` signal so the effect genuinely depends on it rather than on two
effect declarations happening to be in the right order.

**The artefact contract.** The payload's shape was written three times — by the Python that
emits it, by `types.ts` that declares it, by `data.ts` that validates it — with nothing
comparing them, and `types.ts` said so of itself. [`scripts/lib/contract.py`](../scripts/lib/contract.py)
now reduces a payload to its shape, [`tests/contract/payload.json`](../tests/contract/payload.json)
commits it, `export_web.py` refuses to publish a payload that has drifted, and
`web/src/lib/contract.test.ts` checks the other direction — that every field the dashboard
fetches for is one the pipeline actually writes. Growth passes; a lexicon edit passes; a
renamed or dropped field does not.

**Two false rows in the README status table.** The membership composition and the
per-speaker keyness were both marked as not built, months after they shipped. That table is
this project's honesty mechanism, so a stale row in it costs more than a stale row
elsewhere.

**The palette, written down in six places.** `void $colourScheme; return palette();` stood
verbatim in `Heatmap.svelte` and three routes, and `CountryMap.svelte` skipped `palette()`
altogether to read `getComputedStyle` itself with `#1b5fa8` and `#3d444c` as its own
fallbacks. `theme.ts` now exports `colours`, a store derived from the scheme, and the load
bearing `void` is explained once where it lives rather than copied four times where it looks
like a mistake. `palette()` resolves the computed style once instead of sixteen times, and
the map paints from the same two values as every other figure. Verified in a browser: the
ECharts strokes move from `#2c3134`/`#e7e9e2` to `#d6d9cf`/`#14171a` on the toggle, so the
figures still follow the theme.

**Two decisions moved out of this file and into the code.** Why ECharts 6's `setTheme()`
was considered and refused now sits in `theme.ts`, where the next reader meets it as a
decision rather than as a gap; and `escapeHtml` and `escapeXml` each say why the other
exists, so the pair is not merged into one function that is subtly wrong in whichever place
it is not.

---

## 1 · Maintainability

Nothing here changes what a reader sees. Each is a decision written down more than once,
which is how two copies of it start to disagree.

### 1.1 The fetch boundary states its requirements twice

`json()` takes a `required` key list *and* a validator, and every validator re-checks the
same keys: `annual` passes `['meta', 'periods', 'corpus', 'terms']` and `validateAnnual`
dereferences all four. The list is now a value (`REQUIRED` in `data.ts`, which the contract
test reads), so the remaining work is to make the validators derive their structural checks
from it instead of repeating them, leaving each validator holding only its *substantive*
refusals — the alignment checks, the finite-number checks, the standing-block sum.

**Done when** a key can be added to `REQUIRED` and nothing else needs editing for the
boundary to require it.

### 1.2 `frames.write` reimplements the atomic write

`artifacts.py` owns atomic replacement, and `frames.write` has its own ten-line copy of the
temp-file dance because `to_parquet` wants a path rather than bytes. An `atomic_path()`
context manager in `artifacts.py` would serve both, and would keep the crash-safety
argument in one file.

**Done when** `frames.py` no longer imports `tempfile`.

### 1.3 Two `# type: ignore[index]` in `export_web.py`

Both are on `manifest["parts"][name]`, and both go away by giving `parts` its own typed
local instead of building it inside an untyped `dict[str, object]`. A silenced type error is
a small lie about what the code knows.

**Done when** `export_web.py` has no `type: ignore`.

### 1.4 Fifteen copies of the `sys.path` bootstrap

Every numbered script inserts `scripts/` on the path before importing `lib`, and
`pyproject.toml` carries a per-file `E402` ignore to permit it. It is genuinely awkward to
remove — a module cannot be named `04_series`, so `python -m` is not available — and the
current shape is honest about what it does. Listed so that it is a known cost rather than
an unexamined habit, not because it should change today.

---

## 2 · What a reader can feel

These change runtime behaviour, so each needs a decision rather than just an edit.

### 2.1 The artefact cache never evicts

`data.ts` caches every payload by URL for the life of the session, deliberately: the
comment says it exists so a reader moving between views does not pay twice for a 10 MB
concordance. There is no ceiling. A reader who opens all 22 terms holds every parsed
payload at once, and the parsed form is several times the transferred size.

The question is not whether to cache but what the ceiling is. An LRU of two or three
concordances plus every small artefact would keep the property the cache was built for and
bound the rest.

**Needs a decision:** what a reader is assumed to be able to hold.

### 2.2 The concordance re-sorts 51,000 lines per keystroke

`filtered` is derived from every filter *and* the free-text query, so each character typed
re-filters and re-sorts the whole term. The sorts are the interesting ones — left and right
context are reversed-string comparisons over the full set — and none of that work survives
the next keystroke.

Debouncing the query alone would fix it without touching the other filters, which are
discrete and should stay immediate.

**Done when** typing in the search box does not re-sort until typing stops.

### 2.3 `ResizeObserver` calls `resize()` synchronously

`Chart.svelte` resizes the chart inside the observer callback. This is the shape that
produces "ResizeObserver loop completed with undelivered notifications" when a resize
changes layout that the observer then sees again. It has not been observed here — the plot
is a fixed-height box — but scheduling on `requestAnimationFrame` is the cheap guard, and
it also coalesces a drag-resize into one redraw per frame instead of one per event.

**Done when** a slow drag on the window edge redraws once a frame.

---

## 3 · The libraries

Checked against upstream documentation on 11 August 2026. The pinned versions are current:
ECharts 6.1.0, Svelte 5.56.8, SvelteKit 2.70.2, Vite 8.2.1, MapLibre `^6.2.0` resolving to
6.3.0.

### 3.1 `setStyle` should carry the speakers across, not re-add them

`CountryMap.svelte` handles a theme change by letting `setStyle` discard every source and
layer and re-adding them on `style.load`. That is what the library required before
`transformStyle`, which injects your source and layer into the incoming style *before* it is
applied. Adopting it removes the `style.load` handler, the `getLayer` re-entry guard in
`paint()`, and the blank frame between the two styles.

This one has to be seen rather than reasoned about: the failure mode of getting it wrong is
a map that looks right until the second toggle, which is exactly the bug the current comment
records having already been bitten by.

**Done when** toggling the theme three times leaves the circles and the click handling
intact, verified in a browser.

### 3.2 The worker handling is already right

`?worker&url` plus `setWorkerUrl`, with a comment explaining why plain `?url` fails. This
matches the v5-to-v6 migration guide almost sentence for sentence. Recorded here so a
future tidy-up does not simplify it back into the bug.

### 3.3 TypeScript 7 is out

The native compiler is published as `typescript@7`. It is a large change to the toolchain
for a benefit — compile speed — that this codebase does not currently feel: `svelte-check`
covers 4,090 files in well under a second. Worth revisiting when `svelte-check` and
`typescript-eslint` both declare support, not before.

---

## 4 · Not on this list

Two things a reader of the code might expect to find here, and why they are absent.

**The prose.** The comments in this repository are long, and several of them are longer than
the function they sit above. They are the design record — most of them say what was tried,
what broke, and why the current shape is the one that survived — and shortening them would
delete the only account of decisions that are not recoverable from the code. They are not
technical debt.

**The size of `07_topics.py` and `lib/topics.py`.** Together they are the largest thing in
the repository, and they are also the part `PLAN.md` §4 has explicitly not adopted. Splitting
a module nothing reads, to make it easier to change in a direction nobody has committed to,
is work spent against a decision that has not been taken. Revisit if and when the topic
layer enters the release.
