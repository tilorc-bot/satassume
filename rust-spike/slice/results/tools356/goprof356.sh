#!/bin/bash
# goprof356.sh SHA NAME (sa-port-356, orion, under setsid; tools350/goprof350.sh and tools327/go327.sh): the profile of
# item 1. Stages pareto1 ~/sa-rust-ids-work/sa-port-356/s1/bench-SHA: tree = the archive of SHA plus b7302f83's bench .so
# (0b6f073f5c5a600b, built on pareto1 by sa-port-354; SHA's crate, satassume and slice sources equal b7302f83's, checked
# here), sympy, evalbench and data of sa-port-354's s1/common (S1's environment), tools = this directory, tools342/qt342.py
# and sa-port-327's pysampler.so and decoders. Then onlease356p.sh under ONE quiet lease, the rows copied back, the .so's nm
# table added to sa-port-327's, and ana356.py per workload. End marker: sa-port-356/go$NAME-end.txt, the last line.
WT=~/sa-rust-ids-work/sa-port-356/wt; X=~/sa-rust-ids-work/sa-port-356; R1=/home/tilo/sa-rust-ids-work/sa-port-356; s=$1; NAME=$2
P=/home/tilo/sa-rust-ids-work/sa-port-354/s1/bench-b7302f83; C=/home/tilo/sa-rust-ids-work/sa-port-354/s1/common; G=/home/tilo/sa-rust-ids-work/sa-port-327/s1
T=$WT/rust-spike/slice/results; W=$R1/s1/bench-$s
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/go$NAME-end.txt; exit; }
git -C $WT diff --quiet b7302f83 $s -- rust-spike/slice/solver_rs ':(glob)rust-spike/slice/*.py' satassume || fin "source of $s differs from b7302f83"
mkdir -p $X/s1
ssh pareto1 "set -e; rm -rf $W; mkdir -p $W/tree $W/tools; echo $s > $W/SHA; cp -a $C/sympy $C/evalbench $C/data $W/" || fin "pareto1 common"
git -C $WT archive $s | ssh pareto1 "tar -x -C $W/tree" || fin "pareto1 archive"
ssh pareto1 "set -e; cp $P/tree/rust-spike/slice/sa_solver.so $W/tree/rust-spike/slice/sa_solver.so; cp $G/tools/pysampler.so $W/tools/; nm -n -S $W/tree/rust-spike/slice/sa_solver.so > $R1/s1/sa_solver.so.nm" || fin "pareto1 .so"
{ tar -c -C $T/tools356 .; } | ssh pareto1 "tar -x -C $W/tools" || fin "pareto1 tools"
ssh pareto1 "cat > $W/tools/qt342.py" < $T/tools342/qt342.py || fin "pareto1 qt342"
machine run pareto1 --quiet --wait 2h -r "sa-port-356: whole-pass profile by Python file (issue 323) on $s: dev fuzz budget wiring, 5 timed rounds pinned plus sampler rows, about 20 minutes" -- bash $W/tools/onlease356p.sh $s $NAME > $X/lease-$NAME.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/$NAME pareto1:$R1/s1/$NAME-end.txt pareto1:$R1/s1/sa_solver.so.nm $X/s1/ 2>> $X/lease-$NAME.log
mkdir -p $X/s1/$NAME/run/nm; cp $G/nm/*.nm $X/s1/sa_solver.so.nm $X/s1/$NAME/run/nm/
for wl in dev fuzz budget wiring; do
  GD_NM=$X/s1/$NAME/run/nm python3 $T/tools356/ana356.py $G/tools $X/s1/$NAME/run $wl $X/s1/$NAME/ana-$wl.json > $X/s1/$NAME/ana-$wl.log 2>&1 || rc="$rc ana-$wl"
done
echo "END $rc $(date -u +%FT%TZ)" > $X/go$NAME-end.txt
