#!/bin/bash
# stage336.sh SHA BASE (sa-port-336, orion): stage the frozen tree of SHA (a git archive of the worktree's commit, never
# the worktree) for everything that runs on the paretos, and build its crate.
#  pareto1  ~/sa-rust-ids-work/sa-port-336/s1/bench-SHA: sympy, evalbench and data of sa-port-327's s1/bench-6587181 (S1's
#           environment), tree/ = the archive; build336.sh under a shared lease: the venv .so and the bench .so
#  pareto0  ~/sp19/sa-rust-ids-work/sa-port-336/s1/bench-SHA/tree = the archive plus the venv .so, and bench-BASE/tree =
#           BASE's archive plus sa-port-334's pareto1 build of f4ce4b2 (c20c326f; the crate is source-equal, checked here),
#           the tools (tools328 and tools336) and the plugins of the iv check and the repeat check
# End marker: sa-port-336/stage-SHA.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-336; SHA=$1; BASE=$2
R1=/home/tilo/sa-rust-ids-work/sa-port-336; R0=/home/tilo/sp19/sa-rust-ids-work/sa-port-336; P=/home/tilo/sa-rust-ids-work/sa-port-327/s1/bench-6587181
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$SHA.txt; exit; }
git -C $WT diff --quiet f4ce4b2 $BASE -- rust-spike/slice/solver_rs || fin "base crate differs from f4ce4b2"
rm -rf $X/tools; mkdir -p $X/tools $X/plug $X/so
cp $WT/rust-spike/slice/results/tools328/* $WT/rust-spike/slice/results/tools336/* $X/tools/
cp ~/sa-rust-ids-work/sa-port-324/plug/*.py ~/sa-rust-ids-work/sa-port-318/plug/*.py $X/plug/
ssh pareto1 "set -e; mkdir -p $R1/s1/bench-$SHA/tree $R1/s1/tools; cd $R1/s1/bench-$SHA; [ -e sympy ] || cp -a $P/sympy $P/evalbench $P/data .; echo $SHA > SHA" || fin "pareto1 mkdir"
git -C $WT archive $SHA | ssh pareto1 "tar -x -C $R1/s1/bench-$SHA/tree" || fin "pareto1 archive"
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --shared --wait 30m -r "sa-port-336: witness check (issue 323): two cargo builds of $SHA, about 5 minutes" -- bash $R1/s1/tools/build336.sh $SHA > $X/build-$SHA.log 2>&1 || fin "build failed"
ssh pareto1 "cat $R1/build-$SHA/so.txt" > $X/so/so-$SHA.txt
ssh pareto1 "cat $R1/so-venv-$SHA/sa_solver.so" > $X/so/sa_solver-$SHA.so
for s in $SHA $BASE; do
  ssh pareto0 "mkdir -p $R0/s1/bench-$s/tree $R0/s1/tools $R0/s1/plug; echo $s > $R0/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh pareto0 "tar -x -C $R0/s1/bench-$s/tree"
done
ssh pareto0 "cat > $R0/s1/bench-$SHA/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$SHA.so
ssh pareto0 "cat > $R0/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < ~/sa-rust-ids-work/sa-port-334/p1so/sa_solver.so
tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R0/s1/tools"
tar -c -C $X/plug --exclude __pycache__ . | ssh pareto0 "tar -x -C $R0/s1/plug"
ssh pareto0 "sha256sum $R0/s1/bench-*/tree/rust-spike/slice/sa_solver.so" > $X/staged-so-$SHA.txt
fin "staged $SHA $BASE"
