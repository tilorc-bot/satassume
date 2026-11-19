#!/bin/bash
# stage340.sh SHA SO_HOST_PATH (sa-port-340, orion): stage a frozen tree of SHA (a git archive of the commit, never the
# worktree) on pareto0 and pareto1 under ~/sp19/sa-rust-ids-work/sa-port-340/tree-SHA, with the x86-64 .so taken from
# SO_HOST_PATH on pareto1 (a build of a source-equal crate; the caller checks the equality), and the tools, flat in tools/.
# End marker: ~/sa-rust-ids-work/sa-port-340/stage-SHA.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-340/wt; X=~/sa-rust-ids-work/sa-port-340; SHA=$1; SO=$2
R=/home/tilo/sp19/sa-rust-ids-work/sa-port-340
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$SHA.txt; exit; }
mkdir -p $X/so
ssh pareto1 "cat $SO" > $X/so/sa_solver-$SHA.so || fin "no .so"
for h in pareto0 pareto1; do
  ssh $h "rm -rf $R/tree-$SHA; mkdir -p $R/tree-$SHA $R/tools" || fin "$h mkdir"
  git -C $WT archive $SHA | ssh $h "tar -x -C $R/tree-$SHA" || fin "$h archive"
  ssh $h "cat > $R/tree-$SHA/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$SHA.so
  tar -c -C $WT/rust-spike/slice/results tools340 tools334 tools328 tools336 | ssh $h "tar -x -C $R/tools --strip-components=1"
  ssh $h "sha256sum $R/tree-$SHA/rust-spike/slice/sa_solver.so"
done > $X/staged-so-$SHA.txt
fin "staged $SHA"
