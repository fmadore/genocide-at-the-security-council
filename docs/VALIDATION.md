# Open items to verify against the original records

The corpus is OCR'd from two-column `S/PV.*` verbatim records (see
[`CORPUS.md` §3](CORPUS.md)). Where the pipeline resolves damaged text
automatically, the resolution is recorded here rather than silently absorbed,
so it can be checked against the source PDF.

**This is a living list.** Each pipeline step appends the cases it could not
decide on its own, or decided by approximate means.

## How to pull an original record

Records are addressed by their `meeting_symbol` (`S/PV.3137`). Resumptions
carry a suffix in the corpus (`S/PV.3745Resumption1`) that becomes
`S/PV.3745 (Resumption 1)` in the library.

- UN Digital Library search: <https://digitallibrary.un.org/search?ln=en&p=S%2FPV.3137>
- Security Council meeting records index: <https://research.un.org/en/docs/sc/quick/meetings/>

The `filename` column locates the individual speech within the meeting
(`UNSC_1992_SPV.3137_spch0009.txt` → the 9th speech of that record).

---

## 1. OCR variants of `genocid*` — 1 case

The OCR-tolerant net (`gen[eo]cid|senocid|qenocid`, `lexicon.yml:
genocide_ocr_variants`, disabled by default) finds **exactly one** speech that
the plain `genocid*` pattern misses across all 106,302 speeches.

| Record | Date | Speaker | Reading |
|---|---|---|---|
| `S/PV.3137` | 1992-11-16 | Bosnia and Herzegovina | `…abhorrent "ethnic cleansing" and **genecide** in Bosnia…` |

**To verify:** does the printed record read "genocide"? If so this is an OCR
slip and the tolerant pattern is correct to catch it. The headline figure of
3,273 speeches is unaffected either way — one speech is 0.03%.

*Established by: `03_lexicon.py`.*

## 2. Delivery language read off the form of address — 27 approximate

`(spoke in French)` / `(interpretation from Arabic)` yields a delivery language
for **42,765 speeches (40.2%)**. Of those, 27 needed approximate matching
because the language name itself is OCR-damaged. Every one is listed so the
reading can be confirmed:

| Printed | Read as | Speeches |
|---|---|---|
| `inArabic`, `fromArabic` | Arabic | 8 |
| `inFrench`, `Prench`, `Frenci.`, `Frerch`, `Fcench`, `F reach` | French | 8 |
| `inRussian`, `Russiar`, `Rassian` | Russian | 4 |
| `inSpanish`, `..anish`, `Spam'sh` | Spanish | 3 |
| `Chiness`, `Cht'nese`, `Ch[nese` | Chinese | 3 |
| `Acabic` | Arabic | 1 |

Matching is confined to a closed 26-language vocabulary, so a damaged spelling
can only ever resolve to a language the corpus already attests — it cannot
invent one. Two spellings too mangled for the similarity threshold
(`Snaniah` → Spanish, `Preach` → French) are corrected by name in
`scripts/lib/text.py: _SPELLING_FIXES`.

**Priority: low.** The mapping is unambiguous to a reader in all 27 cases.

*Established by: `02_normalise.py`.*

## 3. Speeches with no opening form of address — 5,172 (4.9%)

`split_address` matches a form of address in 101,130 of 106,302 speeches. The
remainder open straight into prose ("I thank the President for organizing
today's debate…"). These are read as genuine continuation speeches and are
left untruncated.

**To verify:** sample ~20 and confirm the printed record really does lack a
speaker line at that point, rather than the segmentation having dropped one.
If some are missed segmentation, `country_org` attribution for those speeches
should be treated as less reliable.

**Priority: medium** — it bears on speaker attribution, not on lexical counts.

*Established by: `02_normalise.py`.*

## 4. The 36 rows repaired in `S/PV.5225`

A literal newline inside `agenda_item3` splits each of this meeting's 36
speeches across two physical lines ([`CORPUS.md` §5.2](CORPUS.md)). The repair
rejoins them by tab count and the token sum then matches the codebook exactly,
which is strong evidence it is correct.

**To verify:** confirm the agenda item of S/PV.5225 (2005-07-12) reads *The
Role of the Security Council in Humanitarian Crises* and that the meeting has
36 speeches.

**Priority: low** — the token-sum check already corroborates this.

*Established by: `01_build_parquet.py`.*

---

## Reconciled

### Three lexicon terms exceed their documented occurrence counts

`03_lexicon.py` checks all 14 terms for which [`CORPUS.md` §8](CORPUS.md)
published a figure. Eleven reproduce exactly. The other three exceed it, and
the cause is the same in each case: **the reconnaissance scan counted only the
primary phrase, while the lexicon also matches the acronym or synonym.**

| Term | Primary phrase alone | Documented | Second alternative | Combined |
|---|---|---:|---|---|
| `icc` | `international criminal court` → 6,590 / 4,744 | 6,590 / 4,744 | `\bICC\b` → +5,886 occ. | 12,476 / 4,766 |
| `responsibility_to_protect` | `responsibility to protect` → 1,773 / 1,353 | 1,773 / 1,353 | `\bR2P\b` → +22 occ. | 1,795 / 1,353 |
| `holocaust` | `holocaust` → 242 / 181 | 242 / 181 | `\bshoah\b` → +2 occ. | 244 / 181 |

*(occurrences / speeches)*

So **all 14 documented figures are reproduced exactly by their primary
pattern**; the differences are additions the lexicon makes deliberately, not
drift. Note that for `responsibility_to_protect` and `holocaust` the speech
counts are unchanged — the acronym and the synonym only ever appear in speeches
that already use the full form. `ICC` alone reaches 22 speeches that never
spell the Court out.

**No action needed.** Recorded here so the difference between the README's
reconnaissance figures and the pipeline's is accounted for rather than
puzzling.

---

## Verified against the printed record

*(Nothing yet — move items here with the date and who checked, once confirmed
against the original PDF.)*
