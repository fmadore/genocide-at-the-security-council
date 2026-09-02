# Validation register

The corpus is OCR-derived from two-column `S/PV.*` verbatim records. This register keeps
approximations, human-review tasks and resolved discrepancies visible instead of silently
absorbing them into the pipeline.

Status: 11 August 2026 — every count below re-checked against the current artefacts on that
date; the open human checks are unchanged, because none of them is work a re-run can do.
“Mechanically reconciled” means code and source metadata agree; it does not mean a person
has inspected the original PDF. Amended 28 August 2026: checks 6 and 7 added for Phase L
(the genocide gold sample and the model-run register), and check 2 updated for the seeded
referent list. Amended 30 August 2026: the first two model runs registered in §7. Amended 1 September 2026: lexicon v3 registered below, with
the two counting corrections it carries and the re-count it still owes.

## How to inspect an original record

Records are addressed by `meeting_symbol` (`S/PV.3137`). Resumptions carry a corpus suffix
such as `S/PV.3745Resumption1`, rendered by the UN as `S/PV.3745 (Resumption 1)`.

- UN Digital Library: <https://digitallibrary.un.org/search?ln=en&p=S%2FPV.3137>
- Security Council records index: <https://research.un.org/en/docs/sc/quick/meetings/>

The `filename` identifies the speech (`UNSC_1992_SPV.3137_spch0009.txt` is the ninth
speech record in that document).

## Open human checks

### 1. OCR variant of `genocid*` — one case

The disabled tolerant pattern (`gen[eo]cid|senocid|qenocid`) finds one speech not covered
by the headline `genocid*` pattern:

| Record | Date | Speaker | Corpus reading |
|---|---|---|---|
| `S/PV.3137` | 1992-11-16 | Bosnia and Herzegovina | `…ethnic cleansing and genecide in Bosnia…` |

Check whether the printed record reads “genocide.” The headline count remains 3,273
speeches either way because the tolerant pattern is reported separately.

### 2. Human lexicon audit — three sampling frames

`data/interim/lexicon_audit_candidates.csv` combines three deterministic occurrence-level
samples, also written as separate probability, coverage and high-recall-negative CSV files.
The probability sample supports an overall precision estimate; the unequal-probability
coverage sample spans term × period strata for diagnosis; the negative sample inspects
declared disabled patterns for possible misses and is not, by itself, a corpus-wide recall
estimate. Every row records its frame size, selection probability, sampling weight, seed and
frame/sample hashes.

Human work is stored separately in the versioned `annotations/lexicon/annotations.csv`; the
pipeline joins both into the generated `data/interim/lexicon_audit_review.csv` and never
writes the annotation file. Reviewers must follow
[`annotations/lexicon/CODEBOOK.md`](../annotations/lexicon/CODEBOOK.md), which separates:

- match `verdict` from quotation, `stance`, rhetorical `function`, and controlled `referent`;
- source consultation from the evidence span and coding confidence;
- administrative coder, date, schema, and lexicon versions.

The controlled referent identifiers live in
[`annotations/lexicon/referents.csv`](../annotations/lexicon/referents.csv). The list was
seeded on 28 August 2026 (codebook v2.1) with 29 identifiers — cases invoked before the
Council, historical memory cases, meta-referents and the three reserved values — and grows
only through reviewed diffs; both coders must review it before scored coding or a model
run. Coding describes discourse and does not decide whether an underlying event legally
constitutes genocide.

Report precision separately for the core term and extended lexicon, with denominators and
uncertain cases. Any regex change invalidates the verdicts for that term and requires a new
lexicon version.

### 3. Approximate delivery-language readings — 27 forms

Explicit `(spoke in French)` / `(interpretation from Arabic)` markers recover a
non-English language for 42,765 speeches (40.2%). Twenty-seven damaged forms require the
closed-vocabulary corrections below:

| Printed | Read as | Speeches |
|---|---|---:|
| `inArabic`, `fromArabic` | Arabic | 8 |
| `inFrench`, `Prench`, `Frenci.`, `Frerch`, `Fcench`, `F reach` | French | 8 |
| `inRussian`, `Russiar`, `Rassian` | Russian | 4 |
| `inSpanish`, `..anish`, `Spam'sh` | Spanish | 3 |
| `Chiness`, `Cht'nese`, `Ch[nese` | Chinese | 3 |
| `Acabic` | Arabic | 1 |

Missing in-person markers are labelled `English (inferred, in-person)`. Missing markers
for 5,072 VTC speeches are `Unknown (VTC)`, because the VTC format does not carry the same
evidence. Priority: low; inspect the 27 explicit repairs if language-based claims become a
publication focus.

### 4. No opening form of address — 5,172 speeches

These records open directly into prose and are treated as continuations without trimming.
Sample about twenty against the source PDF. If some are segmentation failures, their
speaker attribution is weaker even though lexical counts remain intact. Priority: medium.

### 5. Repaired rows in `S/PV.5225` — 36 speeches

A literal newline inside `agenda_item3` splits 36 TSV records. The parser rejoins records by
the exact column count; row count and total tokens then match the codebook. Confirm in the
source that the agenda is *The Role of the Security Council in Humanitarian Crises* and the
document contains 36 corpus speech records. Priority: low.

### 6. Genocide gold sample — 0 of 200 rows coded

`scripts/13_gold_sample.py` draws 200 candidates over 195 distinct `genocide` occurrences:
120 by equal probability, 80 by coverage over decade × usage-cue strata (rejection,
quotation, commemorative, dense meeting, plain — the cue is a sampling stratum, never a
label). Candidates and the review join are generated files under `data/interim/`; human
work lives only in the versioned
[`annotations/genocide/annotations.csv`](../annotations/genocide/annotations.csv), coded by
`FM` and `JG` under the codebook's two-coder protocol — the full sample double-coded, a
shared pilot outside the scored sample first, adjudication preserving both original rows.
`scripts/15_usage.py` computes and publishes the agreement; nothing is hand-typed into an
artefact. Priority: high — the `/usage` view reports its model layer as unvalidated until
this is done.

### 7. Model annotation runs

Every run of `scripts/14_llm_annotate.py` and of its counter-instrument
`scripts/16_llm_annotate_gemini.py` is committed under
[`model_annotations/genocide/runs/`](../model_annotations/genocide/) with its manifest —
model id, prompt version and hash, coverage, parse failures, invalid evidence quotes and
token usage — and the run the dashboard reads is named in `current_run.txt` as a reviewed
diff. Register of runs:

| Run | Model | Prompt | Coverage | Parse failures | Evidence invalid |
|---|---|---|---|---:|---:|
| `2026-08-30-luna-pilot` | `gpt-5.6-luna`, effort high | v1 `a44fdbb59321` | 50 speeches, 91 of 91 pilot occurrences | 0 | 0 |
| `2026-08-30-luna-v1` | `gpt-5.6-luna`, effort high | v1 `a44fdbb59321` | 6,092 of 6,092 occurrences, 3,273 of 3,273 speeches | 0 | 15 |
| `2026-08-31-gemini-pilot` | `gemini-3.7-flash`, thinking high | v1 `a44fdbb59321` | 50 speeches, 91 of 91 pilot occurrences | 0 | 0 |
| `2026-08-31-gemini-v1` | `gemini-3.7-flash`, thinking high | v1 `a44fdbb59321` | 6,092 of 6,092 occurrences, 3,273 of 3,273 speeches | 0 | 3 |

`2026-08-30-luna-v1` is the run `current_run.txt` publishes. Its 15 unlocated evidence
quotes (0.25%) are flagged `evidence_valid=false` in the run and excluded from every
discourse figure; nothing was repaired. The pilot covers the first 50 genocide-bearing
speeches in corpus order and is kept for comparison, not published.

`2026-08-31-gemini-pilot` is the counter-instrument's pilot over that same first 50
speeches, so the two pilots enumerate one population: all 91 occurrence ids join, and
every one of the 91 evidence quotes was located as an exact substring of its speech.
Per-field observed agreement against `2026-08-30-luna-pilot` is verdict 91/91,
quotation 86/91, referent 86/91, stance 81/91, function 69/91 by set equality. This is
stability across instruments and not accuracy; the gold sample remains the only
calibration. No Gemini run is published: `comparison_run.txt` is still empty.

`2026-08-31-gemini-v1` is the counter-instrument over the whole corpus. It annotates the
same 6,092 occurrences as `2026-08-30-luna-v1` — every occurrence id is present in both
runs and in neither alone — with the byte-identical prompt, so the two are comparable
rather than merely similar. Three evidence quotes could not be located (0.05%, against
luna's 15) and are flagged rather than repaired. One speech, `UNSC_2022_SPV.9062_spch0012`,
was first refused for `MAX_TOKENS` and succeeded on a live retry; `failures.jsonl` keeps
that record.

Observed agreement between the two runs, over all 6,092 occurrences:

| Field | Agreement | Cohen's kappa |
|---|---:|---:|
| `verdict` | 99.9% | 0.000 |
| `quotation` | 90.2% | 0.615 |
| `referent` | 87.6% | 0.853 |
| `stance` | 81.2% | 0.688 |
| `function` (set equality) | 69.9% | — |

3,068 occurrences (50.4%) are contested on at least one field. The `verdict` kappa of 0.000
is an artefact of the metric and not a disagreement: both instruments call almost every
occurrence a true positive, so there is nearly no variance for kappa to normalise against,
and the 99.9% raw agreement is the figure that means anything. Quote it with that caveat or
not at all.

The whole table measures stability across two instruments and never accuracy. Both models
can be confidently wrong together, and the human gold sample — still 0 of 200 coded —
remains the only calibration either run has.

When a run is added, record it here and re-check the artefact counts on the Methods page
against its manifest. Automatic resolutions (a relocated evidence quote, a normalised
whitespace match) are counted in the manifest, never silently absorbed.

## Mechanically reconciled

### Primary-source chronology overlay

All 35 entries in `config/events.csv` now have a non-empty `source` and an HTTPS
`source_url` pointing to the relevant UN, ICC, ICJ, OHCHR or archived government record.
The config loader rejects missing source URLs, and the dashboard links directly to them.
These dates are contextual annotations only; the models do not use them and the interface
does not imply causal attribution.

### Lexicon v2 replaces reconnaissance counts

The earlier prose treated a mixture of primary phrases, acronyms and buggy singular/plural
patterns as one comparable set. Lexicon v2 fixes `atrocity/atrocities` and `mass
atrocity/atrocities`, declares examples and candidate literals, and treats the generated
concordance as the count authority. Current exact counts are:

| Term | Speeches | Occurrences |
|---|---:|---:|
| `genocide` | 3,273 | 6,092 |
| `war_crimes` | 4,326 | 6,241 |
| `crimes_against_humanity` | 3,465 | 4,136 |
| `atrocity` | 4,244 | 6,120 |
| `mass_atrocity` | 573 | 733 |
| `responsibility_to_protect` | 1,144 | 1,577 |
| `icc` | 4,057 | 11,739 |

`scripts/08_kwic.py` independently fails unless every one of the 22 term files reproduces
the occurrence count in `speeches_flagged.parquet`; all 22 currently agree. Differences
from old narrative counts are documented changes, not silently forced “reproductions.”

### Lexicon v3 corrects the fast path and the roll-ups

Lexicon v3 (1 September 2026) changes **no pattern**. Two corrections to how the patterns
are applied move counts, and the table above is the v2 reading they are to be compared
against:

- **A phrase broken across a line was never counted.** `Term.count` runs a pattern only on
  speeches containing one of its literal `prefilters`. The v2 literals for multi-word terms
  carried a space (`war crime`, `mass atroc`, `responsibility to protect`, `genocide
  convention`, `prevention of genocide`, `early warning`, `never again`, `international
  criminal court`), which a record's hard line break defeats while the pattern's `\s+` does
  not, so such occurrences were dropped before the regex ran. v3 makes every prefilter a
  whitespace-free literal contained in every string its pattern can match, the loader
  refuses a literal with whitespace, and `tests/test_config.py` checks the fast path
  against the bare regex over wrapped and indented examples. `08_kwic.py`'s reconciliation
  could not catch this: it compares two outputs of the same filter.
- **A nested term was counted twice in its register.** `mass_atrocity` is declared nested
  under `atrocity` and both are register `legal`, so every *mass atrocity* added two to
  `n_register_legal`, the count behind the legal register's occurrence series and token
  rate; `n_lexicon_total` double-counted all four nested pairs. v3 sums a roll-up over
  `lexicon.summable`, which drops a term whose declared parent is in the same sum. The
  `has_` flags, and so every speech rate, are unchanged. Two alternatives inside nested
  patterns (`convention on the prevention and punishment`, `special adviser on the
  prevention`) do not sit inside a parent match, so the roll-ups now understate those few
  mentions rather than inflating them; the direction is chosen, and recorded in the
  helper's docstring.

Every term carries `pattern_since: 2`, the version in which its pattern last changed.
`scripts/15_usage.py` and the annotation merge in `lib/audit.py` read a committed run's or a
coded row's `lexicon_version` against that field rather than against the lexicon's version,
so the gold sample and the two model runs registered in §7, made against v2, remain valid:
`genocide` enumerates exactly the occurrences it did (its pattern `\bgenocid\w*` and
literal `genocid` are untouched), and its row in the table above must not move. The claim
is held honest by `config/lexicon.lock.json`, which records each pattern's SHA-256 beside
its `pattern_since`: `lexicon.load()` refuses a pattern edited without its bump, so the
forgetting fails at 03 and in CI rather than validating artefacts cut from a regex the file
no longer holds. `python tools/lock_lexicon.py` rewrites the lock.

**Open check: re-count under v3.** The size of the first gap is unmeasured until
`03_lexicon.py` runs on the corpus. Record the v3 counts for the seven terms in the v2 table
beside the v2 ones and confirm `genocide` at 3,273 / 6,092. Record the `n_register_legal`
delta as two components with opposite signs: the de-duplication removes exactly the v3
`mass_atrocity` count (733 under v2, and v3 can only raise it), while the prefilter fix adds
to `war_crimes`, `mass_atrocity` and `genocide_convention`, all three in the same register.
The net delta therefore has no sign known in advance, and neither component is bounded by
the other.

### Documents versus meeting symbols

The source distribution contains 6,595 document records but 6,582 distinct
`meeting_symbol` values. The web reader therefore exports 6,595 files; aggregate Council
statistics use 6,582 distinct symbols. Documentation and UI must name the relevant unit.
