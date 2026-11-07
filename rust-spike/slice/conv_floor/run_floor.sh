#!/bin/sh
# In bench-container, /work = bench dir, read-only. Unprofiled rounds of each arm, rotated, in one invocation.
mkdir -p /tmp/shim && ln -sf /work/evalbench /tmp/shim/evalbench
export SA_EVAL_DATA=/work/data PYTHONHASHSEED=0
R=/results
one() { # round wl arm
  case $3 in
    base) T=/work/base; c=; l=; t=;;
    term-py) T=/work/base; c=; l=; t=py;;
    off) T=/work/tree; c=; l=; t=;;
    cache) T=/work/tree; c=1; l=; t=;;
    lazy) T=/work/tree; c=; l=1; t=;;
    both) T=/work/tree; c=1; l=1; t=;;
  esac
  if [ -n "$t" ]; then export SLICE_TERM=$t; else unset SLICE_TERM; fi
  SLICE_DIR=$T/rust-spike/slice PYTHONPATH=$T:/work/sympy:/tmp/shim SLICE_CONV_CACHE=$c SLICE_CONV_LAZY=$l \
    python /work/tools/qt76.py $2 rust time | sed "s/^{/{\"round\": $1, \"arm\": \"$3\", /" >> $R/floor.jsonl
}
{ python -VV; sha256sum /work/base/rust-spike/slice/sa_solver.so /work/tree/rust-spike/slice/sa_solver.so; cat /work/SHA; nproc; } > $R/env.txt 2>&1
ARMS="base off cache lazy both term-py"
for r in 0 1 2 3 4 5; do
  for wl in dev fuzz; do
    k=0; set --; for a in $ARMS; do set -- "$@" $a; done
    while [ $k -lt $r ]; do x=$1; shift; set -- "$@" $x; k=$((k+1)); done
    for a in "$@"; do one $r $wl $a; done
  done
  echo "round $r $(date -u +%T)" >> $R/progress
done
echo DONE >> $R/progress
