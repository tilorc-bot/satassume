#!/bin/bash
# stage359.sh NEW BASE (sa-port-359, orion, under setsid; tools352/stage352.sh with this step's paths): stage the frozen
# tree of NEW (a git archive of the commit, never the worktree) and build its crate.
#  pareto1  ~/sa-rust-ids-work/sa-port-359/s1/bench-NEW/tree = the archive; tools352/build352.sh NEW sa-port-359 under a
#           shared lease: the venv .so (copied to orion sa-port-359/so) and the bench .so (left in the bench tree, for
#           S1); bench-BASE/tree = BASE's archive plus the bench .so of b7302f83 that sa-port-354 built
#           (0b6f073f5c5a600b; BASE's crate is source-equal, checked here); common/ = sa-port-350's s1/common
#  pareto0  ~/sp19/sa-rust-ids-work/sa-port-359/s1/bench-NEW/tree = the archive plus the venv .so; bench-BASE/tree =
#           BASE's archive plus the venv .so of b7302f83 (37b7560e245df518); s1/tools = tools328, tools336, tools342,
#           tools352, tools354 and tools359 of the worktree, flat (also on orion, sa-port-359/tools; TOOLS-SHA says
#           which HEAD); s1/plug = sa-port-354's plugins plus cv_seen.py
# End marker: sa-port-359/stage-NEW.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-356/wt; S=sa-port-359; X=~/sa-rust-ids-work/$S; NEW=$1; BASE=$2
R1=/home/tilo/sa-rust-ids-work/$S; R0=/home/tilo/sp19/sa-rust-ids-work/$S; SO=~/sa-rust-ids-work/sa-port-354/so/sa_solver-b7302f83.so
P=/home/tilo/sa-rust-ids-work/sa-port-354/s1/bench-b7302f83; C=/home/tilo/sa-rust-ids-work/sa-port-350/s1/common
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$NEW.txt; exit; }
git -C $WT diff --quiet b7302f83 $BASE -- rust-spike/slice/solver_rs || fin "crate of $BASE differs from b7302f83"
[ "$(sha256sum $SO | cut -c1-16)" = 37b7560e245df518 ] || fin "the venv .so of b7302f83 is not 37b7560e245df518"
rm -rf $X/tools $X/plug; mkdir -p $X/tools $X/plug $X/so
for d in tools328 tools336 tools342 tools352 tools354 tools359; do cp $WT/rust-spike/slice/results/$d/*.sh $WT/rust-spike/slice/results/$d/*.py $X/tools/ 2>/dev/null; done
{ git -C $WT rev-parse HEAD; git -C $WT status --short rust-spike/slice/results; } > $X/tools/TOOLS-SHA
cp ~/sa-rust-ids-work/sa-port-354/plug/*.py $X/tools/cv_seen.py $X/plug/
ssh pareto1 "set -e; mkdir -p $R1/s1/tools $R1/s1/common; cd $R1/s1; for s in $NEW $BASE; do rm -rf bench-\$s; mkdir -p bench-\$s/tree; echo \$s > bench-\$s/SHA; done; [ -e common/sympy ] || cp -a $C/sympy $C/evalbench $C/data common/" || fin "pareto1 mkdir"
for s in $NEW $BASE; do git -C $WT archive $s | ssh pareto1 "tar -x -C $R1/s1/bench-$s/tree" || fin "pareto1 archive $s"; done
ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $R1/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" || fin "pareto1 base .so"
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --shared --wait 30m -r "$S: convert.py port (issue 323): two cargo builds of $NEW, about 5 minutes" -- bash $R1/s1/tools/build352.sh $NEW $S > $X/build-$NEW.log 2>&1 || fin "build failed"
ssh pareto1 "cat $R1/build-$NEW/so.txt" > $X/so/so-$NEW.txt
ssh pareto1 "cat $R1/so-venv-$NEW/sa_solver.so" > $X/so/sa_solver-$NEW.so
ssh pareto0 "mkdir -p $R0/s1/tools $R0/s1/plug" || fin "pareto0 mkdir"
for s in $NEW $BASE; do
  ssh pareto0 "rm -rf $R0/s1/bench-$s; mkdir -p $R0/s1/bench-$s/tree; echo $s > $R0/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh pareto0 "tar -x -C $R0/s1/bench-$s/tree" || fin "pareto0 archive $s"
done
ssh pareto0 "cat > $R0/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$NEW.so
ssh pareto0 "cat > $R0/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < $SO
tar -c -C $X/tools . | ssh pareto0 "tar -x -C $R0/s1/tools"
tar -c -C $X/plug --exclude __pycache__ . | ssh pareto0 "tar -x -C $R0/s1/plug"
{ ssh pareto0 "sha256sum $R0/s1/bench-*/tree/rust-spike/slice/sa_solver.so"; ssh pareto1 "sha256sum $R1/s1/bench-*/tree/rust-spike/slice/sa_solver.so"; } > $X/staged-$NEW.txt
fin "staged $NEW $BASE"
