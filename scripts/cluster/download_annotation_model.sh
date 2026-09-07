#!/usr/bin/env bash
# Prefetch one pinned annotation checkpoint on a login node with internet.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

load_python
activate_vllm
configure_annotation_model

echo "==> model: $VLLM_MODEL_ID"
echo "==> revision: $VLLM_MODEL_REVISION"
echo "==> hub cache: $HF_HOME/hub"

# No --cache-dir. `HF_HOME` names the whole Hugging Face home and the hub cache
# is `$HF_HOME/hub` beneath it; passing HF_HOME as the cache directory writes the
# repository one level too high, where every reader that resolves the cache from
# HF_HOME fails to find it. Offline on a compute node that surfaces as a
# LocalEntryNotFoundError naming the revision, which is the symptom and not the
# cause. `download_models.sh` sets the variable and passes nothing, and its
# weights land where vLLM looks; this follows it.
hf download "$VLLM_MODEL_ID" --revision "$VLLM_MODEL_REVISION"
hf cache verify "$VLLM_MODEL_ID" --revision "$VLLM_MODEL_REVISION"
