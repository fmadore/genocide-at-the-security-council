# Running the GPU steps on the Bayreuth cluster

Steps 00–05, 08 and 09 run on a laptop. Steps **06 (embeddings)** and **07 (the
topic comparison)** do not: encoding 106,302 speeches is GPU work, and the
stability battery in 07 refits a dozen models. Both run on the University of
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
key. That is a property worth keeping, because this repository is intended to
become public with a citable release.

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
| `04`, `05`, `08`, `09` | anywhere | locked | unchanged; a laptop is fine |

Asking for a GPU that will sit idle means queueing behind everyone who needs
one, so 07 and 10 deliberately do not request one.

### Two environments, and why

`setup_env.sh` builds both.

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

## The cluster, as it actually is

Verified with `sinfo` and `module avail` on **9 August 2026**. These change;
re-check before assuming.

```bash
sinfo -o "%20P %10G %12N %10l %6D %t"
```

| Partition | GPUs | `--gres=` | Time limit |
|---|---|---|---|
| `GPU` | 4× H100 on one node | `gpu:h100:N` | 24 h |
| `normal` (default) | L40, L40S, MI210 — plus many CPU-only nodes | `gpu:l40:N`, `gpu:l40s:N` | 24 h |
| `dev` | up to 2× L40, one CPU node | `gpu:l40:N` | 90 min |
| `edu` | L40S | `gpu:l40s:N` | 24 h |

There is no lowercase `gpu` partition. The default model needs one card of any
of these; `GPU` is requested in `submit_embed.sh` for speed, but an L40 on
`normal` works and usually starts sooner.

**Storage.** Only `/home` is backed up.

| Path | Size | Lifetime | Backed up | Used for |
|---|---|---|---|---|
| `/home/<n>/<account>` | 15 GB | permanent | yes | the repository, archived results |
| `/workdir/<account>` | 3 TB | 60 days | no | venv, HF cache, `data/` |
| `/scratch/<account>` | shared, very large | 10 days | no | scratch I/O |

`setup_env.sh` puts both environments, the model cache and `data/` on `/workdir`,
and the submit scripts copy finished outputs back to `~/unsc-archive` when they
succeed. Set `UNSC_ARCHIVE=off` in `.env` to skip that.

**Watch the `/home` quota.** 15 GB is not much once a project keeps a venv there,
and a full `/home` does not fail politely: it truncates the next `rsync` or
`tar`, leaving a repository that is half old and half new. `archive_outputs`
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
cd ~/un-security-council-debates
cp .env.example .env          # edit if the defaults do not suit
bash scripts/cluster/setup_env.sh
```

That creates the venv on `/workdir`, installs `requirements.lock` with hashes
plus the GPU extras, links `data/`, and prints what torch can see.

Then fetch the corpus and the weights — both need the internet, so both run on
the login node:

```bash
python scripts/00_fetch_data.py
bash scripts/cluster/download_models.sh
```

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

## Acknowledgement

Work using the cluster carries a DFG funding acknowledgement for the hardware —
project **523317330** ("funded by the Deutsche Forschungsgemeinschaft (DFG) –
523317330"), as recorded in the festus-transcribe documentation. Confirm the
current wording with the HPC team before a publication rather than copying it
from here, and add it to `CITATION.cff` and the paper if the GPU steps
contribute to a result.
