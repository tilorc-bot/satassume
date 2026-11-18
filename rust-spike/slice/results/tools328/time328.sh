#!/bin/sh
# time328.sh (sa-port-328, from sa-port-317's time317.sh): inside bench-container, one pinned CPU, /work = pareto1
# ~/sa-rust-ids-work/sa-port-328/s1 read-only, /results writable. Unprofiled timed rounds, each run a cold process
# (qt195.py, kind time); the arms alternate inside one invocation and the order rotates each round.
# Arms: MODE-WITNESS, MODE py (the package alone) or rust (the slice with SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust, "both
# Rust switches on"); WITNESS off, on32 (SLICE_WITNESS=1, cap 32) or on0 (SLICE_WITNESS=1 SLICE_WITNESS_CAP=0, no cap).
# After the rounds: one wit328.py pass per workload and on-arm (the check counted and timed; not an S1 time).
R=/results; Q=/work/tools/qt195.py; B=/work/bench-$SHA; T=$B/tree
stamp() { echo "$1 $(date -u +%T)" >> $R/progress; }
mkdir -p /tmp/shim && ln -sfn $B/evalbench /tmp/shim/evalbench
env_of() { # env_of ARM: the environment of an arm
  m=${1%%-*}; w=${1##*-}; cv=py; fr=py; [ $m = rust ] && { cv=rust; fr=rust; }
  sw=0; cap=32; case $w in on32) sw=1;; on0) sw=1; cap=0;; esac
  echo "SLICE_WITNESS=$sw SLICE_WITNESS_CAP=$cap SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$B/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$B/sympy:/tmp/shim"
}
one() { # one ARM WL ROUND
  env $(env_of $1) python $Q $2 ${1%%-*} time 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per',None); d.pop('ans',None)
for k in ('installed','session','term','lra'): d.pop(k,None)
d.update(arm='$1', round=$3); print(json.dumps(d))" >> $R/time.jsonl
}
stamp start
S="$ARMS"
{ python -VV; nproc; echo "ARMS $S ROUNDS $ROUNDS WLS $WLS"; cat $B/SHA; sha256sum $T/rust-spike/slice/sa_solver.so $T/satassume/witness.py $Q; } > $R/env.txt 2>&1
for r in $ROUNDS; do
  for wl in $WLS; do for s in $S; do one $s $wl $r; done; done
  S="${S#* } ${S%% *}"
  stamp "round $r"
done
for wl in $WLS; do for s in $ARMS; do case $s in *-off) continue;; esac
  env $(env_of $s) python /work/tools/wit328.py $wl ${s%%-*} 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.update(arm='$s'); print(json.dumps(d))" >> $R/wit.jsonl
done; done
stamp DONE
