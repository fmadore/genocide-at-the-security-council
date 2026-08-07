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

Python dependencies live in `requirements.txt` (`numpy`, `pandas`, `pyarrow`, `PyYAML`) and
`requirements-dev.txt` (`pytest`, `ruff`). Steps 00-05 and 08 need nothing beyond those,
which is why `.github/workflows/checks.yml` can lint and test the whole pipeline in under
40 seconds.

Still to add, and which step each one gates:

| Package | Gates | Weight |
|---|---|---|
| `scikit-learn` | §3.3 LDA/NMF | small |
| `sentence-transformers`, `umap-learn`, `bertopic` | §3.3 BERTopic, §3.4 semantic map | **large** — pulls `torch`, ~2.5 GB, and a model download at first run |
| `anthropic` | §5 the LLM layer | small |

`spacy` + `en_core_web_sm` is **no longer needed**. It was in the plan for sentence
segmentation in §3.5; `08_kwic.py` uses rule-based segmentation instead, for the reasons
set out there.

The BERTopic group is the only real decision in this table: it changes the install from
"pip install and go" to a multi-gigabyte environment, and it makes CI a different
proposition. Worth taking deliberately rather than as a side effect of running `06`.

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

**Status: complete**, bar one item that needs a human (the precision audit verdict).
`01_build_parquet.py` validates clean (106,302 rows, 0 missing texts, 0 orphans); `02`
and `03` run clean on top of it.

### 2.1 `scripts/02_normalise.py` ✅

- [x] Merge `country_org` aliases (§5.3 of the README) via an explicit, version-controlled
      mapping file — not a fuzzy matcher. → **`config/country_aliases.csv`**, 32 entries,
      629 raw labels to 601 canonical. Renames are merged (Türkiye/Turkey); successions
      are not (Zaire, Yugoslavia, Serbia and Montenegro keep their own rows).
- [x] Normalise case on `agenda_item2/3/4` and `participanttype` (`The PRESIDENT` → `The President`).
      → `text.modal_case` collapses onto the *most frequent* spelling rather than imposing
      a title-case rule. `agenda_item2` 124 → 108, matching the 16 collisions documented
      in CORPUS.md; `topic` 590 → 546.
- [x] Build **`config/entities.csv`**: one row per distinct `country_org`, with
      `iso3` · `entity_type` (state / IGO / UN agency / NGO / civil society / academia /
      company / other) · `lat` · `lon` · `un_regional_group`.
      → 601 rows: 200 states (all with ISO3, centroid and UN regional group), 166 civil
      society, 59 IGO, 50 NGO, 49 other, 33 academia, 27 UN, 17 company.
      `tools/bootstrap_entities.py` proposes rows from ISO 3166 + a centroid dataset and
      never edits the checked-in file; `--missing` re-proposes only new speakers.
      `entities.validate_coverage` fails the run on any untyped `country_org`, and the
      tests assert that no non-state carries a centroid.
- [x] Strip the opening form of address from each text into a `text_body` column, keeping
      the raw text for display. → stored as a `body_start` **offset** rather than a second
      129 MB copy of the text; `frames.body()` reconstitutes it in one call, and offsets
      stay valid into the full text for the reader's highlighting. Matches 95.13%; the
      remaining 4.87% are continuation speeches with no address and are left untruncated.
- [x] Flag P5 / E10 / non-member / UN / non-state per speech, per year.
      → **`config/council_membership.csv`**, one row per term. Validated two ways: every
      year 1992-2023 must hold exactly 5 permanent and 10 elected seats, and every
      recorded member must actually speak in the year it served. Both pass.
- [x] *Bonus, not in the original plan:* **delivery language** recovered for 42,765
      speeches (40.2%) from the `(spoke in …)` markers — see §7 open question 4, which
      this partly answers.

### 2.2 `scripts/03_lexicon.py` ✅

- [x] Formalise the lexicon as a versioned YAML file: term → regex → register
      (legal / preventive / commemorative / contentious / adjacent). → 22 active terms,
      compiled with their tier and register; sets validated against defined terms.
- [x] Add OCR-tolerant variants (`gen[eo]cid`, `s[eg]nocide`) and measure how many extra
      matches they yield — report the number, don't silently absorb it.
      → **exactly 1** extra speech across the whole corpus (`genecide`, S/PV.3137, 1992).
      The pattern stays disabled; the case is logged in `docs/VALIDATION.md`.
- [x] Emit per-speech boolean + count columns for each term into `speeches_flagged.parquet`.
      → 62 lexicon columns: `n_`/`has_` per term, per register and per set.
      Counting on the body reproduces the documented 3,273 speeches / 6,092 occurrences
      exactly, which confirms the form of address holds no real words.
- [ ] **Sanity audit**: hand-check a random 100 matches for false positives (e.g. "genocide"
      inside a quoted resolution title, or a treaty name). Report a precision estimate in
      the README. → **sample emitted** to `data/interim/lexicon_audit_sample.csv` with an
      empty `verdict` column, reproducible via `--seed`. *Awaiting a human verdict.*

---

## 3. Phase 2 — Computational analysis

Each script writes both a JSON artefact for the dashboard and a Markdown findings note for
the team.

### 3.1 `04_series.py` — temporal ✅

- [x] Counts and rates per year / per quarter, per term, per register.
      → 32 measures (22 terms, 6 registers, 4 sets) x 32 years and 128 quarters. Sets carry
      no occurrence count on purpose: a set is a union, and summing its members would count
      a speech saying both *genocide* and *war crimes* twice.
- [x] Breakdowns crossed with `agenda_item1`, `agenda_item_manual` (top 20), `participanttype`,
      speaker group, `entity_type` — plus **delivery language**, which §7.4 asks about.
- [x] **Change-point detection** on the normalised series. Not `ruptures`, and not plain
      binary segmentation either: the latter only ever splits a segment as a whole, which
      makes it blind to a bump, and this corpus is bump-shaped (1993-96, 2013-15). The scan
      runs over sub-intervals — Wild Binary Segmentation — with a permutation test on every
      accepted split. ~200 lines in `lib/series.py`, unit-tested against series whose answer
      is known by construction.
- [x] Event overlay: **`config/events.csv`**, 35 reference dates across six kinds, with a
      UN document symbol wherever one exists. **Machine-drafted and unverified** — logged in
      `docs/VALIDATION.md` §5 as the highest-priority item there, because a chart annotation
      carries the authority of the chart.

**The result the plan was built to find.** `genocide` breaks on the raw count (speeches
2013, occurrences 2014) and **nowhere on either rate**. The famous 2014 peak is the corpus
growing: speeches per year roughly doubled over the same span, and the largest normalised
year in the corpus is still 1994.

**The result it was not.** The wider `atrocity_core` set *does* break on the rate — 1996
(x0.70), 2013 (x1.24), 2017 (x0.74). The normalised structure lives in the atrocity
vocabulary as a whole, not in `genocide` alone. That is direct evidence on open question 3
below, and it argues for the 7,936-speech set as the real object of study.

### 3.2 `05_lexical.py` — lexicometry ✅

- [x] **Collocates** by log-likelihood at ±5, ±8 and ±15, sliced by period, speaker group
      and speaker. Every row also carries **log ratio** (Hardie 2014): on 59 M tokens
      almost everything is significant, and the effect size is what decides whether a row
      is a finding.
      → **The speaker slice is the headline the plan predicted.** Rwanda's profile is
      unlike anyone's: `tutsi`, `denial`, `ideology`, `convicts`, `fdlr`, `fugitives` — an
      accountability-and-denial register. Everyone else's top collocates are the Rome
      Statute triad. Bosnia's are `srebrenica`, `cleansing`, `aggression`.
      → **The period slice shows the register turning over.** 1992-1999 runs on
      `aggression`, `punishment`, `acts`; 2020-2023 on `denial`, `glorification`,
      `criminals`. The word moves from qualifying an event to contesting a memory.
- [x] **Keyness** against a control matched on year × agenda item × speaker group.
      3,104 of 3,273 targets matched (94.8%); the 100 strata that could not be filled are
      listed rather than back-filled, since they are the debates where nearly everyone
      used the word.
      → The unmatched comparison ships alongside, **not as a result but as the thing the
      matching is meant to improve on**. Median effect size across the top 15 unmatched
      keywords falls by 1.85 on the log2 scale — a factor of 3.6 in rate. `bosnia`,
      `herzegovina` and `tribunals` drop out entirely; `genocide`, `humanity` and
      `rwandan` survive. That is the occasion being subtracted from the concept, shown
      rather than asserted.
- [x] **Word clouds** are a *rendering* of these tables, not a separate artefact. Shipping
      them as their own file would invite them to drift from the numbers they depict.
- [x] **Co-occurrence network**, PMI at speech level, whole corpus and per period, with
      **normalised** PMI as the edge weight so a term appearing in 30 speeches cannot buy
      an edge with rarity alone.
      → It does make the predicted structure visible: `crimes_against_humanity`↔`war_crimes`
      (nPMI 0.735) and `genocide`↔both are the three strongest edges in the graph, and
      `denial`↔`glorification` (0.470) shows up as its own pair.

**`config/stopwords.txt` is function words only**, and the file says why at length: whether
`council` sits disproportionately close to `genocide` is exactly what the collocate
analysis exists to find out, and a stoplist that removed it would answer the question by
assumption.

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

### 3.5 `08_kwic.py` — concordance ✅

**The core of the "quotes in context" requirement.**

Done, and it came out larger than estimated: **80,011 lines across 22 terms, 61.7 MB**
(the estimate below assumed ~40k lines at 450 bytes and did not price the sentence).
`genocide` alone is 6,092 lines / 4.8 MB, which still ships eagerly; the rest stay lazy.

Two departures from what follows:

- **Sentence segmentation is rule-based, not spaCy.** The genre's traps are specific and
  enumerable — `Mr.`, `para.`, `No.`, `U.S.`, `S/PV.3453`, `resolution 955 (1994).`, and
  initials in a name — and a general model has no particular advantage on them. The rules
  are in `lib/kwic.py`, unit-tested against exactly those cases, and add nothing to
  install or to CI. Median sentence 173-222 characters by term, 95th percentile ~400,
  with 1-5% over 500 characters flagged in the note for a human to look at. If that
  distribution ever looks wrong, it is one function to swap.
- **`file` is not stored per line.** It is `id` up to the `#`, plus `.txt`. At 80,000
  lines that redundancy is several megabytes for nothing.

The run **fails** rather than writing anything if a term's line count disagrees with the
occurrence count in `speeches_flagged.parquet`. All 22 reproduce exactly. A concordance
that does not add up to the totals printed beside it is worse than none: the reader has
no way to tell which number is wrong.

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

| Phase | Content | Rough effort | Depends on | State |
|---|---|---|---|---|
| **1** | Normalisation, entity crosswalk, lexicon YAML, audit | ~3 days | — | ✅ bar the audit verdict |
| **2a** | Series (`04`), lexicometry (`05`), KWIC (`08`) | ~3 days | 1 | ✅ |
| **2b** | Topics (`06`), embeddings (`07`), speech export (`09`) | ~2 days | 1, and the `torch` decision in §1.1 | ⬜ |
| **3a** | SvelteKit scaffold + Overview / Chronology / Concordance / Reader | ~6 days | 2a | ⬜ |
| **3b** | Actors, Language, Maps | ~5 days | 2a, entity crosswalk | ⬜ |
| **4** | LLM stages A→E | ~6 days, spread over calendar time | 2 | ⬜ |
| **5** | Integration of LLM layer, methods page, deployment | ~3 days | 3, 4 | ⬜ |

Phases 3a and 4 can run in parallel — Stage A of the LLM work needs nothing from the
dashboard.

**2a is done, and 3a no longer waits on 2b.** The Overview, Chronology, Concordance and
Reader views need `series/`, `lexical/` and `kwic/`, all of which now exist. Topics and
embeddings feed the Language and semantic-map views, which come later — so the dashboard
scaffold can start immediately, without first committing to a 2.5 GB install.

`09_export_speeches.py` is the one gap in 2b that 3a genuinely needs: the Reader view has
no full text without it, and it depends on nothing but the parquet. It should be pulled
forward ahead of `06` and `07`.

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
   **Evidence from `04_series.py`:** the `genocide` rate has no detectable regime shift
   across 1992-2023; the `atrocity_core` rate has three. Whatever changes in this
   discourse, it does not change at the level of the single word. That is an argument for
   the wider set — though it is one test on one series, and §3.2's keyness pass is the
   better place to settle it.
4. **Multilingualism.** The corpus is English-only by construction (§10.4). Worth stating
   as a limitation, or worth attempting to recover original-language records for a subset?
   The latter is a substantial separate project.
   **Partly answered by Phase 1:** the *delivery language* is now known for 42,765
   speeches (40.2%), read off the form of address. So the limitation can be stated
   quantitatively rather than vaguely — two speeches in five are translations — and the
   subset worth recovering originals for is now identifiable rather than hypothetical.
   It also opens a question the plan did not anticipate: does invocation of "genocide"
   vary with the language a speech was delivered in, holding speaker and period constant?
   That is a cheap crosstab on data we already have.
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
