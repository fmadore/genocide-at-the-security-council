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

SELECT=()
[[ -n "${UNSC_SAMPLE:-}" ]] && SELECT+=(--sample "$UNSC_SAMPLE")
[[ -n "${UNSC_K:-}"      ]] && SELECT+=(--k "$UNSC_K")
[[ -n "${UNSC_SEEDS:-}"  ]] && SELECT+=(--seeds "$UNSC_SEEDS")
[[ "${UNSC_NO_SWEEP:-}" == "1" ]] && SELECT+=(--no-sweep)

srun python scripts/07_topics.py "${SELECT[@]}"

archive_outputs "$REPO/data/derived/topics"
archive_outputs "$REPO/notes"
echo "==> $(date '+%F %T') | done."
