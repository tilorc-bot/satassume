#!/bin/sh
# evalbench/fetch.sh CLONE SHA NAME: snapshot a worker's commit as a
# detached worktree cands/NAME-SHA of this repo (never the worker's clone itself).
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
clone=$1 sha=$2 name=$3
git -C "$here" fetch -q "$clone" "$sha"
full=$(git -C "$here" rev-parse "$sha^{commit}")
short=$(git -C "$here" rev-parse --short=7 "$full")
dest="$here/cands/$name-$short"
[ -d "$dest" ] || git -C "$here" worktree add -q --detach "$dest" "$full"
echo "$dest"
