#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Copy this repository to the cluster. RUN THIS LOCALLY.
#
#   bash scripts/cluster/push_code.sh
#   bash scripts/cluster/push_code.sh --ssh festus --remote ~/un-security-council-debates
#
# Code only. The corpus is not uploaded: it is 900 MB, it is CC0 and
# DOI-addressable, and `python scripts/00_fetch_data.py` rebuilds it on the
# cluster login node faster than this connection would move it.
#
# `.env` is excluded on purpose. It is where your account-specific paths live,
# and the cluster wants its own copy with cluster paths in it.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_TARGET="${UNSC_SSH:-festus}"
REMOTE_REPO="${UNSC_REMOTE_REPO:-~/un-security-council-debates}"
DRY=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssh)     SSH_TARGET="${2:?--ssh needs a target}"; shift 2 ;;
    --remote)  REMOTE_REPO="${2:?--remote needs a path}"; shift 2 ;;
    --dry-run) DRY=(--dry-run); shift ;;
    -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

# What never travels. `data` is excluded because the corpus is 900 MB, CC0 and
# DOI-addressable — 00_fetch_data.py rebuilds it on the login node faster than
# this connection would move it — and because on the cluster `data` is a symlink
# to /workdir that must not be overwritten by a directory.
EXCLUDES=(
  .git .env data logs notes node_modules __pycache__
  .venv .pytest_cache .ruff_cache web/.svelte-kit web/build
)

echo ">> $REPO  ->  $SSH_TARGET:$REMOTE_REPO"

if command -v rsync >/dev/null 2>&1; then
  ARGS=()
  for e in "${EXCLUDES[@]}"; do ARGS+=(--exclude "$e"); done
  rsync -av "${DRY[@]}" "${ARGS[@]}" "$REPO"/ "$SSH_TARGET:$REMOTE_REPO"/
else
  # Git Bash on Windows ships without rsync, which is where this is usually run.
  # tar over ssh needs nothing installed on either end and copies the working
  # tree, so uncommitted work reaches the cluster too.
  echo "   (no rsync — using tar over ssh)"
  ARGS=()
  for e in "${EXCLUDES[@]}"; do ARGS+=(--exclude="$e"); done
  if [[ ${#DRY[@]} -gt 0 ]]; then
    tar czf - -C "$REPO" "${ARGS[@]}" . | tar tzf - | head -50
    echo "   (dry run: first 50 entries)"
    exit 0
  fi
  tar czf - -C "$REPO" "${ARGS[@]}" . \
    | ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_TARGET" \
        "mkdir -p $REMOTE_REPO && tar xzf - -C $REMOTE_REPO"
fi

# Stamp the commit. `.git` is excluded from the transfer, so a job on the cluster
# has no repository to ask and every manifest it wrote said "unknown" — against a
# research contract that requires the generating commit. `-dirty` is recorded
# honestly when the working tree carries uncommitted changes: the sha then names
# the neighbourhood of the code that ran, not the code itself.
COMMIT="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
if [[ "$COMMIT" != unknown && -n "$(git -C "$REPO" status --porcelain 2>/dev/null)" ]]; then
  COMMIT="$COMMIT-dirty"
  echo ">> commit $COMMIT (uncommitted changes — commit before a run you intend to cite)"
else
  echo ">> commit $COMMIT"
fi
ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_TARGET" \
  "printf '%s\n' '$COMMIT' > $REMOTE_REPO/.git-commit"

# Verify rather than assume. A remote extraction that runs out of quota leaves a
# *partial* repository — some files new, some stale, none obviously wrong — and
# the next job then fails somewhere unrelated with a confusing error. Checking a
# handful of files that must exist turns that into an immediate, honest failure.
echo ">> verifying"
SENTINELS="scripts/cluster/env.sh scripts/cluster/setup_env.sh requirements.lock requirements-cluster.txt"
if ! ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_TARGET" \
     "cd $REMOTE_REPO 2>/dev/null && for f in $SENTINELS; do [ -s \"\$f\" ] || { echo \"MISSING: \$f\" >&2; exit 1; }; done"; then
  echo "ERROR: the transfer did not arrive intact." >&2
  echo "       Check the remote quota — a full disk truncates the extraction:" >&2
  echo "         ssh $SSH_TARGET 'df -h ~; du -sh ~/* | sort -rh | head'" >&2
  exit 1
fi

echo ">> done. On the cluster:"
echo "     cd $REMOTE_REPO && bash scripts/cluster/setup_env.sh"
