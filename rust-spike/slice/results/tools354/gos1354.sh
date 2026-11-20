#!/bin/bash
# gos1354.sh NEW BASE (sa-port-354, orion, under setsid; tools347/gos1347.sh): S1 for the native witness check (item 5).
# Expects NEW staged by `S=sa-port-354 tools352/stage352.sh NEW BASE` (pareto1 ~/sa-rust-ids-work/sa-port-354/s1/
# bench-NEW/tree = the archive plus its own bench .so, built there). Adds on pareto1: common/ = sympy, evalbench and
# data of sa-port-350's s1/common (S1's environment), bench-BASE/tree = BASE's archive plus 786410d's bench .so
# (0982a28074215658; BASE's crate is source-equal, checked here), tools354 and qt342.py into s1/tools. Then
# onlease354.sh under ONE quiet lease, the rows copied back and read by med354.py.
# End marker: sa-port-354/gos1-end.txt, the last line here.
WT=~/sa-rust-ids-work/sa-port-350/wt; X=~/sa-rust-ids-work/sa-port-354; R1=/home/tilo/sa-rust-ids-work/sa-port-354; NEW=$1; BASE=$2
P=/home/tilo/sa-rust-ids-work/sa-port-336/s1/bench-786410d; C=/home/tilo/sa-rust-ids-work/sa-port-350/s1/common
T=$WT/rust-spike/slice/results
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/gos1-end.txt; exit; }
git -C $WT diff --quiet 786410d $BASE -- rust-spike/slice/solver_rs || fin "crate of $BASE differs from 786410d"
mkdir -p $X/s1
ssh pareto1 "set -e; [ -s $R1/s1/bench-$NEW/tree/rust-spike/slice/sa_solver.so ]; mkdir -p $R1/s1/common $R1/s1/tools; cd $R1/s1; [ -e common/sympy ] || cp -a $C/sympy $C/evalbench $C/data common/; rm -rf bench-$BASE; mkdir -p bench-$BASE/tree; echo $BASE > bench-$BASE/SHA" || fin "pareto1 common"
git -C $WT archive $BASE | ssh pareto1 "tar -x -C $R1/s1/bench-$BASE/tree" || fin "pareto1 archive"
ssh pareto1 "cp $P/tree/rust-spike/slice/sa_solver.so $R1/s1/bench-$BASE/tree/rust-spike/slice/sa_solver.so" || fin "pareto1 .so"
tar -c -C $T/tools354 . | ssh pareto1 "tar -x -C $R1/s1/tools" || fin "pareto1 tools"
ssh pareto1 "cat > $R1/s1/tools/qt342.py" < $T/tools342/qt342.py || fin "pareto1 qt342"
machine run pareto1 --quiet --wait 2h -r "sa-port-354: native witness check (issue 323): S1 on $NEW against $BASE, dev fuzz budget wiring, 9 arms, 12 rounds pinned, about 30 minutes" -- bash $R1/s1/tools/onlease354.sh $NEW $BASE > $X/lease-s1.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/timing-s1 pareto1:$R1/s1/timing-bw pareto1:$R1/s1/compile.txt pareto1:$R1/s1/end.txt $X/s1/ 2>> $X/lease-s1.log
. ~/sa-rust-ids-work/env.sh
$PY $T/tools354/med354.py $BASE $NEW $X/s1/timing-s1 $X/s1/timing-bw > $X/s1/med.txt 2>&1
echo "END $rc $(date -u +%FT%TZ)" > $X/gos1-end.txt
