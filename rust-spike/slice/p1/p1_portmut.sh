#!/bin/bash
# port_mutants.py on dev, ground and fuzz, fresh, one workload's shards at a time, against the fresh Python rows. Under p1_job.sh.
OUT=${OUT:-$REAL/sa-rust-ids-work/sa-port-21/portmut}; mkdir -p $OUT; date -u >$OUT/start; J=${J:-6}
# lib.rs reaches the core by a relative #[path]: crate/src/../../.. is $OUT here
ln -sfn $S/../lra $OUT/lra
mkdir -p $OUT/so; $PY port_mutants.py build $OUT/so >$OUT/build.log 2>&1 || { echo build failed >$OUT/done; exit 1; }
for wl in dev ground fuzz; do
  ref=${REF:-$REAL/sa-rust-ids-work/sa-port-21/checks/fresh}/$wl-py.jsonl
  [ $wl = ground ] && ref=$B/ground/py.jsonl
  D=$OUT/$wl; mkdir -p $D
  N=$($PY -c "import live; print(len(live.load('$wl')))")
  for name in $($PY port_mutants.py list); do
    n=${name/:/_}; so=; [ -e $OUT/so/$n/sa_solver.so ] && so="--so $OUT/so/$n"
    for i in $(seq 0 $((J-1))); do
      only=$(seq $i $J $((N-1)) | paste -sd,)
      $PY port_mutants.py run $name $wl rust $D/$n.s$i.jsonl --check entry --fork --only $only $so >$D/$n.s$i.tot 2>$D/$n.s$i.err &
    done
    wait
    $PY $HOME/merge_shards.py $D/$n.jsonl $D/$n.s?.jsonl >/dev/null 2>>$D/merge.err
  done
  $PY port_mutants.py score $ref $D >$D/score.txt 2>&1
done
date -u >$OUT/done
