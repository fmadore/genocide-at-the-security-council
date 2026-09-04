#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Step 06: encode all 167,642 speeches on one GPU.
#
#   sbatch scripts/cluster/submit_embed.sh
#   UNSC_MODEL=qwen3-4b sbatch scripts/cluster/submit_embed.sh
#
# Submit FROM THE REPOSITORY ROOT so $SLURM_SUBMIT_DIR points at it.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-embed
#SBATCH --partition=GPU
#SBATCH --gres=gpu:h100:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/embed-%j.out
#SBATCH --error=logs/embed-%j.err

# VERIFY the partition and gres before submitting — they change:
#   sinfo -o "%20P %10G %12N %10l %6D %t"
# `GPU` (uppercase) carries the H100s; `normal` and `edu` carry L40/L40S, which
# are ample for the 0.6B default. There is no lowercase `gpu` partition.
# The whole corpus takes roughly 25 minutes on one H100 with qwen3-0.6b, so the
# 4-hour request is headroom for a larger model, not an estimate.

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

# Compute nodes have no internet; weights were prefetched by download_models.sh.
# Failing loudly here is the point — a job that downloaded its own weights would
# be a job whose model version depends on when it ran.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

load_python
activate_extras
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname) | model=${UNSC_MODEL:-<registry default>}"
report_gpu

SELECT=()
[[ -n "${UNSC_MODEL:-}" ]] && SELECT+=(--model "$UNSC_MODEL")
[[ -n "${UNSC_LIMIT:-}" ]] && SELECT+=(--limit "$UNSC_LIMIT")
[[ -n "${UNSC_STORAGE_DTYPE:-}" ]] && SELECT+=(--storage-dtype "$UNSC_STORAGE_DTYPE")

srun python scripts/06_embed.py "${SELECT[@]}"

# /workdir is not backed up and purges after 60 days. The vectors are 218 MB and
# take 25 GPU-minutes to rebuild; the note and manifest are what makes them
# interpretable. Copy all of it somewhere durable.
archive_outputs "$REPO/data/derived/embeddings"
archive_outputs "$REPO/notes"
echo "==> $(date '+%F %T') | done."
