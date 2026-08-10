#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Step 07: the topic-model comparison and its evaluation battery.
#
#   sbatch scripts/cluster/submit_topics.sh
#   UNSC_SAMPLE=40000 UNSC_K=40 sbatch scripts/cluster/submit_topics.sh
#
# No GPU. NMF, UMAP and HDBSCAN are CPU work, and asking for a card that would
# sit idle means queueing behind everyone who actually needs one.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-topics
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --output=logs/topics-%j.out
#SBATCH --error=logs/topics-%j.err

# The default run is 12 fits: two models, plus five resampled refits each for the
# stability battery, plus the k sweep. On 20,000 speeches that is a few hours.
# Cut it with --no-sweep or a smaller --seeds while iterating.

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

load_python
activate_extras
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname)"

if [[ ! -f "$REPO/data/derived/embeddings/vectors.npy" ]]; then
  echo "ERROR: data/derived/embeddings/vectors.npy is missing." >&2
  echo "       Run 06 first:  sbatch scripts/cluster/submit_embed.sh" >&2
  exit 1
fi

# Every import the run needs, before it needs them. 07 imports its heavy
# dependencies inside the functions that use them, which keeps the test suite
# free of them and CI cheap — but it also means a missing package surfaces
# wherever it is first used rather than at the start. matplotlib is imported
# last of all, when the figures are drawn, so a stale environment killed a run
# after every model had been fitted and every statistic computed. Adding a
# package to requirements-cluster.txt does not install it; this is the check
# that says so, in a second rather than in eight minutes.
if ! python - <<'PY'
# `import importlib` alone does not bind `importlib.util`; the submodule has to
# be imported by name, or this check fails on every run including the good ones.
import importlib.util
import sys

missing = [m for m in ("sklearn", "umap", "matplotlib") if not importlib.util.find_spec(m)]
if missing:
    print("missing: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
then
  echo "ERROR: the extras environment is missing packages 07 needs (above)." >&2
  echo "       requirements-cluster.txt has changed since it was built. Rebuild it:" >&2
  echo "         bash scripts/cluster/setup_env.sh" >&2
  echo "       or, for one package:  pip install 'matplotlib>=3.11.1,<4'" >&2
  exit 1
fi

SELECT=()
[[ -n "${UNSC_SAMPLE:-}" ]] && SELECT+=(--sample "$UNSC_SAMPLE")
[[ -n "${UNSC_K:-}"      ]] && SELECT+=(--k "$UNSC_K")
[[ -n "${UNSC_SEEDS:-}"  ]] && SELECT+=(--seeds "$UNSC_SEEDS")
[[ "${UNSC_NO_SWEEP:-}" == "1" ]] && SELECT+=(--no-sweep)

srun python scripts/07_topics.py "${SELECT[@]}"

archive_outputs "$REPO/data/derived/topics"
archive_outputs "$REPO/notes"
echo "==> $(date '+%F %T') | done."
