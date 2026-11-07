#!/bin/bash
# hash_trace_job.sh: sa-port-94, on pareto1 under a shared lease. Builds sa_solver.so in each tree given (unless BUILD=0),
# then runs hash_trace.py (copied from this branch into the output dir) on dev and fuzz in each of MODES (default rust; py writes
# NAME-WL-py.json), PYTHONHASHSEED from env.sh.
# Usage: hash_trace_job.sh OUT NAME=TREE [NAME=TREE ...]. Writes OUT/NAME-{dev,fuzz}.json, .err, OUT/source.txt and OUT/DONE.
set -u
export REAL=/home/tilo CARGO_HOME=/home/tilo/.cargo RUSTUP_HOME=/home/tilo/.rustup PATH=/home/tilo/.cargo/bin:$PATH HOME=/home/tilo/sp19
O=$1; shift; mkdir -p $O
. $HOME/sa-rust-ids-work/env.sh
export PY W SA_EVAL_DATA PYTHONHASHSEED
cp "$(dirname "$0")/../hash_trace.py" $O/hash_trace.py
for nt in "$@"; do
  n=${nt%%=*}; T=${nt#*=}; S=$T/rust-spike/slice
  echo "+ $n $T $(cd $T && git rev-parse --short HEAD)" | tee -a $O/source.txt
  if [ "${BUILD:-1}" = 1 ]; then
    echo "+ cargo build in $S/solver_rs, target $O/target-$n" | tee -a $O/source.txt
    (cd $S/solver_rs && CARGO_TARGET_DIR=$O/target-$n PYO3_PYTHON=$PY cargo build --release > $O/build-$n.log 2>&1) || { echo "build $n failed" >> $O/source.txt; continue; }
    cp $O/target-$n/release/libsa_solver.so $S/sa_solver.so
  fi
  sha256sum $S/sa_solver.so >> $O/source.txt
  for m in ${MODES:-rust}; do for wl in dev fuzz; do
    o=$O/$n-$wl; [ $m = rust ] || o=$o-$m
    echo "+ PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$S $PY $O/hash_trace.py $wl $m" >> $O/source.txt
    (cd $S && PYTHONPATH=$T:$W/sympy:$W/shim SLICE_DIR=$S timeout 1800 $PY $O/hash_trace.py $wl $m > $o.json 2> $o.err)
    echo "$n $wl $m exit $?" >> $O/source.txt
  done; done
done
date -u > $O/DONE
