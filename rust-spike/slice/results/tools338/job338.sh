#!/bin/bash
# job338.sh ROOT NEW BASE (sa-port-338, pareto1, under ONE shared lease, detached), on the staged frozen trees
# ROOT/s1/bench-SHA/tree (stage338.sh), under HOME=~/sp19:
#  1. tools328/suite331.sh: the slice suite by id, on = NEW with SLICE_WITNESS=1, off = NEW with =0, base = BASE with the
#     variable unset, backends rust and python, six suites at once, 3 workers each      -> ROOT/job-NEW/suite-*
#  2. order338.sh: tests/test_templates.py, tests/test_p4_review.py and tests/test_witness.py of NEW in one process,
#     rust and python, switch off and on, the two once-leaking tests first, last, interleaved, and three shuffles
#     (24 runs)                                                                         -> ROOT/job-NEW/order
# End marker: ROOT/job-NEW/end.txt, the last line here.
export HOME=/home/tilo/sp19
ROOT=$1; NEW=$2; BASE=$3; G=$ROOT/s1; OUT=$ROOT/job-$NEW
mkdir -p $OUT
bash $G/tools/suite331.sh $ROOT $NEW $BASE > $OUT/suites.out 2>&1
for be in rust python; do for sw in 0 1; do for mode in first last interleaved seed:1 seed:2 seed:3; do
  PLUG=$G/plug bash $G/tools/order338.sh $G/bench-$NEW/tree $OUT/order $be $sw $mode
done; done; done > $OUT/order.out 2>&1
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
