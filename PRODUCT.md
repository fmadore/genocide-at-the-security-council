# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary visitor is a researcher, a social scientist or historian, who
arrives with a claim about how the word *genocide* is used at the United Nations
Security Council and wants to test it against the record. They read at a desk,
usually on a laptop, often with a paper or a draft open beside the browser. The
job ends when they can cite a figure, a number, or a passage with its meeting
symbol, or when they have found that the claim does not hold.

Other audiences (students, journalists, peer reviewers of the study) use the
same paths and are served by the same design; none of them has been confirmed
as a separate audience with separate needs.

## Product Purpose

A corpus study of the word *genocide* and its semantic neighbourhood in Security
Council debates, 1946 to 2024: when it is invoked, by whom, about what, and with
which discursive function. The site publishes the study's figures and lets the
visitor open every count onto the speeches behind it. Success is a visitor who
leaves with a citable figure or passage and a correct understanding of what that
figure does and does not show.

## Positioning

Every number is traceable to the record. Each figure names the script and the
data file that produced it, every count opens onto the matching passages, and
the marked word is the link between the chart and the transcript. A neighbouring
project could publish the same corpus; it could not truthfully claim that each
of its numbers can be walked back to a meeting symbol and a script.

## Operating Context

- The record is Sakamoto & Matsuoka, *The UNSC Meetings and Speeches*, v5.0
  (Harvard Dataverse, CC0), pinned by checksum. One corpus for the whole span;
  no splice in 1992.
- A deterministic Python pipeline (`Makefile`, `scripts/00_*` to `export_web.py`)
  writes static JSON; the site (`web/`, SvelteKit with `adapter-static`) has no
  backend. It is served from GitHub Pages under the subpath
  `/genocide-at-the-security-council/`.
- Figures are cited in papers: they are downloaded as CSV, SVG and PNG, and the
  pages are printed. Meeting symbols such as `S/PV.3137` are the primary keys a
  reader carries away.
- A reading scope (the word, the vocabulary, the debate) is set once in the
  masthead and governs Chronology, Actors, Concordance and the Reader.
- A basket collects passages across pages for later citation; it lives in the
  browser only.
- Some layers are model-assisted (the Usage page, the Semantic map). Their
  provenance (computed, mixed, model) is labelled on every page and figure and
  is an analytical claim, not a style.

## Capabilities and Constraints

- Nine surfaces: Overview, Chronology, Words in context, Actors, Concordance,
  Reader (one meeting), Usage, Semantic map, Methods.
- Every figure must state its question, how to read it, what it does not show,
  and its source; `web/src/lib/Figure.svelte` enforces this structurally and
  `web/scripts/word-budget.mjs` enforces the word budgets in CI.
- The data registers (legal, preventive, commemorative, contentious,
  accountability, descriptive) are an analytical classification and need a
  colour layer of their own; that layer must never be confused with
  interaction colour.
- Light and dark themes are both first-class; chart colours are read from the
  CSS tokens at runtime (`web/src/lib/theme.ts`).
- Terminology is fixed by the study: *occurrence*, *speech*, *meeting*,
  *reading set*, *register*, *keyness*, *change point*. The site's copy is not
  to be edited under design work.
- A service worker serves pages and data offline after first visit.
- Explicitly undecided: whether students or journalists will get orientation
  of their own.

## Brand Commitments

- The name is *Genocide at the Security Council*, and the wordmark sets
  *Genocide* as a `<mark>`: the marked word is the site's one gesture at its own
  scale and must survive any redesign.
- The footer credit stays as written: Frédérick Madore (University of Bayreuth),
  the corpus citation, MIT for code, CC BY 4.0 for figures and tables, CC0 for
  quoted speech.
- Figures must print and export cleanly for papers.
- Author's judgement recorded 14 September 2026: the current look reads as
  generic AI output and is to be replaced, not polished. Figures, tables and
  maps must use the full page width.

## Evidence on Hand

- The corpus and every derived table under `data/` (gitignored payload of
  491 MB built by the pipeline; `web/e2e/fixtures/` holds tiny committed
  fixtures for browser tests).
- `docs/CORPUS.md` (schema and limitations), `docs/VALIDATION.md` (human audit
  and verification record), `docs/PLAN.md` (research contract and release gates).
- The Claude Design project "The Verbatim Record", the origin of the incumbent
  visual system; not readable from this workspace until `/design-login` runs or
  its files are exported.
- No photography, no illustration, no logo beyond the wordmark. Nothing of that
  kind is to be fabricated.

## Product Principles

1. A number without its passage is not evidence; every count opens onto the record.
2. Provenance is shown, never implied: computed, mixed and model are labelled where the number is.
3. The interface recedes behind the record; the marked word is the interface.
4. What a figure does not show is stated beside it, not hidden behind a toggle.
5. Anything a researcher takes away (a figure, a table, a citation) must survive the trip: print, export, and a meeting symbol that resolves.

## Accessibility & Inclusion

WCAG 2.2 AA is the floor and is enforced by axe checks in the Playwright suite
on every CI run. Keyboard paths through figures, full-screen mode and the basket
are tested. Colour is never the only code for a register or a provenance kind.
