# Model annotations

Files below this directory are durable, version-controlled research inputs, exactly as the
ones under `annotations/` are. The difference is who wrote them: `scripts/14_llm_annotate.py`
writes a run once, by hand, against a paid API. Every later step reads it. Nothing rebuilds
it — not a pipeline re-run, not CI, not the deploy.

That is a constraint, not a filing preference. The GitHub Pages deploy rebuilds all derived
data from the pinned corpus, and it can never make a paid API call. A model run therefore has
to arrive the way the human annotations arrive: already present, committed, reviewable as a
diff. A run kept under `data/` would be git-ignored, missing from the deploy, and unciteable.

The rule this whole store exists to keep is the closing line of `docs/PLAN.md` §5:

> No model output may overwrite corpus text, lexicon counts or human annotations.

So: `annotations/` is human-owned and no script writes there. `model_annotations/` is written
by 14 and by nothing else. `scripts/15_usage.py` joins a run to `speeches_flagged.parquet` and
aggregates into `data/derived/usage/`, where the model's labels stay their own fields beside
the corpus rather than becoming part of it. Steps 03, 04, 05, 08, 09, 11 and 12 do not read
this directory at all, so no published lexicon count depends on a model having been run.

## Layout

```
genocide/
  PROMPT.md                    the versioned prompt; its raw bytes are hashed into every run
  current_run.txt              the run id the dashboard shows, or empty for none
  runs/<run_id>/
    manifest.json              model, prompt hash, counts, token usage, status
    annotations.jsonl          one row per annotated occurrence
    failures.jsonl             one row per speech whose response was refused, with the reason
```

One directory per lexicon term, one directory per run. A run id names the day, the model and
the prompt version — `2026-09-05-luna-v1` — because those three are what a reader needs to
tell two runs apart. Runs are append-only and are never edited in place: `annotations.jsonl`
grows as batches return, and a rerun with a changed prompt is a new run id, never a rewrite of
an old one. The prompt hash is recorded in the manifest *and* in every row, so a row can be
matched to the exact prompt text that produced it without trusting the directory name.

`failures.jsonl` is committed alongside the annotations. A speech whose response fails
validation contributes no rows, which leaves a coverage gap; 15 reports that gap rather than
smoothing over it, and the failure file says which speeches and why.

Raw API responses are *not* here. They go to `data/interim/llm_raw/<run_id>/`, which is
git-ignored, because they are large, they carry nothing the validated rows do not, and they
are for debugging one run rather than for citing it.

## `current_run.txt`

One line: the run id under `runs/` that the dashboard reads, or empty when no run has been
selected. It is the only switch in this directory, and changing it is a reviewed diff that
changes what the site shows — which is the point of keeping it as a file rather than as a
default in code. An empty file means the usage layer has no model run to display, and 15 says
so instead of failing.
