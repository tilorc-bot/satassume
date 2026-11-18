#!/bin/bash
# job329.sh NEW BASE (sa-port-329, pareto1, under one shared lease, detached): the slice suite by id and the iv history
# check for the witness check. Runs under HOME=~/sp19 (pareto1's suite environment, as ~/sp19/p1_job.sh).
# Phase 1, six suites at once, 3 workers each, bar.sh suite()'s derandomized hypothesis profile: on = NEW with
# SLICE_WITNESS=1, off = NEW with SLICE_WITNESS=0, base = BASE with the variable unset; backends rust and python.
# Phase 2: iv329.sh on NEW. End marker: OUT/end.txt, the last line of this script (OUT = sa-port-329/job on pareto1).
export HOME=/home/tilo/sp19
G=/home/tilo/sa-rust-ids-work/sa-port-329/s1; export OUT=/home/tilo/sa-rust-ids-work/sa-port-329/job
mkdir -p $OUT; echo "start $(date -u +%FT%TZ) new $1 base $2 lease $MACHINE_LEASE_ID" > $OUT/start.txt
suite() { # suite NAME SHA BACKEND SWITCH
  ( unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
    [ -n "$4" ] && export SLICE_WITNESS=$4
    PYTEST_N="-n 3" bash $G/bench-$2/tree/rust-spike/slice/run_suite.sh $OUT/suite-$1-$3 $3 tests -p hyp_profile --hypothesis-profile=bar > $OUT/suite-$1-$3.out 2>&1 ) &
}
for be in rust python; do suite on $1 $be 1; suite off $1 $be 0; suite base $2 $be ""; done
wait
echo "SUITES $(date -u +%FT%TZ)" > $OUT/suites-end.txt
SHA=$1 bash $G/tools/iv329.sh > $OUT/iv.out 2>&1
echo "END $(date -u +%FT%TZ)" > $OUT/end.txt
