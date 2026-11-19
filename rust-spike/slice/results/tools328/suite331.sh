#!/bin/bash
# suite331.sh ROOT NEW BASE (sa-port-331, pareto0 or pareto1, under a shared lease, detached; job329.sh's phase 1): the
# slice suite by id on the staged trees ROOT/s1/bench-SHA/tree, bar.sh suite()'s derandomized hypothesis profile, 3
# workers each, six at once: on = NEW with SLICE_WITNESS=1, off = NEW with SLICE_WITNESS=0, base = BASE with the
# variable unset; backends rust and python. Runs under HOME=~/sp19 (the paretos' suite environment).
# End marker: ROOT/job-NEW/suites-end.txt, the last line here.
export HOME=/home/tilo/sp19
G=$1/s1; export OUT=$1/job-$2
mkdir -p $OUT; echo "start $(date -u +%FT%TZ) host $(hostname) new $2 base $3 lease $MACHINE_LEASE_ID load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/start.txt
sha256sum $G/bench-$2/tree/rust-spike/slice/sa_solver.so $G/bench-$2/tree/satassume/witness.py $G/bench-$3/tree/rust-spike/slice/sa_solver.so >> $OUT/start.txt
suite() { # suite NAME SHA BACKEND SWITCH
  ( unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
    [ -n "$4" ] && export SLICE_WITNESS=$4
    PYTEST_N="-n 3" bash $G/bench-$2/tree/rust-spike/slice/run_suite.sh $OUT/suite-$1-$3 $3 tests -p hyp_profile --hypothesis-profile=bar > $OUT/suite-$1-$3.out 2>&1 ) &
}
for be in rust python; do suite on $2 $be 1; suite off $2 $be 0; suite base $3 $be ""; done
wait
echo "SUITES $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/suites-end.txt
