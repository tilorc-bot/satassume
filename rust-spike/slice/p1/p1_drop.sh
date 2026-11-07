#!/bin/bash
# The 27 drop: mutants with rows that survive the state read: dev (sa-port-12's items) and ground. Run under p1_job.sh.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-21/drop}; mkdir -p $OUT/dev $OUT/ground; date -u >$OUT/start
export PY OUT
cp $HOME/drop_in/drop_*.in $OUT/dev/; cp $B/ground/dm/drop_*.in $OUT/ground/ 2>/dev/null
for wl in dev ground; do
  ls $OUT/$wl/*.in | xargs -P 3 -I{} bash -c 'f={}; n=$(basename $f .in); m=$(echo $n | sed "s/_/:/"); $PY dump_mutants.py run $m '$wl' $f $OUT/'$wl'/$n.jsonl >$OUT/'$wl'/$n.tot 2>$OUT/'$wl'/$n.err'
done
$PY dump_mutants.py score $B/fresh2/dev-py.jsonl $OUT/dev >$OUT/dev/score.txt 2>&1
$PY dump_mutants.py score $B/ground/py.jsonl $OUT/ground >$OUT/ground/score.txt 2>&1
date -u >$OUT/done
