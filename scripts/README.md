# Pipeline

Numbered steps, run in order. Each is **idempotent** — safe to re-run — reads from
`data/`, writes to `data/derived/` and drops a Markdown findings note in `notes/`.

The numbered scripts are thin orchestrators. All the logic lives in [`lib/`](lib), which
is importable and unit-tested, so a step reads as a sequence of named operations and the
operations themselves can be checked without a 131 MB parquet.

Analysis inputs that are meant to be edited by hand live in [`../config/`](../config/);
one-off maintenance helpers live in [`../tools/`](../tools).

Use the x64 Python that has `pyarrow`:

```
C:/Users/frede/AppData/Local/Programs/Python/Python312/python.exe
```

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
| 08 | `08_kwic.py` | `speeches_flagged.parquet` | `derived/kwic/*.json` | ✅ |
| 09 | `09_export_speeches.py` | `speeches_flagged.parquet`, `meetings.parquet` | `web/static/data/speeches/*.json` | ✅ |
| — | `export_web.py` | `derived/{series,lexical,kwic}/` | `web/static/data/` | ✅ |

Topics, embeddings and LLM extraction are research proposals, not missing pipeline steps.
Their evaluation gates are specified in [`../docs/PLAN.md`](../docs/PLAN.md); they should
receive script numbers only if those gates are approved.

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
| [`lib/kwic.py`](lib/kwic.py) | Sentence segmentation for the genre, and concordance-line extraction. |
| [`lib/lexical.py`](lib/lexical.py) | Tokens, log-likelihood and log ratio, matched controls, PMI. |

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
known answers.

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
