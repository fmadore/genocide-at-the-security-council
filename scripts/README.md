# Pipeline

Numbered steps, run in order. Each is **idempotent** — safe to re-run — reads from
`data/`, writes to `data/derived/` and drops a Markdown findings note in `notes/`.

Shared configuration lives in [`lib/paths.py`](lib/paths.py); analysis inputs that are
meant to be edited live in [`../config/`](../config/).

Use the x64 Python that has `pyarrow`:

```
C:/Users/frede/AppData/Local/Programs/Python/Python312/python.exe
```

## Steps

| # | Script | Reads | Writes | State |
|---|---|---|---|---|
| 00 | `00_fetch_data.py` | Dataverse API | `data/raw/` | ✅ |
| 01 | `01_build_parquet.py` | `data/raw/` | `data/derived/speeches.parquet`, `meetings.parquet` | ✅ |
| 02 | `02_normalise.py` | `speeches.parquet` | `speeches_norm.parquet`, `config/entities.csv` | ⬜ |
| 03 | `03_lexicon.py` | `speeches_norm.parquet`, `config/lexicon.yml` | `speeches_flagged.parquet` | ⬜ |
| 04 | `04_series.py` | `speeches_flagged.parquet` | `derived/series/*.json` | ⬜ |
| 05 | `05_lexical.py` | `speeches_flagged.parquet` | `derived/lexical/*.json` | ⬜ |
| 06 | `06_topics.py` | `speeches_flagged.parquet` | `derived/topics/*.json` | ⬜ |
| 07 | `07_embed.py` | `speeches_flagged.parquet` | `derived/embeddings/*.json` | ⬜ |
| 08 | `08_kwic.py` | `speeches_flagged.parquet` | `derived/kwic/*.json` | ⬜ |
| 09 | `09_export_speeches.py` | `speeches_norm.parquet` | `web/static/data/speeches/*.json` | ⬜ |
| 10 | `10_llm_open.py` | sample of 200 | `derived/llm/open/*.json` | ⬜ |
| 11 | `11_llm_extract.py` | `docs/CODEBOOK.md` + subset | `derived/llm/extractions.parquet` | ⬜ |
| 12 | `12_llm_validate.py` | extractions + gold standard | `notes/12_validation.md` | ⬜ |

See [`../docs/PLAN.md`](../docs/PLAN.md) for what each step is meant to establish.

## Conventions

- **Validate loudly.** A script that cannot assert its output is correct should exit
  non-zero rather than write a plausible-looking artefact. `01` asserts row count, token
  sum, join completeness and date parsing against the published codebook.
- **No magic constants in scripts.** Lexicons, aliases and thresholds live in `config/`
  under version control, so a changed number is a reviewable diff.
- **Record parameters in outputs.** Topic models and LLM runs write their settings
  alongside their results; a figure that cannot be traced to its parameters is not usable
  in a publication.
- **Notes are for humans.** Every script writes `notes/NN_name.md` summarising what it
  found, not just what it did.
