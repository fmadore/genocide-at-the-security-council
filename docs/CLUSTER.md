# Running the GPU steps on the Bayreuth cluster

Steps 00–05, 08, 09, 11 and 12 run on a laptop. Steps **06 (embeddings)**,
**07 (the topic comparison)** and **14 (model annotation)** use the University of
Bayreuth HPC cluster, whose GPU nodes are reachable with an ordinary university
account — no separate HPC registration, and no data leaves the university.

The harness here is a trimmed adaptation of the one in the private
`AM-Digital-Research-Environment/festus-transcribe` repository: same `env.sh`
pattern, same login-node-downloads / compute-node-offline split, same
archive-off-scratch habit. What differs is that this pipeline reads a parquet
corpus rather than a folder of media, so there is no job array — one GPU
finishes the corpus in about 25 minutes.

## Nothing identifying is committed

The repository contains no account name, no hostname, no home directory and no
key. **This repository is public**, so that is no longer a precaution against a
future mistake — it is the current state of a published record, and every commit
from here on is published the moment it is pushed.

| Where it belongs | What |
|---|---|
| `~/.ssh/config` on your own machine | the login host, your account, your key |
| `.env` (git-ignored; copy `.env.example`) | your paths on the cluster |
| `$USER`, resolved at runtime | every path the scripts build |

Every script addresses the cluster through an ssh **alias**, so the host appears
once, in a file that is not in git:

```
Host festus
    HostName <the cluster login host>
    User     <your university account>
    IdentityFile ~/.ssh/<your key>
    IdentitiesOnly yes
```

If you call the alias something else, set `UNSC_SSH` in `.env`.

`tests/test_privacy.py` fails the build if an account id, a `user@host` string
or an absolute home directory appears in a tracked file. It is a cheap check
against the obvious mistake — pasting a working command into the documentation.

## What runs where

| Step | Where | Environment | Why |
|---|---|---|---|
| `00_fetch_data.py` | login node | locked | needs the internet; compute nodes have none |
| `01`–`03` | `submit_corpus.sh`, CPU | locked | builds the parquet the other steps read |
| `download_models.sh` | login node | extras | prefetches weights; jobs then run offline |
| `06_embed.py` | `submit_embed.sh`, 1 GPU | extras | 16 min for the corpus on an H100 |
| `07_topics.py` | `submit_topics.sh`, CPU | extras | NMF/UMAP/HDBSCAN are not GPU work |
| `10_lemmatise.py` | `submit_lemmas.sh`, CPU | extras | spaCy parallelises over processes |
| `download_annotation_model.sh` | login node | vLLM | prefetches one pinned checkpoint |
| `14_llm_annotate.py` | `submit_annotate.sh`, GPU | locked + client overlay; vLLM server | interprets occurrences through loopback |
| `04`, `05`, `08`, `09`, `11`, `12` | anywhere | locked | unchanged; a laptop is fine |

Asking for a GPU that will sit idle means queueing behind everyone who needs
one, so 07 and 10 deliberately do not request one.

### Three environments, and why

`setup_env.sh` builds all three.

**Locked** (`/workdir/$USER/unsc/venv`) is `requirements.lock` installed with
`--require-hashes`, and nothing else. Everything that produces a published figure
runs here, so those artifacts come from exactly the environment CI validates.

**Extras** (`/workdir/$USER/unsc/venv-extras`) is `requirements.txt` plus
`requirements-cluster.txt`, resolved freely. It has to be free: `umap-learn`
needs `numba`, and no `numba` release yet supports the numpy version the lock
pins. Installed into one shared environment, pip resolves that by silently
downgrading numpy — and the corpus would then be built by an environment that no
longer matches its own reproducibility record. Splitting them means an optional
step can never move the pinned pipeline.

The consequence is visible and intended: a manifest from step 06 or 10 will name
a different numpy from one written by step 01. `setup_env.sh` prints the
differences when it finishes, and every run records its own resolved versions.
Lift the split when numba catches up — nothing else depends on it.

**vLLM** (`/workdir/$USER/unsc/venv-vllm`) contains only the pinned inference
server and the Torch stack it resolves. It cannot modify either analytical
environment. Step 14 itself uses the locked interpreter plus an OpenAI protocol
client installed into a separate target directory; only JSON crosses between
that process and vLLM. New run manifests record both sides.

## Model annotation

### Independent batches for future models

Keep the running unbatched Qwen run unchanged. For the second model, create a
fixed plan, then use a Slurm array. Each task owns a distinct run directory;
the array concurrency cap controls simultaneous jobs, not requests per GPU.
Each task still runs its model-specific reasoning probe before annotation.

```bash
python scripts/annotation_batches.py plan --size 250 --output data/interim/second-model-plan.json
# For the current 4,133-speech corpus the command prints indices 0-16.
# Qwen example: at most two single-H100 tasks concurrently.
UNSC_ANNOTATION_MODEL=qwen UNSC_RUN_ID=second-model-v3 \
  UNSC_BATCH_PLAN=data/interim/second-model-plan.json \
  sbatch --array=0-16%2 --partition=GPU --gres=gpu:h100:1 \
  scripts/cluster/submit_annotate.sh
```

Choose the actual model profile and GPU resources together. The configured
DeepSeek profile needs four H100s per task and tensor parallelism four:
use `UNSC_ANNOTATION_MODEL=deepseek VLLM_TENSOR_PARALLEL_SIZE=4`,
`--gres=gpu:h100:4`, and initially `%1`. Two or three concurrent tasks require
enough GPUs for two or three full model replicas; sharding does not reduce
the memory needed for model weights. Complete its serving smoke first.

The plan distributes corpus-ordered speeches across batches, contains every
speech exactly once, and is bound into each run's identity. Do not regenerate
it during a run. A timeout preserves completed responses. Resubmit only the
unfinished array indices with the same base run ID, plan and model settings
(for example `--array=3,7%2`); never submit a second writer for a live index.
An incomplete batch retries unfinished speeches on resume, including rejected
responses. A completed batch is immutable and must not be resubmitted.

Check each batch manifest's `status`, not just Slurm's exit code: a pass can
end normally while recording rejected speeches. After every batch completes,
assemble a new run:

```bash
python scripts/annotation_batches.py merge \
  --plan data/interim/second-model-plan.json \
  --output model_annotations/genocide/runs/second-model-v3 \
  model_annotations/genocide/runs/second-model-v3-batch-*
```

Assembly checks identities, settings, exact population coverage and duplicate
occurrences. It rejects incomplete, missing or overlapping batches. Original
shards remain untouched; the merged manifest retains their hashes, usage,
validation counters and probe hashes. The assembled run is for downstream
review, not for resuming inference. Publication still requires explicit run
selection and research review.

The server binds `127.0.0.1`, uses weights prefetched at an immutable Hugging
Face revision, and runs offline on the compute node. No API key is involved.

```bash
# Login node: install only the annotation environments when the corpus is
# already prepared. Use setup_env.sh instead on a new cluster account.
bash scripts/cluster/setup_annotation_env.sh
UNSC_ANNOTATION_MODEL=qwen bash scripts/cluster/download_annotation_model.sh

# A bounded smoke writes only under data/interim/. Qwen's bf16 checkpoint needs
# an H100; the annotation profile remains identical to the eventual corpus run.
UNSC_ANNOTATION_MODEL=qwen UNSC_RUN_ID=2026-09-04-qwen-smoke \
  UNSC_LIMIT=12 UNSC_SMOKE=1 sbatch --partition=GPU --gres=gpu:h100:1 \
  --time=02:00:00 scripts/cluster/submit_annotate.sh

# Interactive serving, when inspecting requests through an SSH tunnel.
UNSC_ANNOTATION_MODEL=qwen sbatch scripts/cluster/serve_annotation.sh
```

`qwen` is the primary profile; `gemma` (Google Gemma 4 31B IT) is the selected
second model. `deepseek` is retained as an unused optional profile.
Gemma uses `enable_thinking=true`, not a graded reasoning-effort ladder:
the probe aliases `low` to off and `high` to on, and the runtime records the
actual boolean parameter. This follows the pinned template and the
[official Gemma model card](https://huggingface.co/google/gemma-4-31B-it#2-thinking-mode-configuration).
The Gemma run uses two H100s per task for context/cache headroom, with at most
two simultaneous batch tasks. Its smoke must pass before the array starts.
The common temperature/top-p settings remain fixed for comparison with Qwen;
they differ from Google's general sampling recommendation, which is recorded
as a comparison-design choice rather than silently changing the instrument.
Their revisions and reasoning placements live in
`scripts/cluster/env.sh`. `submit_annotate.sh` traps every exit path and stops
the server, so cancellation cannot leave a process holding the GPU. Before it asks the corpus,
the job runs the selected profile's reasoning ladder over the same three speeches and writes
`data/interim/model_annotation_probes/<run-id>/probe.json`. Identical resumed jobs reuse a
passed probe; a flat ladder stops in words before a corpus row is written.

The client allows one hour per response. At the observed H100 decode rate,
the largest 65,536-token output allowance can take more than 15 minutes;
the transport timeout must not prematurely cut off maximum reasoning.

The server explicitly sets `--max-num-seqs` from `VLLM_MAX_NUM_SEQS` (default 4),
matching the annotation client's usual concurrency. On 8 September, job 760377
failed during startup because vLLM chose 1,024 sequences while the hybrid Qwen
model had only 311 available Mamba cache blocks. The bounded setting preserves
the configured context and 0.90 GPU-memory fraction. Both serving entrypoints
use it, and new runtime records include it. Increase it only after checking
cache capacity on the target hardware; existing run identities must not silently
absorb a changed serving configuration.

The default context is now 131,072 tokens. A pinned-tokenizer audit of all 4,133
current genocide-bearing speeches on 8 September found a maximum of 79,392
tokens for prompt plus the full requested output allowance. The former 65,536
window rejected the second probe speech before generation. The H100 reported
271,610 cache-token capacity. No speech or output allowance was shortened.

### Festus operating guidance checked on 8 September 2026

The [Festus system guide](https://www.hpc.uni-bayreuth.de/clusters/festus/)
and [GPU example](https://www.hpc.uni-bayreuth.de/material/example_jobs/pytorch_gpu/)
confirm `--partition=GPU --gres=gpu:h100:1` and the `python/3.12.4` module.
Use `python3` after loading the module, or the explicit activated venv interpreter;
the system `python` command alone is not a reliable module selector. The annotation
preflight uses `$VENV/bin/python3`. The live GPU partition reports a 24-hour limit.

Before submission, run the offline preflight with the annotation environment:

```bash
source scripts/cluster/env.sh
load_python
activate_annotator
configure_annotation_model
"$VENV/bin/python3" scripts/preflight_annotation.py
```

It rejects the retired corpus by row count and schema, verifies SDK call compatibility
and adapter body preservation without network access, and checks cached model shards. It does not certify model
accuracy or weight hashes. The batch script repeats it before starting vLLM.
Package and vLLM compilation caches default to `/workdir` beside the serving venv,
with `PIP_CACHE_DIR` and `VLLM_CACHE_ROOT` overrides. The server subprocess removes
the client overlay from `PYTHONPATH` before activating its own environment.

### The four jobs that failed at zero elapsed time, and what it was

On 4 and 5 September 2026 four annotation jobs failed the same way: `748010` never started,
`748011` and `748012` were allocated on `dev`, and `748013` waited fifteen hours for an H100
on `GPU`. Each ended with its batch step `CANCELLED` at `00:00:00` elapsed and no output file
anywhere on the filesystem.

An earlier revision of this document read that as a partition or node-startup failure. **It
was not.** On 7 September `df -h ~` reported `/home` at **15 G of 15 G, 0 available**. The
job's own log is `logs/annotate-%j.out`, which lives on `/home`; Slurm creates it *before* it
runs the first line of the script, and when it cannot, it cancels the batch step and records
an empty allocation. The absence of the log was not a symptom to be explained around — it was
the whole diagnosis, and it pointed at the quota this document already warns about two
sections below.

The lesson is cheap to state and was expensive to miss: **a job that fails at zero elapsed
time with no log is a filesystem problem until proved otherwise.** Read `df -h ~` before
reading anything about Slurm, the partition, vLLM or the model. Nothing in these four failures
is evidence about any of them, and the `dev`/L40 path remains untested rather than suspect.

Clearing `~/.cache/pip` recovered 5.1 G and returned `/home` to 71%. Job `760172` was then
submitted with the H100 command above and queued normally.

## The cluster, as it actually is

Verified with `sinfo` and `module avail` on **9 August 2026**, and the partition
availability re-checked on **10 August 2026**. These change; re-check before
assuming.

```bash
sinfo -o "%20P %10G %12N %10l %6D %t"
```

| Partition | GPUs | `--gres=` | Time limit | Usable by this account |
|---|---|---|---|---|
| `GPU` | 4× H100 on one node | `gpu:h100:N` | 24 h | yes |
| `normal` (default) | L40, L40S, MI210 — plus many CPU-only nodes | `gpu:l40:N`, `gpu:l40s:N` | 24 h | yes |
| `dev` | up to 2× L40, one CPU node | `gpu:l40:N` | 90 min | yes |
| `edu` | L40S | `gpu:l40s:N` | 24 h | **no** — rejected as an invalid account/partition combination |
| `znver5` | none, 128 CPU cores | — | — | **no** — `AVAIL: down` |

There is no lowercase `gpu` partition. The default model needs one card of any
of these; `GPU` is requested in `submit_embed.sh` for speed, but an L40 on
`normal` works and usually starts sooner.

**The last two columns matter more than they look.** On 10 August 2026 `normal`
was fully allocated — 9,408 of 9,408 cores — and a 16-core CPU job queued there
was scheduled to start **two weeks later**, while `edu` and `znver5` sat
completely idle. Idle is not the same as available: `edu` refuses this account,
and `znver5` is administratively down. That leaves `dev` as the only partition
that can start a job promptly when `normal` is saturated, at the cost of a
90-minute wall.

Ask before waiting:

```bash
squeue --me -j <jobid> --start                  # N/A means Slurm cannot even guess
sinfo -o "%.10P %.10a %.8t %.5D %.14C"          # AVAIL, state, and idle cores
sbatch --partition=<p> --test-only <script>     # where would this actually land
```

`--test-only` answers "if this partition ran it, when" — it is not a promise
that the partition will run anything. It happily estimated a start time on
`znver5`, which is down; the `AVAIL` column in `sinfo` is the one that decides.
A job submitted to a down partition sits in `PENDING (PartitionDown)` forever
rather than failing, so it is worth reading the reason in `squeue` after
submitting rather than assuming a queued job is a waiting one.

**Storage.** Festus documents `/workdir` and `/scratch` as purgeable and unbacked.
Keep a separate durable copy of results and verify the account's home backup policy.

| Path | Size | Lifetime | Backed up | Used for |
|---|---|---|---|---|
| `/home/<n>/<account>` | 10 GB documented; 15 GB observed for this account | permanent | verify account policy | the repository, archived results |
| `/workdir/<account>` | 3 TB | 60 days | no | venv, HF cache, `data/` |
| `/scratch/<account>` | shared, very large | 10 days | no | scratch I/O |

`setup_env.sh` puts both environments, the model cache and `data/` on `/workdir`,
and the submit scripts copy finished outputs back to `~/unsc-archive` when they
succeed. Set `UNSC_ARCHIVE=off` in `.env` to skip that.

**Watch the `/home` quota.** 15 GB is not much once a project keeps a venv there,
and a full `/home` does not fail politely. It truncates the next `rsync` or
`tar`, leaving a repository that is half old and half new, and it kills every
submitted job at zero elapsed time, because Slurm opens `logs/annotate-%j.out`
on `/home` before it runs a line of the script. Four jobs were lost to that in
September 2026 and misread as a partition fault; the account above is worth
reading before debugging a job that produced no log. `archive_outputs`
therefore checks free space and declines with a warning rather than filling the
disk, and `push_code.sh` verifies its transfer arrived instead of assuming. If
either complains:

```bash
ssh festus 'df -h ~; du -sh ~/* ~/.[a-z]* | sort -rh | head'
```

`~/.cache/pip` is usually the easiest several gigabytes to reclaim — it is a
download cache, and pip refills it as needed.

`data/` inside the repository is made a **symlink** to `/workdir/$USER/unsc/data`
rather than being relocated by an environment variable. `lib/paths.py` resolves
everything relative to the repository root and `lib/artifacts.py` records
provenance paths relative to it; a symlink keeps both true, where a
`UNSC_DATA=/workdir/...` override would make `describe_file` raise on every
manifest it wrote.

**Python.** `module -t avail python` currently offers 3.10.20, 3.12.4 and
3.13.3. The repository targets 3.12 (`pyproject.toml`), which is what
`env.sh` loads. Override with `UNSC_PYTHON_MODULE` in `.env`.

## Setup, once

```bash
bash scripts/cluster/push_code.sh
```

Then on the cluster:

```bash
cd ~/genocide-at-the-security-council
cp .env.example .env          # edit if the defaults do not suit
bash scripts/cluster/setup_env.sh
```

That creates the venv on `/workdir`, installs `requirements.lock` with hashes
plus the GPU extras, links `data/`, and prints what torch can see.

Then fetch the corpus and the weights — both need the internet, so both run on
the login node:

```bash
make raw                                   # 00: fetch, or MD5-verify, the pinned corpus
bash scripts/cluster/download_models.sh
```

The step order is the repository's `Makefile`, which the batch scripts below call into
(`make cluster` is 06, 07 and the lemma re-run of 05, in dependency order); it is not
copied here.

## Running

```bash
sbatch scripts/cluster/submit_corpus.sh    # 01-03, CPU
sbatch scripts/cluster/smoke.sh            # 45 min on dev: proves the GPU path
sbatch scripts/cluster/submit_embed.sh     # 06, one GPU
sbatch scripts/cluster/submit_topics.sh    # 07, CPU
sbatch scripts/cluster/submit_lemmas.sh    # 10, CPU
```

Step 10 builds a lemma layer so that `killing`, `killed` and `kills` share a row
in the lexicometry instead of competing for three. Afterwards, re-run 05 over it:

```bash
UNSC_VOCABULARY=lemma sbatch scripts/cluster/submit_lexical.sh
```

Note which environment that job uses: 05 belongs to the release pipeline, so it
runs **locked**, even though its extra input was produced by the extras
environment. A parquet of strings crosses between the two; an environment does
not.

That writes `data/derived/lexical_lemma/` and leaves `data/derived/lexical/`
alone — the surface tables are what the dashboard reads and what the
`docs/PLAN.md` §1.1 audit is being conducted against. The lexicon itself is never
lemmatised: it matches surface forms, and folding `genocides` into `genocide`
before step 03 would move every published count and restart that audit.

Step 10 now writes a content-validated layer: each row includes a SHA-256 of
the speech body, and the manifest records the tokenizer, schema and parquet
checksum. Steps 05 and 18 reject old, incomplete, altered or misaligned layers.
The older 106,302-speech layer must be regenerated before use on the current
corpus. `--limit` writes a smoke layer and a separate smoke note.

For matched keyness sensitivity, tag only the complete saved comparison:

```bash
python scripts/18_lexical_robustness.py
python scripts/10_lemmatise.py --pairs data/derived/lexical_robustness/pairs.csv --processes 4
python scripts/18_lexical_robustness.py --lemma-layer data/derived/lemmas_matched
```

This CPU workflow needs the spaCy/model dependencies for step 10 only. It writes
`lemmas_matched/` and `lexical_robustness_lemma/`, with the same 3,950 pairs and
token denominators as the surface comparison. A matched layer cannot stand in
for a full-corpus layer. The CSV comparison reports exact type membership and
ranks; `lemma_forms.csv` records every changed surface/lemma pair in the selected
speeches. `lemma_meeting_influence.csv` and `lemma_deletion_effects.parquet`
retain the corresponding meeting-deletion checks for the lemma ranking.
The comparison CSV includes target/control counts before and after lemmatization
and a `partly_lemmatized` flag for forms with changed and unchanged occurrences.
This exposes potentially misleading residual forms without treating every
context-dependent split as a tagging error.
Both analyses use the same stoplist, and the manifest reports all
observed stopword leaks. For a regenerated full layer, `make robustness-lemma`
runs the comparison using `data/derived/lemmas/`.

Watch with `squeue --me`, and read `logs/embed-<jobid>.out`.

`sinfo` marks some nodes `idle~`, meaning powered down. A job that lands on one
sits in `CONFIGURING` for several minutes with an empty log while the node boots
— the `dev` GPU node is usually in this state, so the smoke test is the run most
likely to look stuck when it is merely waiting. It is not a failure; give it five
minutes before investigating.

`smoke.sh` encodes a few hundred speeches into `data/derived/embeddings_smoke/`.
`06_embed.py` diverts its output whenever `--limit` is set, so a smoke test
cannot overwrite a real run — `artifacts.atomic_directory` replaces its target
wholesale, and the replacement would look exactly like a corpus artefact.

Environment variables override the defaults without editing anything:

```bash
UNSC_MODEL=qwen3-4b sbatch scripts/cluster/submit_embed.sh
UNSC_SAMPLE=40000 UNSC_K=40 sbatch scripts/cluster/submit_topics.sh
```

## Getting results back

Run locally:

```bash
bash scripts/cluster/fetch_results.sh
bash scripts/cluster/fetch_results.sh --watch 643031   # wait for the job first
bash scripts/cluster/fetch_results.sh --what topics
```

This pulls `data/derived/embeddings/`, `data/derived/topics/` and `notes/`.
`/workdir` is not backed up and purges after 60 days, so pull once a run
finishes rather than treating the cluster as storage.

## Choosing a model

`config/embedding_models.yml` is the registry, and it is a hand-edited analysis
input rather than a flag: changing the encoder changes every distance
downstream. It records why each model is there, and why the obvious alternatives
are not — gated repositories cannot be prefetched by an unattended job, and
models needing `trust_remote_code` execute arbitrary code under your cluster
account and are harder to reconstruct from a manifest.

`06_embed.py` asserts the dimensionality the registry declares against the model
that actually loads, and fails rather than writing an artefact that misdescribes
itself.

## What the GPU steps are, and are not

`06` produces vectors. A cosine between two of them says two speeches used
similar language. It is not agreement, influence, or a shared position, and
`docs/PLAN.md` §4 governs what may be built on it.

`07` produces a **comparison and an evaluation, not a release artefact**. Nothing
in `web/` reads `data/derived/topics/`, and `export_web.py` does not know it
exists. `docs/PLAN.md` §4 defers topic modelling until there is a research
question collocates and agenda labels cannot answer; what 07 supplies is the
evidence needed to decide that — coherence, stability under resampling,
sensitivity to `k`, topic composition, and a blinded word-intrusion task for a
human to complete. Read `evaluation.json` before either model's own output.

The intrusion task comes back as two files, and the split is the point.
`intrusion_task.csv` is what you fill in: an opaque item id, six words, and a
blank `intruder_guess` for the word that does not belong. `intrusion_key.csv`
holds the answers — **do not open it first**, and do not open `nmf.json` either,
because it publishes the topic word lists the task is drawn from. Items from
both models are shuffled together and their ids decode to nothing, so the file
cannot be answered except by reading the words. Leave a row blank to abstain;
an abstention is reported separately rather than counted wrong. Then, locally:

```bash
python scripts/score_intrusion.py
```

That writes `intrusion_score.json` beside the task and `notes/07_intrusion.md`,
with accuracy per model, its denominator, and the 1-in-6 chance rate to read it
against. Pass `--task` if the completed file lives outside the repository; it is
recorded by name and hash rather than by path, so a note never carries a home
directory off the cluster.

Its `calibration` block is worth reading first. NMF's abstention threshold is not
a setting: the job refits the baseline on the frozen sample dealt out at random
and takes the 95th percentile of the shares that produces, so "unassigned" means
"no more concentrated than noise" rather than "below a number somebody typed".
The block records the threshold, the floor 1/k it must beat, both share
distributions and the unassigned share across a range of thresholds. A run whose
`binds` is false found a baseline that concentrates no better on the Council than
on shuffled words, and its topics should be read as labels rather than findings.

## Acknowledgement

Work using the cluster carries a DFG funding acknowledgement for the hardware —
project **523317330** ("funded by the Deutsche Forschungsgemeinschaft (DFG) –
523317330"), as recorded in the festus-transcribe documentation. Confirm the
current wording with the HPC team before a publication rather than copying it
from here, and add it to `CITATION.cff` and the paper if the GPU steps
contribute to a result.
