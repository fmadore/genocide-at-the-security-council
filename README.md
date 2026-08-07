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
| Normalisation & country crosswalk | ⬜ next |
| Lexical / topic / embedding analysis | ⬜ |
| Dashboard (SvelteKit) | ⬜ |
| LLM structured extraction | ⬜ |

---

## Quick start

Requires **Python 3.12 (x64)** with `pandas` and `pyarrow`.

```bash
python scripts/00_fetch_data.py      # ~500 MB from Harvard Dataverse into data/raw/
python scripts/01_build_parquet.py   # → data/derived/speeches.parquet (131 MB)
```

The build asserts the corpus against the published codebook and exits non-zero on any
mismatch. A clean run reports:

```
106,302 speeches | 6,595 meetings | 1992-01-06 to 2023-12-30 | 66,392,703 tokens
```

Everything downstream reads `data/derived/speeches.parquet` and never touches the raw
files again.

---

## Layout

```
├── config/              Versioned analysis inputs — edit these, not the scripts
│   └── lexicon.yml        Genocide lexicon: patterns, tiers, discursive registers
├── data/                Gitignored. Rebuilt from the DOI by scripts/00 and 01.
│   ├── raw/               As downloaded from Dataverse — never modified
│   ├── interim/           Intermediate artefacts
│   └── derived/           speeches.parquet, meetings.parquet, analysis outputs
├── docs/
│   ├── CORPUS.md          Corpus documentation: variables, traps, first findings
│   ├── PLAN.md            Five-phase action plan
│   └── reference/         Codebook PDF, companion paper
├── notes/               Gitignored. Markdown findings notes emitted by each script.
├── scripts/             Numbered, idempotent pipeline steps — see scripts/README.md
│   └── lib/paths.py       One definition of where everything lives
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
