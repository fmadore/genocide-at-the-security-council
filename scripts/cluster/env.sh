#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Shared settings for every cluster script. Sourced by setup_env.sh,
# download_models.sh, smoke.sh and the submit_*.sh jobs.
#
# Nothing here identifies a person or a machine. Account name, host and paths
# all come from $USER, from the `festus` ssh alias in your own ~/.ssh/config, or
# from $REPO/.env — which is git-ignored. See docs/CLUSTER.md.
#
# Every value can be overridden from the environment without editing this file:
#     UNSC_VENV=/scratch/$USER/venv sbatch scripts/cluster/submit_embed.sh
# ---------------------------------------------------------------------------

# Repo root. Under `sbatch` the submit script sets REPO from $SLURM_SUBMIT_DIR
# first — the spooled copy of the script cannot locate the repository itself.
REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Load $REPO/.env (KEY=VALUE). Variables already set in the environment win, so
# `UNSC_MODEL=x sbatch ...` still overrides the file. $USER/$HOME are expanded.
load_dotenv() {
  local f="$REPO/.env" line key val
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"; val="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ -z "$key" ]] && continue
    val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
    val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
    val="${val//\$\{USER\}/$USER}"; val="${val//\$USER/$USER}"
    val="${val//\$\{HOME\}/$HOME}"; val="${val//\$HOME/$HOME}"
    [[ -n "${!key+x}" ]] && continue   # never clobber an already-set variable
    export "$key=$val"
  done < "$f"
}
load_dotenv

# Two environments, created by setup_env.sh. /home is 15 GB and the torch wheels
# alone are ~4 GB, so both live on /workdir.
#
# `VENV` is the release pipeline's environment: requirements.lock, installed with
# hashes, and nothing else. Steps 00-05, 08 and 09 run here, so the artefacts
# that reach the dashboard are built by exactly the environment CI validates.
#
# `EXTRAS_VENV` is for the optional steps 06, 07 and 10. They cannot share the
# first one: umap-learn needs numba, numba does not yet support the numpy the
# lock pins, and pip resolves that by quietly downgrading numpy — which would
# leave the corpus being built by an environment that no longer matches its own
# reproducibility record. Keeping them apart means the optional steps never get
# to move the pinned pipeline. Their manifests record the versions they actually
# ran under, which is how any difference is read back later.
VENV="${UNSC_VENV:-/workdir/$USER/unsc/venv}"
EXTRAS_VENV="${UNSC_EXTRAS_VENV:-/workdir/$USER/unsc/venv-extras}"
VLLM_VENV="${UNSC_VLLM_VENV:-/workdir/$USER/unsc/venv-vllm}"
LLM_CLIENT_PACKAGES="${UNSC_LLM_CLIENT_PACKAGES:-/workdir/$USER/unsc/llm-client}"

# Hugging Face cache — /workdir (3 TB), never /home (15 GB).
export HF_HOME="${HF_HOME:-/workdir/$USER/unsc/hf_cache}"

# Where the corpus lives on the cluster. `data/` inside the repo is a symlink to
# this, created by setup_env.sh: 900 MB of parquet does not belong on /home, but
# lib/paths.py resolves everything relative to the repository root and
# lib/artifacts.py records provenance paths relative to it too. A symlink keeps
# both true without giving the pipeline an environment-dependent path.
DATA_STORE="${UNSC_DATA_STORE:-/workdir/$USER/unsc/data}"

# Lmod module providing Python. `module -t avail python` on Festus currently
# offers 3.10.20, 3.12.4 and 3.13.3; the repository targets 3.12 (pyproject.toml).
PYTHON_MODULE="${UNSC_PYTHON_MODULE:-python/3.12.4}"

# Run `module load` safely under the submit scripts' `set -euo pipefail`.
# lmod's bash init reads $LD_LIBRARY_PATH; if it is unset (as on a freshly
# powered-up node) `set -u` makes `module` abort with "LD_LIBRARY_PATH: unbound
# variable", which silently leaves the module unloaded and the venv interpreter
# then cannot find its shared libraries. Bind the variable and relax `set -u`
# only around the call, then restore it.
_module_load() {
  command -v module >/dev/null 2>&1 || return 0
  local had_u=0; case "$-" in *u*) had_u=1;; esac
  set +u
  export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
  module load "$@"
  local rc=$?
  [ "$had_u" -eq 1 ] && set -u
  return $rc
}

# A no-op off-cluster, so the same scripts run on a laptop for a smoke test.
load_python() { _module_load "$PYTHON_MODULE"; }

_activate() {
  local path="$1" what="$2"
  if [[ ! -f "$path/bin/activate" ]]; then
    echo "ERROR: no $what environment at $path — run scripts/cluster/setup_env.sh on the login node first." >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$path/bin/activate"
  echo "==> environment: $what ($path)"
}

#: The locked environment — steps 00-05, 08, 09.
activate_venv() { _activate "$VENV" "locked"; }

#: The optional-steps environment — 06, 07, 10.
activate_extras() { _activate "$EXTRAS_VENV" "extras"; }

# The annotator uses the locked pipeline interpreter plus a target-installed
# protocol client. This keeps the release environment byte-for-byte locked and
# keeps vLLM's torch resolver in the third, serving-only environment.
activate_annotator() {
  activate_venv
  if [[ ! -d "$LLM_CLIENT_PACKAGES" ]]; then
    echo "ERROR: no annotation client at $LLM_CLIENT_PACKAGES — run setup_env.sh." >&2
    exit 1
  fi
  export PYTHONPATH="$LLM_CLIENT_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
  echo "==> overlay: annotation protocol client ($LLM_CLIENT_PACKAGES)"
}

activate_vllm() { _activate "$VLLM_VENV" "vLLM serving"; }

# Immutable instrument profiles. Override deployment state (port, cache,
# concurrency) freely; changing an analytical input such as revision,
# quantisation or reasoning level must produce a different manifest/run id.
configure_annotation_model() {
  local profile="${UNSC_ANNOTATION_MODEL:-qwen}"
  case "$profile" in
    qwen)
      VLLM_MODEL_ID="${VLLM_MODEL_ID:-Qwen/Qwen3.8-27B}"
      VLLM_MODEL_REVISION="${VLLM_MODEL_REVISION:-1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0}"
      VLLM_REASONING_PARSER="${VLLM_REASONING_PARSER:-qwen3}"
      VLLM_REASONING_EFFORT="${VLLM_REASONING_EFFORT:-xhigh}"
      VLLM_REASONING_LEVELS="${VLLM_REASONING_LEVELS:-low,medium,xhigh}"
      VLLM_REASONING_LOCATION="${VLLM_REASONING_LOCATION:-chat_template_kwargs}"
      ;;
    deepseek)
      VLLM_MODEL_ID="${VLLM_MODEL_ID:-deepseek-ai/DeepSeek-V4-Flash-0731}"
      VLLM_MODEL_REVISION="${VLLM_MODEL_REVISION:-7872f01b1d1fe23eabc4c98b48bffcef5a386062}"
      VLLM_REASONING_PARSER="${VLLM_REASONING_PARSER:-deepseek_v4}"
      VLLM_REASONING_EFFORT="${VLLM_REASONING_EFFORT:-max}"
      VLLM_REASONING_LEVELS="${VLLM_REASONING_LEVELS:-low,high,max}"
      VLLM_REASONING_LOCATION="${VLLM_REASONING_LOCATION:-request}"
      ;;
    gemma)
      VLLM_MODEL_ID="${VLLM_MODEL_ID:-google/gemma-4-31B-it}"
      VLLM_MODEL_REVISION="${VLLM_MODEL_REVISION:-842da3794eaa0b77d5f08bae87a17459d91ff475}"
      VLLM_REASONING_PARSER="${VLLM_REASONING_PARSER:-gemma4}"
      VLLM_REASONING_EFFORT="${VLLM_REASONING_EFFORT:-high}"
      VLLM_REASONING_LEVELS="${VLLM_REASONING_LEVELS:-low,medium,high}"
      VLLM_REASONING_LOCATION="${VLLM_REASONING_LOCATION:-chat_template_kwargs}"
      ;;
    *) echo "ERROR: unknown UNSC_ANNOTATION_MODEL '$profile' (qwen, deepseek, gemma)." >&2; exit 2 ;;
  esac
  VLLM_PORT="${VLLM_PORT:-8000}"
  VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-65536}"
  VLLM_TENSOR_PARALLEL_SIZE="${VLLM_TENSOR_PARALLEL_SIZE:-1}"
  VLLM_QUANTIZATION="${VLLM_QUANTIZATION:-none}"
  VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.90}"
  VLLM_TEMPERATURE="${VLLM_TEMPERATURE:-0.0}"
  VLLM_TOP_P="${VLLM_TOP_P:-1.0}"
  VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:$VLLM_PORT/v1}"
  export VLLM_MODEL_ID VLLM_MODEL_REVISION VLLM_REASONING_PARSER
  export VLLM_REASONING_EFFORT VLLM_REASONING_LOCATION VLLM_PORT
  export VLLM_REASONING_LEVELS
  export VLLM_MAX_MODEL_LEN VLLM_TENSOR_PARALLEL_SIZE VLLM_QUANTIZATION
  export VLLM_GPU_MEMORY_UTILIZATION VLLM_BASE_URL
  export VLLM_TEMPERATURE VLLM_TOP_P
}

# Match the thread pools to what Slurm actually granted. Left alone, OpenMP and
# BLAS size themselves from the number of cores on the *node* (64+ here), which
# on a shared node means dozens of threads fighting over 8 allocated cores —
# UMAP and NMF get slower, not faster.
set_threads() {
  local n="${SLURM_CPUS_PER_TASK:-${UNSC_THREADS:-4}}"
  export OMP_NUM_THREADS="$n" MKL_NUM_THREADS="$n" OPENBLAS_NUM_THREADS="$n"
  export NUMEXPR_NUM_THREADS="$n" TOKENIZERS_PARALLELISM=false
  echo "==> threads: $n"
}

# Copy a job's outputs to backed-up storage. Jobs write under /workdir, which is
# NOT backed up and purges after 60 days (/scratch after 10). Embeddings and
# topic tables are small next to the corpus, so /home is a safe durable home for
# them. Set UNSC_ARCHIVE=off to disable, or to a path to choose where.
archive_outputs() {
  local src="$1"
  local root="${UNSC_ARCHIVE:-$HOME/unsc-archive}"
  local dest="$root/$(basename "$src")"
  [[ "${UNSC_ARCHIVE:-}" == "off" || "${UNSC_ARCHIVE:-}" == "none" ]] && return 0
  [[ -d "$src" ]] || return 0
  mkdir -p "$dest" 2>/dev/null || { echo "WARN: cannot create archive dir $dest" >&2; return 0; }

  # /home is a 15 GB quota shared with everything else the account does, and it
  # fills. A copy that runs it to zero does not just lose the archive: it breaks
  # the next `rsync`, the next `git`, and the next job to write a log. Check
  # first, and decline loudly rather than filling the disk.
  local need avail
  need="$(du -sk "$src" 2>/dev/null | cut -f1)"
  avail="$(df -Pk "$root" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [[ -n "$need" && -n "$avail" ]] && (( need + 262144 > avail )); then
    echo "WARN: not archiving $(basename "$src") — needs $((need / 1024)) MB, $((avail / 1024)) MB free on $root" >&2
    echo "      results remain at $src (on purgeable storage — fetch them)" >&2
    echo "      free space, or set UNSC_ARCHIVE to somewhere larger, or =off" >&2
    return 0
  fi
  # -rt, not -a: copy contents and mtimes for incremental skips, without trying
  # to preserve owner/group/perms — those fail on NFS and return non-zero even
  # when the data copied fine. Always return 0; a best-effort archive must never
  # fail the job, which runs under `set -e`.
  if command -v rsync >/dev/null 2>&1; then
    rsync -rt "$src"/ "$dest"/ || echo "WARN: archive rsync exit $? (results still on $src)" >&2
  else
    cp -r "$src"/. "$dest"/ || echo "WARN: archive cp failed (results still on $src)" >&2
  fi
  echo "==> archived $src -> $dest"
  return 0
}

# Report the GPU a job actually landed on, into the Slurm log. When an embedding
# run has to be explained months later, "which card, which driver" is the first
# question, and fp16 matrix products are not bit-identical across architectures.
report_gpu() {
  command -v nvidia-smi >/dev/null 2>&1 || { echo "==> no nvidia-smi (CPU node)"; return 0; }
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
}
