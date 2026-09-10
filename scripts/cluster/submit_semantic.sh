#!/usr/bin/env bash
# CPU projection of validated full-corpus vectors. Submit with
# sbatch --dependency=afterok:EMBED_JOB scripts/cluster/submit_semantic.sh
#SBATCH --job-name=unsc-semantic
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/semantic-%j.out
#SBATCH --error=logs/semantic-%j.err
set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"
load_python
activate_extras
set_threads
cd "$REPO"
srun python -u scripts/21_semantic_map.py --embeddings "data/derived/embeddings/${UNSC_MODEL:-qwen3-0.6b}"
archive_outputs "$REPO/data/derived/semantic"
