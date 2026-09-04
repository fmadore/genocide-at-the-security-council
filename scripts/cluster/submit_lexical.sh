#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Step 05: the lexicometry, over either vocabulary.
#
#   UNSC_VOCABULARY=lemma sbatch scripts/cluster/submit_lexical.sh
#   sbatch scripts/cluster/submit_lexical.sh                      # surface
#
# 05 belongs to the release pipeline, so it runs in the LOCKED environment —
# even in lemma mode, where its extra input was produced by the other one. That
# is the point of the split: a parquet of strings crosses between them, an
# environment does not.
#
# It is here rather than on the login node because the matched-keyness stability
# pass refits the control set twenty times over 167,642 speeches.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-lexical
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/lexical-%j.out
#SBATCH --error=logs/lexical-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

load_python
activate_venv
set_threads

cd "$REPO"
VOCABULARY="${UNSC_VOCABULARY:-surface}"
echo "==> $(date '+%F %T') | node=$(hostname) | vocabulary=$VOCABULARY"

if [[ "$VOCABULARY" == "lemma" && ! -f "$REPO/data/derived/lemmas/lemmas.parquet" ]]; then
  echo "ERROR: data/derived/lemmas/lemmas.parquet is missing." >&2
  echo "       Build the lemma layer first:  sbatch scripts/cluster/submit_lemmas.sh" >&2
  exit 1
fi

SELECT=(--vocabulary "$VOCABULARY")
[[ -n "${UNSC_LEXICAL_LIMIT:-}" ]] && SELECT+=(--limit "$UNSC_LEXICAL_LIMIT")
[[ -n "${UNSC_COUNTRIES:-}"     ]] && SELECT+=(--countries "$UNSC_COUNTRIES")

srun python scripts/05_lexical.py "${SELECT[@]}"

if [[ "$VOCABULARY" == "lemma" ]]; then
  archive_outputs "$REPO/data/derived/lexical_lemma"
else
  archive_outputs "$REPO/data/derived/lexical"
fi
archive_outputs "$REPO/notes"
echo "==> $(date '+%F %T') | done."
