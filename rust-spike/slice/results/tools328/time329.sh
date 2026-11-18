#!/bin/sh
# time329.sh (sa-port-329, from time328.sh): inside bench-container, one pinned CPU, /work = pareto1
# ~/sa-rust-ids-work/sa-port-329/s1 read-only, /results writable. The check's own time call by call (cnt329.py, only
# `witnesses` wrapped): ROUNDS cold passes per workload and on-arm into cost.jsonl; then one `reasons` pass each into
# why.jsonl (counts only). Not S1 times: no off arm is run here.
R=/results; B=/work/bench-$SHA; T=$B/tree
mkdir -p /tmp/shim && ln -sfn $B/evalbench /tmp/shim/evalbench
env_of() { m=${1%%-*}; w=${1##*-}; cv=py; fr=py; [ $m = rust ] && { cv=rust; fr=rust; }
  cap=32; [ $w = on0 ] && cap=0
  echo "SLICE_WITNESS=1 SLICE_WITNESS_CAP=$cap SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$B/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$B/sympy:/tmp/shim"; }
{ python -VV; cat $B/SHA; sha256sum $T/rust-spike/slice/sa_solver.so $T/satassume/witness.py /work/tools/cnt329.py; } > $R/env.txt 2>&1
for r in $ROUNDS; do for wl in $WLS; do for s in $ARMS; do
  env $(env_of $s) python /work/tools/cnt329.py $wl ${s%%-*} 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('ans'); d.update(arm='$s', round=$r); print(json.dumps(d))" >> $R/cost.jsonl
done; done; echo "round $r $(date -u +%T)" >> $R/progress; done
for wl in $WLS; do for s in $ARMS; do
  env $(env_of $s) python /work/tools/cnt329.py $wl ${s%%-*} reasons 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per'); d.update(arm='$s'); print(json.dumps(d))" >> $R/why.jsonl
done; done
echo "DONE $(date -u +%T)" >> $R/progress
