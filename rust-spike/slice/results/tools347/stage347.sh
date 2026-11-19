#!/bin/bash
# stage347.sh NEW BASE (sa-port-347, orion; tools343/stage343.sh for the gate of the witness bounds, pareto0 only):
# stage the frozen trees of NEW and BASE (git archives of the commits, never the worktree) on pareto0
# ~/sp19/sa-rust-ids-work/sa-port-347/s1/bench-SHA/tree, each with the venv .so of 29c5a0db that sa-port-340 staged
# (cad764d46471b1c6, a pareto1 build; the crate is unchanged since 29c5a0db, checked here); s1/tools = tools328,
# tools336, tools340, tools342, tools343, tools344, tools346 and tools347 of the worktree's HEAD, flat (also on orion,
# sa-port-347/tools); s1/plug = sa-port-336's plugins of the iv and repeat checks.
# End marker: sa-port-347/stage.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-346/wt; X=~/sa-rust-ids-work/sa-port-347; NEW=$1; BASE=$2
R=/home/tilo/sp19/sa-rust-ids-work/sa-port-347; SO=~/sa-rust-ids-work/sa-port-340/so/sa_solver-29c5a0db.so
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage.txt; exit; }
for s in $NEW $BASE; do git -C $WT diff --quiet 29c5a0db $s -- rust-spike/slice/solver_rs || fin "crate of $s differs from 29c5a0db"; done
rm -rf $X/tools; mkdir -p $X/tools
for d in tools328 tools336 tools340 tools342 tools343 tools344 tools346 tools347; do git -C $WT archive HEAD:rust-spike/slice/results/$d | tar -x -C $X/tools; done
git -C $WT rev-parse HEAD > $X/tools/TOOLS-SHA
h=pareto0
ssh $h "mkdir -p $R/s1/tools $R/s1/plug" || fin "$h mkdir"
for s in $NEW $BASE; do
  ssh $h "rm -rf $R/s1/bench-$s; mkdir -p $R/s1/bench-$s/tree; echo $s > $R/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh $h "tar -x -C $R/s1/bench-$s/tree" || fin "$h archive $s"
  ssh $h "cat > $R/s1/bench-$s/tree/rust-spike/slice/sa_solver.so" < $SO
done
tar -c -C $X/tools . | ssh $h "tar -x -C $R/s1/tools"
tar -c -C ~/sa-rust-ids-work/sa-port-336/plug --exclude __pycache__ . | ssh $h "tar -x -C $R/s1/plug"
ssh $h "sha256sum $R/s1/bench-*/tree/rust-spike/slice/sa_solver.so $R/s1/bench-*/tree/satassume/witness.py $R/s1/bench-*/tree/satassume/engine.py" | sed "s/^/$h /" > $X/staged.txt
fin "staged $NEW $BASE"
