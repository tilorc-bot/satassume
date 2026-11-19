#!/bin/bash
# gos1347.sh NEW BASE (sa-port-347, orion, under setsid; tools343/gos1343.sh): S1 for the witness bounds. Stages pareto1
# ~/sa-rust-ids-work/sa-port-347/s1: common/ = sympy, evalbench and data of sa-port-336's s1/bench-786410d (S1's
# environment), bench-SHA/tree = the archive of each SHA plus 786410d's bench .so (0982a28074215658; the crate is
# source-equal, checked here), tools flat (sa-port-347/tools, staged by stage347.sh). Then onlease347.sh under ONE quiet
# lease, the rows copied back and read by med347.py. End marker: sa-port-347/gos1-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-346/wt; X=~/sa-rust-ids-work/sa-port-347; R1=/home/tilo/sa-rust-ids-work/sa-port-347; NEW=$1; BASE=$2
P=/home/tilo/sa-rust-ids-work/sa-port-336/s1/bench-786410d
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gos1-end.txt; exit; }
for s in $NEW $BASE; do git -C $WT diff --quiet 786410d $s -- rust-spike/slice/solver_rs || fin "crate of $s differs from 786410d"; done
mkdir -p $X/s1
ssh pareto1 "set -e; mkdir -p $R1/s1/common $R1/s1/tools; cd $R1/s1; [ -e common/sympy ] || cp -a $P/sympy $P/evalbench $P/data common/" || fin "pareto1 common"
for s in $NEW $BASE; do
  ssh pareto1 "rm -rf $R1/s1/bench-$s; mkdir -p $R1/s1/bench-$s/tree; echo $s > $R1/s1/bench-$s/SHA" || fin "pareto1 mkdir"
  git -C $WT archive $s | ssh pareto1 "tar -x -C $R1/s1/bench-$s/tree" || fin "pareto1 archive"
  ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $R1/s1/bench-$s/tree/rust-spike/slice/sa_solver.so" || fin "pareto1 .so"
done
tar -c -C $X/tools . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --quiet --wait 2h -r "sa-port-347: witness bounds (issue 323): S1 on $NEW against $BASE, dev fuzz budget wiring, 12 arms, 12 rounds pinned, about 35 minutes" -- bash $R1/s1/tools/onlease347.sh $NEW $BASE > $X/lease-s1.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/timing-s1 pareto1:$R1/s1/timing-bw pareto1:$R1/s1/compile.txt pareto1:$R1/s1/end.txt $X/s1/ 2>> $X/lease-s1.log
. ~/sa-rust-ids-work/env.sh
$PY $X/tools/med347.py $BASE $NEW $X/s1/timing-s1 $X/s1/timing-bw > $X/s1/med.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos1-end.txt
