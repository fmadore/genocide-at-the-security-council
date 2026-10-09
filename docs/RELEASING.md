# Releasing a citable version

The website is rebuilt on every push to `main`, so a link to it points at whatever
was built last. A citation needs something that does not move: a numbered release
whose files are archived with a DOI. This guide explains how to make one.

Nothing has been released yet. The only git tag, `semantic-2026-09-11`, carries a
data file the build downloads (`config/semantic-release.json`); it is not a
version of the study.

## What the first release is

The first release is **v0.1 — unvalidated preview**. The name states what it
contains: the computed corpus measures, plus model labels that no human has yet
checked. It does not pass the release gate in [PLAN.md](PLAN.md#13-release-gate),
which requires the human audit first. A later release, after the gold sample is
coded and the evaluation plan applied, can drop the word "unvalidated".

Whether and when to cut it is FM's decision.

## What a release contains

| File | What it holds | How it is made |
|---|---|---|
| Source archive | The repository at the tagged commit: code, configuration, documentation, the committed human and model annotations | Made by GitHub from the tag |
| `derived-tables-v0.1.zip` | The analytical tables and their manifests, as `make payload` writes them under `data/derived/` | Built from a clean checkout (below) |
| `site-v0.1.zip` | The complete built website, data included, as it was on the release date | `web/build/` after the build |
| `gold-sample-v0.1.zip` (proposed) | The drawn gold sample: `data/interim/genocide_gold_*.csv`, including the blinded packet and the design | Written by step 13 during `make payload` |

The derived tables are not in git (they are rebuilt from the corpus), so the
source archive alone does not contain them. That is why they are attached as a
separate file.

Two choices for FM:

- **The speech text.** `data/derived/speeches.parquet`, `speeches_norm.parquet`
  and `speeches_flagged.parquet` hold the full text of every speech. The text is
  CC0 and can be rebuilt from Harvard Dataverse, and the files are large. Leave
  them out of `derived-tables` unless the deposit is meant to serve as a second
  source for the corpus if Dataverse is unreachable (review item A9).
- **The gold sample.** Archiving the drawn sample freezes it before coding
  starts; see [EVALUATION_PLAN.md](EVALUATION_PLAN.md). This is proposed, not
  decided.

## Before the first release: switch on Zenodo

Zenodo, run by CERN, archives a GitHub release and gives it a DOI. The link
between the repository and Zenodo has to be made by the repository owner, in his
own accounts; nobody else can do it.

1. Sign in to <https://zenodo.org> with the GitHub account that owns
   `fmadore/genocide-at-the-security-council`.
2. Open the GitHub page of the Zenodo account settings and switch the
   repository on.
3. From then on, every **published** GitHub release becomes a new version of
   one Zenodo record. This includes releases made only to carry a data file,
   like `semantic-2026-09-11`. Before the next such data release, decide
   whether it should be archived; if not, switch the integration off for the
   time it takes to publish it.

Zenodo reads the record's title, authors, licence, keywords and related works
from [`.zenodo.json`](../.zenodo.json) at the root of the repository. It leaves
out the version and the DOI on purpose: Zenodo takes the version from the tag
and mints the DOI itself.

**Check this on the first release.** The integration archives the source archive
of the tag. Files attached to the GitHub release may not be copied into the
Zenodo record. If they are not, upload `derived-tables`, `site` and the gold
sample to a second Zenodo record by hand (upload type "dataset", same creators,
licence CC BY 4.0), and link the two records to each other with a related
identifier.

## Cutting the release, step by step

Work in a fresh clone, not in your working copy. A clean build starts from an
empty `data/`, and `make clean` in a working copy deletes files the build cannot
recreate, such as the cluster embeddings (review item B10).

1. **Check that `main` is healthy.** The Checks workflow passed on the commit to
   be released, and the deploy of that commit succeeded.
2. **Build from a clean checkout of that commit.**

   ```bash
   git clone https://github.com/fmadore/genocide-at-the-security-council.git release-v0.1
   cd release-v0.1
   python -m pip install --require-hashes -r requirements.lock
   python scripts/fetch_semantic.py
   make payload
   python scripts/export_web.py --check
   npm --prefix web ci
   npm --prefix web run build
   ```

3. **Package the files** listed above: zip `data/derived/` (with or without the
   speech parquets, as decided), `web/build/`, and, if adopted, the gold sample
   files.
4. **Update the citation file.** In [`CITATION.cff`](../CITATION.cff), add
   `version: "0.1.0"` and `date-released:` with the release date. Commit this
   to `main` before tagging, so the archived copy carries it.
5. **Tag and publish.**

   ```bash
   git tag -a v0.1.0 -m "v0.1 — unvalidated preview"
   git push origin v0.1.0
   gh release create v0.1.0 --title "v0.1 — unvalidated preview" \
     --notes-file release-notes.md \
     derived-tables-v0.1.zip site-v0.1.zip gold-sample-v0.1.zip
   ```

   GitHub refuses a release file of 2 GiB or more; split a larger zip.
6. **Write the release notes** (`release-notes.md`) in plain words:
   - what the release is, and that its model labels are unvalidated;
   - the corpus: Sakamoto and Matsuoka v5.0, DOI 10.7910/DVN/CKPTRB, pinned by
     the checksums in `config/dataset-pin.json`;
   - the model run shown: `2026-09-08-qwen-131k`, partial (4,097 of 4,133
     speeches), prompt v3, and that the Gemma comparison is not included unless
     it has been published by then;
   - the gold sample's state (on 8 October 2026: 0 of 469 rows coded);
   - the commit, and the `analysis_hash` of the main artefacts, read from the
     `meta` block of `series/annual.json`, `kwic/genocide.json` and
     `usage/usage.json`;
   - a pointer to [CLAIMS.md](CLAIMS.md) for what each figure rests on.
7. **Record the DOI.** When Zenodo has minted the DOI, add `doi:` to
   `CITATION.cff` and a line to the README's "Licence and citation" section.
   Zenodo gives two DOIs: one for this version, and a "concept" DOI that always
   resolves to the latest version. Cite the version DOI in a publication.
8. **Save key pages to the Internet Archive** (next section).

## Saving pages to the Internet Archive

The Wayback Machine keeps dated copies of web pages. For each page below, open
<https://web.archive.org/save>, paste the address, and save it. Keep the dated
capture links in the release notes.

- <https://fmadore.github.io/genocide-at-the-security-council/>
- `…/chronology/`, `…/language/`, `…/actors/`, `…/concordance/`, `…/usage/`,
  `…/semantic/` and `…/methods/` under the same address.

Then open each capture and check that the figures appear. The site loads its
data after the page itself, so a capture can lack figures. The site zip in the
release is the complete copy; the captures are a convenience for readers.

## After a release

- A new release is needed whenever a published figure changes in a way a reader
  could cite: a new model run, coded gold rows, a lexicon or corpus change.
- Never move or delete a tag once Zenodo has archived it. Correct a mistake with
  a new release.
