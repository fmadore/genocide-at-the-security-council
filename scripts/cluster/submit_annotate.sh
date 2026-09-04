#!/usr/bin/env bash
# Serve, annotate and stop without requiring an attended shell or API key.
#SBATCH --job-name=unsc-annotate
#SBATCH --partition=GPU
#SBATCH --gres=gpu:h100:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=24:00:00
#SBATCH --output=logs/annotate-%j.out
#SBATCH --error=logs/annotate-%j.err

set -euo pipefail
REPO="${UNSC_REPO:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "$REPO/scripts/cluster/env.sh"

export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
configure_annotation_model
set_threads
cd "$REPO"

SERVER_PID=""
stop_server() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap stop_server EXIT INT TERM

echo "==> $(date '+%F %T') | node=$(hostname) | $VLLM_MODEL_ID@$VLLM_MODEL_REVISION"
report_gpu

(
  load_python
  activate_vllm
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
  exec srun "${SERVE[@]}"
) &
SERVER_PID=$!

# Readiness uses the standard library from the locked interpreter and never
# sends corpus text. The loop also notices a server that died during startup.
load_python
activate_annotator
export VLLM_VERSION="$($VLLM_VENV/bin/python -c 'import vllm; print(vllm.__version__)')"
export VLLM_GPU_MODEL="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
export VLLM_GPU_COUNT="$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)"
python - "$VLLM_BASE_URL" "$SERVER_PID" <<'PY'
import os, sys, time, urllib.request

url = sys.argv[1].removesuffix("/v1") + "/health"
pid = int(sys.argv[2])
for _ in range(300):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.status == 200:
                print(f"==> ready: {url}")
                raise SystemExit(0)
    except Exception:
        try:
            os.kill(pid, 0)
        except OSError:
            raise SystemExit("ERROR: vLLM exited before becoming ready")
        time.sleep(2)
raise SystemExit("ERROR: vLLM did not become ready within 10 minutes")
PY

python scripts/probe_reasoning.py \
  --run-id "${UNSC_RUN_ID:?set UNSC_RUN_ID to a new, stable run id}" \
  --model "$VLLM_MODEL_ID" \
  --model-revision "$VLLM_MODEL_REVISION" \
  --reasoning-location "$VLLM_REASONING_LOCATION" \
  --levels "$VLLM_REASONING_LEVELS" \
  --speeches "${UNSC_REASONING_PROBE_SPEECHES:-3}" \
  --temperature "$VLLM_TEMPERATURE" \
  --top-p "$VLLM_TOP_P"

ARGS=(
  --run-id "${UNSC_RUN_ID:?set UNSC_RUN_ID to a new, stable run id}"
  --model "$VLLM_MODEL_ID"
  --reasoning-effort "$VLLM_REASONING_EFFORT"
  --reasoning-location "$VLLM_REASONING_LOCATION"
  --concurrency "${UNSC_ANNOTATION_CONCURRENCY:-4}"
  --temperature "$VLLM_TEMPERATURE"
  --top-p "$VLLM_TOP_P"
)
if [[ -n "${UNSC_LIMIT:-}" ]]; then ARGS+=(--limit "$UNSC_LIMIT"); fi
if [[ "${UNSC_SMOKE:-0}" == 1 ]]; then ARGS+=(--smoke); fi
if [[ "${UNSC_RETRY_FAILURES:-0}" == 1 ]]; then ARGS+=(--retry-failures); fi

python scripts/14_llm_annotate.py "${ARGS[@]}"
echo "==> $(date '+%F %T') | annotation pass ended; stopping server."
