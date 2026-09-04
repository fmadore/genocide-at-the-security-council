#!/usr/bin/env bash
# Prefetch one pinned annotation checkpoint on a login node with internet.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

load_python
activate_vllm
configure_annotation_model

echo "==> model: $VLLM_MODEL_ID"
echo "==> revision: $VLLM_MODEL_REVISION"
hf download "$VLLM_MODEL_ID" \
  --revision "$VLLM_MODEL_REVISION" \
  --cache-dir "$HF_HOME"
hf cache verify "$VLLM_MODEL_ID" \
  --revision "$VLLM_MODEL_REVISION" \
  --cache-dir "$HF_HOME"
