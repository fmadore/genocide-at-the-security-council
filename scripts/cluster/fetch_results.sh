#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Pull results from the cluster to this machine. RUN THIS LOCALLY — Git Bash on
# Windows, or WSL/macOS/Linux — not on the cluster.
#
#   bash scripts/cluster/fetch_results.sh                 # embeddings, topics, lemmas, notes
#   bash scripts/cluster/fetch_results.sh --watch 643031  # wait for a job, THEN pull
#   bash scripts/cluster/fetch_results.sh --what lemmas    # or: topics, lexical, embeddings, notes
#   bash scripts/cluster/fetch_results.sh --what run --run 2026-09-09-gemma4
#
# `--what run` fetches one model-annotation run: its directory under
# model_annotations/genocide/runs/ and its raw responses, probes and smoke
# record under data/interim/, for the run id itself and for every
# `<run id>-batch-N` of a batched run.
#
# The ssh target is an alias you define in your own ~/.ssh/config, so no
# hostname or account appears in this repository:
#
#   Host festus
#       HostName <the cluster login host>
#       User     <your university account>
#       IdentityFile ~/.ssh/<your key>
#
# Override with --ssh or $UNSC_SSH if you call the alias something else.
#
# tar-over-ssh rather than rsync: it is byte-clean, needs nothing installed on
# either end, and handles the accented speaker names in the notes correctly.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_TARGET="${UNSC_SSH:-festus}"
REMOTE_REPO="${UNSC_REMOTE_REPO:-~/genocide-at-the-security-council}"
WHAT="all"
WATCH_JOB=""
RUN_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)  WATCH_JOB="${2:?--watch needs a Slurm job id}"; shift 2 ;;
    --what)   WHAT="${2:?--what needs one of: all embeddings topics lemmas lexical notes run}"; shift 2 ;;
    --run)    RUN_ID="${2:?--run needs a run id}"; shift 2 ;;
    --ssh)    SSH_TARGET="${2:?--ssh needs a target}"; shift 2 ;;
    --remote) REMOTE_REPO="${2:?--remote needs a path}"; shift 2 ;;
    -h|--help)
      sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

case "$WHAT" in
  all)
    PATHS=(
      data/derived/embeddings data/derived/topics
      data/derived/lemmas data/derived/lexical_lemma notes
    ) ;;
  embeddings) PATHS=(data/derived/embeddings notes) ;;
  topics)     PATHS=(data/derived/topics notes) ;;
  lemmas)     PATHS=(data/derived/lemmas notes) ;;
  lexical)    PATHS=(data/derived/lexical_lemma notes) ;;
  notes)      PATHS=(notes) ;;
  run)
    # The id goes into a command the cluster's shell runs, so only the
    # characters run ids are made of are let through.
    if [[ ! "$RUN_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
      echo "--what run needs --run <run id> (letters, digits, dot, dash, underscore)" >&2
      exit 2
    fi
    # The batch patterns are expanded by the cluster's shell, not this one.
    PATHS=()
    for base in model_annotations/genocide/runs data/interim/llm_raw \
                data/interim/model_annotation_probes data/interim/model_annotation_smoke; do
      PATHS+=("$base/$RUN_ID" "$base/$RUN_ID-batch-*")
    done ;;
  *)
    echo "unknown --what '$WHAT'" >&2
    echo "  all | embeddings | topics | lemmas | lexical | notes | run" >&2
    exit 2 ;;
esac

# Keepalives so that a long wait or a large transfer notices a dead link
# rather than hanging on it.
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=60
     -o ServerAliveCountMax=3 "$SSH_TARGET")

if [[ -n "$WATCH_JOB" ]]; then
  if [[ ! "$WATCH_JOB" =~ ^[0-9]+$ ]]; then
    echo "--watch needs a numeric Slurm job id" >&2
    exit 2
  fi
  echo ">> waiting for Slurm job $WATCH_JOB (polled on the cluster, over one connection) ..."
  # The loop runs on the cluster, so the wait costs one connection however
  # long the job takes. Polling from here opened a fresh connection every
  # 20 s, and the login nodes ban an address for about ten minutes after a
  # burst of connections. A dropped link (a laptop asleep, a VPN reconnecting)
  # is retried after five minutes, which is nowhere near a burst; a first
  # attempt that fails at once is a configuration problem and stops here.
  started=$SECONDS
  connected=""
  until "${SSH[@]}" "while squeue -h -j '$WATCH_JOB' -o %T 2>/dev/null | grep -q .; do sleep 60; done"; do
    if [[ -z "$connected" ]] && (( SECONDS - started < 60 )); then
      echo "ERROR: could not reach $SSH_TARGET. Check the ssh alias, the key and the VPN." >&2
      exit 1
    fi
    connected=1
    echo "   connection lost at $(date '+%H:%M'); reconnecting in five minutes" >&2
    sleep 300
  done
  echo ">> job $WATCH_JOB has left the queue."
fi

echo ">> fetching ${PATHS[*]}"
echo "   from $SSH_TARGET:$REMOTE_REPO"
echo "   into $REPO"

# `tar -C` on the remote resolves each path relative to the repository, so the
# archive unpacks into the identical layout here. Missing directories are
# skipped with a warning rather than failing the whole transfer.
"${SSH[@]}" "cd $REMOTE_REPO 2>/dev/null || { echo 'REMOTE_MISSING:$REMOTE_REPO' >&2; exit 3; }; \
             present=; for p in ${PATHS[*]}; do [ -e \"\$p\" ] && present=\"\$present \$p\"; done; \
             [ -n \"\$present\" ] || { echo 'NOTHING_TO_FETCH' >&2; exit 4; }; \
             tar czf - \$present" | tar xzf - -C "$REPO"

echo ">> done."
shopt -s nullglob
for p in "${PATHS[@]}"; do
  # Unquoted on purpose: a batch pattern expands here to what arrived.
  # shellcheck disable=SC2086
  for found in "$REPO"/$p; do
    if [[ -e "$found" ]]; then du -sh "$found"; fi
  done
done
