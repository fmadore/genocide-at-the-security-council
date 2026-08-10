# Licence for derived artefacts

The code in this repository is MIT-licensed; see [`LICENSE`](LICENSE). This file covers
everything the code *produces*, which is a different kind of thing and carries a different
licence.

## Three layers, three licences

| Layer | What | Licence |
|---|---|---|
| Source corpus | The UN Security Council Debates, Harvard Dataverse v6.1, DOI [10.7910/DVN/KGVSYH](https://doi.org/10.7910/DVN/KGVSYH) | CC0 1.0, by its depositors |
| Code | Everything under `scripts/`, `web/`, `tests/`, `tools/`, `config/` | MIT |
| Derived artefacts | Everything under `data/derived/` and `notes/`, plus the figures, tables and prose of the dashboard and `docs/` | **CC BY 4.0** |

Derived artefacts are the normalised corpus, the lexicon matches and counts, the series,
lexicometry and keyness tables, the concordance, the embeddings, the topic comparison, the
lemma layer, their manifests, and the generated notes — every file a pipeline step writes.

## CC BY 4.0, in short

You may share and adapt them, including commercially, provided you give appropriate credit,
link to the licence, and indicate whether changes were made. Full text:
<https://creativecommons.org/licenses/by/4.0/>.

Attribution should name this repository and its author, and — because a derived table is
worth nothing without the record it came from — the source corpus as well:

> Madore, F. (2026). *UN Security Council Debates — genocide discourse dashboard*.
> <https://github.com/fmadore/genocide-at-the-security-council>. Derived from Schoenfeld, M.,
> Eckhard, S., Patz, R., van Meegdenburg, H., & Pires, A. (2019), *The UN Security Council
> Debates* [Data set], Harvard Dataverse V6.1, <https://doi.org/10.7910/DVN/KGVSYH> (CC0).

See [`CITATION.cff`](CITATION.cff) for machine-readable metadata.

## What this licence does not do

CC BY 4.0 applies to the selection, arrangement and computation this project contributes.
It makes no claim over the underlying speech text, which is a public United Nations record
released CC0 by its depositors and stays CC0 in whatever form it reaches you. Extracting
verbatim speech from a derived artefact leaves you holding CC0 material, not CC BY
material.

Nor does the licence make a derived figure correct. `docs/PLAN.md` states which claims are
validated and which gates remain open; a number under an open gate is licensed for reuse
and not yet warranted for citation.
