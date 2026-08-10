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
| — | `export_web.py` | `derived/{series,lexical,kwic,countries}/` | `web/static/data/` | ✅ |
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

See [`../docs/PLAN.md`](../docs/PLAN.md) for what each step is meant to establish.

## Modules

| Module | Responsibility |
|---|---|
| [`lib/paths.py`](lib/paths.py) | Where everything lives. One definition, imported everywhere. |
| [`lib/console.py`](lib/console.py) | Uniform reporting, and UTF-8 stdout on Windows. |
| [`lib/artifacts.py`](lib/artifacts.py) | Atomic files/directories, hashes and provenance manifests. |
| [`lib/frames.py`](lib/frames.py) | Parquet read/write; `body()` reconstructs a speech minus its form of address. |
| [`lib/text.py`](lib/text.py) | Line endings, the opening form of address, delivery language, case collisions. |
| [`lib/language.py`](lib/language.py) | Explicit, inferred and unknown delivery-language policy. |
| [`lib/entities.py`](lib/entities.py) | The `country_org` crosswalk: aliases in, type/ISO3/centroid out. |
| [`lib/council.py`](lib/council.py) | Council membership by year; the P5 / E10 / non-member / UN / non-state split. |
| [`lib/lexicon.py`](lib/lexicon.py) | Loads, compiles and counts `config/lexicon.yml`. |
| [`lib/series.py`](lib/series.py) | Periods, denominators, rates, breakdowns; change-point detection; the event overlay. |
| [`lib/actors.py`](lib/actors.py) | Per-speaker aggregation over `lib/series.py`'s arithmetic; the minimum-sample rule; ISO3 collisions and what may be mapped. |
| [`lib/kwic.py`](lib/kwic.py) | Sentence segmentation for the genre, and concordance-line extraction. |
| [`lib/lexical.py`](lib/lexical.py) | Tokens, log-likelihood and log ratio, matched controls, PMI. |
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

## Tests

```bash
python -m pytest
```

About a second, no data required, and run in CI on every push and pull request
([`checks.yml`](../.github/workflows/checks.yml), alongside the dashboard's own
`prettier`, `eslint` and `svelte-check`).
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
- **Notes are for humans.** Every script writes `notes/NN_name.md` summarising what it
  found, not just what it did.
