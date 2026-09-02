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
`scripts/13_gold_sample.py` draws 688 distinct occurrences of `genocide` from the 6,092 the
model annotates in full, in three frames, and writes the candidates to
`data/interim/genocide_gold_*.csv`. Two coders code every one of them independently; the
agreement between them is what the model's scores are read against, so a case coded once is
not yet gold.

**Three frames, and they are never pooled.** 120 occurrences by equal probability, which is
the only part of the sample that estimates anything about the corpus and is weighted by its
own inclusion probabilities; 80 more covering every period and usage-cue stratum, so that
nothing is missing entirely; and 535 drawn from the strata the two committed model runs read
differently — every occurrence either run called `rejects_or_denies`, every one whose
referent predates the case it names, and a hundred each of the three large contested strata.
That third frame is what makes anything per class sayable: an equal-probability draw of 200
holds about three rejections. It is read unweighted, and a rate computed over the union of
the frames would estimate nothing. Every candidate row records the inclusion probability
that put it there.

**A model label is a sampling stratum, exactly as the cue is.** The third frame is cut from
`model_annotations/`, and what it says about an occurrence is that it is worth a coder's
time — never what the coder should write. Nothing under this directory is read while a
candidate is being drawn, and nothing here is written by any script.

Same schema, same codebook, same rules: the columns are the fifteen in
`lexicon/annotations.csv`, the labels are the ones defined in `lexicon/CODEBOOK.md`
(codebook 2.2, annotation schema 2), and new referents go into `lexicon/referents.csv`
first. A separate file rather than more rows in
`lexicon/annotations.csv` because each sample validates its own candidates: an annotation
whose occurrence is absent from the candidates it is merged against is refused, so one file
per sample is what keeps both merges honest. As with the lexicon file, the pipeline reads it
and never writes it — a rerun regenerates the candidates and the review join, never the
coding.
