#!/bin/bash
# job352b.sh ROOT NEW BASE (sa-port-352, pareto0, under ONE shared lease, detached), under HOME=~/sp19 on the staged
# frozen trees ROOT/s1/bench-SHA/tree (stage352.sh):
#  1. suite352.sh: the slice suite by id, cells nat, wit, off (NEW) and base (BASE)      -> ROOT/job-NEW/suite-*
#  2. iv352.sh: the iv history check, wit against nat                                    -> ROOT/job-NEW/iv
# End marker: ROOT/job-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; NEW=$2; BASE=$3; export G=$ROOT/s1 OUT=$ROOT/job-$NEW
mkdir -p $OUT
bash $G/tools/suite352.sh $ROOT $NEW $BASE > $OUT/suites.out 2>&1
SHA=$NEW N=16 bash $G/tools/iv352.sh > $OUT/iv.out 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
