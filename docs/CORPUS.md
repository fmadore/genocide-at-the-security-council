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

## Government-change datasets: an evaluation, not an adoption

The site reads a speech as a State speaking. It is a government speaking, and the
difference is sometimes the finding: the characterisation of the Rwandan killings
changes when the government changes, and read as one State's position over time
that reversal is a puzzle it need not be. Roadmap item R15 records the
distinction and defers the overlay. This section is the evaluation R15 asks for.
**No dataset is adopted here.** Any government-change overlay must be
preregistered as a new analysis, under the rule in
[`PLAN.md`, section 6](PLAN.md#6-lexical-and-statistical-follow-up), and its
coverage must be stated against the corpus's own span before anything is joined.

### The join key the corpus already carries

`source_cow_ccode` is present on **158,563 of 167,642 rows**, 94.58% of the
corpus, over **200 distinct** Correlates of War codes. The field is stored as a
string of a float — Rwanda is `'517.0'`, not `517` — so a merge against an
integer-typed leader table matches no row at all and returns an empty frame.
That failure is loud, and it is the only one below that is.

The 9,079 rows carrying no code are not distributed as the corpus is. By speaker
type they are very nearly the non-state rows: 6,502 `other`, 1,716 `un`, 445
`igo`, 376 `ngo`, and 40 rows typed `state`. By decade they concentrate in the
recent period.

| Decade | Rows without a COW code | Rows | Share |
|---|---:|---:|---:|
| 1940s | 397 | 11,461 | 3.46% |
| 1950s | 240 | 7,190 | 3.34% |
| 1960s | 178 | 11,143 | 1.60% |
| 1970s | 308 | 12,345 | 2.49% |
| 1980s | 333 | 11,115 | 3.00% |
| 1990s | 211 | 13,043 | 1.62% |
| 2000s | 1,972 | 29,038 | 6.79% |
| 2010s | 3,430 | 45,630 | 7.52% |
| 2020s | 2,010 | 26,677 | 7.53% |

An inner join on the code therefore drops the Secretary-General, the briefers and
the civil-society speakers, and drops proportionally more of them the closer the
corpus comes to the present. The effect is sharper on this project's subject: of
the 4,133 speeches carrying `genocid*`, **558 (13.50%)** have no COW code, two
and a half times the corpus rate, because the officials who report atrocities to
the Council are the uncoded rows. The 40 `state` rows without a code are a short
list of names the source did not resolve — East Timor (11), the Turkish Federated
State of Cyprus and of Kibris (10), five rows labelled `USA`, four labelled
`India or Netherland`, and a tail of orthographic variants of states coded
elsewhere.

Every figure in this section that concerns the corpus was computed with pandas
over `data/derived/speeches_flagged.parquet`; upstream facts about each candidate
were read from that project's own pages on 7 September 2026 and are cited below.

### The five candidates

Coverage is measured against the corpus's observed span, 17 January 1946 to 30
December 2024. A blanked share is the number of corpus speeches falling outside
a dataset's coverage, over the corpus denominator of 167,642.

| Dataset | Unit and country key | Coverage | Blanked, recent end | Blanked, early end | Licence |
|---|---|---|---:|---:|---|
| Archigos 4.1 | leader spell; `ccode` on the Gleditsch–Ward state list | 1875 – 31 December 2015 | 49,633 (29.61%) | none | none stated |
| CHISOLS 5.0 | state-year and leader; COW code | 1919 – 2018 | 32,940 (19.65%) | none | none stated |
| WhoGov 4 | cabinet member-year; ISO alpha-3 | 1966 – 2025 | none | 24,792 (14.79%) | none stated |
| REIGN | leader-month; `cowcode` | January 1950 – August 2021 | 24,164 (14.41%) | 11,461 (6.84%) | none stated |
| V-Dem 16 | country-year; `COWcode` | 1789 – 2025 | none | none | CC BY-SA 4.0 |

**Archigos** stops nine years short of the corpus, on 31 December 2015, and its
last release is version 4.1 of February 2016. It also does not key on what R15
assumed it keys on. Its codebook says the project employs "the CCODE and IDACR
variables from the Correlates of War project", and in the same document says the
universe of cases is Gleditsch and Ward's compilation of independent states;
`peacesciencer`, which redistributes the data, names the field `gwcode` and warns
that the codes are not Correlates of War state codes. The two lists share a
numeric range and agree on most entries, so a merge on `source_cow_ccode` would
succeed on nearly every row and misalign on the successions where the identity of
the State is itself contested — German unification, the Yugoslav succession. A
join that fails on 100% of rows is a bug report; a join that fails on the handful
of rows a genocide corpus is actually about is a finding.

**CHISOLS** is the one candidate that measures the mechanism R15 names. It does
not flag a change of occupant; it flags the leadership changes that bring to
power a leader whose support is drawn from different societal groups than the
predecessor's, which is exactly the Rwandan case and the reason the
characterisation moves with it. It keys the state-year on the COW code the corpus
already carries, and it ships in two shapes, state-year and leader. Version 5.0
covers 1919–2018 for states above 500,000 population. Six years short at the
recent end is 32,940 speeches, 19.65% of the corpus, and the raw share understates
the loss because the corpus's own volume rises steeply across the blank: 3,185
speeches in 2013 against 7,210 in 2022, 7,816 in 2023 and 7,497 in 2024.

**WhoGov** is the only candidate that has been extended into the corpus's final
years — version 4, released June 2026, runs 1966–2025 over 60,458 cabinet members
in 177 countries — and it is the one that cannot be joined on the corpus's key at
all. It identifies countries by alpha-3 ISO code, so a join needs a crosswalk from
`source_cow_ccode`, or it needs `iso3`, which this document already records as an
optional and incomplete enrichment and never an aggregation key. It also starts in
1966 and so blanks the corpus's first twenty years, 24,792 speeches or 14.79%, the
period in which the Council's vocabulary for mass violence was being set. Cabinet
composition is in any case a wider object than the government-change question:
it answers who holds which portfolio, not whether the government accusing is the
government accused.

**REIGN** has the right grain and has stopped. Its leader-month resolution is the
finest of the five and the only one that matches a Council debate, which happens
on a day rather than in a year, and it carries a Correlates of War code directly.
Collection ceased in August 2021 and the dataset is archived; the last month
blanks 24,164 speeches, 14.41%, and the January 1950 start blanks a further
11,461, 6.84%. A dataset that has stopped has a blank span that grows with every
year the corpus is extended, which makes it the weakest of the five as a
foundation for anything intended to be maintained.

**V-Dem** spans the corpus with room at both ends, carries `COWcode`, is released
annually — version 16 in March 2026, covering 1789 through 2025 for 202 countries
— under CC BY-SA 4.0 with a versioned DOI. It is also the candidate that answers
a different question. It measures regime characteristics at country-year: it
would report that Rwanda's scores moved, not that the government being accused
had been replaced by the government doing the accusing. Country-year is coarser
than the corpus, which resolves to the day, and a regime index is a covariate
rather than the treatment R15 describes.

### Which one, and still not adopted

The most promising candidate is **CHISOLS**, because it is the only one whose
measured quantity is the mechanism R15 states rather than a proxy for it, and
because it keys on the code the corpus already carries. Its cost is a 19.65% blank
at the recent end, which is not a reason to reject it and is a reason no figure
built on it may be published without that share on its face. **V-Dem** is the
natural second, not as a substitute but as the covariate layer, because it alone
spans 1946–2024, and because its licence, citation and annual versioned DOI make
it the only candidate this project could pin as hard as it pins its corpus.
Neither is adopted, no join is written, and the acceptance test R15 sets is met by
this section rather than by any code: nothing has been joined, and the coverage of
each candidate is now stated against the corpus's own span.

### The individual level is not proposed

`speaker` holds **10,813 distinct name strings** and no stable person identifier.
Most are a surname behind an honorific — `Mr. Churkin` on 999 rows, `Mr. Nebenzia`
on 932, `Mr. Lavrov` on 919 — 1,080 rows carry `n.a.`, and the strings are not
stable even for one person: case-folding alone collapses the 10,813 to 10,251, so
562 of them are casing variants of another string in the same column. A name
string is therefore neither unique to a person nor constant for one. Anything
about the circulation of particular diplomats — the delegates who specialise in
this subject and reappear across situations and decades — needs name
disambiguation first, and that is its own project, not a field on this corpus.

### Sources consulted

> Goemans, H. E., Gleditsch, K. S., & Chiozza, G. (2016). _Archigos: A Data Set on
> Leaders 1875–2015_, version 4.1.
> https://www.rochester.edu/college/faculty/hgoemans/data.htm

> Mattes, M., Leeds, B. A., & Matsumura, N. (2016). "Measuring change in source of
> leader support: The CHISOLS dataset", _Journal of Peace Research_ 53(2),
> 259–267. Data version 5.0. http://www.chisols.org/

> Nyrup, J., & Bramwell, S. (2020). "Who Governs? A New Global Dataset on Members
> of Cabinets", _American Political Science Review_ 114(4), 1366–1374. WhoGov
> version 4, June 2026.
> https://politicscentre.nuffield.ox.ac.uk/whogov-dataset/

> Bell, C. (2016). _The Rulers, Elections, and Irregular Governance Dataset
> (REIGN)_. OEF Research. Collection ceased August 2021.
> https://oefdatascience.github.io/REIGN.github.io/

> Coppedge, M., Gerring, J., Knutsen, C. H., et al. (2026). _V-Dem
> [Country-Year/Country-Date] Dataset v16_. Varieties of Democracy Project.
> [doi:10.23696/vdemds26](https://doi.org/10.23696/vdemds26)

## Citation

> Sakamoto, T., & Matsuoka, T. (2023). _The UNSC Meetings and Speeches_
> (Version 5.0) [Data set]. Harvard Dataverse.
> https://doi.org/10.7910/DVN/CKPTRB

Associated article: Sakamoto, T., Matsuoka, T., & Ito, H. (2026), “The Security
Council in its entirety: unveiling 80 years of deliberation through the UNSC
Meetings and Speeches dataset”, _Journal of Peace Research_,
[doi:10.1093/jopres/xjag018](https://doi.org/10.1093/jopres/xjag018).
