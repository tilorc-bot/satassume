#!/bin/bash
# go344.sh NEW BASE (sa-port-344, orion, under setsid): the two reruns with pc344.py.
#  cx: pareto0, shared lease: cx344.sh on sa-port-343's staged tree of NEW -> sa-port-344/cx/WL.json; marker cx-end.txt
#  pc: pareto1, quiet lease: onlease344.sh -> sa-port-344/s1/timing-pc; marker pc-end.txt, the last line here
NEW=$1; BASE=$2; X=~/sa-rust-ids-work/sa-port-344
P0=/home/tilo/sp19/sa-rust-ids-work; P1=/home/tilo/sa-rust-ids-work
( ssh pareto0 "mkdir -p $P0/sa-port-344/tools" && scp -q $X/tools/pc344.py $X/tools/cx344.sh pareto0:$P0/sa-port-344/tools/ &&
  machine run pareto0 --shared --wait 4h -r "sa-port-344: witness reasons (issue 323): calls of the check per workload, 20 workloads, counts, about 5 minutes" -- bash $P0/sa-port-344/tools/cx344.sh $P0/sa-port-343/s1/bench-$NEW/tree $P0/sa-port-344/cx > $X/cx.log 2>&1
  rc=$?; mkdir -p $X/cx; ssh pareto0 "tar -c -C $P0/sa-port-344 cx" | tar -x -C $X
  echo "END $rc $(date -u +%FT%TZ)" > $X/cx-end.txt ) &
ssh pareto1 "set -e; mkdir -p $P1/sa-port-344/s1/tools; cd $P1/sa-port-344/s1; [ -e common ] || cp -a $P1/sa-port-343/s1/common .; for s in $NEW $BASE; do [ -e bench-\$s ] || cp -a $P1/sa-port-343/s1/bench-\$s .; done" > $X/stage1.log 2>&1 || { echo "END stage-failed $(date -u +%FT%TZ)" > $X/pc-end.txt; wait; exit 1; }
scp -q $X/tools/pc344.py $X/tools/pc344.sh $X/tools/onlease344.sh pareto1:$P1/sa-port-344/s1/tools/
machine run pareto1 --quiet --wait 2h -r "sa-port-344: witness reasons (issue 323): per-call rows of the check on budget and wiring, both trees, 3 passes pinned, about 6 minutes" -- bash $P1/sa-port-344/s1/tools/onlease344.sh $NEW $BASE > $X/lease-pc.log 2>&1
rc=$?
mkdir -p $X/s1; rsync -a pareto1:$P1/sa-port-344/s1/timing-pc pareto1:$P1/sa-port-344/s1/end.txt $X/s1/ 2>> $X/lease-pc.log
wait
echo "END $rc $(date -u +%FT%TZ)" > $X/pc-end.txt
