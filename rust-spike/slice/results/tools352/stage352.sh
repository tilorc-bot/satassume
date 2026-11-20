#!/bin/bash
# stage352.sh NEW BASE (sa-port-352; S=SESSION names the output directories, default sa-port-352; orion, under setsid; tools336/stage336.sh and tools347/stage347.sh): stage the
# frozen tree of NEW (a git archive of the commit, never the worktree) and build its crate.
#  pareto1  ~/sa-rust-ids-work/sa-port-352/s1/bench-NEW/tree = the archive; build352.sh under a shared lease: the venv
#           .so (copied to orion sa-port-352/so) and the bench .so (left in the bench tree, for S1)
#  pareto0  ~/sp19/sa-rust-ids-work/sa-port-352/s1/bench-NEW/tree = the archive plus the venv .so; bench-BASE/tree =
#           BASE's archive plus the venv .so of 29c5a0db that sa-port-340 staged (cad764d46471b1c6; BASE's crate is
#           source-equal, checked here); s1/tools = tools328, tools336, tools352 of the worktree's HEAD, flat (also on
#           orion, sa-port-352/tools); s1/plug = sa-port-336's plugins plus wn_seen.py
# End marker: sa-port-352/stage-NEW.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-350/wt; S=${S:-sa-port-352}; X=~/sa-rust-ids-work/$S; NEW=$1; BASE=$2
R1=/home/tilo/sa-rust-ids-work/$S; R0=/home/tilo/sp19/sa-rust-ids-work/$S; SO=~/sa-rust-ids-work/sa-port-340/so/sa_solver-29c5a0db.so
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage-$NEW.txt; exit; }
git -C $WT diff --quiet 29c5a0db $BASE -- rust-spike/slice/solver_rs || fin "crate of $BASE differs from 29c5a0db"
rm -rf $X/tools $X/plug; mkdir -p $X/tools $X/plug $X/so
for d in tools328 tools336 tools352; do git -C $WT archive HEAD:rust-spike/slice/results/$d | tar -x -C $X/tools; done
git -C $WT rev-parse HEAD > $X/tools/TOOLS-SHA
cp ~/sa-rust-ids-work/sa-port-336/plug/*.py $X/tools/wn_seen.py $X/plug/
ssh pareto1 "set -e; mkdir -p $R1/s1/bench-$NEW/tree $R1/s1/tools; echo $NEW > $R1/s1/bench-$NEW/SHA" || fin "pareto1 mkdir"
git -C $WT archive $NEW | ssh pareto1 "tar -x -C $R1/s1/bench-$NEW/tree" || fin "pareto1 archive"
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --shared --wait 30m -r "$S: native witness check (issue 323): two cargo builds of $NEW, about 5 minutes" -- bash $R1/s1/tools/build352.sh $NEW $S > $X/build-$NEW.log 2>&1 || fin "build failed"
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
ssh pareto0 "sha256sum $R0/s1/bench-*/tree/rust-spike/slice/sa_solver.so $R0/s1/bench-*/tree/satassume/witness.py" > $X/staged-$NEW.txt
fin "staged $NEW $BASE"
