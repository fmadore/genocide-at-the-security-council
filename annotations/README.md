# Human annotations

Files below this directory are durable, version-controlled research inputs. Pipeline runs
read them but never create, clear or overwrite them.

The lexicon candidate sample and the merged review table are generated under
`data/interim/`, including separate probability, coverage and high-recall-negative sampling
frames. Human work belongs only in `lexicon/annotations.csv`. Until the annotation schema
and codebook pilot begins, leave that file header-only. Follow `lexicon/CODEBOOK.md` and add
reviewed case or entity identifiers to `lexicon/referents.csv` before using them in an
annotation row.

`lexicon/referents.csv` is versioned in place. Adding a referent gives it `since` set to the
next version; withdrawing one sets `retired_in` and, where there is a successor,
`superseded_by`, and leaves the row where it is. Rows are never deleted: a committed model
run records the identifiers it was offered, and a deletion would orphan every row that used
one. The list version is the highest version any row mentions, so nothing has to be kept in
step by hand. Correcting `iso3` or `years` is documentation and changes no version;
`tests/test_audit.py` holds the meaning-bearing columns to a digest, so an edit that changes
what an identifier covers cannot pass unnoticed.

## `genocide/`

`genocide/annotations.csv` is the gold sample that evaluates the model-assisted usage layer.
`scripts/13_gold_sample.py` draws the candidates from every `genocide` occurrence in the
canonical corpus except the ten the prompt's worked examples are cut from, and writes them to
`data/interim/genocide_gold_*.csv`: on 24 September 2026, 469 rows over 453 distinct
occurrences. Two coders code every one of them independently; the agreement between them is
what the model's scores are read against, so a case coded once is not yet gold.

**Three frames, and one design over them.** There are 120 occurrences drawn with equal
probability, 80 more that cover every period and usage-cue stratum, and a third frame of 269
cut from the published model run's labels (`model_strata`), so that the rare positions are
measurable at all. Once a second run is named in `gold_comparison_run.txt`, step 13 cuts the third
frame from where the two runs disagree instead, which changes the sample: freeze it before
coding starts ([`docs/EVALUATION_PLAN.md`](../docs/EVALUATION_PLAN.md)). The frames are reported one by one, and
`genocide_gold_design.csv` gives every occurrence its probability under each frame and under
their union, which is what lets 15 weight *all* the coding back to the corpus. An unweighted
rate over the union would estimate nothing; a weighted one is design-unbiased.

**Coders work from the blinded packet.** `genocide_gold_packet.csv` holds each sampled
occurrence once, in a seeded shuffle, with no frame, cue, stratum or probability — a stratum
named `rejects` is the model's answer printed beside the question. `python
tools/coding_page.py` turns it into `data/interim/genocide_coding.html`, an offline page that
shows each passage in its speech, takes the evidence span as a text selection, applies the
codebook's cascade and exports rows in this file's column order. The frames stay in the
candidate and review files, which are the key.

**The offline page asks the codebook as questions.** Every field of the codebook is there
and the exported rows are unchanged, but a coder reads plain-language questions with an
example under each option, and sees only the questions that apply. Three things follow from
an answer without a further question. A text error (`false_positive`) sets every discourse
field to `not_applicable`. "No specific situation" sets `speaker_position` to `no_position`,
offers only the three non-case referents, and records `referent_source: passage` and
`own_state_accused: not_applicable`, which is what the published model run writes on such
rows. "Cannot tell which situation" records `referent_source: not_applicable`. The first two
are the codebook's rules; the two values recorded for a non-case mention are this page's
convention, chosen so that a field no one was asked about cannot produce a disagreement.

**Sending the page to a coder.** `python tools/coding_page.py --coder <ID>` writes
`data/interim/genocide_coding_<ID>.html` with that identifier fixed in the page. It is one
file of about 5 MB that opens with a double click and needs no connection: send it by e-mail
or a shared folder. Without `--coder` the page offers FM, JG and the adjudicator. The
research assistant codes as `RA1`. Step 15 compares whichever two coders the annotation
file holds (`gold_estimates.coder_pair`), so `RA1` beside FM or beside JG is read as the
pair. A file holding three coders is refused: which two are compared is a decision to take,
not something the pipeline picks.

**Saving and resuming.** Answers autosave in the coder's browser, not into the HTML file or
the repository, and the page reopens on the passage the coder left. At the end of every
session, **Save a copy to file** downloads every answer, finished or not; the page reminds
the coder once ten passages have changed since the last copy. **Restore from a saved copy**
(in the Guide) loads that CSV on another computer or after browser data were cleared; it
warns before replacing answers and recalculates completeness rather than treating drafts as
finished. **Download finished passages for your supervisor** writes the file that is
validated and then added to `annotations/genocide/annotations.csv`. No file is sent
automatically. If browser saving fails, the page warns and keeps the session in memory so a
copy can still be downloaded before closing it.

**Passages already read against a model's labels are flagged, not dropped.**
`genocide/prior_review.csv` lists the 59 occurrences read against the Qwen run's labels on
10 September 2026, by `occurrence_id` and line id and with no label, evidence or rationale;
`tools/prior_review.py` rebuilds it from the review's records, step 13 marks the ones it draws
with a `prior_review` column in the candidate and design files (never in the packet), and
step 15 reports every gold figure with and without them
([`docs/EVALUATION_PLAN.md`](../docs/EVALUATION_PLAN.md), section 4).

**A model label can be a sampling stratum, exactly as the cue is.** The optional third frame
is cut from `model_annotations/`, and what it says about an occurrence is that it is worth a
coder's time—never what the coder should write. Nothing under this directory is read while a
candidate is being drawn, and nothing here is written by the pipeline: `prior_review.csv`
changes only when someone runs `tools/prior_review.py --write` and commits the diff.

Same schema, same codebook, same rules: the columns are the twenty-two in
`lexicon/annotations.csv`, the labels are the ones defined in `lexicon/CODEBOOK.md`
(codebook 3, annotation schema 3, referent list 2), and new referents go into
`lexicon/referents.csv` first. A separate file rather than more rows in
`lexicon/annotations.csv` because each sample validates its own candidates: an annotation
whose occurrence is absent from the candidates it is merged against is refused, so one file
per sample is what keeps both merges honest. As with the lexicon file, the pipeline reads it
and never writes it — a rerun regenerates the candidates and the review join, never the
coding.
