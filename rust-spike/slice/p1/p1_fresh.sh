#!/bin/bash
# Fresh dev and fuzz, py and rust, shards; merged with the real totals, then livecmp. Exception probe after, Rust and Python.
O=$B/fresh2; mkdir -p $O; date -u >$O/start
$PY -c 'import satassume,sa_solver,hashlib; print(satassume.__file__, sa_solver.__file__, hashlib.sha256(open(sa_solver.__file__,"rb").read()).hexdigest())' >$O/tree.txt
J=8
for wl in dev fuzz; do
  N=$($PY -c "import live; print(len(live.load('$wl')))")
  for m in py rust; do for i in $(seq 0 $((J-1))); do
    only=$(seq $i $J $((N-1)) | paste -sd,)
    $PY live.py $wl $m $O/$wl-$m.s$i.jsonl --check entry --fork --only $only >$O/$wl-$m.s$i.tot 2>$O/$wl-$m.s$i.err &
  done; done
  wait
  for m in py rust; do $PY $HOME/merge_shards.py $O/$wl-$m.jsonl $O/$wl-$m.s?.jsonl >>$O/merge.txt; done
  $PY livecmp.py $O/$wl-py.jsonl $O/$wl-rust.jsonl >$O/$wl.cmp 2>&1
done
date -u >$O/done
X=$B/exc; mkdir -p $X
$PY except_probe.py dev $O/dev-py.jsonl $X/count.jsonl.counts $X/rust-once.jsonl --stride 5 >$X/rust-once.tally 2>$X/rust-once.err &
$PY except_probe.py dev $O/dev-py.jsonl $X/count.jsonl.counts $X/rust-persist.jsonl --stride 5 --persist >$X/rust-persist.tally 2>$X/rust-persist.err &
$PY except_probe.py dev $O/dev-py.jsonl $X/count.jsonl.counts $X/py-persist.jsonl --stride 5 --persist --py >$X/py-persist.tally 2>$X/py-persist.err &
wait
date -u >$X/done
