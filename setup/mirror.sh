#!/usr/bin/env bash
# Mirror a factory's result repository to GitHub while the run is going, from outside the room.
#
#   bash mirror.sh <result-repo> <https-remote-url> [minutes]     # default every 10 minutes
#
# Pushes main with a plain (never forced) push and every seat branch as a forced update, since a
# seat may rewrite its own unmerged branch; GitHub then matches the local repository exactly. It posts nothing to the room and changes nothing in the
# working trees, so it is infrastructure, not human input. Stop it with Ctrl-C or kill.
# On WSL, reuse Windows' GitHub sign-in once (escape the space; do not wrap in quotes; older
# Git for Windows keeps it under mingw64 instead of ucrt64):
#   git config --global credential.helper '/mnt/c/Program\ Files/Git/ucrt64/bin/git-credential-manager.exe'
# Check without writing anything: git push --dry-run <url> main
set -euo pipefail
REPO="${1:?result repo}"; URL="${2:?remote url}"; EVERY="${3:-10}"
git -C "$REPO" remote get-url mirror >/dev/null 2>&1 || git -C "$REPO" remote add mirror "$URL"
while true; do
  branches=$(git -C "$REPO" for-each-ref --format='%(refname:short)' refs/heads/)
  refspecs=$(for b in $branches; do [ "$b" = main ] && echo main || echo "+$b"; done)
  if git -C "$REPO" push --quiet mirror $refspecs 2>/tmp/mirror.err; then
    echo "$(date -u +%FT%TZ) pushed: $(echo $branches | tr '\n' ' ') @ $(git -C "$REPO" rev-parse --short main)"
  else
    echo "$(date -u +%FT%TZ) push failed: $(tail -1 /tmp/mirror.err)"
  fi
  sleep $((EVERY * 60))
done
