# Pipeline

Numbered steps, run in order. Each is **idempotent** — safe to re-run — reads from
`data/`, writes to `data/derived/` and drops a Markdown findings note in `notes/`.

The numbered scripts are thin orchestrators. All the logic lives in [`lib/`](lib), which
is importable and unit-tested, so a step reads as a sequence of named operations and the
operations themselves can be checked without a 131 MB parquet.

Analysis inputs that are meant to be edited by hand live in [`../config/`](../config/);
one-off maintenance helpers live in [`../tools/`](../tools).

Use an x64 Python 3.12 — `pyarrow` publishes no 32-bit wheel, and a 32-bit interpreter
fails at install time rather than at import.

Install the exact, hashed environment with `python -m pip install --require-hashes -r
requirements.lock` from the repository root. `requirements.txt` and
`requirements-dev.txt` declare supported ranges; the lock is the reproducibility record.

## Steps

| # | Script | Reads | Writes | State |
|---|---|---|---|---|
| 00 | `00_fetch_data.py` | Dataverse API | `data/raw/` | ✅ |
| 01 | `01_build_parquet.py` | `data/raw/` | `derived/speeches.parquet`, `meetings.parquet` | ✅ |
| 02 | `02_normalise.py` | `speeches.parquet`, `config/{entities,country_aliases,council_membership}.csv` | `derived/speeches_norm.parquet` | ✅ |
| 03 | `03_lexicon.py` | `speeches_norm.parquet`, `config/lexicon.yml` | `derived/speeches_flagged.parquet` | ✅ |
| 04 | `04_series.py` | `speeches_flagged.parquet`, `config/events.csv` | `derived/series/*.json` | ✅ |
| 05 | `05_lexical.py` | `speeches_flagged.parquet`, `config/stopwords.txt` | `derived/lexical/*.json` | ✅ |
| 06 | `06_embed.py` | `speeches_flagged.parquet`, `config/embedding_models.yml` | `derived/embeddings/` | 🖥️ GPU |
| 07 | `07_topics.py` | `speeches_flagged.parquet`, `derived/embeddings/` | `derived/topics/` | 🔬 evaluation only |
| 08 | `08_kwic.py` | `speeches_flagged.parquet` | `derived/kwic/*.json` | ✅ |
| 09 | `09_export_speeches.py` | `speeches_flagged.parquet`, `meetings.parquet` | `web/static/data/speeches/*.json` | ✅ |
| 10 | `10_lemmatise.py` | `speeches_flagged.parquet` | `derived/lemmas/` | 🔬 optional |
| 11 | `11_countries.py` | `speeches_flagged.parquet`, `config/entities.csv` | `derived/countries/countries.json` | ✅ |
| 12 | `12_speaker_keyness.py` | `speeches_flagged.parquet`, `config/stopwords.txt` | `derived/countries/speaker_keyness.json` | ✅ |
| 13 | `13_gold_sample.py` | `speeches_norm.parquet`, `config/lexicon.yml`, `annotations/genocide/` | `data/interim/genocide_gold_*.csv` | ✅ |
| 14 | `14_llm_annotate.py` | `speeches_norm.parquet`, `model_annotations/genocide/PROMPT.md`, the OpenAI API | `model_annotations/genocide/runs/<id>/` | ✋ manual, paid |
| 15 | `15_usage.py` | `model_annotations/genocide/`, `annotations/genocide/`, `speeches_norm.parquet` | `derived/usage/*.json` | 🧪 experimental |
| 16 | `16_llm_annotate_gemini.py` | `speeches_norm.parquet`, `model_annotations/genocide/PROMPT.md`, the Gemini API | `model_annotations/genocide/runs/<id>/` | ✋ manual, paid |
| — | `export_web.py` | `derived/{series,lexical,kwic,countries,usage}/` | `web/static/data/` | ✅ |
| — | `score_intrusion.py` | `derived/topics/intrusion_{task,key}.csv` | `derived/topics/intrusion_score.json` | 🔬 after a human |

**06, 07 and 10 are not part of the release pipeline.** They need the extra dependencies in
[`../requirements-cluster.txt`](../requirements-cluster.txt) — and, for 06, a GPU — and they
run on the Bayreuth cluster; see [`../docs/CLUSTER.md`](../docs/CLUSTER.md). None is read by
`export_web.py`, and the dashboard does not know they exist.

**11 builds the table [`../docs/PLAN.md`](../docs/PLAN.md) §7 requires before anything is
drawn on a map.** Per speaker and per period: the speaker's own denominator, its
term-bearing speeches and occurrences, both rates, its ISO3 and centroid where the
crosswalk has them, and a `sufficient` flag against a declared minimum sample. It draws
nothing and changes nothing 04 wrote — a rate is *withheld* below the minimum rather than
published small, because the alternative is a map whose brightest country spoke twice.

**12 is the other half of the same requirement, for language rather than rates.** For every
speaker with enough of a record, it pairs each of that speaker's speeches with one from the
same year, agenda item and speaker group given by somebody else, and reports what
distinguishes the two vocabularies — plus the unmatched comparison beside it, so a reader
can see what holding the occasion constant removed. The step draws nothing; the figure over
it is `SpeakerKeyness.svelte` on the actor view, written after the table as §7 requires.
Two gates withhold a table rather than publish a weak one, and the second exists because of
a case the first does not catch: the UN Secretariat is the only speaker in its speaker
group, so the matching found partners for 123 of its 4,709 speeches (2.6%) — comfortably
past a minimum counted in pairs, and a profile of a delegation resting on a non-random
fortieth of what it said. Seven of the 133 eligible speakers are withheld this way; the
artefact names which gate closed for each.

**10 is numbered after 09 although it feeds 05.** The numbers are creation order, and 00–09
were already referenced from the dashboard, the notes and CI before it existed; renumbering
would have moved five committed steps to make room for an optional one. Its dependency is
stated instead — it needs 03, and it enables `05_lexical.py --vocabulary lemma`, which
writes to `derived/lexical_lemma/` and never touches the surface tables.

06 produces vectors. 07 produces the *comparison and the evaluation*
[`../docs/PLAN.md`](../docs/PLAN.md) §4 requires before a topic model may be believed —
a count-based baseline against an embedding-based approach on a frozen sample, with
coherence, stability under resampling, sensitivity to `k`, topic composition, and a
blinded word-intrusion task for a human to complete. §4 still defers adoption: a topic
model enters the release only once there is a research question collocates and agenda
labels cannot answer. LLM extraction (§5) remains a proposal with no script.

`score_intrusion.py` is unnumbered and deliberately a separate run: it turns a completed
intrusion task into the interpretability number §4 wants, and keeping it out of 07 means no
unattended job can ever produce one as a side effect of fitting a model. 07 writes the task
and its key as two files so that the file a human opens does not contain the answer.

**13, 14 and 15 are the model-assisted usage layer** (Phase L in
[`../docs/IMPROVEMENT_ROADMAP.md`](../docs/IMPROVEMENT_ROADMAP.md)). 13 draws the human
gold sample and is deterministic. **14 is never run by CI or the deploy**: it needs
`OPENAI_API_KEY`, the extra dependency in
[`../requirements-llm.txt`](../requirements-llm.txt), and money — a full run sends all
6,092 `genocide` occurrences to the model. Its output is committed under
`model_annotations/`, which is why the deploy can rebuild the payload without ever holding
a key. 15 is deterministic again: it joins the committed run, the human gold rows and the
corpus into `derived/usage/`, refusing a run whose term pattern, occurrence identities or
source digests no longer match. Besides the actor × referent matrix and the stance
profiles, its `usage.json` carries a `diffusion` block (Phase L7): per referent, the dated
first occurrence per delegation in three milestone classes — first mention, first
assertion, first rejection of the word — from which the `/usage` view draws its cumulative
adoption curves and their clickable chronology.

## The model annotation run

```bash
python -m pip install -r requirements-llm.txt   # once, on the machine that runs 14
python scripts/13_gold_sample.py                # the gold sample the run is judged against
python scripts/14_llm_annotate.py --run-id <date>-luna-pilot --model gpt-5.6-luna --limit 50
#   read runs/<pilot-id>/annotations.jsonl and failures.jsonl; commit the pilot run
python scripts/14_llm_annotate.py --run-id <date>-luna-v1 --model gpt-5.6-luna
#   gpt-5.6-luna exactly — the gpt-5.6 alias routes to Sol, a different model
#   Batch API, resumable with --poll; commit the run, then name it in
#   model_annotations/genocide/current_run.txt (a reviewed diff)
python scripts/15_usage.py
python scripts/export_web.py
```

To preview the `/usage` view before paying for a run,
[`../tools/synthetic_usage_run.py`](../tools/synthetic_usage_run.py) fabricates a clearly
labelled synthetic run under `data/interim/synthetic_run/`;
`python scripts/15_usage.py --run-dir data/interim/synthetic_run` aggregates it. Synthetic
runs are never committed under `model_annotations/`.

The comparison run (Phase L8) is the same procedure through the other door. 16 is 14's
Gemini sibling — same enumeration, same `PROMPT.md`, byte-compatible rows — keyed by
`GEMINI_API_KEY` (or `GOOGLE_API_KEY`; see `.env.example` for the precedence quirk):

```bash
python scripts/16_llm_annotate_gemini.py --run-id <date>-gemini-v1 --model gemini-3.7-flash
#   Batch API, resumable with --poll; commit the run, then name it in
#   model_annotations/genocide/comparison_run.txt (a reviewed diff)
python scripts/15_usage.py && python scripts/export_web.py
```

15 then computes where the two instruments disagree — per-field agreement, per-occurrence
`contested` flags — and refuses a comparison made against a different prompt hash. The
comparison is computed, never merged: `current_run.txt` still names the only run the
matrix, stance and diffusion figures are drawn from, and agreement between two models is
stability across instruments, never accuracy.

Human coding proceeds in parallel: `FM` and `JG` fill
`annotations/genocide/annotations.csv` per the codebook; after each tranche, rerun 15 and
`export_web.py` and the agreement tables on `/usage` update. Record every run in
[`../docs/VALIDATION.md`](../docs/VALIDATION.md) §7.

See [`../docs/PLAN.md`](../docs/PLAN.md) for what each step is meant to establish.

## Changing the lexicon

The word list is the study's central scholarly choice, and
[`../docs/PLAN.md`](../docs/PLAN.md) calls it a proposal rather than a result. Adding or
removing a term is therefore a recorded decision, not a configuration tweak.

1. **Edit [`../config/lexicon.yml`](../config/lexicon.yml).** A term needs a `pattern`
   (Python regex), `prefilters`, `examples`, a `tier`, a `register` and a `pattern_since`.
   A prefilter is a literal contained in *every* string the pattern can match: it only
   decides which speeches are worth running the regex on, so one that is not in every
   match loses occurrences silently rather than merely slowing the scan down. It must
   contain no whitespace — the records keep their hard line breaks, and `\s+` spans a
   break that `war crime` never will. `pattern_since` is the version in which that term's
   `pattern` last changed; leave it alone unless you edit the pattern, and set it to the
   new `version` when you do. Use `note` for the rationale — why this term belongs to this
   study, and what it is expected to catch that the existing terms do not. That sentence
   is the part a reader of the published figures will want and cannot reconstruct.
2. **Bump `version` and `updated`** in the same file. The version travels into every
   artefact's `meta` and into every CSV header, so a figure and the word list that produced
   it can always be matched. The bump on its own invalidates nothing keyed to a single
   term: `15` reads a committed run's recorded version against that term's `pattern_since`,
   so a release that edited other terms leaves the gold sample and the model runs standing.
   Editing a `pattern` — and so bumping its `pattern_since` — does invalidate them.
3. **Rerun, in order:** `03` (which recounts every speech), then `04`, `05`, `08`, `09`,
   `11` and `12`, then `export_web.py`. Each step asserts its own output, so a broken
   pattern fails at 03 rather than surfacing as an empty column in the dashboard. A change
   to the `genocide` pattern additionally invalidates `13`'s gold sample and any committed
   model run: `15` refuses a run recorded against a version older than that term's
   `pattern_since`, or whose occurrence identities no longer match, so the price of editing
   that term is a new sample, new coding and a new run.

What follows from that, worth knowing before you start:

- **Every downstream number changes**, including ones that do not mention the new term: a
  register or set that the term joins is recounted, and so is anything measured against the
  corpus as a whole.
- **Existing annotations do not carry over automatically across an incompatible pattern
  change.** That is the A2 rule in
  [`../docs/IMPROVEMENT_ROADMAP.md`](../docs/IMPROVEMENT_ROADMAP.md): an occurrence ID is
  built from the span and matched text, and the lexicon version is stored beside it, so a
  changed pattern produces new occurrences rather than silently inheriting old verdicts.
  `pattern_since` is what makes "incompatible" decidable — a bump that left the term's
  pattern alone carries over, an edited pattern does not.
- **The dashboard needs no code change.** The concordance builds its term list from
  `kwic/index.json`, and no view hardcodes a term. A new term appears in the selects, the
  chronology measures and the co-occurrence network on its own.
- **The contract should not need editing either.** It tracks one representative term file
  rather than all twenty-two, and the lexicon-keyed collections — `terms`, `registers`,
  `sets`, `measures`, `series`, speech `hits` — are contracted on presence and type only,
  precisely so an ordinary lexicon edit does not read as a breaking change. Run
  `python -m pytest tests/test_contract.py` to prove it rather than assuming it; if it does
  fail, that is a real shape change and `python scripts/export_web.py --update-contract` is
  the deliberate second step.

## Modules

| Module | Responsibility |
|---|---|
| [`lib/paths.py`](lib/paths.py) | Where everything lives. One definition, imported everywhere. |
| [`lib/console.py`](lib/console.py) | Uniform reporting, and UTF-8 stdout on Windows. |
| [`lib/artifacts.py`](lib/artifacts.py) | Atomic files/directories, hashes and provenance manifests. |
| [`lib/contract.py`](lib/contract.py) | The payload's shape, and whether it still has it. Enforced at the export seam. |
| [`lib/frames.py`](lib/frames.py) | Parquet read/write; `body()` reconstructs a speech minus its form of address. |
| [`lib/text.py`](lib/text.py) | Line endings, the opening form of address, delivery language, case collisions. |
| [`lib/language.py`](lib/language.py) | Explicit, inferred and unknown delivery-language policy. |
| [`lib/entities.py`](lib/entities.py) | The `country_org` crosswalk: aliases in, type/ISO3/centroid out. |
| [`lib/council.py`](lib/council.py) | Council membership by year; the P5 / E10 / non-member / UN / non-state split. |
| [`lib/lexicon.py`](lib/lexicon.py) | Loads, compiles and counts `config/lexicon.yml`. |
| [`lib/series.py`](lib/series.py) | Periods, denominators, rates, breakdowns; change-point detection; the event overlay. |
| [`lib/actors.py`](lib/actors.py) | Per-speaker aggregation over `lib/series.py`'s arithmetic; the minimum-sample rule; ISO3 collisions and what may be mapped. |
| [`lib/kwic.py`](lib/kwic.py) | Sentence segmentation for the genre, and concordance-line extraction. |
| [`lib/occurrences.py`](lib/occurrences.py) | One enumeration of a term's occurrences, carrying both the audit `occurrence_id` and the KWIC line id; 13, 14 and 15 share it. |
| [`lib/llm.py`](lib/llm.py) | The model annotation layer's logic: prompt parsing, request building, response validation against the codebook's vocabularies, evidence-quote location, resume rules. No network, no SDK import at module level. |
| [`lib/usage.py`](lib/usage.py) | Aggregation for the usage layer: eligible/assigned funnel, the actor × referent matrix, withholding, and the human/model agreement arithmetic. |
| [`lib/lexical.py`](lib/lexical.py) | Tokens, log-likelihood and log ratio, matched controls, PMI. |
| [`lib/keyness.py`](lib/keyness.py) | One speaker against the room: the corpus as a count matrix, the strata, the two gates, agenda composition. |
| [`lib/embeddings.py`](lib/embeddings.py) | The model registry, the chunking policy for long speeches, pooling, neighbours. |
| [`lib/topics.py`](lib/topics.py) | The frozen sample, both topic models, and the evaluation: NPMI coherence, adjusted Rand, c-TF-IDF, word intrusion. |
| [`lib/lemmas.py`](lib/lemmas.py) | The lemma layer: offset alignment to `lexical.tokenise`, the stored form, the audit mapping. |
| [`lib/download_models.py`](lib/download_models.py) | Prefetches weights on the cluster login node. |

`embeddings.py`, `topics.py` and `lemmas.py` import torch, scikit-learn, umap-learn and
spaCy *inside* the functions that need them, so the test suite and steps 00–05 run without
the cluster extras installed. Everything that decides what a model sees, and what is done
with what it returns, is plain Python and is tested on any machine.

## Cluster

[`cluster/`](cluster) holds the Slurm harness for steps 06 and 07 —
`setup_env.sh`, `download_models.sh`, `submit_*.sh`, plus `push_code.sh` and
`fetch_results.sh`, which run on your own machine. Nothing in it names an account or a
host: the cluster is addressed through an ssh alias you define in `~/.ssh/config`, and
machine-specific paths live in `.env` (git-ignored; copy `.env.example`).
[`../docs/CLUSTER.md`](../docs/CLUSTER.md) is the walkthrough.

## Tools

| Tool | Purpose |
|---|---|
| [`../tools/bootstrap_entities.py`](../tools/bootstrap_entities.py) | Proposes rows for `config/entities.csv`. Downloads ISO 3166 codes and centroids once; never edits the checked-in file. Run with `--missing` when the corpus gains new speakers. |
| [`../tools/build_boundaries.py`](../tools/build_boundaries.py) | Rebuilds `web/static/geo/countries.json`, the polygons the actor view's filled map draws. Keyed on the `iso3` column of `config/entities.csv`, from Natural Earth 1:110m at a pinned tag. The output is committed — it is derived from the crosswalk and not from the corpus, so it is not a pipeline artefact and does not belong to the Dataverse pin. Re-run it when `entities.csv` gains a state. |

## Tests

```bash
python -m pytest
```

Seconds, no data required, and run in CI on every push and pull request
([`checks.yml`](../.github/workflows/checks.yml), alongside the dashboard's own `prettier`,
`eslint`, `svelte-check` and `vitest` gates). CI is the source of truth for how many there
are; a count written down here is one that goes stale on the next commit.
[`tests/test_config.py`](../tests/test_config.py) runs against the real `config/` files, so
a bad alias or a mistyped Council term fails here rather than halfway through a pipeline
run. [`tests/test_series.py`](../tests/test_series.py) checks exploratory segmentation and
the denominator-aware binomial/Poisson breakpoint models against constructed series with
known answers. [`tests/test_actors.py`](../tests/test_actors.py) does the same for the
per-country table, on the cases that would leave it looking right while being wrong: an
untyped speaker, a blank ISO3, a denominator one short of the minimum, and a historical
state sharing a living one's code.

## Conventions

- **Validate loudly.** A script that cannot assert its output is correct should exit
  non-zero rather than write a plausible-looking artefact. `01` asserts row count, token
  sum, join completeness and date parsing against the published codebook; `02` refuses to
  run on a speaker missing from the crosswalk, or a Council year that does not add up to
  five permanent and ten elected members.
- **No magic constants in scripts.** Lexicons, aliases and thresholds live in `config/`
  under version control, so a changed number is a reviewable diff.
- **Record parameters and lineage in outputs.** Every stage records settings, input and
  config hashes, package versions, Git commit and generation time. A figure that cannot be
  traced to its inputs is not usable in a publication.
- **Report the approximate path.** Where a step resolves OCR damage by fuzzy means, it
  counts and lists what it absorbed, and the cases go to
  [`../docs/VALIDATION.md`](../docs/VALIDATION.md) to be checked against the original
  PDFs. A silent fix is unfalsifiable.
- **The payload's shape is a contract, not a convention.** The dashboard reads these
  artefacts through hand-written TypeScript types, so a renamed or dropped field used to
  fail as a blank chart rather than as an error.
  [`../tests/contract/payload.json`](../tests/contract/payload.json) records the shape —
  keys, nesting and the type at each leaf, with the data thrown away — and
  `export_web.py` refuses to publish a payload that has drifted from it. Growth is not
  drift: a new field passes, and so does a lexicon edit that changes which measures carry
  what. When a change *is* intended, `python scripts/export_web.py --update-contract`
  rewrites the file so it arrives as a diff somebody reads.
- **Notes are for humans.** Every script writes `notes/NN_name.md` summarising what it
  found, not just what it did.
