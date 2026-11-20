#!/bin/bash
# stage366.sh NEW BASE (sa-port-366, orion, under setsid; tools359/stage359.sh with this step's paths): stage the frozen
# tree of NEW (a git archive of the commit, never the worktree) and build its crate; BASE is f5c1f3f4 or a commit whose
# source (satassume, rust-spike/slice/*.py, solver_rs) equals f5c1f3f4's (checked here), so its builds are sa-port-363's.
# Everything is on pareto1 (pareto0 runs sa-port-370's bar): the bench trees under ~/sa-rust-ids-work, the gate's trees
# under ~/sp19/sa-rust-ids-work.
#  pareto1  ~/sa-rust-ids-work/sa-port-366/s1/bench-NEW/tree = the archive; tools352/build352.sh NEW sa-port-366 under a
#           shared lease: the venv .so (copied to orion sa-port-366/so) and the bench .so (left in the bench tree, for
#           S1); bench-BASE/tree = BASE's archive plus the bench .so of f5c1f3f4 that sa-port-363 built (4ae7f5cf1dbbca07); common/ =
#           sa-port-350's s1/common
#  pareto1  ~/sp19/sa-rust-ids-work/sa-port-366/s1/bench-NEW/tree = the archive plus the venv .so; bench-BASE/tree =
#           BASE's archive plus the venv .so of f5c1f3f4 (a653fd4179da9161); s1/tools = tools328, tools336, tools342,
#           tools352, tools354, tools359, tools363 and tools366 of the worktree, flat (also on orion, sa-port-366/tools; TOOLS-SHA
#           says which HEAD); s1/plug = sa-port-354's plugins plus cv_seen.py
# End marker: sa-port-366/stage-NEW.txt on orion, the last line here.
set -u
S=sa-port-366; X=~/sa-rust-ids-work/$S; WT=$X/wt; NEW=$1; BASE=$2
R1=/home/tilo/sa-rust-ids-work/$S; R0=/home/tilo/sp19/sa-rust-ids-work/$S; SO=~/sa-rust-ids-work/sa-port-363/so/sa_solver-f5c1f3f4.so
P=/home/tilo/sa-rust-ids-work/sa-port-363/s1/bench-f5c1f3f4; C=/home/tilo/sa-rust-ids-work/sa-port-350/s1/common
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$NEW.txt; exit; }
git -C $WT diff --quiet f5c1f3f4 $BASE -- satassume rust-spike/slice/*.py rust-spike/slice/solver_rs || fin "source of $BASE differs from f5c1f3f4"
[ "$(sha256sum $SO | cut -c1-16)" = a653fd4179da9161 ] || fin "the venv .so of f5c1f3f4 is not a653fd4179da9161"
rm -rf $X/tools $X/plug; mkdir -p $X/tools $X/plug $X/so
for d in tools328 tools336 tools342 tools352 tools354 tools359 tools363 tools366; do cp $WT/rust-spike/slice/results/$d/*.sh $WT/rust-spike/slice/results/$d/*.py $X/tools/ 2>/dev/null; done
{ git -C $WT rev-parse HEAD; git -C $WT status --short rust-spike/slice/results; } > $X/tools/TOOLS-SHA
cp ~/sa-rust-ids-work/sa-port-354/plug/*.py $X/tools/cv_seen.py $X/plug/
ssh pareto1 "set -e; mkdir -p $R1/s1/tools $R1/s1/common; cd $R1/s1; for s in $NEW $BASE; do rm -rf bench-\$s; mkdir -p bench-\$s/tree; echo \$s > bench-\$s/SHA; done; [ -e common/sympy ] || cp -a $C/sympy $C/evalbench $C/data common/" || fin "pareto1 mkdir"
for s in $NEW $BASE; do git -C $WT archive $s | ssh pareto1 "tar -x -C $R1/s1/bench-$s/tree" || fin "pareto1 archive $s"; done
ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $R1/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" || fin "pareto1 base .so"
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --shared --wait 30m -r "$S: per-term level removal (issue 323): two cargo builds of $NEW, about 5 minutes" -- bash $R1/s1/tools/build352.sh $NEW $S > $X/build-$NEW.log 2>&1 || fin "build failed"
ssh pareto1 "cat $R1/build-$NEW/so.txt" > $X/so/so-$NEW.txt
ssh pareto1 "cat $R1/so-venv-$NEW/sa_solver.so" > $X/so/sa_solver-$NEW.so
ssh pareto1 "mkdir -p $R0/s1/tools $R0/s1/plug" || fin "pareto1 sp19 mkdir"
for s in $NEW $BASE; do
  ssh pareto1 "rm -rf $R0/s1/bench-$s; mkdir -p $R0/s1/bench-$s/tree; echo $s > $R0/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh pareto1 "tar -x -C $R0/s1/bench-$s/tree" || fin "pareto1 sp19 archive $s"
done
ssh pareto1 "cat > $R0/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$NEW.so
ssh pareto1 "cat > $R0/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < $SO
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R0/s1/tools"
tar -c -C $X/plug --exclude __pycache__ . | ssh pareto1 "tar -x -C $R0/s1/plug"
{ ssh pareto1 "sha256sum $R0/s1/bench-*/tree/rust-spike/slice/sa_solver.so"; ssh pareto1 "sha256sum $R1/s1/bench-*/tree/rust-spike/slice/sa_solver.so"; } > $X/staged-$NEW.txt
fin "staged $NEW $BASE"
