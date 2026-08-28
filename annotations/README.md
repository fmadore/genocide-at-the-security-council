# Human annotations

Files below this directory are durable, version-controlled research inputs. Pipeline runs
read them but never create, clear or overwrite them.

The lexicon candidate sample and the merged review table are generated under
`data/interim/`, including separate probability, coverage and high-recall-negative sampling
frames. Human work belongs only in `lexicon/annotations.csv`. Until the annotation schema
and codebook pilot begins, leave that file header-only. Follow `lexicon/CODEBOOK.md` and add
reviewed case or entity identifiers to `lexicon/referents.csv` before using them in an
annotation row.

## `genocide/`

`genocide/annotations.csv` is the gold sample that evaluates the model-assisted usage layer.
`scripts/13_gold_sample.py` draws about 200 occurrences of `genocide` from the 6,092 the
model annotates in full, both by equal probability and to cover every period and cue
stratum, and writes the candidates to `data/interim/genocide_gold_*.csv`. Two coders code
the sample independently; the agreement between them is what the model's scores are read
against, so a case coded once is not yet gold.

Same schema, same codebook, same rules: the columns are the fifteen in
`lexicon/annotations.csv`, the labels are the ones defined in `lexicon/CODEBOOK.md`
(codebook 2.1, annotation schema 2), and new referents go into `lexicon/referents.csv`
first. A separate file rather than more rows in
`lexicon/annotations.csv` because each sample validates its own candidates: an annotation
whose occurrence is absent from the candidates it is merged against is refused, so one file
per sample is what keeps both merges honest. As with the lexicon file, the pipeline reads it
and never writes it — a rerun regenerates the candidates and the review join, never the
coding.
