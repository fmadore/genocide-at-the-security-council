# Human annotations

Files below this directory are durable, version-controlled research inputs. Pipeline runs
read them but never create, clear or overwrite them.

The lexicon candidate sample and the merged review table are generated under
`data/interim/`, including separate probability, coverage and high-recall-negative sampling
frames. Human work belongs only in `lexicon/annotations.csv`. Until the annotation schema
and codebook pilot begins, leave that file header-only. Follow `lexicon/CODEBOOK.md` and add
reviewed case or entity identifiers to `lexicon/referents.csv` before using them in an
annotation row.
