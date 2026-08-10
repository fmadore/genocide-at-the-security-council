#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Pull results from the cluster to this machine. RUN THIS LOCALLY — Git Bash on
# Windows, or WSL/macOS/Linux — not on the cluster.
#
#   bash scripts/cluster/fetch_results.sh                 # embeddings + topics + notes
#   bash scripts/cluster/fetch_results.sh --watch 643031  # wait for a job, THEN pull
#   bash scripts/cluster/fetch_results.sh --what lemmas    # or: topics, lexical, embeddings
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)  WATCH_JOB="${2:?--watch needs a Slurm job id}"; shift 2 ;;
    --what)   WHAT="${2:?--what needs one of: all embeddings topics notes}"; shift 2 ;;
    --ssh)    SSH_TARGET="${2:?--ssh needs a target}"; shift 2 ;;
    --remote) REMOTE_REPO="${2:?--remote needs a path}"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
  *)
    echo "unknown --what '$WHAT'" >&2
    echo "  all | embeddings | topics | lemmas | lexical | notes" >&2
    exit 2 ;;
esac

SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_TARGET")

if [[ -n "$WATCH_JOB" ]]; then
  echo ">> waiting for Slurm job $WATCH_JOB ..."
  while "${SSH[@]}" "squeue -j '$WATCH_JOB' -h -o %T 2>/dev/null" | grep -q .; do
    sleep 20
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
for p in "${PATHS[@]}"; do
  [[ -e "$REPO/$p" ]] && du -sh "$REPO/$p"
done
