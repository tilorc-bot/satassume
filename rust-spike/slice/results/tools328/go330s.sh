#!/bin/bash
# go330s.sh SHA (sa-port-330, orion, detached): stage SHA on pareto1 (sa-port-330/s1/bench-SHA/tree = git archive of SHA
# from the worktree plus sa-port-329's x86-64 sa_solver.so of 5e6e46a: the crate is source-equal, checked here), run
# suite330.sh there under a shared lease, copy the rows back next to sa-port-329's base rows and compare by id
# (cmp329.py). Orion end marker: sa-port-330/gos-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-330; G=$X/s1; P=~/sa-rust-ids-work/sa-port-329; SHA=$1
git -C $WT diff --quiet 5e6e46a $SHA -- rust-spike/slice/solver_rs || { echo "crate differs" > $X/gos-end-$SHA.txt; exit 2; }
ssh pareto1 "set -e; mkdir -p $G/bench-$SHA/tree $G/tools; echo $SHA > $G/bench-$SHA/SHA"
git -C $WT archive $SHA | ssh pareto1 "tar -x -C $G/bench-$SHA/tree"
ssh pareto1 "cp $P/s1/bench-5e6e46a/tree/rust-spike/slice/sa_solver.so $G/bench-$SHA/tree/rust-spike/slice/sa_solver.so"
rsync -a $X/tools/ pareto1:$G/tools/
machine run pareto1 --shared --wait 30m -r "sa-port-330: witness check (issue 323): suite by id on/off on $SHA, about 10 minutes" -- bash $G/tools/suite330.sh $SHA > $X/suite-$SHA.log 2>&1
rc=$?
rsync -a --exclude hyp --exclude '.hypothesis' pareto1:$X/job-$SHA $X/
for be in rust python; do ln -sfn $P/job/suite-base-$be $X/job-$SHA/suite-base-$be; done
. ~/sa-rust-ids-work/env.sh; $PY $X/tools/cmp329.py $X/job-$SHA > $X/job-$SHA/suite-cmp.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos-end-$SHA.txt
