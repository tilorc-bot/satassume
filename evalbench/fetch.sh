#!/bin/sh
# evalbench/fetch.sh CLONE SHA NAME: snapshot a worker's commit as a
# detached worktree cands/NAME-SHA of this repo (never the worker's clone itself).
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
clone=$1 sha=$2 name=$3
full=$(git -C "$clone" rev-parse --verify "$sha^{commit}")   # workers send short shas; fetch needs the full one
git -C "$here" fetch -q "$clone" "$full"
short=$(git -C "$here" rev-parse --short=7 "$full")
dest="$here/cands/$name-$short"
[ -d "$dest" ] || git -C "$here" worktree add -q --detach "$dest" "$full"
echo "$dest"
