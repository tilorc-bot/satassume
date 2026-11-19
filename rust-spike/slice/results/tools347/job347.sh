#!/bin/bash
# job347.sh ROOT NEW BASE (sa-port-347, pareto0, under ONE shared lease, detached; tools342/job342.sh with pre347.sh): on
# the staged frozen trees ROOT/s1/bench-SHA/tree (stage342.sh), under HOME=~/sp19:
#  1. tools328/suite331.sh: the slice suite by id, on = NEW with SLICE_WITNESS=1, off = NEW with =0, base = BASE with the
#     variable unset, backends rust and python, six suites at once, 3 workers each      -> ROOT/job-NEW/suite-*
#  2. pre347.sh: dev and fuzz digests off and on and under each plant, test_witness.py, the repeat check -> job-NEW/pre
#  3. tools336/iv336.sh: the iv history check, switch off and on                         -> job-NEW/iv
# End marker: ROOT/job-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; NEW=$2; BASE=$3; export G=$ROOT/s1 OUT=$ROOT/job-$NEW
mkdir -p $OUT
bash $G/tools/suite331.sh $ROOT $NEW $BASE > $OUT/suites.out 2>&1
bash $G/tools/pre347.sh $G/bench-$NEW/tree $OUT/pre $G/plug > $OUT/pre.out 2>&1
SHA=$NEW N=16 bash $G/tools/iv336.sh > $OUT/iv.out 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
