#!/bin/bash
# gopc361.sh NEW BASE (sa-port-361, orion, under setsid): the count probe (tools354/pc354.sh and pcby354.py, unchanged)
# on pareto1 under a shared lease, on frozen trees staged here (git archive of the commit plus its venv .so, under
# ~/sp19/sa-rust-ids-work/sa-port-361/s1/bench-SHA/tree on pareto1): the cells d0 (every switch unset: the default),
# w1 (SLICE_WITNESS=1 SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust) and nat (w1 plus SLICE_WITNESS_RUST=1) on NEW and on
# BASE, so convert.py's Python calls under SLICE_CONVERT=rust are counted before and after the port, and the default
# path's counts are compared (the probe count against 21 of 32). Rows copied back to sa-port-361/pc-NEW and pc-BASE.
# End marker: sa-port-361/gopc-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-356/wt; X=~/sa-rust-ids-work/sa-port-361; R1=/home/tilo/sp19/sa-rust-ids-work/sa-port-361; NEW=$1; BASE=$2
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gopc-end.txt; exit; }
ssh pareto1 "mkdir -p $R1/s1/tools" || fin "pareto1 mkdir"
for s in $NEW $BASE; do
  ssh pareto1 "rm -rf $R1/s1/bench-$s; mkdir -p $R1/s1/bench-$s/tree; echo $s > $R1/s1/bench-$s/SHA"
  git -C $WT archive $s | ssh pareto1 "tar -x -C $R1/s1/bench-$s/tree" || fin "pareto1 archive $s"
done
ssh pareto1 "cat > $R1/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so" < $X/so/sa_solver-$NEW.so
ssh pareto1 "cat > $R1/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" < ~/sa-rust-ids-work/sa-port-354/so/sa_solver-b7302f83.so
tar -c -C $WT/rust-spike/slice/results/tools354 pc354.sh pcby354.py | ssh pareto1 "tar -x -C $R1/s1/tools" || fin "pareto1 tools"
ssh pareto1 "sha256sum $R1/s1/bench-*/tree/rust-spike/slice/sa_solver.so" > $X/staged-pc-$NEW.txt
machine run pareto1 --shared --wait 4h -r "sa-port-361: convert.py port (issue 323): count probe on $NEW and $BASE, 3 cells each, 20 workloads, 10 at a time" -- bash -c "bash $R1/s1/tools/pc354.sh $R1/s1/bench-$NEW/tree $R1/pc-$NEW 'd0 w1 nat'; bash $R1/s1/tools/pc354.sh $R1/s1/bench-$BASE/tree $R1/pc-$BASE 'd0 w1 nat'" > $X/lease-pc.log 2>&1
rc=$?
ssh pareto1 "cd $R1 && tar -c --exclude '*.jsonl' --exclude '*.handlers' pc-$NEW pc-$BASE" | tar -x -C $X 2>> $X/lease-pc.log
fin "$rc"
