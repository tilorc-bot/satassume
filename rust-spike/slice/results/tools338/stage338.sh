#!/bin/bash
# stage338.sh NEW BASE (sa-port-338, orion): stage the frozen trees (git archives, never the worktree) on pareto1 under
# ~/sp19/sa-rust-ids-work/sa-port-338/s1: bench-NEW/tree with sa-port-336's pareto1 venv build of 786410d (cad764d4;
# refused unless NEW's guarded source equals 786410d's), bench-BASE/tree with sa-port-334's pareto1 build of f4ce4b2
# (c20c326f; refused unless BASE's crate equals f4ce4b2's), the tools and the order plugin.
# End marker: sa-port-338/stage-NEW.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-328/wt; X=~/sa-rust-ids-work/sa-port-338; NEW=$1; BASE=$2
R=/home/tilo/sp19/sa-rust-ids-work/sa-port-338
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$NEW.txt; cat $X/stage-$NEW.txt; exit; }
[ -z "$(git -C $WT diff --name-only 786410d $NEW -- satassume rust-spike/slice ':(exclude)rust-spike/slice/results')" ] || fin "guarded source differs from 786410d"
git -C $WT diff --quiet f4ce4b2 $BASE -- rust-spike/slice/solver_rs || fin "base crate differs from f4ce4b2"
cp $WT/rust-spike/slice/results/tools328/suite331.sh $WT/rust-spike/slice/results/tools328/cmp329.py $X/tools/
for s in $NEW $BASE; do
  ssh pareto1 "mkdir -p $R/s1/bench-$s/tree $R/s1/tools $R/s1/plug; echo $s > $R/s1/bench-$s/SHA" || fin "mkdir"
  git -C $WT archive $s | ssh pareto1 "tar -x -C $R/s1/bench-$s/tree" || fin "archive $s"
done
ssh pareto1 "cp /home/tilo/sa-rust-ids-work/sa-port-336/so-venv-786410d/sa_solver.so $R/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so" || fin "new so"
ssh pareto1 "cat > $R/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < ~/sa-rust-ids-work/sa-port-334/p1so/sa_solver.so || fin "base so"
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R/s1/tools"
tar -c -C $X/plug --exclude __pycache__ . | ssh pareto1 "tar -x -C $R/s1/plug"
ssh pareto1 "sha256sum $R/s1/bench-*/tree/rust-spike/slice/sa_solver.so" > $X/staged-so-$NEW.txt
fin "staged $NEW $BASE"
