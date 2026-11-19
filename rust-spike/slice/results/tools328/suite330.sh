#!/bin/bash
# suite330.sh SHA (sa-port-330, pareto1, under a shared lease, detached; job329.sh's phase 1 without the base arm): the
# slice suite by id on the staged tree of SHA, bar.sh suite()'s derandomized hypothesis profile, 3 workers each:
# on (SLICE_WITNESS=1) and off (=0), backends rust and python. Runs under HOME=~/sp19 (pareto1's suite environment).
# The base rows are sa-port-329's (job/suite-base-*, e5db633). End marker: OUT/suites-end.txt, the last line here.
export HOME=/home/tilo/sp19
G=/home/tilo/sa-rust-ids-work/sa-port-330/s1; export OUT=/home/tilo/sa-rust-ids-work/sa-port-330/job-$1
mkdir -p $OUT; echo "start $(date -u +%FT%TZ) new $1 lease $MACHINE_LEASE_ID" > $OUT/start.txt
sha256sum $G/bench-$1/tree/rust-spike/slice/sa_solver.so $G/bench-$1/tree/satassume/witness.py >> $OUT/start.txt
suite() { # suite NAME SHA BACKEND SWITCH
  ( unset SLICE_WITNESS SLICE_WITNESS_CAP SLICE_WITNESS_PLANT SLICE_CONVERT SLICE_TERM_FRAMES
    [ -n "$4" ] && export SLICE_WITNESS=$4
    PYTEST_N="-n 3" bash $G/bench-$2/tree/rust-spike/slice/run_suite.sh $OUT/suite-$1-$3 $3 tests -p hyp_profile --hypothesis-profile=bar > $OUT/suite-$1-$3.out 2>&1 ) &
}
for be in rust python; do suite on $1 $be 1; suite off $1 $be 0; done
wait
echo "SUITES $(date -u +%FT%TZ)" > $OUT/suites-end.txt
