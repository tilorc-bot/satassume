#!/bin/bash
# run-audit.sh OUTDIR: audit.py over hash seeds and query orders (no timing)
. ~/sa-rust-ids-work/env.sh; export PYTHONPATH
cd ~/dev/sa-rust
for wl in dev fuzz; do
  for spec in "0 0" "1 0" "2 0" "0 1" "0 2"; do
    set -- $spec
    PYTHONHASHSEED=$1 $PY rust-spike/slice/audit.py $wl $2 "$OUTDIR/$wl-h$1-s$2.json" > "$OUTDIR/$wl-h$1-s$2.log" 2>&1 &
  done
done
wait
