# UN Security Council Debates — genocide discourse dashboard

An interactive dashboard over the **UN Security Council Debates** corpus (1992–2023,
106,302 speeches), studying how the word **genocide** and its semantic neighbourhood have
been used at the Council: when, by whom, about what, and to what end.

The dashboard will be published openly as a static site. This repository holds the data
pipeline, the analysis scripts and the web application.

---

## Status

| Stage | State |
|---|---|
| Corpus documentation | ✅ [`docs/CORPUS.md`](docs/CORPUS.md) |
| Action plan | ✅ [`docs/PLAN.md`](docs/PLAN.md) |
| Data pipeline — build & validate | ✅ `scripts/00`, `scripts/01` |
| Normalisation & country crosswalk | ✅ `scripts/02` · [`config/entities.csv`](config/entities.csv) |
| Lexicon flagging & precision audit | ✅ `scripts/03` (audit sample awaiting a human verdict) |
| Series / lexicometry / topics / KWIC | ⬜ next — `scripts/04`–`08` |
| Dashboard (SvelteKit) | ⬜ |
| LLM structured extraction | ⬜ |

---

## Quick start

Requires **Python 3.12 (x64)** — on Windows, the installation that has a `pyarrow` wheel.

```bash
python -m pip install -r requirements.txt
```

```bash
python scripts/00_fetch_data.py      # ~500 MB from Harvard Dataverse into data/raw/
python scripts/01_build_parquet.py   # → data/derived/speeches.parquet (131 MB)
python scripts/02_normalise.py       # → speeches_norm.parquet    (aliases, entities, groups)
python scripts/03_lexicon.py         # → speeches_flagged.parquet (lexicon counts)
```

Each step asserts its output and exits non-zero on any mismatch rather than leaving a
plausible-looking artefact behind. A clean `01` reports:

```
106,302 speeches | 6,595 meetings | 1992-01-06 to 2023-12-30 | 66,392,703 tokens
```

Everything downstream reads the parquet and never touches the raw files again.
Findings notes land in `notes/`; see [`scripts/README.md`](scripts/README.md) for the
module layout.

```bash
python -m pytest
```

85 tests, no data required — including integrity checks on the hand-edited files in
`config/`. These and `ruff check` run on every push and pull request via
[`.github/workflows/checks.yml`](.github/workflows/checks.yml), so a bad edit to a config
file fails in CI rather than halfway through someone's pipeline run.

---

## Layout

```
├── .github/workflows/   checks.yml (ruff + pytest) · deploy.yml (Pages)
├── config/              Versioned analysis inputs — edit these, not the scripts
│   ├── lexicon.yml           Genocide lexicon: patterns, tiers, discursive registers
│   ├── entities.csv          country_org → type · ISO3 · UN group · centroid
│   ├── country_aliases.csv   Labels denoting the same speaker
│   └── council_membership.csv  P5 and E10 terms, 1992-2023
├── data/                Gitignored. Rebuilt from the DOI by scripts/00 and 01.
│   ├── raw/               As downloaded from Dataverse — never modified
│   ├── interim/           Intermediate artefacts, reference downloads, audit samples
│   └── derived/           speeches.parquet and the normalised/flagged tables
├── docs/
│   ├── CORPUS.md          Corpus documentation: variables, traps, first findings
│   ├── PLAN.md            Five-phase action plan
│   ├── VALIDATION.md      Readings to confirm against the original S/PV PDFs
│   └── reference/         Codebook PDF, companion paper
├── notes/               Gitignored. Markdown findings notes emitted by each script.
├── scripts/             Numbered, idempotent pipeline steps — see scripts/README.md
│   └── lib/               The tested modules the steps orchestrate
├── tests/               pytest; runs against the real config/, needs no data
├── tools/               One-off maintenance helpers (entity crosswalk bootstrap)
└── web/                 SvelteKit dashboard (not yet scaffolded)
```

---

## The corpus

| | |
|---|---|
| **Source** | Schoenfeld, Eckhard, Patz, van Meegdenburg & Pires — [doi:10.7910/DVN/KGVSYH](https://doi.org/10.7910/DVN/KGVSYH), v6.1 |
| **Licence** | **CC0 1.0** — public domain |
| **Coverage** | 1992-01-06 → 2023-12-30 · 106,302 speeches · 6,582 meetings · 66.4 M tokens |
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

- **Delivery language is recoverable for 42,765 speeches (40.2%)**, read off the
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

Counting on the speech body rather than the raw text reproduces **all fourteen** figures
published in [`docs/CORPUS.md` §8](docs/CORPUS.md) exactly, `genocid*` among them at
3,273 speeches and 6,092 occurrences. That confirms stripping the form of address removes
no real words. Three terms exceed their documented *occurrence* count because the lexicon
matches an acronym the reconnaissance scan did not (`ICC`, `R2P`, `shoah`); the
arithmetic is set out in [`docs/VALIDATION.md`](docs/VALIDATION.md).

---

## Citation

The corpus:

> Schoenfeld, M., Eckhard, S., Patz, R., van Meegdenburg, H., & Pires, A. (2019).
> *The UN Security Council Debates* [Data set]. Harvard Dataverse, V6.1.
> <https://doi.org/10.7910/DVN/KGVSYH>

This repository: see [`CITATION.cff`](CITATION.cff).

---

## Licence

Corpus data is CC0 (Harvard Dataverse). A licence for the code and derived artefacts in
this repository is **not yet set** — see the open items in [`docs/PLAN.md` §7](docs/PLAN.md).
