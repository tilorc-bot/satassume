#!/bin/sh
# time354.sh (sa-port-354; tools347/time347.sh with the native arm, for item 5 of the native witness check):
# inside bench-container, one pinned CPU, /work = pareto1 ~/sa-rust-ids-work/sa-port-354/s1 read-only, /results writable.
# Unprofiled timed rounds, each run a cold process (qt342.py, kind time: nothing wraps a function of witness.py, so the
# native path stays on); the arms alternate inside one invocation and the order rotates each round.
# Arms: SHA:MODE-WITNESS over the staged tree /work/bench-SHA/tree; MODE py (the package alone) or rust (the slice with
# SLICE_CONVERT=rust SLICE_TERM_FRAMES=rust, "both Rust switches on"); WITNESS off, on32 (SLICE_WITNESS=1, cap 32,
# Python's witness.py) or nat (on32 with SLICE_WITNESS_RUST=1: the native check). SLICE_WITNESS_WORK, SLICE_WITNESS_PLANT,
# SLICE_WITNESS_RUST_PLANT are unset in every arm and SLICE_WITNESS_RUST in every arm but nat.
# sympy, evalbench and data are one copy for every arm (/work/common).
# After the rounds: one wn354.py pass per workload and arm (the hook, counters 706-713 and the certified count as that
# arm's process read them; a count, not an S1 time).
R=/results; Q=/work/tools/qt342.py; C=/work/common
stamp() { echo "$1 $(date -u +%T)" >> $R/progress; }
mkdir -p /tmp/shim && ln -sfn $C/evalbench /tmp/shim/evalbench
env_of() { # env_of ARM: the environment of an arm
  sha=${1%%:*}; a=${1#*:}; m=${a%%-*}; w=${a##*-}; T=/work/bench-$sha/tree; cv=py; fr=py; [ $m = rust ] && { cv=rust; fr=rust; }
  sw=1; x=""; case $w in off) sw=0;; nat) x="SLICE_WITNESS_RUST=1 ";; esac
  echo "${x}SLICE_WITNESS=$sw SLICE_WITNESS_CAP=32 SLICE_CONVERT=$cv SLICE_TERM_FRAMES=$fr SLICE_DIR=$T/rust-spike/slice SA_EVAL_DATA=$C/data PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T:$C/sympy:/tmp/shim"
}
mode_of() { a=${1#*:}; echo ${a%%-*}; }
U="-u SLICE_WITNESS_WORK -u SLICE_WITNESS_PLANT -u SLICE_WITNESS_RUST -u SLICE_WITNESS_RUST_PLANT"
one() { # one ARM WL ROUND
  env $U $(env_of $1) python $Q $2 $(mode_of $1) time 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.pop('per',None); d.pop('ans',None)
for k in ('installed','session','term','lra'): d.pop(k,None)
d.update(arm='$1', round=$3); print(json.dumps(d))" >> $R/time.jsonl
}
stamp start
S="$ARMS"
{ python -VV; nproc; echo "ARMS $S ROUNDS $ROUNDS WLS $WLS"; cat /work/bench-*/SHA; sha256sum /work/bench-*/tree/rust-spike/slice/sa_solver.so /work/bench-*/tree/satassume/witness.py /work/bench-*/tree/satassume/engine.py /work/bench-*/tree/rust-spike/slice/witness_live.py $Q; } > $R/env.txt 2>&1
for r in $ROUNDS; do
  for wl in $WLS; do for s in $S; do one $s $wl $r; done; done
  S="${S#* } ${S%% *}"
  stamp "round $r"
done
for wl in $WLS; do for s in $ARMS; do
  env $U $(env_of $s) python /work/tools/wn354.py $wl $(mode_of $s) 2>> $R/err.txt | python -c "
import json,sys
d=json.loads(sys.stdin.read()); d.update(arm='$s'); print(json.dumps(d))" >> $R/wn.jsonl
done; done
stamp DONE
