#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Steps 01-03: build the parquet corpus the GPU steps read.
#
#   python scripts/00_fetch_data.py            # login node — needs the internet
#   sbatch scripts/cluster/submit_corpus.sh    # here
#
# 00 is deliberately not part of this job. Compute nodes have no route to
# Harvard Dataverse, and a corpus build that silently produced an empty download
# would be worse than one that refuses to start.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-corpus
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/corpus-%j.out
#SBATCH --error=logs/corpus-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

load_python
activate_venv
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname)"

if [[ -z "$(ls -A "$REPO/data/raw" 2>/dev/null | grep -v '^\.gitkeep$' || true)" ]]; then
  echo "ERROR: data/raw is empty — run this on the login node first:" >&2
  echo "         python scripts/00_fetch_data.py" >&2
  exit 1
fi

srun python scripts/01_build_parquet.py
srun python scripts/02_normalise.py
srun python scripts/03_lexicon.py

echo "==> $(date '+%F %T') | corpus ready:"
ls -la "$REPO/data/derived"/*.parquet
