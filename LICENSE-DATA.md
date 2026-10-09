# Licence for derived artefacts

The code in this repository is MIT-licensed; see [`LICENSE`](LICENSE). This file covers
everything the code *produces*, which is a different kind of thing and carries a different
licence.

## Three layers, three licences

| Layer | What | Licence |
|---|---|---|
| Source corpus | Sakamoto & Matsuoka, *The UNSC Meetings and Speeches*, Harvard Dataverse v5.0, DOI [10.7910/DVN/CKPTRB](https://doi.org/10.7910/DVN/CKPTRB) | CC0 1.0, by its depositors |
| Code | Everything under `scripts/`, `web/`, `tests/`, `tools/`, `config/` | MIT |
| Derived artefacts | Everything under `data/derived/` and `notes/`, plus the figures, tables and prose of the dashboard and the project's own prose in `docs/` | **CC BY 4.0** |

Derived artefacts are the normalised corpus, the lexicon matches and counts, the series,
lexicometry and keyness tables, the concordance, the embeddings, the topic comparison, the
lemma layer, their manifests, and the generated notes — every file a pipeline step writes.

Material by other authors that the documentation quotes, cites or links to — papers,
codebooks, dataset descriptions — is not covered by this licence. It stays under the terms
its authors chose, and the repository links to it at its source rather than redistributing
it.

## CC BY 4.0, in short

You may share and adapt them, including commercially, provided you give appropriate credit,
link to the licence, and indicate whether changes were made. Full text:
<https://creativecommons.org/licenses/by/4.0/>.

Attribution should name this repository and its author, and — because a derived table is
worth nothing without the record it came from — the source corpus as well:

> Madore, F. (2026). *Genocide at the Security Council*.
> <https://github.com/fmadore/genocide-at-the-security-council>. Derived from Sakamoto, T.,
> & Matsuoka, T. (2026), *The UNSC Meetings and Speeches* (Version 5.0) [Data set], Harvard
> Dataverse, <https://doi.org/10.7910/DVN/CKPTRB> (CC0).

Harvard Dataverse's own suggested citation for the corpus gives the year it was first
published, 2023, followed by "V5"; either form identifies the same pinned version.

See [`CITATION.cff`](CITATION.cff) for machine-readable metadata.

## What this licence does not do

CC BY 4.0 applies to the selection, arrangement and computation this project contributes.
It makes no claim over the underlying speech text, which is a public United Nations record
released CC0 by its depositors and stays CC0 in whatever form it reaches you. Extracting
verbatim speech from a derived artefact leaves you holding CC0 material, not CC BY
material.

Nor does the licence make a derived figure correct. [`docs/CLAIMS.md`](docs/CLAIMS.md)
states what each kind of figure rests on and whether it is validated, and `docs/PLAN.md`
which gates remain open; a number under an open gate is licensed for reuse and not yet
warranted for citation.
