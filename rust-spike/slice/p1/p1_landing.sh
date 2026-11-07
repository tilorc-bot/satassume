#!/bin/bash
# Everything counted for landing, on the rebased source, one after another so nothing rebuilds under a loaded .so.
# Run under p1_job.sh. Each part writes OUT/PART/done; OUT/done is last. `rsync` this tree first and check OUT/tree.txt.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-34/land}; mkdir -p $OUT; date -u >$OUT/start
J=${J:-6}
shards() { # dir wl mode: live.py --fork in J shards, merged
  d=$1; wl=$2; m=$3
  N=$($PY -c "import live; print(len(live.load('$wl')))")
  for i in $(seq 0 $((J-1))); do
    only=$(seq $i $J $((N-1)) | paste -sd,)
    $PY live.py $wl $m $d/$wl-$m.s$i.jsonl --check entry --fork --only $only >$d/$wl-$m.s$i.tot 2>$d/$wl-$m.s$i.err &
  done
  wait
  $PY $HOME/merge_shards.py $d/$wl-$m.jsonl $d/$wl-$m.s?.jsonl >>$d/merge.txt
  cat $d/$wl-$m.s?.jsonl.handlers >$d/$wl-$m.jsonl.handlers 2>/dev/null
}
# 1. Suite, Rust then Python. It builds, so the .so below is this tree's.
OUT=$OUT/suite bash $S/p1/p1_suite.sh
$PY -c 'import satassume,sa_solver,hashlib; print(satassume.__file__, sa_solver.__file__, hashlib.sha256(open(sa_solver.__file__,"rb").read()).hexdigest())' >$OUT/tree.txt
# 2. Fresh, all four workloads
F=$OUT/fresh; mkdir -p $F
for wl in dev fuzz ground port; do
  for m in py rust; do shards $F $wl $m; done
  $PY livecmp.py $F/$wl-py.jsonl $F/$wl-rust.jsonl >$F/$wl.cmp 2>&1
done
date -u >$F/done
# 3. Forced moves, with the counter: every call on dev and ground, every 16th on fuzz
M=$OUT/mv; mkdir -p $M
for spec in dev:1 ground:1 fuzz:16; do
  wl=${spec%:*}; st=${spec#*:}; echo "$wl stride $st" >>$M/stride.txt
  $PY move_every_call.py count $wl $M/$wl-count.jsonl >$M/$wl-count.tot 2>$M/$wl-count.err
  for i in $(seq 0 $((J-1))); do
    $PY move_every_call.py run $wl $M/$wl-count.jsonl.counts $M/$wl.s$i.jsonl --shard $i/$J --stride $st >$M/$wl.s$i.tot 2>$M/$wl.s$i.err &
  done
  wait
  $PY move_every_call.py cmp $F/$wl-py.jsonl $M/$wl.s?.jsonl >$M/$wl.cmp 2>&1
done
date -u >$M/done
# 4. Planted bugs in the port, on all four
OUT=$OUT/portmut REF=$F WLS="dev ground fuzz port" bash $S/p1/p1_portmut.sh
# 5. History and hash seeds
H=$OUT/hist
bash $S/run_history.sh $H $J >$OUT/hist.out 2>&1
$PY historycmp.py $H >$H/cmp.txt 2>&1
date -u >$H/done
date -u >$OUT/done
