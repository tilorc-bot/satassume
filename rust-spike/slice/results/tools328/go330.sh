#!/bin/bash
# go330.sh SHA (sa-port-330, orion, detached): freeze SHA from the worktree into sa-port-330/frozen/SHA/tree (git archive
# plus the worktree's aarch64 sa_solver.so; the crate must be source-equal to 46750d4, whose build that .so is), then
# pre330.sh and gate330.sh on the frozen copy, output sa-port-330/SHA/. End marker: sa-port-330/SHA/go-end.txt, the last
# line here.
set -u
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-330; SHA=$1; F=$X/frozen/$SHA
git -C $WT diff --quiet 46750d4 $SHA -- rust-spike/slice/solver_rs || { echo "crate differs from 46750d4" > $X/go-end.txt; exit 2; }
mkdir -p $F/tree && git -C $WT archive $SHA | tar -x -C $F/tree && cp $WT/rust-spike/slice/sa_solver.so $F/tree/rust-spike/slice/ && echo $SHA > $F/SHA
# the tools of this step are committed after the function SHA: a copy of them goes into the frozen tree
cp $X/tools/*330* $F/tree/rust-spike/slice/results/tools328/
chmod -R a-w $F/tree/satassume
mkdir -p $X/$SHA
bash $F/tree/rust-spike/slice/results/tools328/pre330.sh $F/tree $X/$SHA > $X/$SHA/pre.out 2>&1
N=6 bash $F/tree/rust-spike/slice/results/tools328/gate330.sh $F/tree $X/$SHA/gate > $X/$SHA/gate.out 2>&1
echo "END $(date -u +%FT%TZ)" > $X/$SHA/go-end.txt
