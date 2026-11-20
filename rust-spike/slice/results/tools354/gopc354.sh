#!/bin/bash
# gopc354.sh NEW BASE (sa-port-354, orion, under setsid): item 6's count probe on pareto0 under a shared lease, on the
# trees stage352.sh staged (~/sp19/sa-rust-ids-work/sa-port-354/s1/bench-SHA/tree, each with its venv .so): pc354.sh on
# NEW with the cells d0, w1 and nat, then on BASE with d0 (the default path's counts, for the probe count against
# 21/32). Rows copied back to sa-port-354/pc-NEW and pc-BASE. End marker: sa-port-354/gopc-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-350/wt; X=~/sa-rust-ids-work/sa-port-354; R0=/home/tilo/sp19/sa-rust-ids-work/sa-port-354; NEW=$1; BASE=$2
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gopc-end.txt; exit; }
tar -c -C $WT/rust-spike/slice/results/tools354 . | ssh pareto0 "tar -x -C $R0/s1/tools" || fin "pareto0 tools"
machine run pareto0 --shared --wait 4h -r "sa-port-354: native witness check (issue 323): count probe on $NEW (3 cells) and $BASE (1 cell), 20 workloads, 10 at a time" -- bash -c "bash $R0/s1/tools/pc354.sh $R0/s1/bench-$NEW/tree $R0/pc-$NEW 'd0 w1 nat'; bash $R0/s1/tools/pc354.sh $R0/s1/bench-$BASE/tree $R0/pc-$BASE d0" > $X/lease-pc.log 2>&1
rc=$?
ssh pareto0 "cd $R0 && tar -c --exclude '*.jsonl' --exclude '*.handlers' pc-$NEW pc-$BASE" | tar -x -C $X 2>> $X/lease-pc.log     # pareto0 has no rsync
fin "$rc"
