#!/bin/sh
# time342.sh (sa-port-342; tools336/time336.sh with the SHA in the arm, so two trees alternate inside one invocation):
# inside bench-container, one pinned CPU, /work = pareto1 ~/sa-rust-ids-work/sa-port-342/s1 read-only, /results writable.
# Unprofiled timed rounds, each run a cold process (qt342.py, kind time); the arms alternate inside one invocation and
# the order rotates each round.
# Arms: SHA:MODE-WITNESS over the staged tree /work/bench-SHA/tree; MODE py (the package alone) or rust (the slice with
# SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust, "both Rust switches on"); WITNESS off or on32 (SLICE_WITNESS=1, cap 32).
# sympy, evalbench and data are one copy for every arm (/work/common).
# After the rounds, with WIT=1: one wit328.py pass per workload and on-arm (the check counted and timed; not an S1 time).
R=/results; Q=/work/tools/qt342.py; C=/work/common
stamp() { echo "$1 $(date -u +%T)" >> $R/progress; }
mkdir -p /tmp/shim && ln -sfn $C/evalbench /tmp/shim/evalbench
env_of() { # env_of ARM: the environment of an arm
  sha=${1%%:*}; a=${1#*:}; m=${a%%-*}; w=${a##*-}; T=/work/bench-$sha/tree; cv=py; fr=py; [ $m = rust ] && { cv=rust; fr=rust; }
  sw=0; [ $w = on32 ] && sw=1
  echo "SLICE_WITNESS=$sw SLICE_WITNESS_CAP=32 SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$C/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$C/sympy:/tmp/shim"
}
mode_of() { a=${1#*:}; echo ${a%%-*}; }
one() { # one ARM WL ROUND
  env $(env_of $1) python $Q $2 $(mode_of $1) time 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per',None); d.pop('ans',None)
for k in ('installed','session','term','lra'): d.pop(k,None)
d.update(arm='$1', round=$3); print(json.dumps(d))" >> $R/time.jsonl
}
stamp start
S="$ARMS"
{ python -VV; nproc; echo "ARMS $S ROUNDS $ROUNDS WLS $WLS"; cat /work/bench-*/SHA; sha256sum /work/bench-*/tree/rust-spike/slice/sa_solver.so /work/bench-*/tree/satassume/witness.py $Q; } > $R/env.txt 2>&1
for r in $ROUNDS; do
  for wl in $WLS; do for s in $S; do one $s $wl $r; done; done
  S="${S#* } ${S%% *}"
  stamp "round $r"
done
[ "$WIT" = 1 ] && for wl in $WLS; do for s in $ARMS; do case $s in *-off) continue;; esac
  env $(env_of $s) python /work/tools/wit328.py $wl $(mode_of $s) 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per',None); d.pop('ans',None); d.pop('cert_ids',None); d.update(arm='$s'); print(json.dumps(d))" >> $R/wit.jsonl
done; done
stamp DONE
