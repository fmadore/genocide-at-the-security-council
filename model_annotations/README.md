# Model annotations

> **Corpus migration (2026-09-03).** Every run currently under `genocide/runs/`
> was produced against the retired Schoenfeld 1992–2023 corpus. Its identifiers
> and text hashes do not address Sakamoto–Matsuoka v5, so these runs are retained
> only as provenance and must not be joined to the canonical 1946–2024 corpus.
> Both pointer files are intentionally empty. A new run must enumerate the
> 7,747 `genocid*` occurrences in 4,133 speeches from the rebuilt parquet.

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
  PROMPT.md                    the current prompt; its raw bytes are hashed into every run
  prompts/v<n>.md              the superseded prompts, kept so their runs stay readable
  current_run.txt              the run id the dashboard shows, or empty for none
  comparison_run.txt           the run id read against it as a second opinion, or empty
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

## `prompts/`

The superseded prompt texts, one file per version, named `v<n>.md`. `PROMPT.md` holds the
current one and is the only file 14 and 16 render; when it is revised, its old text moves
here unchanged and `PROMPT.md` gets a higher `version:` line.

This directory exists because the digest is the whole provenance. Every run records the
SHA-256 of the prompt file's raw bytes on its manifest and on each of its rows, and 15
publishes that prompt verbatim beside the labels it produced — so before this directory
existed there was exactly one file the digest could be compared against, and editing
`PROMPT.md` made every committed run un-aggregatable at once. Two improvements were declined
on 2 September 2026 for that price alone. Now a run resolves *by digest* against `PROMPT.md`
and every file here, and only a wording this repository no longer holds is refused.

Two rules keep the resolution unambiguous, and `lib.llm.load_prompt_library` enforces both:
a file here is named for the version it declares, and every version here is *below*
`PROMPT.md`'s. So the current text is never duplicated into this directory — the rejected
alternative, an archive holding every version including the current one, reads more evenly
and costs a state in which two copies of one version differ, which is the single failure a
digest cannot arbitrate.

A run's `prompt_version` is checked against the resolved file's own header rather than used
to find it: the digest is what was measured, and the version line is a claim about it.

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

## `comparison_run.txt`

The same one line, naming the run read against the published one as a **counter-instrument**:
a different model, given the same `PROMPT.md`, annotating the same occurrences. 15 computes
the agreement between the two — per field, and per occurrence — and writes it into
`usage.json` and `occurrences.json`. It never merges them: no label from the comparison run
enters a count, replaces a published label, or breaks a tie. A comparison run made against a
different prompt is refused outright, because a disagreement between two models asked two
questions cannot be told apart from a disagreement about one. The prompt archive does not
loosen this: it lets a v1 run and a v2 run each be published, one aggregation at a time,
under the wording each was made with, and never lets one be laid over the other.

What agreement here means is narrow, and it is the reason the file is empty by default.
Two models agreeing shows that a label is **stable across instruments** — the same
questionnaire, answered twice, by two machines with overlapping training and the same blind
spots. It is not validation and not accuracy. The human gold sample under `annotations/` is
the only calibration this project has, and a second model does not become one by agreeing.
