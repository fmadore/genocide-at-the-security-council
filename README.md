# Genocide at the Security Council

A corpus study of the use of **genocide** and its semantic neighbourhood at the
United Nations Security Council: when it is invoked, by whom, about what, and
with which discursive function.

The canonical corpus is now **Sakamoto & Matsuoka, _The UNSC Meetings and
Speeches_, v5.0**, covering 1946–2024. The former Schoenfeld 1992–2023 corpus has
been fully removed from the pipeline inputs.

Website: <https://fmadore.github.io/genocide-at-the-security-council/>

## Corpus

| | |
|---|---|
| Source | [Sakamoto & Matsuoka, Harvard Dataverse](https://doi.org/10.7910/DVN/CKPTRB) |
| Version | 5.0, pinned by file identifiers, sizes, and MD5 checksums |
| Source licence | CC0 1.0 |
| Coverage | 1946-01-17 to 2024-12-30 |
| Speeches | 167,642 |
| Meetings with speeches | 9,464 |
| Analytical words | 86,854,907 |
| `genocid*` (lexicon v4) | 4,133 speeches · 7,747 occurrences |

Detailed documentation of the schema, source categories, and limitations is in
[`docs/CORPUS.md`](docs/CORPUS.md).

## Migration principles

- One source covers the entire period, with no artificial splice in 1992.
- Text, segmentation, identifiers, and affiliations come from dataset v5.0.
- The `state`, `un`, `igo`, `ngo`, and `other` types come from the dataset's
  row-level indicators.
- P5 and E10 status comes from the dataset's membership indicators, rather than
  from our former manually maintained calendar.
- `config/entities.csv` no longer classifies or renames speakers. It remains an
  optional mapping enrichment based on exact matches.
- Former LLM runs are archived but disabled. They cannot be joined to the new
  identifiers and must be recomputed.

## Reproducing the analysis

Python 3.12 x64 is required (`pyarrow` must be available).

```bash
python -m pip install --require-hashes -r requirements.lock
make payload
```

The deterministic pipeline is declared in [`Makefile`](Makefile):

```text
00_fetch_data.py       verifies/downloads speeches.tsv and meetings.tsv
01_build_parquet.py    adapts the source to the canonical schema
02_normalise.py        counts words and attaches source categories
03_lexicon.py          applies the lexicon
04_series.py           rebuilds the 1946–2024 series
05_lexical.py          computes collocations, keyness, and the lexical network
08_kwic.py             builds the concordance
09_export_speeches.py  exports meeting-level reading files
11_countries.py        builds affiliation aggregates
12_speaker_keyness.py  computes matched affiliation-level keyness
13_gold_sample.py      creates a new human-annotation sample
15_usage.py            builds the LLM layer, only after a new run exists
17_frames.py           extracts grammatical constructions, with or without LLM data
export_web.py          assembles and validates the dashboard payload
```

Steps 06, 07, and 10 (embeddings, topics, and lemmatisation) remain optional and
require the environment described in [`docs/CLUSTER.md`](docs/CLUSTER.md).
Step 14 runs pinned open-weights models on university hardware and is never run by CI.

## Produced data

Raw and derived data are gitignored and reproducible:

```text
data/raw/                         unchanged v5.0 TSV files
data/derived/speeches.parquet     canonical source adaptation
data/derived/speeches_norm.parquet
data/derived/speeches_flagged.parquet
data/derived/{series,lexical,kwic,countries,frames,usage}/
web/static/data/                  dashboard payload
```

Each step writes a manifest recording its inputs, hashes, software versions,
and outputs. Validation rejects incorrect population totals, checksum drift,
and annotation runs built against a different occurrence population.

## Verification

```bash
python -m ruff check scripts tests
python -m pytest
npm --prefix web ci
npm --prefix web run lint
npm --prefix web run check
npm --prefix web run build
```

## LLM annotations

The four historical runs under
[`model_annotations/genocide/runs/`](model_annotations/genocide/runs/) remain
versioned for provenance. The `current_run.txt` and `comparison_run.txt`
pointers are empty after migration. A new run must cover all 7,747 current
occurrences; see [`model_annotations/README.md`](model_annotations/README.md)
and [`scripts/README.md`](scripts/README.md).
The next published and comparison instruments are `Qwen/Qwen3.8-27B` and
`deepseek-ai/DeepSeek-V4-Flash-0731` (with `google/gemma-4-31B-it` as the recorded
fallback), served locally through vLLM at pinned Hugging Face revisions.

## Licence and citation

The code is licensed under MIT. Derived artefacts are licensed under CC BY 4.0;
the source corpus remains CC0. See [`LICENSE-DATA.md`](LICENSE-DATA.md) and
[`CITATION.cff`](CITATION.cff).
