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
`scripts/13_gold_sample.py` currently draws 200 candidate rows (199 distinct occurrences)
from the 7,747 occurrences in the canonical corpus, in two pre-model frames, and writes them to
`data/interim/genocide_gold_*.csv`. Two coders code every one of them independently; the
agreement between them is what the model's scores are read against, so a case coded once is
not yet gold.

**The frames are never pooled.** There are 120 occurrences drawn with equal probability, which is
the only part of the sample that estimates anything about the corpus and is weighted by its
its own inclusion probabilities; 80 more cover every period and usage-cue stratum, so that
nothing is missing entirely. Once two replacement model runs exist, the script can add a
third frame drawn from the strata those runs read differently. That disagreement frame is
read unweighted; a rate computed over the union of the frames would estimate nothing. Every
candidate row records the inclusion probability that put it there.

**A model label can be a sampling stratum, exactly as the cue is.** The optional third frame
is cut from `model_annotations/`, and what it says about an occurrence is that it is worth a
coder's time—never what the coder should write. Nothing under this directory is read while a
candidate is being drawn, and nothing here is written by any script.

Same schema, same codebook, same rules: the columns are the fifteen in
`lexicon/annotations.csv`, the labels are the ones defined in `lexicon/CODEBOOK.md`
(codebook 3, annotation schema 3, referent list 2), and new referents go into
`lexicon/referents.csv` first. A separate file rather than more rows in
`lexicon/annotations.csv` because each sample validates its own candidates: an annotation
whose occurrence is absent from the candidates it is merged against is refused, so one file
per sample is what keeps both merges honest. As with the lexicon file, the pipeline reads it
and never writes it — a rerun regenerates the candidates and the review join, never the
coding.
