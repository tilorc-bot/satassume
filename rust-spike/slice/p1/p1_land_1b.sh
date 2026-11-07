#!/bin/bash
# Component 1b's landing, run under a p1_job.sh that sets S, T, B, PY: p1_land_short.sh (suite on Rust by id, fresh dev and fuzz,
# LRA_MUT 0, 6, 7), then what the 1b ruling adds: Python's suite for the split, the handler plants on both backends, and the
# constants history on dev and fuzz. OUT/ALL.done is last, written by the job.
export OUT=${OUT:-$B/land}; mkdir -p $OUT
bash $S/p1/p1_land_short.sh
SLICE_SUITE_SHUFFLE=1 PYTEST_N="-n 6" bash $S/run_suite.sh $OUT/suite-python python >$OUT/suite-python.out 2>&1
date -u >$OUT/suite-python/done
for b in rust python; do
  PYTEST_N="-n 4" bash $S/run_suite.sh $OUT/plant-$b $b rust-spike/slice/suite_plant_handlers.py >$OUT/plant-$b.out 2>&1
done
H=$OUT/hist; mkdir -p $H
git -C $T rev-parse HEAD >$H/head.txt; sha256sum $S/sa_solver.so >>$H/head.txt
bash $S/run_history.sh $H 6 >$H/run.out 2>&1; echo $? >$H/run.exit
$PY $S/historycmp.py $H >$H/cmp.txt 2>&1; echo $? >$H/cmp.exit
date -u >$H/done
date -u >$OUT/ALL.done
