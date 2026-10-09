#!/usr/bin/env bash
# Safe fast-forward sync for the user's Termux checkout.
# Never resets, cleans, stashes, or touches running services.
set -Eeuo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: run this from inside the market-intelligence-core Git repository."
  exit 2
}
cd "$ROOT"

BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" != "main" ]]; then
  echo "SAFE ABORT: current branch is '$BRANCH', not 'main'. No files changed."
  exit 2
fi

git fetch origin main || {
  echo "SAFE ABORT: could not fetch origin/main. No files changed."
  exit 2
}

if ! git merge-base --is-ancestor HEAD origin/main; then
  echo "SAFE ABORT: local main has diverged or contains local commits. No files changed."
  exit 2
fi

CHANGED_PATHS="$(git diff --name-only HEAD..origin/main)"
if [[ -z "$CHANGED_PATHS" ]]; then
  echo "SYNC: already at origin/main."
  exit 0
fi

DIRTY_PATHS="$(git status --porcelain | sed -E 's/^...//')"
while IFS= read -r dirty; do
  [[ -z "$dirty" ]] && continue
  while IFS= read -r upstream; do
    [[ -z "$upstream" ]] && continue
    if [[ "$upstream" == "$dirty" || "$upstream" == "$dirty/"* || "$dirty" == "$upstream/"* ]]; then
      echo "SAFE ABORT: local path '$dirty' overlaps upstream change '$upstream'."
      echo "No files changed. Review or back up that path before syncing."
      exit 2
    fi
  done <<< "$CHANGED_PATHS"
done <<< "$DIRTY_PATHS"

STAMP="$(date +%Y%m%d-%H%M%S)"
PATCH="$HOME/market-intelligence-core-pre-sync-$STAMP.patch"
BACKUP_BRANCH="backup/pre-main-sync-$STAMP"

git diff --binary HEAD > "$PATCH"
git branch "$BACKUP_BRANCH" HEAD
echo "BACKUP: tracked local changes saved to $PATCH"
echo "BACKUP: current commit saved as $BACKUP_BRANCH"

if ! git merge --ff-only origin/main; then
  echo "SAFE ABORT: fast-forward failed. No reset/clean was attempted."
  exit 2
fi

if python -m unittest discover -s tests -q; then
  echo "SYNC_OK: main updated and lightweight unit tests passed."
  echo "Local changes and untracked files were preserved."
  git status --short
  exit 0
fi

echo "TEST FAILURE: attempting rollback to $BACKUP_BRANCH while preserving non-overlapping local changes."
if git reset --merge "$BACKUP_BRANCH"; then
  echo "ROLLBACK_OK: HEAD restored. Backup patch remains at $PATCH."
else
  echo "ROLLBACK NEEDS REVIEW: automatic rollback was refused; do not run reset --hard or clean."
  echo "Backup branch: $BACKUP_BRANCH"
  echo "Tracked diff backup: $PATCH"
fi
exit 1
