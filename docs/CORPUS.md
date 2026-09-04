# Canonical corpus

This project exclusively uses **Sakamoto & Matsuoka, _The UNSC Meetings and
Speeches_, version 5.0**. The former Schoenfeld 1992–2023 corpus is no longer a
pipeline input.

| Field | Value |
|---|---|
| DOI | [10.7910/DVN/CKPTRB](https://doi.org/10.7910/DVN/CKPTRB) |
| Pinned version | 5.0, published 31 March 2026 |
| Source licence | CC0 1.0 |
| Consumed files | `speeches.tsv`, `meetings.tsv` |
| Observed coverage | 17 January 1946 to 30 December 2024 |
| Speeches | 167,642 |
| Meetings with speeches | 9,464 |
| Meeting records | 10,294 |
| Source-reported words | 87,678,254 |
| Project analytical words | 86,854,907 |

The complete pin—Dataverse file identifiers, sizes, and MD5 checksums—is in
[`config/dataset-pin.json`](../config/dataset-pin.json).
`scripts/00_fetch_data.py` rejects any file whose checksum differs.

## Why a single corpus

Using the same source throughout 1946–2024 avoids an artificial break in 1992
in OCR, speech segmentation, identifiers, affiliations, and speaker categories.
This makes longitudinal comparisons more coherent than joining two corpora
produced with different methods.

The canonical pipeline retains the text distributed by the dataset. It does not
therefore perform local OCR. A future OCR pass could provide targeted quality
control for problematic documents without silently replacing the source text.

## Adaptation to the project schema

`scripts/01_build_parquet.py` adapts the two TSV files without modifying speech
content:

- `row_id` and `record_speech` use `speech_id`;
- `record_id` and `basename` use the meeting identifier;
- `meeting_symbol` uses the source-provided `S/PV` symbol;
- `text` contains the complete speech transcript;
- `source_affiliation` preserves the raw affiliation;
- `country_org` uses `affiliation_cow` for states when available, and the raw
  affiliation otherwise;
- every original indicator is retained under a `source_*` name.

The canonical raw Parquet file is `data/derived/speeches.parquet`. The normalised
file adds counts and categories in `data/derived/speeches_norm.parquet`, after
which the lexicon step creates `data/derived/speeches_flagged.parquet`.

## Affiliation and institutional status

The former manual annotations no longer classify speakers.

`entity_type` is derived for each speech from the source indicators:

1. `source_state` becomes `state`;
2. `source_un_org` becomes `un`;
3. `source_igo` becomes `igo`;
4. `source_ngo` becomes `ngo`;
5. no indicator becomes `other`.

`un_org` takes precedence over `igo`, because UN bodies carry both indicators
in the dataset. The category is a property of an intervention: the same
affiliation label can be coded differently between rows, and the pipeline does
not overwrite it with an assumed permanent actor category.

Likewise, `speaker_group` uses `source_permanent_member` and
`source_elected_member` to produce `P5`, `E10`, `Non-member state`, `UN`, or
`Non-state`. This covers the full period, including years before the former
manually maintained membership file.

The historical `config/entities.csv` file no longer participates in either
classification. Step 11 may still use it to obtain an ISO3 code and centroid for
map display, using an exact case-insensitive match only. A missing match leaves
the actor unmapped; it does not rename the actor, change its type, or remove it
from any total.

## Validation totals

After normalisation:

| Source category | Speeches |
|---|---:|
| State | 158,603 |
| UN | 1,716 |
| Other IGO | 445 |
| NGO | 376 |
| Other / unspecified | 6,502 |

| Status at the time of the speech | Speeches |
|---|---:|
| E10 | 83,464 |
| P5 | 47,363 |
| Non-member state | 27,776 |
| Non-state | 7,323 |
| UN | 1,716 |

Lexicon v4 finds `genocid*` in **4,133 speeches**, with **7,747 occurrences**.
These figures replace the former 1992–2023 totals in every annotation-stage
population check.

## Limitations that must remain visible

- The transcripts are in English. The language actually spoken cannot be
  recovered from this distribution and remains `Unknown`.
- `source_word_count` differs slightly from the project's tokenisation. Project
  rates use only `words`, computed once by `lib.lexical`.
- `other` means “no source indicator,” not “civil society.”
- Geographic fields are optional and incomplete enrichments, never an
  aggregation key.
- The LLM runs dated August 2026 were produced against the former corpus. They
  are archived, their pointers are empty, and they must be recomputed against
  the new `occurrence_id` values.

## Citation

> Sakamoto, T., & Matsuoka, T. (2023). _The UNSC Meetings and Speeches_
> (Version 5.0) [Data set]. Harvard Dataverse.
> https://doi.org/10.7910/DVN/CKPTRB

Associated article: Sakamoto, T., Matsuoka, T., & Ito, H. (2026), “The Security
Council in its entirety: unveiling 80 years of deliberation through the UNSC
Meetings and Speeches dataset”, _Journal of Peace Research_,
[doi:10.1093/jopres/xjag018](https://doi.org/10.1093/jopres/xjag018).
