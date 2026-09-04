#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-time environment setup. RUN ON THE LOGIN NODE — it needs the internet.
#
#     bash scripts/cluster/setup_env.sh
#
# Creates THREE isolated environments on /workdir and points the repository's data/
# directory there as well. See scripts/cluster/env.sh for why they are separate.
# ---------------------------------------------------------------------------
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

load_python
echo "==> python: $(command -v python3) ($(python3 --version 2>&1))"

mkdir -p "$(dirname "$VENV")" "$HF_HOME" "$DATA_STORE" "$REPO/logs"

# --- 1. The locked environment: the release pipeline ------------------------
# requirements.lock and nothing else, so steps 00-05, 08 and 09 are built by
# exactly the environment CI validates.
if [[ ! -f "$VENV/bin/activate" ]]; then
  echo "==> creating the locked environment at $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip wheel
echo "==> installing the pinned pipeline (requirements.lock, hashed)"
python -m pip install --require-hashes -r "$REPO/requirements.lock"
python -c "import pandas, pyarrow, numpy; print(f'    pandas {pandas.__version__}  pyarrow {pyarrow.__version__}  numpy {numpy.__version__}')"
deactivate

# The annotation client overlays the locked interpreter without modifying its
# site-packages. vLLM is deliberately not installed here.
mkdir -p "$LLM_CLIENT_PACKAGES"
python3 -m pip install --upgrade --target "$LLM_CLIENT_PACKAGES" \
  -r "$REPO/requirements-llm.txt"

# --- 2. The extras environment: the optional steps --------------------------
# requirements.txt (ranges, not the lock) plus the cluster extras, resolved
# freely. It must be free: umap-learn needs numba, and numba does not yet support
# the numpy version the lock pins. Resolving that here rather than in the locked
# environment is the whole point of the split — the optional steps never get to
# move the pipeline that produces the published figures.
if [[ ! -f "$EXTRAS_VENV/bin/activate" ]]; then
  echo "==> creating the extras environment at $EXTRAS_VENV"
  python3 -m venv "$EXTRAS_VENV"
fi
# shellcheck disable=SC1091
source "$EXTRAS_VENV/bin/activate"
python -m pip install --upgrade pip wheel
echo "==> installing pipeline requirements + cluster extras (several GB)"
python -m pip install -r "$REPO/requirements.txt" -r "$REPO/requirements-cluster.txt"

# Report, rather than enforce, how the two environments differ. A difference is
# expected and is not an error — but it must be visible, because it is the
# reason a manifest from step 06 will not name the same numpy as one from 01.
echo
echo "==> how the extras environment differs from the lock"
python - "$REPO/requirements.lock" <<'PY'
import re, sys
from importlib.metadata import PackageNotFoundError, version

locked = {}
for line in open(sys.argv[1], encoding="utf-8"):
    match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", line)
    if match:
        locked[match.group(1).lower().replace("_", "-")] = match.group(2)

rows = []
for package in ("numpy", "pandas", "pyarrow", "pyyaml"):
    want = locked.get(package)
    if not want:
        continue
    try:
        got = version(package)
    except PackageNotFoundError:
        continue
    rows.append((package, want, got))

for package, want, got in rows:
    mark = "same" if want == got else "DIFFERS"
    print(f"    {package:<8} lock {want:<10} extras {got:<10} {mark}")
print("    (differences are recorded in each run's manifest; see docs/CLUSTER.md)")
PY

echo
echo "==> sanity check"
python -c "import torch; print(f'    torch {torch.__version__}  cuda {torch.version.cuda}  available={torch.cuda.is_available()}')"
python -c "import sentence_transformers as st; print(f'    sentence-transformers {st.__version__}')"
python -c "import umap, sklearn; print(f'    umap {umap.__version__}  scikit-learn {sklearn.__version__}')"
python -c "import spacy; print(f'    spacy {spacy.__version__}')"
deactivate

# --- 3. The vLLM server: its own torch resolver -----------------------------
if [[ ! -f "$VLLM_VENV/bin/activate" ]]; then
  echo "==> creating the vLLM environment at $VLLM_VENV"
  python3 -m venv "$VLLM_VENV"
fi
# shellcheck disable=SC1091
source "$VLLM_VENV/bin/activate"
python -m pip install --upgrade pip wheel
echo "==> installing the pinned inference server"
python -m pip install -r "$REPO/requirements-vllm.txt"
python -c "import vllm; print(f'    vLLM {vllm.__version__}')"
deactivate

# --- 4. data/ -> /workdir ---------------------------------------------------
# lib/paths.py resolves the corpus relative to the repository root, so the code
# stays on /home (backed up) while the 900 MB of parquet it reads lives on
# /workdir (large, purgeable, re-creatable from Dataverse by 00_fetch_data.py).
if [[ -L "$REPO/data" ]]; then
  echo "==> data/ already links to $(readlink "$REPO/data")"
elif [[ -d "$REPO/data" ]] && [[ -n "$(ls -A "$REPO/data" 2>/dev/null | grep -v '^\.gitkeep$' || true)" ]]; then
  echo "WARN: $REPO/data exists and is not empty — leaving it alone." >&2
  echo "      Move it aside and re-run if you want it on $DATA_STORE." >&2
else
  rm -rf "$REPO/data"
  ln -s "$DATA_STORE" "$REPO/data"
  echo "==> data/ -> $DATA_STORE"
fi

cat <<'NEXT'

==> Done. Next:

  1. Build the corpus (00 needs the internet, so it runs here on the login node):
       python scripts/00_fetch_data.py
       sbatch scripts/cluster/submit_corpus.sh          # steps 01-03, CPU

  2. Prefetch the embedding and annotation models (login node — compute nodes run offline):
       bash scripts/cluster/download_models.sh
       UNSC_ANNOTATION_MODEL=qwen bash scripts/cluster/download_annotation_model.sh

  3. Check the annotation path end to end with a bounded H100 run:
       UNSC_LIMIT=12 UNSC_SMOKE=1 sbatch --partition=GPU --gres=gpu:h100:1 --time=02:00:00 scripts/cluster/submit_annotate.sh

  4. Run the optional steps:
       sbatch scripts/cluster/submit_embed.sh           # 06, one GPU
       sbatch scripts/cluster/submit_topics.sh          # 07, CPU
       sbatch scripts/cluster/submit_lemmas.sh          # 10, CPU
NEXT
