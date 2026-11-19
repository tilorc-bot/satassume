#!/bin/sh
# time327.sh (sa-port-327, from sa-port-301's tools280/time301.sh): inside bench-container, one pinned CPU, /work = pareto1
# ~/sa-rust-ids-work/sa-port-327/s1 read-only (bench-SHA trees, each with its own .so), /results writable.
# Unprofiled timed rounds only, each run a cold process, Rust mode; the arms alternate inside one invocation and the
# order rotates each round. Arms from $TREES: SHA, with +rust for SLICE_CONVERT=rust and +frames for SLICE_TERM_FRAMES=rust.
R=/results; Q=/work/tools/qt195.py
stamp() { echo "$1 $(date -u +%T)" >> $R/progress; }
one() { # one ARM WL MODE ROUND
  a=${1%%+*}; cv=py; fr=py; case $1 in *+rust*) cv=rust;; esac; case $1 in *+frames*) fr=rust;; esac
  B=/work/bench-$a; T=$B/tree
  mkdir -p /tmp/shim-$a && ln -sfn $B/evalbench /tmp/shim-$a/evalbench
  SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$B/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$B/sympy:/tmp/shim-$a \
    python $Q $2 $3 time 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per',None); d.pop('ans',None)
for k in ('installed','session','term','lra'): d.pop(k,None)
d.update(sha='$1', round=$4); print(json.dumps(d))" >> $R/time.jsonl
}
stamp start
S="$TREES"
{ python -VV; nproc; echo "TREES $S ROUNDS $ROUNDS WLS $WLS"; for s in $S; do cat /work/bench-${s%%+*}/SHA; sha256sum /work/bench-${s%%+*}/tree/rust-spike/slice/sa_solver.so; done; sha256sum $Q; } > $R/env.txt 2>&1
for r in $ROUNDS; do
  for wl in $WLS; do for s in $S; do one $s $wl rust $r; done; done
  S="${S#* } ${S%% *}"
  stamp "round $r"
done
stamp DONE
