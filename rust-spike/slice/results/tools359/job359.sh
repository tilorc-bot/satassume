#!/bin/bash
# job359.sh ROOT NEW BASE (sa-port-359, pareto0, under ONE shared lease, detached), under HOME=~/sp19 on the staged
# frozen trees ROOT/s1/bench-SHA/tree (stage359.sh): item 4 of the convert.py port.
#  1. gate359.sh: the kept file, the per-query comparison, the differential and livecmp     -> ROOT/job-NEW/gate, convdiff
#  2. suite359.sh: the slice suite by id, cells rust, py, nat, off (NEW) and base (BASE)      -> ROOT/job-NEW/suite-*
#  3. iv359.sh: the iv history check, SLICE_CONVERT=rust against =py                          -> ROOT/job-NEW/iv
# End marker: ROOT/job-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; export NEW=$2 BASE=$3 G=$ROOT/s1 OUT=$ROOT/job-$2
mkdir -p $OUT
bash $G/tools/gate359.sh > $OUT/gate.out 2>&1
bash $G/tools/suite359.sh > $OUT/suites.out 2>&1
N=16 bash $G/tools/iv359.sh > $OUT/iv.out 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
