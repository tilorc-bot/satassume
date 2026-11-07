#!/bin/bash
# Full suite on the final source, Rust then Python, same shuffle seed. Run under p1_job.sh.
# Output under OUT (default ~/sa-rust-ids-work/sa-port-21/suite on the real home); $OUT/done is the end marker.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-21/suite}; mkdir -p $OUT; date -u >$OUT/start
sh $S/build_solver.sh >$OUT/build.log 2>&1 || { echo build failed >$OUT/done; exit 1; }
sha256sum $S/sa_solver.so >$OUT/so.txt
export SLICE_SUITE_SHUFFLE=1 PYTEST_N="${PYTEST_N:--n 8}"
bash $S/run_suite.sh $OUT/rust rust >$OUT/rust.out 2>&1
date -u >$OUT/rust.end
bash $S/run_suite.sh $OUT/python python >$OUT/python.out 2>&1
date -u >$OUT/done
