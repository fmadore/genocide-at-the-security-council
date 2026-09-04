#!/usr/bin/env bash
# Serve one pinned annotation model for interactive use through an SSH tunnel.
# Submit from the repository root; override Slurm resources with sbatch flags.
#SBATCH --job-name=unsc-serve
#SBATCH --partition=GPU
#SBATCH --gres=gpu:h100:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=04:00:00
#SBATCH --output=logs/serve-%j.out
#SBATCH --error=logs/serve-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
load_python
activate_vllm
configure_annotation_model
set_threads

cd "$REPO"
echo "==> $(date '+%F %T') | node=$(hostname) | $VLLM_MODEL_ID@$VLLM_MODEL_REVISION"
report_gpu

SERVE=(
  vllm serve "$VLLM_MODEL_ID"
  --revision "$VLLM_MODEL_REVISION"
  --served-model-name "$VLLM_MODEL_ID"
  --host 127.0.0.1
  --port "$VLLM_PORT"
  --max-model-len "$VLLM_MAX_MODEL_LEN"
  --tensor-parallel-size "$VLLM_TENSOR_PARALLEL_SIZE"
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
  --reasoning-parser "$VLLM_REASONING_PARSER"
  --enable-prefix-caching
)
[[ "$VLLM_QUANTIZATION" != none ]] && SERVE+=(--quantization "$VLLM_QUANTIZATION")

echo "==> endpoint: $VLLM_BASE_URL"
exec srun "${SERVE[@]}"
