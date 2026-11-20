#!/bin/bash
# gos1366.sh NEW BASE (sa-port-366, orion, under setsid; tools359/gos1359.sh): S1 for the per-term level's removal
# (item 6). Expects both trees staged by stage366.sh on pareto1 (~/sa-rust-ids-work/sa-port-366/s1/bench-SHA/tree with
# their bench .so, common/). Syncs the tools again, then onlease366.sh under ONE quiet lease, the rows copied back and
# read by med366.py. End marker: sa-port-366/gos1-end.txt, the last line here.
X=~/sa-rust-ids-work/sa-port-366; WT=$X/wt; R1=/home/tilo/sa-rust-ids-work/sa-port-366; NEW=$1; BASE=$2
T=$WT/rust-spike/slice/results
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gos1-end.txt; exit; }
mkdir -p $X/s1
ssh pareto1 "set -e; for s in $NEW $BASE; do [ -s $R1/s1/bench-\$s/tree/rust-spike/slice/sa_solver.so ]; done; [ -e $R1/s1/common/sympy ]" || fin "pareto1 staging"
for f in $T/tools366/time366.sh $T/tools366/onlease366.sh $T/tools359/wn359.py $T/tools342/qt342.py; do ssh pareto1 "cat > $R1/s1/tools/$(basename $f)" < $f || fin "pareto1 tools"; done
machine run pareto1 --quiet --wait 2h -r "sa-port-366: per-term level removal (issue 323): S1 on $NEW against $BASE, dev fuzz budget wiring, 12 arms, 12 rounds pinned, about 50 minutes" -- bash $R1/s1/tools/onlease366.sh $NEW $BASE > $X/lease-s1.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/timing-s1 pareto1:$R1/s1/timing-bw pareto1:$R1/s1/compile.txt pareto1:$R1/s1/end.txt $X/s1/ 2>> $X/lease-s1.log
. ~/sa-rust-ids-work/env.sh
$PY $T/tools366/med366.py $BASE $NEW $X/s1/timing-s1 $X/s1/timing-bw > $X/s1/med.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos1-end.txt
