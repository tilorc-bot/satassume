#!/bin/sh
# prof350.sh (sa-port-350; in bench-container, one pinned CPU, /work = pareto1 ~/sa-rust-ids-work/sa-port-350/s1
# read-only, /results writable; tools347/time347.sh's environment): the profile of the planner's item 1. Per round and
# workload, cold processes of prof350.py alternating: MODE py and rust (the slice with SLICE_CONVERT=rust
# SLICE_TERM_FRAMES=rust, "both Rust switches on"), each off (SLICE_WITNESS=0, kind plain), plain and phase
# (SLICE_WITNESS=1, cap 32, the tree's work bound). After the rounds one cprof pass per workload and mode.
R=/results; Q=/work/tools/prof350.py; C=/work/common; T=/work/bench-$SHA/tree
mkdir -p /tmp/shim && ln -sfn $C/evalbench /tmp/shim/evalbench
one() { # one WL MODE ARM ROUND
  cv=py; [ $2 = rust ] && cv=rust; sw=1; k=$3; [ $3 = off ] && { sw=0; k=plain; }
  env -u SLICE_WITNESS_WORK -u SLICE_WITNESS_PLANT SLICE_WITNESS=$sw SLICE_WITNESS_CAP=32 SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$cv \
    SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$C/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$C/sympy:/tmp/shim \
    python $Q $1 $2 $k 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.update(arm='$3', round=$4); print(json.dumps(d))" >> $R/prof.jsonl
}
{ python -VV; nproc; echo "SHA $SHA ROUNDS $ROUNDS WLS $WLS"; sha256sum $T/rust-spike/slice/sa_solver.so $T/satassume/witness.py $T/satassume/engine.py $Q; } > $R/env.txt 2>&1
for r in $ROUNDS; do
  for wl in $WLS; do for m in rust py; do for a in off plain phase; do one $wl $m $a $r; done; done; done
  echo "round $r $(date -u +%T)" >> $R/progress
done
for wl in $WLS; do for m in rust py; do one $wl $m cprof 0; done; done
echo "DONE $(date -u +%T)" >> $R/progress
