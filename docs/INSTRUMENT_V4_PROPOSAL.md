# Proposal — instrument v4 (prompt v4, codebook 4)

24 September 2026. **Status: proposal for review by the two coders (FM, JG).** Nothing
is activated. Prompt v3 remains the instrument of the Qwen and Gemma runs, and the
comparison between the two models is valid only if they answer the same questionnaire. A
v4 will require a new run identifier and a new probe. Tracking: [ROADMAP.md](ROADMAP.md),
items RV7, RV8, RV9 and RV17.

## 1. What motivates the revision

- **Referent identifiers.** Of the 77 refusals in run `2026-09-08-qwen-131k`, 73 are
  labels in place of identifiers ("genocide in general" for `genocide_in_general`,
  "Bosnia and Srebrenica" for `bosnia_srebrenica`). The ten annotated examples of prompt
  v3 themselves write `referent: Rwanda`: the prompt teaches the error it then refuses. A
  single invalid referent causes the whole speech to be rejected.
- **Non-contiguous evidence.** 11 rows out of 3,608 (0.30%) in the 9 September snapshot
  quote a recomposed passage: an intervening sentence omitted (SC01253-01-003#2), an
  objection cut out (SC03454-02-003#1), the order reversed (SC04127-01-006#1), the
  spelling corrected (SC01745-01-023#1).
- **The distancing rule.** Codebook 3 places "allegations of genocide" in `rejects` and
  "accused of genocide" in `asserts`. Yet a reported allegation is not a denial:
  SC00235-01-001#3 is coded `rejects` although Pakistan denies having accused the Indian
  government, just before asserting that there was genocide (#4); SC03247-01-039#1 is
  coded `reports_without_position` for "what it termed "genocide"" despite the rule.
- **Decoding.** The run decoded deterministically (`temperature=0`). The Qwen3.8-27B model
  card recommends `temperature=1.0, top_p=0.95, top_k=20` in reasoning mode. The Gemma
  reconnaissance truncated 2 speeches out of 12.

## 2. Proposed changes to the prompt (v4)

1. **Declare `constraints: referent-enum, sentence-evidence`** in the header. This is
   already implemented (`lib/llm.py`) and has no effect on v3. The output schema then
   contains the exact list of current identifiers, the occurrence numbers of the request
   and their count: a guided decoder can no longer produce an invalid referent or forget
   an occurrence.
2. **Rewrite the examples with identifiers** (`referent: rwanda`), and cite them by their
   v5.0 identifiers (`model_annotations/genocide/prompt_examples.csv`). These ten
   occurrences remain excluded from the gold sample.
3. **Evidence = numbered sentences.** The speech is presented sentence by sentence,
   numbered; the model returns the first and last sentence of the evidence. The evidence
   is contiguous by construction and always located; a recomposed passage becomes
   impossible.
4. **Decoding parameters**: set them after the measurement made by
   `scripts/probe_sampling.py` (≈100 speeches, half of them the longest) — truncation rate,
   refusals, and agreement of the labels between settings. Fewer truncations are a gain
   only if the labels hold up against the gold sample.

## 3. Proposed change to the codebook (4): engagement

Proposal: split `rejects` according to the typology of **engagement** (Martin & White,
*The Language of Evaluation*, 2005), which distinguishes precisely what the current rule
conflates:

| Proposed value | Engagement | Example |
|---|---|---|
| `asserts` | proclaim / monoglossic | "This is genocide." |
| `denies` | disclaim: deny | "There was no genocide in Darfur." |
| `distances` | attribute: distance | "the so-called genocide", "allegations of genocide", distancing quotation marks |
| `reports_without_position` | attribute: acknowledge | "the Commission described the acts as genocide" |
| `conditional` | entertain | "this could become genocide" |
| `no_position` | — (no concrete case) | the Convention, the Special Adviser |

Consequences: `distances` no longer counts as a rejection in the "Who rejects the word"
ranking; the v3 runs are not recoded automatically (a v3 `rejects` row is either `denies`
or `distances`, and only a coder can tell which).

For the coders to decide: is a separate field (`hedge_scope`: label / person / act)
needed rather than one more value? "alleged genocide financier" casts doubt on a person,
not on the category: `asserts` under both options.

## 4. Pilot protocol

1. **Pilot sample outside the gold sample** (30–40 occurrences): the refusals of the Qwen
   run, the eleven non-contiguous evidence quotes, and the boundary cases from the review
   of 10 September — SC00228-01-002#1, SC00232-01-005#1–3, SC00211-01-007#1–2,
   SC00235-01-001#3–4, SC03247-01-039#1, SC03656-01-005#7, SC06880-01-031#10 — plus pairs
   constructed for each boundary (deny / distance / report).
2. **Independent coding** by the two coders under the proposed codebook 4, with the
   offline page (`tools/coding_page.py`).
3. **Separate measures**: share of valid identifiers and of contiguous evidence (model),
   human agreement field by field (κ and PABAK), confusion matrix
   `denies`/`distances`/`reports_without_position`.
4. **Decision**: adopt, amend or abandon engagement; freeze prompt v4; run Qwen and Gemma
   under v4 with new run identifiers.

## 5. What does not change

- Prompt v3, its runs and their identifiers remain readable and published as they are.
- Agreement between models measures stability, not accuracy; only the gold sample
  measures accuracy, and the corrected shares (RV15) depend on it.
