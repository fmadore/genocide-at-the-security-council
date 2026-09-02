# Genocide at the Security Council

A corpus study of how the word **genocide** and its semantic neighbourhood have been used at
the UN Security Council: when, by whom, about what, and to what end. Built over the
**UN Security Council Debates** corpus (Schoenfeld et al., 1992–2023, 106,302 speeches) —
this repository is a study *of* that corpus, not a copy of it.

**Live: <https://fmadore.github.io/genocide-at-the-security-council/>** — rebuilt from the
Harvard Dataverse DOI by a workflow on every push, never uploaded from a workstation. This
repository holds the data pipeline, the analysis scripts and the web application.

The site is published; **no version is tagged**, because the human lexicon audit that the
first citable release is gated on has not been done. Read [Methods](https://fmadore.github.io/genocide-at-the-security-council/methods/)
before quoting a number from it.

Seven views, and every chart on them states what it answers, how to read its marks, what it
does **not** show, and which script produced the file behind it. A chart without that
account is a decoration. Every figure's numbers download as CSV with their provenance, and
every chart as SVG or PNG with its filters written into the image.

---

## Status

| Stage | State |
|---|---|
| Corpus documentation | ✅ [`docs/CORPUS.md`](docs/CORPUS.md) |
| Action plan | ✅ [`docs/PLAN.md`](docs/PLAN.md) |
| Targeted improvement roadmap | 🚧 [`docs/IMPROVEMENT_ROADMAP.md`](docs/IMPROVEMENT_ROADMAP.md) — adopted; I1–I3 and A1–A3 complete |
| Data pipeline — build & validate | ✅ `scripts/00`, `scripts/01` |
| Normalisation & country crosswalk | ✅ `scripts/02` · [`config/entities.csv`](config/entities.csv) |
| Lexicon flagging & precision audit | ✅ `scripts/03`; generated candidates are separate from durable annotations, **0 rows coded** |
| Temporal series & change points | ✅ `scripts/04` · [`config/events.csv`](config/events.csv) |
| Lexicometry — collocates, keyness, network | ✅ `scripts/05` · [`config/stopwords.txt`](config/stopwords.txt) |
| Concordance (75,373 lines, 28 terms) | ✅ `scripts/08`; a line is reachable by term, year, month, speaker and meeting |
| Grammatical frames of the node | ✅ `scripts/17` · [`scripts/lib/node_frames.py`](scripts/lib/node_frames.py); 17 constructions and a published residue over the 6,092 occurrences, with shares by period and speaker group and a cross-tabulation against both committed model runs |
| Month resolution — grid and pooled calendar | ✅ `scripts/04` → `series/monthly.json`; 331 of 384 months clear the 100-speech minimum, the other 53 are drawn as withheld |
| Download beside every figure | ✅ [`web/src/lib/export.ts`](web/src/lib/export.ts): the artefact's numbers as CSV with provenance, the picture as SVG or PNG with its filters drawn into it |
| Speech export & web payload | ✅ `scripts/09`, `scripts/export_web.py` |
| Dashboard — 7 views, SvelteKit 2 / Svelte 5 | ✅ [`web/`](web/); Pages rebuilds the 491 MB payload from v6.1 |
| Per-speaker table | ✅ `scripts/11`; 133 of 601 speakers clear the 100-speech minimum, the rest carry null rates |
| Membership composition per speaker | ✅ `scripts/11` → `standing`, drawn by [`Standing.svelte`](web/src/lib/Standing.svelte); 105 speakers spoke both from a seat and from outside one |
| Licence & citation metadata | ✅ [MIT](LICENSE) + [CC BY 4.0](LICENSE-DATA.md), [`CITATION.cff`](CITATION.cff) confirmed |
| Public deployment | ✅ [live](https://fmadore.github.io/genocide-at-the-security-council/); Pages source is GitHub Actions, payload rebuilt from the DOI each run |
| First citable release | ⬜ untagged — gated on the §1.1 audit, **0 of 200 rows verdicted** |
| Speech embeddings | ✅ `scripts/06` on a GPU cluster ([`docs/CLUSTER.md`](docs/CLUSTER.md)); **not read by the dashboard** |
| Topic comparison & its evaluation | ✅ `scripts/07` — evidence for a decision, not a result; adoption still deferred |
| Lemma layer & lemma lexicometry | ✅ `scripts/10`, `scripts/05 --vocabulary lemma`; built, **not adopted** — see Phase 6 |
| Actor view — ranking, locator map, concordance links | ✅ `web/src/routes/actors/`, with the membership composition and the per-speaker keyness [`docs/PLAN.md`](docs/PLAN.md) §3 asks for, each as its own figure rather than as shading on the ranking |
| Model-assisted usage layer | 🧪 experimental — Phase L in [`docs/IMPROVEMENT_ROADMAP.md`](docs/IMPROVEMENT_ROADMAP.md): `scripts/13–15`, committed runs under [`model_annotations/`](model_annotations/), the `/usage` view with its actor × referent matrix, stance profiles and per-referent diffusion chronology; human gold sample is the authority, **0 of 688 occurrences coded** |

The three ✅ rows that say "not adopted" are not a backlog. They are built, run and
documented so the decision to use them can rest on evidence; [`docs/PLAN.md`](docs/PLAN.md)
records what each would have to pass first. Nothing in `web/` reads any of them.

---

## Quick start

Requires **Python 3.12 (x64)** — on Windows, the installation that has a `pyarrow` wheel.

```bash
python -m pip install --require-hashes -r requirements.lock
```

```bash
make payload      # the whole pipeline, from the fetch to the exported payload
make -n payload   # what would run, in what order, without running it
```

The [`Makefile`](Makefile) is the pipeline's graph: one target per step, keyed on the file
the step writes and declared against every input it reads, so an edited config or script
rebuilds what it invalidates and nothing more. The deploy workflow runs the same target.
What `make payload` runs, in order:

```text
00_fetch_data.py       ~500 MB from Harvard Dataverse into data/raw/ (no network once it
                       is there: config/dataset-pin.json carries Harvard's MD5s, so a
                       present corpus verifies offline)
01_build_parquet.py    → data/derived/speeches.parquet (131 MB), meetings.parquet
02_normalise.py        → speeches_norm.parquet    (aliases, entities, groups)
03_lexicon.py          → speeches_flagged.parquet (lexicon counts)
04_series.py           → derived/series/*.json    (rates, intervals, change points)
05_lexical.py          → derived/lexical/*.json   (collocates, keyness, PMI)
08_kwic.py             → derived/kwic/*.json      (75,373 concordance lines)
09_export_speeches.py  → web/static/data/speeches (6,595 document files)
11_countries.py        → derived/countries/*.json (per-speaker denominators)
12_speaker_keyness.py  → derived/countries/       (per-speaker matched keyness)
13_gold_sample.py      → data/interim/            (the genocide gold sample, deterministic)
15_usage.py            → derived/usage/*.json     (model-assisted usage layer, from the
                                                   committed run named in model_annotations/)
17_frames.py           → derived/frames/*.json    (the constructions the node appears in,
                                                   crossed with both committed runs)
export_web.py          → web/static/data          (assembles and checks the payload)
```

Then the dashboard:

```bash
npm --prefix web ci && npm --prefix web run dev
```

Each step asserts its output and exits non-zero on any mismatch rather than leaving a
plausible-looking artefact behind. A clean `01` reports:

```
106,302 speeches | 6,595 documents | 6,582 meeting symbols | 66,392,703 tokens
```

Everything downstream reads the parquet and never touches the raw files again.
Findings notes land in `notes/`; see [`scripts/README.md`](scripts/README.md) for the
module layout.

Steps **06**, **07** and **10** are missing from that list on purpose. They need the extra
dependencies in `requirements-cluster.txt` — and, for 06, a GPU — and they run on the
University of Bayreuth cluster; [`docs/CLUSTER.md`](docs/CLUSTER.md) is the walkthrough. 06
encodes the corpus; 07 runs the topic-model comparison that [`docs/PLAN.md`](docs/PLAN.md)
§4 requires before a topic model may be believed; 10 builds a lemma layer that an optional
re-run of 05 can count instead of surface forms. None of the three is part of the release:
`export_web.py` does not read their output, and the dashboard does not know it exists.

Steps **13** and **14** are also missing, for a different reason. 13 draws the human gold
sample for the model-assisted usage layer and only needs rerunning when the sample design
changes; 14 is the one step that costs money — it sends every `genocide` occurrence to a
commercial model and commits the run under [`model_annotations/`](model_annotations/), so
it is run by hand, never by CI or the deploy. [`scripts/README.md`](scripts/README.md)
carries the run book.

```bash
python -m pytest
```

The Python suite needs no production data and includes integrity checks on the hand-edited
files in `config/`. The dashboard has its own focused suite over the modules that decide
what a figure may draw. Both suites, `ruff check`, and the dashboard's `prettier` /
`eslint` / `svelte-check` run on every push and pull request via
[`.github/workflows/checks.yml`](.github/workflows/checks.yml), so a bad edit to a config
file fails in CI rather than halfway through someone's pipeline run.

New analytical JSON artefacts also carry `meta.analysis_hash`: a SHA-256 identity computed
from canonical analytical content and declared inputs/configuration. Regeneration time and
Git dirtiness are deliberately excluded, while the readable timestamp and commit remain
alongside it for operational provenance.

The two halves are joined by one more thing.
[`tests/contract/payload.json`](tests/contract/payload.json) records the *shape* of every
artefact the dashboard fetches — keys, nesting and the type at each leaf, 32 kB standing in
for 491 MB — because that shape was previously written three times, in two languages, with
nothing comparing them: a renamed field passed `pytest`, passed `svelte-check`, and was
found by looking at an empty figure. `export_web.py` now refuses to publish a payload that
has drifted from it, and the dashboard's own suite checks that every field it fetches for
is one the pipeline actually writes.

---

## Layout

```
├── .github/workflows/   checks.yml (pipeline + dashboard) · deploy.yml (Pages)
├── config/              Versioned analysis inputs — edit these, not the scripts
│   ├── lexicon.yml           Genocide lexicon: patterns, tiers, discursive registers
│   ├── lexicon.lock.json     Digest of every pattern beside its pattern_since; tools/lock_lexicon.py
│   ├── embedding_models.yml  Encoders for step 06, and why each one is on the list
│   ├── entities.csv          country_org → type · ISO3 · UN group · centroid
│   ├── country_aliases.csv   Labels denoting the same speaker
│   ├── council_membership.csv  P5 and E10 terms, 1992-2023
│   ├── stopwords.txt         Function words only — the file argues for the boundary
│   └── events.csv            35 primary-sourced reference dates for the chart overlay
├── data/                Gitignored. Rebuilt from the DOI by scripts/00 and 01.
│   ├── raw/               As downloaded from Dataverse — never modified
│   ├── interim/           Intermediate artefacts, reference downloads, audit samples
│   └── derived/           speeches.parquet, the flagged table, series/, lexical/, kwic/
├── docs/
│   ├── CORPUS.md          Corpus documentation: variables, traps, first findings
│   ├── PLAN.md            Phases 0-7, and the gate each one has to pass
│   ├── CLUSTER.md         Running the GPU steps on the Bayreuth cluster
│   ├── VALIDATION.md      Readings to confirm against the original S/PV PDFs
│   └── reference/         Codebook PDF, companion paper
├── notes/               Gitignored. Markdown findings notes emitted by each script.
├── scripts/             Numbered, idempotent pipeline steps — see scripts/README.md
│   ├── lib/               The tested modules the steps orchestrate
│   └── cluster/           Slurm harness for the GPU steps — see docs/CLUSTER.md
├── tests/               pytest; runs against the real config/, needs no data
│   └── contract/          The shape the dashboard is written against, checked at export
├── tools/               One-off maintenance helpers (entity crosswalk, map boundaries)
└── web/                 SvelteKit dashboard — src/routes is one file per view
    ├── static/data/       Gitignored. 491 MB, built by scripts/09 and export_web.py
    └── static/geo/        Committed. Country polygons for the filled map, from tools/
```

---

## The corpus

| | |
|---|---|
| **Source** | Schoenfeld, Eckhard, Patz, van Meegdenburg & Pires — [doi:10.7910/DVN/KGVSYH](https://doi.org/10.7910/DVN/KGVSYH), v6.1 |
| **Licence** | **CC0 1.0** — public domain |
| **Coverage** | 1992-01-06 → 2023-12-30 · 106,302 speeches · 6,595 documents / 6,582 meeting symbols · 58.9 M words in the speech bodies (66.4 M codebook tokens) |
| **Paper** | [arXiv:1906.10969](https://arxiv.org/abs/1906.10969) |

The raw distribution has two undocumented defects that silently corrupt a naive read — a
UTF-8/cp1252 encoding trap and 36 rows split by a literal newline. Both are handled in
`scripts/01_build_parquet.py`; see [`docs/CORPUS.md` §5](docs/CORPUS.md) for the details.

### Why this corpus, for this question

`genocid*` appears in **3,273 speeches (3.08%)**, 6,092 occurrences. Three findings from
the first pass frame the project:

- **The 2014 peak exceeds 1994 in absolute volume** (659 vs 228 occurrences) while
  remaining lower in density. The word has a second life after 2013, driven by
  heterogeneous uses — Ukraine, Yazidis, commemorations, R2P — rather than by one crisis.
- **Two usage regimes among speakers**: states carrying a genocide memory (Rwanda 26.8%,
  Armenia 28.2%, Bosnia 13.9%) and norm-entrepreneur states (Liechtenstein 21.2%,
  Slovenia, Costa Rica). Russia sits at 0.84% across 5,101 speeches.
- **The word is thematic before it is situational**: it circulates mainly in debates on
  tribunals (29.1%), protection of civilians and the rule of law. Israel/Palestine (1.45%)
  and Syria (0.51%) — the corpus's two largest files — are among the poorest.

Full results in [`docs/CORPUS.md` §8](docs/CORPUS.md).

### What normalisation added

Three things the pipeline established that were not visible in the raw distribution:

- **A non-English delivery language is explicit for 42,765 speeches (40.2%)**, read off the
  `(spoke in French)` / `(interpretation from Arabic)` markers in the form of address and
  resolved against a closed 26-language vocabulary. French (14,603), Spanish (12,287),
  Arabic (6,157), Russian (5,015) and Chinese (4,500) dominate, with a long tail down to
  single speeches in Hindi, Nepalese and Vietnamese. This gives the translation caveat in
  [`docs/CORPUS.md` §10.4](docs/CORPUS.md) a measurable denominator for the first time.
- **The E10 out-speaks the P5 two to one** — 52,276 speeches against 25,813, with
  non-member states at 21,018, the UN system at 4,861 and non-state speakers at 2,334.
  Membership is resolved per year, so Rwanda counts as elected in 1994-1995 and 2013-2014
  and as a non-member elsewhere.
- **The OCR-tolerant pattern adds exactly one speech.** Across all 106,302 records,
  `gen[eo]cid|senocid|qenocid` finds a single occurrence that `genocid*` misses
  (`genecide`, S/PV.3137, 1992). The headline count is robust; the case is logged in
  [`docs/VALIDATION.md`](docs/VALIDATION.md) to be checked against the printed record.

Lexicon v2 makes each pattern auditable with declared examples and literal candidate
filters, fixes singular/plural matching for `atrocity` and `mass atrocity`, and validates
all 22 concordances against the annotation table. The generated counts supersede the
earlier reconnaissance table; the differences are recorded in
[`docs/VALIDATION.md`](docs/VALIDATION.md). Lexicon v3 (1 September 2026) changes no
pattern: it fixes the prefilter that dropped a phrase broken across a line and stops
counting a nested term twice in its register. On the corpus that moved six terms — `war
crimes` from 4,326 to 4,664 speeches, `ICC` from 4,057 to 4,766 — and left `genocide` at
3,273 speeches and 6,092 occurrences; the re-count is in the same file.

Lexicon v4 (2 September 2026) does change patterns — but not the one that matters most.
It gives `genocidaires` — an actor label for the ex-FAR and Interahamwe — its own term and
publishes the headline as a derived measure, `genocide_qualification` = `genocide` minus
`genocidaires`, 6,061 occurrences across 3,268 speeches. `genocide` itself keeps
`\bgenocid\w*` untouched, so every occurrence identity, the gold sample and the four
committed model runs stand and `15` goes on aggregating them; the day a v4 run exists,
narrowing the pattern reproduces the derived figures exactly. It adds a sentence **anchor**: seven terms are now counted
only where the sentence holding them also says `genocid*`, because the commemorative
register as built was tracking the anniversary of resolution 1325 and the survivors of
sexual violence rather than genocide memory. It adds `massacre`, `mass killing`, `ICJ`,
`intent to destroy` and `incitement`, gives the Residual Mechanism back to `tribunals`,
and stops `holocaust` counting the nuclear kind. Every figure it moves was measured on
the corpus before it was committed and is tabulated in
[`docs/VALIDATION.md`](docs/VALIDATION.md), including the argument for deriving the
headline rather than narrowing the pattern.

Since the same day, a rate *per 100,000 words* divides by words. It used to divide by the
codebook's `tokens` column — quanteda's count over the full text, punctuation and numbers
included, 66,392,703 against the 58,904,180 words the corpus actually holds — so every
published rate stood 11.3% below the label it carried.

### What the 2014 peak turns out to be

The first finding above — *the 2014 peak exceeds 1994 in absolute volume* — does not
survive normalisation, and `scripts/04` is where that gets settled rather than argued.

The primary inferential layer scans one annual two-rate partition with the denominator intact:
binomial likelihood for speech prevalence and Poisson likelihood for occurrences with
word exposure. Two thousand no-change series repeat the complete breakpoint search, with
Bonferroni correction across the three planned rate tests. Since 2 September 2026 those
series are built by permuting whole meetings across years rather than treating every
speech as an independent draw — one debate can hold two hundred occurrences — and the
p-value under the older independent-speech null is published beside the block one, so the
size of that clustering is a number on the page. The three planned tests run on the
published headline, `genocide_qualification` — the word minus its *génocidaires* actor
label — and on the atrocity-core union. The strongest partitions start in 2017 for the
headline's speech prevalence (later/earlier rate ratio 0.71; p = 0.0005 under both nulls),
2016 for its rate per 100,000 words (0.65; p = 0.0095 under the meeting-block null against
0.0005), and 1996 for atrocity-core speech prevalence (0.72; p = 0.0255 against 0.0005).
The two headline splits clear the corrected threshold; the 1996 atrocity-core split does
not, and the site marks it as the best split rather than as a break. The re-calibration is
recorded in [`docs/VALIDATION.md`](docs/VALIDATION.md), under “The rate tests under a
meeting-block null”. Rejecting a constant rate does not prove an
abrupt historical break: smooth trends and Poisson overdispersion remain limitations. Every
share of speeches on the site carries its Wilson 95% interval. The raw-count breaks and wild
binary segmentation remain visible as explicitly exploratory descriptions.

### The same word, doing different work

`scripts/05` profiles what `genocide` travels with — over a stated function-word stoplist,
with log-likelihood as a floor a row must clear and never as its rank, because on 59
million tokens significance is cheap and effect size is not. Rows are ranked by effect
(logDice for collocates, log ratio for keywords) and each carries its dispersion — the
speeches and meetings it appears in, and Gries's DP — so one debate's word is not read as
the register's.

Almost every speaker's strongest collocates are the Rome Statute triad: `crimes`,
`humanity`, `war`. **Rwanda's are not.** Across its 187 genocide-bearing speeches the
profile is `tutsi`, `denial`, `ideology`, `convicts`, `fdlr`, `fugitives` — a register of
accountability and denial rather than of legal qualification. Bosnia's is a third thing
again: `srebrenica`, `cleansing`, `aggression`.

The vocabulary also turns over in time. In 1992–1999 the word sits among `aggression`,
`punishment`, `acts`; by 2020–2023 among `denial`, `glorification`, `criminals`. It moves
from qualifying an event to contesting a memory of one. These profiles were read from
tables ranked by G²; since 2 September 2026 the tables rank by logDice above the floor, and
the words named here are to be re-read from the language page — an open check in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

`scripts/17` asks the same question of the word itself rather than of its neighbours: what
construction is it in when it is said? Every one of the 6,092 occurrences is filed under one
of seventeen frames or an `unframed` residue, from a ±90-character window. **Nearly a
quarter of them — 1,446, 23.7% — are the catalogue**, the word as one item of *genocide, war
crimes and crimes against humanity*, and that share doubled from 12.4% before 2002 to 26.6%
after. The constructions in which a speaker actually applies the label to an event —
*constitutes genocide*, *genocide occurred*, *genocide against the Tutsi* — are 366 between
them, 6.0%; explicit refusal, the scare-quoted and *so-called* uses, is 78, 1.3%. A fifth of
the occurrences match no pattern and are published as a category rather than absorbed.

The frames are read off the text with no model involved, which makes them a free check on
the model-assisted layer. Both committed runs agree with the codebook where it is least
ambiguous — the Special Adviser's title is a neutral legal reference in 176 of 176
occurrences in both — and disagree with each other exactly where §4.2 of the review said
they would: the 78 distancing occurrences are modally *attributes* for one model and
*rejects* for the other. [`docs/VALIDATION.md`](docs/VALIDATION.md) carries the full
cross-tabulation.

Keyness is measured with true target/control pairs matched on year × agenda item × speaker
group — 3,104 of 3,273 targets found a partner (94.8%), and the 100 short strata are listed
rather than back-filled. Twenty consecutive seeds quantify sampling sensitivity. The
unmatched comparison ships alongside it, not as a result but
as the thing the matching is meant to improve on: read word by word, the median of the top
fifteen unmatched keywords falls by 1.69 on the log2 scale — a factor of 3.2 in rate — once
the occasion is held constant. `bosnia`, `herzegovina` and `tribunals` drop out entirely;
`genocide`, `humanity` and `rwandan` survive.

---

## Citation

The corpus:

> Schoenfeld, M., Eckhard, S., Patz, R., van Meegdenburg, H., & Pires, A. (2019).
> *The UN Security Council Debates* [Data set]. Harvard Dataverse, V6.1.
> <https://doi.org/10.7910/DVN/KGVSYH>

This repository:

> Madore, F. (2026). *UN Security Council Debates — genocide discourse dashboard*.
> University of Bayreuth. <https://github.com/fmadore/genocide-at-the-security-council>
> ORCID [0000-0003-0959-2092](https://orcid.org/0000-0003-0959-2092)

Machine-readable metadata is in [`CITATION.cff`](CITATION.cff). Cite both: a derived table
is worth nothing without the record it came from.

**Acknowledgements.** Joël Glasman (University of Bayreuth) prompted the model-assisted
usage layer — the actor-by-referent question, the asserted-versus-rejected distinction and
the diffusion question (when each delegation first adopted or refused the word for each
case) are his — and is the second coder (`JG`) of its gold sample.

**No version is tagged yet, and citing an untagged state cites a moving target.** The first
citable release is gated on the human lexicon audit in
[`docs/PLAN.md` §1.1](docs/PLAN.md#11-human-lexicon-audit) — 0 of 200 sampled rows currently
carry a verdict, so no false-positive rate has been measured for any figure here.

---

## Licence

Three layers, three licences:

| Layer | Licence |
|---|---|
| Source corpus (Harvard Dataverse v6.1) | CC0 1.0, by its depositors |
| Code — `scripts/`, `web/`, `tests/`, `tools/`, `config/` | [MIT](LICENSE) |
| Derived artefacts — `data/derived/`, `notes/`, the dashboard's figures and tables | [CC BY 4.0](LICENSE-DATA.md) |

The middle row is the ordinary one. The third exists because a derived table is this
project's contribution rather than the United Nations', and reuse of it should carry the
attribution that lets a reader find the record behind the number. Verbatim speech text
extracted from a derived artefact remains CC0 — see [`LICENSE-DATA.md`](LICENSE-DATA.md).
