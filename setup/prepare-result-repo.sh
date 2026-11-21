#!/usr/bin/env bash
# Prepare a fresh, empty result repository with one git worktree per seat.
#
#   bash prepare-result-repo.sh /home/<you>/buildathon/band-work/result
#
# Creates:
#   <repo>            integration checkout on branch main (Gatekeeper's identity)
#   <repo>-wt/<seat>  one worktree + branch per seat that writes (lead, builder-a, builder-b, prover)
# Each worktree commits under its own seat identity, so git history shows who wrote what.
# Writes no files into the repository: the only commit is an empty root commit.
set -euo pipefail

REPO="${1:?usage: prepare-result-repo.sh /absolute/path/to/result-repo}"
case "$REPO" in /*) ;; *) echo "path must be absolute: $REPO" >&2; exit 1 ;; esac
WT="${REPO}-wt"

if [ -e "$REPO/.git" ] || [ -e "$WT" ]; then
  echo "refusing: $REPO is already a repository or $WT exists; use a fresh path" >&2
  exit 1
fi

mkdir -p "$REPO" "$WT"
git -C "$REPO" init -q -b main
git -C "$REPO" config extensions.worktreeConfig true
git -C "$REPO" -c user.name="Factory setup" -c user.email="setup@factory.invalid" \
  commit -q --allow-empty -m "Initialize empty result repository"

# Integration checkout: only the Gatekeeper merges here.
git -C "$REPO" config --worktree user.name "Gatekeeper"
git -C "$REPO" config --worktree user.email "gatekeeper@factory.invalid"

add_seat() {  # $1 = branch/handle, $2 = display name
  git -C "$REPO" worktree add -q -b "$1" "$WT/$1" main
  git -C "$WT/$1" config --worktree user.name "$2"
  git -C "$WT/$1" config --worktree user.email "$1@factory.invalid"
}
add_seat lead      "Lead"
add_seat builder-a "Builder A"
add_seat builder-b "Builder B"
add_seat prover    "Prover"

echo "Result repository ready:"
echo "  integration (main, Gatekeeper): $REPO"
for s in lead builder-a builder-b prover; do
  printf '  %-10s %s  (identity: %s)\n' "$s" "$WT/$s" "$(git -C "$WT/$s" config user.name)"
done
