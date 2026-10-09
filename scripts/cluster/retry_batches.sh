#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Resubmit unfinished batches of a batched model-annotation run as a Slurm
# array. Run it on the login node, in the repository on the cluster.
#
#   bash scripts/cluster/retry_batches.sh --model gemma --gpus 2 \
#     --run-id 2026-09-09-gemma4 --plan data/interim/gemma-plan.json \
#     --indices 3,7 --smoke 2026-09-09-gemma4-smoke
#
# Each array task runs submit_annotate.sh for one batch, which resumes that
# batch's own run directory, <run id>-batch-N, and asks again only for the
# speeches it has not finished. Give the same run id, plan, model and card
# count as the first submission: they are part of every batch's identity.
#
# It refuses, before anything is queued: an index outside the plan; a batch
# whose manifest already says complete, because a complete batch is immutable;
# and, with --smoke, a smoke run that is not complete or that served another
# model, card count, tensor-parallel size or context length, since a gate that
# reads only the status passes a smoke of the wrong configuration. A second
# writer on a batch that is still running is stopped by 14's writer lock.
#
# Options, with their environment equivalents and defaults:
#   --model        qwen | gemma | deepseek               UNSC_ANNOTATION_MODEL
#   --run-id       the base run id                       UNSC_RUN_ID
#   --plan         the batch plan the run was made from  UNSC_BATCH_PLAN
#   --indices      array indices, e.g. 3,7 or 0-16       UNSC_RETRY_INDICES
#   --gpus         H100s per task, also the tensor-parallel size (1)  UNSC_GPUS
#   --concurrent   tasks running at once (2)             UNSC_ARRAY_LIMIT
#   --mem-per-gpu  memory per card (128G)                UNSC_MEM_PER_GPU
#   --time         wall time per task (24:00:00)         UNSC_TIME
#   --smoke        the smoke run id to check against     UNSC_SMOKE_RUN_ID
#   --dry-run      check and print the sbatch command, submit nothing
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL="${UNSC_ANNOTATION_MODEL:-}"
RUN_ID="${UNSC_RUN_ID:-}"
PLAN="${UNSC_BATCH_PLAN:-}"
INDICES="${UNSC_RETRY_INDICES:-}"
GPUS="${UNSC_GPUS:-1}"
LIMIT="${UNSC_ARRAY_LIMIT:-2}"
MEM="${UNSC_MEM_PER_GPU:-128G}"
TIME="${UNSC_TIME:-24:00:00}"
SMOKE="${UNSC_SMOKE_RUN_ID:-}"
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)       MODEL="${2:?--model needs a profile}"; shift 2 ;;
    --run-id)      RUN_ID="${2:?--run-id needs a run id}"; shift 2 ;;
    --plan)        PLAN="${2:?--plan needs a path}"; shift 2 ;;
    --indices)     INDICES="${2:?--indices needs array indices}"; shift 2 ;;
    --gpus)        GPUS="${2:?--gpus needs a card count}"; shift 2 ;;
    --concurrent)  LIMIT="${2:?--concurrent needs a number}"; shift 2 ;;
    --mem-per-gpu) MEM="${2:?--mem-per-gpu needs a size}"; shift 2 ;;
    --time)        TIME="${2:?--time needs a wall time}"; shift 2 ;;
    --smoke)       SMOKE="${2:?--smoke needs a run id}"; shift 2 ;;
    --dry-run)     DRY=1; shift ;;
    -h|--help)     sed -n '2,33p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

die() { echo "ERROR: $*" >&2; exit 2; }
ID='^[A-Za-z0-9][A-Za-z0-9._-]*$'
[[ -n "$MODEL" ]] || die "--model is required: qwen, gemma or deepseek"
[[ "$RUN_ID" =~ $ID ]] || die "--run-id is required: the base run id, without -batch-N"
[[ -n "$PLAN" ]] || die "--plan is required"
[[ "$INDICES" =~ ^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$ ]] \
  || die "--indices takes array indices such as 3,7 or 0-16; the limit goes in --concurrent"
[[ "$GPUS" =~ ^[1-9][0-9]*$ ]] || die "--gpus takes a number of cards"
[[ "$LIMIT" =~ ^[1-9][0-9]*$ ]] || die "--concurrent takes a number of tasks"
if [[ -n "$SMOKE" && ! "$SMOKE" =~ $ID ]]; then die "--smoke takes a run id"; fi
# The server shards the model across exactly the cards the task is given.
if [[ -n "${VLLM_TENSOR_PARALLEL_SIZE:-}" && "$VLLM_TENSOR_PARALLEL_SIZE" != "$GPUS" ]]; then
  die "VLLM_TENSOR_PARALLEL_SIZE=$VLLM_TENSOR_PARALLEL_SIZE disagrees with --gpus $GPUS"
fi

cd "$REPO"
[[ -f "$PLAN" ]] || die "no batch plan at $PLAN"

# What every task inherits through sbatch. submit_annotate.sh refuses a plan
# combined with a smoke or a limit, so neither may leak in from this shell.
export UNSC_ANNOTATION_MODEL="$MODEL" UNSC_RUN_ID="$RUN_ID" UNSC_BATCH_PLAN="$PLAN"
export VLLM_TENSOR_PARALLEL_SIZE="$GPUS"
unset UNSC_LIMIT UNSC_SMOKE

source "$REPO/scripts/cluster/env.sh"
load_python
# In a subshell: the profile is resolved here only to be checked against; each
# task resolves it again for itself, and nothing from this check is exported.
(
  configure_annotation_model
  python3 - "$PLAN" "$RUN_ID" "$INDICES" "$SMOKE" "$GPUS" "$VLLM_MODEL_ID" "$VLLM_MAX_MODEL_LEN" <<'PY'
import json
import sys
from pathlib import Path

plan, run_id, spec, smoke, gpus, model, max_len = sys.argv[1:]
count = len(json.loads(Path(plan).read_text(encoding="utf-8"))["batches"])
indices = set()
for part in spec.split(","):
    low, _, high = part.partition("-")
    indices.update(range(int(low), int(high or low) + 1))

problems = []
for index in sorted(indices):
    if index >= count:
        problems.append(f"index {index} is outside the plan, which has batches 0-{count - 1}")
        continue
    manifest = Path(f"model_annotations/genocide/runs/{run_id}-batch-{index}/manifest.json")
    if manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8")).get("status") == "complete":
        problems.append(f"batch {index} is complete, and a complete batch is immutable")

if smoke:
    record = Path(f"data/interim/model_annotation_smoke/{smoke}/manifest.json")
    if not record.is_file():
        problems.append(f"there is no smoke record at {record}")
    else:
        manifest = json.loads(record.read_text(encoding="utf-8"))
        runtime = manifest.get("runtime", {})
        if manifest.get("status") != "complete":
            problems.append(f"smoke {smoke} is {manifest.get('status')}, not complete")
        expected = {
            "model": (runtime.get("served_model"), model),
            "card count": (runtime.get("hardware", {}).get("gpu_count"), int(gpus)),
            "tensor-parallel size": (runtime.get("serving", {}).get("tensor_parallel_size"), int(gpus)),
            "context length": (runtime.get("serving", {}).get("max_model_len"), int(max_len)),
        }
        for label, (seen, wanted) in expected.items():
            if seen != wanted:
                problems.append(f"smoke {smoke} ran with {label} {seen}; this submission uses {wanted}")

if problems:
    sys.exit("ERROR: nothing submitted.\n  " + "\n  ".join(problems))
print(f">> batches {', '.join(map(str, sorted(indices)))} of {count}: checked")
PY
)

SBATCH=(
  sbatch --array="$INDICES%$LIMIT" --partition=GPU --gres="gpu:h100:$GPUS"
  --mem-per-gpu="$MEM" --time="$TIME"
  --output=logs/annotate-%A_%a.out --error=logs/annotate-%A_%a.err
  scripts/cluster/submit_annotate.sh
)
echo ">> UNSC_ANNOTATION_MODEL=$MODEL UNSC_RUN_ID=$RUN_ID UNSC_BATCH_PLAN=$PLAN VLLM_TENSOR_PARALLEL_SIZE=$GPUS"
echo "   ${SBATCH[*]}"
if (( DRY )); then
  echo "   (dry run: nothing submitted)"
  exit 0
fi
mkdir -p logs
"${SBATCH[@]}"
