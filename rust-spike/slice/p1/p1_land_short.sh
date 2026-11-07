#!/bin/bash
# The planner's landing bar on the rebased source: suite on Rust by id; fresh dev and fuzz, answers and state; one planted bug
# through that comparison. Everything else in p1_landing.sh moved to "before any backend PR". Run under a job script that sets
# REAL, S, PY as p1_job.sh does. Each part writes OUT/PART/done; OUT/done is last.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-36/land}; mkdir -p $OUT; date -u >$OUT/start
J=${J:-4}
git -C $S rev-parse HEAD >$OUT/head.txt 2>/dev/null
shards() { # dir wl mode [flags]: live.py --fork in J shards, merged
  d=$1; wl=$2; m=$3; shift 3
  N=$($PY -c "import live; print(len(live.load('$wl')))")
  for i in $(seq 0 $((J-1))); do
    only=$(seq $i $J $((N-1)) | paste -sd,)
    $PY live.py $wl $m $d/$wl-$m.s$i.jsonl --check entry --fork --only $only "$@" >$d/$wl-$m.s$i.tot 2>$d/$wl-$m.s$i.err &
  done
  wait
  $PY $S/p1/merge_shards.py $d/$wl-$m.jsonl $d/$wl-$m.s?.jsonl >>$d/merge.txt
  cat $d/$wl-$m.s?.jsonl.handlers >$d/$wl-$m.jsonl.handlers 2>/dev/null
}
sh $S/build_solver.sh >$OUT/build.log 2>&1 || { echo build failed >$OUT/done; exit 1; }
$PY -c 'import satassume,sa_solver,hashlib; print(satassume.__file__, sa_solver.__file__, hashlib.sha256(open(sa_solver.__file__,"rb").read()).hexdigest())' >$OUT/tree.txt
# Fresh alongside the suite; neither rebuilds.
(
  F=$OUT/fresh; mkdir -p $F
  for wl in dev fuzz; do
    for m in py rust; do shards $F $wl $m; done
    $PY livecmp.py $F/$wl-py.jsonl $F/$wl-rust.jsonl >$F/$wl.cmp 2>&1
  done
  date -u >$F/done
) &
SLICE_SUITE_SHUFFLE=1 PYTEST_N="${PYTEST_N:--n 8}" bash $S/run_suite.sh $OUT/suite-rust rust >$OUT/suite-rust.out 2>&1
date -u >$OUT/suite-rust/done
wait
# One planted bug through that comparison: LRA_MUT 6 and 7 on a mutants build, 0 the same build unmutated, which must read clean
L=$OUT/lramut; mkdir -p $L/so
(cd solver_rs && PYO3_PYTHON=$PY CARGO_TARGET_DIR=$L/target cargo build --release --features mutants) >$L/build.log 2>&1
cp $L/target/release/libsa_solver.so $L/so/sa_solver.so
for k in 0 6 7; do mkdir -p $L/m$k
  LRA_MUT=$k shards $L/m$k dev rust --so $L/so
  $PY livecmp.py $OUT/fresh/dev-py.jsonl $L/m$k/dev-rust.jsonl >$L/m$k/dev.cmp 2>&1
done
date -u >$L/done
date -u >$OUT/done
