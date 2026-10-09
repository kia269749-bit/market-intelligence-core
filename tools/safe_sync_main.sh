#!/usr/bin/env bash
# Safe fast-forward sync for Termux. Local work is backed up and stashed,
# not discarded or blindly reapplied over upstream changes.
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
  git status --short
  exit 0
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
PATCH="$HOME/market-intelligence-core-pre-sync-$STAMP.patch"
UNTRACKED_BACKUP="$HOME/market-intelligence-core-untracked-$STAMP.tar.gz"
UNTRACKED_LIST="$HOME/market-intelligence-core-untracked-$STAMP.files0"
BACKUP_BRANCH="backup/pre-main-sync-$STAMP"

# Back up tracked edits and all untracked files before moving the branch.
git diff --binary HEAD > "$PATCH"
git ls-files --others --exclude-standard -z > "$UNTRACKED_LIST"
if [[ -s "$UNTRACKED_LIST" ]]; then
  tar -czf "$UNTRACKED_BACKUP" --null -T "$UNTRACKED_LIST"
  echo "BACKUP: untracked files saved to $UNTRACKED_BACKUP"
fi
rm -f "$UNTRACKED_LIST"
git branch "$BACKUP_BRANCH" HEAD
echo "BACKUP: tracked changes saved to $PATCH"
echo "BACKUP: original commit saved as $BACKUP_BRANCH"

if [[ -n "$(git status --porcelain)" ]]; then
  git stash push --include-untracked -m "pre-main-sync-$STAMP"
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "SAFE ABORT: working tree did not become clean after stash. No sync attempted."
    echo "Patch: $PATCH"
    echo "Backup branch: $BACKUP_BRANCH"
    exit 2
  fi
  echo "LOCAL_WORK: saved in git stash and left untouched; it will not be blindly reapplied over upstream changes."
else
  echo "LOCAL_WORK: working tree was clean."
fi

if ! git merge --ff-only origin/main; then
  echo "SAFE ABORT: fast-forward failed. Local work remains in the stash and backup."
  echo "No reset --hard or git clean was used."
  exit 2
fi

if python -m unittest discover -s tests -q; then
  echo "SYNC_OK: main updated and lightweight unit tests passed."
  echo "Local edits/untracked files remain backed up in the stash; no local work was deleted."
  git status --short
  git stash list -1
  exit 0
fi

echo "TEST FAILURE: rolling HEAD back to $BACKUP_BRANCH. The stash and backups remain."
if git reset --merge "$BACKUP_BRANCH"; then
  echo "ROLLBACK_OK: previous commit restored; local work remains in stash."
else
  echo "ROLLBACK NEEDS REVIEW: automatic rollback was refused."
  echo "Do not run reset --hard or git clean."
fi
echo "Tracked diff backup: $PATCH"
echo "Untracked backup (if present): $UNTRACKED_BACKUP"
echo "Backup branch: $BACKUP_BRANCH"
exit 1
