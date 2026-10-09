# Model annotations

## The published run is a stopped, partial run

The run the site shows, `2026-09-08-qwen-131k`, is **a partial run that was stopped
and published as a preview** on 14 September 2026. It is not finished, and no
human has checked its labels: the gold sample is uncoded.

- **Coverage.** Qwen3.8-27B (prompt v3) annotated 4,097 of the 4,133 speeches and
  7,694 of the 7,747 occurrences of the population it was made against (lexicon
  v6). Lexicon v8 later added the 40 accented *génocidaires*, which the run
  predates, so it now covers 7,694 of 7,787 occurrences.
- **What is missing.** 36 speeches have no accepted response: 34 because the
  model wrote a display name where an identifier from the referent list was
  required, 2 because the response was cut off at the output limit. The
  manifest's `truncation_count` of 4 counts cut-off responses over both passes,
  so it is larger than the two speeches still missing.
- **What is excluded.** 24 evidence quotes could not be found in their speech;
  those rows are left out of every discourse figure. Three more were found only
  by a looser match (folding quotation marks, dashes, letter case and line-break
  hyphens) and are marked as relocated.
- **Why the build accepts it.** A run must cover the whole population unless its
  gap is authorised. `allow_partial_run.txt` names this run, so the Makefile
  passes `--allow-partial` to step 15 for it alone; any other selected run is
  held to full coverage.

**Why the manifest still says `"status": "in_progress"` and `"completed": null`.**
Read these as "stopped, not finished"; no job is running. Step 14 is the only
program that writes a manifest, and it writes `complete` only when every planned
speech has a valid response, which 36 do not. Run files are append-only and are
never edited by hand, so the status stays as the runner left it. Marking the run
complete would also make step 14 refuse to resume it, closing the way to a later
pass over the 36 speeches under the same run identity.

**Why the commit ends in `-dirty`.** The manifest's `git_commit` is
`98c473f2a1ae4245049ddebb308c7e8595920317-dirty`: the run was started from a
working copy with uncommitted changes on top of commit `98c473f` (7 September
2026). Those changes are not in git, and the exact code cannot be recovered after
the fact. What defines the instrument is recorded separately, by checksum, in
`identity.json` and the manifest: the prompt, the referent list, the output
schema (3.1), the occurrence population (lexicon 6), the exact requests sent, the
model revision, the vLLM version, the hardware and the sampling settings
(temperature 0). The cluster
workspace has been pushed from a clean tree since 18 September 2026, so later
runs cite a commit that exists.

The comparison run (Gemma 4 31B IT, same prompt) is not published:
`comparison_run.txt` is empty. The four hosted runs of August 2026 remain
historical provenance for the retired corpus and must not be joined to v5.

Files below this directory are durable, version-controlled research inputs, exactly as the
ones under `annotations/` are. The difference is who wrote them: `scripts/14_llm_annotate.py`
writes a run through a pinned open-weights model on university hardware.
`scripts/annotation_batches.py merge` can assemble complete independent batches
into a new run, retaining their hashes and leaving the originals untouched. Every later step
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

What agreement here means is narrow, and it is the reason the file is empty by default.
Two models agreeing shows that a label is **stable across instruments** — the same
questionnaire, answered twice, by two machines with overlapping training and the same blind
spots. It is not validation and not accuracy. The human gold sample under `annotations/` is
the only calibration this project has, and a second model does not become one by agreeing.
