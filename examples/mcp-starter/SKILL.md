---
name: unsc-genocide-research
description: Query and interpret the Genocide at the Security Council corpus via MCP while enforcing source traceability and separating computed corpus measures from unvalidated LLM labels. Use when answering questions about UN Security Council debates using the genocide-at-the-security-council MCP server.
---

# UN Security Council Genocide Corpus Research Skill

Use this workflow whenever querying the `genocide-at-the-security-council` MCP server.

## 1. Check provenance and epistemic layer first

- Call `get_catalog` at the start of a session to check available endpoints and epistemic rules.
- Label every figure or claim explicitly as either **computed from the record** (`series`, `kwic`, `speeches`, `countries`, `lexical`, `frames`) or **model-derived / unvalidated preview** (`usage`, `semantic`).

## 2. Never overclaim from corpus counts

- Remind the user when quoting rates or totals that the corpus is Sakamoto & Matsuoka v6.0 (`doi:10.7910/DVN/CKPTRB`, 1946–2026): the **English UN verbatim record**, including UN translations of speeches delivered in French, Russian, Chinese, Arabic, or Spanish.
- Note that informal consultations leave no verbatim record, 717 of 10,636 meeting records hold no speeches, and scanning damage makes every count a **minimum**.
- Respect withheld rates: periods with fewer than 125 speeches (such as 1959) carry `null` rates, not zeros.

## 3. Trace textual claims to full speeches

- Never rely on concordance snippets (`search_concordance`) alone when interpreting a delegation's argument or stance.
- Before quoting or interpreting a match, call `get_speech` with its `speech_id` (for example `SC07155-01-007`) and cite the exact meeting symbol (`S/PV.7155`), date, and speaker affiliation.

## 4. Handle experimental LLM labels with strict discipline

- Treat output from `get_model_labels` (`usage/occurrences.json`) strictly as an **unvalidated exploratory preview** until human gold coding is completed.
- Exclude rows with `evidence_valid: false` from any summary.
- Always surface `contested` fields and the comparison model's `alt` labels (Gemma 4 vs. Qwen3.8). Agreement between two models measures stability, not accuracy.
- Never infer legal determinations of genocide or timeless national positions from delegation labels or vocabulary counts.

## 5. Citation

When producing a summary or table for research use, cite both:

- The project (*Genocide at the Security Council*, `CITATION.cff`, CC BY 4.0 for derived tables) and the `analysis_hash` returned by the tool; and
- The source corpus: Sakamoto, T., & Matsuoka, T. (2023), *The UNSC Meetings and Speeches* (Version 6.0), Harvard Dataverse, `https://doi.org/10.7910/DVN/CKPTRB` (CC0 1.0).
