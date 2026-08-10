#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Step 10: build the lemma layer.
#
#   sbatch scripts/cluster/submit_lemmas.sh
#   UNSC_SPACY_MODEL=en_core_web_lg sbatch scripts/cluster/submit_lemmas.sh
#
# No GPU. spaCy's small English pipeline is CPU work, and it parallelises over
# processes rather than cores, so the job asks for many CPUs and hands them to
# `nlp.pipe(n_process=...)`.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-lemmas
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/lemmas-%j.out
#SBATCH --error=logs/lemmas-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

load_python
activate_extras
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname)"

# spaCy worker processes, not BLAS threads: set_threads pinned the latter to 1
# per allocated core, and oversubscribing both would leave the workers fighting.
PROCESSES="${UNSC_SPACY_PROCESSES:-${SLURM_CPUS_PER_TASK:-4}}"

SELECT=(--processes "$PROCESSES")
[[ -n "${UNSC_SPACY_MODEL:-}" ]] && SELECT+=(--model "$UNSC_SPACY_MODEL")
[[ -n "${UNSC_LIMIT:-}"       ]] && SELECT+=(--limit "$UNSC_LIMIT")

srun python scripts/10_lemmatise.py "${SELECT[@]}"

archive_outputs "$REPO/data/derived/lemmas"
archive_outputs "$REPO/notes"
echo "==> $(date '+%F %T') | done."
echo "    Re-run the lexicometry over it with:"
echo "      python scripts/05_lexical.py --vocabulary lemma"
