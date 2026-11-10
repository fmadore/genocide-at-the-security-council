# Data sheet: the derived dataset

This sheet describes the data this project derives from the Sakamoto and Matsuoka
corpus: what it is, how it was made, what it may and may not be used for, and what
each field in the main tables means. It follows the questions of Gebru et al.,
"Datasheets for Datasets" (2021). For the source corpus itself, see
[CORPUS.md](CORPUS.md); for the status of each published figure, see
[CLAIMS.md](CLAIMS.md).

Figures below describe the state of 2 November 2026: corpus v6.0, lexicon v8.

## Contents

1. Motivation
2. Composition
3. Collection
4. Processing
5. Uses and misuses
6. Ethics
7. Distribution and licence
8. Maintenance
9. Field dictionary

## 1. Motivation

The dataset exists to study how the word *genocide* and its neighbouring
vocabulary are used in the public meetings of the UN Security Council from 1946
to 2026: when the word is said, by whom, about which situations, and to what end.
It was built by Frédérick Madore (University of Bayreuth) for a historical study
and a public website, "Genocide at the Security Council". The model-annotation
runs used the Bayreuth Centre for High Performance Computing; see
[CLUSTER.md](CLUSTER.md#acknowledgement).

## 2. Composition

**Unit.** The basic unit is one speech in a formal meeting, as segmented by the
source. The analysis adds a finer unit: one **occurrence**, a single match of a
lexicon term in a speech.

**Size.**

| | |
|---|---|
| Speeches | 182,684 |
| Meetings with speeches | 9,919 |
| Analytical words | 92,547,139 |
| Lexicon terms counted | 28 (lexicon v8) |
| Occurrences of `g[eé]nocid*` | 8,611, in 4,576 speeches |

The committed count of every term is in
[`config/lexicon.counts.json`](../config/lexicon.counts.json).

**Layers.** The dataset has three layers that must not be confused:

- **Computed** layers, produced by fixed rules from the text: lexicon counts,
  annual, quarterly and monthly series, the concordance, collocations and
  keyness, grammatical frames, actor tables.
- A **model-derived** layer: labels a language model assigned to each occurrence
  of *genocide* (verdict, position, referent and so on). The published run
  covers every occurrence but is unvalidated (see [model_annotations/README.md](../model_annotations/README.md)).
- An **experimental** semantic map built from text embeddings.

**What is missing.**

- Speech outside formal meetings: informal consultations leave no verbatim
  record. Of 10,636 meeting records, 717 carry no speeches.
- The language actually spoken: the text is the English record, and for speakers
  of other languages it is a UN translation.
- Words damaged by scanning, which are not counted: every count is a minimum.
- Seven of the 4,576 speeches carrying `g[eé]nocid*` have no labels from the
  comparison model run, documented in [VALIDATION.md](VALIDATION.md) §7. The
  published run labels all of them.

The full list of limitations is in [CORPUS.md](CORPUS.md#limitations-that-must-remain-visible).

## 3. Collection

The project collects nothing itself. It reads two files from the source dataset:

> Sakamoto, T., & Matsuoka, T. (2023). *The UNSC Meetings and Speeches*
> (Version 6.0) [Data set]. Harvard Dataverse.
> <https://doi.org/10.7910/DVN/CKPTRB> (CC0 1.0).

`speeches.tsv` holds the speech transcripts and their metadata; `meetings.tsv`
holds one row per meeting record. The source's authors converted the UN's
verbatim records (`S/PV` documents) to plain text and segmented them into
speeches; how they did so is described in their documentation and in Sakamoto,
Matsuoka and Ito (2026), *Journal of Peace Research*,
[doi:10.1093/jopres/xjag018](https://doi.org/10.1093/jopres/xjag018).

The files are pinned by Dataverse file identifier, size and MD5 checksum in
[`config/dataset-pin.json`](../config/dataset-pin.json), and the fetch step
refuses any file that does not match.

## 4. Processing

The numbered steps in [`scripts/`](../scripts/README.md) run in the order the
`Makefile` declares. In short:

1. **Adapt** (step 01): the two TSV files become one table per speech, without
   changing the speech text. Source columns keep a `source_` prefix.
2. **Normalise** (step 02): words are counted once by one rule (`words`), and each
   speech gets its speaker category (`entity_type`) and Council status
   (`speaker_group`) from the source's own flags.
3. **Apply the lexicon** (step 03): every term's pattern in
   [`config/lexicon.yml`](../config/lexicon.yml) is matched against each speech
   body, after the opening form of address. Counts must equal the committed ones.
4. **Build the tables** (steps 04, 05, 08, 09, 11, 12, 17, 20): series,
   collocations and keyness, the concordance, the meeting reader files, actor
   tables, grammatical frames and annual actor tables.
5. **Model labels** (steps 14 and 15): a pinned open-weights model labels each
   occurrence on university hardware (step 14, never run by the public build);
   step 15 joins a committed run to the corpus and aggregates it.
6. **Export** (`export_web.py`): assembles and validates the files the website
   reads.

Every step writes a manifest recording its inputs, their checksums, the software
versions and an `analysis_hash` of its result. No step edits the speech text, and
no model output overwrites a count or a human annotation.

## 5. Uses and misuses

**Suitable uses.**

- Finding and reading passages: every count links to the concordance line and
  the speech it comes from.
- Describing change in the recorded use of the word over time, with the stated
  denominators and intervals.
- Comparing vocabularies between periods or speaker groups, as exploration that
  leads back to close reading.

**Uses the data do not support.**

- Treating a count as the number of times something was said: counts are
  minimums of words in the English record.
- Reading a delegation's recorded words as a timeless national position, or as
  the view of a government, a leader or a person. The source's state label does
  not identify any of these.
- Treating a model label as a finding. Until the gold sample is coded, no model
  label is validated, and agreement between two models measures stability, not
  accuracy.
- Ranking delegations by the language of speakers who used other languages,
  without allowing for translation.
- Inferring intent, legal responsibility or whether events constituted genocide.
  The dataset records vocabulary, not legal determinations.
- Reading distance on the semantic map as diplomatic alignment.

## 6. Ethics

The speakers are public officials speaking in office, in a public forum whose
record the UN publishes. Their names appear as the source gives them. The project
adds no personal information and does not attempt to identify individuals beyond
the source's speaker field.

Labels about named states are interpretations, not findings. A model label such
as "rejects" or "own state accused" attached to a delegation is a reading of one
passage by one instrument, not yet checked by a person. The website marks these
figures as model-derived and experimental, and the evaluation plan
([EVALUATION_PLAN.md](EVALUATION_PLAN.md)) sets the conditions under which they
may be shown with stronger claims. A user who quotes such a figure about a named
state should quote its status with it.

## 7. Distribution and licence

- **Where:** the website,
  <https://fmadore.github.io/genocide-at-the-security-council/>, ships the
  derived files and offers CSV downloads of each figure. The code and committed
  annotations are on GitHub. A citable release is not yet published;
  [RELEASING.md](RELEASING.md) describes it.
- **Licence:** derived artefacts and the project's prose are CC BY 4.0; the code
  is MIT; the speech text stays CC0 in whatever form it reaches you
  ([LICENSE-DATA.md](../LICENSE-DATA.md)).
- **Citation:** cite this project ([CITATION.cff](../CITATION.cff)) and the
  source corpus.

## 8. Maintenance

The project is maintained by its author. The website is rebuilt from the pinned
corpus on every change to `main`. Corrections can be proposed through the GitHub
repository. A
change of lexicon pattern, corpus version or model run changes the derived data;
each is versioned (lexicon version, dataset pin, run identifier) and recorded in
every manifest, and [VALIDATION.md](VALIDATION.md) logs the checks made. Older
derived data are not kept online; a citable release will be the way to keep a
fixed copy.

## 9. Field dictionary

The website's data files sit under the site's `data/` folder. The tables below
cover the files a reader is most likely to download or cite. Arrays in the JSON
series files run parallel to `periods`.

### 9.1 Concordance lines: `kwic/<term>.json` and its CSV download

One line per occurrence of one term (`kwic/genocide.json` holds the 8,611 of
*genocide*). Written by step 08 (`scripts/lib/kwic.py`).

| JSON field | CSV column | Meaning |
|---|---|---|
| `id` | `id` | Line identifier: speech identifier, `#`, the occurrence's ordinal in the speech (`SC07155-01-007#3`). The ordinal depends on the lexicon version. |
| `spv` | `spv` | Meeting record symbol (`S/PV.7155`). |
| `date` | `date` | Date of the speech (the meeting's date), `YYYY-MM-DD`. |
| `country` | `country` | Speaker's affiliation (`country_org`): the source's Correlates of War name for states where it has one, otherwise the source's affiliation label. |
| `iso3` | — | ISO 3166 alpha-3 code from the optional geography lookup; empty where none. Never used to aggregate. |
| `group` | `group` | Status at the time of the speech: `P5`, `E10`, `Non-member state`, `UN` or `Non-state`, from the source's flags. |
| `type` | `participant_type` | Speaking capacity derived from the source's flags: `Council member`, `UN official`, `Council President`, `Procedural` or `Guest`. |
| `agenda` | `agenda` | The meeting's topic as the source gives it, or its agenda where no topic is given. |
| `start`, `end` | — | Character offsets of the match in the whole speech text (end exclusive). |
| `left`, `right` | — | Up to 150 characters of context either side, line breaks flattened. |
| `kw` | `keyword` | The matched text. |
| `sent` | `sentence` | The full sentence holding the match. |

The file's other keys: `term`, `pattern` (the regular expression), `register` and
`tier` (labels that group terms on the site; not measures), `count`, `id_format`
and `meta`.

### 9.2 Model labels per occurrence: `usage/occurrences.json`

One row per occurrence of *genocide* that the published run labelled. Written by
step 15. **Model-derived and unvalidated.** The label vocabularies are defined in
[the codebook](../annotations/lexicon/CODEBOOK.md); `not_applicable` marks a field
that does not apply, as for a false positive.

| Field | Meaning |
|---|---|
| `id` | Line identifier, as in the concordance; joins the two. |
| `occurrence_id` | Checksum identity of the occurrence: SHA-256 over the speech file, the term, the offsets in the speech body, the matched text and a checksum of the body. Does not change when the lexicon adds a form elsewhere; joins to the gold sample. |
| `verdict` | `true_positive`, `false_positive` or `uncertain`: is the match a use of the word? |
| `quotation` | Whether the word is the speaker's own (`not_quoted`), quoted, or reported. |
| `concrete_case` | Whether the word is applied to a determinate case (`yes`, `no`, `unclear`). |
| `speaker_position` | What the speaker does with the characterisation: `asserts`, `rejects`, `conditional`, `reports_without_position`, `no_position`, `unclear`. |
| `function` | One or more rhetorical functions, joined by `|`. |
| `referent` | The situation meant, as an identifier from `annotations/lexicon/referents.csv`. |
| `proposed_referent` | The model's free-text proposal where `referent` is `other`. |
| `referent_source` | Where the referent was found: `passage`, `speech`, `header`. |
| `accused_actor`, `victim_group` | Free text, as the passage names them; empty if it names none. |
| `victim_group_grouped` | The group `annotations/lexicon/victim_groups.csv` counts `victim_group` under, so spellings of one people count together; empty where the table lists no group. Not yet checked by a person (`docs/VALIDATION.md`, check 6b). |
| `own_state_accused` | Whether the speaker's own state or organisation is the one accused. |
| `salience` | `passing` or `substantive`. |
| `evidence_quote` | The passage the model quoted in support. |
| `evidence_valid` | Whether that quote was found in the speech. Rows with `false` are left out of every discourse figure. |
| `rationale` | The model's one-sentence reason. |
| `contested` | Fields a comparison run labelled differently; empty when there is no comparison run. |
| `alt` | The comparison run's labels where it differed; otherwise null. |

The `meta` block names the run, model, prompt version and file, schema and
referent versions, and states whether the run is partial (`allow_partial`) and how
many occurrences it covers (`occurrences_annotated` of `occurrences_total`).

### 9.3 Annual series: `series/annual.json` and the CSV "The word list over time"

One value per year, 1946–2026, for every term. Written by step 04
(`scripts/lib/series.py`). `series/quarterly.json` has the same shape by quarter.

| JSON field | CSV column | Meaning |
|---|---|---|
| `periods` | `period` | The year. |
| `corpus.speeches` | `corpus_speeches` | Speeches held that year: the denominator of a speech rate. |
| `corpus.words` | `corpus_tokens` | Analytical words that year: the denominator of a word rate. Despite its CSV name, this column holds words. |
| `corpus.meetings` | — | Meetings with speeches that year. |
| (term name) | `measure` | The lexicon term. |
| — | `kind` | Always `term` (aggregate measures were withdrawn in lexicon v5). |
| `terms.*.register` | `register` | Shelf label grouping the term on the site; not a measure. |
| `terms.*.speeches` | `speeches` | Speeches containing the term at least once. |
| `terms.*.speech_rate` | `speech_rate` | Share of that year's speeches containing the term, from 0 to 1. |
| `terms.*.speech_rate_low`, `_high` | `speech_rate_wilson95_low`, `_high` | Wilson 95% interval, treating speeches as independent. |
| `terms.*.speech_rate_cluster_low`, `_high` | `speech_rate_meeting95_low`, `_high` | 95% interval from resampling whole meetings (`cluster_interval` gives the method, number of resamples, seed and unit). Wider where a year's use rests on a few debates. |
| `terms.*.occurrences` | `occurrences` | Number of occurrences. |
| `terms.*.token_rate` | `token_rate_per_100k` | Occurrences per 100,000 analytical words. |
| `terms.*.tier` | — | How central the term is to the study: `core`, `atrocity` or `adjacent`. Documentation, not a measure. |
| `sufficient` | — | Whether the period holds at least `minimum_speeches` speeches. |
| `minimum_speeches` | — | 125: the speeches a period needs before its rates are published. |
| `record.first_date`, `record.last_date` | — | The first and last speech date in the corpus (1946-01-17 and 2026-06-23), so a part-year can be read as one. |

Counts are always written. Below the minimum every rate of the period is null —
both intervals and `token_rate` included, and the comparison population's
rates too; only 1959 (86 speeches) is withheld. `series/quarterly.json` is a
complete grid from the first quarter of the record to the last: 322 quarters,
8 of them without a speech (written as zeros), 275 at or above the minimum.

`corpora.genocide_free_atrocity` is a comparison population: speeches that use
*ethnic cleansing*, *crimes against humanity* or *war crimes* and do not use
`genocid*`, with its own counts, rates and Wilson bounds.

`series/monthly.json` follows the same rule on a year x month grid of whole
years. Its `record` adds `first_period` and `last_period`, the first and last
months with speeches, and `coverage.months_outside_record` counts grid months
outside them (6: July to December 2026), which are unrecorded rather than
months the Council did not meet. `series/breakdowns.json` applies the same
`minimum_speeches` to each cell (a year's speeches from one group): each row
carries `sufficient`, and its rates are null when `held` is below the minimum.

### 9.4 Annual actor table: `actor_year/actor_year.csv`

One row per source affiliation, year and measure (currently `genocide`). Written
by step 20 (`scripts/lib/actors.py`).

| Column | Meaning |
|---|---|
| `country_org` | Source affiliation, as in the concordance. Historical affiliations stay distinct. |
| `year`, `measure` | The year and the term. |
| `held` | All speeches by this affiliation that year: the denominator. |
| `words` | Analytical words in those speeches. |
| `tokens` | The source's own word count for those speeches (it differs slightly from `words`). |
| `meetings` | Meetings in which the affiliation spoke. |
| `speeches`, `occurrences` | Speeches containing the term, and its occurrences. |
| `speech_rate`, `speech_rate_low`, `speech_rate_high` | Share of the affiliation's speeches containing the term, with Wilson 95% bounds (speech-level, not meeting-clustered). |
| `token_rate` | Occurrences per 100,000 words. |
| `sufficient` | Whether `held` reaches the minimum of 125 speeches; rates are empty when it does not. |
| `withheld_reason` | Why a rate is empty: `no speeches` or `below minimum`; empty when the rate is published. |

### 9.5 Who stays silent: the `silence` block of `countries/countries.json`

Per speaker (`rows`) and per period (`periods`), how often a speaker used the
word in meetings where another speaker had used it. Written by step 11
(`scripts/lib/actors.py`). Procedural turns by the presidency are left out.

| Field | Meaning |
|---|---|
| `exposed` | Meetings in which the speaker gave a substantive speech and another speaker used the word. |
| `joined` | Those of them in which the speaker used it too. |
| `share`, `share_low`, `share_high` | `joined / exposed`, with Wilson 95% bounds; null below `minimum_meetings` (30). |
| `exposed_after` | Meetings in which the speaker gave a substantive speech *after* another speaker's first use of the word, in the source's speaking order. |
| `joined_after` | Those of them in which one of the speaker's later speeches used the word. |
| `share_after`, `_low`, `_high`, `sufficient_after` | The same ratio and bounds on the ordered counts, with their own minimum flag. |
| `room_share`, `room_share_after` | Per period: joined over exposed for all speakers together, on each reading. |
| `speakers_at_minimum`, `speakers_at_minimum_after` | Per period: speakers with a share on each reading. |

`rule` and `rule_after` state the two readings in words. The first counts a
meeting even when the speaker had finished before anyone else used the word;
the second does not. Across the corpus 20,296 of 30,752 exposed attendances
meet the ordered test, and the room's share is 13.4% on it against 11.3%.

### 9.6 Provenance: the `meta` block and the CSV header

Every JSON file carries a `meta` block: the script that wrote it, when
(`generated`), the pipeline commit (`git_commit`), the lexicon version, the input
and configuration files with their sizes and SHA-256 checksums, the Python and
package versions, and `analysis_hash`, a checksum of the file's content that
ignores the timestamp and commit. Two files with the same `analysis_hash` hold the
same analysis.

The 9,919 meeting files under `speeches/` share one such block, which is written
once, in `meetings.json`. Each keeps the script, `generated`, `git_commit`, the
lexicon version and its `analysis_hash`, and a `provenance` field naming
`meetings.json`. Its `analysis_hash` is taken with the shared block in place, so
it changes when an input or configuration does, as every other file's does.

Every CSV download begins with comment lines starting `#` (read as comments by
pandas and R): the site, the figure, the artifact and the script that wrote it,
the lexicon version, the analysis hash, the commit, the inputs and
configurations with their checksums, the filters on screen, which rows the file
holds, and the licence.
