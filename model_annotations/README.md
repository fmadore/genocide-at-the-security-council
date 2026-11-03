# Model annotations

## The published run is a complete, merged run

The run the site shows, `2026-11-03-qwen-131k`, was assembled on 3 November 2026 from
the September run `2026-09-08-qwen-131k` and a top-up asked on Festus. It covers every
occurrence of the current corpus, but no human has checked its labels: the gold sample
is uncoded, so it remains an **unvalidated preview**.

- **Coverage.** Qwen3.8-27B (prompt v3) answered all 4,576 speeches and all 8,611
  occurrences of corpus v6.0 (lexicon v8). Its manifest reads `"status": "complete"`
  and lists no gaps.
- **Where the rows come from.** 6,790 rows are carried from `2026-09-08-qwen-131k`,
  which was asked about corpus v5.0, through `carry_over.json` (below), only where the
  text around each occurrence is unchanged; 94 of that run's carried rows were
  superseded by the top-up. The other 812 speeches, new in v6.0, changed near the
  word, or never answered in September, were asked again in four top-up batches with
  the same model, prompt and settings, and merged with the carried rows by
  `scripts/annotation_batches.py merge --carry` ([docs/CLUSTER.md](../docs/CLUSTER.md)).
  The manifest records the carried run under `carried` and the batches under
  `assembly`. The batch directories are not committed.
- **What was missing, and is no longer.** The top-up included the 36 speeches the
  September run never answered, so the published run has no gap.
- **What is excluded.** 24 evidence quotes could not be found in their speech; those
  rows are left out of every discourse figure.
- **Why the build accepts it.** A run must cover the whole population unless its gap
  is authorised in `allow_partial_run.txt`. This one has no gap, so that file is empty
  and the Makefile no longer passes `--allow-partial` to step 15.

**The carried source, `2026-09-08-qwen-131k`, stays committed and unedited.** It was
stopped and published as a preview on 14 September 2026, and the site showed it until
3 November 2026. It annotated 4,097 of the 4,133 speeches and 7,694 of the 7,747
occurrences of the population it was made against (lexicon v6, corpus v5.0). 36
speeches had no accepted response: 34 because the model wrote a display name where an
identifier from the referent list was required, 2 because the response was cut off at
the output limit. Its manifest's `truncation_count` of 4 counts cut-off responses over
both passes, so it is larger than the two speeches missing. 24 of its evidence quotes
could not be found in their speech, and three more were found only by a looser match
(folding quotation marks, dashes, letter case and line-break hyphens) and are marked
as relocated.

**Why the September manifest still says `"status": "in_progress"` and `"completed": null`.**
Read these as "stopped, not finished"; no job is running. Step 14 is the only
program that writes a manifest, and it writes `complete` only when every planned
speech has a valid response, which 36 do not. Run files are append-only and are
never edited by hand, so the status stays as the runner left it. Marking the run
complete by hand would also have made step 14 refuse to resume it. The 36 speeches
were answered instead in the top-up, under the new run identity, and it is
`2026-11-03-qwen-131k` whose manifest reads `complete`.

**Why the September commit ends in `-dirty`.** That manifest's `git_commit` is
`98c473f2a1ae4245049ddebb308c7e8595920317-dirty`: the run was started from a
working copy with uncommitted changes on top of commit `98c473f` (7 September
2026). Those changes are not in git, and the exact code cannot be recovered after
the fact. The 6,790 carried rows of the published run were answered by that code.
What defines the instrument is recorded separately, by checksum, in
`identity.json` and the manifest: the prompt, the referent list, the output
schema (3.1), the occurrence population (lexicon 6), the exact requests sent, the
model revision, the vLLM version, the hardware and the sampling settings
(temperature 0). The cluster
workspace has been pushed from a clean tree since 18 September 2026, so later
runs, the top-up batches included, cite a commit that exists.

The comparison run, `2026-11-03-gemma4` (Gemma 4 31B IT, same prompt), is
published as the second opinion: `comparison_run.txt` names it since 3 November
2026, in place of `2026-09-09-gemma4`, from which it was merged the same way (6,818
carried rows, 781 speeches asked again). The gold sample does not follow it (see
`gold_comparison_run.txt` below). It covers 4,569 of the 4,576 speeches and 8,573 of
the 8,611 occurrences. Its manifest reads `status: partial` and lists the seven
speeches it leaves out (38 occurrences) under `gaps`, each with the failure its batch
last recorded: five cut off at the output limit, `SC07155-01-013` contradicting
itself (as in September), and `SC09711-01-021` naming an unknown referent; more is in
`docs/VALIDATION.md` §7. Two of September's three gaps, `SC03203-01-007` and
`SC09241-02-044`, were answered this time. 33 of its evidence quotes could not be
located. Over the 8,573 occurrences both runs answer, they agree on the referent for
89.2% (kappa 0.876), and 3,112 occurrences are contested on at least one field. The
four hosted runs of August 2026 remain historical provenance for the retired corpus
and must not be joined to the current one.

Files below this directory are durable, version-controlled research inputs, exactly as the
ones under `annotations/` are. The difference is who wrote them: `scripts/14_llm_annotate.py`
writes a run through a pinned open-weights model on university hardware.
`scripts/annotation_batches.py merge` can assemble complete independent batches
into a new run, retaining their hashes and leaving the originals untouched. A
speech no pass could answer is left out only if it is named with `--accept-gap`. Every later step
reads it. Nothing rebuilds it — not a pipeline re-run, not CI, not the deploy.

That is a constraint, not a filing preference. The GitHub Pages deploy rebuilds all derived
data from the pinned corpus, and it never starts a GPU model. A model run therefore has
to arrive the way the human annotations arrive: already present, committed, reviewable as a
diff. A run kept under `data/` would be git-ignored, missing from the deploy, and unciteable.

The rule this whole store exists to keep is stated in `docs/PLAN.md` §5:

> No model output may overwrite corpus text, lexicon counts or human annotations.

So: `annotations/` is human-owned and no script writes there. `model_annotations/` is written
by 14 and the validated batch assembler. `scripts/15_usage.py` joins a run to `speeches_flagged.parquet` and
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
  gold_comparison_run.txt      the second run the gold sample's third frame is cut from, or empty
  carry_over.json              how the runs asked about corpus v5.0 are read against v6.0
  runs/<run_id>/
    manifest.json              weights revision, runtime, prompt, counts, usage, status
    identity.json              checksums of everything that defines the instrument
    probe.json                 the reasoning-level probe the run passed before it started
    annotations.jsonl          one row per annotated occurrence
    failures.jsonl             one row per speech whose response was refused, with the reason
```

`identity.json` and `probe.json` exist for runs made since the integrity repairs of
September 2026; the four hosted runs of August 2026 predate them.

One directory per lexicon term, one directory per run. A run id names the day, the model and
the prompt version — `2026-09-05-qwen-v3` — because those three are what a reader needs to
tell two runs apart. Runs are append-only and are never edited in place: `annotations.jsonl`
grows as responses return, and a rerun with a changed prompt is a new run id, never a rewrite of
an old one. The prompt hash is recorded in the manifest *and* in every row, so a row can be
matched to the exact prompt text that produced it without trusting the directory name.

## `prompts/`

The superseded prompt texts, one file per version, named `v<n>.md`. `PROMPT.md` holds the
current one and is the only file 14 renders; when it is revised, its old text moves
here unchanged and `PROMPT.md` gets a higher `version:` line.

This directory exists because the digest is the whole provenance. Every run records the
SHA-256 of the prompt file's raw bytes on its manifest and on each of its rows, and 15
publishes that prompt verbatim beside the labels it produced — so before this directory
existed there was exactly one file the digest could be compared against, and editing
`PROMPT.md` made every committed run un-aggregatable at once. Two improvements were declined
on 2 September 2026 for that price alone. Now a run resolves *by digest* against `PROMPT.md`
and every file here, and only a wording this repository no longer holds is refused.

Two rules keep the resolution unambiguous, and `lib.prompts.load_prompt_library` enforces both:
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

Raw protocol responses are *not* here. They go to `data/interim/llm_raw/<run_id>/`, which is
git-ignored, because they are large, they carry nothing the validated rows do not, and they
are for debugging one run rather than for citing it.

For self-hosted runs, `manifest.json` also records the immutable Hugging Face revision,
served model id, quantisation, vLLM version, GPU model and count, context length, reasoning
parser, tensor-parallel size, prefix/speculative settings, reasoning parameter placement,
sampling parameters, output ceiling and truncation count. The server command can therefore
be reconstructed from the run record. The four hosted 2026-08 runs predate these fields and
are intentionally not back-filled with guesses.

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

What agreement here means is narrow, and it is the reason the file is empty by default
and was filled only by a recorded decision (FM, 11 October 2026, for `2026-09-09-gemma4`;
its merged successor `2026-11-03-gemma4` took its place on 3 November 2026).
Two models agreeing shows that a label is **stable across instruments** — the same
questionnaire, answered twice, by two machines with overlapping training and the same blind
spots. It is not validation and not accuracy. The human gold sample under `annotations/` is
the only calibration this project has, and a second model does not become one by agreeing.

## `gold_comparison_run.txt`

The second run `scripts/13_gold_sample.py` cuts the gold sample's third frame from. Empty, the
frame is `model_strata`, read off the run in `current_run.txt` alone; naming a run there makes
it the `disagreement` frame, cut from where the two runs differ. It is kept apart from
`comparison_run.txt` so that publishing a second opinion on the site does not redraw the sample
under the coders (decided by FM, 11 October 2026). With Gemma named, the disagreement frame
would take every occurrence either run calls `rejects`; counted against the September runs, it
would have grown the sample from 469 to 799 rows.
Changing this file redraws the sample; see
[`docs/EVALUATION_PLAN.md`](../docs/EVALUATION_PLAN.md), section 3.

## `carry_over.json`

The Qwen and Gemma runs were asked about corpus v5.0. Their files are never edited, so the
move to v6.0 lives in this table, written by `tools/carry_over_runs.py` and applied by
`lib.model_runs.read` to the runs it lists. A row whose speech is unchanged is read as
written; a row whose passage is found unchanged in v6.0 is re-pointed at it; every row of a
speech whose text near an occurrence changed is dropped, and that speech is left to a top-up
run. Labels are never touched. Run without `--write`, the tool checks that every row of every
committed run, read through the table, names an occurrence of the current corpus once.
