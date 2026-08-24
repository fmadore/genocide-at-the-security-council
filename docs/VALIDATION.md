# Validation register

The corpus is OCR-derived from two-column `S/PV.*` verbatim records. This register keeps
approximations, human-review tasks and resolved discrepancies visible instead of silently
absorbing them into the pipeline.

Status: 11 August 2026 — every count below re-checked against the current artefacts on that
date; the open human checks are unchanged, because none of them is work a re-run can do.
“Mechanically reconciled” means code and source metadata agree; it does not mean a person
has inspected the original PDF.

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
[`annotations/lexicon/referents.csv`](../annotations/lexicon/referents.csv). The initial
list contains only reserved values; named cases and entities should be added through the
shared pilot before scored coding begins. Coding describes discourse and does not decide
whether an underlying event legally constitutes genocide.

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

### Documents versus meeting symbols

The source distribution contains 6,595 document records but 6,582 distinct
`meeting_symbol` values. The web reader therefore exports 6,595 files; aggregate Council
statistics use 6,582 distinct symbols. Documentation and UI must name the relevant unit.
