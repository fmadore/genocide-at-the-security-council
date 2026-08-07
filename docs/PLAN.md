# Action plan — "Genocide at the Security Council" dashboard

Target: an interactive dashboard over the UNSC Debates corpus (1992-2023), centred on how
the word **genocide** and its semantic neighbourhood have been used — when, by whom, about
what, to what end.

Read `README.md` first: it holds the corpus documentation, the data traps, and the first
scan results this plan builds on.

---

## 0. Guiding principles

1. **Normalise everything.** The corpus grows ×7.4 over the period. Any raw count is a
   measure of corpus growth, not of discourse. Every series ships with a rate
   (per speech, per 100k tokens) as the *default* view; raw counts are opt-in.
2. **Every number is clickable.** No aggregate is a dead end: a bar, a country, a year, a
   topic all lead to concordance lines and then to the full speech. This is the difference
   between a dashboard and a poster.
3. **Static-first.** No backend, no database server. Precomputed artefacts + static hosting.
   Cheap, archivable, citable, and it survives the end of any grant.
4. **The lexicon is a hypothesis, not a ground truth.** `genocid*` matches 3.08% of speeches;
   what counts as "discussing genocide" is a separate, harder question. The LLM layer exists
   to interrogate that gap, not to paper over it.
5. **Nothing is a black box.** Every derived artefact is produced by a versioned script from
   the parquet, with parameters recorded in the output. Topic models and LLM extractions
   included.

---

## 1. Architecture

### 1.1 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | **SvelteKit 2 / Svelte 5** (runes) | Static adapter, familiar from IwacSearch |
| Charts | **Apache ECharts 6** | Handles 100k-point scatter, time series, sankey, graph, treemap in one library |
| Maps | **MapLibre GL 6** | Two genuinely mappable dimensions (§4.4) |
| Ad-hoc querying | **DuckDB-WASM** (optional, phase 4) | "Power query" tab over the parquet; note the npm `latest` tag currently points at a dev build — pin a stable release explicitly |
| Build | Vite 8 | |
| Data prep | **Python 3.12 x64** (`C:/Users/frede/AppData/Local/Programs/Python/Python312/python.exe`) | The one with `pyarrow` |

*Versions checked upstream on 2026-08-07. Re-verify before pinning.*

Python packages to add: `scikit-learn`, `spacy` (+ `en_core_web_sm`), `umap-learn`,
`sentence-transformers`, `bertopic`, `anthropic`.

### 1.2 Data flow

```
Harvard Dataverse (doi:10.7910/DVN/KGVSYH, CC0)
        │  scripts/00_fetch_data.py
        ▼
data/raw/{speaker.tsv, meta.tsv, speeches.tar}
        │  scripts/01_build_parquet.py   (done — repairs, joins, validates)
        ▼
data/derived/speeches.parquet  (106,302 × 29, 131 MB)  ← single source of truth
data/derived/meetings.parquet  (6,595 × 9)
        │  scripts/02..08  (normalise, lexicon, series, topics, embeddings, KWIC)
        ▼
web/static/data/*.json           ← precomputed artefacts, ~15-25 MB total
web/static/data/speeches/*.json  ← 6,595 per-meeting files, fetched on demand
        │  SvelteKit build → .github/workflows/deploy.yml
        ▼
GitHub Pages (public at launch)
```

Nothing under `data/` is committed. The repository is self-bootstrapping: a fresh clone
plus `scripts/00` and `scripts/01` reproduces the canonical parquet from the DOI.

**Why per-meeting JSON files rather than one big blob:** the full text is 389 MB — too much
to ship to the browser, and too fragmented at 106,302 individual files for a static host.
Bundling by meeting gives 6,595 files averaging 59 KB: one fetch opens a full session with
all its speeches, which is exactly the unit a reader wants when they click a concordance
line.

---

## 2. Phase 1 — Data preparation

**Status: substantially done during reconnaissance.** `01_build_parquet.py` exists and
validates clean (106,302 rows, 0 missing texts, 0 orphans).

Remaining work:

### 2.1 `scripts/02_normalise.py`

- [ ] Merge `country_org` aliases (§5.3 of the README) via an explicit, version-controlled
      mapping file — not a fuzzy matcher. Around a dozen pairs; auditable by hand.
- [ ] Normalise case on `agenda_item2/3/4` and `participanttype` (`The PRESIDENT` → `The President`).
- [ ] Build **`config/entities.csv`**: one row per distinct `country_org`, with
      `iso3` · `entity_type` (state / IGO / UN agency / NGO / civil society / academia /
      company / other) · `lat` · `lon` · `un_regional_group`.
      ~195 states can be matched automatically against an ISO list; the ~435 remaining
      entities need manual typing. Budget half a day. **This is the single most
      labour-intensive prep task and it gates the map.**
      *Confirmed in scope: all countries will be mapped.* Since the crosswalk is a
      hand-checked artefact rather than a computed one, it lives in `config/` under
      version control, and the script that consumes it must fail loudly on any
      `country_org` value it has never seen — otherwise new data silently drops off the
      map.
- [ ] Strip the opening form of address from each text into a `text_body` column, keeping
      the raw text for display. Regex on the segmentation pattern the authors used.
- [ ] Flag P5 / E10 / non-member / UN / non-state per speech, per year (Council membership
      changes annually — needs an E10 roster table by year).

### 2.2 `scripts/03_lexicon.py`

- [ ] Formalise the lexicon as a versioned YAML file: term → regex → register
      (legal / preventive / commemorative / contentious / adjacent).
- [ ] Add OCR-tolerant variants (`gen[eo]cid`, `s[eg]nocide`) and measure how many extra
      matches they yield — report the number, don't silently absorb it.
- [ ] Emit per-speech boolean + count columns for each term into `speeches_flagged.parquet`.
- [ ] **Sanity audit**: hand-check a random 100 matches for false positives (e.g. "genocide"
      inside a quoted resolution title, or a treaty name). Report a precision estimate in
      the README.

---

## 3. Phase 2 — Computational analysis

Each script writes both a JSON artefact for the dashboard and a Markdown findings note for
the team.

### 3.1 `04_series.py` — temporal

- Counts and rates per year / per quarter, per term, per register.
- Breakdowns crossed with: `agenda_item1`, `agenda_item_manual`, `participanttype`,
  P5/E10/guest, `entity_type`.
- **Change-point detection** on the normalised series (`ruptures` or a simple binary
  segmentation) to date the regime shifts empirically rather than by eye.
- Event overlay table: a hand-curated list of ~30 reference dates (Rwanda 1994, Srebrenica
  1995, Rome Statute 1998, World Summit/R2P 2005, Darfur ICC referral 2005, Syria 2011,
  ISIS/Yazidis 2014, Crimea 2014, Myanmar 2017, Ukraine 2022, Gaza 2023) to annotate the
  chart.

### 3.2 `05_lexical.py` — lexicometry

- **Collocates** by log-likelihood at several windows (±5, ±8, ±15), sliced by period and
  by speaker group. The collocate profile of Rwanda vs Russia vs Liechtenstein is likely a
  headline result.
- **Keyness**: which words distinguish genocide-bearing speeches from a matched control
  set (same year, same agenda item, same speaker type)? Matching matters — an unmatched
  comparison just recovers "these are speeches about Rwanda".
- **Word clouds** — requested, and worth shipping, but scoped honestly: they go in as a
  *secondary* rendering of the collocate/keyness tables, never as the primary evidence.
  A cloud sorted by log-likelihood with a stated stoplist is defensible; a raw-frequency
  cloud is not.
- **Co-occurrence network** of the 14 lexicon terms (ECharts graph layout), edge weight =
  pointwise mutual information, sliceable by decade. This should make the Rome Statute
  triad and the R2P quartet visible as structure.

### 3.3 `06_topics.py` — topic modelling

Two models, deliberately:

| Model | Scope | Purpose |
|---|---|---|
| **LDA / NMF** (scikit-learn) | The 3,273 genocide speeches | Fast, deterministic, interpretable, easy to describe in a paper. k swept 8-30, coherence-scored. |
| **BERTopic** (sentence-transformers + UMAP + HDBSCAN) | Same subset, plus the 7,936 atrocity-core set | Better semantic clusters, gives the embedding needed for the semantic map |

Deliverables: topic-term matrices, doc-topic assignments, topic prevalence over time
(a stacked-area chart is the natural view), and topic × speaker-group crosstabs.

**Caveat to build in:** speeches average 624 tokens. That is short for LDA. Consider
modelling at paragraph level within the subset, and report the choice.

### 3.4 `07_embed.py` — semantic map

- Sentence embeddings of the genocide subset (or of the ±200-word window around each
  occurrence — arguably the better unit: it embeds *the use of the word*, not the speech).
- UMAP → 2D, coloured by year / speaker group / topic / (later) LLM-extracted frame.
- Exported as a JSON of 3,273-6,092 points; ECharts scatter handles this comfortably.

### 3.5 `08_kwic.py` — concordance

**The core of the "quotes in context" requirement.**

For every occurrence of every lexicon term:

```json
{ "id": "UNSC_2014_SPV.7155_spch0007#3",
  "file": "UNSC_2014_SPV.7155_spch0007.txt",
  "term": "genocide", "register": "legal",
  "left": "…Russia's action tarnishes the memory of all those who died in the ",
  "kw": "Srebrenica genocide",
  "right": ". Russia will have to justify its decision to the families of the more than 8,000…",
  "sent": "<full sentence>",
  "date": "2015-07-08", "country": "United Kingdom…", "iso3": "GBR",
  "type": "Mentioned", "agenda": "Bosnia And Herzegovina", "spv": "S/PV.7481" }
```

~6,100 lines for `genocid*` alone; ~40k across the full lexicon. At ~450 bytes per line
that is 3 MB / 18 MB — the genocide file ships eagerly, the rest lazily per term.

Window: ±150 characters for the display snippet, plus the **full sentence** (spaCy
sentence segmentation) as the citable unit. Both are needed: the snippet for scanning, the
sentence for quoting.

### 3.6 `09_export_speeches.py`

One JSON per meeting (6,595 files): meeting metadata + every speech with full text,
speaker, country, position, and per-term occurrence offsets so the viewer can highlight
matches without re-running the regex client-side.

---

## 4. Phase 3 — The dashboard

Seven views. Everything cross-filters through a shared URL-encoded filter state
(period · term/register · speaker group · agenda item · entity type), so any view is
shareable and citable as a link.

### 4.1 Overview

Headline figures (3,273 speeches · 6,092 occurrences · 3.08% · 630 entities), the
normalised time series with event annotations, and the four or five findings from §8 of the
README rendered as small multiples. This is the view that has to make a visitor understand
the question in fifteen seconds.

### 4.2 Chronology

Time series with a switch between raw / per-speech rate / per-100k-token rate; term and
register selectors; stacked breakdown by speaker group; a brushable axis that drives every
other view. Change points marked. Clicking a year opens the concordance filtered to it.

### 4.3 Actors

- Ranked bars: by volume and by rate, with the rate view guarded by a minimum-speeches
  slider (the Armenia problem: 28.2% on 124 speeches is not comparable to Rwanda's 26.8%
  on 697 — the UI must make the denominator visible, not hide it).
- P5 / E10 / non-member / UN / non-state comparison over time.
- Per-actor profile page: their series, their collocates, their topics, their quotes.
- A speaker-topic bipartite network (echoing Eckhard, Patz, Schoenfeld & van Meegdenburg
  2023, which did exactly this on this corpus — worth citing and extending to the
  genocide subset).

### 4.4 Maps (MapLibre)

Two layers, and the point of the view is the **asymmetry between them**:

1. **Who speaks** — choropleth/proportional symbols on the speaker's country
   (`country_org` → ISO3), rate of genocide invocation.
2. **What is spoken about** — the geography of the agenda item
   (`agenda_item_manual` → country/region), i.e. where the alleged genocide is located.

A country that talks a lot about genocide elsewhere but is never the object of such talk
occupies a very different position from one that is only ever the object. A flow layer
(speaker → subject, arcs) makes this legible; it is also the single most likely thing to
become a figure in a publication.

Non-state speakers (NGOs, UN, IGOs) can't be mapped to a state — they get a separate
panel, not a fake centroid.

### 4.5 Language

Collocates (sortable table + cloud), keyness vs the matched control, the co-occurrence
network, and register-share over time. Every word in every cloud and table is clickable
through to concordance lines containing it.

### 4.6 Concordance (KWIC)

The workhorse view:

- Full-text search across the corpus (or within the current filter), with regex support.
- Sortable by date, country, agenda item, or by left/right context (classic corpus-linguistic
  sorting — this is how patterns become visible).
- Each line expands to the full sentence, then to the full speech in a side panel, then to
  the full meeting.
- Export selected lines to CSV/BibTeX-ish citation format with `S/PV` reference — so a
  researcher can lift quotes straight into a paper.
- Deep-linkable: every concordance line has a stable URL.

### 4.7 Speech reader

Full text with lexicon matches highlighted by register, speaker metadata, position in the
meeting, links to the previous/next speech and to the UN Digital Library record via the
`S/PV` symbol. Later: the LLM-extracted structured summary alongside.

---

## 5. Phase 4 — LLM structured extraction

Two-stage design, following the sequence agreed for this project: **open inductive pass →
inspect → induced codebook → constrained pass**. The point is that the categories come from
the corpus, not from our prior assumptions about it.

### Stage A — Open coding (inductive)

Sample **200 speeches**, stratified by decade × region × speaker type × occurrence count,
including the extremes (the 198-occurrence session, and speeches with a single passing
mention).

Prompt, deliberately unconstrained: *given this speech and its metadata, what is the speaker
doing with the word "genocide" here?* Free-form output. No schema, no category list, no
suggested vocabulary — anything we hand it, it will hand back.

- Model: **`claude-opus-5`** at `effort: high` (this stage is about the quality of the
  reading, not throughput).
- Output: 200 free-text analyses, saved with their inputs.

### Stage B — Codebook induction

Read the 200 outputs (a mix of manual reading and an LLM synthesis pass over them) and
derive the actual dimensions. Expected candidates, to be confirmed or discarded by what
Stage A actually returns:

- **Speech act**: accusation · denial · commemoration · legal qualification · warning /
  prevention · analogy · procedural reference · rebuttal of another's accusation
- **Referent**: which event/place, and is it historical or ongoing?
- **Legal register**: is the Convention/Statute invoked? is qualification asserted, denied,
  deferred to a court, or hedged?
- **Target of the accusation**: named state · non-state actor · unnamed · the Council itself
- **Political function**: obtain a resolution/referral · block one · establish moral standing ·
  contest another state's framing · commemorate · deflect
- **Comparison work**: is this genocide compared to another? which one?

Deliverable: **`codebook.md`** with definitions, boundary cases, and 2-3 worked examples
per category, drawn from Stage A. This is the intellectual core of the LLM layer and it is
a human deliverable, not a generated one.

### Stage C — Constrained extraction

Apply the codebook as a strict JSON schema (`output_config.format`) across the full
subset.

- Scope: the 3,273 speeches with ≥1 occurrence. (The 1,061 with ≥2 is the fallback if
  results are noisy on single passing mentions.)
- Model: **`claude-sonnet-5`** via the **Batch API** (50% discount), with the codebook and
  schema in a cached prefix. Escalate to `claude-opus-5` if the validation pass (Stage D)
  shows Sonnet under-performing on the harder categories.
- Every extraction must return **verbatim supporting quotes** with character offsets for
  each coded field. A code without a quote is not usable evidence, and the offsets let the
  dashboard show the model's warrant in the reader view.
- Include an explicit `uncertain` / `not_applicable` path per field, and a free-text
  `notes` field to catch what the schema misses — which feeds a possible codebook v2.

**Cost estimate** (Batch API, prompt caching on the codebook prefix; first-party API rates
as of 2026-08-07):

| Model | Input ≈4.5M tok | Output ≈2M tok | Batch total |
|---|---:|---:|---:|
| `claude-sonnet-5` ($3/$15) | $6.75 | $15.00 | **≈ $22** |
| `claude-opus-5` ($5/$25) | $11.25 | $25.00 | **≈ $36** |

Both are negligible against the project's value. Cost is not the constraint here — validation
effort is. Budget for two or three full re-runs as the codebook is refined.

### Stage D — Validation (non-negotiable)

- **Double-coding**: run 150 speeches twice at temperature-equivalent settings and measure
  self-consistency per field.
- **Human gold standard**: two team members hand-code 100 speeches against the codebook;
  compute Cohen's κ human-vs-human (the ceiling) and human-vs-model.
- **Report both**, per field, in the README and in the dashboard's methods page. Fields
  below κ ≈ 0.6 are shown as exploratory or dropped.
- Adversarial spot-check: verify every returned quote actually appears in the source text
  (mechanical check, catches fabrication immediately).

### Stage E — Integration

LLM codes become dashboard filters and views: speech-act distribution over time, political
function by speaker group, accusation networks (who accuses whom of genocide, and when),
and a per-speech card in the reader. Every LLM-derived figure carries a visible marker
distinguishing it from directly-measured data.

---

## 6. Sequencing

| Phase | Content | Rough effort | Depends on |
|---|---|---|---|
| **1** | Normalisation, entity crosswalk, lexicon YAML, audit | ~3 days | — |
| **2** | Series, lexicometry, KWIC, topics, embeddings | ~5 days | 1 |
| **3a** | SvelteKit scaffold + Overview / Chronology / Concordance / Reader | ~6 days | 2 |
| **3b** | Actors, Language, Maps | ~5 days | 2, entity crosswalk |
| **4** | LLM stages A→E | ~6 days, spread over calendar time | 2 |
| **5** | Integration of LLM layer, methods page, deployment | ~3 days | 3, 4 |

Phases 3a and 4 can run in parallel — Stage A of the LLM work needs nothing from the
dashboard.

**Suggested first milestone:** finish Phase 1 + `08_kwic.py` + a minimal Chronology and
Concordance view. That combination alone is already a usable research instrument, and it
puts the corpus in the team's hands early enough to shape everything after it.

---

## 7. Open questions

1. ~~**Publication scope.**~~ **Settled:** private repository during development, published
   openly as a static GitHub Pages site at launch. Two consequences to carry:
   *(a)* Pages from a private repository requires a paid GitHub plan — on a free account
   the repository has to be flipped to public before the site can publish, so plan the
   launch as a deliberate visibility change rather than a deploy.
   *(b)* An open dashboard raises the bar on the LLM layer: every model-derived figure
   needs a visible provenance marker and the validation metrics (§5 Stage D) have to be
   published alongside, not filed away.
2. **Corpus scope.** Stay on genocide + neighbours, or build the general-purpose UNSC
   dashboard with genocide as the flagship case study? The infrastructure is nearly
   identical; the framing and the writing are not.
3. **The lexicon's boundary.** Should "ethnic cleansing", "crimes against humanity" and
   "atrocity" be first-class subjects alongside genocide, or context for it? §8.4 suggests
   they are inseparable in practice — which argues for treating the atrocity-core set
   (7,936 speeches) as the real object.
4. **Multilingualism.** The corpus is English-only by construction (§10.4). Worth stating
   as a limitation, or worth attempting to recover original-language records for a subset?
   The latter is a substantial separate project.
5. **Should the LLM layer read whole speeches or windows?** Whole speeches give context and
   political intent; ±300-word windows give the *use* of the word and cost a fifth as much.
   Stage A should test both on the same 30 speeches before Stage C commits.

---

## 8. Deliverables

- `README.md` — corpus documentation *(done)*
- `PLAN.md` — this document *(done)*
- `scripts/` — numbered, idempotent, each writing a Markdown findings note
- `codebook.md` — the induced coding scheme *(Stage B)*
- `data/` — parquet + derived artefacts, gitignored, rebuildable from source
- `web/` — the SvelteKit application
- `METHODS.md` — reproducibility, validation metrics, limitations, for publication use
