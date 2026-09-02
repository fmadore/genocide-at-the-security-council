# UN Security Council Debates — corpus notes

Working notes on the *UN Security Council Debates* dataset (Schoenfeld, Eckhard, Patz,
van Meegdenburg & Pires), in preparation for an interactive dashboard on the use of the
word **genocide** in the Security Council.

---

## 1. Identification

| | |
|---|---|
| **Title** | The UN Security Council Debates |
| **Authors** | Mirco Schoenfeld (U. Bayreuth, [ORCID](https://orcid.org/0000-0002-2843-3137)) · Steffen Eckhard (U. Konstanz) · Ronny Patz (LMU Munich) · Hilde van Meegdenburg (Leiden) · Antonio Pires (UF Pernambuco) |
| **Repository** | Harvard Dataverse — [doi:10.7910/DVN/KGVSYH](https://doi.org/10.7910/DVN/KGVSYH) |
| **Version used** | **6.1**, released 19 February 2025 |
| **Licence** | **CC0 1.0** (public domain) — no reuse restrictions |
| **Primary source** | `S/PV.*` verbatim records, <https://research.un.org/en/docs/sc/quick/meetings/> |
| **Companion paper** | Schoenfeld *et al.* (2025), *The UN Security Council debates 1992-2023*, [arXiv:1906.10969v3](https://arxiv.org/abs/1906.10969) (cs.DL, 17 March 2025) |
| **Contact** | mirco.schoenfeld@tum.de |
| **Related dataset** | [UNSC debates on Afghanistan](https://doi.org/10.7910/DVN/OM9RG8) |

> ⚠️ Dataverse's `timePeriodCovered` field reads **1995-01-06 → 2020-12-29**. This is stale
> metadata that was not updated for v6.1. The actual coverage, verified against the data,
> is **1992-01-06 → 2023-12-30**; the codebook and the paper both confirm 1992-2023. Do not
> cite the Dataverse period.

**Recommended citation**

> Schoenfeld, M., Eckhard, S., Patz, R., van Meegdenburg, H., & Pires, A. (2019).
> *The UN Security Council Debates* [Data set]. Harvard Dataverse, V6.1.
> <https://doi.org/10.7910/DVN/KGVSYH>

---

## 2. Files

| File | Size | Contents |
|---|---:|---|
| `speeches.tar` | 474 MB | 106,302 `.txt` files, one per speech, under `speeches/` |
| `speaker.tsv` | 33 MB | Per-**speech** metadata (26 columns) |
| `meta.tsv` | 605 KB | Per-**meeting** metadata (9 columns) |
| `docs.RData` | 119 MB | R object: full texts (convertible to a `quanteda` corpus) |
| `docs_meta.RData` | 2.1 MB | R object: `speaker.tsv` and `meta.tsv` merged |
| `Codebook.pdf` | 105 KB | Variable documentation (January 2025) |

The `.RData` files are redundant with the TSVs + tar. **The pipeline uses only the TSVs and
the tar** — no R dependency.

The local folder also holds the paper: `1906.10969v3.pdf` (+ `1906.10969v3.txt`).

---

## 3. Structure and production chain

The verbatim records are two-column PDFs. The authors' pipeline:

1. **Reflow** the two-column layout with `k2pdfopt` → high-resolution image;
2. **OCR** with `tesseract` for older documents; for recent, natively digital records, a
   direct **PDF → DOCX** export instead (no OCR);
3. **Cleanup**: ligatures, em-dashes and non-ASCII spaces removed;
4. **Segmentation** into speeches by regex on the forms of address (`The President:`,
   `Mr. Levitte (France) (spoke in French):`, `Ms. …`, plus `Sir`, `Baron`, `Sheikh`,
   `Nana`, `Dato` — 28 markers in total);
5. **Attribution**: country taken from the participants list on page 1 (separately OCR'd
   with dedicated settings); for guests absent from that list, extracted from the
   parenthetical at the start of the speech, or **entered manually**.

Consecutive speeches by the same speaker are merged (the case of an interposed vote). Over
500 official communiqués were excluded.

**Methodological consequences.** `country_org` attribution is semi-automatic and therefore
uneven: highly reliable for Council members, shakier for invited speakers. OCR noise is
real and visible (`interpretation fron Arabic`, `nredecessor`, `senocide`), concentrated in
the 1990s and early 2000s. Any lexical measurement must account for it: counts are
**floors**, not exact values.

---

## 4. Verified volumetrics

| Measure | Codebook / paper | Verified against the data |
|---|---:|---:|
| Speeches | 106,302 | **106,302** ✅ |
| Meetings | 6,233 | **6,582** distinct `S/PV.*` symbols ⚠️ |
| Documents (resumptions included) | — | **6,595** |
| Tokens (codebook) | 66,392,703 | **66,392,703** ✅ (sum of `tokens`, after repair) |
| Words in the speech bodies | — | **58,904,180** (`lib/lexical.py::TOKEN_RE`, the denominator of every rate) |
| Period | 1992-01-06 → 2023-12-30 | ✅ identical |
| Raw text characters | — | 388.8 M |

**On the 6,233 / 6,582 discrepancy:** the paper reports 6,233 meetings, but `meta.tsv`
holds 6,595 rows (one per *document*), covering 6,582 distinct meeting identifiers. The
difference comes from **resumptions** (`S/PV.9052 (Resumption 1)`): 14,853 speeches carry a
`Resumption` marker in `document_symbol`. The paper's 6,233 appears stale or based on a
different counting rule. **Use 6,582 meetings / 6,595 documents**, and document the choice.

---

## 5. Technical traps (⚠️ handle before any analysis)

### 5.1 Encoding — UTF-8, not the system codepage

Both TSVs are **valid UTF-8**. On Windows, `pandas.read_csv()` without an explicit
`encoding=` falls back to cp1252 and yields mojibake (`C�te D'ivoire`,
`Peace And Security � Terrorist Acts`). Always force it:

```python
pd.read_csv(path, sep='\t', quoting=3, encoding='utf-8',
            na_values=['NA'], keep_default_na=False, dtype=str)
```

`quoting=3` (`QUOTE_NONE`) is mandatory: fields contain R-style doubled apostrophes
(`D''Affaires`) and unescaped quotation marks.

### 5.2 36 rows split by a literal `\n`

`speaker.tsv` has 106,520 physical lines for 106,302 speeches. Meeting **S/PV.5225**
(2005-07-12, *The Role Of The Security Council In Humanitarian Crises*) carries a literal
newline inside its `agenda_item3` value, so each of its 36 speeches is spread across two
physical lines (21 tabs + 4 tabs = 25).

A naive read yields 106,338 rows, 36 of them corrupt (empty year, speaker, country). The
repair is to join lines until the tab count reaches 25:

```python
def repair(path, n_tabs):
    out, buf = [], ''
    for ln in open(path, encoding='utf-8').read().split('\n'):
        buf = ln if not buf else buf + ' ' + ln
        if buf.count('\t') >= n_tabs:
            out.append(buf); buf = ''
    return out
# speaker.tsv → n_tabs=25 ; meta.tsv → n_tabs=8
```

After repair: **exactly 106,302 rows**, and a perfect join against the tar (0 missing
texts, 0 orphan files).

### 5.3 Normalising `country_org`

630 distinct values, of which only ~195 are states; the rest are NGOs, regional
organisations, UN agencies, universities and even companies (*Goldman Sachs*, *Microsoft*,
*Mastercard*, *Anthropic (Firm)*). 295 values occur exactly once.

Aliases and duplicates to merge before any aggregation:

| Alias A | Alias B |
|---|---|
| `Turkey` (732) | `Türkiye` (61) |
| `Czech Republic` (197) | `Czechia` (10) |
| `Cape Verde` (125) | `Cabo Verde` (2) |
| `Bolivia (Plurinational State Of)` (751) | `Plurinational State Of Bolivia` (2) |
| `Micronesia (Federated States of)` (2) | `Federated States Of Micronesia` (4) |
| `Interpol` / `INTERPOL` · `Group Of Five For The Sahel` / `Group of Five for the Sahel` | (3 case collisions) |

`agenda_item2` has 16 comparable case collisions (`Children and armed conflict` vs
`Children And Armed Conflict`). **Normalise case before any `groupby`.**

A **`country_org` → ISO-3166 alpha-3 + entity-type crosswalk** (state / IGO / NGO / civil
society / UN agency / other) also needs to be built: it is a prerequisite for mapping and
for separating state from non-state speakers.

### 5.4 `UN` = 4,709 speeches

`country_org = "UN"` bundles the Secretary-General, special representatives and senior
officials: the **6th "speaker" in the corpus**, on par with each individual P5 member. This
is the paper's central finding (the "P6"). The `role` field gives the position, but is
empty in 86% of rows — usable only on the populated subset (≈3,100 speeches with a job
title).

---

## 6. Variable dictionary

### `speaker.tsv` — 106,302 rows × 26 columns

| Column | Filled | Card. | Description |
|---|---:|---:|---|
| *(index)* | 100% | 106,302 | R row identifier |
| `filename` | 100% | 106,302 | `UNSC_{year}_SPV.{n}_spch{nnnn}.txt` — **join key to the tar** |
| `date` | 100% | 4,094 | ISO date `YYYY-MM-DD` |
| `day` / `month` / `year` | 100% | 31/12/32 | Date components |
| `speaker` | **99.0%** | 7,527 | Speaker name (1,115 missing) |
| `speaker_undl` | **7.2%** | 891 | UNDL identifier — too sparse for systematic use |
| `speaker_country` | **0.1%** | 33 | 130 values only — unusable |
| `country_org` | 100% | 630 | Country or organisation represented — ⚠️ see §5.3 |
| `role` | **86.8%** non-null but **89,238 empty strings** | 518 | UN position; ≈3,100 usable values |
| `participanttype` | 100% | 3 (+2 noise) | `The President` (39,483) · `Mentioned` (38,181) · `Guest` (28,630); 8 `The PRESIDENT` to normalise |
| `speech_number` | 100% | 179 | Position of the speech within the meeting |
| `record_speech` | **5.9%** | 4,874 | Undocumented in the codebook — purpose unknown |
| `tokens` / `types` / `sentences` | 100% | — | `quanteda` metrics; means 624 / 273 / 22 |
| `topic` | 100% | 591 | Agenda item as printed in the record |
| `agenda_item1` | 100% | 6 | Repertoire, level 1: `Thematic` (41,865) · `Africa` (23,119) · `Middle East` (20,413) · `Europe` (11,268) · `Asia` (6,499) · `Americas` (3,138) |
| `agenda_item2` | 89.5% | 125 | Repertoire, level 2 |
| `agenda_item3` | 90.1% | 183 | Repertoire, level 3 |
| `agenda_item4` | **23.9%** | 234 | Repertoire, level 4 |
| `agenda_item_manual` | 100% | 100 | **Harmonised manual label — the most usable field** |
| `document_symbol` | 100% | 6,595 | Document symbol (resumptions included) |
| `meeting_symbol` | 100% | 6,582 | Meeting symbol |
| `speech_format` | 100% | 2 | `In-Person` (101,194) · `VTC` (5,072, concentrated 2020-2022) |

Useful derived column: `basename = filename.replace(r'_spch\d+\.txt$', '')` → joins to
`meta.tsv.basename` (perfect match after repair).

### `meta.tsv` — 6,595 rows × 9 columns

`basename` · `date` · `topic` · `year` · `month` · `day` · `spv` · `num_speeches`.
`num_speeches` ranges from 1 to 179 and underpins the paper's meeting typology (§7).

### Text files

One UTF-8 file per speech, no header. The text **includes the opening form of address**
(`Mr. AL-KIDWA (Palestine) (interpretation from Arabic): …`) — strip it before any lexical
counting, or country names will be over-represented. Mean length 3,658 characters (median
3,437); no empty files.

---

## 7. What the paper establishes (arXiv:1906.10969v3)

Findings worth knowing, since they frame how the corpus can be read:

- **Three growth regimes.** 1,023 speeches in 1992 → 7,621 in 2023 (×7.4). Plateaus:
  1992-1999 (~1,400/yr), 2000-2004 (>2,500), 2005-2007 (dip), 2008-2013 (~3,000), a break
  in 2014 (4,769) then continuous growth. Covid dip in 2020.
  **Every time series must be normalised** (rate per speech or per 100k words), otherwise
  you are measuring corpus growth.
- **The P5 does not dominate.** From 2014 onward the rise in total volume is not matched by
  the P5's share: it comes from the E10 and from guests at open debates.
- **The "P6".** The UN administration is the 6th speaker (4,709 speeches), on par with each
  permanent member.
- **Four meeting types** (from the `num_speeches` distribution): adoption meeting
  (1 speech) · briefing (2-3) · limited formal debate (15-40, mode ≈ 20) · open or intensive
  debate (40-180). Every session above 100 speeches falls between 2013 and 2020.
- **New themes** emerging within the period: *Women, Peace and Security*, *Climate-related
  Disasters*.
- The paper is a *data paper*: it contains **no lexical or content analysis whatsoever**.
  The ground for studying the word "genocide" is entirely open.

---

## 8. First findings — the semantic field of genocide

This section began as a reconnaissance scan. The table is now aligned with lexicon v4 (2
September 2026, measured on `speeches_norm.parquet`; what moved between v2, v3 and v4 is in
[`VALIDATION.md`](VALIDATION.md)); generated artifacts and that register remain the
authority if a future lexicon version changes these figures.

Every active term, across all 106,302 speeches (case-insensitive regex; total occurrences).
Seven terms are **anchored**: they are counted only where the sentence holding the match
also says `genocid*`, which is why `commemoration` and `survivors` are so much smaller here
than a scan for those words would suggest. `config/lexicon.yml` says of each one why.

| Term | Register | Speeches | % corpus | Occurrences |
|---|---|---:|---:|---:|
| `impunity` | accountability | 9,662 | 9.09% | 13,616 |
| `tribunals` | accountability | 2,626 | 2.47% | 13,030 |
| `icc` | accountability | 4,766 | 4.48% | 12,476 |
| `war_crimes` | legal | 4,664 | 4.39% | 6,588 |
| `atrocity` | legal | 4,244 | 3.99% | 6,120 |
| `genocide` | core | 3,273 | 3.08% | 6,092 |
| `crimes_against_humanity` | legal | 3,465 | 3.26% | 4,136 |
| `icj` | accountability | 1,447 | 1.36% | 2,399 |
| `massacre` | descriptive | 1,588 | 1.49% | 2,313 |
| `early_warning` | preventive | 1,606 | 1.51% | 1,960 |
| `responsibility_to_protect` | preventive | 1,353 | 1.27% | 1,795 |
| `ethnic_cleansing` | legal | 1,229 | 1.16% | 1,705 |
| `mass_atrocity` | legal | 624 | 0.59% | 784 |
| `never_again` | commemorative | 305 | 0.29% | 338 |
| `commemoration` ⚓ | commemorative | 199 | 0.19% | 321 |
| `extermination` | legal | 224 | 0.21% | 281 |
| `denial` ⚓ | contentious | 186 | 0.17% | 269 |
| `holocaust` | commemorative | 175 | 0.16% | 238 |
| `prevention_of_genocide` | preventive | 212 | 0.20% | 237 |
| `mass_killing` | descriptive | 149 | 0.14% | 158 |
| `genocide_convention` | legal | 135 | 0.13% | 153 |
| `survivors` ⚓ | commemorative | 73 | 0.07% | 106 |
| `glorification` ⚓ | contentious | 93 | 0.09% | 103 |
| `incitement` ⚓ | preventive | 47 | 0.04% | 49 |
| `genocidal_ideology` | contentious | 30 | 0.03% | 39 |
| `genocidaires` | core | 21 | 0.02% | 31 |
| **`genocide_qualification`** (derived) | **core** | **3,268** | **3.07%** | **6,061** |
| `intent_to_destroy` ⚓ | legal | 16 | 0.02% | 23 |
| `ethnic_violence` ⚓ | contentious | 13 | 0.01% | 13 |

⚓ marks an anchored term. **`genocide_qualification` is derived, not matched**: it is
`genocide` minus `genocidaires`, and it is the figure the chronology, the change-point
tests and the actor table publish, because a delegation calling the ex-FAR
*génocidaires* is naming who did it rather than qualifying the event. The raw term is
published beside it and is what the concordance enumerates; `genocidaires` has its own 31
lines. The `genocide` pattern is deliberately unchanged at v4, so every occurrence
identity, the gold sample and the four committed model runs stand — see
[`VALIDATION.md`](VALIDATION.md).

Forms of `genocid*`: `genocide` (5,685), `genocidal` (313), `genocides` (62),
`genocidaires` (29), `genocidaire` (2), `genocida` (1), summing to the term's 6,092. The
two `genocidaire` spellings, 31 occurrences, are what `genocide_qualification` subtracts.
Marginal OCR variants (`genecide`) should be caught by a tolerant regex; the French
`génocidaires` occurs 8 further times and is outside both patterns on purpose.

**Available subsets**

Words, not codebook tokens: since 2 September 2026 every denominator in this repository is
the word count of the speech bodies (`lib/lexical.py::TOKEN_RE`), 58,904,180 of them
against the codebook's 66,392,703 tokens over the full texts.

| Criterion | Speeches | Words |
|---|---:|---:|
| ≥ 1 occurrence of `genocide_qualification` | 3,268 | 3,448,202 |
| ≥ 2 occurrences | 1,055 | 1,219,863 |
| ≥ 3 occurrences | 513 | 640,885 |
| ≥ 5 occurrences | 205 | 279,191 |
| Atrocity core (genocide ∪ ethnic cleansing ∪ CAH ∪ war crimes ∪ mass atrocity) | 7,981 | 8,277,171 |
| Active lexicon (28 terms) | 20,892 | 19,908,544 |

The first four rows count the qualifying uses; the raw term reaches 3,273 speeches, the
figure every earlier version of this table gave for `genocid*`, and the five it adds are
speeches whose only `genocid*` word is the actor label. The atrocity-core union is the v3
number unchanged, because the term it is built on is unchanged. The active-lexicon union
is *smaller* than the 23,271 the v2 table gave over 22 terms, and v4 has 28: the seven
anchors take far more speeches out of the commemorative and contentious registers than
`massacre`, `mass_killing`, `icj`, `incitement` and `intent_to_destroy` put back.

### 8.1 Chronology

The normalised rate tells a story the raw counts hide. Occurrences of
`genocide_qualification` per 100,000 **words** (lexicon v4; the v3 figures over the
codebook's token denominator ran about 11% lower and are in
[`VALIDATION.md`](VALIDATION.md)):

```
1994  32.2  ████████████████████████████████  Rwanda
2014  25.4  █████████████████████████         Ukraine/Crimea, ISIS/Yazidis, CAR, Rwanda +20
1993  19.3  ███████████████████               Bosnia
1995  18.5  ██████████████████                Srebrenica
2015  18.0  ██████████████████                Srebrenica +20 (Russian veto), Daesh
1999  16.6  █████████████████                 Kosovo, East Timor
1996  16.4  ████████████████
2000  14.3  ██████████████                    Carlsson report on Rwanda
2005  14.3  ██████████████                    Darfur, World Summit (R2P)
…
2022  10.6  ███████████                       Ukraine
2023   9.9  ██████████                        Gaza, Ukraine
1997   5.3  █████                             absolute trough
```

Reading the raw `genocide` term instead moves only 2014 (25.4 to 25.6), 1999, 2000, 2006
and 2007, by a tenth each: the actor label is a Great Lakes word, and it is rare.

**The 2014 peak (659 occurrences) exceeds 1994 (228) in absolute volume** while remaining
below it in density. This is the single most interesting result of the first scan: the word
has a second life after 2013, driven by new uses (Ukraine, Yazidis, commemorations, R2P)
rather than by one crisis.

### 8.2 Who says the word?

**By volume:** UN (227) · **Rwanda (187)** · United States (163) · France (127) ·
United Kingdom (94) · Bosnia and Herzegovina (56) · Argentina (54) · Ukraine (54) ·
European Union (51) · Liechtenstein (46).

**By rate** (≥ 200 speeches overall):

| Country / organisation | Speeches | with "genocide" | Rate |
|---|---:|---:|---:|
| **Rwanda** | 697 | 187 | **26.8%** |
| Armenia | 124 | 35 | 28.2% (below threshold, but notable) |
| **Liechtenstein** | 217 | 46 | **21.2%** |
| Bosnia and Herzegovina | 404 | 56 | 13.9% |
| Iraq | 246 | 32 | 13.0% |
| Tanzania | 236 | 23 | 9.8% |
| Slovenia | 308 | 29 | 9.4% |
| Croatia | 461 | 43 | 9.3% |
| Cuba | 233 | 19 | 8.2% |
| Azerbaijan | 478 | 38 | 8.0% |
| Israel | 430 | 33 | 7.7% |
| **Russian Federation** | 5,101 | 43 | **0.84%** |

Two usage regimes emerge: **states carrying a genocide memory** (Rwanda, Armenia, Bosnia,
Croatia, Israel) and **norm-entrepreneur states** (Liechtenstein, Slovenia, Costa Rica,
Luxembourg, Canada — the ICC and R2P advocacy bloc). Russia, by contrast, uses the word 32
times less often than Rwanda despite giving 7 times more speeches — an asymmetry worth
explaining.

**By participant type:** `Guest` 6.31% · `Mentioned` 3.42% · `The President` 0.41%.
Guests — civil society, survivors, NGOs — are the word's primary carriers; the presidency,
whose interventions are procedural, barely uses it.

### 8.3 In which files?

| Agenda item | Speeches | with "genocide" | Rate |
|---|---:|---:|---:|
| International Tribunals | 1,501 | 437 | **29.1%** |
| Rwanda | 452 | 124 | **27.4%** |
| Middle East (dedicated heading) | 159 | 32 | 20.1% |
| Rule of Law | 673 | 109 | 16.2% |
| Protection of Civilians | 3,716 | 384 | 10.3% |
| Bosnia and Herzegovina | 3,185 | 300 | 9.4% |
| Myanmar | 260 | 20 | 7.7% |
| Great Lakes | 608 | 44 | 7.2% |
| Burundi | 747 | 54 | 7.2% |
| Maintenance of Int'l Peace and Security | 7,776 | 288 | 3.7% |
| Israel/Palestine | 10,212 | 148 | **1.45%** |
| Syria | 4,876 | 25 | **0.51%** |

By region (`agenda_item1`): `Thematic` 4.41% · `Europe` 4.21% · `Africa` 2.67% ·
`Middle East` 1.38% · `Asia` 0.72% · `Americas` 0.13%.

**Two surprises to pursue.** (a) The word is *thematic* before it is *situational*: it
circulates mainly in debates on tribunals, protection of civilians and the rule of law —
a legal and commemorative register. (b) Israel/Palestine and Syria, the two largest files
in the corpus, are **among the poorest in "genocide"** — which makes the 2023 reversal all
the more visible.

### 8.4 Co-occurrence

Share of genocide-bearing speeches that also contain:

| Term | In genocide speeches | Corpus baseline | Ratio |
|---|---:|---:|---:|
| `war crimes` | 48.2% | 4.4% | ×11 |
| `crimes against humanity` | 47.2% | 3.3% | ×14 |
| `impunity` | 41.3% | 9.1% | ×4.5 |
| `ICC` | 26.6% | 4.5% | ×6 |
| `atrocit*` | 24.3% | 3.6% | ×6.8 |
| `ethnic cleansing` | 16.4% | 1.2% | ×14 |
| `R2P` | 10.5% | 1.3% | ×8 |
| `mass atrocity` | 7.1% | 0.5% | ×14 |
| `genocide convention` | 3.9% | 0.13% | ×30 |

The word almost never travels alone: it appears inside a **canonical legal triad**
(genocide / war crimes / crimes against humanity) inherited from the Rome Statute, extended
since 2005 by the R2P quartet (+ ethnic cleansing).

### 8.5 Collocates (log-likelihood, ±8-word window)

```
crimes 19618 · humanity 10793 · against 7838 · war 6655 · rwanda 4093 ·
cleansing 2922 · ethnic 2074 · srebrenica 2041 · tutsi 1520 · rwandan 1508 ·
prevention 1482 · crime 1349 · denial 1173 · committed 996 · responsible 960 ·
punishment 774 · violations 612 · adviser 573 · perpetrators 563 ·
twentieth 529 · glorification 525 · atrocities 488 · anniversary 473 ·
victims 473 · protect 461 · criminals 401 · prosecution 390 · ideology 372 ·
perpetrated 365 · justice 304 · impunity 297 · convicted 294 · mass 284 ·
commemoration 251 · tutsis 241 · prevent 236 · dieng 236 · survivors 216
```

Four registers read straight off this list:

1. **Legal** — `crimes`, `punishment`, `prosecution`, `convicted`, `perpetrators`, `impunity`
2. **Preventive** — `prevention`, `prevent`, `protect`, `adviser` (the *Special Adviser on
   the Prevention of Genocide*), `dieng` (Adama Dieng, Special Adviser 2012-2020)
3. **Commemorative** — `twentieth`, `anniversary`, `commemoration`, `victims`, `survivors`
4. **Contentious** — `denial`, `glorification`, `ideology` (denial and instrumentalisation)

The commemorative and contentious registers are the two least expected, and probably the
richest for analysis.

### 8.6 Densest meetings

| Date | Symbol | Subject | Occurrences |
|---|---|---|---:|
| 2014-04-16 | S/PV.7155 | Threats to International Peace and Security | **198** |
| 2000-04-14 | S/PV.4127 | Rwanda — report on the 1994 genocide | 115 |
| 2015-07-08 | S/PV.7481 | Bosnia and Herzegovina (Russian veto on Srebrenica) | 115 |
| 2019-07-17 | S/PV.8576 | International Residual Mechanism for Criminal Tribunals | 62 |
| 2014-06-05 | S/PV.7192 | ICTY & ICTR | 58 |
| 1994-11-08 | S/PV.3453 | The situation concerning Rwanda (creation of the ICTR) | 55 |
| 2022-06-21 | S/PV.9069 | Maintenance of Peace and Security of Ukraine | 55 |

These sessions make an excellent test set for the concordancer and for validating LLM
extractions.

---

## 9. Reproducibility

Minimal preparation chain (Python 3.12 x64, `pandas` + `pyarrow`):

1. Repair the split lines in both TSVs (§5.2);
2. Read as UTF-8, `quoting=QUOTE_NONE`, `na_values=['NA']`;
3. Type the numeric columns and the date;
4. Stream `speeches.tar` with `tarfile` (≈6 s, 106,302 files) and join on `filename`;
5. Write `speeches.parquet` (131 MB zstd) and `meetings.parquet` (0.13 MB).

Assertions to enforce: 106,302 rows · 0 missing texts · 0 orphan files · 0 unparsed dates ·
unique `filename`.

The resulting parquet is the **single source** for everything downstream; the original
files are never read again.

---

## 10. Limitations to state in any publication

1. **Public meetings only.** Closed consultations, where most decisions are made, are
   absent. The corpus documents official speech, not negotiation.
2. **OCR noise**, unquantified by the authors and unevenly distributed over time.
3. **Semi-automatic speaker attribution**, with an unaudited manual component.
4. **Translation.** Records are in English; 40.2% carry an explicit non-English delivery
   marker and are official translations. Missing in-person markers imply English under the
   record convention, while 5,072 VTC speeches remain unknown. Stylistic analysis partly
   measures UN translation services, not only the speaker.
5. **Partly stale Dataverse metadata** (§1) and two valid counting units: 6,595 corpus
   documents versus 6,582 distinct meeting symbols (§4).
6. **`role` is empty in 86% of rows**: analyses by UN function rest on a non-random subset.

---

*Notes compiled from version 6.1 of the dataset, the January 2025 codebook, the arXiv v3
paper (March 2025) and a full profiling pass over the local data.*
