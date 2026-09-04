#!/usr/bin/env bash
# Install only the keyless annotation client and isolated vLLM server.
# Run on the login node, where package indexes are reachable.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

load_python
mkdir -p "$(dirname "$VLLM_VENV")" "$LLM_CLIENT_PACKAGES" "$HF_HOME" "$REPO/logs"

echo "==> installing the OpenAI-compatible client overlay at $LLM_CLIENT_PACKAGES"
python3 -m pip install --upgrade --target "$LLM_CLIENT_PACKAGES" \
  -r "$REPO/requirements-llm.txt"

if [[ ! -f "$VLLM_VENV/bin/activate" ]]; then
  echo "==> creating the vLLM environment at $VLLM_VENV"
  python3 -m venv "$VLLM_VENV"
fi
# shellcheck disable=SC1091
source "$VLLM_VENV/bin/activate"
python -m pip install --upgrade pip wheel
echo "==> installing the pinned inference server"
python -m pip install -r "$REPO/requirements-vllm.txt"
python -c "import vllm; print(f'==> vLLM {vllm.__version__}')"
