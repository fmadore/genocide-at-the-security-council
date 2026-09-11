# Dashboard copy review — 11 September 2026

The dashboard remains in English. This revision addresses social science researchers who need to interpret the findings without prior training in computational text analysis.

## Coverage

Reviewed the nine views: overview, chronology, words in context, actors, concordance, usage, similar speeches, methods and the meeting reader. The review also covers shared figure explanations, table headings, controls, tooltips, exports, saved passages, loading messages and error messages. All 24 figure definitions retain the site's limits on explanation length.

## Main changes

| Area | Editorial changes and checks against the implementation |
| --- | --- |
| Overview and chronology | Separate occurrence counts, speech shares and rates per 100,000 words. Explain pooled denominators, small samples and change-point tests. An unaccepted split means insufficient evidence under the test, not proof of constant usage. Monthly explanations follow the selected unit. |
| Words in context | Explain nearby words, comparison frequencies, G², log ratio, logDice and dispersion. Distinguish ranking from plotted coordinates. Describe the network as the displayed matrix. Replace technical phrase-pattern labels with readable names and explanations that acknowledge negation and attribution. |
| Actors | Define affiliation and Council membership groups. Explain thresholds and comparison populations. Counts describe recorded speech, not diplomatic influence or commitment. |
| Concordance and reader | Explain the scope of search results and selected reading sets. Clarify local browser storage, export contents, language metadata and recovery from missing records. |
| Usage | Describe automatic labels as model classifications. Separate assigned mentions from eligible passages. Explain human reference coding, model agreement and evaluation metrics. Remove obsolete fixed totals and explicitly handle a release with no classifications. |
| Similar speeches | Explain embeddings as numerical representations of text, cosine scores as similarity rather than percentages of agreement, and the distortions of a two-dimensional map. Clarify filters, neighbours and validation diagnostics. |
| Methods | Reorganise the explanation around research questions and interpretation. Retain technical names and a pipeline ledger for reproducibility, including the semantic map and neighbour index. Explain uncertainty and limitations alongside the relevant measures. |

The measure formerly described as “genocide as an event qualification” is now labelled “genocide (excluding génocidaires)”. The calculation removes a word form; it does not classify whether a speaker has qualified an event as genocide. The overview's link to the raw-word concordance now uses the corresponding raw-word count.

Corpus quotations, classification instructions, analytic identifiers and source data remain unchanged. Display explanations of phrase patterns are maintained separately from the exported codebook. No statistical model or analytical calculation was changed.

## Verification

The browser review used the current local data on all nine views at widths of 390, 720 and 1,440 pixels. It found no document-level horizontal overflow, broken in-page links or browser exceptions. Desktop and mobile screenshots were inspected, including figure explanations. Dense charts retain their existing table alternatives.

Existing unit and browser test expectations were updated where they assert the revised visible wording or accessible control names.

- Formatting, ESLint, figure provenance and all 24 figure word budgets: passed.
- Svelte check: zero errors and zero warnings.
- Unit tests: 543 passed across 26 files.
- Production build: passed; 13 static entry points and four manifest icons verified. Vite retains its bundle-size warning.
- Browser inspection with current data: all nine views checked at three widths, with no browser exceptions or broken in-page links.
- Browser regression suite: all 45 tests passed locally after the CI follow-up. The initial review was limited by Vite server-start timeouts; CI subsequently exposed two remaining stale disclosure assertions in one Usage-page test. Both assertions now match the revised wording, and the disclosure handles “1 column” correctly. Formatting, lint and Svelte checks were rerun successfully before the follow-up commit.
- Service-worker browser test: passed locally on port 5184 after the default-port attempt timed out. The test verifies that a visited reader remains usable offline.

This is an editorial and implementation-consistency review, not a new validation study of the models or corpus.
