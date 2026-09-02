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
the two counting corrections it carries and the re-count it still owes. Amended 2 September
2026: the rate change-point test's meeting-block null and the Wilson intervals registered
below, with the re-calibration they owe; and, the same day, the lexical tables' floor,
effect ranking and dispersion, with the re-run and the lemma layer they owe. Amended 2
September 2026, later: the corpus run landed with the merge (deploy run 59 ran every step
through `15_usage.py` before `export_web.py` refused a hand-edited contract, corrected in
PR #6; run 61, on the push that followed, published the result); the re-count, the
re-calibration and the vocabulary
counts below are read from that run's console output, and what a log cannot show is left
open.

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

All 43 entries in `config/events.csv` now have a non-empty `source` and an HTTPS
`source_url` pointing to the relevant UN, ICC, ICJ, ICTY/ICTR, OHCHR or archived government
record. The config loader rejects missing source URLs, and the dashboard links directly to
them. These dates are contextual annotations only; the models do not use them and the
interface does not imply causal attribution.

**Open check: eight legal milestones added on 2 September 2026** (review §3.5, item 15):
Akayesu (1998-09-02), Krstić (2001-08-02), the Darfur Commission report S/2005/60
(dated 2005-02-01 as transmitted), *Bosnia v. Serbia* (2007-02-26), the first al-Bashir
warrant (2009-03-04), S/PV.7155 (2014-04-16, kind `council`), Karadžić (2016-03-24) and
Mladić (2017-11-22). Dates and labels were written from the review and from memory of the
judgments; each `source_url` is the tribunal's, the Court's or the UN's own page for the
case or document, and the date should be read off that page before any of these is cited
from the chart. The rail under the chronology draws them by kind, with a kind filter, in
place of the full-height rules.

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

**Re-count under v3, recorded 2 September 2026** from the console output of
`03_lexicon.py` on the corpus (deploy run 59, the first run of the merged tree).
`genocide` holds at 3,273 / 6,092. The seven terms of the v2 table, and the three others
the prefilter fix reaches:

| Term | v2 speeches / occurrences | v3 speeches / occurrences | Change |
|---|---:|---:|---|
| `genocide` | 3,273 / 6,092 | 3,273 / 6,092 | none |
| `war_crimes` | 4,326 / 6,241 | 4,664 / 6,588 | +338 / +347, the prefilter |
| `crimes_against_humanity` | 3,465 / 4,136 | 3,465 / 4,136 | none |
| `atrocity` | 4,244 / 6,120 | 4,244 / 6,120 | none |
| `mass_atrocity` | 573 / 733 | 624 / 784 | +51 / +51, the prefilter |
| `responsibility_to_protect` | 1,144 / 1,577 | 1,353 / 1,795 | +209 / +218, the prefilter |
| `icc` | 4,057 / 11,739 | 4,766 / 12,476 | +709 / +737, the prefilter |
| `never_again` | 287 / 320 | 305 / 338 | +18 / +18, the prefilter |
| `genocide_convention` | 92 / 110 | 135 / 153 | +43 / +43, the prefilter |
| `ethnic_cleansing` | 1,229 / 1,705 | 1,229 / 1,705 | none |

Every term whose v2 prefilter carried a space moved, and no other term did. Three of them
(`war_crimes`, `never_again`, `genocide_convention`) now reproduce the reconnaissance
figures of `docs/CORPUS.md` §8 exactly, which were measured over the raw texts with no
prefilter at all: 03 reports 9 of its 14 documented terms reproduced, where the v2 table
gives 6, and the five that still differ (`icc`, `atrocity`, `responsibility_to_protect`,
`mass_atrocity`, `holocaust`) differ because v2 changed what those patterns mean, as
recorded above. The `n_register_legal` delta nets −343 occurrences: −733 from no longer
counting `mass_atrocity` on top of `atrocity` (the v3 count the de-duplication removes is
784, which already holds the +51), +347 `war_crimes` and +43 `genocide_convention` from
the prefilter. The `has_` unions (atrocity core, active lexicon) move with `war_crimes`,
`mass_atrocity`, `responsibility_to_protect` and `icc`; 03 does not print them, and
`docs/CORPUS.md` §8 marks the two it quotes as v2 readings until they are read from the
artefact.

### The rate tests under a meeting-block null

Registered 2 September 2026 (roadmap S1, first slice; review §3.1, §3.3, §5.2). Two
changes to what the published series carry, neither of which moves a count:

- **The rate change-point p-values are calibrated by permuting meetings across years.**
  `lib/series.py::rate_change_point` used to simulate every no-change series by drawing each
  year's speeches independently at the pooled rate. Speeches are not independent: whether
  *genocide* can be said at all is fixed by the agenda of the debate, and S/PV.7155 alone
  holds 198 occurrences. The null now shuffles which meeting fell in which year, each year
  keeping its number of meetings and each meeting travelling with all of its speeches and
  hits, and repeats the search. The artefact names the null it used (`inference.null`), the
  number of blocks, and keeps the independent-speech p-value beside the block one
  (`p_value_independent`); `accepted` follows the block p. The partition, the two rates and
  their ratio are the same statistic as before and do not move.
- **Every speech rate carries Wilson 95% bounds** (`speech_rate_low`, `speech_rate_high`),
  from the one implementation in `lib/series.py::wilson_interval`, blanked exactly where the
  rate is withheld. They describe sampling width given the denominator; they do not correct
  for clustering, and the site says so.

On a synthetic 32-year corpus with two dense debates, the token-rate split read p = 0.015
under the independent null and 0.69 under the block null — the direction the review
predicted, on data built to show it.

**Re-calibrated on the corpus, 2 September 2026** (`04_series.py` and `11_countries.py`,
deploy run 59; 2,000 permutations, Bonferroni over the three planned tests):

| Test | Best split | Later / earlier rate | p, independent null | p, meeting-block null | Accepted |
|---|---|---:|---:|---:|---|
| `genocide` speech rate | 2017 | 0.71 | 0.0005 | 0.0010 | yes |
| `genocide` token rate | 2016 | 0.65 | 0.0005 | 0.0095 | yes |
| `atrocity_core` speech rate | 1996 | 0.71 | 0.0005 | 0.0255 | no |

The partitions and the ratios did not move, as the design says they cannot. The two
`genocide` splits survive the corrected threshold (0.05 / 3); the 1996 `atrocity_core`
split does not, and the site shows it as the best split rather than as a break. Under the
independent null all three sat at the floor of 2,000 draws; the block null lifts them by
two to fifty times, which is the size of the clustering the review predicted.
`README.md`'s change-point paragraph is rewritten from this artefact. The exploratory
raw-count breaks are unchanged in kind (`genocide` speeches 2013, occurrences 2014;
`atrocity_core` speeches 1999 and 2013, speech rate 1996, 2013 and 2017) and stay
labelled exploratory. 11 reports the same 133 speakers at or above 100 speeches over the
whole corpus and the same 96-speech threshold for an informative zero.

### Lexical tables: a floor, an effect ranking, and dispersion

Registered 2 September 2026 (roadmap S5, first slice; review §3.2). Four changes to what a
collocate or keyword row is:

- **G² is a floor.** A row must clear |G²| ≥ 10.83 (p < 0.001, one degree of freedom) to
  appear, and the rows that clear it are ranked by effect — log ratio for keyword tables,
  logDice for collocate tables, which now carry it. Tables used to be ranked by G², which
  on 59 million tokens puts the commonest words first however small their rate difference.
  Every table on the site and in the notes therefore re-orders on the next run of 05 and
  12; the words do not change, their order and their cut-off do.
- **Dispersion per row.** `documents`, distinct `meetings` and Gries's DP over the target
  speeches (keywords) or the windows (collocates), from `lib/lexical.py::dispersion` and
  its vectorised twin `DocumentTerms.dispersion`, held equal by a test.
- **The tokeniser.** `TOKEN_RE` cannot end on an apostrophe or hyphen and may carry a digit
  after its first letter. `'genocide'` in scare quotes was `genocide'`, a separate type,
  and `R2P` was `r` and `p`; both now count as the words they are. Every vocabulary count
  moves by the number of such tokens, which the re-run will state here.
- **Definitional edges.** `lexical.definitional_pairs` names every pair whose co-occurrence
  is written into the lexicon — nesting, or one term's regex matching another's declared
  example — and the network does not draw them. On the current lexicon the rule adds one
  pair the nesting rule missed: `genocide`–`denial`, because `denial`'s pattern contains
  `genocid`. `war_crimes`–`crimes_against_humanity` is not caught, and should not be.

**Re-run on the corpus, 2 September 2026, in part** (`05_lexical.py` and
`12_speaker_keyness.py`, deploy run 59). What the console output records: the surface
vocabulary is 58,904,180 tokens and 109,949 types over 106,302 speeches (25,184,530
document–type entries); `genocide`'s windows hold 60,050 (±5), 94,790 (±8) and 171,194
(±15) tokens over 6,092 occurrences, and every whole-corpus collocate table kept its 100
rows, so the floor did not shorten one; the matched control is unchanged at 3,104 of 3,273
(94.8%); the network draws 160 edges over 22 terms (32, 70, 126 and 88 in the four
periods); speaker keyness publishes 126 of 133 candidates, withholds 7 and never pairs
468.

**Open check: what the log cannot show.** The number of tokens the tokeniser change moved
(types ending on `'`, `’` or `-`, and tokens carrying a digit): the previous run's counts
were never committed and its log is out of this environment's reach, so the comparison
needs the pre-change commit re-run beside this one. The floor's effect on the shorter
sliced and per-speaker tables. The new top collocates against the old order: read them
from the published language page and set them beside the profile sentences in `README.md`
and `docs/CORPUS.md` §8.5. And the lemma layer (`data/interim/lemmas/lemmas.parquet`),
aligned token by token to the old pattern: `lemmas.tokens` will refuse it, and
`10_lemmatise.py` must run on the cluster before `05 --vocabulary lemma` is read again.

### Documents versus meeting symbols

The source distribution contains 6,595 document records but 6,582 distinct
`meeting_symbol` values. The web reader therefore exports 6,595 files; aggregate Council
statistics use 6,582 distinct symbols. Documentation and UI must name the relevant unit.
