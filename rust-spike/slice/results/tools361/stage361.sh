#!/bin/bash
# stage361.sh NEW BASE (sa-port-361, orion; tools359/stage359.sh without the builds): the frozen trees on pareto0 for the
# pre-bar checks. NEW's crate is source-equal to 00535462's (checked here), so its venv .so is the one sa-port-359
# staged (0f78ac2962f34b3a), copied to sa-port-361/so under NEW's name; BASE's is b7302f83's (37b7560e245df518).
#  pareto0  ~/sp19/sa-rust-ids-work/sa-port-361/s1/bench-NEW/tree and bench-BASE/tree = git archive of the commit (never
#           the worktree) plus the venv .so; s1/tools = tools360 and tools361 of the worktree, flat.
# End marker: sa-port-361/stage-NEW.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-356/wt; S=sa-port-361; X=~/sa-rust-ids-work/$S; NEW=$1; BASE=$2
R0=/home/tilo/sp19/sa-rust-ids-work/$S; SO=~/sa-rust-ids-work/sa-port-354/so/sa_solver-b7302f83.so; SN=~/sa-rust-ids-work/sa-port-359/so
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$NEW.txt; exit; }
git -C $WT diff --quiet b7302f83 $BASE -- rust-spike/slice/solver_rs || fin "crate of $BASE differs from b7302f83"
git -C $WT diff --quiet 00535462 $NEW -- rust-spike/slice/solver_rs || fin "crate of $NEW differs from 00535462"
[ "$(sha256sum $SO | cut -c1-16)" = 37b7560e245df518 ] || fin "the venv .so of b7302f83 is not 37b7560e245df518"
[ "$(sha256sum $SN/sa_solver-00535462.so | cut -c1-16)" = 0f78ac2962f34b3a ] || fin "the venv .so of 00535462 is not 0f78ac2962f34b3a"
mkdir -p $X/so $X/tools; cp $SN/sa_solver-00535462.so $X/so/sa_solver-$NEW.so
{ echo "crate of $NEW == crate of 00535462 (git diff --quiet); the builds of 00535462 by sa-port-359:"; cat $SN/so-00535462.txt; } > $X/so/so-$NEW.txt
for d in tools360 tools361; do cp $WT/rust-spike/slice/results/$d/*.sh $WT/rust-spike/slice/results/$d/*.py $X/tools/ 2>/dev/null; done
{ git -C $WT rev-parse HEAD; git -C $WT status --short rust-spike/slice/results; } > $X/tools/TOOLS-SHA
ssh pareto0 "mkdir -p $R0/s1/tools" || fin "pareto0 mkdir"
for s in $NEW $BASE; do
  ssh pareto0 "rm -rf $R0/s1/bench-$s; mkdir -p $R0/s1/bench-$s/tree; echo $s > $R0/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh pareto0 "tar -x -C $R0/s1/bench-$s/tree" || fin "pareto0 archive $s"
done
ssh pareto0 "cat > $R0/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$NEW.so
ssh pareto0 "cat > $R0/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < $SO
tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R0/s1/tools"
ssh pareto0 "sha256sum $R0/s1/bench-*/tree/rust-spike/slice/sa_solver.so" > $X/staged-$NEW.txt
fin "staged $NEW $BASE"
