#!/bin/bash
# goprof350.sh SHA NAME WL... (sa-port-350, orion, under setsid; tools347/gos1347.sh): the profile of item 1. Stages pareto1
# ~/sa-rust-ids-work/sa-port-350/s1: common/ = sympy, evalbench and data of sa-port-347's s1/common (S1's environment),
# bench-SHA/tree = the archive of SHA plus 786410d's bench .so (0982a28074215658; the crate is source-equal, checked
# here), tools = this directory. Then onlease350p.sh under ONE quiet lease, the rows copied back.
# End marker: sa-port-350/go$NAME-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-350/wt; X=~/sa-rust-ids-work/sa-port-350; R1=/home/tilo/sa-rust-ids-work/sa-port-350; s=$1; NAME=$2; shift 2
P=/home/tilo/sa-rust-ids-work/sa-port-336/s1/bench-786410d; C=/home/tilo/sa-rust-ids-work/sa-port-347/s1/common
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/go$NAME-end.txt; exit; }
git -C $WT diff --quiet 786410d $s -- rust-spike/slice/solver_rs || fin "crate of $s differs from 786410d"
mkdir -p $X/s1
ssh pareto1 "set -e; mkdir -p $R1/s1/common $R1/s1/tools; cd $R1/s1; [ -e common/sympy ] || cp -a $C/sympy $C/evalbench $C/data common/; rm -rf bench-$s; mkdir -p bench-$s/tree; echo $s > bench-$s/SHA" || fin "pareto1 common"
git -C $WT archive $s | ssh pareto1 "tar -x -C $R1/s1/bench-$s/tree" || fin "pareto1 archive"
ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $R1/s1/bench-$s/tree/rust-spike/slice/sa_solver.so" || fin "pareto1 .so"
tar -c -C $WT/rust-spike/slice/results/tools350 . | ssh pareto1 "tar -x -C $R1/s1/tools"
machine run pareto1 --quiet --wait 2h -r "sa-port-350: witness check profile (issue 323) on $s, $*, 5 rounds pinned, about 10 minutes" -- bash $R1/s1/tools/onlease350p.sh $s $NAME $* > $X/lease-$NAME.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/$NAME pareto1:$R1/s1/compile.txt pareto1:$R1/s1/$NAME-end.txt $X/s1/ 2>> $X/lease-$NAME.log
echo "END $rc $(date -u +%FT%TZ)" > $X/go$NAME-end.txt
