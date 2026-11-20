#!/bin/bash
# gos1359.sh NEW BASE (sa-port-359, orion, under setsid; tools354/gos1354.sh): S1 for the convert.py port (item 5).
# Expects both trees staged by stage359.sh on pareto1 (~/sa-rust-ids-work/sa-port-359/s1/bench-SHA/tree with their
# bench .so, common/). Syncs the tools again, then onlease359.sh under ONE quiet lease, the rows copied back and read
# by med359.py. End marker: sa-port-359/gos1-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-356/wt; X=~/sa-rust-ids-work/sa-port-359; R1=/home/tilo/sa-rust-ids-work/sa-port-359; NEW=$1; BASE=$2
T=$WT/rust-spike/slice/results
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gos1-end.txt; exit; }
mkdir -p $X/s1
ssh pareto1 "set -e; for s in $NEW $BASE; do [ -s $R1/s1/bench-\$s/tree/rust-spike/slice/sa_solver.so ]; done; [ -e $R1/s1/common/sympy ]" || fin "pareto1 staging"
for f in $T/tools359/time359.sh $T/tools359/onlease359.sh $T/tools359/wn359.py $T/tools342/qt342.py; do ssh pareto1 "cat > $R1/s1/tools/$(basename $f)" < $f || fin "pareto1 tools"; done
machine run pareto1 --quiet --wait 2h -r "sa-port-359: convert.py port (issue 323): S1 on $NEW against $BASE, dev fuzz budget wiring, 10 arms, 12 rounds pinned, about 40 minutes" -- bash $R1/s1/tools/onlease359.sh $NEW $BASE > $X/lease-s1.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/timing-s1 pareto1:$R1/s1/timing-bw pareto1:$R1/s1/compile.txt pareto1:$R1/s1/end.txt $X/s1/ 2>> $X/lease-s1.log
. ~/sa-rust-ids-work/env.sh
$PY $T/tools359/med359.py $BASE $NEW $X/s1/timing-s1 $X/s1/timing-bw > $X/s1/med.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos1-end.txt
