#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Copy this repository to the cluster. RUN THIS LOCALLY.
#
#   bash scripts/cluster/push_code.sh
#   bash scripts/cluster/push_code.sh --ssh festus --remote ~/genocide-at-the-security-council
#
# Code only. The corpus is not uploaded: it is 900 MB, it is CC0 and
# DOI-addressable, and `python scripts/00_fetch_data.py` rebuilds it on the
# cluster login node faster than this connection would move it.
#
# Files deleted here are deleted there too, but only under scripts/, tests/
# and tools/, so a removed module cannot stay importable on the cluster. Data,
# logs, notes, model runs and .env are outside those and never touched.
#
# `.env` is excluded on purpose. It is where your account-specific paths live,
# and the cluster wants its own copy with cluster paths in it.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_TARGET="${UNSC_SSH:-festus}"
REMOTE_REPO="${UNSC_REMOTE_REPO:-~/genocide-at-the-security-council}"
DRY=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssh)     SSH_TARGET="${2:?--ssh needs a target}"; shift 2 ;;
    --remote)  REMOTE_REPO="${2:?--remote needs a path}"; shift 2 ;;
    --dry-run) DRY=(--dry-run); shift ;;
    -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

# What never travels. `data` is excluded because the corpus is 900 MB, CC0 and
# DOI-addressable — 00_fetch_data.py rebuilds it on the login node faster than
# this connection would move it — and because on the cluster `data` is a symlink
# to /workdir that must not be overwritten by a directory.
# `.impeccable` is design-review tooling: 7 tracked markdown files and ~12 MB of
# git-ignored screenshots. Being git-ignored does not keep a file out of the tar,
# which copies the working tree, so it has to be named here like the rest.
EXCLUDES=(
  .git .env data logs notes node_modules __pycache__
  .venv .pytest_cache .ruff_cache web/.svelte-kit web/build .impeccable
)
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_TARGET")

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
    | "${SSH[@]}" "mkdir -p $REMOTE_REPO && tar xzf - -C $REMOTE_REPO"
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

# Prune what was deleted here. Neither transfer deletes anything, so a module
# removed locally stayed importable on the cluster, and a removed test kept
# running there. The cluster's scripts/, tests/ and tools/ are cut back to the
# files this machine has in them, skipping the names the transfer skips, so
# its own __pycache__ survives. The list of files to keep goes over stdin, and
# nothing is pruned unless it names env.sh, so a list that came out empty
# cannot empty the directories.
CODE_DIRS=(scripts tests tools)
PRUNE=()
for e in "${EXCLUDES[@]}"; do
  [[ "$e" == */* ]] || PRUNE+=(-name "$e" -prune -o)
done
KEEP="$(cd "$REPO" && find "${CODE_DIRS[@]}" "${PRUNE[@]}" -type f -print)"
if ! grep -qx 'scripts/cluster/env.sh' <<<"$KEEP"; then
  echo "ERROR: could not list the local code files; nothing was stamped or pruned." >&2
  exit 1
fi

# Verify rather than assume. A remote extraction that runs out of quota leaves a
# *partial* repository — some files new, some stale, none obviously wrong — and
# the next job then fails somewhere unrelated with a confusing error. Checking a
# handful of files that must exist turns that into an immediate, honest failure.
SENTINELS="scripts/cluster/env.sh scripts/cluster/setup_env.sh requirements.lock requirements-cluster.txt"

# Stamp, prune and verify over one connection: the login nodes ban an address
# after a burst of connections. Quoted, so it is expanded by the cluster's
# shell, with the values below set in front of it.
FINISH="$(cat <<'REMOTE'
cd "$repo" 2>/dev/null || { echo "REMOTE_MISSING: $repo" >&2; exit 3; }
if [ "$dry" != 1 ]; then printf '%s\n' "$commit" > .git-commit; fi
keep=$(mktemp) && here=$(mktemp) || exit 1
trap 'rm -f "$keep" "$here"' EXIT
LC_ALL=C sort > "$keep"
grep -qx 'scripts/cluster/env.sh' "$keep" || { echo "KEEP_LIST_INCOMPLETE" >&2; exit 5; }
# $dirs and $prune are word lists on purpose.
find $dirs $prune -type f -print 2>/dev/null | LC_ALL=C sort > "$here"
LC_ALL=C comm -23 "$here" "$keep" | while IFS= read -r f; do
  if [ "$dry" = 1 ]; then echo "   would remove $f"; else rm -f -- "$f" && echo "   removed $f"; fi
done
[ "$dry" = 1 ] && exit 0
for f in $sentinels; do [ -s "$f" ] || { echo "MISSING: $f" >&2; exit 1; }; done
REMOTE
)"
echo ">> pruning deleted code and verifying"
dry=0
[[ ${#DRY[@]} -gt 0 ]] && dry=1
status=0
"${SSH[@]}" "repo=$REMOTE_REPO commit='$COMMIT' dry=$dry dirs='${CODE_DIRS[*]}' prune='${PRUNE[*]}' sentinels='$SENTINELS'
$FINISH" <<<"$KEEP" || status=$?
if (( status != 0 )); then
  echo "ERROR: the transfer did not arrive intact (remote status $status)." >&2
  echo "       Check the remote quota — a full disk truncates the extraction:" >&2
  echo "         ssh $SSH_TARGET 'df -h ~; du -sh ~/* | sort -rh | head'" >&2
  exit 1
fi

echo ">> done. On the cluster:"
echo "     cd $REMOTE_REPO && bash scripts/cluster/setup_env.sh"
