#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Prove the GPU path works before spending a real reservation on it.
#
#   sbatch scripts/cluster/smoke.sh
#
# Runs on the 90-minute `dev` partition and encodes a few hundred speeches into
# data/derived/embeddings_smoke/ — 06_embed.py diverts its output whenever
# --limit is set, so a smoke test can never overwrite a real artefact.
# ---------------------------------------------------------------------------
#SBATCH --job-name=unsc-smoke
#SBATCH --partition=dev
#SBATCH --gres=gpu:l40:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=00:45:00
#SBATCH --output=logs/smoke-%j.out
#SBATCH --error=logs/smoke-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"

load_python
activate_extras
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname)"
report_gpu

echo
echo "==> torch sees:"
python - <<'PY'
import torch
print(f"   torch {torch.__version__}, CUDA {torch.version.cuda}, available={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   device: {torch.cuda.get_device_name(0)} (capability {'.'.join(map(str, torch.cuda.get_device_capability(0)))})")
    x = torch.randn(2048, 2048, device="cuda", dtype=torch.bfloat16)
    print(f"   matmul check: {float((x @ x).float().abs().mean()):.3f}")
PY

echo
echo "==> encoding a sample"
srun python scripts/06_embed.py --limit "${UNSC_LIMIT:-256}"

echo
echo "==> $(date '+%F %T') | smoke test passed. Real run:"
echo "      sbatch scripts/cluster/submit_embed.sh"
