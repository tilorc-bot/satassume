#!/bin/bash
# goprof367.sh SHA NAME (sa-port-367, orion, under setsid; tools356/goprof356.sh for both paths on rust-slice's head).
# Stages pareto1 ~/sa-rust-ids-work/sa-port-367/s1/bench-SHA: tree = the archive of SHA plus sa-port-363's bench .so of
# 966268c (8b8041d3fe6223c2, sa-port-359's pareto1 build of 00535462; SHA's crate equals 00535462's, checked here),
# sympy, evalbench and data of sa-port-354's s1/common (S1's environment), tools = this directory, tools342/qt342.py,
# tools356/prof356.py and sa-port-327's pysampler.so. Then onlease367p.sh under ONE quiet lease, the rows copied back,
# the .so's nm table added to sa-port-327's, and ana367.py per workload and path. End marker: sa-port-367/go$NAME-end.txt.
WT=~/sa-rust-ids-work/sa-port-367/wt; X=~/sa-rust-ids-work/sa-port-367; R1=/home/tilo/sa-rust-ids-work/sa-port-367; s=$1; NAME=$2
P=/home/tilo/sa-rust-ids-work/sa-port-363/s1/bench-966268c; C=/home/tilo/sa-rust-ids-work/sa-port-354/s1/common; G=/home/tilo/sa-rust-ids-work/sa-port-327/s1
T=$WT/rust-spike/slice/results; W=$R1/s1/bench-$s
fin() { echo "END $1 $(date -u +%FT%TZ)" > $X/go$NAME-end.txt; exit; }
git -C $WT diff --quiet 00535462 $s -- rust-spike/slice/solver_rs || fin "crate of $s differs from 00535462"
mkdir -p $X/s1
ssh pareto1 "set -e; rm -rf $W; mkdir -p $W/tree $W/tools; echo $s > $W/SHA; cp -a $C/sympy $C/evalbench $C/data $W/" || fin "pareto1 common"
git -C $WT archive $s | ssh pareto1 "tar -x -C $W/tree" || fin "pareto1 archive"
ssh pareto1 "set -e; cp $P/tree/rust-spike/slice/sa_solver.so $W/tree/rust-spike/slice/sa_solver.so; cp $G/tools/pysampler.so $W/tools/; nm -n -S $W/tree/rust-spike/slice/sa_solver.so > $R1/s1/sa_solver.so.nm" || fin "pareto1 .so"
{ tar -c -C $T/tools367 .; } | ssh pareto1 "tar -x -C $W/tools" || fin "pareto1 tools"
ssh pareto1 "cat > $W/tools/qt342.py" < $T/tools342/qt342.py || fin "pareto1 qt342"
ssh pareto1 "cat > $W/tools/prof356.py" < $T/tools356/prof356.py || fin "pareto1 prof356"
machine run pareto1 --quiet --wait 2h -r "sa-port-367: whole-pass profile by Python file, default path and rust-nat (issue 323) on $s: dev fuzz budget wiring, 5 timed rounds pinned plus sampler rows, about 35 minutes" -- bash $W/tools/onlease367p.sh $s $NAME > $X/lease-$NAME.log 2>&1
rc=$?
rsync -a pareto1:$R1/s1/$NAME pareto1:$R1/s1/$NAME-end.txt pareto1:$R1/s1/sa_solver.so.nm $X/s1/ 2>> $X/lease-$NAME.log
mkdir -p $X/s1/$NAME/run/nm; cp $G/nm/*.nm $X/s1/sa_solver.so.nm $X/s1/$NAME/run/nm/
for wl in dev fuzz budget wiring; do for m in py rust; do
  GD_NM=$X/s1/$NAME/run/nm python3 $T/tools367/ana367.py $G/tools $X/s1/$NAME/run $wl $X/s1/$NAME/ana-$wl-$m.json $m > $X/s1/$NAME/ana-$wl-$m.log 2>&1 || rc="$rc ana-$wl-$m"
done; done
echo "END $rc $(date -u +%FT%TZ)" > $X/go$NAME-end.txt
