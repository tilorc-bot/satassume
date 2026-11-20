#!/bin/bash
# job352a.sh OUT (sa-port-352, orion, detached, 4 at once; not a timing): item 3's per-query comparison on the worktree's
# tree and .so: diff352.py arms diff, native and python on the gate's 20 workloads and on evalbench's fuzz seeds 0 1 2 42,
# then cmp352.py native against python per workload                                      -> OUT/WL-ARM.{json,jsonl,err}, cmp.txt
# End marker: OUT/end.txt, the last line here.
D=$(cd "$(dirname "$0")" && pwd); export D OUT=$1; mkdir -p $OUT
WLS="lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls fuzz0 fuzz1 fuzz2 fuzz42"
for wl in $WLS; do for arm in diff native python; do echo "$wl $arm"; done; done > $OUT/todo.txt
xargs -P 4 -L 1 bash -c 'wl=$0; arm=$1; n=$(echo $wl | tr -d :); f=$OUT/$n-$arm
  $D/run352.sh $wl $arm $f.jsonl > $f.json 2> $f.err; echo "$? $wl $arm" >> $OUT/rc.txt' < $OUT/todo.txt
. ~/sa-rust-ids-work/env.sh
for wl in $WLS; do n=$(echo $wl | tr -d :); echo "$wl $($PY $D/cmp352.py $OUT/$n-native.jsonl $OUT/$n-python.jsonl 2>&1 | tail -1)"; done > $OUT/cmp.txt
echo "END $(date -u +%FT%TZ) load $(cut -d' ' -f1-3 /proc/loadavg)" > $OUT/end.txt
