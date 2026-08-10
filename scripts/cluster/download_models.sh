#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Prefetch embedding weights into $HF_HOME. RUN ON THE LOGIN NODE — it needs the
# internet. Compute nodes then run fully offline (HF_HUB_OFFLINE=1 in the submit
# scripts), so a model that was not fetched here fails the job immediately
# rather than hanging on a network call that cannot succeed.
#
#     bash scripts/cluster/download_models.sh              # the default model
#     bash scripts/cluster/download_models.sh qwen3-0.6b qwen3-4b
#     bash scripts/cluster/download_models.sh --all
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

load_python
# The extras environment: huggingface_hub and the registry loader live there.
activate_extras

# IMPORTANT: do NOT set HF_HUB_OFFLINE here — this is the step that needs the network.
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE || true

echo "==> HF cache: $HF_HOME"
mkdir -p "$HF_HOME"

python "$REPO/scripts/lib/download_models.py" "$@"

echo "==> cache now holds $(du -sh "$HF_HOME" 2>/dev/null | cut -f1)"
