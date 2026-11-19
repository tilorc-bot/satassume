#!/bin/bash
# stage343.sh NEW BASE (sa-port-343, orion; tools342/stage342.sh under sa-port-343 with tools343 added): stage the frozen trees of NEW and BASE (git archives of the commits, never
# the worktree) for the gate. No build: the crate is unchanged since 29c5a0db (checked here), so both trees take the
# venv .so of 29c5a0db that sa-port-340 staged (cad764d46471b1c6, a pareto1 build).
#  orion    ~/sa-rust-ids-work/sa-port-343/tree-SHA                     the archive, no .so (cnt342.py runs in py mode)
#  pareto0, pareto1  ~/sp19/sa-rust-ids-work/sa-port-343/s1/bench-SHA/tree  the archive plus the .so; s1/tools (tools328,
#           tools336, tools340, tools342, flat) and s1/plug (sa-port-336's plugins of the iv and repeat checks)
# End marker: sa-port-343/stage.txt on orion, the last line here.
set -u
WT=~/sa-rust-ids-work/sa-port-340/wt; X=~/sa-rust-ids-work/sa-port-343; NEW=$1; BASE=$2
R=/home/tilo/sp19/sa-rust-ids-work/sa-port-343; SO=~/sa-rust-ids-work/sa-port-340/so/sa_solver-29c5a0db.so
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/stage.txt; exit; }
git -C $WT diff --quiet 29c5a0db $NEW -- rust-spike/slice/solver_rs || fin "crate differs from 29c5a0db"
git -C $WT diff --quiet 29c5a0db $BASE -- rust-spike/slice/solver_rs || fin "base crate differs from 29c5a0db"
rm -rf $X/tools; mkdir -p $X/tools
for d in tools328 tools336 tools340 tools342 tools343; do git -C $WT archive $NEW:rust-spike/slice/results/$d | tar -x -C $X/tools; done
for s in $NEW $BASE; do rm -rf $X/tree-$s; mkdir -p $X/tree-$s; git -C $WT archive $s | tar -x -C $X/tree-$s; done
for h in pareto0 pareto1; do
  ssh $h "mkdir -p $R/s1/tools $R/s1/plug" || fin "$h mkdir"
  for s in $NEW $BASE; do
    ssh $h "rm -rf $R/s1/bench-$s; mkdir -p $R/s1/bench-$s/tree; echo $s > $R/s1/bench-$s/SHA"
    git -C $WT archive $s | ssh $h "tar -x -C $R/s1/bench-$s/tree" || fin "$h archive $s"
    ssh $h "cat > $R/s1/bench-$s/tree/rust-spike/slice/sa_solver.so" < $SO
  done
  tar -c -C $X/tools . | ssh $h "tar -x -C $R/s1/tools"
  tar -c -C ~/sa-rust-ids-work/sa-port-336/plug --exclude __pycache__ . | ssh $h "tar -x -C $R/s1/plug"
  ssh $h "sha256sum $R/s1/bench-*/tree/rust-spike/slice/sa_solver.so $R/s1/bench-*/tree/satassume/witness.py" | sed "s/^/$h /"
done > $X/staged.txt
fin "staged $NEW $BASE"
