#!/bin/bash
# job366.sh ROOT NEW BASE (sa-port-366, pareto1, under ONE shared lease, detached), under HOME=~/sp19 on the staged
# frozen trees ROOT/s1/bench-SHA/tree (stage366.sh): item 5 of the per-term level's removal.
#  1. gate366.sh: the kept file, BASE against NEW per query under both walkers, live rows, the differential
#                                                                                     -> ROOT/job-NEW/gate, convdiff
#  2. suite366.sh: the slice suite by id, cells rust, py and off on NEW and on BASE          -> ROOT/job-NEW/suite-*
#  3. tools359/iv359.sh: the iv history check on NEW, SLICE_CONVERT=rust against =py         -> ROOT/job-NEW/iv
# End marker: ROOT/job-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; export NEW=$2 BASE=$3 G=$ROOT/s1 OUT=$ROOT/job-$2
mkdir -p $OUT
bash $G/tools/gate366.sh > $OUT/gate.out 2>&1
bash $G/tools/suite366.sh > $OUT/suites.out 2>&1
N=16 bash $G/tools/iv359.sh > $OUT/iv.out 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
